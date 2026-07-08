"""Communication module."""

from .models import Communication, CommunicationRecipient, CommunicationTemplate, CommunicationAttachment
from .service import CommunicationService

__all__ = [
    "Communication",
    "CommunicationRecipient",
    "CommunicationTemplate",
    "CommunicationAttachment",
    "CommunicationService",
]
