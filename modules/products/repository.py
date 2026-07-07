"""
Product repository – database operations.

Original ProductRepository is fully preserved.
New repositories added below, one per expansion:

  CategoryRepository    – Expansion 1 (Categorías)
  SupplierRepository    – Expansion 3 (Proveedor Default)
  ProductRelationRepository – Expansion 7 (Productos Relacionados)
  PriceHistoryRepository    – Expansion 8 (Historial de Precios)

All new filter methods on ProductRepository are additive; existing
callers are unaffected.
"""

from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from models.product import Product
from models.category import Category
from models.supplier import Supplier
from models.product_relation import ProductRelation
from models.price_history import PriceHistory


# ======================================================================
# Original repository – extended with new filter helpers
# ======================================================================

class ProductRepository:
    """Repository for product database operations."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Original methods – unchanged
    # ------------------------------------------------------------------

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

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        search: str = None,
        active_only: bool = True,
        # Expansion 1
        category_id: int = None,
        # Expansion 2
        brand: str = None,
        # Expansion 3
        supplier_id: int = None,
    ) -> List[Product]:
        """Get all products with optional filtering.

        New optional keyword arguments for expansions 1, 2, and 3 default
        to None so existing callers are unaffected.
        """
        query = self.db.query(Product)

        if active_only:
            query = query.filter(Product.is_active == True)

        if search:
            query = query.filter(
                or_(
                    Product.name.ilike(f"%{search}%"),
                    Product.sku.ilike(f"%{search}%"),
                    Product.description.ilike(f"%{search}%"),
                    # Expansion 4 – also search in details
                    Product.details.ilike(f"%{search}%"),
                )
            )

        # Expansion 1 – filter by category
        if category_id is not None:
            query = query.filter(Product.category_id == category_id)

        # Expansion 2 – filter by brand (exact, case-insensitive)
        if brand is not None:
            query = query.filter(Product.brand.ilike(brand))

        # Expansion 3 – filter by supplier
        if supplier_id is not None:
            query = query.filter(Product.default_supplier_id == supplier_id)

        return query.offset(skip).limit(limit).all()

    def count(
        self,
        active_only: bool = True,
        search: str = None,
        category_id: int = None,
        brand: str = None,
        supplier_id: int = None,
    ) -> int:
        """Count products with optional filtering."""
        query = self.db.query(Product)

        if active_only:
            query = query.filter(Product.is_active == True)

        if search:
            query = query.filter(
                or_(
                    Product.name.ilike(f"%{search}%"),
                    Product.sku.ilike(f"%{search}%"),
                    Product.description.ilike(f"%{search}%"),
                    Product.details.ilike(f"%{search}%"),
                )
            )

        if category_id is not None:
            query = query.filter(Product.category_id == category_id)

        if brand is not None:
            query = query.filter(Product.brand.ilike(brand))

        if supplier_id is not None:
            query = query.filter(Product.default_supplier_id == supplier_id)

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

    # ------------------------------------------------------------------
    # Expansion 2 – Marca
    # ------------------------------------------------------------------

    def get_distinct_brands(self) -> List[str]:
        """Return a sorted list of all distinct non-null brands in use."""
        rows = (
            self.db.query(Product.brand)
            .filter(Product.brand.isnot(None), Product.is_active == True)
            .distinct()
            .order_by(Product.brand)
            .all()
        )
        return [row[0] for row in rows]

    # ------------------------------------------------------------------
    # Expansion 6 – Stock Mínimo Global
    # ------------------------------------------------------------------

    def get_products_below_global_min(self) -> List[Product]:
        """Return active products whose combined physical stock is below
        their global_min_stock threshold.

        Only products that have global_min_stock set (not NULL) are
        considered.  The comparison is done in Python after loading the
        inventory sums to avoid a complex subquery while keeping things
        readable.
        """
        candidates = (
            self.db.query(Product)
            .filter(
                Product.is_active == True,
                Product.global_min_stock.isnot(None),
            )
            .all()
        )

        results = []
        for product in candidates:
            total_stock = sum(
                (inv.physical_stock or 0) for inv in product.inventory_items
            )
            if total_stock < product.global_min_stock:
                results.append(product)
        return results


# ======================================================================
# Expansion 1 – CategoryRepository
# ======================================================================

class CategoryRepository:
    """CRUD operations for Category."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict) -> Category:
        category = Category(**data)
        self.db.add(category)
        self.db.commit()
        self.db.refresh(category)
        return category

    def get_by_id(self, category_id: int) -> Optional[Category]:
        return self.db.query(Category).filter(Category.id == category_id).first()

    def get_by_name(self, name: str) -> Optional[Category]:
        return (
            self.db.query(Category)
            .filter(Category.name.ilike(name))
            .first()
        )

    def get_all(self, active_only: bool = True) -> List[Category]:
        """Return all categories, active ones by default."""
        query = self.db.query(Category)
        if active_only:
            query = query.filter(Category.is_active == True)
        return query.order_by(Category.name).all()

    def update(self, category_id: int, data: dict) -> Optional[Category]:
        category = self.get_by_id(category_id)
        if not category:
            return None
        for key, value in data.items():
            if hasattr(category, key):
                setattr(category, key, value)
        self.db.commit()
        self.db.refresh(category)
        return category

    def delete(self, category_id: int) -> bool:
        """Soft delete – sets is_active = False."""
        category = self.get_by_id(category_id)
        if not category:
            return False
        category.is_active = False
        self.db.commit()
        return True

    def name_exists(self, name: str, exclude_id: int = None) -> bool:
        query = self.db.query(Category).filter(Category.name.ilike(name))
        if exclude_id:
            query = query.filter(Category.id != exclude_id)
        return query.first() is not None

    def get_products_by_category(self, category_id: int, active_only: bool = True) -> List[Product]:
        """Return all products that belong to a given category."""
        query = self.db.query(Product).filter(Product.category_id == category_id)
        if active_only:
            query = query.filter(Product.is_active == True)
        return query.all()


