"""
Inventory service layer - Business logic and event emission.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from modules.inventory.repository import InventoryRepository
from core.event_bus import event_bus
from core.settings import settings
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class InventoryService:
    """Service for inventory business logic."""

    def __init__(self, db: Session):
        self.repository = InventoryRepository(db)

    def create_inventory(self, inventory_data: dict) -> Dict[str, Any]:
        """Create a new inventory record."""
        # Check if already exists
        product_id = inventory_data.get("product_id")
        branch_id = inventory_data.get("branch_id")

        if self.repository.exists(product_id, branch_id):
            raise ValueError(f"El inventario para este producto y sucursal ya existe")

        inventory = self.repository.create(inventory_data)
        logger.info(f"Inventory created: Product {product_id} at Branch {branch_id}")
        return inventory.to_dict()

    def get_inventory(self, inventory_id: int) -> Optional[Dict[str, Any]]:
        """Get inventory by ID."""
        inventory = self.repository.get_by_id(inventory_id)
        return inventory.to_dict() if inventory else None

    def get_inventory_by_product_branch(self, product_id: int, branch_id: int) -> Optional[Dict[str, Any]]:
        """Get inventory by product and branch."""
        inventory = self.repository.get_by_product_branch(product_id, branch_id)
        return inventory.to_dict() if inventory else None

    def list_inventory(self, page: int = 1, page_size: int = 20,
                       branch_id: int = None, product_id: int = None,
                       low_stock_only: bool = False, discrepancy_only: bool = False) -> Dict[str, Any]:
        """List inventory with pagination and filtering."""
        skip = (page - 1) * page_size
        inventory_items = self.repository.get_all(
            skip=skip,
            limit=page_size,
            branch_id=branch_id,
            product_id=product_id,
            low_stock_only=low_stock_only,
            discrepancy_only=discrepancy_only
        )

        total = self.repository.count(
            branch_id=branch_id,
            product_id=product_id,
            low_stock_only=low_stock_only,
            discrepancy_only=discrepancy_only
        )

        return {
            "inventory": [self._enrich_inventory(i) for i in inventory_items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }

    def update_inventory(self, inventory_id: int, update_data: dict) -> Optional[Dict[str, Any]]:
        """Update inventory record."""
        inventory = self.repository.update(inventory_id, update_data)
        if not inventory:
            return None

        # Emit event
        event_data = {
            "inventory_id": inventory.id,
            "product_id": inventory.product_id,
            "branch_id": inventory.branch_id,
            "physical_stock": inventory.physical_stock,
            "digital_stock": inventory.digital_stock
        }
        event_bus.emit(settings.Events.INVENTORY_UPDATED, event_data)

        logger.info(f"Inventory updated: ID {inventory_id}")
        return inventory.to_dict()

    def adjust_physical_stock(self, product_id: int, branch_id: int, quantity: int) -> Optional[Dict[str, Any]]:
        """Adjust physical stock (for inventory counts)."""
        # Get or create inventory
        inventory = self.repository.get_by_product_branch(product_id, branch_id)
        if not inventory:
            # Create new inventory
            inventory = self.repository.create({
                "product_id": product_id,
                "branch_id": branch_id,
                "physical_stock": quantity,
                "digital_stock": 0,
                "min_stock": 0
            })
        else:
            inventory = self.repository.set_stock(
                product_id, branch_id,
                physical_stock=quantity
            )

        # Emit inventory counted event
        event_data = {
            "product_id": product_id,
            "branch_id": branch_id,
            "physical_stock": quantity,
            "inventory_id": inventory.id
        }
        event_bus.emit(settings.Events.INVENTORY_COUNTED, event_data)

        logger.info(f"Physical stock adjusted: Product {product_id}, Branch {branch_id}, Quantity {quantity}")
        return inventory.to_dict() if inventory else None

    def adjust_digital_stock(self, product_id: int, branch_id: int, quantity: int, is_absolute: bool = False) -> Optional[Dict[str, Any]]:
        """Adjust digital stock."""
        # Update stock
        if is_absolute:
            inventory = self.repository.set_stock(product_id, branch_id, digital_stock=quantity)
        else:
            inventory = self.repository.update_stock(product_id, branch_id, digital_change=quantity)

        if inventory:
            # Emit event
            event_data = {
                "inventory_id": inventory.id,
                "product_id": inventory.product_id,
                "branch_id": inventory.branch_id,
                "physical_stock": inventory.physical_stock,
                "digital_stock": inventory.digital_stock
            }
            event_bus.emit(settings.Events.INVENTORY_UPDATED, event_data)

            logger.info(f"Digital stock adjusted: Product {product_id}, Branch {branch_id}, Change {quantity}")

        return inventory.to_dict() if inventory else None

    def delete_inventory(self, inventory_id: int) -> bool:
        """Soft delete inventory record."""
        success = self.repository.delete(inventory_id)
        if success:
            logger.info(f"Inventory deleted: ID {inventory_id}")
        return success

    def get_totals(self, branch_id: int = None) -> Dict[str, int]:
        """Get inventory totals."""
        return {
            "total_physical_stock": self.repository.get_total_physical_stock(branch_id),
            "total_digital_stock": self.repository.get_total_digital_stock(branch_id),
            "discrepancy_count": self.repository.get_discrepancy_count(branch_id),
            "low_stock_count": self.repository.get_low_stock_count(branch_id)
        }

    def get_discrepancies(self, branch_id: int = None) -> List[Dict[str, Any]]:
        """Get all items with discrepancies."""
        items = self.repository.get_all(
            limit=1000,
            branch_id=branch_id,
            discrepancy_only=True
        )
        return [self._enrich_inventory(i) for i in items]

    def get_low_stock_items(self, branch_id: int = None) -> List[Dict[str, Any]]:
        """Get all items with low stock."""
        items = self.repository.get_all(
            limit=1000,
            branch_id=branch_id,
            low_stock_only=True
        )
        return [self._enrich_inventory(i) for i in items]

    def _enrich_inventory(self, inventory) -> Dict[str, Any]:
        """Enrich inventory with product and branch details."""
        details = self.repository.get_inventory_with_details(inventory.id)
        if not details:
            return inventory.to_dict()

        result = inventory.to_dict()
        result["product"] = details["product"]
        result["branch"] = details["branch"]
        return result
