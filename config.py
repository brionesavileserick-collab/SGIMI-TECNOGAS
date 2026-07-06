"""
Application configuration file.
"""

import logging
import os
from logging.config import dictConfig

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
            "filename": "logs/sgimi.log",
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
    os.makedirs("logs", exist_ok=True)
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
    "transfer_pending": "Transferencia pendiente"
}

# Alert severities
ALERT_SEVERITIES = {
    "info": "Informacion",
    "warning": "Advertencia",
    "critical": "Critico"
}
