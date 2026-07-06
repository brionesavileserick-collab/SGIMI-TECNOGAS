"""
Branch repository for database operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from models.branch import Branch


class BranchRepository:
    """Repository for branch database operations."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, branch_data: dict) -> Branch:
        """Create a new branch."""
        branch = Branch(**branch_data)
        self.db.add(branch)
        self.db.commit()
        self.db.refresh(branch)
        return branch

    def get_by_id(self, branch_id: int) -> Optional[Branch]:
        """Get branch by ID."""
        return self.db.query(Branch).filter(Branch.id == branch_id).first()

    def get_by_name(self, name: str) -> Optional[Branch]:
        """Get branch by name."""
        return self.db.query(Branch).filter(Branch.name == name).first()

    def get_all(self, skip: int = 0, limit: int = 100, search: str = None, active_only: bool = True) -> List[Branch]:
        """Get all branches with optional filtering."""
        query = self.db.query(Branch)

        if active_only:
            query = query.filter(Branch.is_active == True)

        if search:
            query = query.filter(
                or_(
                    Branch.name.ilike(f"%{search}%"),
                    Branch.address.ilike(f"%{search}%")
                )
            )

        return query.offset(skip).limit(limit).all()

    def count(self, active_only: bool = True, search: str = None) -> int:
        """Count branches with optional filtering."""
        query = self.db.query(Branch)

        if active_only:
            query = query.filter(Branch.is_active == True)

        if search:
            query = query.filter(
                or_(
                    Branch.name.ilike(f"%{search}%"),
                    Branch.address.ilike(f"%{search}%")
                )
            )

        return query.count()

    def update(self, branch_id: int, update_data: dict) -> Optional[Branch]:
        """Update branch."""
        branch = self.get_by_id(branch_id)
        if not branch:
            return None

        for key, value in update_data.items():
            if hasattr(branch, key):
                setattr(branch, key, value)

        self.db.commit()
        self.db.refresh(branch)
        return branch

    def delete(self, branch_id: int) -> bool:
        """Soft delete branch by setting is_active to False."""
        branch = self.get_by_id(branch_id)
        if not branch:
            return False

        branch.is_active = False
        self.db.commit()
        return True

    def hard_delete(self, branch_id: int) -> bool:
        """Permanently delete branch."""
        branch = self.get_by_id(branch_id)
        if not branch:
            return False

        self.db.delete(branch)
        self.db.commit()
        return True

    def name_exists(self, name: str, exclude_id: int = None) -> bool:
        """Check if name already exists."""
        query = self.db.query(Branch).filter(func.lower(Branch.name) == name.lower())
        if exclude_id:
            query = query.filter(Branch.id != exclude_id)
        return query.first() is not None
