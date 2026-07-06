"""
History service layer - Records all events for traceability.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from sqlalchemy.sql import func
from core.database import Base
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class HistoryEntry(Base):
    """History model for storing event records."""

    __tablename__ = "history"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(50), nullable=True)  # product, movement, inventory, alert
    entity_id = Column(Integer, nullable=True)
    user_id = Column(Integer, nullable=True)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)  # JSON string with full event data
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    def to_dict(self):
        """Convert history entry to dictionary."""
        details = None
        if self.details:
            try:
                details = json.loads(self.details)
            except:
                details = self.details

        return {
            "id": self.id,
            "event_type": self.event_type,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "user_id": self.user_id,
            "action": self.action,
            "details": details,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class HistoryService:
    """Service for history/audit trail management."""

    def __init__(self, db: Session):
        self.db = db

    def record_event(self, event_type: str, entity_type: str = None,
                     entity_id: int = None, user_id: int = None,
                     action: str = None, details: Dict[str, Any] = None) -> Dict[str, Any]:
        """Record an event in history."""
        entry = HistoryEntry(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            action=action or event_type,
            details=json.dumps(details) if details else None
        )

        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)

        logger.info(f"History recorded: {event_type}")
        return entry.to_dict()

    def get_entry(self, entry_id: int) -> Optional[Dict[str, Any]]:
        """Get history entry by ID."""
        entry = self.db.query(HistoryEntry).filter(HistoryEntry.id == entry_id).first()
        return entry.to_dict() if entry else None

    def list_history(self, skip: int = 0, limit: int = 100,
                     event_type: str = None,
                     entity_type: str = None,
                     entity_id: int = None,
                     user_id: int = None,
                     date_from: datetime = None,
                     date_to: datetime = None) -> Dict[str, Any]:
        """List history entries with filtering."""
        query = self.db.query(HistoryEntry)

        if event_type:
            query = query.filter(HistoryEntry.event_type == event_type)

        if entity_type:
            query = query.filter(HistoryEntry.entity_type == entity_type)

        if entity_id:
            query = query.filter(HistoryEntry.entity_id == entity_id)

        if user_id:
            query = query.filter(HistoryEntry.user_id == user_id)

        if date_from:
            query = query.filter(HistoryEntry.created_at >= date_from)

        if date_to:
            query = query.filter(HistoryEntry.created_at <= date_to)

        total = query.count()
        entries = query.order_by(HistoryEntry.created_at.desc()).offset(skip).limit(limit).all()

        return {
            "entries": [e.to_dict() for e in entries],
            "total": total,
            "skip": skip,
            "limit": limit
        }

    def get_entity_history(self, entity_type: str, entity_id: int) -> List[Dict[str, Any]]:
        """Get complete history for an entity."""
        entries = self.db.query(HistoryEntry).filter(
            HistoryEntry.entity_type == entity_type,
            HistoryEntry.entity_id == entity_id
        ).order_by(HistoryEntry.created_at.desc()).all()

        return [e.to_dict() for e in entries]

    def search_history(self, search_term: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search history entries."""
        entries = self.db.query(HistoryEntry).filter(
            HistoryEntry.action.ilike(f"%{search_term}%")
        ).order_by(HistoryEntry.created_at.desc()).limit(limit).all()

        return [e.to_dict() for e in entries]

    def get_user_activity(self, user_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get activity history for a user."""
        entries = self.db.query(HistoryEntry).filter(
            HistoryEntry.user_id == user_id
        ).order_by(HistoryEntry.created_at.desc()).limit(limit).all()

        return [e.to_dict() for e in entries]

    def clear_old_history(self, days: int = 90) -> int:
        """Clear history entries older than specified days."""
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)

        count = self.db.query(HistoryEntry).filter(
            HistoryEntry.created_at < cutoff
        ).delete()

        self.db.commit()
        logger.info(f"Cleared {count} old history entries")
        return count
