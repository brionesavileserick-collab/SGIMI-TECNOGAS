"""
Migration 002 – Branch expansions.

Adds the following columns to the ``branches`` table (all nullable or with
a safe default, so existing rows remain valid):

Expansion 1 – Geographic location
    latitude            REAL
    longitude           REAL
    zone                VARCHAR(50)
    city                VARCHAR(100)
    state               VARCHAR(100)
    country             VARCHAR(100)   DEFAULT 'México'

Expansion 2 – Branch-level inventory config
    default_min_stock   INTEGER
    default_max_stock   INTEGER
    stock_alert_enabled BOOLEAN        DEFAULT 1

Expansion 3 – Operational status
    operational_status  VARCHAR(30)    DEFAULT 'operativa'

Expansion 4 – Branch manager (FK → users.id)
    manager_user_id     INTEGER

Expansion 5 – Count frequency
    count_frequency     VARCHAR(20)

Expansion 6 – Capacity
    storage_capacity    VARCHAR(50)
    max_products        INTEGER

The migration is idempotent: each ALTER TABLE is wrapped in a try/except so
that re-running on an already-migrated database is safe.
"""

from typing import Tuple

# ---------------------------------------------------------------------------
# Column definitions: (column_name, sql_type_and_constraint)
# ---------------------------------------------------------------------------
_NEW_COLUMNS: Tuple[Tuple[str, str], ...] = (
    # Expansion 1 – Geographic location
    ("latitude",            "REAL"),
    ("longitude",           "REAL"),
    ("zone",                "VARCHAR(50)"),
    ("city",                "VARCHAR(100)"),
    ("state",               "VARCHAR(100)"),
    ("country",             "VARCHAR(100) DEFAULT 'México'"),
    # Expansion 2 – Inventory config
    ("default_min_stock",   "INTEGER"),
    ("default_max_stock",   "INTEGER"),
    ("stock_alert_enabled", "BOOLEAN DEFAULT 1"),
    # Expansion 3 – Operational status
    ("operational_status",  "VARCHAR(30) NOT NULL DEFAULT 'operativa'"),
    # Expansion 4 – Manager FK
    ("manager_user_id",     "INTEGER REFERENCES users(id) ON DELETE SET NULL"),
    # Expansion 5 – Count frequency
    ("count_frequency",     "VARCHAR(20)"),
    # Expansion 6 – Capacity
    ("storage_capacity",    "VARCHAR(50)"),
    ("max_products",        "INTEGER"),
)


def _column_exists(cursor, table: str, column: str) -> bool:
    """Return True if *column* already exists in *table* (SQLite)."""
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def upgrade(connection) -> None:
    """Add new columns to the branches table."""
    cursor = connection.cursor()
    added: list[str] = []
    skipped: list[str] = []

    for col_name, col_def in _NEW_COLUMNS:
        if _column_exists(cursor, "branches", col_name):
            skipped.append(col_name)
            continue

        try:
            cursor.execute(
                f"ALTER TABLE branches ADD COLUMN {col_name} {col_def}"
            )
            added.append(col_name)
        except Exception as exc:
            # Safety net: log and continue so one bad column doesn't abort all
            print(f"  WARNING: Could not add column '{col_name}': {exc}")

    # Create index on manager_user_id for faster FK lookups
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_branches_manager_user "
        "ON branches(manager_user_id)"
    )

    # Create index on operational_status for status-filtered queries
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_branches_operational_status "
        "ON branches(operational_status)"
    )

    # Create index on zone for geographic grouping
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_branches_zone "
        "ON branches(zone)"
    )

    connection.commit()

    if added:
        print(f"Migration 002 applied. Columns added: {', '.join(added)}.")
    if skipped:
        print(f"Migration 002: columns already present (skipped): {', '.join(skipped)}.")
    if not added and not skipped:
        print("Migration 002: nothing to do.")


def downgrade(connection) -> None:
    """
    SQLite does not support DROP COLUMN on older versions.
    This downgrade recreates the branches table without the expansion columns.
    Existing data in original columns is preserved.
    """
    cursor = connection.cursor()

    # 1. Rename current table
    cursor.execute("ALTER TABLE branches RENAME TO branches_backup_002")

    # 2. Recreate original schema
    cursor.execute('''
        CREATE TABLE branches (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        VARCHAR(100) NOT NULL UNIQUE,
            address     VARCHAR(255),
            is_active   BOOLEAN DEFAULT 1,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at  DATETIME
        )
    ''')

    # 3. Copy original columns back
    cursor.execute('''
        INSERT INTO branches (id, name, address, is_active, created_at, updated_at)
        SELECT               id, name, address, is_active, created_at, updated_at
        FROM branches_backup_002
    ''')

    # 4. Restore original index
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_branches_name ON branches(name)")

    # 5. Drop backup
    cursor.execute("DROP TABLE branches_backup_002")

    connection.commit()
    print("Migration 002 rolled back. Expansion columns removed from branches.")


# ---------------------------------------------------------------------------
# CLI helper – run directly: python 002_branch_expansions.py <db_path>
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    import sqlite3

    if len(sys.argv) < 2:
        print("Usage: python 002_branch_expansions.py <path_to_db> [--downgrade]")
        sys.exit(1)

    db_path = sys.argv[1]
    conn = sqlite3.connect(db_path)

    if "--downgrade" in sys.argv:
        downgrade(conn)
    else:
        upgrade(conn)

    conn.close()
