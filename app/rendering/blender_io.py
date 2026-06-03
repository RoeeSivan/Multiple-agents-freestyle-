"""Deterministic Blender I/O over the BlenderMCP socket addon (port 9876).

This is the mechanical half of the geometry backend — no LLM. It talks the same
JSON-over-TCP protocol the BlenderMCP addon speaks (`{"type", "params"}` ->
`{"status", "result"|"message"}`) and provides the steps that should NOT be left
to a language model:

- `clear_scene()`            wipe the scene for a fresh build
- `generate_object()`        full Hyper3D Rodin text->mesh: create -> poll -> import
                             -> rescale (done here so the agent never tight-loops
                             on the polling API)
- `frame_and_shade()`        material-preview shading + frame all objects
- `viewport_screenshot()`    PNG for the VisionCritic
- `export_glb()`             recenter to origin + drop to ground (Blender is
                             Z-up) and export a game-ready binary .glb
- `get_scene_info` / status helpers

The BuilderAgent drives the *creative* work (layout, materials, world) through
the blender-mcp MCP toolset; this module is what its `generate_object` tool and
the pipeline's render/export steps call.
"""
from __future__ import annotations

import json
import socket
import time

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


def generate_object(
    name: str,
    description: str,
    target_size_m: float = 1.0,
    bbox_condition: list[float] | None = None,
    timeout: float | None = None,
) -> dict:
    """Generate one mesh from text via Hyper3D Rodin and import it, rescaled.

    Blocks until the Rodin job is Done (or `timeout` / settings.rodin_timeout),
    so callers — including the BuilderAgent's tool — get a single synchronous
    call instead of having to poll. Returns the imported object's info.
    """
    timeout = timeout or settings.rodin_timeout

    job = _send(
        "create_rodin_job",
        {"text_prompt": description, "images": None, "bbox_condition": bbox_condition},
    )
    if not isinstance(job, dict):
        raise BlenderError(f"Rodin job not accepted for '{name}': {job}")

    deadline = time.time() + timeout
    if job.get("request_id"):
        # FAL_AI mode: poll by request_id; done when status == COMPLETED.
        req_id = job["request_id"]
        while True:
            status = _send("poll_rodin_job_status", {"request_id": req_id})
            state = (status or {}).get("status")
            if state == "COMPLETED":
                break
            if state not in ("IN_PROGRESS", "IN_QUEUE", None):
                raise BlenderError(f"Rodin (FAL) failed for '{name}': {status}")
            if time.time() > deadline:
                raise BlenderError(
                    f"Rodin timed out after {timeout:.0f}s for '{name}'; last={state}"
                )
            time.sleep(4)
        import_params = {"name": name, "request_id": req_id}
    elif job.get("submit_time"):
        # MAIN_SITE mode: poll by subscription_key; done when all statuses == Done.
        task_uuid = job["uuid"]
        sub_key = job["jobs"]["subscription_key"]
        while True:
            status = _send("poll_rodin_job_status", {"subscription_key": sub_key})
            statuses = (status or {}).get("status_list", [])
            if statuses and all(s == "Done" for s in statuses):
                break
            if any(s in ("Failed", "Canceled", "Cancelled", "Error") for s in statuses):
                raise BlenderError(f"Rodin job failed for '{name}': {statuses}")
            if time.time() > deadline:
                raise BlenderError(
                    f"Rodin timed out after {timeout:.0f}s for '{name}'; last={statuses}"
                )
            time.sleep(4)
        import_params = {"name": name, "task_uuid": task_uuid}
    else:
        raise BlenderError(f"Rodin job not accepted for '{name}': {job}")

    # Import can take a while (server-side download into Blender).
    imported = _send("import_generated_asset", import_params, timeout=240.0)
    if not isinstance(imported, dict) or not imported.get("succeed"):
        raise BlenderError(f"Rodin import failed for '{name}': {imported}")

    obj_name = imported["name"]
    # Rodin meshes import at a normalized size — rescale longest dimension to target.
    run_code(
        f"""
import bpy
o = bpy.data.objects.get({obj_name!r})
if o is not None:
    d = o.dimensions
    m = max(d.x, d.y, d.z)
    if m > 0:
        f = {float(target_size_m)} / m
        o.scale = (o.scale.x * f, o.scale.y * f, o.scale.z * f)
    bpy.context.view_layer.update()
print("RESCALED")
"""
    )
    return imported


def render_png(path) -> str:
    """Render a clean, framed PNG of the scene for the VisionCritic.

    A plain viewport screenshot captures the editor chrome and the user's
    arbitrary view angle. Instead we place a camera with simple bounding-sphere
    math (three-quarter front), guarantee some lighting, and do a fast Eevee
    render — chrome-free, consistently framed, and showing real materials/world.
    """
    from pathlib import Path

    p = str(Path(path).resolve())
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
    center = mathutils.Vector(((mins[0]+maxs[0])/2, (mins[1]+maxs[1])/2, (mins[2]+maxs[2])/2))
    radius = max((mathutils.Vector(maxs) - mathutils.Vector(mins)).length / 2.0, 0.5)

    cam = scene.camera
    if cam is None or cam.type != 'CAMERA':
        cam = bpy.data.objects.new("CriticCam", bpy.data.cameras.new("CriticCam"))
        scene.collection.objects.link(cam)
        scene.camera = cam
    fov = min(cam.data.angle, 1.2)
    dist = radius / math.sin(fov / 2.0) * 1.3
    d = mathutils.Vector((1.0, -1.2, 0.7)); d.normalize()
    cam.location = center + d * dist
    cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()

    # Guarantee the scene isn't black even without a PolyHaven HDRI.
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get('Background')
    if bg is not None and bg.inputs[1].default_value < 0.4:
        bg.inputs[1].default_value = 1.0
    if not any(o.type == 'LIGHT' for o in bpy.data.objects):
        sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", 'SUN'))
        sun.data.energy = 3.0
        sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(40))
        scene.collection.objects.link(sun)

    for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
        try:
            scene.render.engine = eng
            break
        except Exception:
            pass
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 768
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = {p!r}
    bpy.ops.render.render(write_still=True)
    print("SHOT_OK")
""",
        timeout=180.0,
    )
    if "SHOT_OK" not in out:
        raise BlenderError(f"render produced no image (output: {out!r})")
    return p


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
    bpy.ops.export_scene.gltf(filepath={p!r}, export_format='GLB', use_selection=True)
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
