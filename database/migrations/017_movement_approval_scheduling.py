"""
Migration 017 – Movement Approval Workflow and Scheduling.

Adds columns to support:
  - Two-level approval workflow (admin → manager)
  - Movement scheduling with execution
  - Transfer tracking and estimated arrival
  - Batch tracking for movement source

Nuevo columns:
    approval_level            VARCHAR(20) DEFAULT 'none'
    admin_approved            BOOLEAN DEFAULT 0
    admin_approved_at         DATETIME
    admin_approved_by         VARCHAR(100)
    manager_approved          BOOLEAN DEFAULT 0
    manager_approved_at       DATETIME
    manager_approved_by       VARCHAR(100)
    requires_approval         BOOLEAN DEFAULT 0
    scheduled_date            DATETIME
    is_scheduled              BOOLEAN DEFAULT 0
    estimated_transit_days    INTEGER
    sent_at                   DATETIME
    expected_arrival          DATETIME
    actual_transit_days       INTEGER
    source_batch_id           INTEGER (FK → inventory_batches.id)

The migration is idempotent: each ALTER TABLE is wrapped in a check,
so re-running is always safe.
"""

from typing import Tuple


def _column_exists(cursor, table: str, column: str) -> bool:
    """Return True if *column* already exists in *table* (SQLite)."""
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def _table_exists(cursor, table: str) -> bool:
    """Return True if *table* exists in the database."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cursor.fetchone() is not None


# New columns for the ``movements`` table
_MOVEMENT_COLUMNS: Tuple[Tuple[str, str], ...] = (
    # Approval workflow (two-level)
    ("approval_level",        "VARCHAR(20) NOT NULL DEFAULT 'none'"),
    ("admin_approved",        "BOOLEAN NOT NULL DEFAULT 0"),
    ("admin_approved_at",     "DATETIME"),
    ("admin_approved_by",     "VARCHAR(100)"),
    ("manager_approved",      "BOOLEAN NOT NULL DEFAULT 0"),
    ("manager_approved_at",   "DATETIME"),
    ("manager_approved_by",   "VARCHAR(100)"),
    ("requires_approval",     "BOOLEAN NOT NULL DEFAULT 0"),
    # Scheduling
    ("scheduled_date",        "DATETIME"),
    ("is_scheduled",          "BOOLEAN NOT NULL DEFAULT 0"),
    # Transit tracking
    ("estimated_transit_days", "INTEGER"),
    ("sent_at",               "DATETIME"),
    ("expected_arrival",      "DATETIME"),
    ("actual_transit_days",   "INTEGER"),
    # Batch tracking
    ("source_batch_id",       "INTEGER REFERENCES inventory_batches(id) ON DELETE SET NULL"),
)


def upgrade(connection) -> None:
    """Apply migration 017: add approval and scheduling columns."""
    cursor = connection.cursor()

    # Add all new columns to movements table
    for column_name, column_def in _MOVEMENT_COLUMNS:
        if not _column_exists(cursor, "movements", column_name):
            cursor.execute(
                f"ALTER TABLE movements ADD COLUMN {column_name} {column_def}"
            )
            print(f"  [movements] Added column: {column_name}")
        else:
            print(f"  [movements] Column already exists (skipped): {column_name}")

    # Create indexes for new columns
    _create_index_if_missing(
        cursor,
        "idx_movements_approval_level",
        "CREATE INDEX IF NOT EXISTS idx_movements_approval_level "
        "ON movements(approval_level)",
    )
    _create_index_if_missing(
        cursor,
        "idx_movements_is_scheduled",
        "CREATE INDEX IF NOT EXISTS idx_movements_is_scheduled "
        "ON movements(is_scheduled, scheduled_date)",
    )
    _create_index_if_missing(
        cursor,
        "idx_movements_requires_approval",
        "CREATE INDEX IF NOT EXISTS idx_movements_requires_approval "
        "ON movements(requires_approval)",
    )

    connection.commit()
    print("Migration 017_movement_approval_scheduling.py applied successfully.")


def _create_index_if_missing(cursor, index_name: str, create_sql: str) -> None:
    """Execute *create_sql* only when the index does not exist yet."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
        (index_name,),
    )
    if cursor.fetchone() is None:
        cursor.execute(create_sql)
        print(f"  Created index: {index_name}")
    else:
        print(f"  Index already exists (skipped): {index_name}")


def downgrade(connection) -> None:
    """
    SQLite does not support DROP COLUMN, so the downgrade:
      - Does nothing (columns are retained for compatibility).
    The data in these columns will remain in the database but will not be used.
    """
    print("Migration 017: downgrade not implemented (columns retained for compatibility).")
    print("To fully remove these columns, manually rebuild the movements table.")


if __name__ == "__main__":
    import sqlite3

    conn = sqlite3.connect("test.db")
    upgrade(conn)
    conn.close()
