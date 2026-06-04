"""FastAPI app — the SMS front door + live web UI.

Flow: Saperly POSTs an inbound SMS to /sms/incoming. We ack, run the multi-agent
build pipeline in the background, then text back a link to a viewer page that
shows the render and offers the game-ready .glb download. A dashboard shows all
sessions live (great for the demo: phone in one hand, screen behind).
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.agents import build_spec, info_assess, plan_views, reference_from_photos, route_message
from app.config import OUT_DIR, WEB_DIR, settings
from app.messaging import InboundSMS, SaperlyError, saperly
from app.pipeline import build_3d
from app.state import ObjectIntake, PhotoIntake, Session, store

log = logging.getLogger("sms3d")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="SMS 3D Asset Builder")

OUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/out", StaticFiles(directory=str(OUT_DIR)), name="out")
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

# One build at a time per session (texting twice quickly shouldn't race).
_locks: dict[str, asyncio.Lock] = {}


def _lock(sid: str) -> asyncio.Lock:
    return _locks.setdefault(sid, asyncio.Lock())


def _viewer_link(sid: str) -> str:
    base = settings.public_url or ""
    return f"{base}/v/{sid}"


def _upload_link(sid: str) -> str:
    base = settings.public_url or ""
    return f"{base}/u/{sid}"


async def _safe_send(to: str, text: str) -> None:
    try:
        await saperly.send_sms(to, text)
    except SaperlyError as e:
        log.warning("SMS send failed to %s: %s", to, e)


async def _maybe_start_intake(session: Session, request: str, spec) -> bool:
    """If the ViewPlanner wants user photos for any object, park a PhotoIntake and
    text the user an upload link. Returns True when the build was parked (the caller
    should stop here and resume on /u/{sid}/complete)."""
    plan = await plan_views(spec)
    wanted = [ov for ov in plan.objects if ov.needs_photos and ov.views]
    if not wanted:
        return False

    objects: list[ObjectIntake] = []
    for ov in wanted:
        brief = next((o for o in spec.objects if o.name == ov.object_name), None)
        if brief is None:
            continue
        label = (brief.name or ov.object_name).replace("_", " ")
        prompts = {v: p for v, p in zip(ov.views, ov.prompts)}
        objects.append(ObjectIntake(name=ov.object_name, label=label, views=ov.views, prompts=prompts))
    if not objects:
        return False

    intake = PhotoIntake(
        id=str(int(time.time() * 1000)), request=request, is_edit=False, spec=spec, objects=objects
    )
    session.intake = intake
    session.status = "awaiting_photos"

    total = sum(len(o.views) for o in objects)
    labels = ", ".join(o.label for o in objects)
    link = _upload_link(session.sid)
    msg = (
        f"Love it. To match your {labels}, I need a few photos. Tap here and I'll guide "
        f"you angle by angle ({total} photo{'s' if total != 1 else ''}): {link}"
    )
    session.add_turn("agent", msg)
    await _safe_send(session.phone, msg)
    return True


async def _finish_build(session: Session, request: str, current, spec, references) -> None:
    """Run build_3d, persist the result on the session, and text the viewer link."""
    session.status = "building"
    try:
        result = await build_3d(
            request,
            current=current,
            spec=spec,
            references=references,
            out_dir=OUT_DIR / session.sid,
            basename="model",
        )
    except Exception as e:  # noqa: BLE001 — surface any failure back to the user
        session.status = "error"
        log.exception("build failed")
        await _safe_send(session.phone, f"⚠️ Build failed: {e}")
        return

    session.spec = result.spec
    session.iterations = result.iterations
    session.render_version += 1
    session.status = "done"

    passes = "pass" if result.iterations == 1 else "passes"
    spin = "Spin it 360° + grab" if result.mp4 else "View + download"
    msg = f"✅ Done in {result.iterations} {passes}. {spin} the .glb: {_viewer_link(session.sid)}"
    session.add_turn("agent", msg)
    await _safe_send(session.phone, msg)


async def handle_inbound(sms: InboundSMS) -> None:
    """Run the build pipeline for one inbound message and reply with a link."""
    session = store.get(sms.from_number)
    lock = _lock(session.sid)
    if lock.locked():
        await _safe_send(sms.from_number, "Still building your last one — one sec ⏳")
        return

    async with lock:
        session.add_turn("user", sms.message)

        # Mid photo-intake: we're waiting on uploads via the link, not on SMS text.
        if session.intake is not None:
            if sms.message.strip().lower() in {"cancel", "stop", "reset"}:
                session.intake = None
                session.status = "idle"
                reply = "Okay, cancelled. Text me an object to build whenever you're ready."
            else:
                reply = f"I'm waiting on your photos 📸 Upload them here: {_upload_link(session.sid)}"
            session.add_turn("agent", reply)
            await _safe_send(sms.from_number, reply)
            return

        if session.awaiting_clarification:
            # Second leg of a clarifying exchange: merge the answer and build.
            request = f"{session.pending_request} — {sms.message}"
            session.awaiting_clarification = False
            session.pending_request = ""
            current = session.spec  # edit if a scene already exists, else fresh
        else:
            # RouterAgent triages first so greetings/questions don't burn a render.
            route = await route_message(sms.message, has_scene=session.spec is not None)
            if route.action == "chat":
                reply = route.reply or "Text me a 3D scene to build, e.g. 'a red sports car on a beach'."
                session.add_turn("agent", reply)
                await _safe_send(sms.from_number, reply)
                return

            # InfoAgent: ask one clarifying question only if genuinely too vague.
            clar = await info_assess(sms.message, has_scene=session.spec is not None)
            if clar.needs_info and clar.question:
                session.awaiting_clarification = True
                session.pending_request = sms.message
                session.add_turn("agent", clar.question)
                await _safe_send(sms.from_number, clar.question)
                return

            request = sms.message
            current = session.spec if route.action == "edit" else None

        # Plan up front so the ViewPlanner can decide per object whether to ask the
        # user for photos. Photo intake is only for fresh builds (not edits like
        # "make it blue") — those would re-ask for photos pointlessly.
        spec = await build_spec(request, current)
        if settings.photo_intake and current is None:
            if await _maybe_start_intake(session, request, spec):
                return  # parked: build resumes when the user finishes uploading

        await _safe_send(sms.from_number, "🛠 Building your 3D model… link coming shortly.")
        await _finish_build(session, request, current, spec, references=None)


@app.post("/sms/incoming")
async def sms_incoming(req: Request, bg: BackgroundTasks):
    payload = await req.json()
    if payload.get("event") != "sms_received":
        return {"ok": True, "ignored": payload.get("event")}
    sms = InboundSMS.from_payload(payload)
    if not sms.message:
        return {"ok": True, "ignored": "empty"}
    bg.add_task(handle_inbound, sms)
    return {"ok": True}


def _session_json(s: Session) -> dict:
    v = s.render_version
    has_mp4 = v and (OUT_DIR / s.sid / "model.mp4").exists()
    return {
        "sid": s.sid,
        "phone": s.phone,
        "status": s.status,
        "iterations": s.iterations,
        "objects": [o.name for o in s.spec.objects] if s.spec else [],
        "turns": [{"role": t.role, "text": t.text, "ts": t.ts} for t in s.turns],
        "png": f"/out/{s.sid}/model.png?v={v}" if v else None,
        "glb": f"/out/{s.sid}/model.glb?v={v}" if v else None,
        "mp4": f"/out/{s.sid}/model.mp4?v={v}" if has_mp4 else None,
        "updated_at": s.updated_at,
    }


@app.get("/api/state")
async def api_state():
    return JSONResponse({"sessions": [_session_json(s) for s in store.all()]})


@app.get("/api/session/{sid}")
async def api_session(sid: str):
    s = store.by_sid(sid)
    if not s:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(_session_json(s))


def _photo_url(path: str | None) -> str | None:
    if not path:
        return None
    try:
        rel = Path(path).resolve().relative_to(OUT_DIR.resolve())
    except ValueError:
        return None
    return f"/out/{rel.as_posix()}"


def _intake_json(s: Session) -> dict:
    """Shape the active PhotoIntake for the upload wizard (objects -> ordered views)."""
    it = s.intake
    if it is None:
        return {"active": False}
    objects = []
    for o in it.objects:
        views = [
            {
                "view": v,
                "prompt": o.prompts.get(v, f"Send a photo of the {o.label} from the {v}."),
                "uploaded": v in o.received,
                "url": _photo_url(o.received.get(v)),
            }
            for v in o.views
        ]
        objects.append({"name": o.name, "label": o.label, "views": views})
    return {"active": True, "sid": s.sid, "complete": it.complete(), "objects": objects}


_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
_CTYPE_EXT = {"image/png": ".png", "image/webp": ".webp", "image/jpeg": ".jpg"}


@app.get("/api/intake/{sid}")
async def api_intake(sid: str):
    s = store.by_sid(sid)
    if not s:
        return JSONResponse({"active": False}, status_code=404)
    return JSONResponse(_intake_json(s))


@app.post("/u/{sid}/photo")
async def upload_photo(
    sid: str,
    object: str = Form(...),  # noqa: A002 — matches the wizard's form field name
    view: str = Form(...),
    file: UploadFile = File(...),
):
    """Receive one photo for (object, view) and store it under the intake's dir."""
    s = store.by_sid(sid)
    if not s or s.intake is None:
        return JSONResponse({"error": "no active intake"}, status_code=404)
    obj = s.intake.find(object)
    if obj is None or view not in obj.views:
        return JSONResponse({"error": "unknown object/view"}, status_code=400)

    data = await file.read()
    if not data or len(data) > 15_000_000:
        return JSONResponse({"error": "bad file size"}, status_code=400)
    ctype = (file.content_type or "").lower()
    suffix = Path(file.filename or "").suffix.lower()
    if not (ctype.startswith("image/") or suffix in _IMG_EXT):
        return JSONResponse({"error": "not an image"}, status_code=400)
    ext = _CTYPE_EXT.get(ctype) or (suffix if suffix in _IMG_EXT else ".jpg")

    dest = OUT_DIR / sid / "userphotos" / s.intake.id / object
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{view}{ext}"
    for old in dest.glob(f"{view}.*"):  # one file per view — drop a prior ext variant
        if old != path:
            old.unlink(missing_ok=True)
    path.write_bytes(data)
    obj.received[view] = str(path)
    s.updated_at = time.time()
    return JSONResponse(_intake_json(s))


