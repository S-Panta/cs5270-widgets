# Tests for Consumer: each process_one branch and the run() loop.
import json
import logging

import pytest

from widget_consumer.consumer import Consumer
from widget_consumer.sources import RequestSource
from widget_consumer.stores import WidgetStore


class FakeSource(RequestSource):
    """Returns queued items one at a time; None means an empty poll."""

    def __init__(self, items=()):
        self.items = list(items)

    def get_next_request(self):
        return self.items.pop(0) if self.items else None


class FailingSource(RequestSource):
    def get_next_request(self):
        raise RuntimeError("S3 is down")


class FakeStore(WidgetStore):
    def __init__(self, fail=False):
        self.saved = []
        self.fail = fail

    def save(self, widget):
        if self.fail:
            raise RuntimeError("store is down")
        self.saved.append(widget)


def request_json(type_="create", widget_id="w-1"):
    return json.dumps(
        {
            "type": type_,
            "requestId": f"req-{widget_id}",
            "widgetId": widget_id,
            "owner": "Mary Matthews",
            "label": "Gear",
        }
    )


def test_no_request_returns_false():
    assert Consumer(FakeSource(), FakeStore()).process_one() is False


def test_create_request_saves_widget():
    store = FakeStore()
    assert Consumer(FakeSource([request_json()]), store).process_one() is True
    assert [w.widget_id for w in store.saved] == ["w-1"]


def test_invalid_request_is_skipped_and_logged(caplog):
    store = FakeStore()
    with caplog.at_level(logging.ERROR):
        assert Consumer(FakeSource(["not json"]), store).process_one() is True
    assert store.saved == []
    assert "Skipping invalid request" in caplog.text


@pytest.mark.parametrize("type_", ["update", "delete"])
def test_update_and_delete_are_skipped_with_warning(type_, caplog):
    store = FakeStore()
    with caplog.at_level(logging.WARNING):
        Consumer(FakeSource([request_json(type_)]), store).process_one()
    assert store.saved == []
    assert "not supported yet" in caplog.text


def test_source_error_returns_false(caplog):
    with caplog.at_level(logging.ERROR):
        assert Consumer(FailingSource(), FakeStore()).process_one() is False
    assert "Failed to retrieve a request" in caplog.text
