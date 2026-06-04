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

The model is **created by the AI itself in a live Blender** — the BuilderAgent
writes geometry code; nothing is imported from an asset library. PydanticAI
agents share a typed contract (`BuildSpec`):
- **RouterAgent** [app/agents/router.py](app/agents/router.py) — triage: `new` / `edit` / `chat`.
- **InfoAgent** [app/agents/info.py](app/agents/info.py) — asks **one** clarifying SMS question only when a request is genuinely too vague (conservative; most requests build with defaults).
- **PlannerAgent** [app/agents/intent.py](app/agents/intent.py) — text → `BuildSpec`. Decomposes a scene into distinct whole objects, and decomposes **each object into structured `parts`** (`name`, `shape_hint`, `approx_dims_m`, `anchor`) plus `proportions` and `symmetry` — a stable structural contract the builder follows. Also applies edits. (Module still named `intent.py`; `intent_agent` is an alias of `planner_agent`.)
- **ViewPlanner** [app/agents/photoplan.py](app/agents/photoplan.py) — decides, **per object in isolation**, whether to ask the **user** for photos and which `views` (front/back/side/top) → `PhotoPlan`. Asks for personal/specific objects ("my desk chair"), skips generic ones (a soccer ball → web is enough). `plan_views` sanitizes the output (known views only, prompts aligned). Gated by `PHOTO_INTAKE` (default on), fresh builds only. See the **user-photo intake** flow below.
- **ReferenceAgent** [app/agents/reference.py](app/agents/reference.py) — web grounding. Keyless DuckDuckGo (`ddgs`) tools `search_images` / `search_web`: finds real product photos + real dimensions/facts of each object → `Reference` (chosen photo URLs, `real_dims_m`, `facts`, sources). `get_reference` downloads photos to `out/<sid>/refs/`, caches per object, degrades to `None` on any failure. Toggle with `WEB_REFERENCE` (default on). `reference_from_photos` builds the same `Reference` from the **user's own uploaded photos** instead (`images` + `image_labels` per view; `real_dims_m=0` → planner-guess size; photos-only, no web for that object).
- **BuilderAgent** [app/agents/builder.py](app/agents/builder.py) — the star. Drives a **live Blender via the blender-mcp MCP toolset** (spawned as a PydanticAI `MCPServerStdio`): it **models each object from scratch** with `execute_blender_code` — builds the planned **parts** at their dims, anchors them so they touch, **Mirror** modifier for declared `symmetry`, plus Subdivision/Bevel/Solidify, `shade_smooth`, joined parts, Principled-BSDF materials — seats them on the ground. On a fresh build it's fed the **real reference photos + facts** and models toward them. Returns a `BuildReport`.
- **VisionCritic** [app/agents/critic.py](app/agents/critic.py) — looks at **5 rendered views** (front/three-quarter/side/back/top) + the real reference photos → `Critique` telling the builder how to reshape (catches scatter/asymmetry/back-face errors a single view hid; compares to ground truth). Tuned to **converge**, not chase photorealism.

Programmatic hand-off loop in [app/pipeline.py](app/pipeline.py): Planner → ReferenceAgent (per object, concurrent) → (clear) → Builder → **geometry audit + 5-view render** → Critic → (refine via Builder) → … capped at `MAX_ITERATIONS` (default 3). **Converges only when the critic AND the deterministic audit both pass.** Then hero render + `export_glb` + a **turntable mp4**. One Blender = one scene, so the whole Blender interaction is serialized behind a module-level `_BUILD_LOCK`. `build_3d` accepts an optional pre-planned `spec` (skip re-plan) and a pre-seeded `references` dict — objects already in it (e.g. user photos) **skip the web**; everything else is web-grounded as usual. References are keyed by object **name** and the scene is cleared each fresh build, so **no object ever references a past object**.

**User-photo intake** (the "build from my photos" path): after planning, the **ViewPlanner** decides per object if it needs the user's photos. If so, [api.py](app/server/api.py) parks a `PhotoIntake` ([app/state.py](app/state.py) — per-object `views`/`prompts`/`received`, namespaced by a unique `intake.id` so photos never bleed across builds), texts the user a one-tap **upload link**, and stops. The user walks a mobile **wizard** ([web/upload.html](web/upload.html)) that requests each view one at a time and POSTs each photo to `/u/{sid}/photo`. On `/u/{sid}/complete` the server builds a `Reference` per photographed object via `reference_from_photos` and resumes the same `build_3d` loop (photos-only grounding), then SMS-es the viewer link. Saperly has no inbound MMS, so photos arrive via the link, not the text thread. Builder/critic tag each photo with its `front`/`back`/`side` view.

Deterministic geometry audit [app/rendering/geometry_audit.py](app/rendering/geometry_audit.py): no LLM. Measures the live scene with bpy (per-object bbox/size, connected-component islands grouped by bbox overlap = a robust scatter detector, empty/missing checks) and emits exact builder instructions ("scale by ~0.32x"). Sized against the reference's `real_dims_m` when available (else the planner guess). Fed back to the builder **alongside** the critic, so mis-size/scatter get caught without spending a vision pass.

