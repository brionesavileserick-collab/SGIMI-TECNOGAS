"""
Migration 005 – Movement expansions.

Adds new columns to the ``movements`` table and creates the new
``movement_state_history`` table required by the 8 movement expansions.

All new ``movements`` columns are nullable or carry a safe default value,
so existing rows remain valid without any data backfill.

Expansión 1 – Cancelación y reversión
    is_cancelled              BOOLEAN  NOT NULL DEFAULT 0
    cancelled_at              DATETIME NULL
    cancelled_by              INTEGER  NULL  FK → users(id)
    cancellation_reason       TEXT     NULL
    reversal_of_movement_id   INTEGER  NULL  FK → movements(id)

Expansión 2 – Confirmación de recepción en transferencias
    is_received               BOOLEAN  NOT NULL DEFAULT 0
    received_at               DATETIME NULL
    received_by               INTEGER  NULL  FK → users(id)
    received_notes            TEXT     NULL

Expansión 3 – Prioridad / urgencia
    priority                  VARCHAR(20) NOT NULL DEFAULT 'normal'

Expansión 4 – Origen del movimiento
    source                    VARCHAR(50) NULL

Expansión 5 – Documento de referencia
    reference_number          VARCHAR(100) NULL
    reference_type            VARCHAR(50)  NULL

Expansión 6 – Costo en el momento del movimiento
    unit_cost                 REAL NULL
    total_cost                REAL NULL

Expansión 7 – Historial de cambios de estado  (tabla nueva)
    movement_state_history

Expansión 8 – Confirmación física / recepción
    receiver_name             VARCHAR(100) NULL
    receiver_signature        TEXT         NULL

The migration is idempotent: each ALTER TABLE is wrapped in a PRAGMA
table_info check, and the new table uses CREATE … IF NOT EXISTS.
"""

from typing import Tuple

# ---------------------------------------------------------------------------
# New columns for the existing ``movements`` table
# (column_name, sql_type_and_constraint)
# ---------------------------------------------------------------------------
_MOVEMENT_COLUMNS: Tuple[Tuple[str, str], ...] = (
    # Expansión 1 – Cancelación
    ("is_cancelled",            "BOOLEAN NOT NULL DEFAULT 0"),
    ("cancelled_at",            "DATETIME"),
    ("cancelled_by",            "INTEGER REFERENCES users(id) ON DELETE SET NULL"),
    ("cancellation_reason",     "TEXT"),
    ("reversal_of_movement_id", "INTEGER REFERENCES movements(id) ON DELETE SET NULL"),
    # Expansión 2 – Confirmación de recepción
    ("is_received",             "BOOLEAN NOT NULL DEFAULT 0"),
    ("received_at",             "DATETIME"),
    ("received_by",             "INTEGER REFERENCES users(id) ON DELETE SET NULL"),
    ("received_notes",          "TEXT"),
    # Expansión 3 – Prioridad
    ("priority",                "VARCHAR(20) NOT NULL DEFAULT 'normal'"),
    # Expansión 4 – Origen
    ("source",                  "VARCHAR(50)"),
    # Expansión 5 – Referencia externa
    ("reference_number",        "VARCHAR(100)"),
    ("reference_type",          "VARCHAR(50)"),
    # Expansión 6 – Costo
    ("unit_cost",               "REAL"),
    ("total_cost",              "REAL"),
    # Expansión 8 – Recepción física
    ("receiver_name",           "VARCHAR(100)"),
    ("receiver_signature",      "TEXT"),
)


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


