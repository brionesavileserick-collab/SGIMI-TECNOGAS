"""
History event handlers - React to events and record them.

Expansiones cubiertas:
  - Todos los eventos de settings.Events ya registrados previamente
  - Expansión 9: eventos nuevos agregados al bus:
      BRANCH_STATUS_CHANGED, BRANCH_MANAGER_ASSIGNED
      PRICE_CHANGED
      MOVEMENT_CANCELLED, MOVEMENT_REVERSED
      TRANSFER_REJECTED
      STOCK_REORDER_NEEDED, STOCK_CRITICAL, STOCK_EXCEEDED_MAX
      DISCREPANCY_TOLERANCE_BREACHED
      STOCK_IN_TRANSIT_ADDED, STOCK_IN_TRANSIT_RECEIVED
      USER_CREATED, USER_UPDATED, USER_DELETED
  - Métodos públicos para logs del sistema (login, logout, error)
    que otros módulos pueden llamar directamente.

REGLA: Este archivo solo escucha eventos y delega a HistoryService.
       No contiene lógica de negocio.
"""

from typing import Dict, Any
from sqlalchemy.orm import Session
from modules.history.service import HistoryService
from core.event_bus import event_bus
from core.settings import settings
import logging

logger = logging.getLogger(__name__)


class HistoryHandlers:
    """Event handlers for history module."""

    def __init__(self, db: Session):
        self.db = db
        self.service = HistoryService(db)
        self._register_handlers()
        logger.info("History handlers registered")

    # ─────────────────────────────────────────────────────────────────────────
    # Registro de suscripciones
    # ─────────────────────────────────────────────────────────────────────────

    def _register_handlers(self):
        """Register all event handlers."""
        ev = settings.Events

        # ── Productos ────────────────────────────────────────────────────────
        event_bus.subscribe(ev.PRODUCT_CREATED, self.handle_product_created)
        event_bus.subscribe(ev.PRODUCT_UPDATED, self.handle_product_updated)
        event_bus.subscribe(ev.PRODUCT_DELETED, self.handle_product_deleted)
        event_bus.subscribe(ev.PRICE_CHANGED,   self.handle_price_changed)       # nuevo

        # ── Sucursales ───────────────────────────────────────────────────────
        event_bus.subscribe(ev.BRANCH_CREATED,          self.handle_branch_created)
        event_bus.subscribe(ev.BRANCH_UPDATED,          self.handle_branch_updated)
        event_bus.subscribe(ev.BRANCH_DELETED,          self.handle_branch_deleted)
        event_bus.subscribe(ev.BRANCH_STATUS_CHANGED,   self.handle_branch_status_changed)   # nuevo
        event_bus.subscribe(ev.BRANCH_MANAGER_ASSIGNED, self.handle_branch_manager_assigned) # nuevo

        # ── Movimientos ──────────────────────────────────────────────────────
        event_bus.subscribe(ev.MOVEMENT_CREATED,    self.handle_movement_created)
        event_bus.subscribe(ev.MOVEMENT_VALIDATED,  self.handle_movement_validated)
        event_bus.subscribe(ev.MOVEMENT_REJECTED,   self.handle_movement_rejected)
        event_bus.subscribe(ev.MOVEMENT_CANCELLED,  self.handle_movement_cancelled)  # nuevo
        event_bus.subscribe(ev.MOVEMENT_REVERSED,   self.handle_movement_reversed)   # nuevo

        # ── Inventario ───────────────────────────────────────────────────────
        event_bus.subscribe(ev.INVENTORY_UPDATED,               self.handle_inventory_updated)
        event_bus.subscribe(ev.INVENTORY_COUNTED,               self.handle_inventory_counted)
        event_bus.subscribe(ev.STOCK_REORDER_NEEDED,            self.handle_stock_reorder_needed)           # nuevo
        event_bus.subscribe(ev.STOCK_CRITICAL,                  self.handle_stock_critical)                 # nuevo
        event_bus.subscribe(ev.STOCK_EXCEEDED_MAX,              self.handle_stock_exceeded_max)             # nuevo
        event_bus.subscribe(ev.DISCREPANCY_TOLERANCE_BREACHED,  self.handle_discrepancy_tolerance_breached) # nuevo
        event_bus.subscribe(ev.STOCK_IN_TRANSIT_ADDED,          self.handle_stock_in_transit_added)         # nuevo
        event_bus.subscribe(ev.STOCK_IN_TRANSIT_RECEIVED,       self.handle_stock_in_transit_received)      # nuevo

        # ── Transferencias ───────────────────────────────────────────────────
        event_bus.subscribe(ev.TRANSFER_SENT,     self.handle_transfer_sent)
        event_bus.subscribe(ev.TRANSFER_RECEIVED, self.handle_transfer_received)
        event_bus.subscribe(ev.TRANSFER_REJECTED, self.handle_transfer_rejected) # nuevo

        # ── Alertas ──────────────────────────────────────────────────────────
        event_bus.subscribe(ev.ALERT_GENERATED, self.handle_alert_generated)

        # ── Usuarios ─────────────────────────────────────────────────────────
        event_bus.subscribe(ev.USER_CREATED, self.handle_user_created) # nuevo
        event_bus.subscribe(ev.USER_UPDATED, self.handle_user_updated) # nuevo
        event_bus.subscribe(ev.USER_DELETED, self.handle_user_deleted) # nuevo

    # ─────────────────────────────────────────────────────────────────────────
    # Handlers – Productos
    # ─────────────────────────────────────────────────────────────────────────

    def handle_product_created(self, data: Dict[str, Any]):
        """Record product creation in history."""
        self.service.record_event(
            event_type=settings.Events.PRODUCT_CREATED,
            entity_type="product",
            entity_id=data.get("product_id"),
            action="Producto creado",
            details=data,
        )

    def handle_product_updated(self, data: Dict[str, Any]):
        """Record product update in history."""
        self.service.record_event(
            event_type=settings.Events.PRODUCT_UPDATED,
            entity_type="product",
            entity_id=data.get("product_id"),
            action="Producto actualizado",
            details=data,
        )

    def handle_product_deleted(self, data: Dict[str, Any]):
        """Record product deletion in history."""
        self.service.record_event(
            event_type=settings.Events.PRODUCT_DELETED,
            entity_type="product",
            entity_id=data.get("product_id"),
            action="Producto eliminado",
            details=data,
        )

    def handle_price_changed(self, data: Dict[str, Any]):
        """Record product price change in history."""
        product_id = data.get("product_id")
        old_price = data.get("old_price")
        new_price = data.get("new_price")
        label = f"Precio actualizado: {old_price} → {new_price}" if (
            old_price is not None and new_price is not None
        ) else "Precio actualizado"
        # Normalise payload so get_change_summary() can extract the diff
        enriched = dict(data)
        if old_price is not None and new_price is not None:
            enriched.setdefault("changes", {
                "unit_price": {"before": old_price, "after": new_price}
            })
        self.service.record_event(
            event_type=settings.Events.PRICE_CHANGED,
            entity_type="product",
            entity_id=product_id,
            action=label,
            details=enriched,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Handlers – Sucursales
    # ─────────────────────────────────────────────────────────────────────────

    def handle_branch_created(self, data: Dict[str, Any]):
        """Record branch creation in history."""
        self.service.record_event(
            event_type=settings.Events.BRANCH_CREATED,
            entity_type="branch",
            entity_id=data.get("branch_id"),
            action="Sucursal creada",
            details=data,
        )

    def handle_branch_updated(self, data: Dict[str, Any]):
        """Record branch update in history."""
        self.service.record_event(
            event_type=settings.Events.BRANCH_UPDATED,
            entity_type="branch",
            entity_id=data.get("branch_id"),
            action="Sucursal actualizada",
            details=data,
        )

    def handle_branch_deleted(self, data: Dict[str, Any]):
        """Record branch deletion in history."""
        self.service.record_event(
            event_type=settings.Events.BRANCH_DELETED,
            entity_type="branch",
            entity_id=data.get("branch_id"),
            action="Sucursal eliminada",
            details=data,
        )

    def handle_branch_status_changed(self, data: Dict[str, Any]):
        """Record branch operational status change in history."""
        old_status = data.get("old_status")
        new_status = data.get("new_status") or data.get("operational_status")
        label = f"Estado operativo cambiado: {old_status} → {new_status}" if (
            old_status and new_status
        ) else "Estado operativo de sucursal cambiado"
        enriched = dict(data)
        if old_status and new_status:
            enriched.setdefault("changes", {
                "operational_status": {"before": old_status, "after": new_status}
            })
        self.service.record_event(
            event_type=settings.Events.BRANCH_STATUS_CHANGED,
            entity_type="branch",
            entity_id=data.get("branch_id"),
            action=label,
            details=enriched,
        )

    def handle_branch_manager_assigned(self, data: Dict[str, Any]):
        """Record branch manager assignment in history."""
        manager_id = data.get("manager_user_id")
        self.service.record_event(
            event_type=settings.Events.BRANCH_MANAGER_ASSIGNED,
            entity_type="branch",
            entity_id=data.get("branch_id"),
            user_id=manager_id,
            action="Responsable de sucursal asignado",
            details=data,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Handlers – Movimientos
    # ─────────────────────────────────────────────────────────────────────────

    def handle_movement_created(self, data: Dict[str, Any]):
        """Record movement creation in history."""
        self.service.record_event(
            event_type=settings.Events.MOVEMENT_CREATED,
            entity_type="movement",
            entity_id=data.get("movement_id"),
            user_id=data.get("user_id"),
            action=f"Movimiento creado: {data.get('movement_type', '')}",
            details=data,
        )

    def handle_movement_validated(self, data: Dict[str, Any]):
        """Record movement validation in history."""
        self.service.record_event(
            event_type=settings.Events.MOVEMENT_VALIDATED,
            entity_type="movement",
            entity_id=data.get("movement_id"),
            user_id=data.get("validator_id"),
            action=f"Movimiento validado: {data.get('movement_type', '')}",
            details=data,
        )

    def handle_movement_rejected(self, data: Dict[str, Any]):
        """Record movement rejection in history."""
        self.service.record_event(
            event_type=settings.Events.MOVEMENT_REJECTED,
            entity_type="movement",
            entity_id=data.get("movement_id"),
            user_id=data.get("validator_id"),
            action=f"Movimiento rechazado: {data.get('movement_type', '')}",
            details=data,
        )

    def handle_movement_cancelled(self, data: Dict[str, Any]):
        """Record movement cancellation in history."""
        self.service.record_event(
            event_type=settings.Events.MOVEMENT_CANCELLED,
            entity_type="movement",
            entity_id=data.get("movement_id"),
            user_id=data.get("cancelled_by") or data.get("user_id"),
            action=f"Movimiento cancelado: {data.get('movement_type', '')}",
            details=data,
        )

    def handle_movement_reversed(self, data: Dict[str, Any]):
        """Record movement reversal in history."""
        self.service.record_event(
            event_type=settings.Events.MOVEMENT_REVERSED,
            entity_type="movement",
            entity_id=data.get("movement_id"),
            user_id=data.get("reversed_by") or data.get("user_id"),
            action=f"Movimiento revertido: {data.get('movement_type', '')}",
            details=data,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Handlers – Inventario
    # ─────────────────────────────────────────────────────────────────────────

    def handle_inventory_updated(self, data: Dict[str, Any]):
        """Record inventory update in history."""
        self.service.record_event(
            event_type=settings.Events.INVENTORY_UPDATED,
            entity_type="inventory",
            entity_id=data.get("inventory_id"),
            action="Inventario actualizado",
            details=data,
        )

    def handle_inventory_counted(self, data: Dict[str, Any]):
        """Record inventory count in history."""
        self.service.record_event(
            event_type=settings.Events.INVENTORY_COUNTED,
            entity_type="inventory",
            entity_id=data.get("inventory_id"),
            action="Conteo de inventario registrado",
            details=data,
        )

    def handle_stock_reorder_needed(self, data: Dict[str, Any]):
        """Record stock reorder alert in history."""
        product_id = data.get("product_id")
        branch_id = data.get("branch_id")
        self.service.record_event(
            event_type=settings.Events.STOCK_REORDER_NEEDED,
            entity_type="inventory",
            entity_id=data.get("inventory_id"),
            action=f"Stock bajo — reorden necesaria (producto #{product_id}, sucursal #{branch_id})",
            details=data,
        )

    def handle_stock_critical(self, data: Dict[str, Any]):
        """Record critical stock level in history."""
        product_id = data.get("product_id")
        branch_id = data.get("branch_id")
        self.service.record_event(
            event_type=settings.Events.STOCK_CRITICAL,
            entity_type="inventory",
            entity_id=data.get("inventory_id"),
            action=f"Stock crítico (producto #{product_id}, sucursal #{branch_id})",
            details=data,
        )

    def handle_stock_exceeded_max(self, data: Dict[str, Any]):
        """Record stock exceeded maximum threshold in history."""
        product_id = data.get("product_id")
        branch_id = data.get("branch_id")
        self.service.record_event(
            event_type=settings.Events.STOCK_EXCEEDED_MAX,
            entity_type="inventory",
            entity_id=data.get("inventory_id"),
            action=f"Stock excede máximo (producto #{product_id}, sucursal #{branch_id})",
            details=data,
        )

    def handle_discrepancy_tolerance_breached(self, data: Dict[str, Any]):
        """Record inventory discrepancy breach in history."""
        self.service.record_event(
            event_type=settings.Events.DISCREPANCY_TOLERANCE_BREACHED,
            entity_type="inventory",
            entity_id=data.get("inventory_id"),
            action="Discrepancia de inventario supera tolerancia",
            details=data,
        )

    def handle_stock_in_transit_added(self, data: Dict[str, Any]):
        """Record in-transit stock addition in history."""
        self.service.record_event(
            event_type=settings.Events.STOCK_IN_TRANSIT_ADDED,
            entity_type="inventory",
            entity_id=data.get("inventory_id"),
            action="Stock en tránsito registrado",
            details=data,
        )

    def handle_stock_in_transit_received(self, data: Dict[str, Any]):
        """Record in-transit stock received in history."""
        self.service.record_event(
            event_type=settings.Events.STOCK_IN_TRANSIT_RECEIVED,
            entity_type="inventory",
            entity_id=data.get("inventory_id"),
            action="Stock en tránsito recibido",
            details=data,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Handlers – Transferencias
    # ─────────────────────────────────────────────────────────────────────────

    def handle_transfer_sent(self, data: Dict[str, Any]):
        """Record transfer sent in history."""
        self.service.record_event(
            event_type=settings.Events.TRANSFER_SENT,
            entity_type="movement",
            entity_id=data.get("movement_id"),
            action="Transferencia enviada",
            details=data,
        )

    def handle_transfer_received(self, data: Dict[str, Any]):
        """Record transfer received in history."""
        self.service.record_event(
            event_type=settings.Events.TRANSFER_RECEIVED,
            entity_type="inventory",
            entity_id=data.get("inventory_id"),
            action="Transferencia recibida",
            details=data,
        )

    def handle_transfer_rejected(self, data: Dict[str, Any]):
        """Record transfer rejection in history."""
        self.service.record_event(
            event_type=settings.Events.TRANSFER_REJECTED,
            entity_type="movement",
            entity_id=data.get("movement_id"),
            user_id=data.get("rejected_by") or data.get("validator_id"),
            action="Transferencia rechazada",
            details=data,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Handlers – Alertas
    # ─────────────────────────────────────────────────────────────────────────

    def handle_alert_generated(self, data: Dict[str, Any]):
        """Record alert generation in history."""
        self.service.record_event(
            event_type=settings.Events.ALERT_GENERATED,
            entity_type="alert",
            entity_id=data.get("id"),
            action=f"Alerta generada: {data.get('alert_type', '')}",
            details=data,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Handlers – Usuarios (Expansión 9)
    # ─────────────────────────────────────────────────────────────────────────

    def handle_user_created(self, data: Dict[str, Any]):
        """Record user creation in history."""
        self.service.record_event(
            event_type=settings.Events.USER_CREATED,
            entity_type="user",
            entity_id=data.get("user_id"),
            action=f"Usuario creado: {data.get('name', data.get('email', ''))}",
            details=data,
        )

    def handle_user_updated(self, data: Dict[str, Any]):
        """Record user update in history."""
        self.service.record_event(
            event_type=settings.Events.USER_UPDATED,
            entity_type="user",
            entity_id=data.get("user_id"),
            action=f"Usuario actualizado: {data.get('name', data.get('email', ''))}",
            details=data,
        )

    def handle_user_deleted(self, data: Dict[str, Any]):
        """Record user deletion in history."""
        self.service.record_event(
            event_type=settings.Events.USER_DELETED,
            entity_type="user",
            entity_id=data.get("user_id"),
            action=f"Usuario eliminado: {data.get('name', data.get('email', ''))}",
            details=data,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Expansión 9 – API pública para logs del sistema
    # Otros módulos llaman estos métodos directamente en vez de emitir eventos.
    # ─────────────────────────────────────────────────────────────────────────

    def log_login(self, user_id: int, user_name: str = None) -> None:
        """Call from the authentication layer after a successful login."""
        try:
            self.service.record_login(user_id, user_name)
        except Exception as exc:
            logger.error(f"log_login failed: {exc}")

    def log_logout(self, user_id: int, user_name: str = None) -> None:
        """Call from the authentication layer on logout."""
        try:
            self.service.record_logout(user_id, user_name)
        except Exception as exc:
            logger.error(f"log_logout failed: {exc}")

    def log_error(self, error_message: str, context: Dict[str, Any] = None) -> None:
        """Call from global error handlers to capture application errors."""
        try:
            self.service.record_error(error_message, context)
        except Exception as exc:
            logger.error(f"log_error failed: {exc}")

    def log_config_change(
        self,
        setting_name: str,
        old_value: object,
        new_value: object,
        user_id: int = None,
    ) -> None:
        """Call when a configuration setting is changed."""
        try:
            self.service.record_config_change(setting_name, old_value, new_value, user_id)
        except Exception as exc:
            logger.error(f"log_config_change failed: {exc}")

    # ─────────────────────────────────────────────────────────────────────────
    # Baja de suscripciones
    # ─────────────────────────────────────────────────────────────────────────

    def unregister_handlers(self):
        """Unregister all event handlers."""
        ev = settings.Events

        # Productos
        event_bus.unsubscribe(ev.PRODUCT_CREATED, self.handle_product_created)
        event_bus.unsubscribe(ev.PRODUCT_UPDATED, self.handle_product_updated)
        event_bus.unsubscribe(ev.PRODUCT_DELETED, self.handle_product_deleted)
        event_bus.unsubscribe(ev.PRICE_CHANGED,   self.handle_price_changed)

        # Sucursales
        event_bus.unsubscribe(ev.BRANCH_CREATED,          self.handle_branch_created)
        event_bus.unsubscribe(ev.BRANCH_UPDATED,          self.handle_branch_updated)
        event_bus.unsubscribe(ev.BRANCH_DELETED,          self.handle_branch_deleted)
        event_bus.unsubscribe(ev.BRANCH_STATUS_CHANGED,   self.handle_branch_status_changed)
        event_bus.unsubscribe(ev.BRANCH_MANAGER_ASSIGNED, self.handle_branch_manager_assigned)

        # Movimientos
        event_bus.unsubscribe(ev.MOVEMENT_CREATED,   self.handle_movement_created)
        event_bus.unsubscribe(ev.MOVEMENT_VALIDATED, self.handle_movement_validated)
        event_bus.unsubscribe(ev.MOVEMENT_REJECTED,  self.handle_movement_rejected)
        event_bus.unsubscribe(ev.MOVEMENT_CANCELLED, self.handle_movement_cancelled)
        event_bus.unsubscribe(ev.MOVEMENT_REVERSED,  self.handle_movement_reversed)

        # Inventario
        event_bus.unsubscribe(ev.INVENTORY_UPDATED,              self.handle_inventory_updated)
        event_bus.unsubscribe(ev.INVENTORY_COUNTED,              self.handle_inventory_counted)
        event_bus.unsubscribe(ev.STOCK_REORDER_NEEDED,           self.handle_stock_reorder_needed)
        event_bus.unsubscribe(ev.STOCK_CRITICAL,                 self.handle_stock_critical)
        event_bus.unsubscribe(ev.STOCK_EXCEEDED_MAX,             self.handle_stock_exceeded_max)
        event_bus.unsubscribe(ev.DISCREPANCY_TOLERANCE_BREACHED, self.handle_discrepancy_tolerance_breached)
        event_bus.unsubscribe(ev.STOCK_IN_TRANSIT_ADDED,         self.handle_stock_in_transit_added)
        event_bus.unsubscribe(ev.STOCK_IN_TRANSIT_RECEIVED,      self.handle_stock_in_transit_received)

        # Transferencias
        event_bus.unsubscribe(ev.TRANSFER_SENT,     self.handle_transfer_sent)
        event_bus.unsubscribe(ev.TRANSFER_RECEIVED, self.handle_transfer_received)
        event_bus.unsubscribe(ev.TRANSFER_REJECTED, self.handle_transfer_rejected)

        # Alertas
        event_bus.unsubscribe(ev.ALERT_GENERATED, self.handle_alert_generated)

        # Usuarios
        event_bus.unsubscribe(ev.USER_CREATED, self.handle_user_created)
        event_bus.unsubscribe(ev.USER_UPDATED, self.handle_user_updated)
        event_bus.unsubscribe(ev.USER_DELETED, self.handle_user_deleted)

        logger.info("History handlers unregistered")


def setup_history_handlers(db: Session) -> HistoryHandlers:
    """Setup and return history handlers."""
    return HistoryHandlers(db)
