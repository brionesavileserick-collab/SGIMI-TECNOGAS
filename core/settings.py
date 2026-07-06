"""
Application settings and configuration constants.
"""

import os
from typing import Optional


class Settings:
    """Application settings."""

    # Application
    APP_NAME: str = "SGIMI TECNOGAS"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///sgimi_tecnogas.db")

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


settings = Settings()
