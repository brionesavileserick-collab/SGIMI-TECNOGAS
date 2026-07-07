"""
Migration 011 – Inventory Phase 1 expansions.

- count_session_id on inventory
- inventory_count_sessions table
- inventory_count_items table
- digital_adjustment_notes, adjusted_by_name on inventory_history
"""

from typing import Tuple


def _column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def _table_exists(cursor, table: str) -> bool:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cursor.fetchone() is not None


_INVENTORY_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("count_session_id", "INTEGER REFERENCES inventory_count_sessions(id) ON DELETE SET NULL"),
)

_HISTORY_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("digital_adjustment_notes", "TEXT"),
    ("adjusted_by_name", "VARCHAR(100)"),
)


def upgrade(connection) -> None:
    cursor = connection.cursor()

    # Create count sessions table first (inventory.count_session_id references it)
    if not _table_exists(cursor, "inventory_count_sessions"):
        cursor.execute('''
            CREATE TABLE inventory_count_sessions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                branch_id       INTEGER REFERENCES branches(id) ON DELETE SET NULL,
                scheduled_date  DATETIME NOT NULL,
                started_at      DATETIME,
                completed_at    DATETIME,
                status          VARCHAR(20) NOT NULL DEFAULT 'pending',
                notes           TEXT,
                validator_count INTEGER NOT NULL DEFAULT 1,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("Migration 011: table 'inventory_count_sessions' created.")
    else:
        print("Migration 011: table 'inventory_count_sessions' already exists (skipped).")

    if not _table_exists(cursor, "inventory_count_items"):
        cursor.execute('''
            CREATE TABLE inventory_count_items (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id        INTEGER NOT NULL
                                      REFERENCES inventory_count_sessions(id) ON DELETE CASCADE,
                inventory_id      INTEGER REFERENCES inventory(id) ON DELETE SET NULL,
                product_id        INTEGER REFERENCES products(id) ON DELETE SET NULL,
                expected_physical INTEGER NOT NULL,
                counted_physical  INTEGER,
                difference        INTEGER,
                is_discrepancy    BOOLEAN NOT NULL DEFAULT 0,
                counted_at        DATETIME,
                validator_name    VARCHAR(100),
                notes             TEXT,
                created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("Migration 011: table 'inventory_count_items' created.")
    else:
        print("Migration 011: table 'inventory_count_items' already exists (skipped).")

    for col_name, col_def in _INVENTORY_COLUMNS:
        if _column_exists(cursor, "inventory", col_name):
            continue
        try:
            cursor.execute(f"ALTER TABLE inventory ADD COLUMN {col_name} {col_def}")
            print(f"Migration 011: added inventory.{col_name}")
        except Exception as exc:
            print(f"  WARNING: Could not add column 'inventory.{col_name}': {exc}")

    for col_name, col_def in _HISTORY_COLUMNS:
        if _column_exists(cursor, "inventory_history", col_name):
            continue
        try:
            cursor.execute(f"ALTER TABLE inventory_history ADD COLUMN {col_name} {col_def}")
            print(f"Migration 011: added inventory_history.{col_name}")
        except Exception as exc:
            print(f"  WARNING: Could not add column 'inventory_history.{col_name}': {exc}")

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_count_sessions_branch "
        "ON inventory_count_sessions(branch_id, status)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_count_sessions_scheduled "
        "ON inventory_count_sessions(scheduled_date, status)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_count_items_session "
        "ON inventory_count_items(session_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_inventory_count_session "
        "ON inventory(count_session_id)"
    )

    connection.commit()
    print("Migration 011 applied.")


def downgrade(connection) -> None:
    cursor = connection.cursor()
    cursor.execute("DROP TABLE IF EXISTS inventory_count_items")
    cursor.execute("DROP TABLE IF EXISTS inventory_count_sessions")
    connection.commit()
    print("Migration 011 rolled back (count tables dropped).")


if __name__ == "__main__":
    import sys
    import sqlite3

    if len(sys.argv) < 2:
        print("Usage: python 011_inventory_phase1.py <path_to_db> [--downgrade]")
        sys.exit(1)

    conn = sqlite3.connect(sys.argv[1])
    if "--downgrade" in sys.argv:
        downgrade(conn)
    else:
        upgrade(conn)
    conn.close()
