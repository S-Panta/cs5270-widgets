import json
import logging

from widget_consumer.consumer import Consumer
from widget_consumer.models import Widget
from widget_consumer.sources import RequestSource
from widget_consumer.stores import WidgetStore


class FakeSource(RequestSource):
    """Returns queued items one at a time; None means an empty poll."""

    def __init__(self, items=(), fail_ack=False):
        self.items = list(items)
        self.acknowledged = 0
        self.fail_ack = fail_ack

    def get_next_request(self):
        return self.items.pop(0) if self.items else None

    def acknowledge(self):
        self.acknowledged += 1
        if self.fail_ack:
            raise RuntimeError("ack failed")


class FailingSource(RequestSource):
    def __init__(self):
        self.acknowledged = 0

    def get_next_request(self):
        raise RuntimeError("S3 is down")

    def acknowledge(self):
        self.acknowledged += 1


class InterruptingSource(RequestSource):
    def get_next_request(self):
        raise KeyboardInterrupt


class FakeStore(WidgetStore):
    def __init__(self, fail=False):
        self.widgets = {}
        self.fail = fail

    @property
    def saved(self):
        return list(self.widgets.values())

    def save(self, widget):
        if self.fail:
            raise RuntimeError("store is down")
        self.widgets[(widget.widget_id, widget.owner)] = widget

    def get(self, widget_id, owner):
        return self.widgets.get((widget_id, owner))

    def delete(self, widget_id, owner):
        return self.widgets.pop((widget_id, owner), None) is not None


def request_json(type_="create", widget_id="w-1", **extra):
    data = {
        "type": type_,
        "requestId": f"req-{widget_id}",
        "widgetId": widget_id,
        "owner": "Mary Matthews",
        "label": "Gear",
    }
    data.update(extra)
    return json.dumps(data)


def stored_widget():
    return Widget("w-1", "Mary Matthews", "Gear", "A gear", {"color": "blue"})


def test_no_request_returns_false():
    assert Consumer(FakeSource(), FakeStore()).process_one() is False


def test_source_error_returns_false(caplog):
    with caplog.at_level(logging.ERROR):
        assert Consumer(FailingSource(), FakeStore()).process_one() is False
    assert "Failed to retrieve a request" in caplog.text


def test_no_acknowledge_when_nothing_retrieved():
    source = FakeSource()
    Consumer(source, FakeStore()).process_one()
    assert source.acknowledged == 0


def test_no_acknowledge_when_retrieval_fails():
    source = FailingSource()
    Consumer(source, FakeStore()).process_one()
    assert source.acknowledged == 0


def test_create_request_saves_widget():
    store = FakeStore()
    assert Consumer(FakeSource([request_json()]), store).process_one() is True
    assert [w.widget_id for w in store.saved] == ["w-1"]


def test_create_saves_all_fields():
    store = FakeStore()
    raw = request_json(
        description="A gear", otherAttributes=[{"name": "color", "value": "blue"}]
    )
    Consumer(FakeSource([raw]), store).process_one()
    assert store.saved == [stored_widget()]


def test_update_existing_widget_changes_requested_fields_only():
    store = FakeStore()
    store.save(stored_widget())
    raw = request_json(
        "update", label="New", otherAttributes=[{"name": "size", "value": "9"}]
    )
    Consumer(FakeSource([raw]), store).process_one()
    assert store.get("w-1", "Mary Matthews") == Widget(
        "w-1", "Mary Matthews", "New", "A gear", {"color": "blue", "size": "9"}
    )


def test_update_empty_string_clears_label_and_removes_attribute():
    store = FakeStore()
    store.save(stored_widget())
    raw = request_json(
        "update", label="", otherAttributes=[{"name": "color", "value": ""}]
    )
    Consumer(FakeSource([raw]), store).process_one()
    assert store.get("w-1", "Mary Matthews") == Widget(
        "w-1", "Mary Matthews", None, "A gear", {}
    )


def test_update_missing_widget_warns_and_saves_nothing(caplog):
    store = FakeStore()
    with caplog.at_level(logging.WARNING):
        assert (
            Consumer(FakeSource([request_json("update")]), store).process_one() is True
        )
    assert store.saved == []
    assert "not found" in caplog.text


def test_delete_existing_widget_removes_it():
    store = FakeStore()
    store.save(stored_widget())
    Consumer(FakeSource([request_json("delete")]), store).process_one()
    assert store.get("w-1", "Mary Matthews") is None


def test_delete_missing_widget_warns_and_does_not_raise(caplog):
    store = FakeStore()
    with caplog.at_level(logging.WARNING):
        assert (
            Consumer(FakeSource([request_json("delete")]), store).process_one() is True
        )
    assert "does not exist" in caplog.text


def test_invalid_request_is_skipped_and_logged(caplog):
    store = FakeStore()
    with caplog.at_level(logging.ERROR):
        assert Consumer(FakeSource(["not json"]), store).process_one() is True
    assert store.saved == []
    assert "Skipping invalid request" in caplog.text


def test_store_failure_is_logged_and_does_not_stop_consumer(caplog):
    store = FakeStore(fail=True)
    with caplog.at_level(logging.ERROR):
        assert Consumer(FakeSource([request_json()]), store).process_one() is True
    assert "Failed to process request" in caplog.text


def test_acknowledged_after_success():
    source = FakeSource([request_json()])
    Consumer(source, FakeStore()).process_one()
    assert source.acknowledged == 1


def test_acknowledged_after_invalid_request():
    source = FakeSource(["not json"])
    Consumer(source, FakeStore()).process_one()
    assert source.acknowledged == 1


def test_acknowledged_after_store_failure():
    source = FakeSource([request_json()])
    Consumer(source, FakeStore(fail=True)).process_one()
    assert source.acknowledged == 1


def test_acknowledged_after_missing_widget():
    source = FakeSource([request_json("delete")])
    Consumer(source, FakeStore()).process_one()
    assert source.acknowledged == 1


def test_acknowledge_failure_is_logged_and_does_not_crash(caplog):
    source = FakeSource([request_json()], fail_ack=True)
    with caplog.at_level(logging.ERROR):
        assert Consumer(source, FakeStore()).process_one() is True
    assert "Failed to acknowledge request" in caplog.text


def test_run_processes_all_then_stops_after_max_empty_polls():
    store = FakeStore()
    sleeps = []
    source = FakeSource([request_json(widget_id="w-1"), request_json(widget_id="w-2")])
    Consumer(
        source, store, wait_seconds=0.1, max_empty_polls=2, sleep=sleeps.append
    ).run()
    assert sorted(w.widget_id for w in store.saved) == ["w-1", "w-2"]
    assert sleeps == [0.1, 0.1]


def test_run_resets_empty_poll_count_after_a_request():
    class Scripted(RequestSource):
        def __init__(self):
            self.script = [None, request_json(), None, None]

        def get_next_request(self):
            return self.script.pop(0)

    store = FakeStore()
    sleeps = []
    Consumer(Scripted(), store, max_empty_polls=2, sleep=sleeps.append).run()
    assert len(store.saved) == 1
    assert len(sleeps) == 3


def test_run_stops_cleanly_on_keyboard_interrupt(caplog):
    with caplog.at_level(logging.INFO):
        Consumer(InterruptingSource(), FakeStore()).run()
    assert "interrupted by user" in caplog.text
    assert "Consumer stopped" in caplog.text
