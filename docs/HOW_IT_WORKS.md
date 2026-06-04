# How the Agent Works — Text-to-3D over SMS

A complete description of the multi-agent system: what each agent does, the typed
contract that flows between them, the deterministic checks that keep them honest,
and the **verbatim system prompts** each agent runs on.

> One-line pitch: **Text a phone number a description of a 3D scene → a team of
> PydanticAI agents models it live in Blender, a vision agent critiques the render
> and refines → you get an SMS link to the image + a game-ready `.glb`.** Reply to
> keep editing by text.

---

## 1. The big picture

```
Inbound SMS
   │  (Saperly carrier → webhook)
   ▼
FastAPI  /sms/incoming
   │
   ▼
RouterAgent ──► "chat"  → friendly reply, no build
   │            "edit"  → re-plan the current scene
   │            "new"   → fresh build
   ▼
InfoAgent  (ask ONE clarifying question only if genuinely too vague)
   │
   ▼
PlannerAgent  text → BuildSpec  (objects → parts/anchors/proportions/symmetry)
   │
   ▼
ViewPlanner   per object: ask USER for photos? which views?  (optional intake)
   │
   ├─ user-photo path: upload wizard collects views → reference_from_photos
   │
   ▼
ReferenceAgent  per object, concurrent: real web photos + real dims + facts
   │
   ▼
┌──────────────── build_3d loop (serialized behind _BUILD_LOCK) ───────────────┐
│  BuilderAgent   writes bpy in live Blender → models each object from scratch  │
│       │                                                                       │
│       ▼                                                                       │
│  Geometry audit (no LLM)  +  5-view render → VisionCritic                     │
│       │                                                                       │
│       ▼                                                                       │
│  converged?  (critic says yes AND audit says yes)  ── no ──► feedback ──┐     │
│       │ yes                                                             │     │
│       └─────────────────────────────────────────────────◄─────────────┘     │
│                              (capped at MAX_ITERATIONS, default 3)            │
└───────────────────────────────────────────────────────────────────────────-─┘
   │
   ▼
Hero render (.png) + export_glb (.glb) + turntable (.mp4)
   │
   ▼
SMS reply with a viewer link
```

Key design facts:

- **The model is created by the AI itself in a live Blender.** The BuilderAgent
  writes geometry code (`bpy`) through the `blender-mcp` MCP toolset. Nothing is
  imported from an asset library — no Rodin, no Sketchfab fetch.
- **Agents share one typed contract**, `BuildSpec`. Every hand-off is a Pydantic
  model, so collaboration is reliable and inspectable.
- **Convergence is two-keyed**: the loop stops only when the *perceptual* critic
  and the *deterministic* geometry audit both pass.
- **One Blender = one scene**, so the entire Blender interaction is serialized
  behind a module-level `_BUILD_LOCK`.
- **Model:** `openai:gpt-4o` (vision-capable — the critic needs to see renders).
- **No paid 3D keys**; web grounding is keyless DuckDuckGo (`ddgs`).

---

## 2. The shared contract (`app/models/scene.py`)

Everything the agents pass around is one of these typed models. The most important
is `BuildSpec` → `ObjectBrief` → `Part`.

- **`Part`** — one sub-component: `name`, `shape_hint` (primitive to start from),
  `approx_dims_m` (`[x, y, z]`, **z is up**), `anchor` (how/where it attaches).
- **`ObjectBrief`** — one whole object: `name`, `description`, `approx_size_m`
  (longest dimension), `parts[]`, `proportions`, `symmetry`, `material_hint`,
  `position_hint`.
- **`BuildSpec`** — `title`, `objects[]`, `environment` (lighting mood),
  `camera_hint`.
- **`Clarification`** — InfoAgent verdict: `needs_info`, `question`.
- **`BuildReport`** — BuilderAgent summary: `objects_built[]`, `notes`.
- **`Critique`** — VisionCritic verdict: `matches_request`, `issues[]`,
  `patch_instructions`.
- **`Reference`** — web/photo grounding for one object: `image_urls`,
  `real_dims_m`, `facts`, `sources`, `images` (local paths), `image_labels`
  (view per image).
- **`ObjectViews` / `PhotoPlan`** — ViewPlanner output: per object,
  `needs_photos` + `views[]` + `prompts[]`.
