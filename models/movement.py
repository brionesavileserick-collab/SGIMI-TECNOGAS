"""
Movement model for inventory transactions.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base
import enum


class MovementType(str, enum.Enum):
    """Movement type enumeration."""
    ENTRADA = "entrada"
    SALIDA = "salida"
    AJUSTE = "ajuste"
    TRANSFERENCIA = "transferencia"


class MovementState(str, enum.Enum):
    """Movement state enumeration."""
    PENDIENTE = "pendiente"
    VALIDADO = "validado"
    RECHAZADO = "rechazado"


class Movement(Base):
    """Movement model for inventory transactions."""

    __tablename__ = "movements"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    destination_branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    movement_type = Column(String(20), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    state = Column(String(20), default="pendiente", nullable=False, index=True)
    reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)
    validated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    product = relationship("Product", back_populates="movements")
    branch = relationship("Branch", foreign_keys=[branch_id])
    destination_branch = relationship("Branch", foreign_keys=[destination_branch_id])
    user = relationship("User", foreign_keys=[user_id])
    validator = relationship("User", foreign_keys=[validated_by])

    def __repr__(self):
        return f"<Movement(id={self.id}, type='{self.movement_type}', state='{self.state}', quantity={self.quantity})>"

    def to_dict(self):
        """Convert movement to dictionary."""
        return {
            "id": self.id,
            "product_id": self.product_id,
            "branch_id": self.branch_id,
            "destination_branch_id": self.destination_branch_id,
            "user_id": self.user_id,
            "movement_type": self.movement_type,
            "quantity": self.quantity,
            "state": self.state,
            "reason": self.reason,
            "notes": self.notes,
            "validated_at": self.validated_at.isoformat() if self.validated_at else None,
            "validated_by": self.validated_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
