"""
SavedReport model for persisting report configurations.

Allows users to save a named report (type + parameters) so they can
reload it later without re-entering all filters.

Fields:
    id           – PK
    name         – Human-readable label (max 100 chars)
    report_type  – One of the known report type identifiers
    parameters   – JSON-encoded dict with: branch_id, date_from, date_to,
                   product_id, user_id, and any report-specific extras
    created_by   – FK → users(id), nullable (survives user deletion)
    created_at   – Timestamp set on INSERT
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base


class SavedReport(Base):
    """Persisted report configuration created by a user."""

    __tablename__ = "saved_reports"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    report_type = Column(String(50), nullable=False, index=True)

    # JSON string: {"branch_id": 1, "date_from": "2024-01-01", ...}
    parameters = Column(Text, nullable=True)

    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship – read-only, no cascade needed
    creator = relationship("User", foreign_keys=[created_by], lazy="select")

    def __repr__(self):
        return (
            f"<SavedReport(id={self.id}, name='{self.name}', "
            f"type='{self.report_type}', created_by={self.created_by})>"
        )

    def to_dict(self):
        """Serialize to dictionary (parameters stays as raw JSON string)."""
        return {
            "id": self.id,
            "name": self.name,
            "report_type": self.report_type,
            "parameters": self.parameters,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
