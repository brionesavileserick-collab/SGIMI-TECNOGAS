"""
Migration 014 – Fase 1: Jerarquía de Categorías + Status de Descontinuación.

categories table:
  + parent_category_id  INTEGER  NULL  (FK → categories.id)
  + level               INTEGER  NOT NULL  DEFAULT 0
  + path                VARCHAR(255)  NULL

products table:
  + product_status          VARCHAR(30)   NOT NULL  DEFAULT 'active'
  + discontinued_at         DATETIME      NULL
  + replacement_product_id  INTEGER       NULL  (FK → products.id)

All changes are additive (ALTER TABLE ADD COLUMN) and idempotent.
"""

from typing import Tuple


def _column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


_CATEGORY_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("parent_category_id", "INTEGER"),
    ("level",              "INTEGER NOT NULL DEFAULT 0"),
    ("path",               "VARCHAR(255)"),
)

_PRODUCT_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("product_status",         "VARCHAR(30) NOT NULL DEFAULT 'active'"),
    ("discontinued_at",        "DATETIME"),
    ("replacement_product_id", "INTEGER"),
)


def upgrade(connection) -> None:
    cursor = connection.cursor()

    # ── categories ──────────────────────────────────────────────────────
    for col_name, col_def in _CATEGORY_COLUMNS:
        if _column_exists(cursor, "categories", col_name):
            continue
        try:
            cursor.execute(
                f"ALTER TABLE categories ADD COLUMN {col_name} {col_def}"
            )
            print(f"Migration 014: added categories.{col_name}")
        except Exception as exc:
            print(f"  WARNING: Could not add column 'categories.{col_name}': {exc}")

    # ── products ────────────────────────────────────────────────────────
    for col_name, col_def in _PRODUCT_COLUMNS:
        if _column_exists(cursor, "products", col_name):
            continue
        try:
            cursor.execute(
                f"ALTER TABLE products ADD COLUMN {col_name} {col_def}"
            )
            print(f"Migration 014: added products.{col_name}")
        except Exception as exc:
            print(f"  WARNING: Could not add column 'products.{col_name}': {exc}")

    # Back-fill level=0 and path=name for existing root categories
    try:
        cursor.execute(
            "UPDATE categories SET level = 0 WHERE level IS NULL"
        )
        cursor.execute(
            "UPDATE categories SET path = name "
            "WHERE path IS NULL AND parent_category_id IS NULL"
        )
        print("Migration 014: back-filled level/path on root categories")
    except Exception as exc:
        print(f"  WARNING: Could not back-fill category hierarchy: {exc}")

    # Back-fill product_status = 'active' for existing products
    try:
        cursor.execute(
            "UPDATE products SET product_status = 'active' "
            "WHERE product_status IS NULL"
        )
        print("Migration 014: back-filled product_status = 'active'")
    except Exception as exc:
        print(f"  WARNING: Could not back-fill product_status: {exc}")

    connection.commit()
    print("Migration 014 applied.")


def downgrade(connection) -> None:
    print("Migration 014: no downgrade implemented (columns retained).")


if __name__ == "__main__":
    import sys
    import sqlite3

    if len(sys.argv) < 2:
        print("Usage: python 014_product_category_hierarchy.py <path_to_db>")
        sys.exit(1)

    conn = sqlite3.connect(sys.argv[1])
    upgrade(conn)
    conn.close()