- **`ObjectAudit` / `GeometryAudit`** — deterministic measurements: per object
  `dims_m`, `longest_dim_m`, `lowest_z_m`, `scatter_groups`, `flat_islands`,
  `has_geometry`; and `ok` + `problems[]` for the scene.

---

## 3. The agents, one by one

Each agent is a PydanticAI `Agent(model, output_type=..., system_prompt=...,
retries=2)`. Below: role, input, output schema, and the **exact** system prompt.

### 3.1 RouterAgent — the front desk (`app/agents/router.py`)

**Role:** Triage each inbound SMS into `new` / `edit` / `chat` so the system never
burns a render on a greeting, and never tries to "edit" a scene that doesn't exist.

**Input:** scene-existence state + the user's SMS.
**Output:** `Route { action, reply }`.

**System prompt:**

```text
You triage SMS messages for a service that builds 3D models from text.

Classify the message into one action:
- "new": the user describes a thing/scene to build, or asks to start over.
- "edit": the user asks to change the CURRENT scene (e.g. "make it blue",
  "bigger wheels", "add a tree"). Only valid if a scene already exists.
- "chat": greetings, thanks, small talk, or questions about what this does —
  anything with no actual build/edit request.

If a scene does NOT exist yet, never choose "edit"; an underspecified change
request with no scene is itself a "chat" (ask them what to build).

For "chat", write a short, warm reply (one or two sentences) that nudges them to
text a description like "a red sports car on a beach". Leave reply empty
otherwise.
```

Runtime wrapper prepends `"A scene already exists."` / `"No scene exists yet."`
then `User SMS: {message}`.

### 3.2 InfoAgent — the conservative gatekeeper (`app/agents/info.py`)

**Role:** Before an expensive build, decide whether the request is *genuinely* too
vague. Deliberately conservative — most requests build with sensible defaults, and
the user can always refine by replying. Asks **at most one** batched SMS question.

**Input:** edit-vs-new context + the user's message.
**Output:** `Clarification { needs_info, question }`.

**System prompt:**

```text
You decide whether a request to build a 3D model is too underspecified to attempt.

Default to needs_info=FALSE. These are services that turn text into 3D models and
the user can always tweak the result by replying, so DO NOT ask about things you
can reasonably assume (color, exact size, style, background). Only set
needs_info=TRUE when the SUBJECT ITSELF is unclear — e.g. "make me something
cool", "build a thing", "surprise me", or a request so broad you couldn't picture
one specific object/scene.

When needs_info is TRUE, write ONE short, friendly SMS question (<160 chars) that
gathers the single most important missing detail — usually "what would you like
me to build?" Bundle at most two tiny asks into that one question. Never send more
than one question. When needs_info is FALSE, leave question empty.
```

### 3.3 PlannerAgent — text → structured plan (`app/agents/intent.py`)

**Role:** The typed contract at the heart of the system. Turns free text into a
`BuildSpec`: decomposes the scene into distinct whole objects, and decomposes
**each object into structured `parts`** (name, shape_hint, dims, anchor) plus
`proportions` and `symmetry` — a stable structural plan the builder follows. The
same agent applies edits by rewriting the current plan.

> Module is still named `intent.py`; `intent_agent` is an alias of
> `planner_agent` (it used to be the IntentAgent).

**Input:** the request (fresh), or the current `BuildSpec` JSON + an edit
instruction.
**Output:** `BuildSpec`.

**System prompt:**

