# Text-to-3D over SMS 📱→🧊

**Text a phone number a description of a 3D scene. A team of AI agents models it
in a live Blender — writing the geometry itself, critiquing the render, and
reshaping — then texts you back a link to the image, plus a game-ready `.glb` you
can drop straight into Unity / Unreal / Godot / Three.js. Reply to keep editing
it by text.**

> Assignment 4 · Exercise 1 (multiple agents, freestyle).
> Required ingredients: **PydanticAI** multi-agent + **Saperly** (phone carrier
> for AI agents). Both are core to the design below.

---

## Why it's cool

- You **SMS** plain language ("a red sports car next to a palm tree") and a 3D
  model comes back to your phone.
- The geometry is **created by the AI itself**: the BuilderAgent writes Blender
  Python (modifiers, subdivision, bevel, joins, materials) to model each object —
  nothing is imported from an asset library.
- It's a **conversation**: reply "make the car blue, bigger wheels" and it edits
  the live scene.
- The output isn't just a picture — it's a **reusable `.glb` asset**, recentered
  and dropped to the ground, ready for a game engine.
- The agent literally **drives Blender through MCP**: the prompt goes straight to
  Blender via the blender-mcp toolset, and the **VisionCritic** loops on the render
  to reshape until it reads right.

## How it works

```
 You ──SMS──▶ Saperly ──webhook──▶ FastAPI
                                     │
   ┌──────── RouterAgent (new? edit? chat?) ────────┐
   │                                                │
   │   InfoAgent ── (one question if too vague) ─┐  │
   ▼                                             ▼  ▼
 PlannerAgent ──▶ BuildSpec (typed) ──▶ BuilderAgent ──MCP──▶ live Blender
        ▲                                  │  ├─ execute_blender_code: model + shape
        │                                  │  ├─ modifiers / join / materials
        │                                  │  └─ PolyHaven HDRI (optional lighting)
        │                                  ▼
        │                          render.png ──┐
        └──── VisionCritic ◀── looks at it ◀────┘   (reshape loop, capped)
                                                 │
 You ◀──SMS── link ◀────────── FastAPI ◀─────────┘  + export model.glb
                       + live web dashboard / viewer page
```

### The agents (PydanticAI)

| Agent | Module | Job | Output |
|-------|--------|-----|--------|
| **RouterAgent** | [router.py](app/agents/router.py) | Triage the SMS: build new / edit current / just chat | `Route` |
| **InfoAgent** | [info.py](app/agents/info.py) | Ask **one** clarifying question only when a request is genuinely too vague | `Clarification` |
| **PlannerAgent** | [intent.py](app/agents/intent.py) | Decompose text into distinct objects, each a vivid text-to-3D prompt + hints | `BuildSpec` |
| **BuilderAgent** | [builder.py](app/agents/builder.py) | **Model** each object in a **live Blender** by writing bpy via the blender-mcp toolset | `BuildReport` |
| **VisionCritic** | [critic.py](app/agents/critic.py) | *Look at the render* and say how to reshape | `Critique` |

They collaborate via a programmatic hand-off in [pipeline.py](app/pipeline.py):
Planner → Builder → render → Critic → (refine via Builder) → … capped at
`MAX_ITERATIONS`. The shared contract is one Pydantic model,
[`BuildSpec`](app/models/scene.py).

### Geometry backend (Blender MCP)

The BuilderAgent **models each object itself** — writing Blender Python through
the blender-mcp `execute_blender_code` tool (primitives shaped with modifiers,
joined, materialed, seated on the ground). [blender_io.py](app/rendering/blender_io.py)
handles only the deterministic steps around it over the BlenderMCP socket: clear
the scene, a camera-framed **Eevee** render for the critic, and a recentered,
ground-dropped `.glb` export with modifiers baked in (`export_apply=True`; Blender
Z-up → glTF Y-up). Same technique as a sibling Three.js game project's
`blender/*.py` scripts (Claude writing bpy), but live over MCP and looped by the
critic.

### Saperly (phone carrier for AI agents)

[saperly.py](app/messaging/saperly.py) talks to the Saperly REST API: send SMS,
resolve our line, record outbound consent, and configure the inbound webhook. The
published pip package isn't installable, so we integrate the REST API directly
with `httpx`.

## Project structure

```
app/
  config.py             # settings from .env (incl. Blender host/port)
  models/scene.py       # BuildSpec / ObjectBrief / Clarification / BuildReport / Critique
  agents/               # router.py, info.py, intent.py (planner), builder.py, critic.py
  rendering/blender_io.py # Blender MCP socket I/O: run bpy, render, .glb export
  rendering/geometry_audit.py # deterministic scene measurement (no LLM)
  messaging/saperly.py  # Saperly REST client
  server/api.py         # FastAPI: webhook, viewer, dashboard, static
  pipeline.py           # the multi-agent build loop
  state.py              # in-memory per-sender sessions
web/
  viewer.html           # phone page: render + Download .glb
  dashboard.html        # live grid of all sessions
scripts/
  blender_smoke.py      # end-to-end Rodin build check (no LLM/SMS)
  set_webhook.py        # point the Saperly line's webhook at this server
tests/                  # offline schema tests + a Blender render test (auto-skips)
```

## Setup

You need **Blender** open with the [BlenderMCP](https://github.com/ahujasid/blender-mcp)
addon:

1. Install the addon, open the **BlenderMCP** panel (press `N` in the 3D
   viewport), click **Connect to MCP server** (socket on port 9876).
2. (Optional) Check **Use assets from Poly Haven** so the builder can pull a free
   HDRI for nicer lighting. No paid keys are needed — the AI models the geometry
   itself.

```bash
uv venv --python 3.13
uv pip install -e .

cp .env.example .env        # then fill in the keys
```

`.env`:

```
OPENAI_API_KEY=sk-...           # the agents' model (gpt-4o, vision-capable)
SAPERLY_API_KEY=sk_live_...     # your Saperly line
SAPERLY_PHONE_NUMBER=+1...      # the line's number (line_id auto-resolved)
PUBLIC_URL=                     # set to your tunnel https URL (below)
# optional: BLENDER_HOST / BLENDER_PORT (default 127.0.0.1:9876)
```

## Run it

```bash
# 0) sanity-check the Blender backend end-to-end (real Rodin generation)
uv run python -m scripts.blender_smoke "a red sports car"

# 1) start the server
uv run uvicorn app.server.api:app --port 8000

# 2) expose it publicly (inbound SMS webhook needs a public URL)
cloudflared tunnel --url http://127.0.0.1:8000   # copy https URL into PUBLIC_URL, restart

# 3) point the Saperly line's webhook at it (one-time, via API)
uv run python -m scripts.set_webhook   # PATCHes webhook_url = $PUBLIC_URL/sms/incoming
```

Then **text your Saperly number** a scene. Watch the dashboard at
`http://localhost:8000/` while the reply lands on your phone.

## Tests

```bash
uv run pytest -q   # schema tests + a Blender cube render→.glb (skips if Blender is down)
```

## Notes / limitations

- **One Blender, one scene** — builds are serialized; this is a single-user demo,
  not a concurrent service.
- **Quality is stylized**, not photoreal — the AI models from primitives +
  modifiers, and the VisionCritic loop reshapes until the render reads right. A
  build takes ~tens of seconds, so the server texts a "building…" ack first, then
  the link when done.
- $5 Saperly credit ≈ ~250 SMS. Outbound needs prior inbound or a consent record
  (handled in `record_consent`).
- Voice input is a natural next step (Saperly does voice too) — left as a stretch.
```
