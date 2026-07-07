"""
ProductRelation model – many-to-many self-referential relationship on Product.

Expansion 7 - Productos Relacionados: link products as substitutes,
complements, or similar items.

relation_type accepted values (not enforced at DB level, validated in service):
    "sustituto"   – can replace the product
    "complemento" – typically sold/used together
    "similar"     – same family or presentation

UniqueConstraint on (product_id, related_product_id) prevents duplicates.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base


class ProductRelation(Base):
    """Directional relation between two products."""

    __tablename__ = "product_relations"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    related_product_id = Column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # "sustituto" | "complemento" | "similar" | NULL
    relation_type = Column(String(30), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("product_id", "related_product_id", name="uq_product_relation"),
    )

    # Back-references resolved by string to avoid import cycles
    product = relationship(
        "Product",
        foreign_keys=[product_id],
        back_populates="outgoing_relations",
    )
    related_product = relationship(
        "Product",
        foreign_keys=[related_product_id],
    )

    def __repr__(self):
        return (
            f"<ProductRelation(product_id={self.product_id}, "
            f"related_product_id={self.related_product_id}, "
            f"type='{self.relation_type}')>"
        )

    def to_dict(self):
        """Convert relation to dictionary."""
        return {
            "id": self.id,
            "product_id": self.product_id,
            "related_product_id": self.related_product_id,
            "relation_type": self.relation_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
