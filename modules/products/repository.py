"""
Product repository for database operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from models.product import Product


class ProductRepository:
    """Repository for product database operations."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, product_data: dict) -> Product:
        """Create a new product."""
        product = Product(**product_data)
        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)
        return product

    def get_by_id(self, product_id: int) -> Optional[Product]:
        """Get product by ID."""
        return self.db.query(Product).filter(Product.id == product_id).first()

    def get_by_sku(self, sku: str) -> Optional[Product]:
        """Get product by SKU."""
        return self.db.query(Product).filter(Product.sku == sku).first()

    def get_all(self, skip: int = 0, limit: int = 100, search: str = None, active_only: bool = True) -> List[Product]:
        """Get all products with optional filtering."""
        query = self.db.query(Product)

        if active_only:
            query = query.filter(Product.is_active == True)

        if search:
            query = query.filter(
                or_(
                    Product.name.ilike(f"%{search}%"),
                    Product.sku.ilike(f"%{search}%"),
                    Product.description.ilike(f"%{search}%")
                )
            )

        return query.offset(skip).limit(limit).all()

    def count(self, active_only: bool = True, search: str = None) -> int:
        """Count products with optional filtering."""
        query = self.db.query(Product)

        if active_only:
            query = query.filter(Product.is_active == True)

        if search:
            query = query.filter(
                or_(
                    Product.name.ilike(f"%{search}%"),
                    Product.sku.ilike(f"%{search}%"),
                    Product.description.ilike(f"%{search}%")
                )
            )

        return query.count()

    def update(self, product_id: int, update_data: dict) -> Optional[Product]:
        """Update product."""
        product = self.get_by_id(product_id)
        if not product:
            return None

        for key, value in update_data.items():
            if hasattr(product, key):
                setattr(product, key, value)

        self.db.commit()
        self.db.refresh(product)
        return product

    def delete(self, product_id: int) -> bool:
        """Soft delete product by setting is_active to False."""
        product = self.get_by_id(product_id)
        if not product:
            return False

        product.is_active = False
        self.db.commit()
        return True

    def hard_delete(self, product_id: int) -> bool:
        """Permanently delete product."""
        product = self.get_by_id(product_id)
        if not product:
            return False

        self.db.delete(product)
        self.db.commit()
        return True

    def sku_exists(self, sku: str, exclude_id: int = None) -> bool:
        """Check if SKU already exists."""
        query = self.db.query(Product).filter(Product.sku == sku)
        if exclude_id:
            query = query.filter(Product.id != exclude_id)
        return query.first() is not None
