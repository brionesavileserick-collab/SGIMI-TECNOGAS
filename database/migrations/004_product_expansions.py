"""
Migration 004 – Product expansions.

Creates new tables and adds new columns to ``products`` required by the
product-module expansion plan.

New tables
----------
categories          – Expansion 1 (Categorías)
suppliers           – Expansion 3 (Proveedor Default)
product_relations   – Expansion 7 (Productos Relacionados)
price_history       – Expansion 8 (Historial de Precios)

New columns on ``products``
---------------------------
category_id         INTEGER  NULL  FK → categories(id)   Exp 1
brand               VARCHAR(100) NULL                     Exp 2
default_supplier_id INTEGER  NULL  FK → suppliers(id)    Exp 3
details             TEXT     NULL                         Exp 4
internal_notes      TEXT     NULL                         Exp 5
global_min_stock    INTEGER  NULL                         Exp 6

All changes are idempotent: tables use CREATE … IF NOT EXISTS and each
ALTER TABLE is guarded by a PRAGMA table_info check.
"""

from typing import Tuple

# ---------------------------------------------------------------------------
# New columns for the existing ``products`` table
# (column_name, sql_type_and_constraint)
# ---------------------------------------------------------------------------
_PRODUCT_COLUMNS: Tuple[Tuple[str, str], ...] = (
    # Exp 1 – category FK (table created first in upgrade())
    ("category_id",         "INTEGER REFERENCES categories(id) ON DELETE SET NULL"),
    # Exp 2 – brand
    ("brand",               "VARCHAR(100)"),
    # Exp 3 – default supplier FK (table created first in upgrade())
    ("default_supplier_id", "INTEGER REFERENCES suppliers(id) ON DELETE SET NULL"),
    # Exp 4 – detailed description
    ("details",             "TEXT"),
    # Exp 5 – internal notes
    ("internal_notes",      "TEXT"),
    # Exp 6 – global minimum stock threshold
    ("global_min_stock",    "INTEGER"),
)


