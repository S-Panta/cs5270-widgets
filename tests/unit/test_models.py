# This test only the json parser to see if it works correctly
import json

import pytest

from widget_consumer.models import Widget, WidgetRequest


def make_request_json(**overrides):
    data = {
        "type": "create",
        "requestId": "req-1",
        "widgetId": "w-1",
        "owner": "Mary Matthews",
        "label": "Gear",
        "description": "A gear",
        "otherAttributes": [
            {"name": "color", "value": "blue"},
            {"name": "size", "value": "430"},
        ],
    }
    data.update(overrides)
    return json.dumps({k: v for k, v in data.items() if v is not ...})


def test_from_json_valid_create_parses_all_fields():
    request = WidgetRequest.from_json(make_request_json())
    assert request.type == "create"
    assert request.request_id == "req-1"
    assert request.widget_id == "w-1"
    assert request.owner == "Mary Matthews"
    assert request.label == "Gear"
    assert request.description == "A gear"
    assert request.other_attributes == {"color": "blue", "size": "430"}


@pytest.mark.parametrize("field", ["type", "requestId", "widgetId", "owner"])
def test_from_json_missing_required_field_raises(field):
    with pytest.raises(ValueError, match=field):
        WidgetRequest.from_json(make_request_json(**{field: ...}))


@pytest.mark.parametrize("field", ["type", "requestId", "widgetId", "owner"])
def test_from_json_empty_required_field_raises(field):
    with pytest.raises(ValueError):
        WidgetRequest.from_json(make_request_json(**{field: ""}))


def test_from_json_optional_fields_missing_uses_defaults():
    request = WidgetRequest.from_json(
        make_request_json(label=..., description=..., otherAttributes=...)
    )
    assert request.label is None
    assert request.description is None
    assert request.other_attributes == {}


def test_from_json_null_other_attributes_gives_empty_dict():
    request = WidgetRequest.from_json(make_request_json(otherAttributes=None))
    assert request.other_attributes == {}


@pytest.mark.parametrize("text", ["not json", "", "{"])
def test_from_json_invalid_json_raises(text):
    with pytest.raises(ValueError, match="Invalid JSON"):
        WidgetRequest.from_json(text)


def test_from_json_non_object_raises():
    with pytest.raises(ValueError, match="JSON object"):
        WidgetRequest.from_json("[1, 2, 3]")


def test_from_json_unknown_type_raises():
    with pytest.raises(ValueError, match="Unknown request type"):
        WidgetRequest.from_json(make_request_json(type="explode"))


@pytest.mark.parametrize("type_", ["create", "update", "delete"])
def test_from_json_accepts_each_valid_type(type_):
    assert WidgetRequest.from_json(make_request_json(type=type_)).type == type_


@pytest.mark.parametrize("owner", ["Mary2", "Mary-Matthews", "Mary_M"])
def test_from_json_invalid_owner_raises(owner):
    with pytest.raises(ValueError, match="Invalid owner"):
        WidgetRequest.from_json(make_request_json(owner=owner))


def test_from_json_malformed_other_attribute_raises():
    with pytest.raises(ValueError, match="otherAttributes"):
        WidgetRequest.from_json(make_request_json(otherAttributes=[{"name": "color"}]))


def test_widget_from_request_copies_all_fields():
    request = WidgetRequest.from_json(make_request_json())
    widget = Widget.from_request(request)
    assert widget.widget_id == "w-1"
    assert widget.owner == "Mary Matthews"
    assert widget.label == "Gear"
    assert widget.description == "A gear"
    assert widget.other_attributes == {"color": "blue", "size": "430"}


def test_widget_from_request_copies_attributes_not_shares_them():
    request = WidgetRequest.from_json(make_request_json())
    widget = Widget.from_request(request)
    widget.other_attributes["color"] = "red"
    assert request.other_attributes["color"] == "blue"
