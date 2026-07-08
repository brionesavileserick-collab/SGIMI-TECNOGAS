"""
Models package initialization.
"""

from models.user import User
from models.branch import Branch
from models.category import Category
from models.supplier import Supplier
from models.product_relation import ProductRelation
from models.price_history import PriceHistory
from models.product_change_history import ProductChangeHistory
from models.kit_component import KitComponent
from models.product import Product
from models.inventory import Inventory
from models.inventory_history import InventoryHistory
from models.inventory_count_session import InventoryCountSession
from models.inventory_count_item import InventoryCountItem
from models.inventory_batch import InventoryBatch
from models.movement import Movement, MovementType, MovementState, MovementPriority, MovementSource
from models.movement_state_history import MovementStateHistory
from models.saved_report import SavedReport
from models.dashboard_widget_config import DashboardWidgetConfig, WIDGET_KEYS, DEFAULT_POSITIONS
from models.branch_config_history import BranchConfigHistory

# Re-export Alert and HistoryEntry from their service modules
# These are defined in service files but we expose them here for convenience
from modules.alerts.service import Alert
from modules.history.service import HistoryEntry

__all__ = [
    "User", "Branch",
    "Product", "Category", "Supplier", "ProductRelation", "PriceHistory", "ProductChangeHistory", "KitComponent",
    "Inventory", "InventoryHistory", "InventoryCountSession", "InventoryCountItem", "InventoryBatch",
    "Movement", "MovementType", "MovementState", "MovementPriority", "MovementSource",
    "MovementStateHistory",
    "SavedReport",
    "DashboardWidgetConfig", "WIDGET_KEYS", "DEFAULT_POSITIONS",
    "BranchConfigHistory",
    "Alert", "HistoryEntry",
]
