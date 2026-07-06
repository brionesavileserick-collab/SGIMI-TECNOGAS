"""
History event handlers - React to events and record them.
"""

from typing import Dict, Any
from sqlalchemy.orm import Session
from modules.history.service import HistoryService
from core.event_bus import event_bus
from core.settings import settings
import logging

logger = logging.getLogger(__name__)


class HistoryHandlers:
    """Event handlers for history module."""

    def __init__(self, db: Session):
        self.db = db
        self.service = HistoryService(db)
        self._register_handlers()
        logger.info("History handlers registered")

    def _register_handlers(self):
        """Register all event handlers."""
        # Product events
        event_bus.subscribe(settings.Events.PRODUCT_CREATED, self.handle_product_created)
        event_bus.subscribe(settings.Events.PRODUCT_UPDATED, self.handle_product_updated)
        event_bus.subscribe(settings.Events.PRODUCT_DELETED, self.handle_product_deleted)

        # Branch events
        event_bus.subscribe(settings.Events.BRANCH_CREATED, self.handle_branch_created)
        event_bus.subscribe(settings.Events.BRANCH_UPDATED, self.handle_branch_updated)
        event_bus.subscribe(settings.Events.BRANCH_DELETED, self.handle_branch_deleted)

        # Movement events
        event_bus.subscribe(settings.Events.MOVEMENT_CREATED, self.handle_movement_created)
        event_bus.subscribe(settings.Events.MOVEMENT_VALIDATED, self.handle_movement_validated)
        event_bus.subscribe(settings.Events.MOVEMENT_REJECTED, self.handle_movement_rejected)

        # Inventory events
        event_bus.subscribe(settings.Events.INVENTORY_UPDATED, self.handle_inventory_updated)
        event_bus.subscribe(settings.Events.INVENTORY_COUNTED, self.handle_inventory_counted)

        # Transfer events
        event_bus.subscribe(settings.Events.TRANSFER_SENT, self.handle_transfer_sent)
        event_bus.subscribe(settings.Events.TRANSFER_RECEIVED, self.handle_transfer_received)

        # Alert events
        event_bus.subscribe(settings.Events.ALERT_GENERATED, self.handle_alert_generated)

    def handle_product_created(self, data: Dict[str, Any]):
        """Record product creation in history."""
        self.service.record_event(
            event_type=settings.Events.PRODUCT_CREATED,
            entity_type="product",
            entity_id=data.get("product_id"),
            action="Producto creado",
            details=data
        )

    def handle_product_updated(self, data: Dict[str, Any]):
        """Record product update in history."""
        self.service.record_event(
            event_type=settings.Events.PRODUCT_UPDATED,
            entity_type="product",
            entity_id=data.get("product_id"),
            action="Producto actualizado",
            details=data
        )

    def handle_product_deleted(self, data: Dict[str, Any]):
        """Record product deletion in history."""
        self.service.record_event(
            event_type=settings.Events.PRODUCT_DELETED,
            entity_type="product",
            entity_id=data.get("product_id"),
            action="Producto eliminado",
            details=data
        )

    def handle_branch_created(self, data: Dict[str, Any]):
        """Record branch creation in history."""
        self.service.record_event(
            event_type=settings.Events.BRANCH_CREATED,
            entity_type="branch",
            entity_id=data.get("branch_id"),
            action="Sucursal creada",
            details=data
        )

    def handle_branch_updated(self, data: Dict[str, Any]):
        """Record branch update in history."""
        self.service.record_event(
            event_type=settings.Events.BRANCH_UPDATED,
            entity_type="branch",
            entity_id=data.get("branch_id"),
            action="Sucursal actualizada",
            details=data
        )

    def handle_branch_deleted(self, data: Dict[str, Any]):
        """Record branch deletion in history."""
        self.service.record_event(
            event_type=settings.Events.BRANCH_DELETED,
            entity_type="branch",
            entity_id=data.get("branch_id"),
            action="Sucursal eliminada",
            details=data
        )

    def handle_movement_created(self, data: Dict[str, Any]):
        """Record movement creation in history."""
        self.service.record_event(
            event_type=settings.Events.MOVEMENT_CREATED,
            entity_type="movement",
            entity_id=data.get("movement_id"),
            user_id=data.get("user_id"),
            action=f"Movimiento creado: {data.get('movement_type')}",
            details=data
        )

    def handle_movement_validated(self, data: Dict[str, Any]):
        """Record movement validation in history."""
        self.service.record_event(
            event_type=settings.Events.MOVEMENT_VALIDATED,
            entity_type="movement",
            entity_id=data.get("movement_id"),
            user_id=data.get("validator_id"),
            action=f"Movimiento validado: {data.get('movement_type')}",
            details=data
        )

    def handle_movement_rejected(self, data: Dict[str, Any]):
        """Record movement rejection in history."""
        self.service.record_event(
            event_type=settings.Events.MOVEMENT_REJECTED,
            entity_type="movement",
            entity_id=data.get("movement_id"),
            user_id=data.get("validator_id"),
            action=f"Movimiento rechazado: {data.get('movement_type')}",
            details=data
        )

    def handle_inventory_updated(self, data: Dict[str, Any]):
        """Record inventory update in history."""
        self.service.record_event(
            event_type=settings.Events.INVENTORY_UPDATED,
            entity_type="inventory",
            entity_id=data.get("inventory_id"),
            action="Inventario actualizado",
            details=data
        )

    def handle_inventory_counted(self, data: Dict[str, Any]):
        """Record inventory count in history."""
        self.service.record_event(
            event_type=settings.Events.INVENTORY_COUNTED,
            entity_type="inventory",
            entity_id=data.get("inventory_id"),
            action="Conteo de inventario registrado",
            details=data
        )

    def handle_transfer_sent(self, data: Dict[str, Any]):
        """Record transfer sent in history."""
        self.service.record_event(
            event_type=settings.Events.TRANSFER_SENT,
            entity_type="movement",
            entity_id=data.get("movement_id"),
            action="Transferencia enviada",
            details=data
        )

    def handle_transfer_received(self, data: Dict[str, Any]):
        """Record transfer received in history."""
        self.service.record_event(
            event_type=settings.Events.TRANSFER_RECEIVED,
            entity_type="inventory",
            entity_id=data.get("inventory_id"),
            action="Transferencia recibida",
            details=data
        )

    def handle_alert_generated(self, data: Dict[str, Any]):
        """Record alert generation in history."""
        self.service.record_event(
            event_type=settings.Events.ALERT_GENERATED,
            entity_type="alert",
            entity_id=data.get("id"),
            action=f"Alerta generada: {data.get('alert_type')}",
            details=data
        )

    def unregister_handlers(self):
        """Unregister all event handlers."""
        event_bus.unsubscribe(settings.Events.PRODUCT_CREATED, self.handle_product_created)
        event_bus.unsubscribe(settings.Events.PRODUCT_UPDATED, self.handle_product_updated)
        event_bus.unsubscribe(settings.Events.PRODUCT_DELETED, self.handle_product_deleted)

        event_bus.unsubscribe(settings.Events.BRANCH_CREATED, self.handle_branch_created)
        event_bus.unsubscribe(settings.Events.BRANCH_UPDATED, self.handle_branch_updated)
        event_bus.unsubscribe(settings.Events.BRANCH_DELETED, self.handle_branch_deleted)

        event_bus.unsubscribe(settings.Events.MOVEMENT_CREATED, self.handle_movement_created)
        event_bus.unsubscribe(settings.Events.MOVEMENT_VALIDATED, self.handle_movement_validated)
        event_bus.unsubscribe(settings.Events.MOVEMENT_REJECTED, self.handle_movement_rejected)

        event_bus.unsubscribe(settings.Events.INVENTORY_UPDATED, self.handle_inventory_updated)
        event_bus.unsubscribe(settings.Events.INVENTORY_COUNTED, self.handle_inventory_counted)

        event_bus.unsubscribe(settings.Events.TRANSFER_SENT, self.handle_transfer_sent)
        event_bus.unsubscribe(settings.Events.TRANSFER_RECEIVED, self.handle_transfer_received)

        event_bus.unsubscribe(settings.Events.ALERT_GENERATED, self.handle_alert_generated)
        logger.info("History handlers unregistered")


def setup_history_handlers(db: Session) -> HistoryHandlers:
    """Setup and return history handlers."""
    return HistoryHandlers(db)
