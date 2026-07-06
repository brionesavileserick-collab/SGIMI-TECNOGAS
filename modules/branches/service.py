"""
Branch service layer - Business logic.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from modules.branches.repository import BranchRepository
from modules.inventory.service import InventoryService
from modules.movements.service import MovementService
from core.event_bus import event_bus
from core.settings import settings
from utils.validators import validate_name
import logging

logger = logging.getLogger(__name__)


class BranchService:
    """Service for branch business logic."""

    def __init__(self, db: Session):
        self.repository = BranchRepository(db)
        self.inventory_service = InventoryService(db)
        self.movement_service = MovementService(db)

    def create_branch(self, branch_data: dict) -> Dict[str, Any]:
        """Create a new branch."""
        branch_data = self._sanitize_branch_data(branch_data)
        self._validate_branch_data(branch_data, require_required=True)

        # Validate name uniqueness
        if self.repository.name_exists(branch_data.get("name")):
            raise ValueError(f"Sucursal '{branch_data.get('name')}' ya existe")

        # Create branch
        branch = self.repository.create(branch_data)
        
        # Emit event
        event_data = {
            "branch_id": branch.id,
            "name": branch.name
        }
        event_bus.emit(settings.Events.BRANCH_CREATED, event_data)
        
        logger.info(f"Branch created: {branch.name}")
        return branch.to_dict()

    def get_branch(self, branch_id: int) -> Optional[Dict[str, Any]]:
        """Get branch by ID."""
        branch = self.repository.get_by_id(branch_id)
        return branch.to_dict() if branch else None

    def get_branch_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get branch by name."""
        branch = self.repository.get_by_name(name)
        return branch.to_dict() if branch else None

    def list_branches(self, page: int = 1, page_size: int = 20, search: str = None) -> Dict[str, Any]:
        """List branches with pagination."""
        skip = (page - 1) * page_size
        branches = self.repository.get_all(skip=skip, limit=page_size, search=search)
        total = self.repository.count(search=search)

        return {
            "branches": [b.to_dict() for b in branches],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }

    def update_branch(self, branch_id: int, update_data: dict) -> Optional[Dict[str, Any]]:
        """Update branch."""
        update_data = self._sanitize_branch_data(update_data)
        self._validate_branch_data(update_data, require_required=False)

        # Check for name uniqueness if name is being updated
        if "name" in update_data:
            if self.repository.name_exists(update_data["name"], exclude_id=branch_id):
                raise ValueError(f"Sucursal '{update_data['name']}' ya existe")

        branch = self.repository.update(branch_id, update_data)
        if not branch:
            return None

        # Emit event
        event_data = {
            "branch_id": branch.id,
            "name": branch.name,
            "changes": update_data
        }
        event_bus.emit(settings.Events.BRANCH_UPDATED, event_data)

        logger.info(f"Branch updated: {branch.name}")
        return branch.to_dict()

    def delete_branch(self, branch_id: int) -> bool:
        """Soft delete branch."""
        branch = self.repository.get_by_id(branch_id)
        if not branch:
            return False

        success = self.repository.delete(branch_id)
        if success:
            # Emit event
            event_data = {
                "branch_id": branch_id,
                "name": branch.name
            }
            event_bus.emit(settings.Events.BRANCH_DELETED, event_data)
            
            logger.info(f"Branch deleted: {branch.name}")

        return success

    def search_branches(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search branches by name or address."""
        branches = self.repository.get_all(limit=limit, search=query)
        return [b.to_dict() for b in branches]

    def get_all_active_branches(self) -> List[Dict[str, Any]]:
        """Get all active branches."""
        branches = self.repository.get_all(limit=1000)
        return [b.to_dict() for b in branches]

    def _sanitize_branch_data(self, branch_data: dict) -> dict:
        """Normalize branch input before persistence."""
        data = branch_data.copy()
        if "name" in data and data["name"]:
            data["name"] = data["name"].strip()
        if "address" in data and data["address"] is not None:
            data["address"] = data["address"].strip()
        return data

    def _validate_branch_data(self, branch_data: dict, require_required: bool) -> None:
        """Validate branch fields used by create and update operations."""
        if require_required or "name" in branch_data:
            is_valid, error = validate_name(branch_data.get("name"), "Nombre")
            if not is_valid:
                raise ValueError(error)

        if branch_data.get("address") and len(branch_data["address"]) > 255:
            raise ValueError("La direccion no puede tener mas de 255 caracteres")

    # Matrix-specific methods for global visibility

    def get_global_inventory(self, page: int = 1, page_size: int = 20,
                            product_id: int = None, search: str = None) -> Dict[str, Any]:
        """
        Get global inventory (sum of stock across all branches).
        This is for matrix view to see total stock per product.
        """
        return self.inventory_service.get_global_inventory(
            page=page,
            page_size=page_size,
            product_id=product_id,
            search=search
        )

    def get_product_stock_across_branches(self, product_id: int) -> List[Dict[str, Any]]:
        """
        Get stock for a specific product across all branches.
        Useful for matrix to see product distribution.
        """
        return self.inventory_service.get_product_stock_across_branches(product_id)

    def get_branch_inventory(self, branch_id: int, page: int = 1, page_size: int = 20,
                            product_id: int = None, low_stock_only: bool = False,
                            discrepancy_only: bool = False, search: str = None) -> Dict[str, Any]:
        """
        Get inventory for a specific branch.
        This is for matrix to view any branch's local inventory.
        """
        return self.inventory_service.list_inventory(
            page=page,
            page_size=page_size,
            branch_id=branch_id,
            product_id=product_id,
            low_stock_only=low_stock_only,
            discrepancy_only=discrepancy_only,
            search=search
        )

    def get_transfers_between_branches(self, origin_branch_id: int = None,
                                       destination_branch_id: int = None,
                                       page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        """
        Get transfer movements between branches.
        For matrix to monitor inter-branch transfers.
        """
        return self.movement_service.list_movements(
            page=page,
            page_size=page_size,
            branch_id=origin_branch_id,
            movement_type="transferencia"
        )

    def get_all_branches_totals(self) -> Dict[str, Any]:
        """
        Get inventory totals for all branches.
        For matrix to have a global overview.
        """
        branches = self.get_all_active_branches()
        result = {
            "branches": [],
            "global_totals": {
                "total_physical_stock": 0,
                "total_digital_stock": 0,
                "discrepancy_count": 0,
                "low_stock_count": 0
            }
        }

        for branch in branches:
            branch_totals = self.inventory_service.get_totals(branch_id=branch["id"])
            branch["totals"] = branch_totals
            result["branches"].append(branch)

            # Accumulate global totals
            result["global_totals"]["total_physical_stock"] += branch_totals["total_physical_stock"]
            result["global_totals"]["total_digital_stock"] += branch_totals["total_digital_stock"]
            result["global_totals"]["discrepancy_count"] += branch_totals["discrepancy_count"]
            result["global_totals"]["low_stock_count"] += branch_totals["low_stock_count"]

        return result
