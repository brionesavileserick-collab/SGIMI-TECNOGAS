"""
Migration 016 – Fase 3: Productos Compuestos/Kit + Información Fiscal.

products table:
  + is_kit              INTEGER  NOT NULL  DEFAULT 0  (Boolean)
  + sat_product_code    VARCHAR(20)  NULL
  + customs_tariff_code VARCHAR(20)  NULL
  + country_of_origin   VARCHAR(100)  NULL  DEFAULT 'México'

New table: kit_components
  id                    INTEGER  PK AUTOINCREMENT
  kit_product_id        INTEGER  NOT NULL  (FK → products.id)
  component_product_id  INTEGER  NOT NULL  (FK → products.id)
  quantity              INTEGER  NOT NULL  DEFAULT 1
  notes                 TEXT  NULL
  created_at            DATETIME  NOT NULL  DEFAULT CURRENT_TIMESTAMP
  UNIQUE(kit_product_id, component_product_id)

All changes are additive and idempotent.
"""

from typing import Tuple


def _column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


_PRODUCT_KIT_FISCAL_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("is_kit",              "INTEGER NOT NULL DEFAULT 0"),
    ("sat_product_code",    "VARCHAR(20)"),
    ("customs_tariff_code", "VARCHAR(20)"),
    ("country_of_origin",   "VARCHAR(100) DEFAULT 'México'"),
)

_CREATE_KIT_COMPONENTS = """
CREATE TABLE IF NOT EXISTS kit_components (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    kit_product_id       INTEGER NOT NULL
                             REFERENCES products(id) ON DELETE CASCADE,
    component_product_id INTEGER NOT NULL
                             REFERENCES products(id) ON DELETE CASCADE,
    quantity             INTEGER NOT NULL DEFAULT 1,
    notes                TEXT,
    created_at           DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(kit_product_id, component_product_id)
)
"""

_CREATE_IDX_KIT_PRODUCT = (
    "CREATE INDEX IF NOT EXISTS ix_kit_components_kit_product_id "
    "ON kit_components(kit_product_id)"
)

_CREATE_IDX_KIT_COMPONENT = (
    "CREATE INDEX IF NOT EXISTS ix_kit_components_component_product_id "
    "ON kit_components(component_product_id)"
)


def upgrade(connection) -> None:
    cursor = connection.cursor()

    # ── products – kit / fiscal columns ─────────────────────────────────
    for col_name, col_def in _PRODUCT_KIT_FISCAL_COLUMNS:
        if _column_exists(cursor, "products", col_name):
            continue
        try:
            cursor.execute(
                f"ALTER TABLE products ADD COLUMN {col_name} {col_def}"
            )
            print(f"Migration 016: added products.{col_name}")
        except Exception as exc:
            print(f"  WARNING: Could not add column 'products.{col_name}': {exc}")

    # Back-fill is_kit = 0 for existing products
    try:
        cursor.execute(
            "UPDATE products SET is_kit = 0 WHERE is_kit IS NULL"
        )
        print("Migration 016: back-filled is_kit = 0")
    except Exception as exc:
        print(f"  WARNING: Could not back-fill is_kit: {exc}")

    # ── kit_components table ─────────────────────────────────────────────
    try:
        cursor.execute(_CREATE_KIT_COMPONENTS)
        print("Migration 016: created table kit_components")
    except Exception as exc:
        print(f"  WARNING: Could not create kit_components: {exc}")

    for idx_sql in (_CREATE_IDX_KIT_PRODUCT, _CREATE_IDX_KIT_COMPONENT):
        try:
            cursor.execute(idx_sql)
        except Exception as exc:
            print(f"  WARNING: Could not create index: {exc}")

    print("Migration 016: created indexes on kit_components")

    connection.commit()
    print("Migration 016 applied.")


def downgrade(connection) -> None:
    print("Migration 016: no downgrade implemented (columns and table retained).")


if __name__ == "__main__":
    import sys
    import sqlite3

    if len(sys.argv) < 2:
        print("Usage: python 016_product_kit_fiscal.py <path_to_db>")
        sys.exit(1)

    conn = sqlite3.connect(sys.argv[1])
    upgrade(conn)
    conn.close()
