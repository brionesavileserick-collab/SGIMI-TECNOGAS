"""
Product model for inventory items.

Original fields preserved as-is for full backwards compatibility.

New optional fields added per expansion plan:
  Exp 1  – category_id              (FK → categories, nullable)
  Exp 2  – brand                    (String 100, nullable)
  Exp 3  – default_supplier_id      (FK → suppliers, nullable)
  Exp 4  – details                  (Text, nullable)
  Exp 5  – internal_notes           (Text, nullable)
  Exp 6  – global_min_stock         (Integer, nullable)

New expansion fields (this iteration):
  Variantes     – parent_product_id, variant_group_id, variant_attributes
  Status        – product_status, discontinued_at, replacement_product_id
  Kit           – is_kit
  Fiscal (SAT)  – sat_product_code, customs_tariff_code, country_of_origin

New relationships:
  category                → Category           (many-to-one, optional)
  default_supplier        → Supplier           (many-to-one, optional)
  outgoing_relations      → ProductRelation    (one-to-many, self-ref source)
  price_history_entries   → PriceHistory       (one-to-many)
  variants                → Product            (self-ref children)
  parent_product          → Product            (self-ref parent)
  replacement_product     → Product            (self-ref replacement)
  kit_components          → KitComponent       (one-to-many as kit)
  component_of_kits       → KitComponent       (one-to-many as component)
  change_history          → ProductChangeHistory (one-to-many)

Existing relationships untouched:
  inventory_items         → Inventory
  movements               → Movement
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
    # Variantes de Producto                                               #
    # ------------------------------------------------------------------ #
    parent_product_id = Column(
        Integer,
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    variant_group_id = Column(String(50), nullable=True, index=True)
    variant_attributes = Column(String(255), nullable=True)

    # ------------------------------------------------------------------ #
    # Status de Descontinuación                                           #
    # ------------------------------------------------------------------ #
    # Valores: "active", "discontinued", "temporarily_unavailable", "on_hold"
    product_status = Column(String(30), nullable=False, default="active")
    discontinued_at = Column(DateTime(timezone=True), nullable=True)
    replacement_product_id = Column(
        Integer,
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ------------------------------------------------------------------ #
    # Producto Kit                                                        #
    # ------------------------------------------------------------------ #
    is_kit = Column(Boolean, nullable=False, default=False)

    # ------------------------------------------------------------------ #
    # Información Fiscal (SAT México)                                     #
    # ------------------------------------------------------------------ #
    sat_product_code = Column(String(20), nullable=True)
    customs_tariff_code = Column(String(20), nullable=True)
    country_of_origin = Column(String(100), nullable=True, default="México")

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

    # Variantes – self-referential parent/children
    parent_product = relationship(
        "Product",
        foreign_keys=[parent_product_id],
        remote_side="Product.id",
        back_populates="variants",
    )
    variants = relationship(
        "Product",
        foreign_keys="Product.parent_product_id",
        back_populates="parent_product",
    )

    # Status – replacement product (self-ref)
    replacement_product = relationship(
        "Product",
        foreign_keys=[replacement_product_id],
        remote_side="Product.id",
    )

    # Kit components
    kit_components = relationship(
        "KitComponent",
        foreign_keys="KitComponent.kit_product_id",
        back_populates="kit_product",
        cascade="all, delete-orphan",
    )
    component_of_kits = relationship(
        "KitComponent",
        foreign_keys="KitComponent.component_product_id",
        back_populates="component_product",
    )

    # Product change history
    change_history = relationship(
        "ProductChangeHistory",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductChangeHistory.changed_at.desc()",
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
            # --- expansions 1-6 ---
            "category_id": self.category_id,
            "brand": self.brand,
            "default_supplier_id": self.default_supplier_id,
            "details": self.details,
            "internal_notes": self.internal_notes,
            "global_min_stock": self.global_min_stock,
            # --- variantes ---
            "parent_product_id": self.parent_product_id,
            "variant_group_id": self.variant_group_id,
            "variant_attributes": self.variant_attributes,
            # --- status ---
            "product_status": self.product_status,
            "discontinued_at": self.discontinued_at.isoformat() if self.discontinued_at else None,
            "replacement_product_id": self.replacement_product_id,
            # --- kit ---
            "is_kit": self.is_kit,
            # --- fiscal ---
            "sat_product_code": self.sat_product_code,
            "customs_tariff_code": self.customs_tariff_code,
            "country_of_origin": self.country_of_origin,
        }

    def to_dict_full(self):
        """Extended dict that embeds related objects when already loaded."""
        data = self.to_dict()
        data["category"] = self.category.to_dict() if self.category else None
        data["default_supplier"] = (
            self.default_supplier.to_dict() if self.default_supplier else None
        )
        return data
