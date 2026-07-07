"""
Product service layer – business logic and event emission.

Original ProductService is fully preserved and extended.
New service classes added below:

  CategoryService       – Expansion 1 (Categorías)
  SupplierService       – Expansion 3 (Proveedor Default)
  ProductRelationService – Expansion 7 (Productos Relacionados)
  PriceHistoryService   – Expansion 8 (Historial de Precios)

All new methods on ProductService are additive.  Existing callers of
create_product / update_product / delete_product / list_products /
search_products / get_all_active_products are unaffected.

Expansion 9 (SKU editable): update_product() already supports changing
the SKU through the shared sku_exists(exclude_id=...) guard; no extra
work required.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from modules.products.repository import (
    CategoryRepository,
    PriceHistoryRepository,
    ProductRelationRepository,
    ProductRepository,
    SupplierRepository,
)
from core.event_bus import event_bus
from core.settings import settings
from utils.validators import validate_name, validate_sku
import logging

logger = logging.getLogger(__name__)

# Accepted relation types for Expansion 7
_VALID_RELATION_TYPES = {"sustituto", "complemento", "similar"}

# Accepted change reasons for Expansion 8
_VALID_CHANGE_REASONS = {"ajuste", "promocion", "costo", "error"}


# ======================================================================
# Original service – extended with new helpers
# ======================================================================

class ProductService:
    """Service for product business logic."""

    def __init__(self, db: Session):
        self.repository = ProductRepository(db)
        self._price_history_repo = PriceHistoryRepository(db)

    # ------------------------------------------------------------------
    # Original methods – unchanged signatures
    # ------------------------------------------------------------------

    def create_product(self, product_data: dict) -> Dict[str, Any]:
        """Create a new product and emit event."""
        product_data = self._sanitize_product_data(product_data)
        self._validate_product_data(product_data, require_required=True)

        if self.repository.sku_exists(product_data.get("sku")):
            raise ValueError(f"SKU '{product_data.get('sku')}' already exists")

        product = self.repository.create(product_data)

        event_bus.emit(settings.Events.PRODUCT_CREATED, {
            "product_id": product.id,
            "sku": product.sku,
            "name": product.name,
        })

        logger.info(f"Product created: {product.sku}")
        return product.to_dict()

    def get_product(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Get product by ID."""
        product = self.repository.get_by_id(product_id)
        return product.to_dict() if product else None

    def get_product_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        """Get product by SKU."""
        product = self.repository.get_by_sku(sku)
        return product.to_dict() if product else None

    def list_products(
        self,
        page: int = 1,
        page_size: int = 20,
        search: str = None,
        # Expansion 1
        category_id: int = None,
        # Expansion 2
        brand: str = None,
        # Expansion 3
        supplier_id: int = None,
    ) -> Dict[str, Any]:
        """List products with pagination.

        New optional filters (category_id, brand, supplier_id) default to
        None so existing callers are unaffected.
        """
        skip = (page - 1) * page_size
        products = self.repository.get_all(
            skip=skip,
            limit=page_size,
            search=search,
            category_id=category_id,
            brand=brand,
            supplier_id=supplier_id,
        )
        total = self.repository.count(
            search=search,
            category_id=category_id,
            brand=brand,
            supplier_id=supplier_id,
        )

        return {
            "products": [p.to_dict() for p in products],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }

    def update_product(
        self,
        product_id: int,
        update_data: dict,
        change_reason: str = None,
        changed_by_user_id: int = None,
    ) -> Optional[Dict[str, Any]]:
        """Update product and emit event.

        If unit_price changes, a PriceHistory entry is automatically saved
        and a PRICE_CHANGED event is emitted (Expansion 8).

        change_reason and changed_by_user_id are forwarded to PriceHistory;
        they are ignored when unit_price is not part of the update.
        """
        update_data = self._sanitize_product_data(update_data)
        self._validate_product_data(update_data, require_required=False)

        # Expansion 9 – SKU editability: already handled by sku_exists below
        if "sku" in update_data:
            if self.repository.sku_exists(update_data["sku"], exclude_id=product_id):
                raise ValueError(f"SKU '{update_data['sku']}' already exists")

        # Expansion 8 – capture previous price before saving
        existing = self.repository.get_by_id(product_id)
        if not existing:
            return None

        previous_price = existing.unit_price

        product = self.repository.update(product_id, update_data)
        if not product:
            return None

        # Emit general update event
        event_bus.emit(settings.Events.PRODUCT_UPDATED, {
            "product_id": product.id,
            "sku": product.sku,
            "name": product.name,
            "changes": update_data,
        })

        # Expansion 8 – record price change when unit_price actually differs
        if "unit_price" in update_data and update_data["unit_price"] != previous_price:
            self._price_history_repo.record(
                product_id=product.id,
                previous_price=previous_price,
                new_price=product.unit_price,
                change_reason=change_reason,
                changed_by_user_id=changed_by_user_id,
            )
            event_bus.emit(settings.Events.PRICE_CHANGED, {
                "product_id": product.id,
                "sku": product.sku,
                "previous_price": previous_price,
                "new_price": product.unit_price,
                "change_reason": change_reason,
                "changed_by_user_id": changed_by_user_id,
            })
            logger.info(
                f"Price changed for {product.sku}: "
                f"{previous_price} → {product.unit_price}"
            )

        logger.info(f"Product updated: {product.sku}")
        return product.to_dict()

    def delete_product(self, product_id: int) -> bool:
        """Soft delete product and emit event."""
        product = self.repository.get_by_id(product_id)
        if not product:
            return False

        success = self.repository.delete(product_id)
        if success:
            event_bus.emit(settings.Events.PRODUCT_DELETED, {
                "product_id": product_id,
                "sku": product.sku,
                "name": product.name,
            })
            logger.info(f"Product deleted: {product.sku}")

        return success

    def search_products(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search products by name, SKU, description, or details."""
        products = self.repository.get_all(limit=limit, search=query)
        return [p.to_dict() for p in products]

    def get_all_active_products(self) -> List[Dict[str, Any]]:
        """Get all active products."""
        products = self.repository.get_all(limit=1000)
        return [p.to_dict() for p in products]

    # ------------------------------------------------------------------
    # Expansion 1 – filter helpers
    # ------------------------------------------------------------------

    def get_products_by_category(self, category_id: int) -> List[Dict[str, Any]]:
        """Return active products belonging to a category."""
        products = self.repository.get_all(category_id=category_id, limit=1000)
        return [p.to_dict() for p in products]

    # ------------------------------------------------------------------
    # Expansion 2 – brand helpers
    # ------------------------------------------------------------------

    def get_distinct_brands(self) -> List[str]:
        """Return sorted list of all brands currently in use."""
        return self.repository.get_distinct_brands()

    def get_products_by_brand(self, brand: str) -> List[Dict[str, Any]]:
        """Return active products matching a brand name (case-insensitive)."""
        products = self.repository.get_all(brand=brand, limit=1000)
        return [p.to_dict() for p in products]

    def filter_by_brand(self, brand: str, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """Paginated product list filtered by brand."""
        return self.list_products(page=page, page_size=page_size, brand=brand)

    # ------------------------------------------------------------------
    # Expansion 3 – supplier assignment helpers
    # ------------------------------------------------------------------

    def get_products_by_supplier(self, supplier_id: int) -> List[Dict[str, Any]]:
        """Return active products linked to a supplier."""
        products = self.repository.get_all(supplier_id=supplier_id, limit=1000)
        return [p.to_dict() for p in products]

    def assign_supplier(self, product_id: int, supplier_id: Optional[int]) -> Optional[Dict[str, Any]]:
        """Assign (or clear) the default supplier on a product.

        Pass supplier_id=None to remove the current supplier.
        """
        return self.update_product(product_id, {"default_supplier_id": supplier_id})

    def get_product_with_supplier(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Return product dict with embedded supplier data."""
        product = self.repository.get_by_id(product_id)
        if not product:
            return None
        return product.to_dict_full()

    # ------------------------------------------------------------------
    # Expansion 5 – internal notes
    # ------------------------------------------------------------------

    def update_internal_notes(self, product_id: int, notes: str) -> Optional[Dict[str, Any]]:
        """Update internal_notes field for a product."""
        return self.update_product(product_id, {"internal_notes": notes})

    def get_products_with_internal_notes(self) -> List[Dict[str, Any]]:
        """Return active products that have non-empty internal_notes."""
        products = self.repository.get_all(limit=1000)
        return [
            p.to_dict()
            for p in products
            if p.internal_notes and p.internal_notes.strip()
        ]

    # ------------------------------------------------------------------
    # Expansion 6 – global min stock helpers
    # ------------------------------------------------------------------

    def get_global_min_stock(self, product_id: int) -> Optional[int]:
        """Return the global_min_stock value or None if not set."""
        product = self.repository.get_by_id(product_id)
        if not product:
            return None
        return product.global_min_stock

    def get_products_needing_reorder(self) -> List[Dict[str, Any]]:
        """Return products whose combined physical stock is below global_min_stock."""
        products = self.repository.get_products_below_global_min()
        result = []
        for p in products:
            data = p.to_dict()
            data["total_physical_stock"] = sum(
                (inv.physical_stock or 0) for inv in p.inventory_items
            )
            result.append(data)
        return result

    # ------------------------------------------------------------------
    # Expansion 8 – price history read helpers (write is inside update_product)
    # ------------------------------------------------------------------

    def get_price_history(
        self,
        product_id: int,
        limit: int = 50,
        date_from: datetime = None,
        date_to: datetime = None,
    ) -> List[Dict[str, Any]]:
        """Return price history for a product, newest first."""
        entries = self._price_history_repo.get_history(
            product_id=product_id,
            limit=limit,
            date_from=date_from,
            date_to=date_to,
        )
        return [e.to_dict() for e in entries]

    def get_latest_price(self, product_id: int) -> Optional[float]:
        """Return the most recently recorded price for a product."""
        entry = self._price_history_repo.get_latest(product_id)
        if entry:
            return entry.new_price
        # Fall back to current unit_price if no history yet
        product = self.repository.get_by_id(product_id)
        return product.unit_price if product else None

    def get_price_variation(self, product_id: int, days: int = 30) -> Dict[str, Any]:
        """Return price variation statistics for the last *days* days.

        Returns a dict with:
            product_id, days, entries (count), first_price,
            last_price, min_price, max_price, absolute_change,
            percent_change
        """
        entries = self._price_history_repo.get_entries_since(product_id, days)

        if not entries:
            product = self.repository.get_by_id(product_id)
            current = product.unit_price if product else None
            return {
                "product_id": product_id,
                "days": days,
                "entries": 0,
                "first_price": current,
                "last_price": current,
                "min_price": current,
                "max_price": current,
                "absolute_change": 0,
                "percent_change": 0,
            }

        prices = [e.new_price for e in entries if e.new_price is not None]
        first_price = entries[0].previous_price
        last_price = entries[-1].new_price

        absolute_change = (
            (last_price - first_price)
            if last_price is not None and first_price is not None
            else None
        )
        percent_change = (
            round((absolute_change / first_price) * 100, 2)
            if absolute_change is not None and first_price
            else None
        )

        return {
            "product_id": product_id,
            "days": days,
            "entries": len(entries),
            "first_price": first_price,
            "last_price": last_price,
            "min_price": min(prices) if prices else None,
            "max_price": max(prices) if prices else None,
            "absolute_change": absolute_change,
            "percent_change": percent_change,
        }

    # ------------------------------------------------------------------
    # Private helpers – original
    # ------------------------------------------------------------------

    def _sanitize_product_data(self, product_data: dict) -> dict:
        """Normalize product input before persistence."""
        data = product_data.copy()
        if "sku" in data and data["sku"]:
            data["sku"] = data["sku"].strip().upper()
        if "name" in data and data["name"]:
            data["name"] = data["name"].strip()
        if "description" in data and data["description"] is not None:
            data["description"] = data["description"].strip()
        if "unit_of_measure" in data and data["unit_of_measure"]:
            data["unit_of_measure"] = data["unit_of_measure"].strip()
        # New text fields: strip if present
        if "details" in data and data["details"] is not None:
            data["details"] = data["details"].strip()
        if "internal_notes" in data and data["internal_notes"] is not None:
            data["internal_notes"] = data["internal_notes"].strip()
        if "brand" in data and data["brand"] is not None:
            data["brand"] = data["brand"].strip()
        return data

    def _validate_product_data(self, product_data: dict, require_required: bool) -> None:
        """Validate product fields used by create and update operations."""
        if require_required or "sku" in product_data:
            is_valid, error = validate_sku(product_data.get("sku"))
            if not is_valid:
                raise ValueError(error)

        if require_required or "name" in product_data:
            is_valid, error = validate_name(product_data.get("name"), "Nombre")
            if not is_valid:
                raise ValueError(error)

        if (require_required or "unit_of_measure" in product_data) and not product_data.get("unit_of_measure"):
            raise ValueError("La unidad de medida es requerida")

        if product_data.get("unit_price") is not None:
            if not isinstance(product_data.get("unit_price"), (int, float)):
                raise ValueError("El precio unitario debe ser numerico")
            if product_data.get("unit_price") < 0:
                raise ValueError("El precio unitario no puede ser negativo")

        if product_data.get("global_min_stock") is not None:
            if not isinstance(product_data.get("global_min_stock"), int):
                raise ValueError("El stock mínimo global debe ser un número entero")
            if product_data.get("global_min_stock") < 0:
                raise ValueError("El stock mínimo global no puede ser negativo")


# ======================================================================
# Expansion 1 – CategoryService
# ======================================================================

class CategoryService:
    """Business logic for product categories."""

    def __init__(self, db: Session):
        self.repository = CategoryRepository(db)

    def create_category(self, data: dict) -> Dict[str, Any]:
        """Create a new category."""
        name = (data.get("name") or "").strip()
        if not name:
            raise ValueError("El nombre de la categoría es requerido")
        if self.repository.name_exists(name):
            raise ValueError(f"La categoría '{name}' ya existe")
        data = {**data, "name": name}
        category = self.repository.create(data)
        logger.info(f"Category created: {category.name}")
        return category.to_dict()

    def get_category(self, category_id: int) -> Optional[Dict[str, Any]]:
        category = self.repository.get_by_id(category_id)
        return category.to_dict() if category else None

    def get_all_categories(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Return all categories (active only by default)."""
        categories = self.repository.get_all(active_only=active_only)
        return [c.to_dict() for c in categories]

    def update_category(self, category_id: int, data: dict) -> Optional[Dict[str, Any]]:
        if "name" in data:
            name = (data["name"] or "").strip()
            if not name:
                raise ValueError("El nombre de la categoría es requerido")
            if self.repository.name_exists(name, exclude_id=category_id):
                raise ValueError(f"La categoría '{name}' ya existe")
            data = {**data, "name": name}
        category = self.repository.update(category_id, data)
        return category.to_dict() if category else None

    def delete_category(self, category_id: int) -> bool:
        """Soft delete (is_active = False).  Products keep category_id but
        the category won't appear in get_all_categories()."""
        return self.repository.delete(category_id)

    def get_products_by_category(self, category_id: int) -> List[Dict[str, Any]]:
        products = self.repository.get_products_by_category(category_id)
        return [p.to_dict() for p in products]


# ======================================================================
# Expansion 3 – SupplierService
# ======================================================================

class SupplierService:
    """Business logic for suppliers."""

    def __init__(self, db: Session):
        self.repository = SupplierRepository(db)

    def create_supplier(self, data: dict) -> Dict[str, Any]:
        name = (data.get("name") or "").strip()
        if not name:
            raise ValueError("El nombre del proveedor es requerido")
        if self.repository.name_exists(name):
            raise ValueError(f"El proveedor '{name}' ya existe")
        data = {**data, "name": name}
        supplier = self.repository.create(data)
        logger.info(f"Supplier created: {supplier.name}")
        return supplier.to_dict()

    def get_supplier(self, supplier_id: int) -> Optional[Dict[str, Any]]:
        supplier = self.repository.get_by_id(supplier_id)
        return supplier.to_dict() if supplier else None

    def get_all_suppliers(self, active_only: bool = True) -> List[Dict[str, Any]]:
        suppliers = self.repository.get_all(active_only=active_only)
        return [s.to_dict() for s in suppliers]

    def update_supplier(self, supplier_id: int, data: dict) -> Optional[Dict[str, Any]]:
        if "name" in data:
            name = (data["name"] or "").strip()
            if not name:
                raise ValueError("El nombre del proveedor es requerido")
            if self.repository.name_exists(name, exclude_id=supplier_id):
                raise ValueError(f"El proveedor '{name}' ya existe")
            data = {**data, "name": name}
        supplier = self.repository.update(supplier_id, data)
        return supplier.to_dict() if supplier else None

    def delete_supplier(self, supplier_id: int) -> bool:
        """Soft delete (is_active = False).  Products keep default_supplier_id."""
        return self.repository.delete(supplier_id)

    def assign_supplier(self, product_id: int, supplier_id: Optional[int], db: Session) -> Optional[Dict[str, Any]]:
        """Convenience wrapper – delegates to ProductService.assign_supplier."""
        return ProductService(db).assign_supplier(product_id, supplier_id)

    def get_products_by_supplier(self, supplier_id: int) -> List[Dict[str, Any]]:
        products = self.repository.get_products_by_supplier(supplier_id)
        return [p.to_dict() for p in products]

    def get_product_with_supplier(self, product_id: int, db: Session) -> Optional[Dict[str, Any]]:
        """Return product dict with embedded supplier data."""
        return ProductService(db).get_product_with_supplier(product_id)


# ======================================================================
# Expansion 7 – ProductRelationService
# ======================================================================

class ProductRelationService:
    """Manage self-referential product relationships."""

    def __init__(self, db: Session):
        self.repository = ProductRelationRepository(db)
        self._product_repo = ProductRepository(db)

    def add_related_product(
        self,
        product_id: int,
        related_id: int,
        relation_type: str = None,
    ) -> Dict[str, Any]:
        """Create a directed relation from product_id → related_id."""
        if product_id == related_id:
            raise ValueError("Un producto no puede relacionarse consigo mismo")

        if not self._product_repo.get_by_id(product_id):
            raise ValueError(f"Producto {product_id} no encontrado")
        if not self._product_repo.get_by_id(related_id):
            raise ValueError(f"Producto relacionado {related_id} no encontrado")

        if relation_type and relation_type not in _VALID_RELATION_TYPES:
            raise ValueError(
                f"Tipo de relación inválido '{relation_type}'. "
                f"Válidos: {', '.join(sorted(_VALID_RELATION_TYPES))}"
            )

        relation = self.repository.add(product_id, related_id, relation_type)
        logger.info(f"Product relation added: {product_id} → {related_id} ({relation_type})")
        return relation.to_dict()

    def remove_related_product(self, product_id: int, related_id: int) -> bool:
        """Remove a directed relation."""
        success = self.repository.remove(product_id, related_id)
        if success:
            logger.info(f"Product relation removed: {product_id} → {related_id}")
        return success

    def get_related_products(self, product_id: int) -> List[Dict[str, Any]]:
        """Return dicts of all products that product_id links to."""
        relations = self.repository.get_outgoing(product_id)
        result = []
        for rel in relations:
            related = self._product_repo.get_by_id(rel.related_product_id)
            if related:
                data = related.to_dict()
                data["relation_type"] = rel.relation_type
                data["relation_id"] = rel.id
                result.append(data)
        return result

    def get_product_with_relations(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Return product dict with an embedded 'related_products' list."""
        product = self._product_repo.get_by_id(product_id)
        if not product:
            return None
        data = product.to_dict()
        data["related_products"] = self.get_related_products(product_id)
        return data


# ======================================================================
# Expansion 8 – PriceHistoryService
# ======================================================================

class PriceHistoryService:
    """Read-side access to price history (writes happen in ProductService)."""

    def __init__(self, db: Session):
        self.repository = PriceHistoryRepository(db)
        self._product_repo = ProductRepository(db)

    def get_price_history(
        self,
        product_id: int,
        limit: int = 50,
        date_from: datetime = None,
        date_to: datetime = None,
    ) -> List[Dict[str, Any]]:
        entries = self.repository.get_history(
            product_id=product_id,
            limit=limit,
            date_from=date_from,
            date_to=date_to,
        )
        return [e.to_dict() for e in entries]

    def get_latest_price(self, product_id: int) -> Optional[float]:
        entry = self.repository.get_latest(product_id)
        if entry:
            return entry.new_price
        product = self._product_repo.get_by_id(product_id)
        return product.unit_price if product else None

    def get_price_variation(self, product_id: int, days: int = 30) -> Dict[str, Any]:
        """Delegates to ProductService.get_price_variation for convenience."""
        from sqlalchemy.orm import Session as _Session  # local import avoids cycle
        return ProductService(self._product_repo.db).get_price_variation(product_id, days)
