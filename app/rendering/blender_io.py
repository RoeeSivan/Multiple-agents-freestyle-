"""Deterministic Blender I/O over the BlenderMCP socket addon (port 9876).

This is the mechanical half of the geometry backend — no LLM. It talks the same
JSON-over-TCP protocol the BlenderMCP addon speaks (`{"type", "params"}` ->
`{"status", "result"|"message"}`) and provides the steps that should NOT be left
to a language model:

- `clear_scene()`     wipe the scene for a fresh build
- `run_code()`        run arbitrary bpy (used by tests/utilities)
- `render_png()`      camera-framed Eevee render for the VisionCritic
- `export_glb()`      recenter to origin + drop to ground (Blender is Z-up) and
                      export a game-ready binary .glb (modifiers applied)
- `get_scene_info` / status helpers

The BuilderAgent does the *creative* work — it MODELS each object by writing bpy
through the blender-mcp MCP toolset; this module only handles the deterministic
clear / render / export steps the pipeline runs around it.
"""
from __future__ import annotations

import json
import socket

from app.config import settings


class BlenderError(RuntimeError):
    """A command the Blender addon rejected, or a connection problem."""


def _send(cmd: str, params: dict | None = None, timeout: float = 120.0):
    """Send one command to the addon and return its `result` (raise on error)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((settings.blender_host, settings.blender_port))
    except OSError as e:
        raise BlenderError(
            f"can't reach Blender on {settings.blender_host}:{settings.blender_port} "
            f"— is Blender open with the BlenderMCP addon running? ({e})"
        ) from e
    try:
        s.sendall(json.dumps({"type": cmd, "params": params or {}}).encode())
        buf = b""
        while True:
            try:
                chunk = s.recv(65536)
            except socket.timeout as e:
                raise BlenderError(f"timeout waiting for '{cmd}' response") from e
            if not chunk:
                break
            buf += chunk
            try:
                msg = json.loads(buf.decode())
                break
            except json.JSONDecodeError:
                continue
        else:
            raise BlenderError(f"connection closed before '{cmd}' replied")
    finally:
        s.close()

    if msg.get("status") == "error":
        raise BlenderError(msg.get("message", f"'{cmd}' failed"))
    return msg.get("result")


def reachable() -> bool:
    """True if the Blender addon socket accepts a connection (for test skips)."""
    try:
        s = socket.create_connection(
            (settings.blender_host, settings.blender_port), timeout=1.5
        )
        s.close()
        return True
    except OSError:
        return False


def run_code(code: str, timeout: float = 120.0) -> str:
    """Run bpy Python in Blender; return whatever it printed to stdout."""
    res = _send("execute_code", {"code": code}, timeout=timeout)
    return (res or {}).get("result", "") if isinstance(res, dict) else ""


def get_scene_info() -> dict:
    return _send("get_scene_info")


def hyper3d_status() -> dict:
    return _send("get_hyper3d_status")


def polyhaven_status() -> dict:
    return _send("get_polyhaven_status")


_CLEAR_CODE = """
import bpy
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for coll in (bpy.data.meshes, bpy.data.materials):
    for b in list(coll):
        if b.users == 0:
            coll.remove(b)
print("CLEARED")
"""


def clear_scene() -> None:
    """Delete every object and purge orphaned mesh/material data."""
    run_code(_CLEAR_CODE)


# Standard angles for the multi-view critic. Each entry is (label, direction);
# the direction is normalized and scaled by the fitted camera distance. A single
# front view hides scattered/asymmetric/back-face errors — these five don't.
VIEW_SET: tuple[tuple[str, tuple[float, float, float]], ...] = (
    ("front", (0.0, -1.0, 0.35)),
    ("three_quarter", (1.0, -1.2, 0.7)),
    ("side", (1.0, 0.0, 0.35)),
    ("back", (0.0, 1.0, 0.35)),
    ("top", (0.3, -0.3, 1.4)),
)

# The single hero angle used for the SMS preview + as the default render_png shot.
HERO_DIRECTION: tuple[float, float, float] = (1.0, -1.2, 0.7)


# Studio lighting + render-quality setup shared by every render path (shots +
# turntable). Adds a 3-point sun rig (key/fill/rim) only when the scene has no
# lights, ambient occlusion, soft shadows, and a sample count — then picks Eevee.
# The lights are LIGHT objects (not MESH), so they don't affect bbox/audit/export.
_QUALITY_SETUP = """
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get('Background')
    if bg is not None and bg.inputs[1].default_value < 0.4:
        bg.inputs[1].default_value = 1.0
    if not any(o.type == 'LIGHT' for o in bpy.data.objects):
        for nm, en, rot in (("Key", 4.0, (50, 0, 30)),
                            ("Fill", 1.6, (62, 0, -55)),
                            ("Rim", 3.0, (-35, 0, 190))):
            L = bpy.data.objects.new(nm, bpy.data.lights.new(nm, 'SUN'))
            L.data.energy = en
            try: L.data.angle = math.radians(4)  # softer shadows
            except Exception: pass
            L.rotation_euler = tuple(math.radians(a) for a in rot)
            scene.collection.objects.link(L)
    for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        try:
            scene.render.engine = eng
            break
        except Exception:
            pass
    try: scene.eevee.use_gtao = True
    except Exception: pass
    try: scene.eevee.use_soft_shadows = True
    except Exception: pass
    try: scene.eevee.taa_render_samples = SAMPLES
    except Exception: pass
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 768
"""


def _render_shots(shots: list[tuple[str, tuple[float, float, float]]], samples: int = 32) -> None:
    """Render one framed PNG per (filepath, direction) shot.

    A plain viewport screenshot captures editor chrome and the user's arbitrary
    angle. Instead we compute the scene bounding box ONCE, drop it to the ground
    and center it in X/Y (exactly like export_glb, so the critic judges the same
    grounded object the .glb will contain), set up studio lighting + quality, then
    for each shot place a camera along `direction` at a fitted distance and
    Eevee-render. The scene is restored afterwards so refine passes are unaffected.
    """
    shots_lit = repr([(fp, list(d)) for (fp, d) in shots])
    out = run_code(
        f"""
