"""
InventoryHistory model - Expansión 7: Historial de cambios de stock para auditoría.
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base


class InventoryHistory(Base):
    """
    Registro inmutable de cada cambio de stock en el inventario.
    Solo se crean registros; nunca se modifican ni eliminan en el flujo normal.
    """

    __tablename__ = "inventory_history"

    id = Column(Integer, primary_key=True, index=True)
    inventory_id = Column(
        Integer,
        ForeignKey("inventory.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Valores anteriores y nuevos para auditoría completa
    previous_physical = Column(Integer, nullable=False, default=0)
    new_physical = Column(Integer, nullable=False, default=0)
    previous_digital = Column(Integer, nullable=False, default=0)
    new_digital = Column(Integer, nullable=False, default=0)

    # Tipo de cambio: "count", "movement", "transfer", "adjustment"
    change_type = Column(String(30), nullable=False)

    # Referencia opcional al movimiento que originó el cambio
    movement_id = Column(Integer, nullable=True)

    # Razón o notas del cambio
    reason = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    inventory = relationship("Inventory", back_populates="history")

    def __repr__(self):
        return (
            f"<InventoryHistory(id={self.id}, inventory_id={self.inventory_id}, "
            f"type={self.change_type}, phys {self.previous_physical}->{self.new_physical}, "
            f"dig {self.previous_digital}->{self.new_digital})>"
        )

    @property
    def physical_delta(self) -> int:
        """Net change in physical stock."""
        return self.new_physical - self.previous_physical

    @property
    def digital_delta(self) -> int:
        """Net change in digital stock."""
        return self.new_digital - self.previous_digital

    @property
    def introduced_discrepancy(self) -> bool:
        """True if this change created or increased a discrepancy."""
        prev_diff = abs(self.previous_physical - self.previous_digital)
        new_diff = abs(self.new_physical - self.new_digital)
        return new_diff > prev_diff

    def to_dict(self):
        """Convert history record to dictionary."""
        return {
            "id": self.id,
            "inventory_id": self.inventory_id,
            "previous_physical": self.previous_physical,
            "new_physical": self.new_physical,
            "previous_digital": self.previous_digital,
            "new_digital": self.new_digital,
            "physical_delta": self.physical_delta,
            "digital_delta": self.digital_delta,
            "introduced_discrepancy": self.introduced_discrepancy,
            "change_type": self.change_type,
            "movement_id": self.movement_id,
            "reason": self.reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
