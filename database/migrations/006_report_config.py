"""
Migration 006 – Saved reports configuration table.

Creates the ``saved_reports`` table that allows users to persist named
report configurations (type + filter parameters) for later reuse.

Schema:
    id           INTEGER  PK AUTOINCREMENT
    name         VARCHAR(100) NOT NULL
    report_type  VARCHAR(50)  NOT NULL
    parameters   TEXT         NULL   (JSON string)
    created_by   INTEGER      NULL   FK → users(id) ON DELETE SET NULL
    created_at   DATETIME     DEFAULT CURRENT_TIMESTAMP

The migration is idempotent: the table and indexes are created with
IF NOT EXISTS, so re-running is always safe.
"""


def _table_exists(cursor, table: str) -> bool:
    """Return True if *table* already exists in the SQLite database."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cursor.fetchone() is not None


def _create_index_if_missing(cursor, index_name: str, create_sql: str) -> None:
    """Execute *create_sql* only when the named index does not exist yet."""
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
    """Create the saved_reports table and its indexes."""
    cursor = connection.cursor()

    if not _table_exists(cursor, "saved_reports"):
        cursor.execute("""
            CREATE TABLE saved_reports (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        VARCHAR(100) NOT NULL,
                report_type VARCHAR(50)  NOT NULL,
                parameters  TEXT,
                created_by  INTEGER
                                REFERENCES users(id) ON DELETE SET NULL,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("  Created table: saved_reports")
    else:
        print("  Table already exists (skipped): saved_reports")

    _create_index_if_missing(
        cursor,
        "idx_saved_reports_report_type",
        "CREATE INDEX IF NOT EXISTS idx_saved_reports_report_type "
        "ON saved_reports(report_type)",
    )
    _create_index_if_missing(
        cursor,
        "idx_saved_reports_created_by",
        "CREATE INDEX IF NOT EXISTS idx_saved_reports_created_by "
        "ON saved_reports(created_by)",
    )

    connection.commit()
    print("Migration 006_report_config.py applied successfully.")


def downgrade(connection) -> None:
    """Drop the saved_reports table entirely."""
    cursor = connection.cursor()
    cursor.execute("DROP TABLE IF EXISTS saved_reports")
    connection.commit()
    print("Migration 006_report_config.py rolled back successfully.")


if __name__ == "__main__":
    import sqlite3

    conn = sqlite3.connect("test.db")
    upgrade(conn)
    conn.close()
