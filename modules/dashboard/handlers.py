"""
Dashboard event handlers - React to events and update dashboard.

Subscriptions:
  Original : MOVEMENT_VALIDATED, INVENTORY_UPDATED, ALERT_GENERATED
  Exp 8    : MOVEMENT_CREATED, MOVEMENT_CANCELLED, MOVEMENT_REVERSED
  Exp 6    : TRANSFER_SENT, TRANSFER_RECEIVED, TRANSFER_REJECTED
  Exp 8    : STOCK_REORDER_NEEDED, STOCK_CRITICAL
"""

from typing import Any, Callable, Dict
from sqlalchemy.orm import Session
from core.event_bus import event_bus
from core.settings import settings
import logging

logger = logging.getLogger(__name__)


class DashboardHandlers:
    """Event handlers for dashboard module."""

    def __init__(self, db: Session):
        self.db = db
        self._refresh_callback: Callable = None
        # Optional separate callback for urgent-alert badge refresh
        self._alert_badge_callback: Callable = None
        # Optional callback for transfer-widget refresh only
        self._transfer_callback: Callable = None
        self._register_handlers()
        logger.info("Dashboard handlers registered")

    # ------------------------------------------------------------------
    # Callback registration
    # ------------------------------------------------------------------

    def set_refresh_callback(self, callback: Callable) -> None:
        """Set the callback that fully refreshes the dashboard UI."""
        self._refresh_callback = callback

    def set_alert_badge_callback(self, callback: Callable) -> None:
        """Set a lightweight callback that only updates alert badge counts."""
        self._alert_badge_callback = callback

    def set_transfer_callback(self, callback: Callable) -> None:
        """Set a callback that only refreshes the transfers widget."""
        self._transfer_callback = callback

    # ------------------------------------------------------------------
    # Handler registration / deregistration
    # ------------------------------------------------------------------

    def _register_handlers(self) -> None:
        """Subscribe to all relevant events."""
        ev = settings.Events

        # --- original ---
        event_bus.subscribe(ev.MOVEMENT_VALIDATED, self.handle_movement_change)
        event_bus.subscribe(ev.INVENTORY_UPDATED,  self.handle_inventory_change)
        event_bus.subscribe(ev.ALERT_GENERATED,    self.handle_alert)

        # --- Exp 8: movement lifecycle ---
        event_bus.subscribe(ev.MOVEMENT_CREATED,   self.handle_movement_change)
        event_bus.subscribe(ev.MOVEMENT_CANCELLED, self.handle_movement_change)
        event_bus.subscribe(ev.MOVEMENT_REVERSED,  self.handle_movement_change)

        # --- Exp 6: transfer lifecycle ---
        event_bus.subscribe(ev.TRANSFER_SENT,     self.handle_transfer_event)
        event_bus.subscribe(ev.TRANSFER_RECEIVED, self.handle_transfer_event)
        event_bus.subscribe(ev.TRANSFER_REJECTED, self.handle_transfer_event)

        # --- Exp 8: stock urgency ---
        event_bus.subscribe(ev.STOCK_REORDER_NEEDED, self.handle_urgent_stock)
        event_bus.subscribe(ev.STOCK_CRITICAL,        self.handle_urgent_stock)

    def unregister_handlers(self) -> None:
        """Unsubscribe from all events (call before destroying the widget)."""
        ev = settings.Events

        event_bus.unsubscribe(ev.MOVEMENT_VALIDATED, self.handle_movement_change)
        event_bus.unsubscribe(ev.INVENTORY_UPDATED,  self.handle_inventory_change)
        event_bus.unsubscribe(ev.ALERT_GENERATED,    self.handle_alert)

        event_bus.unsubscribe(ev.MOVEMENT_CREATED,   self.handle_movement_change)
        event_bus.unsubscribe(ev.MOVEMENT_CANCELLED, self.handle_movement_change)
        event_bus.unsubscribe(ev.MOVEMENT_REVERSED,  self.handle_movement_change)

        event_bus.unsubscribe(ev.TRANSFER_SENT,     self.handle_transfer_event)
        event_bus.unsubscribe(ev.TRANSFER_RECEIVED, self.handle_transfer_event)
        event_bus.unsubscribe(ev.TRANSFER_REJECTED, self.handle_transfer_event)

        event_bus.unsubscribe(ev.STOCK_REORDER_NEEDED, self.handle_urgent_stock)
        event_bus.unsubscribe(ev.STOCK_CRITICAL,        self.handle_urgent_stock)

        logger.info("Dashboard handlers unregistered")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def handle_movement_change(self, data: Dict[str, Any]) -> None:
        """Handle any movement lifecycle event (created / validated / cancelled / reversed)."""
        logger.info(f"Dashboard: movement event → {data}")
        self._trigger_refresh()

    def handle_inventory_change(self, data: Dict[str, Any]) -> None:
        """Handle inventory update events."""
        logger.info(f"Dashboard: inventory event → {data}")
        self._trigger_refresh()

    def handle_alert(self, data: Dict[str, Any]) -> None:
        """Handle generic alert events – refresh badges first, then full UI."""
        logger.info(f"Dashboard: alert event → {data}")
        self._trigger_alert_badge()
        self._trigger_refresh()

    def handle_transfer_event(self, data: Dict[str, Any]) -> None:
        """
        Handle transfer sent / received / rejected.
        Refreshes the transfers widget immediately; full refresh follows.
        """
        logger.info(f"Dashboard: transfer event → {data}")
        self._trigger_transfer_refresh()
        self._trigger_refresh()

    def handle_urgent_stock(self, data: Dict[str, Any]) -> None:
        """Handle urgent stock events – update alert badge immediately."""
        logger.info(f"Dashboard: urgent stock event → {data}")
        self._trigger_alert_badge()
        self._trigger_refresh()

    # ------------------------------------------------------------------
    # Internal trigger helpers
    # ------------------------------------------------------------------

    def _trigger_refresh(self) -> None:
        if self._refresh_callback:
            try:
                self._refresh_callback()
            except Exception as e:
                logger.error(f"Error in dashboard refresh callback: {e}")

    def _trigger_alert_badge(self) -> None:
        if self._alert_badge_callback:
            try:
                self._alert_badge_callback()
            except Exception as e:
                logger.error(f"Error in alert badge callback: {e}")

    def _trigger_transfer_refresh(self) -> None:
        if self._transfer_callback:
            try:
                self._transfer_callback()
            except Exception as e:
                logger.error(f"Error in transfer callback: {e}")


def setup_dashboard_handlers(db: Session) -> DashboardHandlers:
    """Setup and return dashboard handlers."""
    return DashboardHandlers(db)
