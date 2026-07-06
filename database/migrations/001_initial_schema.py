"""
Initial database schema migration.

This migration creates all necessary tables for the inventory management system.
Tables: users, branches, products, inventory, movements, alerts, history
"""

from datetime import datetime


def upgrade(connection):
    """Create initial schema."""
    cursor = connection.cursor()

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            registration_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1
        )
    ''')

    # Branches table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS branches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL UNIQUE,
            address VARCHAR(255),
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME
        )
    ''')

    # Products table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku VARCHAR(50) NOT NULL UNIQUE,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            unit_of_measure VARCHAR(20) NOT NULL DEFAULT 'unidad',
            unit_price FLOAT,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME
        )
    ''')

    # Inventory table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            branch_id INTEGER NOT NULL,
            physical_stock INTEGER DEFAULT 0 NOT NULL,
            digital_stock INTEGER DEFAULT 0 NOT NULL,
            min_stock INTEGER DEFAULT 0,
            max_stock INTEGER,
            last_count_date DATETIME,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (branch_id) REFERENCES branches(id) ON DELETE CASCADE,
            UNIQUE(product_id, branch_id)
        )
    ''')

    # Movements table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            branch_id INTEGER NOT NULL,
            destination_branch_id INTEGER,
            user_id INTEGER,
            movement_type VARCHAR(20) NOT NULL,
            quantity INTEGER NOT NULL,
            state VARCHAR(20) DEFAULT 'pendiente' NOT NULL,
            reason TEXT,
            notes TEXT,
            validated_at DATETIME,
            validated_by INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (branch_id) REFERENCES branches(id) ON DELETE CASCADE,
            FOREIGN KEY (destination_branch_id) REFERENCES branches(id) ON DELETE SET NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (validated_by) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')

    # Alerts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type VARCHAR(50) NOT NULL,
            severity VARCHAR(20) NOT NULL,
            title VARCHAR(200) NOT NULL,
            message TEXT NOT NULL,
            product_id INTEGER,
            branch_id INTEGER,
            movement_id INTEGER,
            is_read BOOLEAN DEFAULT 0,
            is_resolved BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            resolved_at DATETIME
        )
    ''')

    # History table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type VARCHAR(100) NOT NULL,
            entity_type VARCHAR(50),
            entity_id INTEGER,
            user_id INTEGER,
            action VARCHAR(100) NOT NULL,
            details TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_branches_name ON branches(name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_name ON products(name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_inventory_product_branch ON inventory(product_id, branch_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_movements_state ON movements(state)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_movements_type ON movements(movement_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_event ON history(event_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_history_created ON history(created_at)')

    connection.commit()
    print("Migration 001_initial_schema.py applied successfully.")


def downgrade(connection):
    """Drop all tables."""
    cursor = connection.cursor()

    tables = ['history', 'alerts', 'movements', 'inventory', 'products', 'branches', 'users']

    for table in tables:
        cursor.execute(f'DROP TABLE IF EXISTS {table}')

    connection.commit()
    print("Migration 001_initial_schema.py rolled back successfully.")


if __name__ == '__main__':
    import sqlite3

    # For testing
    conn = sqlite3.connect('test.db')
    upgrade(conn)
    conn.close()
