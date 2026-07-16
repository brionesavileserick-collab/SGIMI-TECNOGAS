"""
User model for authentication and tracking.
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base
import hashlib
import secrets


class User(Base):
    """User model for system access and movement tracking."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    registration_date = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)
    role = Column(String(20), nullable=False, default="empleado", index=True)
    assigned_branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    is_branch_manager = Column(Boolean, nullable=False, default=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    last_activity = Column(DateTime(timezone=True), nullable=True)
    is_first_login = Column(Boolean, nullable=False, default=True)

    # Relationships
    movements = relationship("Movement", back_populates="user", foreign_keys="Movement.user_id")
    branch = relationship("Branch", foreign_keys=[assigned_branch_id], lazy="select")

    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}', email='{self.email}')>"

    def set_password(self, password: str) -> None:
        """Hash and set password."""
        salt = secrets.token_hex(16)
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        self.password_hash = f"{salt}${password_hash}"

    def verify_password(self, password: str) -> bool:
        """Verify password against stored hash."""
        if not self.password_hash or "$" not in self.password_hash:
            return False
        salt, stored_hash = self.password_hash.split("$")
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return secrets.compare_digest(password_hash, stored_hash)

    def to_dict(self):
        """Convert user to dictionary (excluding password)."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "registration_date": self.registration_date.isoformat() if self.registration_date else None,
            "is_active": self.is_active,
            "role": self.role or "empleado",
            "assigned_branch_id": self.assigned_branch_id,
            "is_branch_manager": self.is_branch_manager,
            "created_by": self.created_by,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "is_first_login": self.is_first_login,
        }