import bpy, math, mathutils
scene = bpy.context.scene
shots = {shots_lit}
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
if not meshes:
    print("NO_MESH")
else:
    mins = [1e18, 1e18, 1e18]
    maxs = [-1e18, -1e18, -1e18]
    for o in meshes:
        for c in o.bound_box:
            w = o.matrix_world @ mathutils.Vector(c)
            for i in range(3):
                mins[i] = min(mins[i], w[i]); maxs[i] = max(maxs[i], w[i])

    off = mathutils.Vector((-(mins[0]+maxs[0])/2.0, -(mins[1]+maxs[1])/2.0, -mins[2]))
    tops = [o for o in bpy.data.objects if o.parent is None]
    for o in tops:
        o.location = o.location + off
    bpy.context.view_layer.update()

    center = mathutils.Vector((0.0, 0.0, (maxs[2]-mins[2]) / 2.0))
    radius = max((mathutils.Vector(maxs) - mathutils.Vector(mins)).length / 2.0, 0.5)

    cam = scene.camera
    if cam is None or cam.type != 'CAMERA':
        cam = bpy.data.objects.new("CriticCam", bpy.data.cameras.new("CriticCam"))
        scene.collection.objects.link(cam)
        scene.camera = cam
    fov = min(cam.data.angle, 1.2)
    dist = radius / math.sin(fov / 2.0) * 1.3
{_QUALITY_SETUP.replace("SAMPLES", str(int(samples)))}
    scene.render.image_settings.file_format = 'PNG'

    for fp, dvec in shots:
        d = mathutils.Vector(dvec); d.normalize()
        cam.location = center + d * dist
        cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = fp
        bpy.ops.render.render(write_still=True)

    for o in tops:
        o.location = o.location - off
    bpy.context.view_layer.update()
    print("SHOTS_OK")
""",
        timeout=300.0,
    )
    if "SHOTS_OK" not in out:
        raise BlenderError(f"render produced no image (output: {out!r})")


def render_png(path) -> str:
    """Render a single clean, framed hero PNG (three-quarter front) of the scene."""
    from pathlib import Path

    p = str(Path(path).resolve())
    _render_shots([(p, HERO_DIRECTION)], samples=64)  # hero shot for the SMS link
    return p


def render_views(out_dir, basename: str = "view", views=VIEW_SET) -> list[tuple[str, str]]:
    """Render the scene from several angles for the multi-view critic.

    Returns a list of (label, absolute_png_path), one per view. All views share a
    single bounding-box/grounding computation, so they frame the object the same.
    """
    from pathlib import Path

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    shots: list[tuple[str, tuple[float, float, float]]] = []
    labelled: list[tuple[str, str]] = []
    for label, direction in views:
        p = str((out / f"{basename}_{label}.png").resolve())
        shots.append((p, direction))
        labelled.append((label, p))
    _render_shots(shots, samples=24)  # lighter samples — 5 frames, just for the critic
    return labelled


def render_turntable(path, frames: int = 30, samples: int = 14, fps: int = 15) -> str | None:
    """Render an orbiting turntable MP4 of the scene — the SMS "wow" preview.

    Blender renders a 360° orbit as a PNG frame SEQUENCE (this Blender build has no
    FFMPEG muxer), then the host's ffmpeg encodes the frames into an .mp4. Uses a
    dedicated camera + Track-To target so the live camera/scene is left clean.
    Returns the .mp4 path, or None if ffmpeg isn't available (best-effort wow).
    """
    import shutil
    import subprocess
    from pathlib import Path

    ffmpeg = shutil.which("ffmpeg")
    p = Path(path).with_suffix(".mp4")
    frames_dir = p.parent / f"{p.stem}_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    prefix = str((frames_dir / "tt_").resolve()).replace("\\", "/")

    out = run_code(
        f"""