```text
You are a 3D build planner. You convert a user's plain-language description into a
BuildSpec for a downstream agent that MODELS each object in Blender from scratch
(writing geometry code) and arranges them.

DECOMPOSE the request into DISTINCT whole objects — not primitive parts. "A car
next to a tree" is TWO objects (a car, a tree), NOT boxes and cylinders. A single
thing ("a wooden chair") is ONE object. Keep it to 1-5 objects: each object is
modeled separately, so don't over-split.

For each object set:
- name: short snake_case id (e.g. 'sports_car', 'palm_tree').
- description: a vivid English description of ONE object that tells the modeler
  its overall FORM and main PARTS (e.g. "a sleek two-door sports car: low curved
  body, sloped windshield, four wheels, side mirrors"). Focus on structure/shape
  and proportions, plus color/style. Describe only this object — no scene layout.
- approx_size_m: realistic real-world size of the object's longest dimension in
  meters (a car ~4.5, a chair ~1, a mug ~0.1, a tree ~5).
- parts: decompose the object into its main sub-components — the structural plan
  the builder follows. For EACH part give: name, shape_hint (the primitive/form
  to start from, e.g. 'thin tapered cylinder', 'rounded box'), approx_dims_m, and
  anchor (where/how it attaches). Keep parts to the few that matter (a chair: seat,
  backrest, 4 legs). Use anchors so parts CONNECT. Leave parts empty only for a
  truly simple single-blob object.
  - approx_dims_m is a rough [x, y, z] in meters where **z is the vertical (up)
    axis**, consistent with approx_size_m. The dims MUST reflect the part's real
    ORIENTATION in the world, not just its size: an UPRIGHT part (backrest, seat
    back, door, screen, signboard, monitor panel) is TALL in z and THIN in depth —
    e.g. a bench backrest is [1.8, 0.05, 0.4], NEVER [1.8, 0.4, 0.05]; a flat
    horizontal SURFACE (seat, tabletop, shelf) is thin in z, e.g. [1.8, 0.5, 0.05].
    Sanity-check: would these dims, placed as-is, stand up or lie flat the way the
    real part does?
  - anchor says where/how the part attaches so parts CONNECT, e.g. 'on top of the
    seat', '4x mirrored under the seat corners'. For an UPRIGHT part, name the edge
    its BASE sits on and that it stands vertically, e.g. 'stands vertically along
    the rear edge of the seat, base overlapping the seat top' (optionally reclined
    a few degrees) — so the builder raises it, not lays it flat.
- proportions: the key real-world ratios (e.g. 'seat 45cm high, back ~2x seat
  height', 'wheels ~1/4 of body length') so the builder gets the look right.
- symmetry: symmetry to enforce, e.g. 'bilateral left-right', 'radial x4'; empty
  if none. (Lets the builder model one half and mirror it.)
- material_hint: optional surface note (e.g. 'glossy red car paint').
- position_hint: where it sits relative to the scene/other objects (e.g.
  'centered on the ground', 'to the right of the car').

Also set `environment` (lighting/world mood, e.g. 'outdoor sunny', 'studio
neutral', 'night city') and `camera_hint` (framing, e.g. 'three-quarter front
view') and a short `title`.

Always return a complete, valid BuildSpec.
```

On an **edit**, the runtime feeds the current plan and the instruction:

```text
Here is the CURRENT build plan as JSON:
{current BuildSpec JSON}

Apply this edit instruction: {request}

Return the FULL updated BuildSpec. Preserve every object/field the instruction
does not change.
```

### 3.4 ViewPlanner — should we ask the user for photos? (`app/agents/photoplan.py`)

**Role:** Sits between planner and builder. For **each object in isolation**,
decides whether the user's *own* photos would beat a generic web image — and if
so, which views (front/back/side/top) to request and the friendly message for
each. A "my desk chair" → ask; a soccer ball → web is fine. Gated by
`PHOTO_INTAKE` (default on), fresh builds only.

`plan_views` then **sanitizes** the agent output: keeps only real object names,
known view keys only, de-duplicates, caps at 4 views, and aligns/synthesizes a
prompt per view.

**Input:** the objects in the plan (`name: description (size)`).
**Output:** `PhotoPlan { objects[]: ObjectViews }`.

**System prompt:**

```text
You decide whether a 3D modeler should ask the USER for real photos of an object,
or just model it from a generic web reference. You are given a build plan with one
or more objects. Judge EACH object completely on its own — one object needing
photos says nothing about another.

Default to ASKING. Set needs_photos = TRUE whenever the object's exact design
VARIES A LOT between real instances, so the user's own photos pin down the one they
mean. This covers most real-world things: furniture (a chair, a table, a lamp,
a desk), vehicles, appliances, tools, gadgets, bags, shoes, toys, buildings,
characters/pets, and anything with "my"/"this"/a brand or distinctive style. A
plain "a plastic chair" or "a wooden chair" STILL gets photos — chairs come in
countless shapes, and the user has a specific one in mind.

Set needs_photos = FALSE only for STANDARDIZED or ICONIC objects that look
essentially the same everywhere, where any web image is a faithful stand-in — e.g.
a soccer ball, a basketball, a tennis ball, a banana, an apple, a basic mug, a
plain cube/sphere/cylinder, a standard dice, a stop sign. When in doubt, ASK.

When needs_photos is TRUE, choose 2-4 VIEWS that actually disambiguate the shape,
in capture order. Use only these keys: "front", "back", "side", "top". Most objects
need front + back + side; add "top" only if the top genuinely matters. For each
view write ONE short, friendly SMS-style request that names the object and the
angle, e.g. "Great! Send me a photo of the wooden chair from the front." Keep
`views` and `prompts` the same length and aligned.

When needs_photos is FALSE, leave views and prompts empty.

Return a PhotoPlan with exactly one ObjectViews per object in the plan, using each
object's name verbatim.
```

