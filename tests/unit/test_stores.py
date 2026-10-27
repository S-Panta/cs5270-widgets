# Tests for widget stores: S3 key/save and DynamoDB flattening/save.
import json

import boto3
import pytest
from moto import mock_aws

from widget_consumer.models import Widget
from widget_consumer.stores import DynamoDBWidgetStore, S3WidgetStore


def make_widget(**overrides):
    values = dict(
        widget_id="w-1", owner="Mary Matthews", label="Gear",
        description="A gear", other_attributes={"color": "blue", "size": "430"},
    )
    values.update(overrides)
    return Widget(**values)



@pytest.mark.parametrize("owner, expected", [
    ("Mary Matthews", "widgets/mary-matthews/w-1"),   
    ("Sue Ann Smith", "widgets/sue-ann-smith/w-1"),   
])
def test_make_key_transforms_owner(owner, expected):
    assert S3WidgetStore.make_key(make_widget(owner=owner)) == expected


def test_s3_save_stores_widget_json_at_key():
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket="widget-bucket")
        S3WidgetStore(s3, "widget-bucket").save(make_widget())

        body = s3.get_object(Bucket="widget-bucket", Key="widgets/mary-matthews/w-1")["Body"].read()
        assert json.loads(body) == {
            "widgetId": "w-1", "owner": "Mary Matthews", "label": "Gear",
            "description": "A gear",
            "otherAttributes": [
                {"name": "color", "value": "blue"},
                {"name": "size", "value": "430"},
            ],
        }



def test_to_item_flattens_other_attributes():
    assert DynamoDBWidgetStore(table=None).to_item(make_widget()) == {
        "id": "w-1", "owner": "Mary Matthews", "label": "Gear",
        "description": "A gear", "color": "blue", "size": "430",
    }


def test_to_item_skips_none_fields():
    widget = make_widget(label=None, description=None, other_attributes={})
    assert DynamoDBWidgetStore(table=None).to_item(widget) == {"id": "w-1", "owner": "Mary Matthews"}


def test_to_item_main_fields_win_on_collision_and_custom_key_name():
    widget = make_widget(other_attributes={"owner": "Someone Else"})
    item = DynamoDBWidgetStore(table=None, key_name="widget_id").to_item(widget)
    assert item["owner"] == "Mary Matthews"
    assert item["widget_id"] == "w-1"
    assert "id" not in item


def test_dynamodb_save_puts_item():
    with mock_aws():
        table = boto3.resource("dynamodb", region_name="us-east-1").create_table(
            TableName="widgets",
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        DynamoDBWidgetStore(table).save(make_widget())
        assert table.get_item(Key={"id": "w-1"})["Item"]["color"] == "blue"