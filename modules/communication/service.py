"""Service layer for communications."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.event_bus import event_bus
from core.settings import settings
from models.user import User
from .models import Communication, CommunicationAttachment, CommunicationRecipient, CommunicationTemplate

_MISSING_RECIPIENT_ERROR = "Destinatario no encontrado"
from .repository import CommunicationRepository

logger = logging.getLogger(__name__)


class CommunicationService:
    """Service for message lifecycle and basic operations."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = CommunicationRepository(db)

    def send_message(
        self,
        sender_id: int,
        subject: str,
        body: str,
        recipients: Optional[List[int]] = None,
        priority: str = "normal",
        communication_type: str = "mensaje",
        related_ids: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        related_ids = related_ids or {}
        sender = self.db.query(User).filter(User.id == sender_id).first()
        if not sender:
            raise ValueError("Remitente no encontrado")

        recipient_ids = recipients or []
        communication = self.repository.create_communication({
            "subject": subject,
            "body": body,
            "communication_type": communication_type,
            "priority": priority,
            "sender_id": sender_id,
            "sender_branch_id": None,
            "related_movement_id": related_ids.get("related_movement_id"),
            "related_alert_id": related_ids.get("related_alert_id"),
            "is_system": False,
            "parent_message_id": related_ids.get("parent_message_id"),
            "confirmation_required": related_ids.get("confirmation_required", False),
        })

        for recipient_id in recipient_ids:
            if self.db.query(User).filter(User.id == recipient_id).first():
                self.repository.add_recipient(communication["id"], {
                    "recipient_id": recipient_id,
                    "recipient_branch_id": None,
                    "status": "pendiente",
                })

        event_bus.emit(settings.Events.COMMUNICATION_SENT, {
            "communication_id": communication["id"],
            "sender_id": sender_id,
            "recipient_ids": recipient_ids,
            "communication_type": communication_type,
        })
        return communication

    def send_announcement(self, sender_id: int, subject: str, body: str, priority: str = "normal", branch_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        sender = self.db.query(User).filter(User.id == sender_id).first()
        if not sender:
            raise ValueError("Remitente no encontrado")

        communication = self.repository.create_communication({
            "subject": subject,
            "body": body,
            "communication_type": "anuncio",
            "priority": priority,
            "sender_id": sender_id,
            "sender_branch_id": None,
            "related_movement_id": None,
            "related_alert_id": None,
            "is_system": False,
            "parent_message_id": None,
            "confirmation_required": False,
        })

        if branch_ids is None:
            users = self.db.query(User).filter(User.is_active.is_(True)).all()
            recipient_ids = [user.id for user in users]
        else:
            recipient_ids = []
        for recipient_id in recipient_ids:
            self.repository.add_recipient(communication["id"], {
                "recipient_id": recipient_id,
                "recipient_branch_id": None,
                "status": "pendiente",
            })

        event_bus.emit(settings.Events.ANNOUNCEMENT_BROADCAST, {
            "communication_id": communication["id"],
            "sender_id": sender_id,
            "branch_ids": branch_ids,
        })
        return communication

    def get_inbox(self, user_id: int, branch_id: Optional[int], page: int, filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        rows = self.repository.get_communications_by_recipient(user_id, branch_id, filters)
        start = (page - 1) * 20
        end = start + 20
        return {"items": rows[start:end], "total": len(rows)}

    def get_sent_items(self, user_id: int, page: int, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        rows = self.repository.get_communications_by_sender(user_id, None, filters)
        start = (page - 1) * 20
        end = start + 20
        return {"items": rows[start:end], "total": len(rows)}

    def mark_as_read(self, communication_id: int, user_id: int) -> Dict[str, Any]:
        recipient_row = self.db.query(CommunicationRecipient).filter(
            CommunicationRecipient.communication_id == communication_id,
            CommunicationRecipient.recipient_id == user_id,
        ).first()
        if not recipient_row:
            raise ValueError("Destinatario no encontrado")
        updated = self.repository.mark_as_read(recipient_row.id)
        event_bus.emit(settings.Events.COMMUNICATION_READ, {"communication_id": communication_id, "user_id": user_id})
        return updated or {}

    def mark_all_read(self, user_id: int, communication_ids: List[int]) -> List[Dict[str, Any]]:
        return self.repository.mark_all_read(user_id, communication_ids)

    def reply_to_message(self, communication_id: int, user_id: int, body: str, priority: str = "normal") -> Dict[str, Any]:
        original = self.repository.get_communication_by_id(communication_id)
        if not original:
            raise ValueError("Mensaje no encontrado")
        reply = self.send_message(
            sender_id=user_id,
            subject=f"Re: {original['subject']}",
            body=body,
            recipients=[original["sender_id"]] if original.get("sender_id") else [],
            priority=priority,
            communication_type="mensaje",
            related_ids={"parent_message_id": communication_id},
        )
        event_bus.emit(settings.Events.COMMUNICATION_REPLY, {"communication_id": communication_id, "reply_id": reply["id"]})
        return reply

    def forward_message(self, communication_id: int, user_id: int, new_recipients: Optional[List[int]] = None) -> Dict[str, Any]:
        original = self.repository.get_communication_by_id(communication_id)
        if not original:
            raise ValueError("Mensaje no encontrado")
        forwarded = self.send_message(
            sender_id=user_id,
            subject=f"Fwd: {original['subject']}",
            body=original["body"],
            recipients=new_recipients or [],
            priority=original.get("priority", "normal"),
            communication_type=original.get("communication_type", "mensaje"),
            related_ids={"parent_message_id": communication_id},
        )
        return forwarded

    def archive_message(self, communication_id: int, user_id: int) -> Dict[str, Any]:
        recipient_row = self.db.query(CommunicationRecipient).filter(
            CommunicationRecipient.communication_id == communication_id,
            CommunicationRecipient.recipient_id == user_id,
        ).first()
        if not recipient_row:
            raise ValueError("Destinatario no encontrado")
        recipient_row.status = "archivado"
        recipient_row.archived_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(recipient_row)
        event_bus.emit(settings.Events.COMMUNICATION_ARCHIVED, {"communication_id": communication_id, "user_id": user_id})
        return recipient_row.to_dict()

    def get_message_with_context(self, communication_id: int) -> Optional[Dict[str, Any]]:
        communication = self.repository.get_communication_by_id(communication_id)
        if not communication:
            return None
        communication["recipients"] = self.repository.get_recipients_by_communication(communication_id)
        return communication

    def search_messages(self, query: str, user_id: int, date_from: Optional[datetime] = None, date_to: Optional[datetime] = None, communication_type: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.repository.search_communications(query, user_id, {"communication_type": communication_type})

    def get_unread_count(self, user_id: int) -> int:
        rows = self.db.query(CommunicationRecipient).filter(
            CommunicationRecipient.recipient_id == user_id,
            CommunicationRecipient.status != "leido",
        ).all()
        return len(rows)

    def get_pending_confirmations(self, user_id: int) -> List[Dict[str, Any]]:
        return self.repository.get_pending_confirmations(user_id)

    def confirm_message_receipt(self, communication_id: int, user_id: int, notes: Optional[str] = None) -> Dict[str, Any]:
        recipient_row = self.db.query(CommunicationRecipient).filter(
            CommunicationRecipient.communication_id == communication_id,
            CommunicationRecipient.recipient_id == user_id,
        ).first()
        if not recipient_row:
            raise ValueError("Destinatario no encontrado")
        updated = self.repository.confirm_receipt(recipient_row.id, {"notes": notes})
        event_bus.emit(settings.Events.COMMUNICATION_CONFIRMATION_RECEIVED, {"communication_id": communication_id, "user_id": user_id})
        return updated or {}

    def get_templates(self, communication_type: Optional[str] = None) -> List[Dict[str, Any]]:
        query = self.db.query(CommunicationTemplate).filter(CommunicationTemplate.is_active.is_(True))
        if communication_type:
            query = query.filter(CommunicationTemplate.communication_type == communication_type)
        return [template.to_dict() for template in query.order_by(CommunicationTemplate.name.asc()).all()]

    def create_template(self, name: str, subject_template: Optional[str], body_template: str, communication_type: Optional[str] = None) -> Dict[str, Any]:
        template = CommunicationTemplate(name=name, subject_template=subject_template, body_template=body_template, communication_type=communication_type)
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template.to_dict()

    def use_template(self, template_id: int, substitutions: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        template = self.db.query(CommunicationTemplate).filter(CommunicationTemplate.id == template_id).first()
        if not template:
            raise ValueError("Plantilla no encontrada")
        substitutions = substitutions or {}
        subject = template.subject_template or ""
        body = template.body_template or ""
        for key, value in substitutions.items():
            subject = subject.replace("{" + key + "}", str(value))
            body = body.replace("{" + key + "}", str(value))
        return {"subject": subject, "body": body, "communication_type": template.communication_type}

    def get_common_templates(self) -> List[Dict[str, Any]]:
        return self.get_templates()

    def add_attachment(self, communication_id: int, filename: str, file_path: str, file_size: Optional[int] = None, mime_type: Optional[str] = None) -> Dict[str, Any]:
        attachment = CommunicationAttachment(
            communication_id=communication_id,
            filename=filename,
            file_path=file_path,
            file_size=file_size,
            mime_type=mime_type,
        )
        self.db.add(attachment)
        self.db.commit()
        self.db.refresh(attachment)
        return attachment.to_dict()
