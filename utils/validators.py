"""
Validation utilities for data validation.
"""

import re
from typing import Optional, Tuple
from datetime import datetime


def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    """
    Validate email format.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not email:
        return False, "El email es requerido"

    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, "Formato de email invalido"

    return True, None


def validate_sku(sku: str) -> Tuple[bool, Optional[str]]:
    """
    Validate SKU format.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not sku:
        return False, "El SKU es requerido"

    if len(sku) < 2:
        return False, "El SKU debe tener al menos 2 caracteres"

    if len(sku) > 50:
        return False, "El SKU no puede tener mas de 50 caracteres"

    # Allow alphanumeric, hyphens, and underscores
    if not re.match(r'^[a-zA-Z0-9_-]+$', sku):
        return False, "El SKU solo puede contener letras, numeros, guiones y guiones bajos"

    return True, None


def validate_name(name: str, field_name: str = "Nombre") -> Tuple[bool, Optional[str]]:
    """
    Validate name field.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not name:
        return False, f"El {field_name.lower()} es requerido"

    name = name.strip()

    if len(name) < 2:
        return False, f"El {field_name.lower()} debe tener al menos 2 caracteres"

    if len(name) > 200:
        return False, f"El {field_name.lower()} no puede tener mas de 200 caracteres"

    return True, None


def validate_quantity(quantity: int) -> Tuple[bool, Optional[str]]:
    """
    Validate quantity for movements.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if quantity is None:
        return False, "La cantidad es requerida"

    if not isinstance(quantity, (int, float)):
        return False, "La cantidad debe ser un numero"

    if quantity < 0:
        return False, "La cantidad no puede ser negativa"

    if quantity > 999999:
        return False, "La cantidad excede el limite maximo"

    return True, None


def validate_password(password: str, min_length: int = 6) -> Tuple[bool, Optional[str]]:
    """
    Validate password strength.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not password:
        return False, "La contrasena es requerida"

    if len(password) < min_length:
        return False, f"La contrasena debe tener al menos {min_length} caracteres"

    return True, None


def validate_stock_value(value: int, min_value: int = 0) -> Tuple[bool, Optional[str]]:
    """
    Validate stock value.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if value is None:
        return False, "El valor de stock es requerido"

    if not isinstance(value, (int, float)):
        return False, "El valor debe ser numerico"

    if value < min_value:
        return False, f"El valor no puede ser menor a {min_value}"

    if value > 999999:
        return False, "El valor excede el limite maximo"

    return True, None


def validate_date_range(date_from: datetime, date_to: datetime) -> Tuple[bool, Optional[str]]:
    """
    Validate date range.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if date_from and date_to:
        if date_from > date_to:
            return False, "La fecha inicial no puede ser posterior a la fecha final"

    return True, None


def validate_phone(phone: str) -> Tuple[bool, Optional[str]]:
    """
    Validate phone number format.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not phone:
        return True, None  # Phone is optional

    # Remove common separators
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)

    # Check if only digits remain and has valid length
    if not cleaned.isdigit():
        return False, "El telefono solo puede contener numeros"

    if len(cleaned) < 7 or len(cleaned) > 15:
        return False, "El telefono debe tener entre 7 y 15 digitos"

    return True, None


def validate_movement_type(movement_type: str) -> Tuple[bool, Optional[str]]:
    """
    Validate movement type.

    Returns:
        Tuple of (is_valid, error_message)
    """
    valid_types = ["entrada", "salida", "ajuste", "transferencia"]

    if not movement_type:
        return False, "El tipo de movimiento es requerido"

    if movement_type not in valid_types:
        return False, f"Tipo de movimiento invalido. Validos: {', '.join(valid_types)}"

    return True, None


def validate_movement_state(state: str) -> Tuple[bool, Optional[str]]:
    """
    Validate movement state.

    Returns:
        Tuple of (is_valid, error_message)
    """
    valid_states = ["pendiente", "validado", "rechazado"]

    if not state:
        return False, "El estado es requerido"

    if state not in valid_states:
        return False, f"Estado invalido. Validos: {', '.join(valid_states)}"

    return True, None


def sanitize_string(value: str, max_length: int = None) -> str:
    """
    Sanitize string input.

    Returns:
        Sanitized string
    """
    if not value:
        return ""

    value = value.strip()

    if max_length:
        value = value[:max_length]

    return value
