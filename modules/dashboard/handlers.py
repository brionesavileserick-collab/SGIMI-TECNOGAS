"""
Dashboard event handlers - React to events and update dashboard.
"""

from typing import Dict, Any
from sqlalchemy.orm import Session
from core.event_bus import event_bus
from core.settings import settings
import logging

logger = logging.getLogger(__name__)


class DashboardHandlers:
    """Event handlers for dashboard module."""

    def __init__(self, db: Session):
        self.db = db
        self._register_handlers()
        logger.info("Dashboard handlers registered")

    def _register_handlers(self):
        """Register all event handlers."""
        event_bus.subscribe(settings.Events.MOVEMENT_VALIDATED, self.handle_movement_change)
        event_bus.subscribe(settings.Events.INVENTORY_UPDATED, self.handle_inventory_change)
        event_bus.subscribe(settings.Events.ALERT_GENERATED, self.handle_alert)

    def handle_movement_change(self, data: Dict[str, Any]):
        """Handle movement-related events."""
        logger.info(f"Movement change detected in dashboard: {data}")
        # Dashboard metrics would be recalculated on next refresh

    def handle_inventory_change(self, data: Dict[str, Any]):
        """Handle inventory-related events."""
        logger.info(f"Inventory change detected in dashboard: {data}")
        # Dashboard metrics would be recalculated on next refresh

    def handle_alert(self, data: Dict[str, Any]):
        """Handle alert events."""
        logger.info(f"Alert received in dashboard: {data}")
        # Could display alert notifications or update alert count

    def unregister_handlers(self):
        """Unregister all event handlers."""
        event_bus.unsubscribe(settings.Events.MOVEMENT_VALIDATED, self.handle_movement_change)
        event_bus.unsubscribe(settings.Events.INVENTORY_UPDATED, self.handle_inventory_change)
        event_bus.unsubscribe(settings.Events.ALERT_GENERATED, self.handle_alert)
        logger.info("Dashboard handlers unregistered")


def setup_dashboard_handlers(db: Session) -> DashboardHandlers:
    """Setup and return dashboard handlers."""
    return DashboardHandlers(db)
