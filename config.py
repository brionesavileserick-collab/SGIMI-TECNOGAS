"""
Application configuration file.
"""

import logging
import os
from logging.config import dictConfig
from core.settings import settings

# Logging configuration
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        },
        "detailed": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "default",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "filename": str(settings.LOG_FILE),
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5
        }
    },
    "loggers": {
        "": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
            "propagate": True
        }
    }
}


def setup_logging():
    """Configure application logging."""
    # Create logs directory if it doesn't exist
    os.makedirs(settings.LOG_DIR, exist_ok=True)
    dictConfig(LOGGING_CONFIG)


# Application metadata
APP_TITLE = "SGIMI TECNOGAS - Sistema de Gestion de Inventario Multi-Sucursal"
APP_DESCRIPTION = "Sistema de gestion de inventario multi-sucursal basado en eventos"
APP_VERSION = "1.0.0"

# Movement types
MOVEMENT_TYPES = {
    "entrada": "Entrada de inventario",
    "salida": "Salida de inventario",
    "ajuste": "Ajuste de inventario",
    "transferencia": "Transferencia entre sucursales"
}

# Movement states
MOVEMENT_STATES = {
    "pendiente": "Pendiente de validacion",
    "validado": "Validado",
    "rechazado": "Rechazado"
}

# Alert types
ALERT_TYPES = {
    "low_stock": "Stock bajo",
    "discrepancy": "Discrepancia detectada",
    "validation_failed": "Validacion fallida",
    "transfer_pending": "Transferencia pendiente",
    "manual": "Alerta manual",           # Exp 6
}

# Alert severities
ALERT_SEVERITIES = {
    "info": "Informacion",
    "warning": "Advertencia",
    "critical": "Critico"
}

# Alert priorities (Exp 10)
ALERT_PRIORITIES = {
    "low": "Baja",
    "normal": "Normal",
    "high": "Alta",
}

# History retention policy by entity type (days)
# Expansion 12: Retención personalizada por tipo de entidad
RETENTION_DAYS = {
    "system": 180,           # System logs: 6 months
    "movement": 365,         # Movements: 1 year
    "inventory": 180,        # Inventory: 6 months
    "product": 99999,        # Products: essentially forever (27+ years)
    "branch": 99999,         # Branches: essentially forever
    "branch_config": 365,    # Branch config changes: 1 year
    "alert": 90,             # Alerts: 3 months
    "user": 99999,           # User records: essentially forever
}