@app.post("/u/{sid}/complete")
async def upload_complete(sid: str, bg: BackgroundTasks):
    """User finished uploading — kick off the build in the background."""
    s = store.by_sid(sid)
    if not s or s.intake is None:
        return JSONResponse({"error": "no active intake"}, status_code=404)
    if not any(o.received for o in s.intake.objects):
        return JSONResponse({"error": "no photos uploaded yet"}, status_code=400)
    bg.add_task(_run_intake_build, s.sid)
    return JSONResponse({"ok": True, "building": True})


async def _run_intake_build(sid: str) -> None:
    """Build from the collected user photos (photos-only grounding), then SMS the link."""
    s = store.by_sid(sid)
    if not s or s.intake is None:
        return
    lock = _lock(sid)
    if lock.locked():
        return  # a build is already running for this sender
    async with lock:
        intake = s.intake
        if intake is None:
            return
        # One Reference per photographed object, keyed by name -> no cross-object bleed.
        references = {o.name: reference_from_photos(o) for o in intake.objects if o.received}
        current = s.spec if intake.is_edit else None
        s.intake = None  # consume before building so a stray text doesn't re-nudge
        await _safe_send(s.phone, "🛠 Got your photos — building your 3D model…")
        await _finish_build(s, intake.request, current, intake.spec, references)


def _page(filename: str, **subs: str) -> HTMLResponse:
    html = (WEB_DIR / filename).read_text()
    for k, val in subs.items():
        html = html.replace(f"__{k}__", val)
    return HTMLResponse(html)


@app.get("/u/{sid}", response_class=HTMLResponse)
async def upload_page(sid: str):
    return _page("upload.html", SID=sid)


@app.get("/v/{sid}", response_class=HTMLResponse)
async def viewer(sid: str):
    return _page("viewer.html", SID=sid)


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return _page("dashboard.html")


@app.get("/health")
async def health():
    return {"ok": True, "public_url": settings.public_url or None}