def upgrade(connection) -> None:
    """Apply all movement expansion changes."""
    cursor = connection.cursor()

    # ------------------------------------------------------------------
    # Part 1 – Add expansion columns to ``movements``
    # ------------------------------------------------------------------
    for column_name, column_def in _MOVEMENT_COLUMNS:
        if not _column_exists(cursor, "movements", column_name):
            cursor.execute(
                f"ALTER TABLE movements ADD COLUMN {column_name} {column_def}"
            )
            print(f"  [movements] Added column: {column_name}")
        else:
            print(f"  [movements] Column already exists (skipped): {column_name}")

    # ------------------------------------------------------------------
    # Part 2 – CREATE TABLE movement_state_history  (Expansión 7)
    # ------------------------------------------------------------------
    if not _table_exists(cursor, "movement_state_history"):
        cursor.execute('''
            CREATE TABLE movement_state_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                movement_id     INTEGER NOT NULL
                                    REFERENCES movements(id) ON DELETE CASCADE,
                previous_state  VARCHAR(20),
                new_state       VARCHAR(20) NOT NULL,
                changed_by      INTEGER
                                    REFERENCES users(id) ON DELETE SET NULL,
                change_reason   TEXT,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("  Created table: movement_state_history")
    else:
        print("  Table already exists (skipped): movement_state_history")

    # ------------------------------------------------------------------
    # Part 3 – Indexes for the new table and new columns
    # ------------------------------------------------------------------
    _create_index_if_missing(
        cursor,
        "idx_movement_state_history_movement",
        "CREATE INDEX IF NOT EXISTS idx_movement_state_history_movement "
        "ON movement_state_history(movement_id)",
    )
    _create_index_if_missing(
        cursor,
        "idx_movement_state_history_created",
        "CREATE INDEX IF NOT EXISTS idx_movement_state_history_created "
        "ON movement_state_history(created_at)",
    )
    _create_index_if_missing(
        cursor,
        "idx_movements_priority",
        "CREATE INDEX IF NOT EXISTS idx_movements_priority "
        "ON movements(priority)",
    )
    _create_index_if_missing(
        cursor,
        "idx_movements_source",
        "CREATE INDEX IF NOT EXISTS idx_movements_source "
        "ON movements(source)",
    )
    _create_index_if_missing(
        cursor,
        "idx_movements_reference_number",
        "CREATE INDEX IF NOT EXISTS idx_movements_reference_number "
        "ON movements(reference_number)",
    )
    _create_index_if_missing(
        cursor,
        "idx_movements_is_cancelled",
        "CREATE INDEX IF NOT EXISTS idx_movements_is_cancelled "
        "ON movements(is_cancelled)",
    )
    _create_index_if_missing(
        cursor,
        "idx_movements_is_received",
        "CREATE INDEX IF NOT EXISTS idx_movements_is_received "
        "ON movements(is_received)",
    )

    connection.commit()
    print("Migration 005_movement_expansions.py applied successfully.")


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
      1. Drops the movement_state_history table entirely.
      2. Recreates ``movements`` without the expansion columns via
         the rename-copy-drop pattern.
    """
    cursor = connection.cursor()

    # Drop history table
    cursor.execute("DROP TABLE IF EXISTS movement_state_history")
    print("  Dropped table: movement_state_history")

    # Rebuild ``movements`` without expansion columns
    # Original columns (from migration 001):
    original_cols = (
        "id", "product_id", "branch_id", "destination_branch_id",
        "user_id", "movement_type", "quantity", "state", "reason",
        "notes", "validated_at", "validated_by", "created_at", "updated_at",
    )
    col_list = ", ".join(original_cols)

    cursor.execute("ALTER TABLE movements RENAME TO movements_old")
    cursor.execute(f'''
        CREATE TABLE movements (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id            INTEGER NOT NULL,
            branch_id             INTEGER NOT NULL,
            destination_branch_id INTEGER,
            user_id               INTEGER,
            movement_type         VARCHAR(20) NOT NULL,
            quantity              INTEGER NOT NULL,
            state                 VARCHAR(20) NOT NULL DEFAULT 'pendiente',
            reason                TEXT,
            notes                 TEXT,
            validated_at          DATETIME,
            validated_by          INTEGER,
            created_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at            DATETIME,
            FOREIGN KEY (product_id)            REFERENCES products(id)  ON DELETE CASCADE,
            FOREIGN KEY (branch_id)             REFERENCES branches(id)  ON DELETE CASCADE,
            FOREIGN KEY (destination_branch_id) REFERENCES branches(id)  ON DELETE SET NULL,
            FOREIGN KEY (user_id)               REFERENCES users(id)     ON DELETE SET NULL,
            FOREIGN KEY (validated_by)          REFERENCES users(id)     ON DELETE SET NULL
        )
    ''')
    cursor.execute(
        f"INSERT INTO movements ({col_list}) SELECT {col_list} FROM movements_old"
    )
    cursor.execute("DROP TABLE movements_old")

    connection.commit()
    print("Migration 005_movement_expansions.py rolled back successfully.")


if __name__ == "__main__":
    import sqlite3

    conn = sqlite3.connect("test.db")
    upgrade(conn)
    conn.close()
