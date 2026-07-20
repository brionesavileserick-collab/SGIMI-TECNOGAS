"""
Script to clear all data from database without altering table structure.
This script deletes all data from all tables while preserving the schema.
"""

import sqlite3
from pathlib import Path
import sys
import os


def get_db_path():
    """Find the database file path."""
    # Add parent directory to path to import settings
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    try:
        from core.settings import settings
        return settings.DATABASE_URL.replace("sqlite:///", "")
    except ImportError:
        # Fallback: look for database file in common locations
        possible_paths = [
            "sgimitecnogas.db",
            "database/sgimitecnogas.db",
            "../sgimitecnogas.db",
        ]
        for path in possible_paths:
            if Path(path).exists():
                return path
        
        # Try to find any .db file in the project
        for db_file in Path(".").rglob("*.db"):
            return str(db_file)
        
        return None


def clear_all_data():
    """Delete all data from all tables while preserving table structure."""
    
    db_path = get_db_path()
    
    if not db_path:
        print("Could not locate database file. Please specify the path manually.")
        return
    
    if not Path(db_path).exists():
        print(f"Database file not found: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Disable foreign key constraints temporarily to allow deletion in any order
    cursor.execute("PRAGMA foreign_keys=OFF")
    
    try:
        # Get list of all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        # Filter out sqlite internal tables
        tables = [t for t in tables if not t.startswith('sqlite_')]
        
        # Order tables to respect dependencies (delete children first)
        # Based on foreign key relationships in the schema
        deletion_order = [
            'history',           # depends on users
            'movements',         # depends on products, branches, users
            'inventory',         # depends on products, branches
            'alerts',            # no dependencies
            'inventory_count_items',  # depends on inventory_count_sessions
            'inventory_count_sessions',  # depends on branches
            'inventory_history', # depends on inventory
            'inventory_batches', # depends on inventory
            'kit_components',    # depends on products
            'product_change_history',  # depends on products
            'price_history',     # depends on products
            'product_relations', # depends on products
            'products',          # parent table
            'branches',          # parent table
            'users',             # parent table
            'categories',        # parent table
            'suppliers',         # parent table
            'saved_reports',     # depends on users
            'dashboard_widget_config',  # depends on users
            'branch_config_history',   # depends on branches
            'communications',   # communication tables
        ]
        
        # Delete from tables in the specified order (only if they exist)
        deleted_count = 0
        for table in deletion_order:
            if table in tables:
                cursor.execute(f"DELETE FROM {table}")
                deleted_count += cursor.rowcount
                print(f"Cleared table: {table} ({cursor.rowcount} rows)")
        
        # Delete from any remaining tables not in our list
        remaining_tables = [t for t in tables if t not in deletion_order]
        for table in remaining_tables:
            cursor.execute(f"DELETE FROM {table}")
            deleted_count += cursor.rowcount
            print(f"Cleared table: {table} ({cursor.rowcount} rows)")
        
        conn.commit()
        print(f"\nSuccessfully cleared {deleted_count} total rows from database.")
        print("Table structure preserved.")
        
        # Reset autoincrement sequences (if sqlite_sequence table exists)
        try:
            for table in tables:
                cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
            conn.commit()
            print("Autoincrement sequences reset.")
        except sqlite3.OperationalError:
            # sqlite_sequence table doesn't exist in this SQLite version
            print("Note: Autoincrement sequences not reset (sqlite_sequence table not available).")
        
    except Exception as e:
        conn.rollback()
        print(f"Error clearing data: {e}")
        raise
    finally:
        # Re-enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys=ON")
        conn.close()


if __name__ == '__main__':
    print("Starting database data cleanup...")
    print("This will delete ALL data from all tables while preserving structure.")
    
    # Check for command line argument to skip confirmation
    if len(sys.argv) > 1 and sys.argv[1] == '--force':
        print("Force mode enabled - proceeding with cleanup...")
        clear_all_data()
        print("Data cleanup completed.")
    else:
        try:
            confirm = input("Type 'yes' to confirm: ")
            if confirm.lower() == 'yes':
                clear_all_data()
                print("Data cleanup completed.")
            else:
                print("Operation cancelled.")
        except EOFError:
            print("\nCannot read input in this environment. Use --force flag to skip confirmation.")
            print("Example: python database/clear_data.py --force")
