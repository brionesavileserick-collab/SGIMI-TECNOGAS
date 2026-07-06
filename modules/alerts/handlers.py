"""
Alerts event handlers - React to events and generate alerts.
"""

from typing import Dict, Any
from sqlalchemy.orm import Session
from modules.alerts.service import AlertService
from core.event_bus import event_bus
from core.settings import settings
import logging

logger = logging.getLogger(__name__)


class AlertHandlers:
    """Event handlers for alerts module."""

    def __init__(self, db: Session):
        self.db = db
        self.service = AlertService(db)
        self._register_handlers()
        logger.info("Alert handlers registered")

    def _register_handlers(self):
        """Register all event handlers."""
        # Listen for inventory updates to detect low stock
        event_bus.subscribe(settings.Events.INVENTORY_UPDATED, self.handle_inventory_updated)

        # Listen for validated movements as required by the event flow.
        event_bus.subscribe(settings.Events.MOVEMENT_VALIDATED, self.handle_movement_validated)

    def handle_inventory_updated(self, data: Dict[str, Any]):
        """
        Handle inventory.updated event.
        Check for low stock conditions.
        """
        try:
            product_id = data.get("product_id")
            branch_id = data.get("branch_id")
            digital_stock = data.get("digital_stock")
            physical_stock = data.get("physical_stock")

            if not all([product_id, branch_id]):
                return

            if data.get("is_low_stock"):
                self._create_low_stock_alert(product_id, branch_id, digital_stock, data.get("min_stock", 0))

            if data.get("has_discrepancy"):
                self._create_discrepancy_alert(product_id, branch_id, physical_stock, digital_stock)

        except Exception as e:
            logger.error(f"Error handling inventory.updated for alerts: {e}")

    def handle_movement_validated(self, data: Dict[str, Any]):
        """
        Handle movement.validated event.
        Inventory updates are evaluated through inventory.updated.
        """
        logger.info(f"Validated movement received by alerts: {data}")

    def _create_low_stock_alert(self, product_id: int, branch_id: int,
                                  current_stock: int, min_stock: int):
        """Create low stock alert."""
        alert_data = self.service.create_alert(
            alert_type="low_stock",
            severity="warning",
            title="Stock Bajo Detectado",
            message=f"El stock actual ({current_stock}) ha caido por debajo del minimo ({min_stock})",
            product_id=product_id,
            branch_id=branch_id
        )

        # Emit alert event
        event_bus.emit(settings.Events.ALERT_GENERATED, alert_data)

    def _create_discrepancy_alert(self, product_id: int, branch_id: int,
                                    physical_stock: int, digital_stock: int):
        """Create discrepancy alert."""
        difference = physical_stock - digital_stock

        alert_data = self.service.create_alert(
            alert_type="discrepancy",
            severity="critical",
            title="Discrepancia de Inventario Detectada",
            message=f"Diferencia detectada: Fisico={physical_stock}, Digital={digital_stock}, Diferencia={difference}",
            product_id=product_id,
            branch_id=branch_id
        )

        # Emit alert event
        event_bus.emit(settings.Events.ALERT_GENERATED, alert_data)

    def unregister_handlers(self):
        """Unregister all event handlers."""
        event_bus.unsubscribe(settings.Events.INVENTORY_UPDATED, self.handle_inventory_updated)
        event_bus.unsubscribe(settings.Events.MOVEMENT_VALIDATED, self.handle_movement_validated)
        logger.info("Alert handlers unregistered")


def setup_alert_handlers(db: Session) -> AlertHandlers:
    """Setup and return alert handlers."""
    return AlertHandlers(db)
