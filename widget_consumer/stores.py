"""Widget stores. Strategy pattern (Gamma et al., Design Patterns, 1994)."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Optional

from botocore.exceptions import ClientError

from .models import Widget

logger = logging.getLogger(__name__)

_S3_MISSING_CODES = ("NoSuchKey", "404", "NotFound")


class WidgetStore(ABC):
    @abstractmethod
    def save(self, widget: Widget) -> None:
        """Store the widget (create or overwrite)."""

    @abstractmethod
    def get(self, widget_id: str, owner: str) -> Optional[Widget]:
        """Return the stored widget, or None if it does not exist."""

    @abstractmethod
    def delete(self, widget_id: str, owner: str) -> bool:
        """Delete the widget. Return False if it did not exist."""


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

    @staticmethod
    def from_json(text: str) -> Widget:
        data = json.loads(text)
        return Widget(
            widget_id=data["widgetId"],
            owner=data["owner"],
            label=data.get("label"),
            description=data.get("description"),
            other_attributes={
                a["name"]: a["value"] for a in data.get("otherAttributes") or []
            },
        )

    @staticmethod
    def _is_missing(error: ClientError) -> bool:
        return error.response.get("Error", {}).get("Code") in _S3_MISSING_CODES

    def _key_for(self, widget_id: str, owner: str) -> str:
        # Reuse make_key so the key format lives in exactly one place.
        return self.make_key(Widget(widget_id=widget_id, owner=owner))

    def save(self, widget: Widget) -> None:
        key = self.make_key(widget)
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=self.to_json(widget).encode("utf-8"),
            ContentType="application/json",
        )
        logger.info("Saved widget %s to s3://%s/%s", widget.widget_id, self.bucket, key)

    def get(self, widget_id: str, owner: str) -> Optional[Widget]:
        key = self._key_for(widget_id, owner)
        try:
            obj = self.s3.get_object(Bucket=self.bucket, Key=key)
        except ClientError as error:
            if self._is_missing(error):
                return None
            raise
        return self.from_json(obj["Body"].read().decode("utf-8"))

    def delete(self, widget_id: str, owner: str) -> bool:
        key = self._key_for(widget_id, owner)
        try:
            # S3 delete_object succeeds even for missing keys, so check first.
            self.s3.head_object(Bucket=self.bucket, Key=key)
        except ClientError as error:
            if self._is_missing(error):
                return False
            raise
        self.s3.delete_object(Bucket=self.bucket, Key=key)
        logger.info("Deleted widget %s from s3://%s/%s", widget_id, self.bucket, key)
        return True


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

    def from_item(self, item: dict) -> Widget:
        reserved = {self.key_name, "owner", "label", "description"}
        return Widget(
            widget_id=item[self.key_name],
            owner=item.get("owner", ""),
            label=item.get("label"),
            description=item.get("description"),
            other_attributes={k: v for k, v in item.items() if k not in reserved},
        )

    def save(self, widget: Widget) -> None:
        self.table.put_item(Item=self.to_item(widget))
        logger.info(
            "Saved widget %s to DynamoDB table %s", widget.widget_id, self.table.name
        )

    def get(self, widget_id: str, owner: str) -> Optional[Widget]:
        item = self.table.get_item(Key={self.key_name: widget_id}).get("Item")
        if item is None:
            return None
        return self.from_item(item)

    def delete(self, widget_id: str, owner: str) -> bool:
        try:
            self.table.delete_item(
                Key={self.key_name: widget_id},
                ConditionExpression="attribute_exists(#k)",
                ExpressionAttributeNames={"#k": self.key_name},
            )
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise
        logger.info(
            "Deleted widget %s from DynamoDB table %s", widget_id, self.table.name
        )
        return True
