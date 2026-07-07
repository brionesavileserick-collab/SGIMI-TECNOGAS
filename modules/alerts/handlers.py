"""
Alerts event handlers - React to events and generate alerts.

Expansions implemented:
  Exp 2  – Notificación visual al generar una alerta (ALERT_GENERATED emite señal
            para que routes.py refresque el badge; popup para críticas via callback)
  Exp 10 – Timer que revisa y marca alertas vencidas cada N minutos

New events consumed (architecture plan):
  STOCK_CRITICAL          → alerta de stock crítico (severity=critical)
  TRANSFER_REJECTED       → alerta de transferencia rechazada
  MOVEMENT_CREATED (type=transferencia, state=pendiente) → transfer_pending alert

Original events (unchanged behavior):
  INVENTORY_UPDATED       → low_stock + discrepancy alerts
  MOVEMENT_VALIDATED      → log only
"""

from typing import Dict, Any, Callable, Optional
from sqlalchemy.orm import Session
from modules.alerts.service import AlertService
from core.event_bus import event_bus
from core.settings import settings
import logging
import threading

logger = logging.getLogger(__name__)

# Interval in seconds between expiration-check runs (Exp 10)
_EXPIRATION_CHECK_INTERVAL_SECONDS = 300   # 5 minutes


class AlertHandlers:
    """Event handlers for the alerts module (all expansions)."""

    def __init__(self, db: Session,
                 on_new_alert: Optional[Callable[[Dict[str, Any]], None]] = None):
        """
        Parameters
        ----------
        db           : SQLAlchemy session.
        on_new_alert : Optional callback invoked whenever a new alert is
                       generated.  Routes layer can pass a lambda that
                       refreshes the badge / shows a toast.
                       Signature: on_new_alert(alert_dict) -> None
        """
        self.db = db
        self.service = AlertService(db)
        self._on_new_alert = on_new_alert
        self._expiration_timer: Optional[threading.Timer] = None
        self._register_handlers()
        self._start_expiration_timer()
        logger.info("Alert handlers registered")

    # ------------------------------------------------------------------ #
    # Registration                                                         #
    # ------------------------------------------------------------------ #

    def _register_handlers(self):
        """Register all event handlers."""
        # Original
        event_bus.subscribe(settings.Events.INVENTORY_UPDATED,  self.handle_inventory_updated)
        event_bus.subscribe(settings.Events.MOVEMENT_VALIDATED, self.handle_movement_validated)

        # New – Exp (architecture plan)
        event_bus.subscribe(settings.Events.STOCK_CRITICAL,     self.handle_stock_critical)
        event_bus.subscribe(settings.Events.TRANSFER_REJECTED,  self.handle_transfer_rejected)
        event_bus.subscribe(settings.Events.MOVEMENT_CREATED,   self.handle_movement_created)

    # ------------------------------------------------------------------ #
    # Original handlers (unchanged logic)                                 #
    # ------------------------------------------------------------------ #

    def handle_inventory_updated(self, data: Dict[str, Any]):
        """
        Handle inventory.updated event.
        Check for low-stock and discrepancy conditions.
        """
        try:
            product_id    = data.get("product_id")
            branch_id     = data.get("branch_id")
            digital_stock = data.get("digital_stock")
            physical_stock = data.get("physical_stock")

            if not all([product_id, branch_id]):
                return

            if data.get("is_low_stock"):
                self._create_low_stock_alert(
                    product_id, branch_id, digital_stock, data.get("min_stock", 0)
                )
            else:
                self.service.resolve_open_alert(
                    alert_type="low_stock",
                    product_id=product_id,
                    branch_id=branch_id,
                )

            if data.get("has_discrepancy"):
                self._create_discrepancy_alert(
                    product_id, branch_id, physical_stock, digital_stock
                )
            else:
                self.service.resolve_open_alert(
                    alert_type="discrepancy",
                    product_id=product_id,
                    branch_id=branch_id,
                )

        except Exception as e:
            logger.error(f"Error handling inventory.updated for alerts: {e}")

    def handle_movement_validated(self, data: Dict[str, Any]):
        """
        Handle movement.validated event.
        Inventory updates are evaluated through inventory.updated.
        When a transfer is validated, resolve any pending transfer alert.
        """
        logger.info(f"Validated movement received by alerts: {data}")
        movement_id = data.get("movement_id") or data.get("id")
        if movement_id:
            self.service.resolve_open_alert(
                alert_type="transfer_pending",
                movement_id=movement_id,
            )

    # ------------------------------------------------------------------ #
    # New handlers                                                         #
    # ------------------------------------------------------------------ #

    def handle_stock_critical(self, data: Dict[str, Any]):
        """
        Handle inventory.stock_critical event.
        Creates a critical-severity low_stock alert.
        """
        try:
            product_id = data.get("product_id")
            branch_id  = data.get("branch_id")
            stock      = data.get("current_stock", 0)
            min_stock  = data.get("min_stock", 0)

            if not all([product_id, branch_id]):
                return

            existing = self.service.get_open_alert(
                alert_type="low_stock", product_id=product_id, branch_id=branch_id
            )
            if existing:
                # Escalate existing alert to critical
                self.service.set_priority(existing["id"], "high")
                return

            alert_data = self.service.create_alert(
                alert_type="low_stock",
                severity="critical",
                title="Stock Crítico Detectado",
                message=(
                    f"El stock actual ({stock}) ha caído por debajo del mínimo "
                    f"crítico ({min_stock}). Atención urgente requerida."
                ),
                product_id=product_id,
                branch_id=branch_id,
                priority="high",
            )
            self._emit_and_notify(alert_data)

        except Exception as e:
            logger.error(f"Error handling stock_critical for alerts: {e}")

    def handle_transfer_rejected(self, data: Dict[str, Any]):
        """
        Handle transfer.rejected event.
        Creates a warning alert about the rejected transfer.
        """
        try:
            movement_id = data.get("movement_id") or data.get("id")
            branch_id   = data.get("branch_id")
            reason      = data.get("reason") or data.get("rejection_reason") or "Sin motivo especificado"

            existing = self.service.get_open_alert(
                alert_type="validation_failed", movement_id=movement_id
            )
            if existing:
                return

            alert_data = self.service.create_alert(
                alert_type="validation_failed",
                severity="warning",
                title="Transferencia Rechazada",
                message=f"La transferencia #{movement_id} fue rechazada. Motivo: {reason}",
                branch_id=branch_id,
                movement_id=movement_id,
            )
            self._emit_and_notify(alert_data)

        except Exception as e:
            logger.error(f"Error handling transfer_rejected for alerts: {e}")

    def handle_movement_created(self, data: Dict[str, Any]):
        """
        Handle movement.created event.
        Creates a transfer_pending alert when a transfer movement is created.
        """
        try:
            movement_type = data.get("movement_type", "")
            state         = data.get("state", "")

            if movement_type != "transferencia" or state != "pendiente":
                return

            movement_id = data.get("movement_id") or data.get("id")
            branch_id   = data.get("branch_id")

            existing = self.service.get_open_alert(
                alert_type="transfer_pending", movement_id=movement_id
            )
            if existing:
                return

            alert_data = self.service.create_alert(
                alert_type="transfer_pending",
                severity="info",
                title="Transferencia Pendiente de Validación",
                message=f"Se creó una transferencia #{movement_id} que requiere validación.",
                branch_id=branch_id,
                movement_id=movement_id,
            )
            self._emit_and_notify(alert_data)

        except Exception as e:
            logger.error(f"Error handling movement_created for alerts: {e}")

    # ------------------------------------------------------------------ #
    # Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _create_low_stock_alert(self, product_id: int, branch_id: int,
                                current_stock: int, min_stock: int):
        """Create low-stock alert if none exists yet."""
        existing = self.service.get_open_alert(
            alert_type="low_stock", product_id=product_id, branch_id=branch_id
        )
        if existing:
            return

        alert_data = self.service.create_alert(
            alert_type="low_stock",
            severity="warning",
            title="Stock Bajo Detectado",
            message=(
                f"El stock actual ({current_stock}) ha caído por debajo "
                f"del mínimo ({min_stock})"
            ),
            product_id=product_id,
            branch_id=branch_id,
        )
        self._emit_and_notify(alert_data)

    def _create_discrepancy_alert(self, product_id: int, branch_id: int,
                                  physical_stock: int, digital_stock: int):
        """Create discrepancy alert if none exists yet."""
        existing = self.service.get_open_alert(
            alert_type="discrepancy", product_id=product_id, branch_id=branch_id
        )
        if existing:
            return

        difference = physical_stock - digital_stock
        alert_data = self.service.create_alert(
            alert_type="discrepancy",
            severity="critical",
            title="Discrepancia de Inventario Detectada",
            message=(
                f"Diferencia detectada: Físico={physical_stock}, "
                f"Digital={digital_stock}, Diferencia={difference}"
            ),
            product_id=product_id,
            branch_id=branch_id,
        )
        self._emit_and_notify(alert_data)

    def _emit_and_notify(self, alert_data: Dict[str, Any]):
        """
        Emit ALERT_GENERATED on the event bus and invoke the optional
        on_new_alert callback so the UI can update badges / show toasts.
        """
        event_bus.emit(settings.Events.ALERT_GENERATED, alert_data)
        if self._on_new_alert:
            try:
                self._on_new_alert(alert_data)
            except Exception as e:
                logger.warning(f"on_new_alert callback raised: {e}")

    # ------------------------------------------------------------------ #
    # Exp 10 – Expiration timer                                           #
    # ------------------------------------------------------------------ #

    def _start_expiration_timer(self):
        """Schedule the first expiration check."""
        self._expiration_timer = threading.Timer(
            _EXPIRATION_CHECK_INTERVAL_SECONDS,
            self._run_expiration_check,
        )
        self._expiration_timer.daemon = True
        self._expiration_timer.start()
        logger.debug(
            f"Expiration timer scheduled in {_EXPIRATION_CHECK_INTERVAL_SECONDS}s"
        )

    def _run_expiration_check(self):
        """
        Mark overdue alerts and escalate them, then reschedule itself.
        Runs in a background daemon thread.
        """
        try:
            count = self.service.mark_expired_alerts()
            if count:
                overdue = self.service.get_overdue_alerts()
                for alert in overdue:
                    self.service.escalate_alert(alert["id"])
                logger.info(
                    f"Expiration check: {count} alert(s) marked expired and escalated"
                )
        except Exception as e:
            logger.error(f"Error in expiration check: {e}")
        finally:
            # Reschedule unless unregistered
            if self._expiration_timer is not None:
                self._start_expiration_timer()

    # ------------------------------------------------------------------ #
    # Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    def unregister_handlers(self):
        """Unregister all event handlers and cancel the expiration timer."""
        # Cancel timer
        if self._expiration_timer is not None:
            self._expiration_timer.cancel()
            self._expiration_timer = None

        event_bus.unsubscribe(settings.Events.INVENTORY_UPDATED,  self.handle_inventory_updated)
        event_bus.unsubscribe(settings.Events.MOVEMENT_VALIDATED, self.handle_movement_validated)
        event_bus.unsubscribe(settings.Events.STOCK_CRITICAL,     self.handle_stock_critical)
        event_bus.unsubscribe(settings.Events.TRANSFER_REJECTED,  self.handle_transfer_rejected)
        event_bus.unsubscribe(settings.Events.MOVEMENT_CREATED,   self.handle_movement_created)
        logger.info("Alert handlers unregistered")


def setup_alert_handlers(
    db: Session,
    on_new_alert: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> AlertHandlers:
    """Setup and return alert handlers.

    Parameters
    ----------
    db           : SQLAlchemy session.
    on_new_alert : Optional UI callback for Exp 2 visual notifications.
                   Example usage from the main window::

                       def _show_alert_toast(alert):
                           if alert["severity"] == "critical":
                               QMessageBox.critical(...)
                           view.refresh()

                       setup_alert_handlers(db, on_new_alert=_show_alert_toast)
    """
    return AlertHandlers(db, on_new_alert=on_new_alert)
