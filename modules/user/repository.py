"""
User repository for database operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from models.user import User


class UserRepository:
    """Repository for user database operations."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, user_data: dict) -> User:
        """Create a new user."""
        user = User(**user_data)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return self.db.query(User).filter(User.email == email.lower()).first()

    def get_all(self, skip: int = 0, limit: int = 100, search: str = None, active_only: bool = True) -> List[User]:
        """Get all users with optional filtering."""
        query = self.db.query(User)

        if active_only:
            query = query.filter(User.is_active == True)

        if search:
            query = query.filter(
                or_(
                    User.name.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%")
                )
            )

        return query.offset(skip).limit(limit).all()

    def count(self, active_only: bool = True, search: str = None) -> int:
        """Count users with optional filtering."""
        query = self.db.query(User)

        if active_only:
            query = query.filter(User.is_active == True)

        if search:
            query = query.filter(
                or_(
                    User.name.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%")
                )
            )

        return query.count()

    def update(self, user_id: int, update_data: dict) -> Optional[User]:
        """Update user."""
        user = self.get_by_id(user_id)
        if not user:
            return None

        for key, value in update_data.items():
            if hasattr(user, key):
                setattr(user, key, value)

        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, user_id: int) -> bool:
        """Soft delete user by setting is_active to False."""
        user = self.get_by_id(user_id)
        if not user:
            return False

        user.is_active = False
        self.db.commit()
        return True

    def hard_delete(self, user_id: int) -> bool:
        """Permanently delete user."""
        user = self.get_by_id(user_id)
        if not user:
            return False

        self.db.delete(user)
        self.db.commit()
        return True

    def email_exists(self, email: str, exclude_id: int = None) -> bool:
        """Check if email already exists."""
        query = self.db.query(User).filter(func.lower(User.email) == email.lower())
        if exclude_id:
            query = query.filter(User.id != exclude_id)
        return query.first() is not None

    def get_by_role(self, role: str) -> List[User]:
        """Get users by role."""
        return self.db.query(User).filter(User.role == role).all()

    def get_by_branch(self, branch_id: int) -> List[User]:
        """Get users assigned to a branch."""
        return self.db.query(User).filter(User.assigned_branch_id == branch_id).all()

    def get_gerentes_by_branch(self, branch_id: int) -> List[User]:
        """Get branch managers by branch."""
        return self.db.query(User).filter(User.assigned_branch_id == branch_id, User.role == "gerente").all()

    def get_empleados_by_branch(self, branch_id: int) -> List[User]:
        """Get employees by branch."""
        return self.db.query(User).filter(User.assigned_branch_id == branch_id, User.role == "empleado").all()

    def get_admins(self) -> List[User]:
        """Get all admins."""
        return self.db.query(User).filter(User.role == "admin").all()

    def update_last_activity(self, user_id: int) -> None:
        """Update the last activity timestamp."""
        user = self.get_by_id(user_id)
        if user:
            user.last_activity = func.now()
            self.db.commit()

    def exists_by_email(self, email: str) -> bool:
        """Alias for email_exists."""
        return self.email_exists(email)
