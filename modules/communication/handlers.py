"""Communication event handlers."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.event_bus import event_bus
from core.settings import settings

logger = logging.getLogger(__name__)


class CommunicationHandlers:
    """Lightweight handlers for communication events."""

    def __init__(self, db):
        self.db = db
        self._register_handlers()

    def _register_handlers(self):
        event_bus.subscribe(settings.Events.COMMUNICATION_SENT, self.on_message_sent)
        event_bus.subscribe(settings.Events.COMMUNICATION_READ, self.on_message_read)
        event_bus.subscribe(settings.Events.ANNOUNCEMENT_BROADCAST, self.on_announcement_broadcast)

    def on_message_sent(self, data: Optional[Dict[str, Any]]):
        logger.info("Communication sent: %s", data)

    def on_message_read(self, data: Optional[Dict[str, Any]]):
        logger.info("Communication read: %s", data)

    def on_announcement_broadcast(self, data: Optional[Dict[str, Any]]):
        logger.info("Announcement broadcast: %s", data)
