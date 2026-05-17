"""
Drive the real Neon Highway game (Three.js) with our trained model.

Flow:
  1. Spawn a quiet local HTTP server pointing at `web_game/`.
  2. Launch a headed Chromium via Playwright with video recording on.
  3. Wait for the page's bridge.js to install `window.gameState()`.
  4. Click MUTE + START, wait until the game's phase flips to 'playing'.
  5. Loop: poll state → 16-d observation → model.predict → send key.
  6. Stop when phase != 'playing' (game over / win).
  7. Save the recorded .webm to the requested path (or print where it
     landed if no path given).

Caveats vs. the Python clone the model trained on:
  * Real game uses Math.random() for lane-random spawns (bird/drone/
    bolt/heart/coin); the clone uses seeded numpy. Patterns (the 12
    green/red sequences) are identical.
  * Real game uses variable dt; clone is fixed 1/60. At 60 fps in a
    desktop browser the gap is small, but be aware the model may
    miss things it would catch in simulation.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Optional

import numpy as np

from .observe_web import observe_web
from .serve import start_server


# Map our 4-way action space to keyboard keys the game listens for.
# main.js:50-51 wires ArrowLeft/Right + A/D and Space.
_ACTION_TO_KEY = {
    1: "ArrowLeft",
    2: "ArrowRight",
    3: "Space",
}

# Match the lane-change cooldown the trained net was used to in the
# Python clone (6 frames @ 60 fps = 100 ms).
_LANE_COOLDOWN_S = 0.10

# How often we tick. 50 ms = 20 Hz. The game itself still updates at
# 60 fps; we're just sampling state and pushing keys at 20 Hz which
# is plenty for lane reactions.
_LOOP_INTERVAL_S = 0.05


def drive_web(
    genome_path: str,
    port: int = 8765,
    record_path: Optional[str] = None,
    max_duration_s: float = 360.0,
    headless: bool = False,
    web_game_dir: str = "web_game",
    events_path: Optional[str] = None,
    capture_audio_events: bool = True,
) -> None:
    # Defer heavy imports so the env var KERAS_BACKEND set in main.py
    # actually takes effect.
    import keras
    from nn.model import predict_action
    from playwright.sync_api import sync_playwright

    web_root = str(Path(web_game_dir).resolve())
    if not Path(web_root, "index.html").is_file():
        raise FileNotFoundError(f"no index.html under {web_root}")

    model = keras.models.load_model(genome_path)
    httpd = start_server(web_root, port=port)
    print(f"[drive-web] model loaded — serving {web_root} on :{port}")

    video_dir = Path("logs/web_videos")
    video_dir.mkdir(parents=True, exist_ok=True)

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=headless,
                # Some Chromium audio quirks bite in headless; mute via flag
                # too in addition to clicking MUTE.
                args=["--mute-audio", "--autoplay-policy=no-user-gesture-required"],
            )
            ctx = browser.new_context(
                viewport={"width": 1280, "height": 800},
                record_video_dir=str(video_dir),
                record_video_size={"width": 1280, "height": 800},
            )
            page = ctx.new_page()

            if capture_audio_events:
                # Seed the audio capture hook before any web_game JS runs.
                # audio.js reads these globals to push event metadata.
                page.add_init_script(
                    "window.__audioCaptureEnabled = true;"
                    "window.__audioLog = [];"
                    "window.__clipT0 = performance.now();"
                )

            page.goto(f"http://127.0.0.1:{port}/")
            page.wait_for_function("window.__bridgeReady === true", timeout=15000)
            print("[drive-web] bridge ready")

            # Mute audio + start the game.
            try:
                page.click("#btn-mute", timeout=2000)
            except Exception:
                pass  # nice-to-have, don't fail the run
            page.click("#btn-start")
            page.wait_for_function(
                "window.gameState() && window.gameState().phase === 'playing'",
                timeout=15000,
            )
            print("[drive-web] phase=playing — model driving")

            _control_loop(
                page,
                model,
                predict_action,
                max_duration_s=max_duration_s,
            )

            # Capture final stats before the page is closed.
            final = page.evaluate("window.gameState()")
            print(
                f"[drive-web] phase={final['phase']} "
                f"score={final['score']} lives={final['lives']} "
                f"level={final['level']} elapsed={final['elapsed']:.1f}s"
            )

            audio_log = []
            if capture_audio_events:
                try:
                    audio_log = page.evaluate("window.__audioLog || []")
                except Exception as e:
                    print(f"[drive-web] could not read audio log: {e}")

            video_path_raw = page.video.path() if page.video else None
            ctx.close()  # flushes the video
            browser.close()
    finally:
        httpd.shutdown()

    # Move/rename the auto-generated .webm to the caller-supplied path.
    final_clip: Optional[Path] = None
    if record_path and video_path_raw:
        dst = Path(record_path)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(video_path_raw, dst)
        final_clip = dst
        print(f"[drive-web] video saved to {dst}")
    elif video_path_raw:
        final_clip = Path(video_path_raw)
        print(f"[drive-web] video saved to {video_path_raw}")

    if capture_audio_events:
        if events_path is not None:
            ev_dst = Path(events_path)
        elif final_clip is not None:
            ev_dst = final_clip.with_suffix(final_clip.suffix + ".events.json")
        else:
            ev_dst = None
        if ev_dst is not None:
            ev_dst.parent.mkdir(parents=True, exist_ok=True)
            ev_dst.write_text(json.dumps(audio_log))
            print(f"[drive-web] audio events ({len(audio_log)}) → {ev_dst}")


def _control_loop(page, model, predict_action_fn, *, max_duration_s: float) -> None:
    """Tick at ~20 Hz: read state, predict action, send key."""
    t_start = time.monotonic()
    last_lane_change = 0.0
    actions_sent = 0
    no_state_strikes = 0

    while True:
        if time.monotonic() - t_start > max_duration_s:
            print("[drive-web] max_duration_s reached — stopping")
            return

        state = page.evaluate("window.gameState ? window.gameState() : null")
        if state is None:
            # Page navigated or bridge missing — bail out quickly.
            no_state_strikes += 1
            if no_state_strikes > 5:
                print("[drive-web] bridge gone — stopping")
                return
            time.sleep(_LOOP_INTERVAL_S)
            continue
        no_state_strikes = 0

        if state["phase"] != "playing":
            print("[drive-web] phase changed — stopping loop")
            return

        obs = observe_web(state)
        action = predict_action_fn(model, obs)

        if action in _ACTION_TO_KEY:
            now = time.monotonic()
            is_lane = action in (1, 2)
            if is_lane and (now - last_lane_change) < _LANE_COOLDOWN_S:
                pass  # skip — still in cooldown
            else:
                page.keyboard.press(_ACTION_TO_KEY[action])
                actions_sent += 1
                if is_lane:
                    last_lane_change = now

        time.sleep(_LOOP_INTERVAL_S)
