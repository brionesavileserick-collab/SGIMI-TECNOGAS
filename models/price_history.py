"""
PriceHistory model – audit trail for product price changes.

Expansion 8 - Historial de Precios: records every unit_price change on a
product, who made it, and an optional reason.

change_reason accepted values (not enforced at DB level, validated in service):
    "ajuste"    – general price adjustment
    "promocion" – temporary promotional price
    "costo"     – cost-driven update
    "error"     – correction of a data entry mistake
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base


class PriceHistory(Base):
    """One entry per price change on a product."""

    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_price = Column(Float, nullable=True)
    new_price = Column(Float, nullable=True)
    # "ajuste" | "promocion" | "costo" | "error" | NULL
    change_reason = Column(String(100), nullable=True)
    # Soft reference – no FK enforced so user deletions don't cascade
    changed_by_user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationship back to Product
    product = relationship("Product", back_populates="price_history_entries")

    def __repr__(self):
        return (
            f"<PriceHistory(product_id={self.product_id}, "
            f"previous={self.previous_price}, new={self.new_price})>"
        )

    def to_dict(self):
        """Convert price history entry to dictionary."""
        return {
            "id": self.id,
            "product_id": self.product_id,
            "previous_price": self.previous_price,
            "new_price": self.new_price,
            "change_reason": self.change_reason,
            "changed_by_user_id": self.changed_by_user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
