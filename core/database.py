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
    from models import product, branch, inventory, movement, user
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
    """Apply pending schema migrations in order."""
    import sqlite3
    import importlib.util
    from pathlib import Path

    if not settings.DATABASE_URL.startswith("sqlite"):
        logger.warning("Migrations only supported for SQLite; skipping.")
        return

    # Extract the file path from the SQLite URL (sqlite:///path)
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")

    migrations_dir = Path(__file__).parent.parent / "database" / "migrations"
    migration_file = migrations_dir / "002_branch_expansions.py"

    try:
        spec = importlib.util.spec_from_file_location("migration_002", migration_file)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        conn = sqlite3.connect(db_path)
        migration.upgrade(conn)
        conn.close()
    except Exception as exc:
        logger.error(f"Migration 002 error: {exc}")


def drop_db() -> None:
    """Drop all tables (use with caution)."""
    Base.metadata.drop_all(bind=engine)
    logger.warning("All database tables dropped")
