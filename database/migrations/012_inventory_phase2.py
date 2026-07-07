"""
Migration 012 – Inventory Phase 2 expansions.

- inventory_batches table
- Hierarchical location columns on inventory (aisle, shelf, level, bin)
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


_LOCATION_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("aisle", "VARCHAR(20)"),
    ("shelf", "VARCHAR(20)"),
    ("level", "VARCHAR(10)"),
    ("bin", "VARCHAR(20)"),
)


def upgrade(connection) -> None:
    cursor = connection.cursor()

    if not _table_exists(cursor, "inventory_batches"):
        cursor.execute('''
            CREATE TABLE inventory_batches (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                inventory_id        INTEGER NOT NULL
                                        REFERENCES inventory(id) ON DELETE CASCADE,
                batch_number        VARCHAR(50),
                manufacturing_date  DATE,
                expiration_date     DATE,
                quantity            INTEGER NOT NULL DEFAULT 0,
                unit_cost           REAL,
                notes               TEXT,
                created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(inventory_id, batch_number)
            )
        ''')
        print("Migration 012: table 'inventory_batches' created.")
    else:
        print("Migration 012: table 'inventory_batches' already exists (skipped).")

    for col_name, col_def in _LOCATION_COLUMNS:
        if _column_exists(cursor, "inventory", col_name):
            continue
        try:
            cursor.execute(f"ALTER TABLE inventory ADD COLUMN {col_name} {col_def}")
            print(f"Migration 012: added inventory.{col_name}")
        except Exception as exc:
            print(f"  WARNING: Could not add column 'inventory.{col_name}': {exc}")

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_inventory_batches_inventory "
        "ON inventory_batches(inventory_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_inventory_batches_expiration "
        "ON inventory_batches(expiration_date)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_inventory_aisle "
        "ON inventory(branch_id, aisle)"
    )

    connection.commit()
    print("Migration 012 applied.")


def downgrade(connection) -> None:
    cursor = connection.cursor()
    cursor.execute("DROP TABLE IF EXISTS inventory_batches")
    connection.commit()
    print("Migration 012 rolled back (batches table dropped).")


if __name__ == "__main__":
    import sys
    import sqlite3

    if len(sys.argv) < 2:
        print("Usage: python 012_inventory_phase2.py <path_to_db> [--downgrade]")
        sys.exit(1)

    conn = sqlite3.connect(sys.argv[1])
    if "--downgrade" in sys.argv:
        downgrade(conn)
    else:
        upgrade(conn)
    conn.close()
