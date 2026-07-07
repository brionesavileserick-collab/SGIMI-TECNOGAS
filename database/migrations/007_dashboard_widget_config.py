"""
Migration 007 – Dashboard widget configuration table.

Creates the ``dashboard_widget_configs`` table that persists per-user
dashboard layout preferences (which widgets are visible and in what order).

Schema:
    id          INTEGER  PK AUTOINCREMENT
    user_id     INTEGER  NULL  FK → users(id) ON DELETE SET NULL
    widget_key  VARCHAR(50)  NOT NULL
    position    INTEGER  NOT NULL  DEFAULT 0
    is_visible  BOOLEAN  NOT NULL  DEFAULT 1
    config      TEXT     NULL  (JSON string for widget-specific settings)
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP

The migration is idempotent: CREATE TABLE/INDEX IF NOT EXISTS.
"""


def _table_exists(cursor, table: str) -> bool:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cursor.fetchone() is not None


def _create_index_if_missing(cursor, index_name: str, create_sql: str) -> None:
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
    """Create the dashboard_widget_configs table and its indexes."""
    cursor = connection.cursor()

    if not _table_exists(cursor, "dashboard_widget_configs"):
        cursor.execute("""
            CREATE TABLE dashboard_widget_configs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER
                                REFERENCES users(id) ON DELETE SET NULL,
                widget_key  VARCHAR(50)  NOT NULL,
                position    INTEGER      NOT NULL DEFAULT 0,
                is_visible  BOOLEAN      NOT NULL DEFAULT 1,
                config      TEXT,
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("  Created table: dashboard_widget_configs")
    else:
        print("  Table already exists (skipped): dashboard_widget_configs")

    _create_index_if_missing(
        cursor,
        "idx_dwc_user_id",
        "CREATE INDEX IF NOT EXISTS idx_dwc_user_id "
        "ON dashboard_widget_configs(user_id)",
    )
    _create_index_if_missing(
        cursor,
        "idx_dwc_widget_key",
        "CREATE INDEX IF NOT EXISTS idx_dwc_widget_key "
        "ON dashboard_widget_configs(widget_key)",
    )

    connection.commit()
    print("Migration 007_dashboard_widget_config.py applied successfully.")


def downgrade(connection) -> None:
    """Drop the dashboard_widget_configs table."""
    cursor = connection.cursor()
    cursor.execute("DROP TABLE IF EXISTS dashboard_widget_configs")
    connection.commit()
    print("Migration 007_dashboard_widget_config.py rolled back.")


if __name__ == "__main__":
    import sqlite3

    conn = sqlite3.connect("test.db")
    upgrade(conn)
    conn.close()
