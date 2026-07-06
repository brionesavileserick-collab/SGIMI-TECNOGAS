"""
Inventory model for tracking stock levels per branch.
"""

from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base


class Inventory(Base):
    """Inventory model for stock tracking per branch."""

    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    physical_stock = Column(Integer, default=0, nullable=False)
    digital_stock = Column(Integer, default=0, nullable=False)
    min_stock = Column(Integer, default=0)
    max_stock = Column(Integer, nullable=True)
    last_count_date = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    product = relationship("Product", back_populates="inventory_items")
    branch = relationship("Branch", back_populates="inventory_items")

    def __repr__(self):
        return f"<Inventory(id={self.id}, product_id={self.product_id}, branch_id={self.branch_id}, physical={self.physical_stock}, digital={self.digital_stock})>"

    @property
    def difference(self) -> int:
        """Calculate difference between physical and digital stock."""
        return self.physical_stock - self.digital_stock

    @property
    def has_discrepancy(self) -> bool:
        """Check if there's a discrepancy between physical and digital stock."""
        return self.physical_stock != self.digital_stock

    @property
    def is_low_stock(self) -> bool:
        """Check if stock is below minimum level."""
        return min(self.physical_stock, self.digital_stock) <= self.min_stock

    def to_dict(self):
        """Convert inventory to dictionary."""
        return {
            "id": self.id,
            "product_id": self.product_id,
            "branch_id": self.branch_id,
            "physical_stock": self.physical_stock,
            "digital_stock": self.digital_stock,
            "difference": self.difference,
            "has_discrepancy": self.has_discrepancy,
            "is_low_stock": self.is_low_stock,
            "min_stock": self.min_stock,
            "max_stock": self.max_stock,
            "last_count_date": self.last_count_date.isoformat() if self.last_count_date else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
