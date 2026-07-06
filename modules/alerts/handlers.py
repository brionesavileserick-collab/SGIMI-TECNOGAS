"""
Alerts event handlers - React to events and generate alerts.
"""

from typing import Dict, Any
from sqlalchemy.orm import Session
from modules.alerts.service import AlertService
from modules.inventory.service import InventoryService
from core.event_bus import event_bus
from core.settings import settings
import logging

logger = logging.getLogger(__name__)


class AlertHandlers:
    """Event handlers for alerts module."""

    def __init__(self, db: Session):
        self.db = db
        self.service = AlertService(db)
        self.inventory_service = InventoryService(db)
        self._register_handlers()
        logger.info("Alert handlers registered")

    def _register_handlers(self):
        """Register all event handlers."""
        # Listen for inventory updates to detect low stock
        event_bus.subscribe(settings.Events.INVENTORY_UPDATED, self.handle_inventory_updated)

        # Listen for inventory counts to detect discrepancies
        event_bus.subscribe(settings.Events.INVENTORY_COUNTED, self.handle_inventory_counted)

        # Listen for movement rejections
        event_bus.subscribe(settings.Events.MOVEMENT_REJECTED, self.handle_movement_rejected)

        # Listen for alerts (alert chaining)
        event_bus.subscribe(settings.Events.ALERT_GENERATED, self.handle_alert_generated)

    def handle_inventory_updated(self, data: Dict[str, Any]):
        """
        Handle inventory.updated event.
        Check for low stock conditions.
        """
        try:
            product_id = data.get("product_id")
            branch_id = data.get("branch_id")
            digital_stock = data.get("digital_stock")

            if not all([product_id, branch_id]):
                return

            # Get full inventory data
            inventory = self.inventory_service.get_inventory_by_product_branch(product_id, branch_id)
            if not inventory:
                return

            # Check low stock
            if inventory["is_low_stock"]:
                self._create_low_stock_alert(product_id, branch_id, inventory["digital_stock"], inventory["min_stock"])

        except Exception as e:
            logger.error(f"Error handling inventory.updated for alerts: {e}")

    def handle_inventory_counted(self, data: Dict[str, Any]):
        """
        Handle inventory.counted event.
        Check for discrepancies between physical and digital stock.
        """
        try:
            product_id = data.get("product_id")
            branch_id = data.get("branch_id")
            physical_stock = data.get("physical_stock")

            if not all([product_id, branch_id]):
                return

            # Get inventory to check discrepancy
            inventory = self.inventory_service.get_inventory_by_product_branch(product_id, branch_id)
            if not inventory:
                return

            digital_stock = inventory["digital_stock"]

            # Check for discrepancy
            if physical_stock != digital_stock:
                self._create_discrepancy_alert(
                    product_id, branch_id,
                    physical_stock, digital_stock
                )

        except Exception as e:
            logger.error(f"Error handling inventory.counted for alerts: {e}")

    def handle_movement_rejected(self, data: Dict[str, Any]):
        """
        Handle movement.rejected event.
        Create alert for rejected movements.
        """
        try:
            movement_id = data.get("movement_id")
            product_id = data.get("product_id")
            branch_id = data.get("branch_id")
            reason = data.get("reason", "Sin razon especificada")

            if not movement_id:
                return

            self._create_validation_failed_alert(
                movement_id, product_id, branch_id, reason
            )

        except Exception as e:
            logger.error(f"Error handling movement.rejected for alerts: {e}")

    def handle_alert_generated(self, data: Dict[str, Any]):
        """
        Handle alert.generated event.
        Log and possibly chain alerts.
        """
        logger.info(f"Alert generated: {data}")

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

    def _create_validation_failed_alert(self, movement_id: int, product_id: int,
                                          branch_id: int, reason: str):
        """Create validation failed alert."""
        alert_data = self.service.create_alert(
            alert_type="validation_failed",
            severity="warning",
            title="Movimiento Rechazado",
            message=f"El movimiento {movement_id} fue rechazado. Razon: {reason}",
            movement_id=movement_id,
            product_id=product_id,
            branch_id=branch_id
        )

        # Emit alert event
        event_bus.emit(settings.Events.ALERT_GENERATED, alert_data)

    def unregister_handlers(self):
        """Unregister all event handlers."""
        event_bus.unsubscribe(settings.Events.INVENTORY_UPDATED, self.handle_inventory_updated)
        event_bus.unsubscribe(settings.Events.INVENTORY_COUNTED, self.handle_inventory_counted)
        event_bus.unsubscribe(settings.Events.MOVEMENT_REJECTED, self.handle_movement_rejected)
        event_bus.unsubscribe(settings.Events.ALERT_GENERATED, self.handle_alert_generated)
        logger.info("Alert handlers unregistered")


def setup_alert_handlers(db: Session) -> AlertHandlers:
    """Setup and return alert handlers."""
    return AlertHandlers(db)