def _column_exists(cursor, table: str, column: str) -> bool:
    """Return True if *column* already exists in *table* (SQLite)."""
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def _table_exists(cursor, table: str) -> bool:
    """Return True if *table* exists in the SQLite database."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cursor.fetchone() is not None


def upgrade(connection) -> None:
    """Apply all product expansion changes."""
    cursor = connection.cursor()

    # ------------------------------------------------------------------
    # Part 1 – CREATE TABLE categories  (Expansion 1)
    # ------------------------------------------------------------------
    if not _table_exists(cursor, "categories"):
        cursor.execute('''
            CREATE TABLE categories (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        VARCHAR(100) NOT NULL UNIQUE,
                description TEXT,
                is_active   BOOLEAN NOT NULL DEFAULT 1,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at  DATETIME
            )
        ''')
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_categories_name ON categories(name)"
        )
        print("Migration 004: table 'categories' created.")
    else:
        print("Migration 004: table 'categories' already exists (skipped).")

    # ------------------------------------------------------------------
    # Part 2 – CREATE TABLE suppliers  (Expansion 3)
    # ------------------------------------------------------------------
    if not _table_exists(cursor, "suppliers"):
        cursor.execute('''
            CREATE TABLE suppliers (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         VARCHAR(200) NOT NULL UNIQUE,
                contact_name VARCHAR(100),
                phone        VARCHAR(30),
                email        VARCHAR(100),
                notes        TEXT,
                is_active    BOOLEAN NOT NULL DEFAULT 1,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_suppliers_name ON suppliers(name)"
        )
        print("Migration 004: table 'suppliers' created.")
    else:
        print("Migration 004: table 'suppliers' already exists (skipped).")

    # ------------------------------------------------------------------
    # Part 3 – ALTER TABLE products ADD COLUMN …
    # ------------------------------------------------------------------
    added: list = []
    skipped: list = []

    for col_name, col_def in _PRODUCT_COLUMNS:
        if _column_exists(cursor, "products", col_name):
            skipped.append(col_name)
            continue
        try:
            cursor.execute(
                f"ALTER TABLE products ADD COLUMN {col_name} {col_def}"
            )
            added.append(col_name)
        except Exception as exc:
            print(f"  WARNING: Could not add column 'products.{col_name}': {exc}")

    if added:
        print(f"Migration 004: columns added to products: {', '.join(added)}.")
    if skipped:
        print(f"Migration 004: products columns already present (skipped): {', '.join(skipped)}.")

    # ------------------------------------------------------------------
    # Part 4 – Indexes on new products columns
    # ------------------------------------------------------------------
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_products_category "
        "ON products(category_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_products_brand "
        "ON products(brand)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_products_supplier "
        "ON products(default_supplier_id)"
    )

    # ------------------------------------------------------------------
    # Part 5 – CREATE TABLE product_relations  (Expansion 7)
    # ------------------------------------------------------------------
    if not _table_exists(cursor, "product_relations"):
        cursor.execute('''
            CREATE TABLE product_relations (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id         INTEGER NOT NULL
                                       REFERENCES products(id) ON DELETE CASCADE,
                related_product_id INTEGER NOT NULL
                                       REFERENCES products(id) ON DELETE CASCADE,
                relation_type      VARCHAR(30),
                created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(product_id, related_product_id)
            )
        ''')
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_product_relations_product "
            "ON product_relations(product_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_product_relations_related "
            "ON product_relations(related_product_id)"
        )
        print("Migration 004: table 'product_relations' created.")
    else:
        print("Migration 004: table 'product_relations' already exists (skipped).")

    # ------------------------------------------------------------------
    # Part 6 – CREATE TABLE price_history  (Expansion 8)
    # ------------------------------------------------------------------
    if not _table_exists(cursor, "price_history"):
        cursor.execute('''
            CREATE TABLE price_history (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id          INTEGER NOT NULL
                                        REFERENCES products(id) ON DELETE CASCADE,
                previous_price      REAL,
                new_price           REAL,
                change_reason       VARCHAR(100),
                changed_by_user_id  INTEGER,
                created_at          DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_price_history_product "
            "ON price_history(product_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_price_history_created "
            "ON price_history(created_at)"
        )
        print("Migration 004: table 'price_history' created.")
    else:
        print("Migration 004: table 'price_history' already exists (skipped).")

    connection.commit()
    print("Migration 004_product_expansions.py applied successfully.")


def downgrade(connection) -> None:
    """
    Reverse migration 004.

    Drops the four new tables and recreates ``products`` without the new
    columns (SQLite does not support DROP COLUMN on older versions).
    Existing original-column data is preserved.
    """
    cursor = connection.cursor()

    # 1. Drop new tables (audit / relational – no critical data loss)
    for table in ("price_history", "product_relations"):
        cursor.execute(f"DROP TABLE IF EXISTS {table}")

    # 2. Recreate products without expansion columns
    cursor.execute("ALTER TABLE products RENAME TO products_backup_004")

    cursor.execute('''
        CREATE TABLE products (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            sku              VARCHAR(50) NOT NULL UNIQUE,
            name             VARCHAR(200) NOT NULL,
            description      TEXT,
            unit_of_measure  VARCHAR(20) NOT NULL DEFAULT 'unidad',
            unit_price       REAL,
            is_active        BOOLEAN DEFAULT 1,
            created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at       DATETIME
        )
    ''')

    cursor.execute('''
        INSERT INTO products (
            id, sku, name, description, unit_of_measure,
            unit_price, is_active, created_at, updated_at
        )
        SELECT
            id, sku, name, description, unit_of_measure,
            unit_price, is_active, created_at, updated_at
        FROM products_backup_004
    ''')

    cursor.execute("DROP TABLE IF EXISTS products_backup_004")

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_products_name ON products(name)"
    )

    # 3. Drop lookup tables (categories / suppliers) last to avoid FK issues
    for table in ("categories", "suppliers"):
        cursor.execute(f"DROP TABLE IF EXISTS {table}")

    connection.commit()
    print("Migration 004_product_expansions.py rolled back successfully.")
