"""
Branch service layer - Business logic.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from modules.branches.repository import BranchRepository
import logging

logger = logging.getLogger(__name__)


class BranchService:
    """Service for branch business logic."""

    def __init__(self, db: Session):
        self.repository = BranchRepository(db)

    def create_branch(self, branch_data: dict) -> Dict[str, Any]:
        """Create a new branch."""
        # Validate name uniqueness
        if self.repository.name_exists(branch_data.get("name")):
            raise ValueError(f"Sucursal '{branch_data.get('name')}' ya existe")

        # Create branch
        branch = self.repository.create(branch_data)
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
        # Check for name uniqueness if name is being updated
        if "name" in update_data:
            if self.repository.name_exists(update_data["name"], exclude_id=branch_id):
                raise ValueError(f"Sucursal '{update_data['name']}' ya existe")

        branch = self.repository.update(branch_id, update_data)
        if not branch:
            return None

        logger.info(f"Branch updated: {branch.name}")
        return branch.to_dict()

    def delete_branch(self, branch_id: int) -> bool:
        """Soft delete branch."""
        branch = self.repository.get_by_id(branch_id)
        if not branch:
            return False

        success = self.repository.delete(branch_id)
        if success:
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
