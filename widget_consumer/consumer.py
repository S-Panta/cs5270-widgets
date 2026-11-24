import logging
import time
from typing import Callable, Optional

from .models import Widget, WidgetRequest
from .sources import RequestSource
from .stores import WidgetStore

logger = logging.getLogger(__name__)


class Consumer:
    def __init__(
        self,
        source: RequestSource,
        store: WidgetStore,
        wait_seconds: float = 0.1,
        max_empty_polls: Optional[int] = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.source = source
        self.store = store
        self.wait_seconds = wait_seconds
        self.max_empty_polls = max_empty_polls
        self._sleep = sleep

    def run(self) -> None:
        logger.info("Consumer started")
        empty_polls = 0
        try:
            while self.max_empty_polls is None or empty_polls < self.max_empty_polls:
                if self.process_one():
                    empty_polls = 0
                else:
                    empty_polls += 1
                    self._sleep(self.wait_seconds)
        except KeyboardInterrupt:
            logger.info("Consumer interrupted by user")
        logger.info("Consumer stopped")

    def process_one(self) -> bool:
        try:
            raw = self.source.get_next_request()
        except Exception:
            logger.exception("Failed to retrieve a request")
            return False

        if raw is None:
            return False

        try:
            try:
                request = WidgetRequest.from_json(raw)
            except ValueError as error:
                # A malformed message can never become valid, so it is still acknowledged.
                logger.error("Skipping invalid request: %s", error)
                return True

            try:
                self.handle(request)
            except Exception:
                logger.exception("Failed to process request %s", request.request_id)
            return True
        finally:
            self._acknowledge()

    def _acknowledge(self) -> None:
        try:
            self.source.acknowledge()
        except Exception:
            logger.exception("Failed to acknowledge request")

    def handle(self, request: WidgetRequest) -> None:
        if request.type == "create":
            widget = Widget.from_request(request)
            self.store.save(widget)
            logger.info(
                "Request %s: created widget %s for owner %s",
                request.request_id,
                widget.widget_id,
                widget.owner,
            )
        elif request.type == "update":
            widget = self.store.get(request.widget_id, request.owner)
            if widget is None:
                logger.warning(
                    "Request %s: widget %s not found, nothing to update",
                    request.request_id,
                    request.widget_id,
                )
                return
            widget.apply_update(request)
            self.store.save(widget)
            logger.info(
                "Request %s: updated widget %s", request.request_id, widget.widget_id
            )
        elif request.type == "delete":
            if self.store.delete(request.widget_id, request.owner):
                logger.info(
                    "Request %s: deleted widget %s",
                    request.request_id,
                    request.widget_id,
                )
            else:
                logger.warning(
                    "Request %s: widget %s does not exist, nothing to delete",
                    request.request_id,
                    request.widget_id,
                )
        else:
            logger.warning(
                "Request %s: unknown type '%s'", request.request_id, request.type
            )
