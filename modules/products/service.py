"""
Product service layer - Business logic and event emission.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from modules.products.repository import ProductRepository
from core.event_bus import event_bus
from core.settings import settings
import logging

logger = logging.getLogger(__name__)


class ProductService:
    """Service for product business logic."""

    def __init__(self, db: Session):
        self.repository = ProductRepository(db)

    def create_product(self, product_data: dict) -> Dict[str, Any]:
        """Create a new product and emit event."""
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
