"""Communication data models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class Communication(Base):
    """Main communication record."""

    __tablename__ = "communications"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    communication_type = Column(String(30), nullable=False, default="mensaje")
    priority = Column(String(20), nullable=False, default="normal")
    sender_id = Column(Integer, nullable=True)
    sender_branch_id = Column(Integer, nullable=True)
    related_movement_id = Column(Integer, nullable=True)
    related_alert_id = Column(Integer, nullable=True)
    is_system = Column(Boolean, nullable=False, default=False)
    parent_message_id = Column(Integer, ForeignKey("communications.id", ondelete="SET NULL"), nullable=True)
    confirmation_required = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    recipients = relationship("CommunicationRecipient", back_populates="communication", cascade="all, delete-orphan")
    attachments = relationship("CommunicationAttachment", back_populates="communication", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "subject": self.subject,
            "body": self.body,
            "communication_type": self.communication_type,
            "priority": self.priority,
            "sender_id": self.sender_id,
            "sender_branch_id": self.sender_branch_id,
            "related_movement_id": self.related_movement_id,
            "related_alert_id": self.related_alert_id,
            "is_system": self.is_system,
            "parent_message_id": self.parent_message_id,
            "confirmation_required": self.confirmation_required,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CommunicationRecipient(Base):
    """Recipient state for each communication."""

    __tablename__ = "communication_recipients"
    __table_args__ = (
        UniqueConstraint("communication_id", "recipient_id", name="uq_communication_recipient"),
    )

    id = Column(Integer, primary_key=True, index=True)
    communication_id = Column(Integer, ForeignKey("communications.id", ondelete="CASCADE"), nullable=False)
    recipient_id = Column(Integer, nullable=True)
    recipient_branch_id = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default="pendiente")
    read_at = Column(DateTime(timezone=True), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    confirmation_sent = Column(Boolean, nullable=False, default=False)
    confirmation_received_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    communication = relationship("Communication", back_populates="recipients")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "communication_id": self.communication_id,
            "recipient_id": self.recipient_id,
            "recipient_branch_id": self.recipient_branch_id,
            "status": self.status,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
            "confirmation_sent": self.confirmation_sent,
            "confirmation_received_at": self.confirmation_received_at.isoformat() if self.confirmation_received_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CommunicationAttachment(Base):
    """Simple attachment metadata for a communication."""

    __tablename__ = "communication_attachments"

    id = Column(Integer, primary_key=True, index=True)
    communication_id = Column(Integer, ForeignKey("communications.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    communication = relationship("Communication", back_populates="attachments")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "communication_id": self.communication_id,
            "filename": self.filename,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
        }


class CommunicationTemplate(Base):
    """Optional reusable templates for common messages."""

    __tablename__ = "communication_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    subject_template = Column(String(200), nullable=True)
    body_template = Column(Text, nullable=False)
    communication_type = Column(String(30), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "subject_template": self.subject_template,
            "body_template": self.body_template,
            "communication_type": self.communication_type,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
