"""
Branch model for multi-branch inventory management.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base


# ---------------------------------------------------------------------------
# Valores permitidos para campos con dominio cerrado
# ---------------------------------------------------------------------------
OPERATIONAL_STATUS_VALUES = (
    "operativa",
    "en_mantenimiento",
    "temporalmente_cerrada",
    "en_renovacion",
)

COUNT_FREQUENCY_VALUES = (
    "mensual",
    "bimestral",
    "trimestral",
    "semestral",
    "anual",
)


class Branch(Base):
    """Branch/Sucursal model for inventory locations."""

    __tablename__ = "branches"

    # ------------------------------------------------------------------
    # Campos originales
    # ------------------------------------------------------------------
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    address = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # ------------------------------------------------------------------
    # Expansión 1 – Ubicación geográfica (todos opcionales)
    # ------------------------------------------------------------------
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    zone = Column(String(50), nullable=True)       # "Norte", "Sur", "Zona Industrial", …
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True, default="México")

    # ------------------------------------------------------------------
    # Expansión 2 – Configuración de inventario por sucursal (opcional)
    # ------------------------------------------------------------------
    default_min_stock = Column(Integer, nullable=True)   # Umbral mínimo propio
    default_max_stock = Column(Integer, nullable=True)   # Umbral máximo propio
    stock_alert_enabled = Column(Boolean, default=True)  # ¿Recibe alertas de stock?

    # ------------------------------------------------------------------
    # Expansión 3 – Estado operativo (default: "operativa")
    # ------------------------------------------------------------------
    operational_status = Column(String(30), default="operativa", nullable=False)

    # ------------------------------------------------------------------
    # Expansión 4 – Responsable de sucursal (FK nullable a users)
    # ------------------------------------------------------------------
    manager_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ------------------------------------------------------------------
    # Expansión 5 – Frecuencia de conteo (opcional)
    # ------------------------------------------------------------------
    count_frequency = Column(String(20), nullable=True)  # "mensual", "bimestral", …

    # ------------------------------------------------------------------
    # Expansión 6 – Capacidad (opcional, dato informativo)
    # ------------------------------------------------------------------
    storage_capacity = Column(String(50), nullable=True)  # "chica", "mediana", "grande" o número
    max_products = Column(Integer, nullable=True)          # Máximo de SKUs que puede manejar

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------
    inventory_items = relationship(
        "Inventory", back_populates="branch", cascade="all, delete-orphan"
    )
    manager = relationship(
        "User",
        foreign_keys=[manager_user_id],
        lazy="select",
    )

    # ------------------------------------------------------------------
    def __repr__(self):
        return f"<Branch(id={self.id}, name='{self.name}', status='{self.operational_status}')>"

    def to_dict(self):
        """Convert branch to dictionary (incluye todos los campos nuevos)."""
        return {
            # Campos originales
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            # Expansión 1 – Ubicación geográfica
            "latitude": self.latitude,
            "longitude": self.longitude,
            "zone": self.zone,
            "city": self.city,
            "state": self.state,
            "country": self.country,
            # Expansión 2 – Configuración de inventario
            "default_min_stock": self.default_min_stock,
            "default_max_stock": self.default_max_stock,
            "stock_alert_enabled": self.stock_alert_enabled,
            # Expansión 3 – Estado operativo
            "operational_status": self.operational_status,
            # Expansión 4 – Responsable
            "manager_user_id": self.manager_user_id,
            # Expansión 5 – Frecuencia de conteo
            "count_frequency": self.count_frequency,
            # Expansión 6 – Capacidad
            "storage_capacity": self.storage_capacity,
            "max_products": self.max_products,
        }
