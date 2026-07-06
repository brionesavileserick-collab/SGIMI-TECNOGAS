"""
Alerts service layer - Detects issues and generates alerts.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from core.database import Base
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Alert(Base):
    """Alert model for storing generated alerts."""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False)  # info, warning, critical
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    product_id = Column(Integer, nullable=True)
    branch_id = Column(Integer, nullable=True)
    movement_id = Column(Integer, nullable=True)
    is_read = Column(Boolean, default=False)
    is_resolved = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self):
        """Convert alert to dictionary."""
        return {
            "id": self.id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "product_id": self.product_id,
            "branch_id": self.branch_id,
            "movement_id": self.movement_id,
            "is_read": self.is_read,
            "is_resolved": self.is_resolved,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None
        }


class AlertService:
    """Service for alert management."""

    def __init__(self, db: Session):
        self.db = db

    def create_alert(self, alert_type: str, severity: str, title: str,
                     message: str, product_id: int = None,
                     branch_id: int = None, movement_id: int = None) -> Dict[str, Any]:
        """Create a new alert."""
        alert = Alert(
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            product_id=product_id,
            branch_id=branch_id,
            movement_id=movement_id
        )

        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)

        logger.info(f"Alert created: {title}")
        return alert.to_dict()

    def get_alert(self, alert_id: int) -> Optional[Dict[str, Any]]:
        """Get alert by ID."""
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        return alert.to_dict() if alert else None

    def list_alerts(self, skip: int = 0, limit: int = 100,
                    is_unread_only: bool = False,
                    severity: str = None,
                    alert_type: str = None) -> List[Dict[str, Any]]:
        """List alerts with filtering."""
        query = self.db.query(Alert)

        if is_unread_only:
            query = query.filter(Alert.is_read == False)

        if severity:
            query = query.filter(Alert.severity == severity)

        if alert_type:
            query = query.filter(Alert.alert_type == alert_type)

        alerts = query.order_by(Alert.created_at.desc()).offset(skip).limit(limit).all()
        return [a.to_dict() for a in alerts]

    def mark_as_read(self, alert_id: int) -> bool:
        """Mark alert as read."""
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return False

        alert.is_read = True
        self.db.commit()
        return True

    def resolve_alert(self, alert_id: int) -> bool:
        """Resolve alert."""
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return False

        alert.is_resolved = True
        alert.resolved_at = datetime.utcnow()
        self.db.commit()
        return True

    def delete_alert(self, alert_id: int) -> bool:
        """Delete alert."""
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return False

        self.db.delete(alert)
        self.db.commit()
        return True

    def get_unread_count(self) -> int:
        """Count unread alerts."""
        return self.db.query(Alert).filter(Alert.is_read == False).count()

    def get_critical_count(self) -> int:
        """Count critical unresolved alerts."""
        return self.db.query(Alert).filter(
            Alert.severity == "critical",
            Alert.is_resolved == False
        ).count()

    def clear_old_alerts(self, days: int = 30) -> int:
        """Clear alerts older than specified days."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)

        count = self.db.query(Alert).filter(
            Alert.is_resolved == True,
            Alert.created_at < cutoff
        ).delete()

        self.db.commit()
        logger.info(f"Cleared {count} old alerts")
        return count
