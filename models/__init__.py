"""
Models package initialization.
"""

from models.user import User
from models.branch import Branch
from models.product import Product
from models.category import Category
from models.supplier import Supplier
from models.product_relation import ProductRelation
from models.price_history import PriceHistory
from models.inventory import Inventory
from models.inventory_history import InventoryHistory
from models.movement import Movement, MovementType, MovementState, MovementPriority, MovementSource
from models.movement_state_history import MovementStateHistory
from models.saved_report import SavedReport

# Re-export Alert and HistoryEntry from their service modules
# These are defined in service files but we expose them here for convenience
from modules.alerts.service import Alert
from modules.history.service import HistoryEntry

__all__ = [
    "User", "Branch",
    "Product", "Category", "Supplier", "ProductRelation", "PriceHistory",
    "Inventory", "InventoryHistory",
    "Movement", "MovementType", "MovementState", "MovementPriority", "MovementSource",
    "MovementStateHistory",
    "SavedReport",
    "Alert", "HistoryEntry",
]
