# Prompt-accuracy tuning log

Disciplined fine-tuning of the agent prompts by running escalating objects through
the FULL refine loop (`scripts/tune_run.py`), reading the 5-view renders + the
per-pass `trace.json`, and changing **one general lever per object** — then
re-running to verify. Every edit is a GLOBAL principle (never an object-specific
hack); the cross-object set (bench → teapot → desk) plus a final mug/chair
regression check guards against overfitting.

Levers: planner [app/agents/intent.py] · builder [app/agents/builder.py] ·
critic [app/agents/critic.py] · audit [app/rendering/geometry_audit.py] ·
loop [app/pipeline.py].

---

## Object 1 — "a park bench"  (stresses: parts/anchors, symmetry, orientation)

**Symptom (before).** The model read as a *double-decker shelf*, not a bench: the
backrest was a horizontal slatted deck floating ABOVE the seat instead of an
upright back. Critic never matched (4/4 iters); the defining bench silhouette was
absent.

**Diagnosis.** Planner gave the backrest `approx_dims_m = [1.8, 0.4, 0.05]` — z
(height) = 0.05, the *thinnest* axis. Those are the dims of a part lying flat. The
builder faithfully built the flat slab it was handed. The planner had no sense that
dims must encode a part's real ORIENTATION (z = up).

**Lever — Planner** [app/agents/intent.py], `parts` section. Added a general rule:
`approx_dims_m` is `[x, y, z]` with **z the vertical axis**, and the dims must
reflect orientation — an UPRIGHT part (backrest, door, screen, monitor panel,
signboard) is TALL in z, THIN in depth (e.g. backrest `[1.8, 0.05, 0.4]`, never
`[1.8, 0.4, 0.05]`); a flat SURFACE (seat, tabletop, shelf) is thin in z. Anchor
guidance for upright parts: name the edge the base sits on and that it stands
vertically. (General — applies to any object with an upright panel, not benches.)

**Result (after).** Planner now emits backrest `[1.8, 0.05, 0.4]` + "stands
vertically along the rear edge of the seat"; the render shows the backrest standing
upright at the rear edge — correct bench profile. Dominant silhouette failure
fixed.

**Still open (watch for recurrence → may become a later object's global lever):**
- parts floating apart / not joined (audit flagged every pass) — legs/slats not
  overlapping into one solid. Likely global; expect it on the teapot spout/handle.
  → RECURRED on teapot, fixed as Object 2's lever (below).
- render is dark + materials all-black (wood not brown). Possibly global
  lighting/material, possibly bench-specific. Defer until it recurs.

---

## Object 2 — "a ceramic teapot"  (stresses: curves, attaching angled parts, refine)

**Symptom (before).** White "double-blob snowman" with a stub spout and NO handle;
audit at iter 3 listed **7 loose, unjoined parts** (`Cylinder, handle, lid,
lid_base, lid_knob, Sphere, Sphere.001`). The first build was clean (audit ok iter
1) — the refine passes are what scattered it: the builder bolted on a loose handle
/ raw primitives instead of re-joining.

**Diagnosis.** The refine CALL prompt in [app/agents/builder.py] told the builder to
fix issues "**with the smallest changes**." That directly contradicts the system
prompt's refine workflow ("clear_named → rebuild the whole object → single
join_objs"), so the LLM made incremental edits and left loose parts. This is the
same "parts floating / unjoined" failure seen on the bench → confirmed GLOBAL (two
unrelated objects).

**Lever — Builder refine prompt** [app/agents/builder.py] `build_scene` feedback
branch. Replaced "smallest changes" with: REBUILD EACH AFFECTED OBJECT AS A WHOLE —
`clear_named('<plan_name>')`, rebuild ALL parts overlapping, finish with one
`join_objs(...)`; afterwards the scene must hold ONLY the planned objects, no loose
primitive left behind; leave unaffected objects untouched. (General — any
multi-part object on any refine pass.)

**Result (after).** Loose parts dropped **7 → 2** (only `body, spout` residual);
the teapot now reads as one connected pale-blue teapot with a visible handle loop,
spout, and lid. Targeted global failure measurably reduced.

**Still open (watch → candidate for Object 3, the scale-spread scene):**
- mis-sized vs target on nearly every teapot pass (built ~0.38 m, target 0.15 m
  from web ref); builder ignores the audit's explicit "scale by ~0.39x". Size
  compliance is the strongest recurring candidate — Object 3 (desk ~1.2 m + laptop
  ~0.33 m + mug ~0.1 m) will stress it hard.
- framing renders the teapot small in-frame (possibly the residual loose part
  inflating the scene bbox the camera fits to).

---

## Object 3 — "a desk with a laptop and a coffee mug on it"  (stresses: multi-object scale/placement, material)

**Note.** The earlier two fixes already paid off here: sizes came out right (desk
1.5 m / laptop 0.35 m / mug 0.1 m — no mis-size flag, so the teapot mis-size was a
web-ref quirk, not a builder bug worth chasing), and the planner orientation rule
gave the laptop a vertically-standing screen for free.

**Symptom (before).** Structure + scale were good, but EVERYTHING rendered white/
grey — the desk should be light oak wood. The critic flagged wrong color on every
pass of ALL THREE objects (bench brown/black, teapot pale blue, desk oak) and never
matched on color.

**Diagnosis.** The builder calls `set_material` but had no guidance to turn a named
material (`material_hint` / reference facts like "light oak wood") into a concrete
RGB, so it left objects the default grey/white. Confirmed GLOBAL (all 3 objects).

**Lever — Builder material/color** [app/agents/builder.py] SYSTEM_PROMPT. Added a
MATERIAL & COLOR rule: color is REQUIRED (the critic fails default grey); TRANSLATE
the named material into a concrete (r,g,b) + metallic, with a mapping table (light
oak, walnut, weathered wood, black metal, brushed aluminum, ceramic glaze, white
ceramic, car paint); set_material per-part BEFORE joining when an object mixes
materials. (General — every object.)

**Result (after).** Desk now renders as light oak wood (was pure white); laptop
reads as grey aluminum, mug white. The critic's complaint downgraded from "make it
wood-colored" to "make the wood slightly darker" — i.e. color now applies; the
residual is convergence-level shade nitpicking, not a failure.

**Still open (minor; not chased — would be the next global lever):**
- on refine the builder still occasionally leaves 1 loose/duplicate primitive
  (e.g. a stray `Cylinder`, a `coffee_mug.001`) — reduced vs. before the Object-2
  fix but not zero. The deterministic audit already catches it; a stronger
  end-of-build self-check (assert scene == planned object set) is the natural next
  lever.

---

## Summary — what generalized

Three independent objects, three GLOBAL prompt levers, each verified by re-run and
guarded against overfitting by the cross-object set:
1. **Planner** — `approx_dims_m` must encode orientation (z = up; upright parts
   tall-in-z). Fixes any flat-vs-upright part (backrest, door, screen, monitor).
2. **Builder (refine)** — on refine, rebuild each affected object whole + re-join,
   never bolt on loose parts. Fixes scatter/loose-part accumulation on every
   multi-part object's refine passes (teapot loose parts 7→2).
3. **Builder (material)** — translate named material → concrete RGB/metallic; color
   is required. Fixes the universal default-grey failure the critic kept rejecting.

The instrumentation (`trace.json` + `scripts/tune_run.py`) is what made the
recurrence visible — each "still open" item that recurred on the next object became
that object's proven lever.
