"""Add role-based user management fields and audit table."""

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if not cursor.fetchone():
        return

    columns = [row[1] for row in cursor.execute("PRAGMA table_info(users)")]

    if 'role' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'empleado'")

    if 'assigned_branch_id' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN assigned_branch_id INTEGER REFERENCES branches(id)")

    if 'is_branch_manager' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_branch_manager BOOLEAN NOT NULL DEFAULT 0")

    if 'created_by' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN created_by INTEGER REFERENCES users(id)")

    if 'last_activity' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN last_activity DATETIME")

    if 'is_first_login' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_first_login BOOLEAN NOT NULL DEFAULT 1")

    if 'is_admin' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0")

    cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
    admin_count = cursor.fetchone()[0]
    if admin_count:
        cursor.execute("UPDATE users SET role='admin', assigned_branch_id=NULL WHERE is_admin=1")

    cursor.execute("UPDATE users SET role='empleado' WHERE COALESCE(role, '')='' OR role IS NULL")
    cursor.execute("UPDATE users SET is_branch_manager=0 WHERE is_branch_manager IS NULL")
    cursor.execute("UPDATE users SET is_first_login=1 WHERE is_first_login IS NULL")

    cursor.execute("CREATE TABLE IF NOT EXISTS user_activity_log (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), action VARCHAR(50) NOT NULL, target_user_id INTEGER, details TEXT, ip_address VARCHAR(50), created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")
    conn.commit()
