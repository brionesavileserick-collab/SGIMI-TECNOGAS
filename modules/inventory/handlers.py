"""
Inventory event handlers - React to events and update inventory.
"""

from typing import Dict, Any
from sqlalchemy.orm import Session
from modules.inventory.service import InventoryService
from core.event_bus import event_bus
from core.settings import settings
import logging

logger = logging.getLogger(__name__)


class InventoryHandlers:
    """Event handlers for inventory module."""

    def __init__(self, db: Session):
        self.db = db
        self.service = InventoryService(db)
        self._register_handlers()

    def _register_handlers(self):
        """Register all event handlers."""
        event_bus.subscribe(settings.Events.MOVEMENT_VALIDATED, self.handle_movement_validated)
        event_bus.subscribe(settings.Events.INVENTORY_COUNTED, self.handle_inventory_counted)
        event_bus.subscribe(settings.Events.TRANSFER_RECEIVED, self.handle_transfer_received)
        event_bus.subscribe(settings.Events.PRODUCT_DELETED, self.handle_product_deleted)
        logger.info("Inventory handlers registered")

    def handle_movement_validated(self, data: Dict[str, Any]):
        """
        Handle movement.validated event.
        Updates digital stock based on validated movement.
        """
        try:
            movement_id = data.get("movement_id")
            product_id = data.get("product_id")
            branch_id = data.get("branch_id")
            movement_type = data.get("movement_type")
            quantity = data.get("quantity")

            if not all([product_id, branch_id, movement_type, quantity]):
                logger.warning(f"Invalid movement data: {data}")
                return

            # Calculate stock change based on movement type
            if movement_type == "entrada":
                # Increase digital stock
                self.service.adjust_digital_stock(product_id, branch_id, quantity, is_absolute=False)
                logger.info(f"Stock increased: Product {product_id}, Branch {branch_id}, +{quantity}")

            elif movement_type == "salida":
                # Decrease digital stock
                self.service.adjust_digital_stock(product_id, branch_id, -quantity, is_absolute=False)
                logger.info(f"Stock decreased: Product {product_id}, Branch {branch_id}, -{quantity}")

            elif movement_type == "ajuste":
                # Set absolute digital stock
                self.service.adjust_digital_stock(product_id, branch_id, quantity, is_absolute=True)
                logger.info(f"Stock adjusted: Product {product_id}, Branch {branch_id}, = {quantity}")

        except Exception as e:
            logger.error(f"Error handling movement.validated: {e}")

    def handle_inventory_counted(self, data: Dict[str, Any]):
        """
        Handle inventory.counted event.
        Updates physical stock and checks for discrepancies.
        """
        try:
            product_id = data.get("product_id")
            branch_id = data.get("branch_id")
            physical_stock = data.get("physical_stock")

            if not all([product_id, branch_id]):
                logger.warning(f"Invalid inventory count data: {data}")
                return

            # Get current inventory to check discrepancy
            inventory = self.service.get_inventory_by_product_branch(product_id, branch_id)
            if inventory:
                if inventory["digital_stock"] != physical_stock:
                    logger.info(
                        f"Discrepancy detected: Product {product_id}, Branch {branch_id}, "
                        f"Physical={physical_stock}, Digital={inventory['digital_stock']}"
                    )

        except Exception as e:
            logger.error(f"Error handling inventory.counted: {e}")

    def handle_transfer_received(self, data: Dict[str, Any]):
        """
        Handle transfer.received event.
        Increases stock at destination branch.
        """
        try:
            product_id = data.get("product_id")
            destination_branch_id = data.get("destination_branch_id")
            quantity = data.get("quantity")

            if not all([product_id, destination_branch_id, quantity]):
                logger.warning(f"Invalid transfer data: {data}")
                return

            # Increase stock at destination
            self.service.adjust_digital_stock(product_id, destination_branch_id, quantity, is_absolute=False)
            logger.info(f"Transfer received: Product {product_id}, Branch {destination_branch_id}, +{quantity}")

        except Exception as e:
            logger.error(f"Error handling transfer.received: {e}")

    def handle_product_deleted(self, data: Dict[str, Any]):
        """
        Handle product.deleted event.
        Soft deletes inventory records for the deleted product.
        """
        try:
            product_id = data.get("product_id")
            if not product_id:
                return

            # Soft delete all inventory for this product
            items = self.service.list_inventory(page=1, page_size=1000, product_id=product_id)
            for item in items["inventory"]:
                self.service.delete_inventory(item["id"])

            logger.info(f"Inventory deleted for product {product_id}")

        except Exception as e:
            logger.error(f"Error handling product.deleted: {e}")

    def unregister_handlers(self):
        """Unregister all event handlers."""
        event_bus.unsubscribe(settings.Events.MOVEMENT_VALIDATED, self.handle_movement_validated)
        event_bus.unsubscribe(settings.Events.INVENTORY_COUNTED, self.handle_inventory_counted)
        event_bus.unsubscribe(settings.Events.TRANSFER_RECEIVED, self.handle_transfer_received)
        event_bus.unsubscribe(settings.Events.PRODUCT_DELETED, self.handle_product_deleted)
        logger.info("Inventory handlers unregistered")


def setup_inventory_handlers(db: Session) -> InventoryHandlers:
    """Setup and return inventory handlers."""
    return InventoryHandlers(db)
