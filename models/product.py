"""
Product model for inventory items.

Original fields preserved as-is for full backwards compatibility.

New optional fields added per expansion plan:
  Exp 1  – category_id          (FK → categories, nullable)
  Exp 2  – brand                 (String 100, nullable)
  Exp 3  – default_supplier_id  (FK → suppliers, nullable)
  Exp 4  – details               (Text, nullable)
  Exp 5  – internal_notes        (Text, nullable)
  Exp 6  – global_min_stock      (Integer, nullable)

New relationships:
  category            → Category  (many-to-one, optional)
  default_supplier    → Supplier  (many-to-one, optional)
  outgoing_relations  → ProductRelation  (one-to-many, self-ref source)
  price_history_entries → PriceHistory  (one-to-many)

Existing relationships untouched:
  inventory_items     → Inventory
  movements           → Movement
"""

from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base


class Product(Base):
    """Product model for inventory items."""

    __tablename__ = "products"

    # ------------------------------------------------------------------ #
    # Original fields – DO NOT change names, types, or constraints        #
    # ------------------------------------------------------------------ #
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    unit_of_measure = Column(String(20), nullable=False, default="unidad")
    unit_price = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # ------------------------------------------------------------------ #
    # Expansion 1 – Categorías                                            #
    # ------------------------------------------------------------------ #
    category_id = Column(
        Integer,
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ------------------------------------------------------------------ #
    # Expansion 2 – Marca                                                 #
    # ------------------------------------------------------------------ #
    brand = Column(String(100), nullable=True, index=True)

    # ------------------------------------------------------------------ #
    # Expansion 3 – Proveedor Default                                     #
    # ------------------------------------------------------------------ #
    default_supplier_id = Column(
        Integer,
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ------------------------------------------------------------------ #
    # Expansion 4 – Descripción Detallada                                 #
    # ------------------------------------------------------------------ #
    details = Column(Text, nullable=True)

    # ------------------------------------------------------------------ #
    # Expansion 5 – Observaciones Internas                                #
    # ------------------------------------------------------------------ #
    internal_notes = Column(Text, nullable=True)

    # ------------------------------------------------------------------ #
    # Expansion 6 – Stock Mínimo Global                                   #
    # ------------------------------------------------------------------ #
    global_min_stock = Column(Integer, nullable=True)

    # ------------------------------------------------------------------ #
    # Relationships – existing (unchanged)                                #
    # ------------------------------------------------------------------ #
    inventory_items = relationship(
        "Inventory", back_populates="product", cascade="all, delete-orphan"
    )
    movements = relationship("Movement", back_populates="product")

    # ------------------------------------------------------------------ #
    # Relationships – new                                                 #
    # ------------------------------------------------------------------ #
    category = relationship("Category", back_populates="products")

    default_supplier = relationship("Supplier", back_populates="products")

    # Self-referential many-to-many via ProductRelation (Exp 7)
    outgoing_relations = relationship(
        "ProductRelation",
        foreign_keys="ProductRelation.product_id",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    # Price audit log (Exp 8)
    price_history_entries = relationship(
        "PriceHistory",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="PriceHistory.created_at.desc()",
    )

    # ------------------------------------------------------------------ #
    # Dunder methods                                                      #
    # ------------------------------------------------------------------ #
    def __repr__(self):
        return f"<Product(id={self.id}, sku='{self.sku}', name='{self.name}')>"

    def to_dict(self):
        """Convert product to dictionary.

        New fields are included but carry None when not set so callers that
        only inspect existing keys are unaffected.
        """
        return {
            # --- original ---
            "id": self.id,
            "sku": self.sku,
            "name": self.name,
            "description": self.description,
            "unit_of_measure": self.unit_of_measure,
            "unit_price": self.unit_price,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            # --- expansions ---
            "category_id": self.category_id,
            "brand": self.brand,
            "default_supplier_id": self.default_supplier_id,
            "details": self.details,
            "internal_notes": self.internal_notes,
            "global_min_stock": self.global_min_stock,
        }

    def to_dict_full(self):
        """Extended dict that embeds related objects when already loaded."""
        data = self.to_dict()
        data["category"] = self.category.to_dict() if self.category else None
        data["default_supplier"] = (
            self.default_supplier.to_dict() if self.default_supplier else None
        )
        return data
