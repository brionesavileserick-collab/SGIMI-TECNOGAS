"""
Models package initialization.
"""

from models.user import User
from models.branch import Branch
from models.product import Product
from models.inventory import Inventory
from models.inventory_history import InventoryHistory
from models.movement import Movement, MovementType, MovementState

# Re-export Alert and HistoryEntry from their service modules
# These are defined in service files but we expose them here for convenience
from modules.alerts.service import Alert
from modules.history.service import HistoryEntry

__all__ = [
    "User", "Branch", "Product", "Inventory", "InventoryHistory",
    "Movement", "MovementType", "MovementState",
    "Alert", "HistoryEntry"
]
