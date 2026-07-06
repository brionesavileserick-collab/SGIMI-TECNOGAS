"""
Product service layer - Business logic and event emission.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from modules.products.repository import ProductRepository
from core.event_bus import event_bus
from core.settings import settings
from utils.validators import validate_name, validate_sku
import logging

logger = logging.getLogger(__name__)


class ProductService:
    """Service for product business logic."""

    def __init__(self, db: Session):
        self.repository = ProductRepository(db)

    def create_product(self, product_data: dict) -> Dict[str, Any]:
        """Create a new product and emit event."""
        product_data = self._sanitize_product_data(product_data)
        self._validate_product_data(product_data, require_required=True)

        # Validate SKU uniqueness
        if self.repository.sku_exists(product_data.get("sku")):
            raise ValueError(f"SKU '{product_data.get('sku')}' already exists")

        # Create product
        product = self.repository.create(product_data)

        # Emit event
        event_data = {
            "product_id": product.id,
            "sku": product.sku,
            "name": product.name
        }
        event_bus.emit(settings.Events.PRODUCT_CREATED, event_data)

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

    def list_products(self, page: int = 1, page_size: int = 20, search: str = None) -> Dict[str, Any]:
        """List products with pagination."""
        skip = (page - 1) * page_size
        products = self.repository.get_all(skip=skip, limit=page_size, search=search)
        total = self.repository.count(search=search)

        return {
            "products": [p.to_dict() for p in products],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }

    def update_product(self, product_id: int, update_data: dict) -> Optional[Dict[str, Any]]:
        """Update product and emit event."""
        update_data = self._sanitize_product_data(update_data)
        self._validate_product_data(update_data, require_required=False)

        # Check for SKU uniqueness if SKU is being updated
        if "sku" in update_data:
            if self.repository.sku_exists(update_data["sku"], exclude_id=product_id):
                raise ValueError(f"SKU '{update_data['sku']}' already exists")

        product = self.repository.update(product_id, update_data)
        if not product:
            return None

        # Emit event
        event_data = {
            "product_id": product.id,
            "sku": product.sku,
            "name": product.name,
            "changes": update_data
        }
        event_bus.emit(settings.Events.PRODUCT_UPDATED, event_data)

        logger.info(f"Product updated: {product.sku}")
        return product.to_dict()

    def delete_product(self, product_id: int) -> bool:
        """Soft delete product and emit event."""
        product = self.repository.get_by_id(product_id)
        if not product:
            return False

        success = self.repository.delete(product_id)
        if success:
            # Emit event
            event_data = {
                "product_id": product_id,
                "sku": product.sku,
                "name": product.name
            }
            event_bus.emit(settings.Events.PRODUCT_DELETED, event_data)
            logger.info(f"Product deleted: {product.sku}")

        return success

    def search_products(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search products by name, SKU, or description."""
        products = self.repository.get_all(limit=limit, search=query)
        return [p.to_dict() for p in products]

    def get_all_active_products(self) -> List[Dict[str, Any]]:
        """Get all active products."""
        products = self.repository.get_all(limit=1000)
        return [p.to_dict() for p in products]

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
