"""FastAPI app — the SMS front door + live web UI.

Flow: Saperly POSTs an inbound SMS to /sms/incoming. We ack, run the multi-agent
build pipeline in the background, then text back a link to a viewer page that
shows the render and offers the game-ready .glb download. A dashboard shows all
sessions live (great for the demo: phone in one hand, screen behind).
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import OUT_DIR, WEB_DIR, settings
from app.messaging import InboundSMS, SaperlyError, saperly
from app.pipeline import build_3d
from app.state import Session, store

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


async def _safe_send(to: str, text: str) -> None:
    try:
        await saperly.send_sms(to, text)
    except SaperlyError as e:
        log.warning("SMS send failed to %s: %s", to, e)


async def handle_inbound(sms: InboundSMS) -> None:
    """Run the build pipeline for one inbound message and reply with a link."""
    session = store.get(sms.from_number)
    lock = _lock(session.sid)
    if lock.locked():
        await _safe_send(sms.from_number, "Still building your last one — one sec ⏳")
        return

    async with lock:
        session.add_turn("user", sms.message)
        session.status = "building"
        await _safe_send(sms.from_number, "🛠 Building your 3D scene… link coming shortly.")

        try:
            result = await build_3d(
                sms.message,
                current=session.spec,
                out_dir=OUT_DIR / session.sid,
                basename="model",
            )
        except Exception as e:  # noqa: BLE001 — surface any failure back to the user
            session.status = "error"
            log.exception("build failed")
            await _safe_send(sms.from_number, f"⚠️ Build failed: {e}")
            return

        session.spec = result.spec
        session.iterations = result.iterations
        session.render_version += 1
        session.status = "done"

        passes = "pass" if result.iterations == 1 else "passes"
        msg = f"✅ Done in {result.iterations} {passes}. View + download .glb: {_viewer_link(session.sid)}"
        session.add_turn("agent", msg)
        await _safe_send(sms.from_number, msg)


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
    return {
        "sid": s.sid,
        "phone": s.phone,
        "status": s.status,
        "iterations": s.iterations,
        "objects": [o.name for o in s.spec.objects] if s.spec else [],
        "turns": [{"role": t.role, "text": t.text, "ts": t.ts} for t in s.turns],
        "png": f"/out/{s.sid}/model.png?v={v}" if v else None,
        "glb": f"/out/{s.sid}/model.glb?v={v}" if v else None,
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


def _page(filename: str, **subs: str) -> HTMLResponse:
    html = (WEB_DIR / filename).read_text()
    for k, val in subs.items():
        html = html.replace(f"__{k}__", val)
    return HTMLResponse(html)


@app.get("/v/{sid}", response_class=HTMLResponse)
async def viewer(sid: str):
    return _page("viewer.html", SID=sid)


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return _page("dashboard.html")


@app.get("/health")
async def health():
    return {"ok": True, "public_url": settings.public_url or None}
