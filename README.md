# Text-to-3D over SMS 📱→🧊

**Text a phone number a description of a 3D scene. A team of AI agents builds it,
critiques the render, refines it, and texts you back a link to the image — plus a
game-ready `.glb` you can drop straight into Unity / Unreal / Godot / Three.js.
Reply to keep editing it by text.**

> Assignment 4 · Exercise 1 (multiple agents, freestyle).
> Required ingredients: **PydanticAI** multi-agent + **Saperly** (phone carrier
> for AI agents). Both are core to the design below.

---

## Why it's cool

- You **SMS** plain language ("a red sports car next to a palm tree on a beach")
  and a real 3D model comes back to your phone seconds later.
- It's a **conversation**: reply "make the car blue, bigger wheels" and it edits.
- The output isn't just a picture — it's a **reusable `.glb` asset**, recentered
  and grounded, ready for a game engine. That's the difference between a gimmick
  and a tool.
- No Blender, no GPU farm: the **browser's WebGL is the renderer**.

## How it works

```
 You ──SMS──▶ Saperly ──webhook──▶ FastAPI
                                     │
        ┌───────────── RouterAgent (new? edit? chat?) ───────────┐
        │                                                        │
        ▼                                                        ▼
   IntentAgent ──▶ SceneSpec (typed) ──▶ headless Chromium + Three.js
        ▲                                   ├─ screenshot ─▶ render.png
        │                                   └─ GLTFExporter ─▶ model.glb
        │                                          │
        └──── VisionCritic ◀── looks at render.png ┘   (loop, capped)
                                                        │
 You ◀──SMS── link  ◀──────────────── FastAPI ◀────────┘
                       + live web dashboard / viewer page
```

### The three agents (PydanticAI)

| Agent | Module | Job | Output |
|-------|--------|-----|--------|
| **RouterAgent** | [router.py](app/agents/router.py) | Triage the SMS: build new / edit current / just chat | `Route` |
| **IntentAgent** | [intent.py](app/agents/intent.py) | Turn text into a typed scene of primitives; apply edits | `SceneSpec` |
| **VisionCritic** | [critic.py](app/agents/critic.py) | *Look at the render* and propose concrete fixes | `Critique` |

They collaborate via a programmatic hand-off in [pipeline.py](app/pipeline.py):
Router → Intent → render → Critic → (refine) → … capped at `MAX_ITERATIONS`.
The shared contract is one Pydantic model, [`SceneSpec`](app/models/scene.py).

### Saperly (phone carrier for AI agents)

[saperly.py](app/messaging/saperly.py) talks to the Saperly REST API: send SMS,
resolve our line, record outbound consent, and configure the inbound webhook.
The published pip package isn't installable, so we integrate the documented REST
API directly with `httpx`.

## Project structure

```
app/
  config.py            # settings from .env
  models/scene.py      # SceneSpec / Obj / Critique  (the shared contract)
  agents/              # router.py, intent.py, critic.py
  rendering/renderer.py# headless Chromium -> PNG + .glb
  messaging/saperly.py # Saperly REST client
  server/api.py        # FastAPI: webhook, viewer, dashboard, static
  pipeline.py          # the multi-agent build loop
  state.py             # in-memory per-sender sessions
web/
  scene.html           # Three.js scene + GLTFExporter (vendored three.js)
  viewer.html          # phone page: render + Download .glb
  dashboard.html       # live grid of all sessions
tests/                 # offline model + render tests
```

## Setup

```bash
uv venv --python 3.13
uv pip install -e .
uv run playwright install chromium

cp .env.example .env        # then fill in the keys
```

`.env`:

```
OPENAI_API_KEY=sk-...           # the agents' model (gpt-4o, vision-capable)
SAPERLY_API_KEY=sk_live_...     # your Saperly line
SAPERLY_PHONE_NUMBER=+1...      # the line's number (line_id auto-resolved)
PUBLIC_URL=                     # set to your ngrok https URL (below)
```

## Run it

```bash
# 1) start the server
uv run uvicorn app.server.api:app --port 8000

# 2) expose it publicly (inbound SMS webhook needs a public URL)
ngrok http 8000        # copy the https URL into PUBLIC_URL, restart server

# 3) point the Saperly line's webhook at it (one-time, via API)
uv run python -m scripts.set_webhook   # PATCHes webhook_url = $PUBLIC_URL/sms/incoming
```

Then **text your Saperly number** a scene. Watch the dashboard at
`http://localhost:8000/` while the reply lands on your phone.

## Tests

```bash
uv run pytest -q     # offline: schema parsing + a real render -> valid .glb
```

## Notes / limitations

- Scenes are composed from primitives (box/sphere/cylinder/cone/torus/plane), so
  results are stylized/low-poly — great for game props, not photoreal.
- $5 Saperly credit ≈ ~250 SMS. Outbound needs prior inbound or a consent record
  (we handle consent in `record_consent`).
- Voice input is a natural next step (Saperly does voice too) — left as a stretch.
