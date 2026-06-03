"""Offline schema/parse tests — no network or browser needed."""
from app.messaging import InboundSMS
from app.models import Obj, SceneSpec
from app.state import SessionStore


def test_scenespec_defaults():
    s = SceneSpec(objects=[Obj(name="cube", shape="box")])
    assert s.ground is True
    assert s.background.startswith("#")
    o = s.objects[0]
    assert o.color == "#cccccc"
    assert o.position == (0.0, 0.0, 0.0)
    assert o.material == "standard"


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