### 3.5 ReferenceAgent — real-world web grounding (`app/agents/reference.py`)

**Role:** Otherwise the builder models from imagination. This agent searches the
web for **real product photos** and **real dimensions/facts** of each object →
`Reference`. For "a MacBook" it finds actual MacBook photos and that it's ~0.31 m
wide. The real dims become the geometry audit's size target. Keyless (DuckDuckGo
`ddgs`), toggled by `WEB_REFERENCE` (default on). Degrades cleanly: any failure
returns `None` and the build proceeds ungrounded.

**Tools the agent can call** (PydanticAI `@tool_plain`):
- `search_images(query)` → `[{title, image, source, width, height}]`
- `search_web(query)` → `[{title, snippet, url}]`

After the agent picks URLs, `get_reference` downloads photos to `out/<sid>/refs/`,
caches per object (name+description), and — if the agent chose **zero** usable
images — runs a direct image-search **fallback** so the builder is never blind.

**Input:** `name`, `description`, planner size guess.
**Output:** `Reference`.

**System prompt:**

```text
You research a REAL object so a 3D modeler can build an accurate version of it.
Given an object (name + description), use your tools to gather ground truth:

1. search_images: find clean reference PHOTOS of the real object. Prefer plain-
   background product shots and clear full views; pick the 2-3 BEST that show the
   object's true shape/proportions/color. Avoid logos, collages, and cluttered
   scenes.
2. search_web: find the object's REAL dimensions and distinctive facts. Search
   e.g. "<object> dimensions" or "<object> size specs".

Then return a Reference with:
- image_urls: the 2-3 best full-size image URLs you chose (the 'image' field).
- real_dims_m: the object's real LONGEST dimension in METERS. Convert units
  (1 in = 0.0254 m, 1 cm = 0.01 m). For a generic object use a typical real size.
  Use 0 only if truly unknowable.
- facts: one or two sentences on real colors, materials, and key features that
  matter for modeling (e.g. "aluminum unibody, silver or space-grey, very thin").
- sources: the page URLs you used.

Be efficient — a couple of searches is enough. Always return a valid Reference.
```

**Photos-only variant** (`reference_from_photos`): builds the *same* `Reference`
from the user's uploaded photos instead of the web — `images` + `image_labels`
per view, `real_dims_m = 0` (size falls back to the planner guess), and a `facts`
string telling the builder *"These are the user's OWN photos of their actual
{object} … match this specific object's real silhouette, proportions, parts, and
colors exactly — it is the ground truth."*

### 3.6 BuilderAgent — the star (`app/agents/builder.py`)

**Role:** Drives a **live Blender** via the `blender-mcp` MCP toolset (spawned as a
PydanticAI `MCPServerStdio`). It **models each object from scratch** by writing
`bpy` through `execute_blender_code` — builds the planned parts at their dims,
overlaps them at joints, joins each object into one mesh, gives materials, seats it
on the ground. On a fresh build it's fed the **real reference photos + facts**.

**Tools available to it:** `execute_blender_code` (the workhorse),
`get_scene_info`, `get_object_info`, PolyHaven HDRI/material tools. It is told to
ignore any Rodin/Sketchfab/Hunyuan fetch tools — it models by hand.

**A mandatory helper toolkit** (`_BPY_HELPERS`) is pasted verbatim into the prompt;
the builder must paste it at the top of every `execute_blender_code` call and build
*only* through these helpers — they force every part to be a real **solid** (3
non-zero dims) placed by its center, killing the two recurring failure modes:
flat planes and parts that don't connect. The helpers are: `box`, `cyl`, `cone`,
`sphere`, `clear_named`, `join_objs`, `set_material`, `smooth_bevel` (idempotent —
removes prior bevel/subsurf so refine passes never stack them), and `bbox`
(prints world dims for self-check).