Geometry backend [app/rendering/blender_io.py](app/rendering/blender_io.py): deterministic JSON-over-TCP to the BlenderMCP socket addon (port 9876) — the mechanical steps around the agent: `clear_scene`, `run_code`, `render_png` (single hero shot), `render_views` (the 5 critic angles, shared bbox/grounding + a `_QUALITY_SETUP`: **Standard view transform** so set colors render true — not AgX-desaturated — plus a 3-point sun rig, ambient occlusion, soft shadows, Eevee samples), `render_turntable` (orbits a Track-To camera, renders a PNG frame sequence, encodes to mp4 with the **host's ffmpeg** since this Blender build has no FFMPEG muxer; returns `None` if ffmpeg is absent), and `export_glb` (recenters + drops to ground, **`export_apply=True`** to bake modifiers; Blender **Z-up** → glTF Y-up; game-ready).

Saperly [app/messaging/saperly.py](app/messaging/saperly.py): REST via httpx (the pip package is not actually installable). Base `https://saperly.com/api/v1`, Bearer auth. send_sms / resolve_line_id / record_consent / update_line.

Server [app/server/api.py](app/server/api.py): `POST /sms/incoming` webhook, `/v/{sid}` viewer, `/` dashboard, `/api/state`, static `/out`. **Photo intake:** `/u/{sid}` upload wizard, `GET /api/intake/{sid}` (its state), `POST /u/{sid}/photo` (one view, multipart), `POST /u/{sid}/complete` (kick off the build). Per-sender state in [app/state.py](app/state.py) (in-memory): `Session` now carries an optional `intake: PhotoIntake`.

## Run

Prereq: **Blender must be open** with the BlenderMCP addon, "Connect to MCP
server" clicked (socket on :9876). **No paid keys** — the AI models the geometry
itself. Optionally check **Use Poly Haven** so the builder can pull a free HDRI
for lighting.

```bash
uv venv --python 3.13 && uv pip install -e .
uv run python -m scripts.blender_smoke "a wooden chair"   # de-risk: planner+builder via MCP -> png + glb
uv run python -m scripts.photo_intake_smoke "a wooden chair" ~/chair_photos  # de-risk: user-photo path -> png + glb
uv run pytest -q                                   # schemas + intake/upload HTTP + (if Blender up) cube render -> glb
uv run uvicorn app.server.api:app --port 8000      # server
cloudflared tunnel --url http://127.0.0.1:8000     # public tunnel (ngrok not authed on this machine)
# put the https URL in .env PUBLIC_URL, restart server, then:
uv run python -m scripts.set_webhook               # PATCH Saperly line webhook_url
```

The BuilderAgent spawns `uvx blender-mcp` itself (its MCP toolset) — that
connects to the same addon socket, so multiple clients on :9876 is expected.

## Conventions / gotchas

- **Model:** `openai:gpt-4o` (vision-capable — the critic needs it). Key `OPENAI_API_KEY`. The user chose OpenAI over Anthropic. (pydantic-ai warns `openai:` will mean the Responses API in v2; use `openai-chat:gpt-4o` to pin Chat Completions if that ever bites.)
- **Geometry backend = Blender MCP, agentic modeling.** The BuilderAgent writes bpy via `execute_blender_code` to model each object — no Rodin, no asset import. Biggest failure mode: the LLM confusing primitive `size=`/`scale` with real size → mis-sized, scattered parts; the prompt tells it to set `obj.dimensions` in meters and verify the bbox, and the VisionCritic loop catches scattered/unrecognizable results. Blender is **Z-up** (ground = z=0). `render_png` is an Eevee render through a fitted camera (NOT a viewport screenshot — that grabbed editor chrome). `export_glb` uses `export_apply=True` to bake the builder's modifiers.
- **Secrets:** `.env` is gitignored and holds the live Saperly key + OpenAI key. Never commit `.env`; always check `git diff --cached --name-only` excludes it.
- **Commit frequently with meaningful messages** (assignment grades this). Private GitHub repo; invite user `dk8827`.
- **Don't name a module `app.py` inside a package that also exports an `app` var** — caused a shadowing bug; the FastAPI module is `server/api.py`.
- **Saperly outbound** needs prior inbound (24h) or a consent record. Inbound-first flow auto-authorizes replies.
- **Chat style:** caveman mode is active in conversation; code/commits/PRs written normally.

## Status / next

Agentic-modeling backend wired + verified end-to-end via MCP. **Accuracy push
shipped (4 workstreams):** (1) multi-view critic + deterministic geometry audit,
(2) structured spec — parts/anchors/symmetry, (3) web reference agent (real photos
+ real dims as ground truth), (4) render polish (3-point/AO) + orbiting turntable
mp4. The old "single-pass bpy is error-prone (mis-sized/scattered)" failure mode
is now caught by the audit (exact numbers, no vision cost) and the 5-view critic;
proportions/size are grounded in real web data. "a coffee mug" e2e in ~48s:
parts+symmetry plan, real 0.12 m reference + 3 photos, png + glb + 245 KB
turntable.

**User-photo intake shipped** (build from the user's OWN photos): ViewPlanner
decides per object → upload-link wizard collects views one-by-one → `build_3d`
grounds photos-only on them. Saperly has no inbound MMS, so photos come via the
link, not the text thread. Offline-tested (schemas, FSM, upload HTTP via
TestClient); `scripts.photo_intake_smoke` de-risks the build path.

**Color-fidelity + cleanup pass shipped** (ship-prep for the chair/table/soccer-
ball demo): a stated **color/finish now survives end-to-end and OVERRIDES the web
reference** — planner always copies it into `material_hint`; builder has a named-
color→RGB palette + a hard "requested color wins over the reference photo" rule
and an explicit per-object `REQUIRED COLOR` note in `build_scene`; critic judges
color against the request, not the reference; render pins
`view_settings.view_transform='Standard'` so a set red renders red, not AgX-muddy.
So "a red soccer ball" comes back red even though real balls are white/black.
**Cleanup:** deleted the dead legacy Three.js renderer stack (`renderer.py`,
`web/scene.html`, `web/vendor/` 1.3 MB, `playwright` dep) + dead `*_status`
wrappers; trimmed stale Rodin/PolyHaven docstrings. `pytest -q` green (27).

**Next:** live e2e over the tunnel (text → glb) for the 3 demo objects + record
the video; a **build timeline** UI showing each refine pass.
