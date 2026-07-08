"""
Category model for grouping products.

Expansion 1 – Categorías: optional grouping for products.
All fields except 'name' are nullable to maintain backwards compatibility.

Expansion (new) – Jerarquía de Categorías:
  parent_category_id  – FK → categories (self-referential, nullable)
  level               – depth in the tree; 0 = root
  path                – human-readable breadcrumb "A > B > C" (auto-computed)
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base


class Category(Base):
    """Category model for grouping products."""

    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # ------------------------------------------------------------------ #
    # Jerarquía de Categorías                                             #
    # ------------------------------------------------------------------ #
    parent_category_id = Column(
        Integer,
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    level = Column(Integer, nullable=False, default=0)
    path = Column(String(255), nullable=True)

    # ------------------------------------------------------------------ #
    # Relationships                                                        #
    # ------------------------------------------------------------------ #
    products = relationship("Product", back_populates="category")

    # Self-referential hierarchy
    parent = relationship(
        "Category",
        remote_side="Category.id",
        foreign_keys=[parent_category_id],
        back_populates="children",
    )
    children = relationship(
        "Category",
        foreign_keys=[parent_category_id],
        back_populates="parent",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}', level={self.level})>"

    def to_dict(self):
        """Convert category to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            # Hierarchy fields
            "parent_category_id": self.parent_category_id,
            "level": self.level,
            "path": self.path,
        }

    def to_dict_with_children(self):
        """Recursive dict that embeds direct children."""
        data = self.to_dict()
        data["children"] = [c.to_dict_with_children() for c in self.children if c.is_active]
        return data