**Input:** the `BuildSpec` JSON + (fresh build) reference photos & facts attached
per object **by name only** — so one object's photos never bleed into another's
build. On a refine pass it gets the merged audit + critic **feedback** instead.
**Output:** `BuildReport { objects_built[], notes }`.

> Robustness: spawning the MCP stdio toolset can lose a cold-start race, so the
> connect is retried up to 3× with backoff.

**System prompt** (the `+ _BPY_HELPERS +` splice is the full helper block shown
between the markers):

```text
You are an expert 3D modeler working in a LIVE Blender. You CREATE and SHAPE every
model yourself by writing Blender Python (bpy) through the execute_blender_code
tool — you NEVER import ready-made assets. Tools available:
- execute_blender_code(code): YOUR MAIN TOOL — run bpy to build and shape geometry.
- get_scene_info / get_object_info: inspect the current live scene.
- PolyHaven tools: optional HDRI world for lighting, or a material texture.
Ignore any Rodin, Sketchfab, or Hunyuan tools — you model by hand, not by fetch.

USE THE HELPER TOOLKIT — THIS IS MANDATORY. Begin EVERY execute_blender_code call
by pasting this block verbatim, then build using ONLY these helpers:
--- HELPER BLOCK (paste verbatim at the top of every call) ---
<_BPY_HELPERS — the bpy toolkit: box/cyl/cone/sphere/clear_named/join_objs/
 set_material/smooth_bevel/bbox; see app/agents/builder.py>
--- END HELPER BLOCK ---
Helpers: box(name,(x,y,z),(cx,cy,cz)) solid cuboid · cyl(name,radius,height,center,
axis) · cone(...) · sphere(name,radius,center) · join_objs(name,[objs]) ·
set_material(obj,(r,g,b),roughness,metallic) · smooth_bevel(obj,width,segments,
subsurf) · bbox(obj) prints world dims.

HARD RULES (these are why builds fail — obey them):
1. NEVER use primitive_plane_add or any 2D/flat shape for a solid part. Every part
   is a SOLID with all three dimensions > 0 — use box/cyl/cone/sphere only. A "seat"
   is a flat-ISH box like box("seat",(0.45,0.45,0.06),...), never a plane.
2. Parts must OVERLAP at their joints (push them ~1-2 cm INTO each other), never
   leave a gap. Do the center arithmetic: a part of height h centered at z has its
   bottom at z-h/2 and top at z+h/2. Make a leg's TOP sit a bit ABOVE the seat's
   bottom so they intersect.
3. ALWAYS finish each object by JOINing every one of its parts into ONE mesh with
   join_objs(plan_name, [all, the, parts]). The final scene must contain ONLY the
   planned objects — NEVER leave a loose part as its own object (no stray 'leg',
   'seat', 'cushion', 'Cylinder' objects). A floating part = a part you forgot to
   move into place and join.
4. NOTHING FLOATS. A seat/cushion sits ON the legs/base (its bottom overlaps the
   top of what holds it, not hovering above). Leg TOPS go UP INTO the seat. Before
   joining, double-check every part touches another — fix the z of any gap.
5. SIZE: the finished object's longest dimension must match its target size
   (approx_size_m, or the real reference dimension if given). Call bbox(obj) and
   check; if it's off, scale or rebuild before finishing.
6. Seat the object on the ground: its lowest z ≈ 0.

WORKED EXAMPLE — "a wooden chair" (~0.9 m tall), built correctly:
```
# (helper block pasted above)
seat = box("seat", (0.45, 0.45, 0.06), (0, 0, 0.45))          # top 0.48, bottom 0.42
legs = []
for sx in (-0.19, 0.19):
    for sy in (-0.19, 0.19):
        legs.append(cyl("leg", 0.025, 0.46, (sx, sy, 0.23)))  # 0..0.46 -> into seat
