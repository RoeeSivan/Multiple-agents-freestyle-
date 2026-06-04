"""HTTP tests for the photo-upload endpoints (no Blender / network).

Drives the real FastAPI app via TestClient: inject a parked PhotoIntake, then
hit /api/intake, /u/{sid}/photo, and /u/{sid}/complete. The actual build is
stubbed so nothing touches Blender.
"""
import app.server.api as api
from app.models import BuildSpec, ObjectBrief
from app.state import ObjectIntake, PhotoIntake, store


def _seed_intake() -> str:
    sess = store.get("+1 555 000 9001")
    spec = BuildSpec(
        title="chair", objects=[ObjectBrief(name="wooden_chair", description="a wooden chair")]
    )
    obj = ObjectIntake(
        name="wooden_chair", label="wooden chair", views=["front", "back"],
        prompts={"front": "send front", "back": "send back"},
    )
    sess.intake = PhotoIntake(
        id="testintake", request="a wooden chair", is_edit=False, spec=spec, objects=[obj]
    )
    sess.status = "awaiting_photos"
    return sess.sid


def test_intake_upload_and_complete(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "OUT_DIR", tmp_path)
    from fastapi.testclient import TestClient

    sid = _seed_intake()
    client = TestClient(api.app)

    # 1) intake JSON reflects the requested views, none uploaded yet.
    j = client.get(f"/api/intake/{sid}").json()
    assert j["active"] and not j["complete"]
    views = j["objects"][0]["views"]
    assert [v["view"] for v in views] == ["front", "back"]
    assert all(not v["uploaded"] for v in views)

    # 2) unknown view is rejected.
    bad = client.post(
        f"/u/{sid}/photo",
        data={"object": "wooden_chair", "view": "underside"},
        files={"file": ("x.jpg", b"\xff\xd8x", "image/jpeg")},
    )
    assert bad.status_code == 400

    # 3) upload the front photo -> stored on disk + marked uploaded.
    ok = client.post(
        f"/u/{sid}/photo",
        data={"object": "wooden_chair", "view": "front"},
        files={"file": ("front.jpg", b"\xff\xd8\xff\xe0jpegbytes", "image/jpeg")},
    )
    assert ok.status_code == 200
    saved = tmp_path / sid / "userphotos" / "testintake" / "wooden_chair" / "front.jpg"
    assert saved.exists() and saved.read_bytes().startswith(b"\xff\xd8")
    front = next(v for v in ok.json()["objects"][0]["views"] if v["view"] == "front")
    assert front["uploaded"] and front["url"].endswith("/wooden_chair/front.jpg")

    # 4) complete schedules the build (stubbed) and reports building.
    called = {}

    async def _stub_build(s):
        called["sid"] = s

    monkeypatch.setattr(api, "_run_intake_build", _stub_build)
    done = client.post(f"/u/{sid}/complete")
    assert done.status_code == 200 and done.json()["building"] is True
    assert called.get("sid") == sid  # background task fired with our sid


def test_complete_requires_at_least_one_photo(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "OUT_DIR", tmp_path)
    from fastapi.testclient import TestClient

    # Fresh sender, intake with nothing uploaded.
    sess = store.get("+1 555 000 9002")
    spec = BuildSpec(title="t", objects=[ObjectBrief(name="lamp", description="a lamp")])
    sess.intake = PhotoIntake(
        id="i2", request="a lamp", is_edit=False, spec=spec,
        objects=[ObjectIntake(name="lamp", label="lamp", views=["front"], prompts={})],
    )
    client = TestClient(api.app)
    r = client.post(f"/u/{sess.sid}/complete")
    assert r.status_code == 400
