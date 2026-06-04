"""Offline tests for the user-photo intake path (no network / Blender / API).

Covers the schemas, the ViewPlanner sanitizer, the PhotoIntake FSM, and
reference_from_photos (user photos -> a per-object Reference, photos-only).
"""
from app.agents.photoplan import _sanitize
from app.agents.reference import reference_from_photos
from app.models import BuildSpec, ObjectBrief, ObjectViews, PhotoPlan
from app.state import ObjectIntake, PhotoIntake


def _spec(*names: str) -> BuildSpec:
    return BuildSpec(
        title="t", objects=[ObjectBrief(name=n, description=f"a {n}") for n in names]
    )


def test_photoplan_defaults():
    ov = ObjectViews(object_name="chair")
    assert ov.needs_photos is False and ov.views == [] and ov.prompts == []
    assert PhotoPlan().objects == []


def test_sanitize_drops_unknown_objects_and_views():
    spec = _spec("chair")
    raw = PhotoPlan(objects=[
        ObjectViews(object_name="chair", needs_photos=True,
                    views=["front", "FRONT", "weird", "back"], prompts=["a"]),
        ObjectViews(object_name="ghost", needs_photos=True, views=["front"]),  # not in spec
    ])
    out = _sanitize(raw, spec)
    assert len(out.objects) == 1
    o = out.objects[0]
    assert o.object_name == "chair" and o.needs_photos is True
    assert o.views == ["front", "back"]          # deduped (case-insensitive) + filtered
    assert len(o.prompts) == len(o.views)        # prompts padded to align with views
    assert o.prompts[1] and "chair" in o.prompts[1]  # synthesized default mentions the object


def test_sanitize_needs_photos_false_when_no_views():
    spec = _spec("ball")
    out = _sanitize(PhotoPlan(objects=[
        ObjectViews(object_name="ball", needs_photos=True, views=[])
    ]), spec)
    assert out.objects[0].needs_photos is False and out.objects[0].views == []


def test_intake_fsm_progress():
    obj = ObjectIntake(
        name="chair", label="chair", views=["front", "back", "side"],
        prompts={"front": "f", "back": "b", "side": "s"},
    )
    intake = PhotoIntake(id="1", request="a chair", is_edit=False, spec=_spec("chair"),
                         objects=[obj])
    assert intake.find("chair") is obj and intake.find("nope") is None
    assert obj.missing() == ["front", "back", "side"]
    assert intake.needed() == [("chair", "front"), ("chair", "back"), ("chair", "side")]
    assert not intake.complete()

    obj.received["front"] = "/tmp/front.jpg"
    obj.received["back"] = "/tmp/back.jpg"
    assert obj.missing() == ["side"] and not intake.complete()
    obj.received["side"] = "/tmp/side.jpg"
    assert obj.missing() == [] and intake.complete()


def test_reference_from_photos_maps_views(tmp_path):
    # Only existing files become images; labels stay aligned and in view order.
    front = tmp_path / "front.jpg"; front.write_bytes(b"\xff\xd8x")
    side = tmp_path / "side.jpg"; side.write_bytes(b"\xff\xd8x")
    obj = ObjectIntake(
        name="wooden_chair", label="wooden chair",
        views=["front", "back", "side"], prompts={},
        received={"front": str(front), "back": str(tmp_path / "missing.jpg"), "side": str(side)},
    )
    ref = reference_from_photos(obj)
    assert ref.object_name == "wooden_chair"
    assert ref.images == [str(front), str(side)]   # missing one dropped
    assert ref.image_labels == ["front", "side"]   # labels track the kept images
    assert ref.real_dims_m == 0.0                  # photos-only -> no web size
    assert "wooden chair" in ref.facts
