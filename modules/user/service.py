"""
User service layer - Business logic.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from modules.user.repository import UserRepository
from core.event_bus import event_bus
from core.settings import settings
from utils.validators import validate_name, validate_email, validate_password
import logging

logger = logging.getLogger(__name__)


class UserService:
    """Service for user business logic."""

    def __init__(self, db: Session):
        self.repository = UserRepository(db)

    def create_user(self, user_data: dict, password: str) -> Dict[str, Any]:
        """Create a new user."""
        user_data = self._sanitize_user_data(user_data)
        self._validate_user_data(user_data, require_required=True)
        
        # Validate password
        is_valid, error = validate_password(password, settings.PASSWORD_MIN_LENGTH)
        if not is_valid:
            raise ValueError(error)

        # Validate email uniqueness
        if self.repository.email_exists(user_data.get("email")):
            raise ValueError(f"Ya existe un usuario con el correo '{user_data.get('email')}'")

        # Create user
        user = self.repository.create(user_data)
        user.set_password(password)
        self.db = self.repository.db
        self.db.commit()
        self.db.refresh(user)
        
        # Emit event
        event_data = {
            "user_id": user.id,
            "name": user.name,
            "email": user.email
        }
        event_bus.emit(settings.Events.USER_CREATED, event_data)
        
        logger.info(f"User created: {user.email}")
        return user.to_dict()

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        user = self.repository.get_by_id(user_id)
        return user.to_dict() if user else None

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email."""
        user = self.repository.get_by_email(email)
        return user.to_dict() if user else None

    def list_users(self, page: int = 1, page_size: int = 20, search: str = None) -> Dict[str, Any]:
        """List users with pagination."""
        skip = (page - 1) * page_size
        users = self.repository.get_all(skip=skip, limit=page_size, search=search)
        total = self.repository.count(search=search)

        return {
            "users": [u.to_dict() for u in users],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }

    def update_user(self, user_id: int, update_data: dict, password: str = None) -> Optional[Dict[str, Any]]:
        """Update user."""
        update_data = self._sanitize_user_data(update_data)
        self._validate_user_data(update_data, require_required=False)

        # Check for email uniqueness if email is being updated
        if "email" in update_data:
            if self.repository.email_exists(update_data["email"], exclude_id=user_id):
                raise ValueError(f"Ya existe un usuario con el correo '{update_data['email']}'")

        user = self.repository.update(user_id, update_data)
        if not user:
            return None

        # Update password if provided
        if password:
            is_valid, error = validate_password(password, settings.PASSWORD_MIN_LENGTH)
            if not is_valid:
                raise ValueError(error)
            user.set_password(password)
            self.db = self.repository.db
            self.db.commit()
            self.db.refresh(user)

        # Emit event
        event_data = {
            "user_id": user.id,
            "name": user.name,
            "email": user.email,
            "changes": update_data
        }
        event_bus.emit(settings.Events.USER_UPDATED, event_data)

        logger.info(f"User updated: {user.email}")
        return user.to_dict()

    def delete_user(self, user_id: int) -> bool:
        """Soft delete user."""
        user = self.repository.get_by_id(user_id)
        if not user:
            return False

        success = self.repository.delete(user_id)
        if success:
            # Emit event
            event_data = {
                "user_id": user_id,
                "name": user.name,
                "email": user.email
            }
            event_bus.emit(settings.Events.USER_DELETED, event_data)
            
            logger.info(f"User deleted: {user.email}")

        return success

    def search_users(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search users by name or email."""
        users = self.repository.get_all(limit=limit, search=query)
        return [u.to_dict() for u in users]

    def get_all_active_users(self) -> List[Dict[str, Any]]:
        """Get all active users."""
        users = self.repository.get_all(limit=1000)
        return [u.to_dict() for u in users]

    def _sanitize_user_data(self, user_data: dict) -> dict:
        """Normalize user input before persistence."""
        data = user_data.copy()
        if "name" in data and data["name"]:
            data["name"] = data["name"].strip()
        if "email" in data and data["email"]:
            data["email"] = data["email"].strip().lower()
        return data

    def _validate_user_data(self, user_data: dict, require_required: bool) -> None:
        """Validate user fields used by create and update operations."""
        if require_required or "name" in user_data:
            is_valid, error = validate_name(user_data.get("name"), "Nombre")
            if not is_valid:
                raise ValueError(error)

        if require_required or "email" in user_data:
            is_valid, error = validate_email(user_data.get("email"))
            if not is_valid:
                raise ValueError(error)
