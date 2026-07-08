import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.database import Base
from modules.reports.service import ReportsService


def test_optional_reports_return_empty_results_when_tables_are_missing():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        service = ReportsService(db)
        report = service.generate_count_session_report()

        assert report["summary"]["total_sessions"] == 0
        assert report["sessions"] == []
        assert report["summary"]["total_items_counted"] == 0
    finally:
        db.close()
