"""
Migration 003 – Inventory expansions.

Adds new columns to the ``inventory`` table and creates the new
``inventory_history`` table required by expansions 1–9.

All new inventory columns are nullable or carry a safe default value, so
existing rows remain valid without any data backfill.

Expansión 1 – Ubicación física
    location                VARCHAR(100)

Expansión 2 – Notas en conteos
    last_count_notes        TEXT

Expansión 3 – Tags / categorías custom
    tags                    VARCHAR(255)

Expansión 4 – Prioridad de reposición
    reorder_priority        VARCHAR(20)   DEFAULT 'normal'

Expansión 5 – Alertas personalizadas por item
    critical_stock_threshold    INTEGER
    max_stock_threshold         INTEGER
    discrepancy_tolerance       INTEGER   DEFAULT 0

Expansión 6 – Stock en tránsito
    in_transit_quantity     INTEGER       DEFAULT 0

Expansión 7 – Historial de cambios (tabla nueva: inventory_history)

Expansión 8 – Valor de inventario
    unit_cost               REAL

The migration is idempotent: each ALTER TABLE is wrapped in a check so
that re-running on an already-migrated database is safe.
"""

from typing import Tuple

# ---------------------------------------------------------------------------
# New columns for the existing ``inventory`` table
# (column_name, sql_type_and_constraint)
# ---------------------------------------------------------------------------
_INVENTORY_COLUMNS: Tuple[Tuple[str, str], ...] = (
    # Expansión 1
    ("location",                    "VARCHAR(100)"),
    # Expansión 2
    ("last_count_notes",            "TEXT"),
    # Expansión 3
    ("tags",                        "VARCHAR(255)"),
    # Expansión 4
    ("reorder_priority",            "VARCHAR(20) NOT NULL DEFAULT 'normal'"),
    # Expansión 5
    ("critical_stock_threshold",    "INTEGER"),
    ("max_stock_threshold",         "INTEGER"),
    ("discrepancy_tolerance",       "INTEGER NOT NULL DEFAULT 0"),
    # Expansión 6
    ("in_transit_quantity",         "INTEGER NOT NULL DEFAULT 0"),
    # Expansión 8
    ("unit_cost",                   "REAL"),
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
    """
    1. Add expansion columns to ``inventory``.
    2. Create ``inventory_history`` table (Expansión 7).
    """
    cursor = connection.cursor()
    added: list = []
    skipped: list = []

    # ------------------------------------------------------------------
    # Part 1 – ALTER TABLE inventory ADD COLUMN …
    # ------------------------------------------------------------------
    for col_name, col_def in _INVENTORY_COLUMNS:
        if _column_exists(cursor, "inventory", col_name):
            skipped.append(col_name)
            continue
        try:
            cursor.execute(
                f"ALTER TABLE inventory ADD COLUMN {col_name} {col_def}"
            )
            added.append(col_name)
        except Exception as exc:
            print(f"  WARNING: Could not add column 'inventory.{col_name}': {exc}")

    # ------------------------------------------------------------------
    # Part 2 – CREATE TABLE inventory_history (Expansión 7)
    # ------------------------------------------------------------------
    if _table_exists(cursor, "inventory_history"):
        print("Migration 003: table 'inventory_history' already exists (skipped).")
    else:
        cursor.execute('''
            CREATE TABLE inventory_history (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                inventory_id        INTEGER NOT NULL
                                        REFERENCES inventory(id) ON DELETE CASCADE,
                previous_physical   INTEGER NOT NULL DEFAULT 0,
                new_physical        INTEGER NOT NULL DEFAULT 0,
                previous_digital    INTEGER NOT NULL DEFAULT 0,
                new_digital         INTEGER NOT NULL DEFAULT 0,
                change_type         VARCHAR(30) NOT NULL,
                movement_id         INTEGER,
                reason              VARCHAR(255),
                created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("Migration 003: table 'inventory_history' created.")

    # ------------------------------------------------------------------
    # Part 3 – Indexes
    # ------------------------------------------------------------------
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_inventory_location "
        "ON inventory(branch_id, location)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_inventory_reorder_priority "
        "ON inventory(branch_id, reorder_priority)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_inventory_in_transit "
        "ON inventory(branch_id, in_transit_quantity)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_inventory_history_inventory "
        "ON inventory_history(inventory_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_inventory_history_created "
        "ON inventory_history(created_at)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_inventory_history_change_type "
        "ON inventory_history(inventory_id, change_type)"
    )

    connection.commit()

    if added:
        print(f"Migration 003 applied. Columns added to inventory: {', '.join(added)}.")
    if skipped:
        print(f"Migration 003: columns already present (skipped): {', '.join(skipped)}.")
    if not added and not skipped:
        print("Migration 003: nothing to do.")


def downgrade(connection) -> None:
    """
    SQLite does not support DROP COLUMN on older versions.
    This downgrade:
      1. Drops inventory_history.
      2. Recreates inventory without the expansion columns.
    Existing data in original columns is preserved.
    """
    cursor = connection.cursor()

    # 1. Drop history table (no data loss concern – it's audit-only)
    cursor.execute("DROP TABLE IF EXISTS inventory_history")

    # 2. Recreate inventory without expansion columns
    cursor.execute("ALTER TABLE inventory RENAME TO inventory_backup_003")

    cursor.execute('''
        CREATE TABLE inventory (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id      INTEGER NOT NULL,
            branch_id       INTEGER NOT NULL,
            physical_stock  INTEGER DEFAULT 0 NOT NULL,
            digital_stock   INTEGER DEFAULT 0 NOT NULL,
            min_stock       INTEGER DEFAULT 0,
            max_stock       INTEGER,
            last_count_date DATETIME,
            is_active       BOOLEAN DEFAULT 1,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at      DATETIME,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (branch_id)  REFERENCES branches(id) ON DELETE CASCADE,
            UNIQUE(product_id, branch_id)
        )
    ''')

    cursor.execute('''
        INSERT INTO inventory (
            id, product_id, branch_id,
            physical_stock, digital_stock,
            min_stock, max_stock,
            last_count_date, is_active,
            created_at, updated_at
        )
        SELECT
            id, product_id, branch_id,
            physical_stock, digital_stock,
            min_stock, max_stock,
            last_count_date, is_active,
            created_at, updated_at
        FROM inventory_backup_003
    ''')

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_inventory_product_branch "
        "ON inventory(product_id, branch_id)"
    )

    cursor.execute("DROP TABLE inventory_backup_003")

    connection.commit()
    print("Migration 003 rolled back. Expansion columns removed from inventory.")


# ---------------------------------------------------------------------------
# CLI helper – run directly: python 003_inventory_expansions.py <db_path>
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    import sqlite3

    if len(sys.argv) < 2:
        print("Usage: python 003_inventory_expansions.py <path_to_db> [--downgrade]")
        sys.exit(1)

    db_path = sys.argv[1]
    conn = sqlite3.connect(db_path)

    if "--downgrade" in sys.argv:
        downgrade(conn)
    else:
        upgrade(conn)

    conn.close()
