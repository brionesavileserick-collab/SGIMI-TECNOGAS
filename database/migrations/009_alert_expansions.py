"""
Migration 009 – Alert expansions.

Adds new columns to the existing ``alerts`` table required by the alert
module expansion plan.  All new columns are nullable or carry a safe
default, so existing rows remain valid without any data backfill.

Exp 7  – Notas de resolución
    resolution_notes      TEXT      NULL

Exp 9  – Asignación a usuario
    assigned_to           INTEGER   NULL  FK → users(id) ON DELETE SET NULL

Exp 10 – Prioridad y expiración
    priority              VARCHAR(20)  NOT NULL DEFAULT 'normal'
    due_date              DATETIME     NULL
    is_expired_flag       BOOLEAN      NOT NULL DEFAULT 0

The migration is idempotent: every ALTER TABLE is wrapped in a
PRAGMA table_info check so re-running it is safe.
"""

from typing import Tuple

# ---------------------------------------------------------------------------
# New columns
# (column_name, sql_type_and_constraint)
# ---------------------------------------------------------------------------
_ALERT_COLUMNS: Tuple[Tuple[str, str], ...] = (
    # Exp 7 – Notas de resolución
    ("resolution_notes",  "TEXT"),
    # Exp 9 – Asignación
    ("assigned_to",       "INTEGER REFERENCES users(id) ON DELETE SET NULL"),
    # Exp 10 – Prioridad
    ("priority",          "VARCHAR(20) NOT NULL DEFAULT 'normal'"),
    # Exp 10 – Fecha límite
    ("due_date",          "DATETIME"),
    # Exp 10 – Flag de expiración
    ("is_expired_flag",   "BOOLEAN NOT NULL DEFAULT 0"),
)


def _column_exists(cursor, table: str, column: str) -> bool:
    """Return True if *column* already exists in *table* (SQLite)."""
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def _create_index_if_missing(cursor, index_name: str, create_sql: str) -> None:
    """Execute *create_sql* only when the index does not already exist."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
        (index_name,),
    )
    if cursor.fetchone() is None:
        cursor.execute(create_sql)
        print(f"  Created index: {index_name}")
    else:
        print(f"  Index already exists (skipped): {index_name}")


def upgrade(connection) -> None:
    """Apply all alert expansion changes."""
    cursor = connection.cursor()

    # ------------------------------------------------------------------
    # Part 1 – Add new columns to ``alerts``
    # ------------------------------------------------------------------
    for column_name, column_def in _ALERT_COLUMNS:
        if not _column_exists(cursor, "alerts", column_name):
            cursor.execute(
                f"ALTER TABLE alerts ADD COLUMN {column_name} {column_def}"
            )
            print(f"  [alerts] Added column: {column_name}")
        else:
            print(f"  [alerts] Column already exists (skipped): {column_name}")

    # ------------------------------------------------------------------
    # Part 2 – Indexes for new columns
    # ------------------------------------------------------------------
    _create_index_if_missing(
        cursor,
        "idx_alerts_assigned_to",
        "CREATE INDEX IF NOT EXISTS idx_alerts_assigned_to "
        "ON alerts(assigned_to)",
    )
    _create_index_if_missing(
        cursor,
        "idx_alerts_priority",
        "CREATE INDEX IF NOT EXISTS idx_alerts_priority "
        "ON alerts(priority)",
    )
    _create_index_if_missing(
        cursor,
        "idx_alerts_due_date",
        "CREATE INDEX IF NOT EXISTS idx_alerts_due_date "
        "ON alerts(due_date)",
    )
    _create_index_if_missing(
        cursor,
        "idx_alerts_is_expired_flag",
        "CREATE INDEX IF NOT EXISTS idx_alerts_is_expired_flag "
        "ON alerts(is_expired_flag)",
    )
    _create_index_if_missing(
        cursor,
        "idx_alerts_is_resolved",
        "CREATE INDEX IF NOT EXISTS idx_alerts_is_resolved "
        "ON alerts(is_resolved)",
    )
    _create_index_if_missing(
        cursor,
        "idx_alerts_branch_id",
        "CREATE INDEX IF NOT EXISTS idx_alerts_branch_id "
        "ON alerts(branch_id)",
    )
    _create_index_if_missing(
        cursor,
        "idx_alerts_created_at",
        "CREATE INDEX IF NOT EXISTS idx_alerts_created_at "
        "ON alerts(created_at)",
    )

    connection.commit()
    print("Migration 009_alert_expansions.py applied successfully.")


def downgrade(connection) -> None:
    """
    SQLite does not support DROP COLUMN directly.
    The downgrade rebuilds ``alerts`` without the expansion columns using
    the rename-copy-drop pattern.
    """
    cursor = connection.cursor()

    # Drop new indexes first
    for idx in (
        "idx_alerts_assigned_to",
        "idx_alerts_priority",
        "idx_alerts_due_date",
        "idx_alerts_is_expired_flag",
        "idx_alerts_is_resolved",
        "idx_alerts_branch_id",
        "idx_alerts_created_at",
    ):
        cursor.execute(f"DROP INDEX IF EXISTS {idx}")
        print(f"  Dropped index: {idx}")

    # Original columns (from migration 001)
    original_cols = (
        "id", "alert_type", "severity", "title", "message",
        "product_id", "branch_id", "movement_id",
        "is_read", "is_resolved", "created_at", "resolved_at",
    )
    col_list = ", ".join(original_cols)

    cursor.execute("ALTER TABLE alerts RENAME TO alerts_old")
    cursor.execute(f"""
        CREATE TABLE alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type  VARCHAR(50)  NOT NULL,
            severity    VARCHAR(20)  NOT NULL,
            title       VARCHAR(200) NOT NULL,
            message     TEXT         NOT NULL,
            product_id  INTEGER,
            branch_id   INTEGER,
            movement_id INTEGER,
            is_read     BOOLEAN DEFAULT 0,
            is_resolved BOOLEAN DEFAULT 0,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            resolved_at DATETIME
        )
    """)
    cursor.execute(
        f"INSERT INTO alerts ({col_list}) SELECT {col_list} FROM alerts_old"
    )
    cursor.execute("DROP TABLE alerts_old")

    connection.commit()
    print("Migration 009_alert_expansions.py rolled back successfully.")


if __name__ == "__main__":
    import sqlite3
    conn = sqlite3.connect("test.db")
    upgrade(conn)
    conn.close()
