"""
Migration 015 – Fase 2: Variantes de Producto + Historial de Cambios.

products table:
  + parent_product_id   INTEGER  NULL  (FK → products.id)
  + variant_group_id    VARCHAR(50)  NULL
  + variant_attributes  VARCHAR(255)  NULL

New table: product_change_history
  id               INTEGER  PK AUTOINCREMENT
  product_id       INTEGER  NOT NULL  (FK → products.id)
  field_name       VARCHAR(50)  NOT NULL
  old_value        TEXT  NULL
  new_value        TEXT  NULL
  changed_at       DATETIME  NOT NULL  DEFAULT CURRENT_TIMESTAMP
  changed_by_name  VARCHAR(100)  NULL

All changes are additive and idempotent.
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


_PRODUCT_VARIANT_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("parent_product_id",  "INTEGER"),
    ("variant_group_id",   "VARCHAR(50)"),
    ("variant_attributes", "VARCHAR(255)"),
)

_CREATE_CHANGE_HISTORY = """
CREATE TABLE IF NOT EXISTS product_change_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER NOT NULL
                        REFERENCES products(id) ON DELETE CASCADE,
    field_name      VARCHAR(50) NOT NULL,
    old_value       TEXT,
    new_value       TEXT,
    changed_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_by_name VARCHAR(100)
)
"""

_CREATE_IDX_CHANGE_HISTORY = (
    "CREATE INDEX IF NOT EXISTS ix_product_change_history_product_id "
    "ON product_change_history(product_id)"
)


def upgrade(connection) -> None:
    cursor = connection.cursor()

    # ── products – variant columns ───────────────────────────────────────
    for col_name, col_def in _PRODUCT_VARIANT_COLUMNS:
        if _column_exists(cursor, "products", col_name):
            continue
        try:
            cursor.execute(
                f"ALTER TABLE products ADD COLUMN {col_name} {col_def}"
            )
            print(f"Migration 015: added products.{col_name}")
        except Exception as exc:
            print(f"  WARNING: Could not add column 'products.{col_name}': {exc}")

    # ── product_change_history table ─────────────────────────────────────
    try:
        cursor.execute(_CREATE_CHANGE_HISTORY)
        print("Migration 015: created table product_change_history")
    except Exception as exc:
        print(f"  WARNING: Could not create product_change_history: {exc}")

    try:
        cursor.execute(_CREATE_IDX_CHANGE_HISTORY)
        print("Migration 015: created index on product_change_history.product_id")
    except Exception as exc:
        print(f"  WARNING: Could not create index: {exc}")

    connection.commit()
    print("Migration 015 applied.")


def downgrade(connection) -> None:
    print("Migration 015: no downgrade implemented (columns and table retained).")


if __name__ == "__main__":
    import sys
    import sqlite3

    if len(sys.argv) < 2:
        print("Usage: python 015_product_variants_history.py <path_to_db>")
        sys.exit(1)

    conn = sqlite3.connect(sys.argv[1])
    upgrade(conn)
    conn.close()
