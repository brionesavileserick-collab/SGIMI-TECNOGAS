"""
InventoryCountItem model - Items individuales dentro de una sesión de conteo.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base


class InventoryCountItem(Base):
    """Registro de conteo de un producto dentro de una sesión."""

    __tablename__ = "inventory_count_items"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer,
        ForeignKey("inventory_count_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    inventory_id = Column(Integer, ForeignKey("inventory.id", ondelete="SET NULL"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    expected_physical = Column(Integer, nullable=False)
    counted_physical = Column(Integer, nullable=True)
    difference = Column(Integer, nullable=True)
    is_discrepancy = Column(Boolean, default=False, nullable=False)
    counted_at = Column(DateTime(timezone=True), nullable=True)
    validator_name = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("InventoryCountSession", back_populates="count_items")

    def __repr__(self):
        return (
            f"<InventoryCountItem(id={self.id}, session_id={self.session_id}, "
            f"expected={self.expected_physical}, counted={self.counted_physical})>"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "inventory_id": self.inventory_id,
            "product_id": self.product_id,
            "expected_physical": self.expected_physical,
            "counted_physical": self.counted_physical,
            "difference": self.difference,
            "is_discrepancy": self.is_discrepancy,
            "counted_at": self.counted_at.isoformat() if self.counted_at else None,
            "validator_name": self.validator_name,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
