"""
DashboardWidgetConfig model – stores per-user dashboard layout preferences.

Fields:
    id          – PK
    user_id     – FK → users(id), nullable (config survives user deletion)
    widget_key  – identifier matching a known widget name in routes.py
    position    – display order (lower = higher on screen)
    is_visible  – whether the widget is shown
    config      – JSON string for widget-specific settings (period, limit, etc.)
    updated_at  – last modification timestamp
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base
import json


# Canonical set of widget keys used by DashboardWidget in routes.py.
# Used for validation and default ordering.
WIDGET_KEYS = (
    "quick_stats",
    "kpi",
    "stock_summary",
    "movements",
    "alerts",
    "transfers",
    "efficiency",
    "ranking",
    "charts",
    "recent_movements",
)

DEFAULT_POSITIONS = {key: idx for idx, key in enumerate(WIDGET_KEYS)}


class DashboardWidgetConfig(Base):
    """Per-user dashboard widget visibility and ordering configuration."""

    __tablename__ = "dashboard_widget_configs"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # One of the keys in WIDGET_KEYS
    widget_key = Column(String(50), nullable=False, index=True)

    # Display position – lower = first
    position = Column(Integer, default=0, nullable=False)

    # Whether the widget should be rendered at all
    is_visible = Column(Boolean, default=True, nullable=False)

    # Optional JSON configuration for the specific widget
    # e.g. '{"period": "this_week", "limit": 5}'
    config = Column(Text, nullable=True)

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationship – read-only reference back to the user
    user = relationship("User", foreign_keys=[user_id], lazy="select")

    def __repr__(self):
        return (
            f"<DashboardWidgetConfig("
            f"id={self.id}, user_id={self.user_id}, "
            f"widget_key='{self.widget_key}', position={self.position}, "
            f"visible={self.is_visible})>"
        )

    def get_config_dict(self) -> dict:
        """Deserialize the JSON config string into a Python dict."""
        if not self.config:
            return {}
        try:
            return json.loads(self.config)
        except (json.JSONDecodeError, TypeError):
            return {}

    def to_dict(self) -> dict:
        """Serialize to a plain dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "widget_key": self.widget_key,
            "position": self.position,
            "is_visible": self.is_visible,
            "config": self.get_config_dict(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
