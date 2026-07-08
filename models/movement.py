"""
Movement model for inventory transactions.

Expansiones incluidas (todas retrocompatibles, campos nullable o con default):
  Exp 1 - Cancelación y reversión  : cancelled_at, cancelled_by, cancellation_reason, is_cancelled
  Exp 2 - Confirmación de recepción: received_at, received_by, received_notes, is_received
  Exp 3 - Prioridad / urgencia     : priority
  Exp 4 - Origen del movimiento    : source
  Exp 5 - Documento de referencia  : reference_number, reference_type
  Exp 6 - Costo en el momento      : unit_cost, total_cost
  Exp 8 - Confirmación física      : receiver_name, receiver_signature
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base
import enum


class MovementType(str, enum.Enum):
    """Movement type enumeration."""
    ENTRADA = "entrada"
    SALIDA = "salida"
    AJUSTE = "ajuste"
    TRANSFERENCIA = "transferencia"


class MovementState(str, enum.Enum):
    """Movement state enumeration."""
    PENDIENTE = "pendiente"
    VALIDADO = "validado"
    RECHAZADO = "rechazado"


class MovementPriority(str, enum.Enum):
    """Movement priority levels."""
    BAJA = "baja"
    NORMAL = "normal"
    ALTA = "alta"
    URGENTE = "urgente"


class MovementSource(str, enum.Enum):
    """Origin source of the movement."""
    APP = "app"
    WEB = "web"
    IMPORT = "import"
    API = "api"
    SYSTEM = "system"
    SCHEDULED = "scheduled"


class Movement(Base):
    """Movement model for inventory transactions."""

    __tablename__ = "movements"

    # ------------------------------------------------------------------
    # Core fields (original)
    # ------------------------------------------------------------------
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id = Column(Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False, index=True)
    destination_branch_id = Column(Integer, ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    movement_type = Column(String(20), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    state = Column(String(20), default="pendiente", nullable=False, index=True)
    reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)
    validated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # ------------------------------------------------------------------
    # Expansión 1 – Cancelación y reversión
    # ------------------------------------------------------------------
    is_cancelled = Column(Boolean, default=False, nullable=False)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    # Referencia al movimiento original si este es un movimiento compensatorio
    reversal_of_movement_id = Column(Integer, ForeignKey("movements.id", ondelete="SET NULL"), nullable=True)

    # ------------------------------------------------------------------
    # Expansión 2 – Confirmación de recepción en transferencias
    # ------------------------------------------------------------------
    is_received = Column(Boolean, default=False, nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=True)
    received_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    received_notes = Column(Text, nullable=True)

    # ------------------------------------------------------------------
    # Expansión 3 – Prioridad / urgencia
    # ------------------------------------------------------------------
    priority = Column(String(20), default="normal", nullable=False)

    # ------------------------------------------------------------------
    # Expansión 4 – Origen del movimiento
    # ------------------------------------------------------------------
    source = Column(String(50), default="app", nullable=True)

    # ------------------------------------------------------------------
    # Expansión 5 – Documento de referencia
    # ------------------------------------------------------------------
    reference_number = Column(String(100), nullable=True)
    reference_type = Column(String(50), nullable=True)

    # ------------------------------------------------------------------
    # Expansión 6 – Costo en el momento del movimiento
    # ------------------------------------------------------------------
    unit_cost = Column(Float, nullable=True)
    total_cost = Column(Float, nullable=True)

    # ------------------------------------------------------------------
    # Expansión 8 – Confirmación física / recepción
    # ------------------------------------------------------------------
    receiver_name = Column(String(100), nullable=True)
    receiver_signature = Column(Text, nullable=True)

    # ------------------------------------------------------------------
    # Expansión 9 – Aprobaciones y programación
    # ------------------------------------------------------------------
    approval_level = Column(String(20), default="none", nullable=False, index=True)
    admin_approved = Column(Boolean, default=False, nullable=False)
    admin_approved_at = Column(DateTime(timezone=True), nullable=True)
    admin_approved_by = Column(String(100), nullable=True)
    manager_approved = Column(Boolean, default=False, nullable=False)
    manager_approved_at = Column(DateTime(timezone=True), nullable=True)
    manager_approved_by = Column(String(100), nullable=True)
    requires_approval = Column(Boolean, default=False, nullable=False, index=True)
    scheduled_date = Column(DateTime(timezone=True), nullable=True)
    is_scheduled = Column(Boolean, default=False, nullable=False, index=True)
    estimated_transit_days = Column(Integer, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    expected_arrival = Column(DateTime(timezone=True), nullable=True)
    actual_transit_days = Column(Integer, nullable=True)
    source_batch_id = Column(Integer, ForeignKey("inventory_batches.id", ondelete="SET NULL"), nullable=True)

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    product = relationship("Product", back_populates="movements")
    source_batch = relationship("InventoryBatch", foreign_keys=[source_batch_id])
    branch = relationship("Branch", foreign_keys=[branch_id])
    destination_branch = relationship("Branch", foreign_keys=[destination_branch_id])
    user = relationship("User", foreign_keys=[user_id])
    validator = relationship("User", foreign_keys=[validated_by])
    canceller = relationship("User", foreign_keys=[cancelled_by])
    receiver = relationship("User", foreign_keys=[received_by])
    reversal_of = relationship("Movement", foreign_keys=[reversal_of_movement_id], remote_side="Movement.id")
    state_history = relationship("MovementStateHistory", back_populates="movement",
                                 cascade="all, delete-orphan", order_by="MovementStateHistory.created_at")

    def __repr__(self):
        return (
            f"<Movement(id={self.id}, type='{self.movement_type}', "
            f"state='{self.state}', quantity={self.quantity}, "
            f"priority='{self.priority}', cancelled={self.is_cancelled})>"
        )

    def to_dict(self):
        """Convert movement to dictionary."""
        return {
            # Core
            "id": self.id,
            "product_id": self.product_id,
            "branch_id": self.branch_id,
            "destination_branch_id": self.destination_branch_id,
            "user_id": self.user_id,
            "movement_type": self.movement_type,
            "quantity": self.quantity,
            "state": self.state,
            "reason": self.reason,
            "notes": self.notes,
            "validated_at": self.validated_at.isoformat() if self.validated_at else None,
            "validated_by": self.validated_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            # Exp 1 – Cancelación
            "is_cancelled": self.is_cancelled,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "cancelled_by": self.cancelled_by,
            "cancellation_reason": self.cancellation_reason,
            "reversal_of_movement_id": self.reversal_of_movement_id,
            # Exp 2 – Recepción de transferencia
            "is_received": self.is_received,
            "received_at": self.received_at.isoformat() if self.received_at else None,
            "received_by": self.received_by,
            "received_notes": self.received_notes,
            # Exp 3 – Prioridad
            "priority": self.priority,
            # Exp 4 – Origen
            "source": self.source,
            # Exp 5 – Referencia externa
            "reference_number": self.reference_number,
            "reference_type": self.reference_type,
            # Exp 6 – Costos
            "unit_cost": self.unit_cost,
            "total_cost": self.total_cost,
            # Exp 8 – Recepción física
            "receiver_name": self.receiver_name,
            "receiver_signature": self.receiver_signature,
            # Expansión 9 – Aprobaciones y programación
            "approval_level": self.approval_level,
            "admin_approved": self.admin_approved,
            "admin_approved_at": self.admin_approved_at.isoformat() if self.admin_approved_at else None,
            "admin_approved_by": self.admin_approved_by,
            "manager_approved": self.manager_approved,
            "manager_approved_at": self.manager_approved_at.isoformat() if self.manager_approved_at else None,
            "manager_approved_by": self.manager_approved_by,
            "requires_approval": self.requires_approval,
            "scheduled_date": self.scheduled_date.isoformat() if self.scheduled_date else None,
            "is_scheduled": self.is_scheduled,
            "estimated_transit_days": self.estimated_transit_days,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "expected_arrival": self.expected_arrival.isoformat() if self.expected_arrival else None,
            "actual_transit_days": self.actual_transit_days,
            "source_batch_id": self.source_batch_id,
        }
