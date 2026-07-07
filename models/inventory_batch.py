"""
InventoryBatch model - Lotes y fechas de caducidad por item de inventario.
"""

from sqlalchemy import Column, Integer, Float, String, Text, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base


class InventoryBatch(Base):
    """Lote de stock asociado a un registro de inventario."""

    __tablename__ = "inventory_batches"
    __table_args__ = (
        UniqueConstraint("inventory_id", "batch_number", name="uq_inventory_batch_number"),
    )

    id = Column(Integer, primary_key=True, index=True)
    inventory_id = Column(
        Integer,
        ForeignKey("inventory.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    batch_number = Column(String(50), nullable=True)
    manufacturing_date = Column(Date, nullable=True)
    expiration_date = Column(Date, nullable=True)
    quantity = Column(Integer, nullable=False, default=0)
    unit_cost = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    inventory = relationship("Inventory", back_populates="batches")

    def __repr__(self):
        return (
            f"<InventoryBatch(id={self.id}, inventory_id={self.inventory_id}, "
            f"batch={self.batch_number}, qty={self.quantity})>"
        )

    def to_dict(self):
        return {
            "id": self.id,
            "inventory_id": self.inventory_id,
            "batch_number": self.batch_number,
            "manufacturing_date": (
                self.manufacturing_date.isoformat() if self.manufacturing_date else None
            ),
            "expiration_date": (
                self.expiration_date.isoformat() if self.expiration_date else None
            ),
            "quantity": self.quantity,
            "unit_cost": self.unit_cost,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
