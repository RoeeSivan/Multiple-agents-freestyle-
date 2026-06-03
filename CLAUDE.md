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

The geometry is built by **AI mesh generation in a live Blender**, not primitive
composition. PydanticAI agents share a typed contract (`BuildSpec`):
- **RouterAgent** [app/agents/router.py](app/agents/router.py) — triage: `new` / `edit` / `chat`.
- **InfoAgent** [app/agents/info.py](app/agents/info.py) — asks **one** clarifying SMS question only when a request is genuinely too vague (conservative; most requests build with defaults).
- **PlannerAgent** [app/agents/intent.py](app/agents/intent.py) — text → `BuildSpec` (decomposes a scene into distinct whole objects, each a vivid text-to-3D prompt + size/material/position hints); also applies edits. (Module still named `intent.py`; `intent_agent` is an alias of `planner_agent`.)
- **BuilderAgent** [app/agents/builder.py](app/agents/builder.py) — the star. Drives a **live Blender via the blender-mcp MCP toolset** (spawned as a PydanticAI `MCPServerStdio`): generates each object as a real mesh with **Hyper3D Rodin**, arranges them with `execute_blender_code`, optionally pulls **PolyHaven** HDRIs/materials. Returns a `BuildReport`.
- **VisionCritic** [app/agents/critic.py](app/agents/critic.py) — *looks at the rendered PNG* → `Critique` with concrete fixes; tuned to **converge**, not chase photorealism.

Programmatic hand-off loop in [app/pipeline.py](app/pipeline.py): Planner → (clear) → Builder → render → Critic → (refine via Builder) → … capped at `MAX_ITERATIONS` (default 3). One Blender = one scene, so the whole Blender interaction is serialized behind a module-level `_BUILD_LOCK`.

Geometry backend [app/rendering/blender_io.py](app/rendering/blender_io.py): deterministic JSON-over-TCP to the BlenderMCP socket addon (port 9876). It owns the steps we don't trust an LLM with: `clear_scene`, `generate_object` (full Rodin flow — create job → poll until Done → import → rescale, so the agent makes one call per object instead of polling), `render_png` (places a camera with bounding-sphere math + guarantees lighting, then a fast **Eevee** render — chrome-free and consistently framed), and `export_glb` (recenters to origin + drops to ground; Blender is **Z-up** → glTF Y-up; game-ready). The legacy Three.js renderer ([app/rendering/renderer.py](app/rendering/renderer.py) + [web/scene.html](web/scene.html)) is kept on disk for reference but **no longer wired in**.

Saperly [app/messaging/saperly.py](app/messaging/saperly.py): REST via httpx (the pip package is not actually installable). Base `https://saperly.com/api/v1`, Bearer auth. send_sms / resolve_line_id / record_consent / update_line.

Server [app/server/api.py](app/server/api.py): `POST /sms/incoming` webhook, `/v/{sid}` viewer, `/` dashboard, `/api/state`, static `/out`. Per-sender state in [app/state.py](app/state.py) (in-memory).

## Run

Prereq: **Blender must be open** with the BlenderMCP addon, "Connect to MCP
server" clicked (socket on :9876), and **Use Hyper3D Rodin + Use Poly Haven**
both checked. Rodin needs a **funded** key (the shared free-trial key returns
`API_INSUFFICIENT_FUNDS`) — set your own hyper3d.ai key in the addon panel.

```bash
uv venv --python 3.13 && uv pip install -e .
uv run python -m scripts.blender_smoke "a red sports car"   # de-risk: real Rodin -> png + glb
uv run pytest -q                                   # schemas + (if Blender up) cube render -> glb
uv run uvicorn app.server.api:app --port 8000      # server
cloudflared tunnel --url http://127.0.0.1:8000     # public tunnel (ngrok not authed on this machine)
# put the https URL in .env PUBLIC_URL, restart server, then:
uv run python -m scripts.set_webhook               # PATCH Saperly line webhook_url
```

The BuilderAgent spawns `uvx blender-mcp` itself (its MCP toolset) — that
connects to the same addon socket, so multiple clients on :9876 is expected.

## Conventions / gotchas

- **Model:** `openai:gpt-4o` (vision-capable — the critic needs it). Key `OPENAI_API_KEY`. The user chose OpenAI over Anthropic. (pydantic-ai warns `openai:` will mean the Responses API in v2; use `openai-chat:gpt-4o` to pin Chat Completions if that ever bites.)
- **Geometry backend = Blender MCP.** Rodin meshes import normalized → always rescale (handled in `generate_object`). Blender is **Z-up** (ground = z=0), unlike the old Three.js Y-up. `render_png` does an Eevee render through a fitted camera, NOT a viewport screenshot (that captured the editor chrome + the user's view angle).
- **Rodin funds:** the shared free-trial key is empty (`API_INSUFFICIENT_FUNDS`); a funded hyper3d.ai key in the addon panel is required for any real build.
- **Secrets:** `.env` is gitignored and holds the live Saperly key + OpenAI key. The Rodin key lives in the Blender addon, not `.env`. Never commit `.env`; always check `git diff --cached --name-only` excludes it.
- **Commit frequently with meaningful messages** (assignment grades this). Private GitHub repo; invite user `dk8827`.
- **Don't name a module `app.py` inside a package that also exports an `app` var** — caused a shadowing bug; the FastAPI module is `server/api.py`.
- **Saperly outbound** needs prior inbound (24h) or a consent record. Inbound-first flow auto-authorizes replies.
- **Chat style:** caveman mode is active in conversation; code/commits/PRs written normally.

## Status / next

Code complete for the Blender backend: contracts, agents, pipeline, server,
tests, and `blender_io` all wired; non-Rodin path (clear/render/export) verified
on a primitive cube, and Planner/Info/Router/Critic LLM agents verified live.
**Blocked only on a funded Rodin key** for a real end-to-end build. Planned next
once funded: tune the BuilderAgent's layout/ground-seating, then a **build
timeline** UI showing each refine pass + the critic's feedback for the demo.
