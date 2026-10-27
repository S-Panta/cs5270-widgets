import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class RequestSource(ABC):
    @abstractmethod
    def get_next_request(self):
        pass


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
