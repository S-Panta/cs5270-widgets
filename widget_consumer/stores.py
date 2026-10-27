"""Widget stores. Strategy pattern (Gamma et al., Design Patterns, 1994)."""

import json
import logging
from abc import ABC, abstractmethod

from .models import Widget

logger = logging.getLogger(__name__)


class WidgetStore(ABC):
    @abstractmethod
    def save(self, widget: Widget) -> None:
        """Store the widget."""


class S3WidgetStore(WidgetStore):
    """Stores widgets as JSON objects in an S3 bucket."""

    def __init__(self, s3_client, bucket: str):
        self.s3 = s3_client
        self.bucket = bucket

    @staticmethod
    def make_key(widget: Widget) -> str:
        owner_part = widget.owner.replace(" ", "-").lower()
        return f"widgets/{owner_part}/{widget.widget_id}"

    @staticmethod
    def to_json(widget: Widget) -> str:
        data = {
            "widgetId": widget.widget_id,
            "owner": widget.owner,
            "label": widget.label,
            "description": widget.description,
            "otherAttributes": [
                {"name": name, "value": value}
                for name, value in widget.other_attributes.items()
            ],
        }
        return json.dumps(data)

    def save(self, widget: Widget) -> None:
        key = self.make_key(widget)
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=self.to_json(widget).encode("utf-8"),
            ContentType="application/json",
        )
        logger.info("Saved widget %s to s3://%s/%s", widget.widget_id, self.bucket, key)


class DynamoDBWidgetStore(WidgetStore):
    """Stores widgets in dynamodb."""

    def __init__(self, table, key_name: str = "id"):
        self.table = table
        self.key_name = key_name

    def to_item(self, widget: Widget) -> dict:
        # Other attributes first, so the main fields win if a name collides.
        item = dict(widget.other_attributes)
        item[self.key_name] = widget.widget_id
        item["owner"] = widget.owner
        if widget.label is not None:
            item["label"] = widget.label
        if widget.description is not None:
            item["description"] = widget.description
        return item

    def save(self, widget: Widget) -> None:
        self.table.put_item(Item=self.to_item(widget))
        logger.info(
            "Saved widget %s to DynamoDB table %s", widget.widget_id, self.table.name
        )
