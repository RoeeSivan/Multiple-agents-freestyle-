"""Offline tests for the deterministic geometry audit + feedback merge.

The Blender measurement (`_measure`) is monkeypatched, so the comparison logic
(mis-size / scatter / missing / empty) is exercised without a live Blender.
"""
from app.models import BuildSpec, Critique, GeometryAudit, ObjectAudit, ObjectBrief
from app.pipeline import _merge_feedback
from app.rendering import geometry_audit


def _spec(name="chair", size=1.0):
    return BuildSpec(
        title=name,
        objects=[ObjectBrief(name=name, description=f"a {name}", approx_size_m=size)],
    )


def _patch_measure(monkeypatch, objs):
    monkeypatch.setattr(geometry_audit, "_measure", lambda: objs)


def test_audit_clean_scene_ok(monkeypatch):
    _patch_measure(
        monkeypatch,
        [ObjectAudit(name="chair", dims_m=[0.5, 0.5, 1.0], longest_dim_m=1.0,
                     scatter_groups=1, has_geometry=True)],
    )
    a = geometry_audit.audit_scene(_spec("chair", 1.0))
    assert a.ok and a.problems == []


def test_audit_flags_oversize(monkeypatch):
    _patch_measure(
        monkeypatch,
        [ObjectAudit(name="tree", dims_m=[2, 2, 9.4], longest_dim_m=9.4,
                     scatter_groups=1, has_geometry=True)],
    )
    a = geometry_audit.audit_scene(_spec("tree", 4.0))
    assert not a.ok
    assert any("mis-sized" in p and "tree" in p for p in a.problems)


def test_audit_flags_scatter(monkeypatch):
    _patch_measure(
        monkeypatch,
        [ObjectAudit(name="chair", dims_m=[0.5, 0.5, 1.0], longest_dim_m=1.0,
                     scatter_groups=3, has_geometry=True)],
    )
    a = geometry_audit.audit_scene(_spec("chair", 1.0))
    assert not a.ok
    assert any("floating apart" in p for p in a.problems)


def test_audit_flags_flat_parts(monkeypatch):
    # A chair whose seat/backrest are flat planes -> flat_islands > 0 is flagged.
    _patch_measure(
        monkeypatch,
        [ObjectAudit(name="chair", dims_m=[0.5, 0.5, 0.9], longest_dim_m=0.9,
                     scatter_groups=1, flat_islands=2, has_geometry=True)],
    )
    a = geometry_audit.audit_scene(_spec("chair", 0.9))
    assert not a.ok
    assert any("FLAT" in p and "chair" in p for p in a.problems)


def test_audit_flags_missing(monkeypatch):
    _patch_measure(monkeypatch, [])  # nothing built
    a = geometry_audit.audit_scene(_spec("chair", 1.0))
    assert not a.ok
    assert any("MISSING" in p for p in a.problems)


def test_audit_size_target_override(monkeypatch):
    # Real-world dims (WS3) override the planner's guess: 9.4 m matches a 9 m target.
    _patch_measure(
        monkeypatch,
        [ObjectAudit(name="tree", dims_m=[2, 2, 9.4], longest_dim_m=9.4,
                     scatter_groups=1, has_geometry=True)],
    )
    a = geometry_audit.audit_scene(_spec("tree", 4.0), size_targets={"tree": 9.0})
    assert a.ok


def test_audit_single_object_name_fallback(monkeypatch):
    # Builder named it differently; single-object plan falls back to the lone object.
    _patch_measure(
        monkeypatch,
        [ObjectAudit(name="Cube.001", dims_m=[1, 1, 1], longest_dim_m=1.0,
                     scatter_groups=1, has_geometry=True)],
    )
    a = geometry_audit.audit_scene(_spec("chair", 1.0))
    assert a.ok


def test_merge_feedback_combines_both():
    audit = GeometryAudit(ok=False, problems=["object 'tree' is mis-sized: scale by ~0.4x."])
    crit = Critique(matches_request=False, patch_instructions="round the trunk")
    merged = _merge_feedback(audit, crit)
    assert "MEASURED" in merged and "tree" in merged
    assert "VISUAL" in merged and "round the trunk" in merged


def test_merge_feedback_empty_when_clean():
    assert _merge_feedback(GeometryAudit(ok=True), Critique(matches_request=True)) == ""
