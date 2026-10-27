"""Command-line entry point."""

import logging

import boto3
import click

from .consumer import Consumer
from .sources import S3RequestSource
from .stores import DynamoDBWidgetStore, S3WidgetStore


def setup_logging(log_file: str) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
        force=True,
    )


def build_store(session, storage, widget_bucket, table, key_name):
    # Use of factory pattern
    if storage == "s3":
        if not widget_bucket:
            raise click.UsageError("--widget-bucket is required when --storage is s3")
        return S3WidgetStore(session.client("s3"), widget_bucket)
    if not table:
        raise click.UsageError("--table is required when --storage is dynamodb")
    return DynamoDBWidgetStore(session.resource("dynamodb").Table(table), key_name)


@click.command()
@click.option(
    "--request-bucket",
    required=True,
    help="Bucket to read Widget Requests from (Bucket 2).",
)
@click.option(
    "--storage",
    required=True,
    type=click.Choice(["s3", "dynamodb"], case_sensitive=False),
    help="Where to store widgets.",
)
@click.option(
    "--widget-bucket", help="Bucket to store widgets in (Bucket 3). Required for s3."
)
@click.option("--table", help="DynamoDB table name. Required for dynamodb.")
@click.option(
    "--key-name",
    default="id",
    show_default=True,
    help="Partition key name of the DynamoDB table.",
)
@click.option("--region", default="us-east-1", show_default=True, help="AWS region.")
@click.option(
    "--max-empty-polls",
    type=click.IntRange(min=1),
    default=None,
    help="Stop after this many consecutive empty polls. Default: run until Ctrl+C.",
)
@click.option(
    "--log-file", default="consumer.log", show_default=True, help="Log file path."
)
def main(
    request_bucket,
    storage,
    widget_bucket,
    table,
    key_name,
    region,
    max_empty_polls,
    log_file,
):
    """Consume Widget Requests from S3 and store widgets in S3 or DynamoDB."""
    session = boto3.Session(region_name=region)
    store = build_store(session, storage.lower(), widget_bucket, table, key_name)
    setup_logging(log_file)
    source = S3RequestSource(session.client("s3"), request_bucket)
    Consumer(source, store, max_empty_polls=max_empty_polls).run()


if __name__ == "__main__":
    main()
