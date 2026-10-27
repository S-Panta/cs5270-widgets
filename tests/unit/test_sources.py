import boto3
import pytest
from moto import mock_aws

from widget_consumer.sources import S3RequestSource

BUCKET = "test-requests"


@pytest.fixture
def s3():
    with mock_aws():
        # This fakes the credentials so that it doesn't touch the real bucket
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client

def test_debug_show_what_we_are_talking_to(s3):
    creds = boto3.Session().get_credentials()
    print("\nAccess key in use:", creds.access_key)
    print("Buckets visible:", [b["Name"] for b in s3.list_buckets()["Buckets"]])

def keys_in_bucket(s3):
    return [obj["Key"] for obj in s3.list_objects_v2(Bucket=BUCKET).get("Contents", [])]


def test_empty_bucket_returns_none(s3):
    assert S3RequestSource(s3, BUCKET).get_next_request() is None


def test_single_request_is_returned_and_deleted(s3):
    s3.put_object(Bucket=BUCKET, Key="1000", Body=b'{"a": 1}')
    source = S3RequestSource(s3, BUCKET)
    assert source.get_next_request() == '{"a": 1}'
    assert keys_in_bucket(s3) == []


def test_smallest_key_is_returned_first(s3):
    for key in ["1002", "1000", "1001"]:
        s3.put_object(Bucket=BUCKET, Key=key, Body=key.encode())
    source = S3RequestSource(s3, BUCKET)
    assert source.get_next_request() == "1000"
    assert keys_in_bucket(s3) == ["1001", "1002"]


def test_repeated_calls_drain_bucket_in_order_then_return_none(s3):
    for key in ["b", "a", "c"]:
        s3.put_object(Bucket=BUCKET, Key=key, Body=key.encode())
    source = S3RequestSource(s3, BUCKET)
    assert [source.get_next_request() for _ in range(4)] == ["a", "b", "c", None]