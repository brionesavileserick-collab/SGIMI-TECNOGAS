"""
Application settings and configuration constants.
"""

import os
import sys
from pathlib import Path
from typing import Optional


def get_user_data_dir() -> Path:
    """Return a writable per-user application data directory."""
    app_folder = "SGIMI TECNOGAS"

    if sys.platform.startswith("win"):
        base_dir = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or str(Path.home())
        return Path(base_dir) / app_folder

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / app_folder

    base_dir = os.getenv("XDG_DATA_HOME")
    if base_dir:
        return Path(base_dir) / "sgimi-tecnogas"
    return Path.home() / ".local" / "share" / "sgimi-tecnogas"


def get_default_database_url() -> str:
    """Return the default SQLite URL in a writable user data directory."""
    data_dir = get_user_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "sgimi_tecnogas.db"
    return f"sqlite:///{db_path.as_posix()}"


class Settings:
    """Application settings."""

    # Application
    APP_NAME: str = "SGIMI TECNOGAS"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    USER_DATA_DIR: Path = get_user_data_dir()
    LOG_DIR: Path = USER_DATA_DIR / "logs"
    LOG_FILE: Path = LOG_DIR / "sgimi.log"

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", get_default_database_url())

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    PASSWORD_MIN_LENGTH: int = 6

    # Inventory thresholds
    LOW_STOCK_THRESHOLD: int = 10
    DISCREPANCY_THRESHOLD: float = 0.05  # 5% tolerance

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # Event names
    class Events:
        # Product events
        PRODUCT_CREATED = "product.created"
        PRODUCT_UPDATED = "product.updated"
        PRODUCT_DELETED = "product.deleted"
        PRICE_CHANGED = "product.price_changed"

        # Branch events
        BRANCH_CREATED = "branch.created"
        BRANCH_UPDATED = "branch.updated"
        BRANCH_DELETED = "branch.deleted"
        BRANCH_STATUS_CHANGED = "branch.status_changed"
        BRANCH_MANAGER_ASSIGNED = "branch.manager_assigned"
        # Branch – count scheduling events
        BRANCH_COUNT_SCHEDULED = "branch.count_scheduled"
        COUNT_SESSION_OVERDUE = "branch.count_overdue"
        BRANCH_COUNT_OVERDUE = COUNT_SESSION_OVERDUE
        # Branch – capacity events
        BRANCH_CAPACITY_WARNING = "branch.capacity_warning"
        BRANCH_CAPACITY_EXCEEDED = "branch.capacity_exceeded"

        # Movement events
        MOVEMENT_CREATED = "movement.created"
        MOVEMENT_VALIDATED = "movement.validated"
        MOVEMENT_REJECTED = "movement.rejected"
        MOVEMENT_PENDING_ADMIN_APPROVAL = "movement.pending_admin_approval"
        MOVEMENT_PENDING_MANAGER_APPROVAL = "movement.pending_manager_approval"
        MOVEMENT_ADMIN_APPROVED = "movement.admin_approved"
        MOVEMENT_MANAGER_APPROVED = "movement.manager_approved"
        MOVEMENT_APPROVAL_REJECTED = "movement.approval_rejected"

        # Inventory events
        INVENTORY_UPDATED = "inventory.updated"
        INVENTORY_COUNTED = "inventory.counted"
        STOCK_REORDER_NEEDED = "inventory.stock_reorder_needed"
        STOCK_CRITICAL = "inventory.stock_critical"
        STOCK_EXCEEDED_MAX = "inventory.stock_exceeded_max"
        DISCREPANCY_TOLERANCE_BREACHED = "inventory.discrepancy_tolerance_breached"
        STOCK_IN_TRANSIT_ADDED = "inventory.in_transit_added"
        STOCK_IN_TRANSIT_RECEIVED = "inventory.in_transit_received"

        # Count session workflow events
        COUNT_SESSION_CREATED = "inventory.count_session_created"
        COUNT_SESSION_STARTED = "inventory.count_session_started"
        COUNT_SESSION_COMPLETED = "inventory.count_session_completed"
        COUNT_ITEM_RECORDED = "inventory.count_item_recorded"

        # Batch events
        BATCH_ADDED = "inventory.batch_added"
        BATCH_EXPIRING = "inventory.batch_expiring"
        BATCH_CONSUMED = "inventory.batch_consumed"

        # Transfer events
        TRANSFER_SENT = "transfer.sent"
        TRANSFER_RECEIVED = "transfer.received"
        TRANSFER_REJECTED = "transfer.rejected"

        # Movement cancellation / reversal events
        MOVEMENT_CANCELLED = "movement.cancelled"
        MOVEMENT_REVERSED = "movement.reversed"

        # Alert events
        ALERT_GENERATED = "alert.generated"

        # Communication events
        COMMUNICATION_SENT = "communication.sent"
        COMMUNICATION_RECEIVED = "communication.received"
        COMMUNICATION_READ = "communication.read"
        COMMUNICATION_ARCHIVED = "communication.archived"
        COMMUNICATION_REPLY = "communication.reply"
        COMMUNICATION_CONFIRMATION_REQUESTED = "communication.confirmation_requested"
        COMMUNICATION_CONFIRMATION_RECEIVED = "communication.confirmation_received"
        ANNOUNCEMENT_BROADCAST = "communication.announcement_broadcast"

        # User events
        USER_CREATED = "user.created"
        USER_UPDATED = "user.updated"
        USER_DELETED = "user.deleted"
        USER_ROLE_CHANGED = "user.role_changed"
        USER_ASSIGNED_TO_BRANCH = "user.assigned_to_branch"
        USER_FIRST_LOGIN = "user.first_login"

        # Product expansion events
        PRODUCT_VARIANT_CREATED = "product.variant_created"
        PRODUCT_DISCONTINUED = "product.discontinued"
        PRODUCT_REACTIVATED = "product.reactivated"
        KIT_COMPONENT_ADDED = "product.kit_component_added"
        KIT_COMPONENT_REMOVED = "product.kit_component_removed"


settings = Settings()
