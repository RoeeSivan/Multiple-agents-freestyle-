# CLAUDE.md — Text-to-3D over SMS

Project context for AI agents working in this repo. See [README.md](README.md) for the user-facing version.

## What this is

Assignment 4 · Exercise 1 (multiple agents, freestyle). **Text a phone number a
description of a 3D scene → PydanticAI agents build it, a vision agent critiques
the render and refines → you get an SMS link to the image + a game-ready `.glb`.
Reply to keep editing by text.** Hard requirements: **PydanticAI multi-agent** +
**Saperly** (phone carrier for AI agents) + a wow factor.

## Architecture

Inbound SMS → Saperly webhook → FastAPI → multi-agent loop → reply with link.

Three PydanticAI agents share one typed contract (`SceneSpec`):
- **RouterAgent** [app/agents/router.py](app/agents/router.py) — triage: `new` / `edit` / `chat`.
- **IntentAgent** [app/agents/intent.py](app/agents/intent.py) — text → `SceneSpec` (composes objects from primitives); also applies edits.
- **VisionCritic** [app/agents/critic.py](app/agents/critic.py) — *looks at the rendered PNG* → `Critique` with concrete fixes.

Programmatic hand-off loop in [app/pipeline.py](app/pipeline.py): Router → Intent → render → Critic → (refine) → … capped at `MAX_ITERATIONS` (default 3). VisionCritic is tuned to **converge** (accept recognizable stylized results), not chase photorealism.

Rendering [app/rendering/renderer.py](app/rendering/renderer.py): **no Blender** — a headless Chromium (Playwright) loads [web/scene.html](web/scene.html) (vendored Three.js), screenshots the canvas to PNG, and exports the content group to a binary `.glb` via `GLTFExporter`. The glb is recentered to origin + dropped to ground at export (game-ready).

Saperly [app/messaging/saperly.py](app/messaging/saperly.py): REST via httpx (the pip package is not actually installable). Base `https://saperly.com/api/v1`, Bearer auth. send_sms / resolve_line_id / record_consent / update_line.

Server [app/server/api.py](app/server/api.py): `POST /sms/incoming` webhook, `/v/{sid}` viewer, `/` dashboard, `/api/state`, static `/out`. Per-sender state in [app/state.py](app/state.py) (in-memory).

## Run

```bash
uv venv --python 3.13 && uv pip install -e . && uv run playwright install chromium
uv run pytest -q                                   # offline: schemas + render -> glb
uv run uvicorn app.server.api:app --port 8000      # server
cloudflared tunnel --url http://127.0.0.1:8000     # public tunnel (ngrok not authed on this machine)
# put the https URL in .env PUBLIC_URL, restart server, then:
uv run python -m scripts.set_webhook               # PATCH Saperly line webhook_url
```

## Conventions / gotchas

- **Model:** `openai:gpt-4o` (vision-capable — the critic needs it). Key `OPENAI_API_KEY`. The user chose OpenAI over Anthropic.
- **Secrets:** `.env` is gitignored and holds the live Saperly key + OpenAI key. Never commit it; always check `git diff --cached --name-only` excludes `.env` before committing.
- **Commit frequently with meaningful messages** (assignment grades this). Private GitHub repo; invite user `dk8827`.
- **scene.html must be served over http** (not file://) — ES-module + importmap is CORS-blocked on file://. The renderer spins a localhost http server for this.
- **Metals/glass need an env map** — `RoomEnvironment` + PMREM in scene.html, else metal renders near-black.
- **Don't name a module `app.py` inside a package that also exports an `app` var** — caused a shadowing bug; the FastAPI module is `server/api.py`.
- **Saperly outbound** needs prior inbound (24h) or a consent record. Inbound-first flow auto-authorizes replies.
- **Chat style:** caveman mode is active in conversation; code/commits/PRs written normally.

## Status / next

Live and tested end-to-end (SMS in → render + glb out). Planned next: a **build
timeline** UI — keep each refine pass's image + show the critic's feedback per
pass, so the demo video visibly shows the agents improving the model.