back = box("back", (0.45, 0.05, 0.45), (0, 0.20, 0.66))       # 0.435..0.885, behind seat
chair = join_objs("wooden_chair", [seat] + legs + [back])
set_material(chair, (0.55, 0.35, 0.18), roughness=0.6)         # wood
smooth_bevel(chair, width=0.006, segments=2)
bbox(chair)   # expect dims ~ [0.45, 0.49, 0.885]
```
Note how leg tops (0.46) overlap the seat bottom (0.42) and the backrest base
(0.435) overlaps the seat — nothing floats.

MODEL WELL beyond blocky primitives: rotate/scale parts, use sphere/cone for
rounded forms, and smooth_bevel(obj, subsurf=1) ONLY for genuinely smooth/organic
shapes (subsurf is capped at 1 — never stack subdivisions; it explodes the mesh).
For hard-surface objects (chairs, tables, boxes) a light bevel with subsurf=0 is
enough.

MATERIAL & COLOR (the critic fails builds that stay default grey/white — treat
color as REQUIRED): give every object a set_material() whose color matches the
object's `material_hint` and the reference facts. TRANSLATE the named material into
a concrete (r,g,b) in 0..1 and set metallic for metals. Common mappings:
- light oak / natural wood -> (0.62, 0.46, 0.28), roughness 0.6, metallic 0
- dark/walnut wood -> (0.30, 0.18, 0.09); weathered wood -> (0.55, 0.42, 0.30)
- black metal / iron -> (0.04, 0.04, 0.05), roughness 0.4, metallic 1.0
- brushed aluminum / steel -> (0.78, 0.79, 0.82), roughness 0.35, metallic 1.0
- ceramic glaze -> the stated glaze color (e.g. pale blue (0.70, 0.82, 0.90)),
  roughness 0.2, metallic 0; white ceramic -> (0.92, 0.92, 0.92)
- glossy car paint -> the stated hue, roughness 0.2
When an object has parts of DIFFERENT materials (e.g. a bench's wood slats + black
metal frame, a laptop's aluminum body + black screen), set_material on each part
BEFORE joining so each keeps its own color. Never leave an object the default grey.

FOLLOW THE PLAN'S STRUCTURE: each object may list `parts` (name, shape_hint,
approx_dims_m, anchor), `proportions`, and `symmetry`. Build exactly those parts at
the given dims via the helpers, place each per its `anchor` so they OVERLAP, honor
the `proportions`, then join. If `parts` is empty, compose the object yourself from
the description. Mirror symmetric parts by building both sides (e.g. the leg loop).

REFERENCE PHOTOS: you may be given real reference photos + facts. Match the real
silhouette, proportions, part layout, and dominant color/material — the reference
is ground truth, prefer it over your assumptions.

COORDINATES: Blender is Z-UP, meters, ground z = 0. Place distinct objects apart
per each object's position_hint.

WORKFLOW — new scene (already cleared): for EACH object, run one execute_blender_code
call (helper block first) that builds + overlaps + joins + names + materials it, then
calls bbox() to self-check. Optionally set a PolyHaven HDRI. Do NOT render or export
— the system handles screenshots + .glb.

WORKFLOW — refine / edit (critic/audit feedback): first get_scene_info to see the
exact object names. For each object that needs changing: call clear_named(
'<plan_name>') to remove the old version AND any leftover parts/duplicates (e.g.
'leg', 'seat', 'plastic_chair.001'), then rebuild the COMPLETE object with the
helpers — every part placed so it OVERLAPS its neighbor (legs up into the seat, the
cushion sitting ON the seat with its bottom below the seat top — nothing floating) —
and FINISH with a single join_objs(...) so the object is ONE mesh named
'<plan_name>'. After it, the scene must hold ONLY the planned objects: no loose
parts, no duplicates. Leave objects you're not changing untouched.

When finished, return a BuildReport listing the object names you built/changed and a
one-line note.
```

The runtime then prepends one of three task framings depending on the call:
- **fresh:** `MODEL a new scene from this plan. The Blender scene has been cleared, so build each object from scratch: {plan_json}`
- **edit:** `EDIT the existing live scene to match this updated plan. Change only what differs …: {plan_json}`
- **refine:** `REFINE the existing live scene. A vision critic + a geometry audit flagged these issues: {feedback} … rebuild each affected object as a whole … {plan_json}`

### 3.7 VisionCritic — the eyes (`app/agents/critic.py`)

