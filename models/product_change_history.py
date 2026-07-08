"""
ProductChangeHistory model – field-level audit log for product updates.

Each row records one field change on one product:
  - which field changed
  - old value (as text)
  - new value (as text)
  - when it changed
  - who made the change (plain text, NO FK to users per design constraints)

Rows are never deleted: even if the product is soft-deleted, history is
preserved for auditing purposes.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from core.database import Base


class ProductChangeHistory(Base):
    """Field-level change log entry for a product."""

    __tablename__ = "product_change_history"

    id = Column(Integer, primary_key=True, index=True)

    product_id = Column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_name = Column(String(50), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    changed_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    # Plain text – no FK to users table per design constraints
    changed_by_name = Column(String(100), nullable=True)

    # Relationship back to product
    product = relationship(
        "Product",
        back_populates="change_history",
    )

    def __repr__(self):
        return (
            f"<ProductChangeHistory(product_id={self.product_id}, "
            f"field='{self.field_name}', at={self.changed_at})>"
        )

    def to_dict(self):
        """Convert change history entry to dictionary."""
        return {
            "id": self.id,
            "product_id": self.product_id,
            "field_name": self.field_name,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "changed_at": self.changed_at.isoformat() if self.changed_at else None,
            "changed_by_name": self.changed_by_name,
        }
