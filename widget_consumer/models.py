# Data classes for Widget requests
# This shall verify the json object provided
import json
import re
from dataclasses import dataclass, field
from typing import Dict, Optional

REQUIRED_FIELDS = ("type", "requestId", "widgetId", "owner")
VALID_TYPES = ("create", "update", "delete")
OWNER_PATTERN = re.compile(r"[A-Za-z ]+")


@dataclass
class WidgetRequest:
    type: str
    request_id: str
    widget_id: str
    owner: str
    label: Optional[str] = None
    description: Optional[str] = None
    other_attributes: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_json(cls, text: str):
        """Parse a JSON Widget Request. Raises ValueError if it is invalid."""
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError) as error:
            raise ValueError(f"Invalid JSON: {error}") from error

        if not isinstance(data, dict):
            raise ValueError("Request must be a JSON object")

        missing = [name for name in REQUIRED_FIELDS if data.get(name) in (None, "")]
        if missing:
            raise ValueError(f"Missing required field(s): {', '.join(missing)}")

        if data["type"] not in VALID_TYPES:
            raise ValueError(f"Unknown request type: {data['type']}")

        if not OWNER_PATTERN.fullmatch(data["owner"]):
            raise ValueError(f"Invalid owner: {data['owner']}")

        other_attributes = {}
        for item in data.get("otherAttributes") or []:
            if not isinstance(item, dict) or "name" not in item or "value" not in item:
                raise ValueError(f"Invalid otherAttributes entry: {item}")
            other_attributes[item["name"]] = item["value"]

        return cls(
            type=data["type"],
            request_id=data["requestId"],
            widget_id=data["widgetId"],
            owner=data["owner"],
            label=data.get("label"),
            description=data.get("description"),
            other_attributes=other_attributes,
        )


@dataclass
class Widget:
    widget_id: str
    owner: str
    label: Optional[str] = None
    description: Optional[str] = None
    other_attributes: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_request(cls, request: WidgetRequest) -> "Widget":
        """Build a widget containing all data from a create request."""
        return cls(
            widget_id=request.widget_id,
            owner=request.owner,
            label=request.label,
            description=request.description,
            other_attributes=dict(request.other_attributes),
        )

    def apply_update(self, request: WidgetRequest):
        """Apply an update request in place ."""
        if request.label is not None:
            self.label = request.label or None
        if request.description is not None:
            self.description = request.description or None
        for name, value in request.other_attributes.items():
            if value is None:
                continue
            if value == "":
                self.other_attributes.pop(name, None)
            else:
                self.other_attributes[name] = value
