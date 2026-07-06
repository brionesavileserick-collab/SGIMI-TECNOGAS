"""
Inventory repository for database operations.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from models.inventory import Inventory
from models.product import Product
from models.branch import Branch
from datetime import datetime


class InventoryRepository:
    """Repository for inventory database operations."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, inventory_data: dict) -> Inventory:
        """Create a new inventory record."""
        inventory = Inventory(**inventory_data)
        self.db.add(inventory)
        self.db.commit()
        self.db.refresh(inventory)
        return inventory

    def get_by_id(self, inventory_id: int) -> Optional[Inventory]:
        """Get inventory by ID."""
        return self.db.query(Inventory).filter(Inventory.id == inventory_id).first()

    def get_by_product_branch(self, product_id: int, branch_id: int) -> Optional[Inventory]:
        """Get inventory by product and branch."""
        return self.db.query(Inventory).filter(
            and_(
                Inventory.product_id == product_id,
                Inventory.branch_id == branch_id
            )
        ).first()

    def get_all(self, skip: int = 0, limit: int = 100,
                branch_id: int = None, product_id: int = None,
                low_stock_only: bool = False, discrepancy_only: bool = False) -> List[Inventory]:
        """Get all inventory records with filtering."""
        query = self.db.query(Inventory).join(Product).join(Branch)

        query = query.filter(Inventory.is_active == True)
        query = query.filter(Product.is_active == True)
        query = query.filter(Branch.is_active == True)

        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)

        if product_id:
            query = query.filter(Inventory.product_id == product_id)

        if low_stock_only:
            query = query.filter(Inventory.digital_stock <= Inventory.min_stock)

        if discrepancy_only:
            query = query.filter(Inventory.physical_stock != Inventory.digital_stock)

        return query.offset(skip).limit(limit).all()

    def count(self, branch_id: int = None, product_id: int = None,
              low_stock_only: bool = False, discrepancy_only: bool = False) -> int:
        """Count inventory records with filtering."""
        query = self.db.query(Inventory).join(Product).join(Branch)

        query = query.filter(Inventory.is_active == True)
        query = query.filter(Product.is_active == True)
        query = query.filter(Branch.is_active == True)

        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)

        if product_id:
            query = query.filter(Inventory.product_id == product_id)

        if low_stock_only:
            query = query.filter(Inventory.digital_stock <= Inventory.min_stock)

        if discrepancy_only:
            query = query.filter(Inventory.physical_stock != Inventory.digital_stock)

        return query.count()

    def update(self, inventory_id: int, update_data: dict) -> Optional[Inventory]:
        """Update inventory record."""
        inventory = self.get_by_id(inventory_id)
        if not inventory:
            return None

        for key, value in update_data.items():
            if hasattr(inventory, key):
                setattr(inventory, key, value)

        self.db.commit()
        self.db.refresh(inventory)
        return inventory

    def update_stock(self, product_id: int, branch_id: int,
                     physical_change: int = 0, digital_change: int = 0) -> Optional[Inventory]:
        """Update stock quantities for a product at a branch."""
        inventory = self.get_by_product_branch(product_id, branch_id)
        if not inventory:
            return None

        inventory.physical_stock += physical_change
        inventory.digital_stock += digital_change
        inventory.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(inventory)
        return inventory

    def set_stock(self, product_id: int, branch_id: int,
                  physical_stock: int = None, digital_stock: int = None) -> Optional[Inventory]:
        """Set absolute stock values."""
        inventory = self.get_by_product_branch(product_id, branch_id)
        if not inventory:
            return None

        if physical_stock is not None:
            inventory.physical_stock = physical_stock
            inventory.last_count_date = datetime.utcnow()

        if digital_stock is not None:
            inventory.digital_stock = digital_stock

        inventory.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(inventory)
        return inventory

    def delete(self, inventory_id: int) -> bool:
        """Soft delete inventory record."""
        inventory = self.get_by_id(inventory_id)
        if not inventory:
            return False

        inventory.is_active = False
        self.db.commit()
        return True

    def get_total_physical_stock(self, branch_id: int = None) -> int:
        """Get total physical stock."""
        query = self.db.query(func.sum(Inventory.physical_stock)).filter(Inventory.is_active == True)
        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)
        result = query.scalar()
        return result or 0

    def get_total_digital_stock(self, branch_id: int = None) -> int:
        """Get total digital stock."""
        query = self.db.query(func.sum(Inventory.digital_stock)).filter(Inventory.is_active == True)
        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)
        result = query.scalar()
        return result or 0

    def get_discrepancy_count(self, branch_id: int = None) -> int:
        """Count items with discrepancies."""
        query = self.db.query(Inventory).join(Product).join(Branch)
        query = query.filter(Inventory.is_active == True)
        query = query.filter(Inventory.physical_stock != Inventory.digital_stock)

        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)

        return query.count()

    def get_low_stock_count(self, branch_id: int = None) -> int:
        """Count items with low stock."""
        query = self.db.query(Inventory).join(Product).join(Branch)
        query = query.filter(Inventory.is_active == True)
        query = query.filter(Inventory.digital_stock <= Inventory.min_stock)

        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)

        return query.count()

    def exists(self, product_id: int, branch_id: int) -> bool:
        """Check if inventory record exists."""
        return self.get_by_product_branch(product_id, branch_id) is not None

    def get_inventory_with_details(self, inventory_id: int) -> Optional[Dict[str, Any]]:
        """Get inventory with product and branch details."""
        result = self.db.query(Inventory, Product, Branch).join(
            Product, Inventory.product_id == Product.id
        ).join(
            Branch, Inventory.branch_id == Branch.id
        ).filter(Inventory.id == inventory_id).first()

        if not result:
            return None

        inventory, product, branch = result
        return {
            "inventory": inventory.to_dict(),
            "product": product.to_dict(),
            "branch": branch.to_dict()
        }
