import logging
from abc import ABC, abstractmethod
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)


class RequestSource(ABC):
    @abstractmethod
    def get_next_request(self) -> Optional[str]:
        """Return the next request body, or None if none is available."""

    def acknowledge(self):
        """Called after the last returned request has been processed."""


class S3RequestSource(RequestSource):
    def __init__(self, s3_client, bucket: str):
        self.s3 = s3_client
        self.bucket = bucket

    def get_next_request(self) -> Optional[str]:
        response = self.s3.list_objects_v2(Bucket=self.bucket, MaxKeys=1)
        contents = response.get("Contents", [])
        if not contents:
            return None

        key = contents[0]["Key"]
        obj = self.s3.get_object(Bucket=self.bucket, Key=key)
        body = obj["Body"].read().decode("utf-8")
        self.s3.delete_object(Bucket=self.bucket, Key=key)
        logger.info("Retrieved and deleted request %s from bucket %s", key, self.bucket)
        return body


class SqsRequestSource(RequestSource):
    """Reads requests from SQS"""

    def __init__(
        self,
        sqs_client,
        queue_url: str,
        wait_seconds: int = 10,
        visibility_timeout: int = 30,
        batch_size: int = 10,
    ):
        self.sqs = sqs_client
        self.queue_url = queue_url
        self.wait_seconds = wait_seconds
        self.visibility_timeout = visibility_timeout
        self.batch_size = batch_size
        self._buffer = deque()
        self._current = None

    def get_next_request(self) -> Optional[str]:
        self._current = None
        if not self._buffer:
            self._fill_buffer()
        if not self._buffer:
            return None
        self._current = self._buffer.popleft()
        return self._current["Body"]

    def _fill_buffer(self) -> None:
        response = self.sqs.receive_message(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=self.batch_size,
            WaitTimeSeconds=self.wait_seconds,
            VisibilityTimeout=self.visibility_timeout,
        )
        messages = response.get("Messages", [])
        logger.debug("Received %d message(s) from %s", len(messages), self.queue_url)
        self._buffer.extend(messages)

    def acknowledge(self) -> None:
        if self._current is None:
            return
        self.sqs.delete_message(
            QueueUrl=self.queue_url,
            ReceiptHandle=self._current["ReceiptHandle"],
        )
        logger.info("Deleted message %s from queue", self._current.get("MessageId"))
        self._current = None
