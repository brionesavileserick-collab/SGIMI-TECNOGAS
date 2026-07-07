"""
Migration 010 – Branch Phase-2 expansions.

Adds the following columns to ``branches`` and creates the new
``branch_config_history`` table.

New columns on ``branches``
───────────────────────────
Expansion 7 – Count scheduling
    last_count_date           DATETIME
    next_scheduled_count      DATETIME
    count_enabled             BOOLEAN   DEFAULT 1

Expansion 8 – Contact information
    contact_phone             VARCHAR(20)
    contact_email             VARCHAR(255)
    emergency_contact         VARCHAR(100)
    emergency_phone           VARCHAR(20)

Expansion 9 – Operating hours
    opening_time              VARCHAR(5)
    closing_time              VARCHAR(5)
    timezone                  VARCHAR(50)  DEFAULT 'America/Mexico_City'
    operational_days          VARCHAR(20)

Expansion 10 – Connectivity status
    last_seen_at              DATETIME
    connection_status         VARCHAR(20)  DEFAULT 'unknown'

New table ``branch_config_history``
────────────────────────────────────
    id                INTEGER PRIMARY KEY AUTOINCREMENT
    branch_id         INTEGER  (FK → branches.id  ON DELETE SET NULL)
    changed_by        VARCHAR(150)
    field_name        VARCHAR(50)  NOT NULL
    old_value         TEXT
    new_value         TEXT
    changed_at        DATETIME     DEFAULT CURRENT_TIMESTAMP
    reason            VARCHAR(255)

The migration is fully idempotent: column additions are skipped if they
already exist; table creation uses CREATE TABLE IF NOT EXISTS.
"""

from typing import Tuple

# ---------------------------------------------------------------------------
# New columns for the ``branches`` table
# ---------------------------------------------------------------------------
_BRANCH_NEW_COLUMNS: Tuple[Tuple[str, str], ...] = (
    # Expansion 7 – Count scheduling
    ("last_count_date",         "DATETIME"),
    ("next_scheduled_count",    "DATETIME"),
    ("count_enabled",           "BOOLEAN DEFAULT 1"),
    # Expansion 8 – Contact information
    ("contact_phone",           "VARCHAR(20)"),
    ("contact_email",           "VARCHAR(255)"),
    ("emergency_contact",       "VARCHAR(100)"),
    ("emergency_phone",         "VARCHAR(20)"),
    # Expansion 9 – Operating hours
    ("opening_time",            "VARCHAR(5)"),
    ("closing_time",            "VARCHAR(5)"),
    ("timezone",                "VARCHAR(50) DEFAULT 'America/Mexico_City'"),
    ("operational_days",        "VARCHAR(20)"),
    # Expansion 10 – Connectivity status
    ("last_seen_at",            "DATETIME"),
    ("connection_status",       "VARCHAR(20) DEFAULT 'unknown'"),
)


