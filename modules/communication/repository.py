"""Repository for communication persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import or_

from .models import Communication, CommunicationRecipient


class CommunicationRepository:
    """Repository wrapper for communication records."""

    def __init__(self, db):
        self.db = db

    def create_communication(self, communication_data: Dict[str, Any]) -> Dict[str, Any]:
        communication = Communication(**communication_data)
        self.db.add(communication)
        self.db.commit()
        self.db.refresh(communication)
        return communication.to_dict()

    def get_communication_by_id(self, communication_id: int) -> Optional[Dict[str, Any]]:
        communication = self.db.query(Communication).filter(Communication.id == communication_id).first()
        return communication.to_dict() if communication else None

    def get_communications_by_sender(self, sender_id: int, branch_id: Optional[int] = None, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        query = self.db.query(Communication).filter(Communication.sender_id == sender_id)
        if branch_id is not None:
            query = query.filter(Communication.sender_branch_id == branch_id)
        if filters:
            comm_type = filters.get("communication_type")
            if comm_type:
                query = query.filter(Communication.communication_type == comm_type)
            priority = filters.get("priority")
            if priority:
                query = query.filter(Communication.priority == priority)
        return [item.to_dict() for item in query.order_by(Communication.created_at.desc()).all()]

    def get_communications_by_recipient(self, recipient_id: int, branch_id: Optional[int] = None, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        query = self.db.query(CommunicationRecipient).filter(CommunicationRecipient.recipient_id == recipient_id)
        if branch_id is not None:
            query = query.filter(CommunicationRecipient.recipient_branch_id == branch_id)
        if filters:
            status = filters.get("status")
            if status:
                query = query.filter(CommunicationRecipient.status == status)
        recipient_rows = query.order_by(CommunicationRecipient.created_at.desc()).all()
        items = []
        for row in recipient_rows:
            communication = self.db.query(Communication).filter(Communication.id == row.communication_id).first()
            if communication:
                payload = communication.to_dict()
                payload["recipient_status"] = row.status
                payload["recipient_id"] = row.id
                items.append(payload)
        return items

    def add_recipient(self, communication_id: int, recipient_data: Dict[str, Any]) -> Dict[str, Any]:
        recipient = CommunicationRecipient(communication_id=communication_id, **recipient_data)
        self.db.add(recipient)
        self.db.commit()
        self.db.refresh(recipient)
        return recipient.to_dict()

    def get_recipients_by_communication(self, communication_id: int) -> List[Dict[str, Any]]:
        rows = self.db.query(CommunicationRecipient).filter(CommunicationRecipient.communication_id == communication_id).all()
        return [row.to_dict() for row in rows]

    def update_recipient_status(self, recipient_id: int, status: str, read_at: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        row = self.db.query(CommunicationRecipient).filter(CommunicationRecipient.id == recipient_id).first()
        if not row:
            return None
        row.status = status
        if read_at is not None:
            row.read_at = read_at
        self.db.commit()
        self.db.refresh(row)
        return row.to_dict()

    def mark_as_read(self, recipient_id: int) -> Optional[Dict[str, Any]]:
        return self.update_recipient_status(recipient_id, "leido", read_at=datetime.now(timezone.utc))

    def mark_all_read(self, recipient_id: int, communication_ids: List[int]) -> List[Dict[str, Any]]:
        rows = self.db.query(CommunicationRecipient).filter(
            CommunicationRecipient.recipient_id == recipient_id,
            CommunicationRecipient.communication_id.in_(communication_ids),
        ).all()
        updated = []
        for row in rows:
            row.status = "leido"
            row.read_at = datetime.now(timezone.utc)
            updated.append(row.to_dict())
        self.db.commit()
        return updated

    def get_pending_confirmations(self, recipient_id: int) -> List[Dict[str, Any]]:
        rows = self.db.query(CommunicationRecipient).filter(
            CommunicationRecipient.recipient_id == recipient_id,
            CommunicationRecipient.confirmation_sent.is_(True),
            CommunicationRecipient.confirmation_received_at.is_(None),
        ).all()
        return [row.to_dict() for row in rows]

    def confirm_receipt(self, recipient_id: int, confirmation_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        row = self.db.query(CommunicationRecipient).filter(CommunicationRecipient.id == recipient_id).first()
        if not row:
            return None
        row.confirmation_sent = True
        row.confirmation_received_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(row)
        return row.to_dict()

    def search_communications(self, query: str, user_id: int, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        search_term = f"%{query}%"
        recipient_ids = self.db.query(CommunicationRecipient.communication_id).filter(
            CommunicationRecipient.recipient_id == user_id
        ).subquery()
        rows = self.db.query(Communication).filter(
            or_(
                Communication.sender_id == user_id,
                Communication.id.in_(recipient_ids),
            )
        ).filter(
            or_(
                Communication.subject.like(search_term),
                Communication.body.like(search_term),
            )
        )
        if filters:
            communication_type = filters.get("communication_type")
            if communication_type:
                rows = rows.filter(Communication.communication_type == communication_type)
        return [item.to_dict() for item in rows.order_by(Communication.created_at.desc()).all()]

    def get_announcements_for_branch(self, branch_id: Optional[int], include_archived: bool = False) -> List[Dict[str, Any]]:
        query = self.db.query(Communication).filter(Communication.communication_type == "anuncio")
        if branch_id is not None:
            query = query.filter(or_(Communication.sender_branch_id == branch_id, Communication.sender_branch_id.is_(None)))
        if not include_archived:
            query = query.filter(Communication.id.is_not(None))
        return [item.to_dict() for item in query.order_by(Communication.created_at.desc()).all()]

    def get_thread_messages(self, parent_message_id: int) -> List[Dict[str, Any]]:
        rows = self.db.query(Communication).filter(Communication.parent_message_id == parent_message_id).order_by(Communication.created_at.asc()).all()
        return [row.to_dict() for row in rows]
