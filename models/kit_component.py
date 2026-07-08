"""
KitComponent model – links a "kit" product to its component products.

A kit is a product whose is_kit flag is True.  Each KitComponent row
records one component (another product) and the quantity required.

Constraints:
  - UniqueConstraint(kit_product_id, component_product_id) prevents
    duplicate component entries in the same kit.
  - A product cannot be its own component (enforced in the service layer).
"""

from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from core.database import Base


class KitComponent(Base):
    """Component entry for a product kit."""

    __tablename__ = "kit_components"

    id = Column(Integer, primary_key=True, index=True)

    kit_product_id = Column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    component_product_id = Column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quantity = Column(Integer, nullable=False, default=1)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "kit_product_id",
            "component_product_id",
            name="uq_kit_component",
        ),
    )

    # Relationships resolved by string to avoid import cycles
    kit_product = relationship(
        "Product",
        foreign_keys=[kit_product_id],
        back_populates="kit_components",
    )
    component_product = relationship(
        "Product",
        foreign_keys=[component_product_id],
        back_populates="component_of_kits",
    )

    def __repr__(self):
        return (
            f"<KitComponent(kit={self.kit_product_id}, "
            f"component={self.component_product_id}, qty={self.quantity})>"
        )

    def to_dict(self):
        """Convert kit component to dictionary."""
        return {
            "id": self.id,
            "kit_product_id": self.kit_product_id,
            "component_product_id": self.component_product_id,
            "quantity": self.quantity,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_dict_full(self):
        """Dict with embedded component product info (when already loaded)."""
        data = self.to_dict()
        if self.component_product:
            data["component_product"] = {
                "id": self.component_product.id,
                "sku": self.component_product.sku,
                "name": self.component_product.name,
                "unit_of_measure": self.component_product.unit_of_measure,
                "unit_price": self.component_product.unit_price,
            }
        return data