import bpy, math, mathutils
scene = bpy.context.scene
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
if not meshes:
    print("NO_MESH")
else:
    mins = [1e18, 1e18, 1e18]
    maxs = [-1e18, -1e18, -1e18]
    for o in meshes:
        for c in o.bound_box:
            w = o.matrix_world @ mathutils.Vector(c)
            for i in range(3):
                mins[i] = min(mins[i], w[i]); maxs[i] = max(maxs[i], w[i])
    off = mathutils.Vector((-(mins[0]+maxs[0])/2.0, -(mins[1]+maxs[1])/2.0, -mins[2]))
    tops = [o for o in bpy.data.objects if o.parent is None]
    for o in tops:
        o.location = o.location + off
    bpy.context.view_layer.update()

    center = mathutils.Vector((0.0, 0.0, (maxs[2]-mins[2]) / 2.0))
    radius = max((mathutils.Vector(maxs) - mathutils.Vector(mins)).length / 2.0, 0.5)

    prev_cam = scene.camera
    prev_start, prev_end = scene.frame_start, scene.frame_end
    target_empty = bpy.data.objects.new("TT_Target", None)
    target_empty.location = center
    scene.collection.objects.link(target_empty)
    ttcam = bpy.data.objects.new("TT_Cam", bpy.data.cameras.new("TT_Cam"))
    scene.collection.objects.link(ttcam)
    scene.camera = ttcam
    con = ttcam.constraints.new('TRACK_TO')
    con.target = target_empty
    con.track_axis = 'TRACK_NEGATIVE_Z'
    con.up_axis = 'UP_Y'
    fov = min(ttcam.data.angle, 1.2)
    dist = radius / math.sin(fov / 2.0) * 1.35

    n = {int(frames)}
    for f in range(1, n + 1):
        ang = 2.0 * math.pi * (f - 1) / n
        ttcam.location = (center.x + dist * math.cos(ang),
                          center.y + dist * math.sin(ang),
                          center.z + radius * 0.55)
        ttcam.keyframe_insert("location", frame=f)
{_QUALITY_SETUP.replace("SAMPLES", str(int(samples)))}
    scene.frame_start = 1
    scene.frame_end = n
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = {prefix!r}
    bpy.ops.render.render(animation=True)

    # Clean up so the live scene is untouched for further edits.
    bpy.data.objects.remove(ttcam, do_unlink=True)
    bpy.data.objects.remove(target_empty, do_unlink=True)
    scene.camera = prev_cam
    scene.frame_start, scene.frame_end = prev_start, prev_end
    for o in tops:
        o.location = o.location - off
    bpy.context.view_layer.update()
    print("TT_FRAMES_OK")
""",
        timeout=420.0,
    )
    if "TT_FRAMES_OK" not in out:
        raise BlenderError(f"turntable frame render did not confirm (output: {out!r})")

    if not ffmpeg:
        return None  # frames rendered but no encoder; skip the mp4 gracefully

    target = str(p.resolve())
    cmd = [
        ffmpeg, "-y", "-framerate", str(int(fps)), "-start_number", "1",
        "-i", f"{prefix}%04d.png",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", target,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not p.exists():
        raise BlenderError(f"ffmpeg failed to encode turntable: {proc.stderr[-400:]}")

    shutil.rmtree(frames_dir, ignore_errors=True)  # keep only the mp4
    return target


def export_glb(path) -> str:
    """Export all meshes to a game-ready .glb, recentered to origin on the ground.

    Blender is Z-up; the glTF exporter converts to glTF's Y-up. We zero the
    combined bounding box in X/Y (center) and Z (drop to ground) before export,
    then restore the live scene so subsequent edits are unaffected.
    """
    from pathlib import Path

    p = str(Path(path).resolve())
    out = run_code(
        f"""
import bpy, mathutils
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
if not meshes:
    print("NO_MESH")
else:
    mins = [1e18, 1e18, 1e18]
    maxs = [-1e18, -1e18, -1e18]
    for o in meshes:
        for c in o.bound_box:
            w = o.matrix_world @ mathutils.Vector(c)
            for i in range(3):
                mins[i] = min(mins[i], w[i])
                maxs[i] = max(maxs[i], w[i])
    off = mathutils.Vector((-(mins[0] + maxs[0]) / 2.0,
                            -(mins[1] + maxs[1]) / 2.0,
                            -mins[2]))
    tops = [o for o in bpy.data.objects if o.parent is None]
    for o in tops:
        o.location = o.location + off
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    for o in meshes:
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath={p!r}, export_format='GLB', use_selection=True,
                              export_yup=True, export_apply=True, export_materials='EXPORT')
    for o in tops:
        o.location = o.location - off
    bpy.context.view_layer.update()
    print("EXPORT_OK")
""",
        timeout=180.0,
    )
    if "EXPORT_OK" not in out:
        raise BlenderError(f"glb export did not confirm (output: {out!r})")
    return p
