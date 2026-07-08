import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from models.branch import Branch
from models.user import User
from modules.communication.models import CommunicationRecipient
from modules.communication.service import CommunicationService


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def create_user(session, name, email):
    user = User(name=name, email=email)
    user.set_password("password123")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_send_message_and_mark_as_read(db_session):
    sender = create_user(db_session, "Alice", "alice@test.com")
    recipient = create_user(db_session, "Bob", "bob@test.com")

    service = CommunicationService(db_session)
    message = service.send_message(
        sender_id=sender.id,
        subject="Prueba",
        body="Cuerpo de prueba",
        recipients=[recipient.id],
        priority="normal",
        communication_type="mensaje",
        related_ids={},
    )

    assert message["subject"] == "Prueba"
    assert message["communication_type"] == "mensaje"

    inbox = service.get_inbox(recipient.id, None, 1, {})
    assert inbox["total"] == 1
    assert inbox["items"][0]["subject"] == "Prueba"

    marked = service.mark_as_read(message["id"], recipient.id)
    assert marked["status"] == "leido"
    assert service.get_unread_count(recipient.id) == 0


def test_send_message_accepts_recipient_names(db_session):
    sender = create_user(db_session, "Alice", "alice2@test.com")
    recipient = create_user(db_session, "Carlos", "carlos@test.com")

    service = CommunicationService(db_session)
    service.send_message(
        sender_id=sender.id,
        subject="Hola",
        body="Mensaje a nombre",
        recipients=[recipient.name],
        priority="alta",
        communication_type="mensaje",
        related_ids={},
    )

    recipient_rows = db_session.query(CommunicationRecipient).all()
    assert len(recipient_rows) == 1
    assert recipient_rows[0].recipient_id == recipient.id


def test_send_message_accepts_branch_names(db_session):
    sender = create_user(db_session, "Alice", "alice3@test.com")
    manager = create_user(db_session, "Carlos", "carlos2@test.com")
    branch = Branch(name="Sucursal Centro", is_active=True, manager_user_id=manager.id)
    db_session.add(branch)
    db_session.commit()

    service = CommunicationService(db_session)
    service.send_message(
        sender_id=sender.id,
        subject="Hola sucursal",
        body="Mensaje a sucursal",
        recipients=[branch.name],
        priority="alta",
        communication_type="mensaje",
        related_ids={},
    )

    recipient_rows = db_session.query(CommunicationRecipient).all()
    assert len(recipient_rows) == 1
    assert recipient_rows[0].recipient_id == manager.id
