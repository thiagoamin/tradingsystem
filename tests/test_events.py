from datetime import datetime

from engine.events import Event


def test_event_fields():
    ev = Event(
        ts=datetime.now(),
        type="signal",
        name="test",
        message="hello",
        severity="info",
        payload={"x": 1},
    )

    assert ev.name == "test"
    assert ev.message == "hello"
    assert ev.severity == "info"
    assert ev.payload == {"x": 1}