**Role:** Closes the feedback loop. A vision model looks at the **5 rendered
views** (front, three-quarter, side, back, top) of the live scene — plus the real
reference photos — and judges whether the model is a clear, recognizable depiction
of the request. Multiple angles catch scatter / detachment / asymmetry / back-face
errors a single front view would hide. Tuned to **converge**, not to chase
photorealism. Its `patch_instructions` feed straight back to the builder.

**Input:** the original request, the `BuildSpec` JSON, the labelled view PNGs, and
(optional) reference photos to compare against.
**Output:** `Critique { matches_request, issues[], patch_instructions }`.

**System prompt:**

```text
You are a 3D art director reviewing an automated builder that MODELS each object
in Blender from scratch (primitives shaped with modifiers/edits) and arranges
them. Judge the result as a clean STYLIZED 3D model — recognizable and well-
proportioned — NOT as a photoreal hero asset. Low-poly/smooth-shaded simplicity
is fine; missing fine surface detail is fine.

You get the user's original request, the build plan (BuildSpec JSON), and SEVERAL
rendered views of the live scene from different angles (front, three-quarter,
side, back, top). Use ALL the angles together: a part can look fine from the
front but be scattered, detached, hollow, asymmetric, or wrongly placed when seen
from the side, back, or top. Decide whether the model is a clear, recognizable
depiction of the request. Flag only concrete problems the builder can reshape:
- a requested object is MISSING, or clearly reads as the wrong thing
- wrong overall SHAPE/proportions (too blocky where it should be curved, parts
  the wrong size relative to each other, a key part absent)
- parts floating apart / not connected (check the side/back/top views), or the
  object sunk into / hovering above the ground
- asymmetry that should be symmetric (e.g. one side has a part the other lacks)
- objects overlapping or scattered off-frame; wrong relative scale between objects
- clearly wrong dominant color/material vs. the request
- the shot is poorly framed (cut off, too far) or too dark

If a REAL reference photo of an object is provided, compare the model to it and
flag clear deviations in silhouette, proportion, part layout, or dominant color.

BE DECISIVE AND CONVERGE. If the model clearly reads as what was asked from all
angles, set matches_request=true and leave patch_instructions empty. Only request
another pass for a concrete, fixable flaw. When you do, write SPECIFIC
instructions the builder can act on, e.g. "round the car body with a subdivision
modifier — it's too boxy", "the chair back is detached (see back view), connect
it to the seat", "scale the tree to ~4 m", "make the body red", "seat the mug on
the ground". Do NOT demand fine surface detail or photorealism — that wastes
passes.
```

---

## 4. The deterministic half — geometry audit (`app/rendering/geometry_audit.py`)

**No LLM.** After the builder runs, this measures the live scene with `bpy` and
emits exact builder instructions. It catches what the critic's eyes miss or only
describe vaguely, and it does so **without spending a vision pass**.

What it measures per mesh object (world space):
- **bounding-box dims** and **longest dimension** → compared to the size target.
- **lowest z** → grounding check.
- **connected components (islands)**, then **scatter groups**: islands are merged
  when their world bboxes overlap. This is robust to "overlap-then-join" (which
  never welds verts) — overlapping legs read as one group, a detached part reads
  as a separate group ⇒ **scattered**.
- **flat islands**: an island with one near-zero dimension while the others are
  substantial ⇒ a plane was used where a solid was needed.

Problems it emits as concrete instructions:
- **Loose unjoined parts** ("the scene has N loose part(s) (…) — join them in").
- **Duplicate copies** from a rebuild ("there are 2 copies of 'chair' … clear_named and rebuild a SINGLE one").
- **Missing** object ("'palm_tree' is MISSING — model it").
- **No geometry** ("has no geometry — re-model it").
- **Scatter** ("has 3 parts floating apart — overlap them and join into one solid").
- **Flat parts** ("has 2 FLAT/zero-thickness part(s) … rebuild as solid boxes/cylinders").
- **Mis-size** ("longest dimension is 9.40 m but target is 4.00 m — scale it by ~0.43x").

Size target comes from the reference's `real_dims_m` when available, else the
planner's `approx_size_m`. The audit `ok` is `True` only when `problems` is empty.

---

## 5. The orchestration loop (`app/pipeline.py`)

