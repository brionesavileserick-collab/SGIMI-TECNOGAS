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
                low_stock_only: bool = False, discrepancy_only: bool = False,
                search: str = None) -> List[Inventory]:
        """Get all inventory records with filtering."""
        query = self.db.query(Inventory).join(Product).join(Branch)

        query = query.filter(Inventory.is_active == True)
        query = query.filter(Product.is_active == True)
        query = query.filter(Branch.is_active == True)

        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)

        if product_id:
            query = query.filter(Inventory.product_id == product_id)

        if search:
            query = query.filter(
                or_(
                    Product.name.ilike(f"%{search}%"),
                    Product.sku.ilike(f"%{search}%"),
                    Branch.name.ilike(f"%{search}%")
                )
            )

        if low_stock_only:
            query = query.filter(Inventory.digital_stock <= Inventory.min_stock)

        if discrepancy_only:
            query = query.filter(Inventory.physical_stock != Inventory.digital_stock)

        return query.offset(skip).limit(limit).all()

    def count(self, branch_id: int = None, product_id: int = None,
              low_stock_only: bool = False, discrepancy_only: bool = False,
              search: str = None) -> int:
        """Count inventory records with filtering."""
        query = self.db.query(Inventory).join(Product).join(Branch)

        query = query.filter(Inventory.is_active == True)
        query = query.filter(Product.is_active == True)
        query = query.filter(Branch.is_active == True)

        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)

        if product_id:
            query = query.filter(Inventory.product_id == product_id)

        if search:
            query = query.filter(
                or_(
                    Product.name.ilike(f"%{search}%"),
                    Product.sku.ilike(f"%{search}%"),
                    Branch.name.ilike(f"%{search}%")
                )
            )

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
        query = self.db.query(func.sum(Inventory.physical_stock)).join(Product).join(Branch)
        query = query.filter(Inventory.is_active == True)
        query = query.filter(Product.is_active == True)
        query = query.filter(Branch.is_active == True)
        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)
        result = query.scalar()
        return result or 0

    def get_total_digital_stock(self, branch_id: int = None) -> int:
        """Get total digital stock."""
        query = self.db.query(func.sum(Inventory.digital_stock)).join(Product).join(Branch)
        query = query.filter(Inventory.is_active == True)
        query = query.filter(Product.is_active == True)
        query = query.filter(Branch.is_active == True)
        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)
        result = query.scalar()
        return result or 0

    def get_discrepancy_count(self, branch_id: int = None) -> int:
        """Count items with discrepancies."""
        query = self.db.query(Inventory).join(Product).join(Branch)
        query = query.filter(Inventory.is_active == True)
        query = query.filter(Product.is_active == True)
        query = query.filter(Branch.is_active == True)
        query = query.filter(Inventory.physical_stock != Inventory.digital_stock)

        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)

        return query.count()

    def get_low_stock_count(self, branch_id: int = None) -> int:
        """Count items with low stock."""
        query = self.db.query(Inventory).join(Product).join(Branch)
        query = query.filter(Inventory.is_active == True)
        query = query.filter(Product.is_active == True)
        query = query.filter(Branch.is_active == True)
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

    def get_global_inventory(self, skip: int = 0, limit: int = 100,
                             product_id: int = None, search: str = None) -> List[Dict[str, Any]]:
        """
        Get global inventory (sum of stock across all branches).
        Returns aggregated stock per product.
        """
        query = self.db.query(
            Product.id,
            Product.sku,
            Product.name,
            Product.unit_of_measure,
            Product.unit_price,
            func.sum(Inventory.physical_stock).label('total_physical_stock'),
            func.sum(Inventory.digital_stock).label('total_digital_stock'),
            func.count(Inventory.branch_id).label('branch_count')
        ).join(
            Inventory, Product.id == Inventory.product_id
        ).join(
            Branch, Inventory.branch_id == Branch.id
        ).filter(
            Inventory.is_active == True,
            Product.is_active == True,
            Branch.is_active == True
        ).group_by(
            Product.id, Product.sku, Product.name, Product.unit_of_measure, Product.unit_price
        )

        if product_id:
            query = query.filter(Product.id == product_id)

        if search:
            query = query.filter(
                or_(
                    Product.name.ilike(f"%{search}%"),
                    Product.sku.ilike(f"%{search}%")
                )
            )

        results = query.offset(skip).limit(limit).all()

        return [
            {
                "product_id": r.id,
                "sku": r.sku,
                "name": r.name,
                "unit_of_measure": r.unit_of_measure,
                "unit_price": r.unit_price,
                "total_physical_stock": r.total_physical_stock or 0,
                "total_digital_stock": r.total_digital_stock or 0,
                "branch_count": r.branch_count
            }
            for r in results
        ]

    def count_global_inventory(self, product_id: int = None, search: str = None) -> int:
        """Count distinct products in global inventory."""
        query = self.db.query(
            func.count(func.distinct(Inventory.product_id))
        ).join(
            Product, Inventory.product_id == Product.id
        ).join(
            Branch, Inventory.branch_id == Branch.id
        ).filter(
            Inventory.is_active == True,
            Product.is_active == True,
            Branch.is_active == True
        )

        if product_id:
            query = query.filter(Product.id == product_id)

        if search:
            query = query.filter(
                or_(
                    Product.name.ilike(f"%{search}%"),
                    Product.sku.ilike(f"%{search}%")
                )
            )

        return query.scalar() or 0

    def get_product_stock_across_branches(self, product_id: int) -> List[Dict[str, Any]]:
        """
        Get stock for a specific product across all branches.
        Useful for matrix to see product distribution.
        """
        results = self.db.query(
            Inventory,
            Branch.name,
            Branch.address
        ).join(
            Branch, Inventory.branch_id == Branch.id
        ).join(
            Product, Inventory.product_id == Product.id
        ).filter(
            Inventory.product_id == product_id,
            Inventory.is_active == True,
            Product.is_active == True,
            Branch.is_active == True
        ).all()

        return [
            {
                "inventory_id": inv.id,
                "branch_id": inv.branch_id,
                "branch_name": branch_name,
                "branch_address": branch_address,
                "physical_stock": inv.physical_stock,
                "digital_stock": inv.digital_stock,
                "difference": inv.difference,
                "has_discrepancy": inv.has_discrepancy,
                "is_low_stock": inv.is_low_stock
            }
            for inv, branch_name, branch_address in results
        ]
