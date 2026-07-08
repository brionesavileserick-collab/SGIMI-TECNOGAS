import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.database import Base
from modules.alerts.service import AlertService
from models.user import User  # noqa: F401


def test_new_alert_helpers_and_grouping():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        service = AlertService(db)
        alert = service.create_count_overdue_alert(branch_id=1, scheduled_date="2026-07-01", session_id=10)
        assert alert is not None
        assert alert["alert_type"] == "count_overdue"
        assert alert["group_key"].startswith("count_overdue")

        capacity = service.create_capacity_alert(branch_id=2, current_skus=95, max_products=100, usage_percent=95)
        assert capacity is not None
        assert capacity["alert_type"] == "capacity_critical"

        summary = service.get_alert_group_summary(capacity["group_key"])
        assert summary["count"] >= 1

        resolved = service.check_and_resolve(
            "count_overdue",
            branch_id=1,
            movement_id=10,
            context_data={"session_completed": True},
        )
        assert resolved is True
    finally:
        db.close()
