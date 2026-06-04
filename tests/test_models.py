"""Offline schema/parse tests — no network, Blender, or API needed."""
from app.messaging import InboundSMS
from app.models import BuildSpec, Clarification, Critique, ObjectBrief, Part
from app.state import SessionStore


def test_buildspec_defaults():
    s = BuildSpec(title="car", objects=[ObjectBrief(name="car", description="a red sports car")])
    assert s.environment  # has a sensible default
    assert s.camera_hint
    o = s.objects[0]
    assert o.approx_size_m == 1.0
    assert o.material_hint == ""
    assert o.position_hint == ""
    # WS2 structural fields default empty -> backward compatible (free-form build).
    assert o.parts == []
    assert o.proportions == "" and o.symmetry == ""


def test_object_with_parts():
    o = ObjectBrief(
        name="chair",
        description="a wooden chair",
        approx_size_m=1.0,
        parts=[
            Part(name="seat", shape_hint="rounded box", approx_dims_m=[0.45, 0.45, 0.05],
                 anchor="0.45 m up"),
            Part(name="leg", shape_hint="thin cylinder", approx_dims_m=[0.05, 0.05, 0.45],
                 anchor="4x mirrored under the seat corners"),
        ],
        symmetry="bilateral left-right",
    )
    assert len(o.parts) == 2
    assert o.parts[0].name == "seat"
    assert o.parts[1].approx_dims_m == [0.05, 0.05, 0.45]
    # Round-trips through JSON (the planner<->builder contract).
    assert ObjectBrief.model_validate_json(o.model_dump_json()) == o


def test_clarification_and_critique_defaults():
    c = Clarification(needs_info=False)
    assert c.question == ""
    cr = Critique(matches_request=True)
    assert cr.issues == [] and cr.patch_instructions == ""


def test_inbound_parse_strips_and_maps():
    payload = {
        "event": "sms_received",
        "line_id": "L1",
        "from_number": "+15555550123",
        "to_number": "+19788611660",
        "message": "  a red cube  ",
        "message_sid": "SM1",
    }
    sms = InboundSMS.from_payload(payload)
    assert sms.from_number == "+15555550123"
    assert sms.message == "a red cube"  # trimmed
    assert sms.message_sid == "SM1"
    assert sms.line_id == "L1"


def test_sid_for_keeps_digits():
    assert SessionStore.sid_for("+972 52-738-2350") == "972527382350"
    assert SessionStore.sid_for("") == "anon"
