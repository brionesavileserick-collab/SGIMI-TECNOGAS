"""
Database configuration and session management.
"""

from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import logging

from core.settings import settings

logger = logging.getLogger(__name__)

# Create engine
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True
)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """Enable foreign key enforcement for SQLite connections."""
    if settings.DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Get database session.
    Yields a session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database, creating all tables and running pending migrations."""
    from models import (  # noqa: F401 – side-effects register tables with Base
        product, category, supplier, product_relation, price_history,
        branch, inventory, inventory_history, inventory_count_session,
        inventory_count_item, inventory_batch, movement, user, saved_report,
        branch_config_history,
    )
    # Dashboard widget config model (Exp 9)
    from models import dashboard_widget_config  # noqa: F401
    # Product expansion models
    from models import kit_component          # noqa: F401
    from models import product_change_history # noqa: F401
    # History models live in the service module; import to register with Base.metadata
    from modules.history import service as _history_service  # noqa: F401
    Base.metadata.create_all(bind=engine)
    if settings.DATABASE_URL.startswith("sqlite"):
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_inventory_product_branch "
                "ON inventory(product_id, branch_id)"
            )
    _run_migrations()
    logger.info("Database initialized successfully")


def _run_migrations() -> None:
    """
    Apply all pending schema migrations in order.
    Scans database/migrations/ for files matching NNN_*.py and runs upgrade()
    on each one. Each migration is idempotent, so re-running is always safe.
    """
    import sqlite3
    import importlib.util
    from pathlib import Path

    if not settings.DATABASE_URL.startswith("sqlite"):
        logger.warning("Migrations only supported for SQLite; skipping.")
        return

    # Extract the file path from the SQLite URL (sqlite:///path)
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")

    migrations_dir = Path(__file__).parent.parent / "database" / "migrations"

    # Collect and sort all numbered migration files (001_*.py, 002_*.py, …)
    migration_files = sorted(
        f for f in migrations_dir.glob("[0-9][0-9][0-9]_*.py")
    )

    for migration_file in migration_files:
        module_name = f"migration_{migration_file.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, migration_file)
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)

            conn = sqlite3.connect(db_path)
            migration.upgrade(conn)
            conn.close()
            logger.info(f"Migration applied: {migration_file.name}")
        except Exception as exc:
            logger.error(f"Migration error in {migration_file.name}: {exc}")


def drop_db() -> None:
    """Drop all tables (use with caution)."""
    Base.metadata.drop_all(bind=engine)
    logger.warning("All database tables dropped")
