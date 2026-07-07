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

        # Branch events
        BRANCH_CREATED = "branch.created"
        BRANCH_UPDATED = "branch.updated"
        BRANCH_DELETED = "branch.deleted"
        BRANCH_STATUS_CHANGED = "branch.status_changed"
        BRANCH_MANAGER_ASSIGNED = "branch.manager_assigned"

        # Movement events
        MOVEMENT_CREATED = "movement.created"
        MOVEMENT_VALIDATED = "movement.validated"
        MOVEMENT_REJECTED = "movement.rejected"

        # Inventory events
        INVENTORY_UPDATED = "inventory.updated"
        INVENTORY_COUNTED = "inventory.counted"

        # Transfer events
        TRANSFER_SENT = "transfer.sent"
        TRANSFER_RECEIVED = "transfer.received"

        # Alert events
        ALERT_GENERATED = "alert.generated"

        # User events
        USER_CREATED = "user.created"
        USER_UPDATED = "user.updated"
        USER_DELETED = "user.deleted"


settings = Settings()
