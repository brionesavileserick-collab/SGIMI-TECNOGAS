"""
MovementStateHistory model — Expansión 7.

Registra cada cambio de estado que sufre un movimiento a lo largo de su
ciclo de vida. La tabla es completamente opcional: no afecta el flujo
principal si no se usa.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base


class MovementStateHistory(Base):
    """Historial de cambios de estado de un movimiento."""

    __tablename__ = "movement_state_history"

    id = Column(Integer, primary_key=True, index=True)
    movement_id = Column(
        Integer,
        ForeignKey("movements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_state = Column(String(20), nullable=True)   # None si es la primera entrada
    new_state = Column(String(20), nullable=False)
    changed_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    change_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    movement = relationship("Movement", back_populates="state_history")
    user = relationship("User", foreign_keys=[changed_by])

    def __repr__(self):
        return (
            f"<MovementStateHistory(movement_id={self.movement_id}, "
            f"'{self.previous_state}' → '{self.new_state}')>"
        )

    def to_dict(self):
        """Convert history entry to dictionary."""
        return {
            "id": self.id,
            "movement_id": self.movement_id,
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "changed_by": self.changed_by,
            "change_reason": self.change_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