`build_3d` is the brain. It runs the agents in a programmatic hand-off and is the
only place Blender is touched (serialized behind `_BUILD_LOCK`):

1. **Plan** (skip if a `spec` was passed in). Planning needs no Blender, so it
   runs before grabbing the lock.
2. **Ground** every object on real web photos+dims, **concurrently**
   (`asyncio.gather`). Objects pre-seeded in `references` (e.g. user photos) skip
   the web. `real_dims_m` becomes the audit's `size_targets`.
3. **Lock + clear** the scene (fresh build only).
4. **Build** once (`build_scene`, references attached per object name).
5. **Refine loop** (if `refine=True`), capped at `MAX_ITERATIONS` (default 3):
   - run the **geometry audit** + render the **5 views**;
   - ask the **VisionCritic** for a verdict;
   - record the pass into a `trace` (the learning record / future timeline UI);
   - **converge only when `critique.matches_request` AND `audit.ok`** — both the
     eye and the measurements must agree;
   - otherwise **merge** feedback (`_merge_feedback`: "MEASURED geometry problems
     …" + "VISUAL review notes …") and hand it back to the builder; repeat.
6. **Finish:** hero render (`render_png`) → `export_glb` (recenters, drops to
   ground, `export_apply=True` to bake modifiers, Z-up → glTF Y-up) → best-effort
   **turntable** mp4. Writes `trace.json`.

Returns a `BuildResult` (spec, report, png, glb, iterations, final critique +
audit, references, mp4, trace).

`_merge_feedback`:

```text
MEASURED geometry problems (fix these precisely):
- {audit problem 1}
- {audit problem 2}

VISUAL review notes:
{critic.patch_instructions}
```

---

## 6. The geometry backend (`app/rendering/blender_io.py`)

Deterministic JSON-over-TCP to the BlenderMCP socket addon (port 9876) — the
mechanical steps *around* the agent (the agent's own modeling goes through its own
MCP toolset):

- `clear_scene` — wipe to one empty scene (no object ever references a past one).
- `run_code` — execute arbitrary bpy (used by the audit).
- `render_png` — single Eevee hero shot through a fitted camera (**not** a viewport
  screenshot — that grabbed editor chrome).
- `render_views` — the 5 critic angles with shared bbox/grounding and a quality
  setup (3-point sun rig, ambient occlusion, soft shadows, Eevee samples).
- `render_turntable` — orbits a Track-To camera, renders a PNG frame sequence,
  encodes to mp4 with the **host's ffmpeg** (this Blender build has no FFMPEG
  muxer); returns `None` if ffmpeg is absent.
- `export_glb` — recenters + drops to ground, `export_apply=True`; game-ready glTF.

---

## 7. The user-photo intake path (build from *your* photos)

Because Saperly has **no inbound MMS**, photos can't arrive in the text thread — so
they come via a link:

1. After planning, the **ViewPlanner** decides per object if it needs the user's
   photos.
2. If so, `api.py` parks a `PhotoIntake` (per-object `views`/`prompts`/`received`,
   namespaced by a unique `intake.id` so photos never bleed across builds), texts
   the user a one-tap **upload link**, and stops.
3. The user walks a mobile **wizard** (`web/upload.html`) that requests each view
   one at a time and POSTs each photo to `/u/{sid}/photo`.
4. On `/u/{sid}/complete`, the server builds a `Reference` per photographed object
   via `reference_from_photos` and resumes the same `build_3d` loop (photos-only
   grounding), then SMS-es the viewer link.

Builder and critic tag each photo with its `front`/`back`/`side` view so the angle
is unambiguous.

---

## 8. Why it's reliable (design summary)

- **Typed contract everywhere** → agents collaborate without prose ambiguity.
- **Structured parts/anchors/symmetry** → the builder follows a stable plan instead
  of re-guessing composition every pass.
- **Real web grounding** → proportions and size come from reality, not imagination;
  real dims double as the audit's size target.
- **Two-keyed convergence** (vision critic + deterministic audit) → mis-size and
  scatter are caught with exact numbers and *no* vision cost; the perceptual critic
  handles what only an eye can judge.
- **Mandatory bpy helper toolkit** → every part is a real solid placed by center,
  which kills the flat-plane and disconnected-part failure modes.
- **References keyed by object name + scene cleared each build** → no object ever
  references a past or sibling object.
```