def _column_exists(cursor, table: str, column: str) -> bool:
    """Return True if *column* already exists in *table* (SQLite)."""
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def _table_exists(cursor, table: str) -> bool:
    """Return True if *table* exists in the current SQLite database."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cursor.fetchone() is not None


def upgrade(connection) -> None:
    """Apply migration 010."""
    cursor = connection.cursor()
    added_cols: list[str] = []
    skipped_cols: list[str] = []

    # ------------------------------------------------------------------
    # 1. Add new columns to branches
    # ------------------------------------------------------------------
    for col_name, col_def in _BRANCH_NEW_COLUMNS:
        if _column_exists(cursor, "branches", col_name):
            skipped_cols.append(col_name)
            continue
        try:
            cursor.execute(
                f"ALTER TABLE branches ADD COLUMN {col_name} {col_def}"
            )
            added_cols.append(col_name)
        except Exception as exc:
            print(f"  WARNING: Could not add column '{col_name}' to branches: {exc}")

    # ------------------------------------------------------------------
    # 2. Create branch_config_history table
    # ------------------------------------------------------------------
    table_created = False
    if not _table_exists(cursor, "branch_config_history"):
        cursor.execute("""
            CREATE TABLE branch_config_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                branch_id   INTEGER REFERENCES branches(id) ON DELETE SET NULL,
                changed_by  VARCHAR(150),
                field_name  VARCHAR(50) NOT NULL,
                old_value   TEXT,
                new_value   TEXT,
                changed_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                reason      VARCHAR(255)
            )
        """)
        table_created = True

    # ------------------------------------------------------------------
    # 3. Indexes
    # ------------------------------------------------------------------
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_branches_next_count "
        "ON branches(next_scheduled_count)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_branches_connection_status "
        "ON branches(connection_status)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_branch_config_history_branch "
        "ON branch_config_history(branch_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_branch_config_history_changed_at "
        "ON branch_config_history(changed_at)"
    )

    connection.commit()

    # ------------------------------------------------------------------
    # Summary output
    # ------------------------------------------------------------------
    if added_cols:
        print(f"Migration 010: columns added to branches: {', '.join(added_cols)}.")
    if skipped_cols:
        print(f"Migration 010: columns already present (skipped): {', '.join(skipped_cols)}.")
    if table_created:
        print("Migration 010: table 'branch_config_history' created.")
    else:
        print("Migration 010: table 'branch_config_history' already exists (skipped).")
    if not added_cols and not table_created:
        print("Migration 010: nothing to do.")


def downgrade(connection) -> None:
    """
    Roll back migration 010.

    SQLite does not support DROP COLUMN on older versions, so the branches
    table is recreated from its pre-010 schema and data is copied back.
    The branch_config_history table is simply dropped.
    """
    cursor = connection.cursor()

    # 1. Drop branch_config_history
    cursor.execute("DROP TABLE IF EXISTS branch_config_history")

    # 2. Recreate branches without the 010 columns
    cursor.execute("ALTER TABLE branches RENAME TO branches_backup_010")
    cursor.execute("""
        CREATE TABLE branches (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            name                VARCHAR(100) NOT NULL UNIQUE,
            address             VARCHAR(255),
            is_active           BOOLEAN DEFAULT 1,
            created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at          DATETIME,
            latitude            REAL,
            longitude           REAL,
            zone                VARCHAR(50),
            city                VARCHAR(100),
            state               VARCHAR(100),
            country             VARCHAR(100) DEFAULT 'México',
            default_min_stock   INTEGER,
            default_max_stock   INTEGER,
            stock_alert_enabled BOOLEAN DEFAULT 1,
            operational_status  VARCHAR(30) NOT NULL DEFAULT 'operativa',
            manager_user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
            count_frequency     VARCHAR(20),
            storage_capacity    VARCHAR(50),
            max_products        INTEGER
        )
    """)
    cursor.execute("""
        INSERT INTO branches (
            id, name, address, is_active, created_at, updated_at,
            latitude, longitude, zone, city, state, country,
            default_min_stock, default_max_stock, stock_alert_enabled,
            operational_status, manager_user_id, count_frequency,
            storage_capacity, max_products
        )
        SELECT
            id, name, address, is_active, created_at, updated_at,
            latitude, longitude, zone, city, state, country,
            default_min_stock, default_max_stock, stock_alert_enabled,
            operational_status, manager_user_id, count_frequency,
            storage_capacity, max_products
        FROM branches_backup_010
    """)
    cursor.execute("DROP TABLE branches_backup_010")

    # 3. Restore indexes from 002
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_branches_manager_user ON branches(manager_user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_branches_operational_status ON branches(operational_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_branches_zone ON branches(zone)")

    connection.commit()
    print("Migration 010 rolled back.")


# ---------------------------------------------------------------------------
# CLI helper – run directly: python 010_branch_phase2_expansions.py <db_path>
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    import sqlite3

    if len(sys.argv) < 2:
        print("Usage: python 010_branch_phase2_expansions.py <path_to_db> [--downgrade]")
        sys.exit(1)

    db_path = sys.argv[1]
    conn = sqlite3.connect(db_path)

    if "--downgrade" in sys.argv:
        downgrade(conn)
    else:
        upgrade(conn)

    conn.close()
