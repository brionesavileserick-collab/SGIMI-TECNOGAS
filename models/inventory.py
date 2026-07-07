"""
Inventory model for tracking stock levels per branch.
"""

from sqlalchemy import Column, Integer, Float, String, Text, DateTime, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base


class Inventory(Base):
    """Inventory model for stock tracking per branch."""

    __tablename__ = "inventory"
    __table_args__ = (
        UniqueConstraint("product_id", "branch_id", name="uq_inventory_product_branch"),
    )

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

    # --- Expansión 1: Ubicación física ---
    # Ejemplo: "Pasillo 3, Anaquel B", "Bodega principal", "Refrigerador 2"
    location = Column(String(100), nullable=True)

    # --- Expansión 2: Notas en conteos ---
    # Notas del último conteo físico registrado
    last_count_notes = Column(Text, nullable=True)

    # --- Expansión 3: Tags / categorías custom ---
    # Lista separada por comas: "fragil,alta-rotacion,perecedero"
    tags = Column(String(255), nullable=True)

    # --- Expansión 4: Prioridad de reposición ---
    # Valores: "urgente", "normal", "bajo"
    reorder_priority = Column(String(20), default="normal", nullable=False)

    # --- Expansión 5: Alertas personalizadas por item ---
    # Si es NULL se usan los umbrales globales o los del modelo base
    critical_stock_threshold = Column(Integer, nullable=True)
    max_stock_threshold = Column(Integer, nullable=True)
    discrepancy_tolerance = Column(Integer, default=0, nullable=False)

    # --- Expansión 6: Stock en tránsito ---
    # Cantidad en camino hacia esta sucursal (aún no recibida)
    in_transit_quantity = Column(Integer, default=0, nullable=False)

    # --- Expansión 8: Valor de inventario ---
    # Costo unitario local; puede diferir por sucursal
    unit_cost = Column(Float, nullable=True)

    # Relationships
    product = relationship("Product", back_populates="inventory_items")
    branch = relationship("Branch", back_populates="inventory_items")
    history = relationship("InventoryHistory", back_populates="inventory", cascade="all, delete-orphan")

    def __repr__(self):
        return (
            f"<Inventory(id={self.id}, product_id={self.product_id}, "
            f"branch_id={self.branch_id}, physical={self.physical_stock}, "
            f"digital={self.digital_stock})>"
        )

    # ------------------------------------------------------------------
    # Computed properties (retrocompatibles con el código existente)
    # ------------------------------------------------------------------

    @property
    def difference(self) -> int:
        """Difference between physical and digital stock."""
        return self.physical_stock - self.digital_stock

    @property
    def has_discrepancy(self) -> bool:
        """True when |difference| exceeds discrepancy_tolerance."""
        return abs(self.difference) > (self.discrepancy_tolerance or 0)

    @property
    def is_low_stock(self) -> bool:
        """True when digital stock is at or below min_stock."""
        return self.digital_stock <= self.min_stock

    @property
    def is_critical_stock(self) -> bool:
        """True when digital stock is at or below critical_stock_threshold (if set)."""
        if self.critical_stock_threshold is None:
            return False
        return self.digital_stock <= self.critical_stock_threshold

    @property
    def is_exceeding_max(self) -> bool:
        """True when digital stock exceeds max_stock_threshold (if set)."""
        if self.max_stock_threshold is None:
            return False
        return self.digital_stock > self.max_stock_threshold

    @property
    def available_stock(self) -> int:
        """Digital stock minus in-transit quantity already counted."""
        return self.digital_stock - (self.in_transit_quantity or 0)

    @property
    def inventory_value(self) -> float:
        """Total value of this inventory item (digital_stock * unit_cost)."""
        if self.unit_cost is None:
            return 0.0
        return self.digital_stock * self.unit_cost

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
            "is_critical_stock": self.is_critical_stock,
            "is_exceeding_max": self.is_exceeding_max,
            "available_stock": self.available_stock,
            "inventory_value": self.inventory_value,
            "min_stock": self.min_stock,
            "max_stock": self.max_stock,
            "last_count_date": self.last_count_date.isoformat() if self.last_count_date else None,
            "is_active": self.is_active,
            # Expansión 1
            "location": self.location,
            # Expansión 2
            "last_count_notes": self.last_count_notes,
            # Expansión 3
            "tags": self.tags,
            # Expansión 4
            "reorder_priority": self.reorder_priority,
            # Expansión 5
            "critical_stock_threshold": self.critical_stock_threshold,
            "max_stock_threshold": self.max_stock_threshold,
            "discrepancy_tolerance": self.discrepancy_tolerance,
            # Expansión 6
            "in_transit_quantity": self.in_transit_quantity,
            # Expansión 8
            "unit_cost": self.unit_cost,
            # Timestamps
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
