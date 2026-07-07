"""
BranchConfigHistory model – audit trail for branch configuration changes.

Records which field was changed, its previous and new values, when the change
occurred, who made it, and an optional reason.  The user identity is stored as
plain text so this table has NO dependency on the users table.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from core.database import Base


class BranchConfigHistory(Base):
    """Stores one record per field changed on a branch configuration."""

    __tablename__ = "branch_config_history"

    id = Column(Integer, primary_key=True, index=True)

    # FK to branches – nullable so logs survive branch soft-delete
    branch_id = Column(
        Integer,
        ForeignKey("branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Who made the change – stored as text; no FK to users
    changed_by = Column(String(150), nullable=True)  # name or email, plain text

    # What changed
    field_name = Column(String(50), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)

    # When and why
    changed_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    reason = Column(String(255), nullable=True)

    # ------------------------------------------------------------------
    def __repr__(self):
        return (
            f"<BranchConfigHistory(id={self.id}, branch_id={self.branch_id}, "
            f"field='{self.field_name}', changed_at={self.changed_at})>"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "branch_id": self.branch_id,
            "changed_by": self.changed_by,
            "field_name": self.field_name,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "changed_at": self.changed_at.isoformat() if self.changed_at else None,
            "reason": self.reason,
        }
