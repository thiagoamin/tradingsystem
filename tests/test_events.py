from engine.events import SignalEvent


def test_signal_event_fields():
    ev = SignalEvent(
        name="test",
        message="hello",
        severity="info",
        payload={"x": 1},
    )

    assert ev.name == "test"
    assert ev.message == "hello"
    assert ev.severity == "info"
    assert ev.payload == {"x": 1}