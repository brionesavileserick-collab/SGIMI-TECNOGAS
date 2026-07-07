"""
Movement event handlers - React to events and log movements.

Handlers registrados:
  Originales : MOVEMENT_CREATED, MOVEMENT_VALIDATED, MOVEMENT_REJECTED, TRANSFER_SENT
  Nuevos     : MOVEMENT_CANCELLED, MOVEMENT_REVERSED, TRANSFER_REJECTED
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
        # Original handlers
        event_bus.subscribe(settings.Events.MOVEMENT_CREATED, self.handle_movement_created)
        event_bus.subscribe(settings.Events.MOVEMENT_VALIDATED, self.handle_movement_validated)
        event_bus.subscribe(settings.Events.MOVEMENT_REJECTED, self.handle_movement_rejected)
        event_bus.subscribe(settings.Events.TRANSFER_SENT, self.handle_transfer_sent)
        # Exp 1 – Cancelación y reversión
        event_bus.subscribe(settings.Events.MOVEMENT_CANCELLED, self.handle_movement_cancelled)
        event_bus.subscribe(settings.Events.MOVEMENT_REVERSED, self.handle_movement_reversed)
        # Exp 2 – Rechazo de recepción de transferencia
        event_bus.subscribe(settings.Events.TRANSFER_REJECTED, self.handle_transfer_rejected)

    # ------------------------------------------------------------------
    # Original handlers
    # ------------------------------------------------------------------

    def handle_movement_created(self, data: Dict[str, Any]):
        """Handle movement.created event."""
        logger.info(
            f"[movement.created] ID={data.get('movement_id')} "
            f"type={data.get('movement_type')} qty={data.get('quantity')} "
            f"branch={data.get('branch_id')} priority={data.get('priority')} "
            f"source={data.get('source')}"
        )

    def handle_movement_validated(self, data: Dict[str, Any]):
        """Handle movement.validated event."""
        logger.info(
            f"[movement.validated] ID={data.get('movement_id')} "
            f"type={data.get('movement_type')} qty={data.get('quantity')} "
            f"branch={data.get('branch_id')} validator={data.get('validator_id')}"
        )
        # Inventory module handles actual stock updates via its own handlers.

    def handle_movement_rejected(self, data: Dict[str, Any]):
        """Handle movement.rejected event."""
        logger.info(
            f"[movement.rejected] ID={data.get('movement_id')} "
            f"reason='{data.get('reason')}' validator={data.get('validator_id')}"
        )

    def handle_transfer_sent(self, data: Dict[str, Any]):
        """Handle transfer.sent event."""
        logger.info(
            f"[transfer.sent] movement={data.get('movement_id')} "
            f"product={data.get('product_id')} qty={data.get('quantity')} "
            f"origin={data.get('origin_branch_id')} "
            f"destination={data.get('destination_branch_id')}"
        )
        # Destination branch confirms receipt via confirm_transfer_reception().
        # This handler is for audit/logging only.

    # ------------------------------------------------------------------
    # New handlers – Exp 1
    # ------------------------------------------------------------------

    def handle_movement_cancelled(self, data: Dict[str, Any]):
        """Handle movement.cancelled event."""
        logger.info(
            f"[movement.cancelled] ID={data.get('movement_id')} "
            f"type={data.get('movement_type')} qty={data.get('quantity')} "
            f"by={data.get('cancelled_by')} reason='{data.get('reason')}'"
        )

    def handle_movement_reversed(self, data: Dict[str, Any]):
        """Handle movement.reversed event.

        Emitted when a compensatory movement is created to undo a cancelled one.
        The compensatory movement still requires validation through the normal flow.
        """
        logger.info(
            f"[movement.reversed] original={data.get('original_movement_id')} "
            f"compensatory={data.get('compensatory_movement_id')} "
            f"type={data.get('movement_type')} qty={data.get('quantity')} "
            f"by={data.get('reversed_by')}"
        )

    # ------------------------------------------------------------------
    # New handler – Exp 2
    # ------------------------------------------------------------------

    def handle_transfer_rejected(self, data: Dict[str, Any]):
        """Handle transfer.rejected event (reception rejected by destination branch)."""
        logger.warning(
            f"[transfer.rejected] movement={data.get('movement_id')} "
            f"product={data.get('product_id')} qty={data.get('quantity')} "
            f"origin={data.get('origin_branch_id')} "
            f"destination={data.get('destination_branch_id')} "
            f"by={data.get('rejected_by')} reason='{data.get('reason')}'"
        )
        # Origin branch should be notified to investigate discrepancy.
        # Alert generation or further compensatory logic can be added here.

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def unregister_handlers(self):
        """Unregister all event handlers."""
        event_bus.unsubscribe(settings.Events.MOVEMENT_CREATED, self.handle_movement_created)
        event_bus.unsubscribe(settings.Events.MOVEMENT_VALIDATED, self.handle_movement_validated)
        event_bus.unsubscribe(settings.Events.MOVEMENT_REJECTED, self.handle_movement_rejected)
        event_bus.unsubscribe(settings.Events.TRANSFER_SENT, self.handle_transfer_sent)
        event_bus.unsubscribe(settings.Events.MOVEMENT_CANCELLED, self.handle_movement_cancelled)
        event_bus.unsubscribe(settings.Events.MOVEMENT_REVERSED, self.handle_movement_reversed)
        event_bus.unsubscribe(settings.Events.TRANSFER_REJECTED, self.handle_transfer_rejected)
        logger.info("Movement handlers unregistered")


def setup_movement_handlers(db: Session) -> MovementHandlers:
    """Setup and return movement handlers."""
    return MovementHandlers(db)