# ======================================================================
# Expansion 3 – SupplierRepository
# ======================================================================

class SupplierRepository:
    """CRUD operations for Supplier."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, data: dict) -> Supplier:
        supplier = Supplier(**data)
        self.db.add(supplier)
        self.db.commit()
        self.db.refresh(supplier)
        return supplier

    def get_by_id(self, supplier_id: int) -> Optional[Supplier]:
        return self.db.query(Supplier).filter(Supplier.id == supplier_id).first()

    def get_by_name(self, name: str) -> Optional[Supplier]:
        return (
            self.db.query(Supplier)
            .filter(Supplier.name.ilike(name))
            .first()
        )

    def get_all(self, active_only: bool = True) -> List[Supplier]:
        query = self.db.query(Supplier)
        if active_only:
            query = query.filter(Supplier.is_active == True)
        return query.order_by(Supplier.name).all()

    def update(self, supplier_id: int, data: dict) -> Optional[Supplier]:
        supplier = self.get_by_id(supplier_id)
        if not supplier:
            return None
        for key, value in data.items():
            if hasattr(supplier, key):
                setattr(supplier, key, value)
        self.db.commit()
        self.db.refresh(supplier)
        return supplier

    def delete(self, supplier_id: int) -> bool:
        """Soft delete – sets is_active = False."""
        supplier = self.get_by_id(supplier_id)
        if not supplier:
            return False
        supplier.is_active = False
        self.db.commit()
        return True

    def name_exists(self, name: str, exclude_id: int = None) -> bool:
        query = self.db.query(Supplier).filter(Supplier.name.ilike(name))
        if exclude_id:
            query = query.filter(Supplier.id != exclude_id)
        return query.first() is not None

    def get_products_by_supplier(self, supplier_id: int, active_only: bool = True) -> List[Product]:
        """Return all products linked to a given supplier."""
        query = self.db.query(Product).filter(
            Product.default_supplier_id == supplier_id
        )
        if active_only:
            query = query.filter(Product.is_active == True)
        return query.all()


# ======================================================================
# Expansion 7 – ProductRelationRepository
# ======================================================================

class ProductRelationRepository:
    """Manage self-referential product relationships."""

    VALID_TYPES = {"sustituto", "complemento", "similar"}

    def __init__(self, db: Session):
        self.db = db

    def add(
        self,
        product_id: int,
        related_product_id: int,
        relation_type: str = None,
    ) -> ProductRelation:
        """Create a directed relation.  Raises ValueError on duplicates."""
        existing = self.get(product_id, related_product_id)
        if existing:
            raise ValueError(
                f"Relation between product {product_id} and {related_product_id} already exists"
            )
        relation = ProductRelation(
            product_id=product_id,
            related_product_id=related_product_id,
            relation_type=relation_type,
        )
        self.db.add(relation)
        self.db.commit()
        self.db.refresh(relation)
        return relation

    def get(self, product_id: int, related_product_id: int) -> Optional[ProductRelation]:
        return (
            self.db.query(ProductRelation)
            .filter(
                ProductRelation.product_id == product_id,
                ProductRelation.related_product_id == related_product_id,
            )
            .first()
        )

    def get_by_id(self, relation_id: int) -> Optional[ProductRelation]:
        return (
            self.db.query(ProductRelation)
            .filter(ProductRelation.id == relation_id)
            .first()
        )

    def get_outgoing(self, product_id: int) -> List[ProductRelation]:
        """All relations where *product_id* is the source."""
        return (
            self.db.query(ProductRelation)
            .filter(ProductRelation.product_id == product_id)
            .all()
        )

    def remove(self, product_id: int, related_product_id: int) -> bool:
        relation = self.get(product_id, related_product_id)
        if not relation:
            return False
        self.db.delete(relation)
        self.db.commit()
        return True

    def remove_by_id(self, relation_id: int) -> bool:
        relation = self.get_by_id(relation_id)
        if not relation:
            return False
        self.db.delete(relation)
        self.db.commit()
        return True


# ======================================================================
# Expansion 8 – PriceHistoryRepository
# ======================================================================

class PriceHistoryRepository:
    """Store and query product price change records."""

    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        product_id: int,
        previous_price: Optional[float],
        new_price: Optional[float],
        change_reason: str = None,
        changed_by_user_id: int = None,
    ) -> PriceHistory:
        """Persist a price change entry."""
        entry = PriceHistory(
            product_id=product_id,
            previous_price=previous_price,
            new_price=new_price,
            change_reason=change_reason,
            changed_by_user_id=changed_by_user_id,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def get_history(
        self,
        product_id: int,
        limit: int = 50,
        date_from: datetime = None,
        date_to: datetime = None,
    ) -> List[PriceHistory]:
        """Return price history for a product, newest first."""
        query = (
            self.db.query(PriceHistory)
            .filter(PriceHistory.product_id == product_id)
        )
        if date_from:
            query = query.filter(PriceHistory.created_at >= date_from)
        if date_to:
            query = query.filter(PriceHistory.created_at <= date_to)
        return (
            query.order_by(PriceHistory.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_latest(self, product_id: int) -> Optional[PriceHistory]:
        """Return the most recent price change entry for a product."""
        return (
            self.db.query(PriceHistory)
            .filter(PriceHistory.product_id == product_id)
            .order_by(PriceHistory.created_at.desc())
            .first()
        )

    def get_entries_since(self, product_id: int, days: int) -> List[PriceHistory]:
        """Return entries from the last *days* days, oldest first."""
        since = datetime.utcnow() - timedelta(days=days)
        return (
            self.db.query(PriceHistory)
            .filter(
                PriceHistory.product_id == product_id,
                PriceHistory.created_at >= since,
            )
            .order_by(PriceHistory.created_at.asc())
            .all()
        )
