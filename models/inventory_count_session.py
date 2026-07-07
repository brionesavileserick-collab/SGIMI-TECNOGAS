"""
InventoryCountSession model - Workflow formal de conteos físicos programados.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base


class InventoryCountSession(Base):
    """Sesión de conteo físico programado para una sucursal."""

    __tablename__ = "inventory_count_sessions"

    id = Column(Integer, primary_key=True, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True)
    scheduled_date = Column(DateTime(timezone=True), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), default="pending", nullable=False)
    notes = Column(Text, nullable=True)
    validator_count = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    count_items = relationship(
        "InventoryCountItem",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return (
            f"<InventoryCountSession(id={self.id}, branch_id={self.branch_id}, "
            f"status={self.status})>"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "branch_id": self.branch_id,
            "scheduled_date": self.scheduled_date.isoformat() if self.scheduled_date else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "notes": self.notes,
            "validator_count": self.validator_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
