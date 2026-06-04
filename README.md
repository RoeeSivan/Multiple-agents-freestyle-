# Text-to-3D over SMS 📱→🧊

**Text a phone number a description of a 3D scene. A team of AI agents models it
in a live Blender — writing the geometry itself, grounding on real reference
photos, critiquing the render, and reshaping — then texts you back a link to the
image, plus a game-ready `.glb` you can drop straight into Unity / Unreal / Godot
/ Three.js. Reply to keep editing it by text.**

> Assignment 4 · Exercise 1 (multiple agents, freestyle).
> Required ingredients: **PydanticAI** multi-agent + **Saperly** (phone carrier
> for AI agents). Both are core to the design below.

---

## Why it's cool

- You **SMS** plain language ("a red soccer ball", "a wooden chair") and a 3D
  model comes back to your phone.
- The geometry is **created by the AI itself**: the BuilderAgent writes Blender
  Python (modifiers, subdivision, bevel, joins, materials) to model each object —
  nothing is imported from an asset library.
- It's **grounded in reality**: a ReferenceAgent pulls real product photos + real
  dimensions off the web so proportions and size are accurate, and a deterministic
  geometry audit checks the built mesh with exact numbers (no vision cost).
- **Color you ask for is the color you get**: say "a *red* soccer ball" and it
  comes back red even though real soccer balls are white/black — an explicitly
  requested color/finish overrides the reference photo.
- It's a **conversation**: reply "make the car blue, bigger wheels" and it edits
  the live scene.
- The output isn't just a picture — it's a **reusable `.glb` asset**, recentered
  and dropped to the ground, ready for a game engine, plus an orbiting **turntable
  mp4** preview.
- You can even **build from your OWN photos**: for personal/specific objects the
  system texts you an upload link, you snap a few angles, and it models toward them.

## Prerequisites

**Always required (local build path):**

