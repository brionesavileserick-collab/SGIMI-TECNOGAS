"""
Migration 013 – Inventory Phase 3 expansions.

- alternate_unit, conversion_factor on inventory
"""

from typing import Tuple


def _column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


_UNIT_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("alternate_unit", "VARCHAR(20)"),
    ("conversion_factor", "REAL"),
)


def upgrade(connection) -> None:
    cursor = connection.cursor()

    for col_name, col_def in _UNIT_COLUMNS:
        if _column_exists(cursor, "inventory", col_name):
            continue
        try:
            cursor.execute(f"ALTER TABLE inventory ADD COLUMN {col_name} {col_def}")
            print(f"Migration 013: added inventory.{col_name}")
        except Exception as exc:
            print(f"  WARNING: Could not add column 'inventory.{col_name}': {exc}")

    connection.commit()
    print("Migration 013 applied.")


def downgrade(connection) -> None:
    print("Migration 013: no downgrade implemented (columns retained).")


if __name__ == "__main__":
    import sys
    import sqlite3

    if len(sys.argv) < 2:
        print("Usage: python 013_inventory_phase3.py <path_to_db>")
        sys.exit(1)

    conn = sqlite3.connect(sys.argv[1])
    upgrade(conn)
    conn.close()
