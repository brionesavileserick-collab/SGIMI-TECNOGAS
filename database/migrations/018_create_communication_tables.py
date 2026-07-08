"""Migration 018 – Create communication tables."""

import sqlite3


def upgrade(connection):
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS communications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject VARCHAR(200) NOT NULL,
            body TEXT NOT NULL,
            communication_type VARCHAR(30) NOT NULL DEFAULT 'mensaje',
            priority VARCHAR(20) NOT NULL DEFAULT 'normal',
            sender_id INTEGER,
            sender_branch_id INTEGER,
            related_movement_id INTEGER,
            related_alert_id INTEGER,
            is_system BOOLEAN NOT NULL DEFAULT 0,
            parent_message_id INTEGER,
            confirmation_required BOOLEAN NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME,
            FOREIGN KEY(parent_message_id) REFERENCES communications(id) ON DELETE SET NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS communication_recipients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            communication_id INTEGER NOT NULL,
            recipient_id INTEGER,
            recipient_branch_id INTEGER,
            status VARCHAR(20) NOT NULL DEFAULT 'pendiente',
            read_at DATETIME,
            archived_at DATETIME,
            confirmation_sent BOOLEAN NOT NULL DEFAULT 0,
            confirmation_received_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(communication_id) REFERENCES communications(id) ON DELETE CASCADE,
            UNIQUE(communication_id, recipient_id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS communication_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            communication_id INTEGER NOT NULL,
            filename VARCHAR(255) NOT NULL,
            file_path VARCHAR(500) NOT NULL,
            file_size INTEGER,
            mime_type VARCHAR(100),
            uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(communication_id) REFERENCES communications(id) ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS communication_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            subject_template VARCHAR(200),
            body_template TEXT NOT NULL,
            communication_type VARCHAR(30),
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_communications_sender ON communications(sender_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_communications_type ON communications(communication_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_comm_recipients_recipient ON communication_recipients(recipient_id, status)")
    connection.commit()
