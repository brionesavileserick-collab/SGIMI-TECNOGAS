"""
Supplier model for default product supplier reference.

Expansion 3 - Proveedor Default: simple supplier registry.
Not a full procurement module; just a reference attached to products.
All contact fields are nullable for backwards compatibility.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base


class Supplier(Base):
    """Supplier model – a named entity that can be linked to products."""

    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), unique=True, nullable=False, index=True)
    contact_name = Column(String(100), nullable=True)
    phone = Column(String(30), nullable=True)
    email = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    products = relationship("Product", back_populates="default_supplier")

    def __repr__(self):
        return f"<Supplier(id={self.id}, name='{self.name}')>"

    def to_dict(self):
        """Convert supplier to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "contact_name": self.contact_name,
            "phone": self.phone,
            "email": self.email,
            "notes": self.notes,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