| Need | Notes |
|------|-------|
| **macOS / Linux / Windows** | Developed on macOS (darwin). |
| **Python 3.11+** | 3.13 used in dev. |
| **[uv](https://docs.astral.sh/uv/)** | Package/venv manager (`brew install uv`). Brings `uvx`, which spawns the `blender-mcp` server. |
| **Blender 4.x+** | Open, with the **[BlenderMCP](https://github.com/ahujasid/blender-mcp)** addon installed and **Connect to MCP server** clicked (socket on `:9876`). The AI talks to this live Blender. |
| **OpenAI API key** | Model `gpt-4o` (vision-capable — the critic needs it). Set `OPENAI_API_KEY`. |
| **Internet** | The ReferenceAgent web-grounds via DuckDuckGo (keyless, no paid key). |

**Additionally required for the live SMS demo:**

| Need | Notes |
|------|-------|
| **Saperly account + line** | `SAPERLY_API_KEY` + `SAPERLY_PHONE_NUMBER`. Phone carrier for AI agents; carries the inbound/outbound SMS. |
| **[cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)** | Public HTTPS tunnel so Saperly's webhook can reach your local server, and so the SMS link opens on a phone (`brew install cloudflared`). |

**Optional:**

| Need | Notes |
|------|-------|
| **ffmpeg** on the host | Encodes the turntable PNG sequence → mp4 (`brew install ffmpeg`). Absent → the build skips the mp4, everything else still works. |
| **Poly Haven** (in the addon) | Tick **Use assets from Poly Haven** to let the builder pull a free HDRI for nicer lighting. No key needed. |

> No paid 3D-generation service is used — the AI models the geometry itself. The
> only paid key is OpenAI (and a Saperly line for the live SMS path).

## How it works

```
 You ──SMS──▶ Saperly ──webhook──▶ FastAPI
                                     │
   ┌──────── RouterAgent (new? edit? chat?) ────────┐
   │                                                │
   │   InfoAgent ── (one question if too vague) ─┐  │
   ▼                                             ▼  ▼
 PlannerAgent ──▶ BuildSpec (typed) ──▶ BuilderAgent ──MCP──▶ live Blender
        ▲           │                     │  ├─ execute_blender_code: model + shape
        │           │                     │  ├─ modifiers / join / materials
        │   ReferenceAgent (real photos   │  └─ PolyHaven HDRI (optional lighting)
        │   + real dims, per object) ─────┘            │
        │                                  render 5 views ─┐
        │                          + geometry audit (exact)│
        └──── VisionCritic ◀── looks at it ◀───────────────┘  (reshape loop, capped)
                                                 │
 You ◀──SMS── link ◀────────── FastAPI ◀─────────┘  + export model.glb + turntable.mp4
                       + live web dashboard / viewer page
```

### The agents (PydanticAI)

| Agent | Module | Job | Output |
|-------|--------|-----|--------|
| **RouterAgent** | [router.py](app/agents/router.py) | Triage the SMS: build new / edit current / just chat | `Route` |
| **InfoAgent** | [info.py](app/agents/info.py) | Ask **one** clarifying question only when a request is genuinely too vague | `Clarification` |
| **PlannerAgent** | [intent.py](app/agents/intent.py) | Decompose text into distinct objects, each broken into structured parts + proportions + symmetry + a captured color/finish | `BuildSpec` |
| **ViewPlanner** | [photoplan.py](app/agents/photoplan.py) | Decide, per object, whether to ask the user for their own photos and which views | `PhotoPlan` |
| **ReferenceAgent** | [reference.py](app/agents/reference.py) | Web-ground each object: real product photos + real dimensions/facts | `Reference` |
| **BuilderAgent** | [builder.py](app/agents/builder.py) | **Model** each object in a **live Blender** by writing bpy via the blender-mcp toolset | `BuildReport` |
| **VisionCritic** | [critic.py](app/agents/critic.py) | *Look at 5 rendered views* + the reference and say how to reshape | `Critique` |

They collaborate via a programmatic hand-off in [pipeline.py](app/pipeline.py):
Planner → ReferenceAgent (per object) → Builder → 5-view render + geometry audit →
Critic → (refine via Builder) → … capped at `MAX_ITERATIONS`. It **converges only
when the critic AND the deterministic audit both pass**. The shared contract is one
Pydantic model, [`BuildSpec`](app/models/scene.py).

### Geometry backend (Blender MCP)

The BuilderAgent **models each object itself** — writing Blender Python through
the blender-mcp `execute_blender_code` tool (primitives shaped with modifiers,
joined, materialed, seated on the ground). [blender_io.py](app/rendering/blender_io.py)
handles only the deterministic steps around it over the BlenderMCP socket: clear
the scene, camera-framed **Eevee** renders (a `Standard` view transform so set
colors render true, a 3-point sun rig + ambient occlusion), and a recentered,
ground-dropped `.glb` export with modifiers baked in (`export_apply=True`; Blender
Z-up → glTF Y-up). [geometry_audit.py](app/rendering/geometry_audit.py) measures
the live scene (size/scatter/empty checks) with no LLM and feeds exact fixes back.

### Saperly (phone carrier for AI agents)

[saperly.py](app/messaging/saperly.py) talks to the Saperly REST API: send SMS,
resolve our line, record outbound consent, and configure the inbound webhook. The
published pip package isn't installable, so we integrate the REST API directly
with `httpx`.

## Project structure

```
app/
  config.py             # settings from .env (incl. Blender host/port)
  models/scene.py       # BuildSpec / ObjectBrief / Reference / Critique / GeometryAudit / ...
  agents/               # router, info, intent (planner), photoplan, reference, builder, critic
  rendering/blender_io.py # Blender MCP socket I/O: run bpy, render, .glb + turntable export
  rendering/geometry_audit.py # deterministic scene measurement (no LLM)
  messaging/saperly.py  # Saperly REST client
  server/api.py         # FastAPI: SMS webhook, viewer, dashboard, photo-upload intake, static
  pipeline.py           # the multi-agent build loop
  state.py              # in-memory per-sender sessions (+ photo intake)
web/
  viewer.html           # phone page: render + Download .glb
  upload.html           # mobile photo-upload wizard (build-from-my-photos)
  dashboard.html        # live grid of all sessions
scripts/
  blender_smoke.py      # end-to-end agentic build check (no SMS) → png + glb
  photo_intake_smoke.py # de-risk the build-from-photos path
  set_webhook.py        # point the Saperly line's webhook at this server
tests/                  # offline schema/HTTP tests + a Blender render test (auto-skips)
```

## Setup

1. Open **Blender**, install the [BlenderMCP](https://github.com/ahujasid/blender-mcp)
   addon, open the **BlenderMCP** panel (press `N` in the 3D viewport), and click
   **Connect to MCP server** (socket on port 9876).
2. (Optional) Tick **Use assets from Poly Haven** for a free HDRI.

```bash
uv venv --python 3.13
uv pip install -e .

cp .env.example .env        # then fill in the keys
```

`.env`:

```
OPENAI_API_KEY=sk-...           # the agents' model (gpt-4o, vision-capable)
SAPERLY_API_KEY=sk_live_...     # your Saperly line (live SMS path only)
SAPERLY_PHONE_NUMBER=+1...      # the line's number (line_id auto-resolved)
PUBLIC_URL=                     # set to your tunnel https URL (below)
# optional: BLENDER_HOST / BLENDER_PORT (default 127.0.0.1:9876)
```

## Run it

```bash
# 0) sanity-check the build end-to-end locally (no SMS) — writes out/<id>/model.png + .glb
uv run python -m scripts.blender_smoke "a red soccer ball"
#    open out/<id>/model.png and confirm it's red. Repeat for "a wooden chair", etc.

# 1) start the server
uv run uvicorn app.server.api:app --port 8000

# 2) expose it publicly (inbound SMS webhook + the phone link both need a public URL)
cloudflared tunnel --url http://127.0.0.1:8000   # copy https URL into PUBLIC_URL, restart server

# 3) point the Saperly line's webhook at it (one-time, via API)
uv run python -m scripts.set_webhook   # PATCHes webhook_url = $PUBLIC_URL/sms/incoming
```

Then **text your Saperly number** a scene. Watch the dashboard at
`http://localhost:8000/` while the reply lands on your phone.

> The free cloudflared URL **changes on every run** — after restarting the tunnel,
> update `PUBLIC_URL` in `.env`, restart the server, and re-run `set_webhook`.

> **Viewport looks grey?** Blender's **Solid** shading ignores materials. Switch the
> viewport to **Material Preview** / **Rendered** (the sphere icons, top-right) to
> see color — the actual SMS output (`out/<id>/model.png`) and the `.glb` carry the
> real color regardless.

## Tests

```bash
uv run pytest -q   # schema + intake/upload HTTP tests + a Blender cube render→.glb (skips if Blender is down)
```

## Notes / limitations

- **One Blender, one scene** — builds are serialized; this is a single-user demo,
  not a concurrent service.
- **Quality is stylized**, not photoreal — the AI models from primitives +
  modifiers, and the VisionCritic + geometry-audit loop reshapes until the render
  reads right. A build takes ~tens of seconds, so the server texts a "building…"
  ack first, then the link when done.
- Saperly has **no inbound MMS**, so the "build from my photos" flow collects
  photos via an upload link, not the text thread.
- $5 Saperly credit ≈ ~250 SMS. Outbound needs prior inbound or a consent record
  (handled in `record_consent`).
- Voice input is a natural next step (Saperly does voice too) — left as a stretch.
```
