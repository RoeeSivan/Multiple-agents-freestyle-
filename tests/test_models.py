"""Offline schema/parse tests — no network, Blender, or API needed."""
from app.messaging import InboundSMS
from app.models import BuildSpec, Clarification, Critique, ObjectBrief
from app.state import SessionStore


def test_buildspec_defaults():
    s = BuildSpec(title="car", objects=[ObjectBrief(name="car", description="a red sports car")])
    assert s.environment  # has a sensible default
    assert s.camera_hint
    o = s.objects[0]
    assert o.approx_size_m == 1.0
    assert o.material_hint == ""
    assert o.position_hint == ""


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
