import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from models.branch import Branch
from models.user import User
from modules.user.service import UserService


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


def make_user(session, name, email, role="empleado", assigned_branch_id=None):
    user = User(name=name, email=email, role=role, assigned_branch_id=assigned_branch_id)
    user.set_password("password123")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_create_user_requires_role_and_branch_for_employees(db_session):
    admin = make_user(db_session, "Admin", "admin@test.com", role="admin")
    service = UserService(db_session)

    with pytest.raises(ValueError, match="rol"):
        service.create_user({"name": "Empleado", "email": "emp@test.com"}, "password123", admin)


def test_update_user_rejects_role_changes(db_session):
    user = make_user(db_session, "Empleado", "empleado@test.com", role="empleado")
    service = UserService(db_session)

    with pytest.raises(ValueError, match="no se puede cambiar"):
        service.update_user(user.id, {"role": "gerente"})
