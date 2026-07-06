"""
Movement event handlers - React to events and log movements.
"""

from typing import Dict, Any
from sqlalchemy.orm import Session
from modules.movements.service import MovementService
from core.event_bus import event_bus
from core.settings import settings
import logging

logger = logging.getLogger(__name__)


class MovementHandlers:
    """Event handlers for movement module."""

    def __init__(self, db: Session):
        self.db = db
        self.service = MovementService(db)
        self._register_handlers()
        logger.info("Movement handlers registered")

    def _register_handlers(self):
        """Register all event handlers."""
        # Listen for movement events for logging/debugging
        event_bus.subscribe(settings.Events.MOVEMENT_CREATED, self.handle_movement_created)
        event_bus.subscribe(settings.Events.MOVEMENT_VALIDATED, self.handle_movement_validated)
        event_bus.subscribe(settings.Events.MOVEMENT_REJECTED, self.handle_movement_rejected)
        event_bus.subscribe(settings.Events.TRANSFER_SENT, self.handle_transfer_sent)

    def handle_movement_created(self, data: Dict[str, Any]):
        """Handle movement.created event."""
        logger.info(f"Movement created event: {data}")
        # Additional processing could be added here
        # Example: Send notifications, update dashboards, etc.

    def handle_movement_validated(self, data: Dict[str, Any]):
        """Handle movement.validated event."""
        logger.info(f"Movement validated event: {data}")
        # Inventory module handles the actual stock update
        # This handler is for movement-specific post-processing

    def handle_movement_rejected(self, data: Dict[str, Any]):
        """Handle movement.rejected event."""
        logger.info(f"Movement rejected event: {data}")
        # Example: Send notification to user who created the movement

    def handle_transfer_sent(self, data: Dict[str, Any]):
        """Handle transfer.sent event."""
        logger.info(f"Transfer sent event: {data}")
        # Transfer.received should be emitted by the destination branch
        # when they confirm receipt, not automatically here.
        # This handler only logs the event for audit purposes.

    def unregister_handlers(self):
        """Unregister all event handlers."""
        event_bus.unsubscribe(settings.Events.MOVEMENT_CREATED, self.handle_movement_created)
        event_bus.unsubscribe(settings.Events.MOVEMENT_VALIDATED, self.handle_movement_validated)
        event_bus.unsubscribe(settings.Events.MOVEMENT_REJECTED, self.handle_movement_rejected)
        event_bus.unsubscribe(settings.Events.TRANSFER_SENT, self.handle_transfer_sent)
        logger.info("Movement handlers unregistered")


def setup_movement_handlers(db: Session) -> MovementHandlers:
    """Setup and return movement handlers."""
    return MovementHandlers(db)
