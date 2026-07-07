"""
Migration 008 – History Archive table + extra indexes.

Creates:
  - archive_history  : mirror of history used by Expansion 7 (archive before purge)
  - idx_history_entity_type   : speeds up entity_type filter (Expansion 1, 3, 9)
  - idx_history_entity_id     : speeds up entity-specific look-ups
  - idx_history_user_id       : speeds up user activity filter
  - idx_archive_created       : allows efficient date-range queries on archive

All statements are idempotent (IF NOT EXISTS).
"""


def upgrade(connection):
    cursor = connection.cursor()

    # ── archive_history table ────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS archive_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            original_id INTEGER NOT NULL,
            event_type  VARCHAR(100) NOT NULL,
            entity_type VARCHAR(50),
            entity_id   INTEGER,
            user_id     INTEGER,
            action      VARCHAR(100) NOT NULL,
            details     TEXT,
            created_at  DATETIME,
            archived_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── indexes on history ───────────────────────────────────────────────────
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_history_entity_type "
        "ON history(entity_type)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_history_entity_id "
        "ON history(entity_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_history_user_id "
        "ON history(user_id)"
    )

    # ── indexes on archive_history ────────────────────────────────────────────
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_archive_original_id "
        "ON archive_history(original_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_archive_event "
        "ON archive_history(event_type)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_archive_created "
        "ON archive_history(created_at)"
    )

    connection.commit()
    print("Migration 008_history_archive.py applied successfully.")


def downgrade(connection):
    cursor = connection.cursor()

    cursor.execute("DROP INDEX IF EXISTS idx_archive_created")
    cursor.execute("DROP INDEX IF EXISTS idx_archive_event")
    cursor.execute("DROP INDEX IF EXISTS idx_archive_original_id")
    cursor.execute("DROP INDEX IF EXISTS idx_history_user_id")
    cursor.execute("DROP INDEX IF EXISTS idx_history_entity_id")
    cursor.execute("DROP INDEX IF EXISTS idx_history_entity_type")
    cursor.execute("DROP TABLE IF EXISTS archive_history")

    connection.commit()
    print("Migration 008_history_archive.py rolled back successfully.")
