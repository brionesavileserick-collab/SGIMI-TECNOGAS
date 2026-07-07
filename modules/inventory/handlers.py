"""
Inventory event handlers - React to events and update inventory.
Expansiones 4, 5, 6: handlers para nuevos eventos de reposición, alertas y tránsito.
"""

from typing import Dict, Any
from sqlalchemy.orm import Session
from modules.inventory.service import InventoryService
from core.event_bus import event_bus
from core.settings import settings
import logging

logger = logging.getLogger(__name__)


class InventoryHandlers:
    """Event handlers for inventory module."""

    def __init__(self, db: Session):
        self.db = db
        self.service = InventoryService(db)
        self._register_handlers()

    def _register_handlers(self):
        """Register all event handlers."""
        # Handlers originales
        event_bus.subscribe(settings.Events.MOVEMENT_VALIDATED, self.handle_movement_validated)
        event_bus.subscribe(settings.Events.INVENTORY_COUNTED, self.handle_inventory_counted)
        event_bus.subscribe(settings.Events.TRANSFER_RECEIVED, self.handle_transfer_received)

        # Expansión 4: reorder
        event_bus.subscribe(settings.Events.STOCK_REORDER_NEEDED, self.handle_stock_reorder_needed)

        # Expansión 5: alertas personalizadas
        event_bus.subscribe(settings.Events.STOCK_CRITICAL, self.handle_stock_critical)
        event_bus.subscribe(settings.Events.STOCK_EXCEEDED_MAX, self.handle_stock_exceeded_max)
        event_bus.subscribe(
            settings.Events.DISCREPANCY_TOLERANCE_BREACHED,
            self.handle_discrepancy_tolerance_breached,
        )

        # Expansión 6: tránsito
        event_bus.subscribe(settings.Events.STOCK_IN_TRANSIT_ADDED, self.handle_in_transit_added)
        event_bus.subscribe(
            settings.Events.STOCK_IN_TRANSIT_RECEIVED, self.handle_in_transit_received
        )

        # Workflow de conteos (sesiones)
        event_bus.subscribe(settings.Events.COUNT_SESSION_CREATED, self.handle_count_session_created)
        event_bus.subscribe(settings.Events.COUNT_SESSION_STARTED, self.handle_count_session_started)
        event_bus.subscribe(settings.Events.COUNT_SESSION_COMPLETED, self.handle_count_session_completed)
        event_bus.subscribe(settings.Events.COUNT_ITEM_RECORDED, self.handle_count_item_recorded)

        # Lotes y fechas de caducidad
        event_bus.subscribe(settings.Events.BATCH_ADDED, self.handle_batch_added)
        event_bus.subscribe(settings.Events.BATCH_EXPIRING, self.handle_batch_expiring)
        event_bus.subscribe(settings.Events.BATCH_CONSUMED, self.handle_batch_consumed)

        logger.info("Inventory handlers registered")

    # ------------------------------------------------------------------
    # Handlers originales (sin cambios de comportamiento)
    # ------------------------------------------------------------------

    def handle_movement_validated(self, data: Dict[str, Any]):
        """
        Handle movement.validated event.
        Updates digital stock based on validated movement.
        """
        try:
            product_id = data.get("product_id")
            branch_id = data.get("branch_id")
            movement_type = data.get("movement_type")
            quantity = data.get("quantity")
            movement_id = data.get("movement_id")

            if not all([product_id, branch_id, movement_type, quantity]):
                logger.warning(f"Invalid movement data: {data}")
                return

            if movement_type == "entrada":
                self.service.adjust_digital_stock(
                    product_id, branch_id, quantity,
                    is_absolute=False, movement_id=movement_id
                )
                logger.info(f"Stock increased: Product {product_id}, Branch {branch_id}, +{quantity}")

            elif movement_type == "salida":
                self.service.adjust_digital_stock(
                    product_id, branch_id, -quantity,
                    is_absolute=False, movement_id=movement_id
                )
                logger.info(f"Stock decreased: Product {product_id}, Branch {branch_id}, -{quantity}")

            elif movement_type == "ajuste":
                self.service.adjust_digital_stock(
                    product_id, branch_id, quantity,
                    is_absolute=True, movement_id=movement_id
                )
                logger.info(f"Stock adjusted: Product {product_id}, Branch {branch_id}, ={quantity}")

            elif movement_type == "transferencia":
                self.service.adjust_digital_stock(
                    product_id, branch_id, -quantity,
                    is_absolute=False, movement_id=movement_id
                )
                logger.info(f"Transfer sent: Product {product_id}, Branch {branch_id}, -{quantity}")

        except Exception as e:
            logger.error(f"Error handling movement.validated: {e}")

    def handle_inventory_counted(self, data: Dict[str, Any]):
        """
        Handle inventory.counted event.
        Logs discrepancy detection — physical stock is already updated by adjust_physical_stock.
        """
        try:
            product_id = data.get("product_id")
            branch_id = data.get("branch_id")
            physical_stock = data.get("physical_stock")
            notes = data.get("notes")

            if not all([product_id, branch_id]):
                logger.warning(f"Invalid inventory count data: {data}")
                return

            inventory = self.service.get_inventory_by_product_branch(product_id, branch_id)
            if inventory and inventory["digital_stock"] != physical_stock:
                logger.info(
                    f"Discrepancy detected: Product {product_id}, Branch {branch_id}, "
                    f"Physical={physical_stock}, Digital={inventory['digital_stock']}"
                    + (f", Notes='{notes}'" if notes else "")
                )

        except Exception as e:
            logger.error(f"Error handling inventory.counted: {e}")

    def handle_transfer_received(self, data: Dict[str, Any]):
        """
        Handle transfer.received event.
        Increases stock at destination branch.
        """
        try:
            product_id = data.get("product_id")
            destination_branch_id = data.get("destination_branch_id")
            quantity = data.get("quantity")

            if not all([product_id, destination_branch_id, quantity]):
                logger.warning(f"Invalid transfer data: {data}")
                return

            self.service.adjust_digital_stock(
                product_id, destination_branch_id, quantity, is_absolute=False
            )
            logger.info(
                f"Transfer received: Product {product_id}, Branch {destination_branch_id}, +{quantity}"
            )

        except Exception as e:
            logger.error(f"Error handling transfer.received: {e}")

    # ------------------------------------------------------------------
    # Expansión 4: reposición
    # ------------------------------------------------------------------

    def handle_stock_reorder_needed(self, data: Dict[str, Any]):
        """
        Expansión 4 - Reacciona a inventory.stock_reorder_needed.
        Loguea la necesidad de reposición; módulos externos pueden suscribirse
        para crear órdenes de compra u otras acciones.
        """
        try:
            inventory_id = data.get("inventory_id")
            product_id = data.get("product_id")
            branch_id = data.get("branch_id")
            digital_stock = data.get("digital_stock")
            min_stock = data.get("min_stock")
            priority = data.get("reorder_priority", "normal")

            logger.warning(
                f"REORDER NEEDED [{priority.upper()}]: inventory={inventory_id}, "
                f"product={product_id}, branch={branch_id}, "
                f"stock={digital_stock} (min={min_stock})"
            )

        except Exception as e:
            logger.error(f"Error handling stock_reorder_needed: {e}")

    # ------------------------------------------------------------------
    # Expansión 5: alertas personalizadas
    # ------------------------------------------------------------------

    def handle_stock_critical(self, data: Dict[str, Any]):
        """
        Expansión 5 - Reacciona a inventory.stock_critical.
        """
        try:
            logger.critical(
                f"STOCK CRÍTICO: inventory={data.get('inventory_id')}, "
                f"product={data.get('product_id')}, branch={data.get('branch_id')}, "
                f"stock={data.get('digital_stock')} "
                f"(umbral={data.get('critical_stock_threshold')})"
            )
        except Exception as e:
            logger.error(f"Error handling stock_critical: {e}")

    def handle_stock_exceeded_max(self, data: Dict[str, Any]):
        """
        Expansión 5 - Reacciona a inventory.stock_exceeded_max.
        """
        try:
            logger.warning(
                f"STOCK EXCEDIDO: inventory={data.get('inventory_id')}, "
                f"product={data.get('product_id')}, branch={data.get('branch_id')}, "
                f"stock={data.get('digital_stock')} "
                f"(max={data.get('max_stock_threshold')})"
            )
        except Exception as e:
            logger.error(f"Error handling stock_exceeded_max: {e}")

    def handle_discrepancy_tolerance_breached(self, data: Dict[str, Any]):
        """
        Expansión 5 - Reacciona a inventory.discrepancy_tolerance_breached.
        """
        try:
            logger.warning(
                f"DISCREPANCIA FUERA DE TOLERANCIA: inventory={data.get('inventory_id')}, "
                f"product={data.get('product_id')}, branch={data.get('branch_id')}, "
                f"diferencia={data.get('difference')} "
                f"(tolerancia={data.get('discrepancy_tolerance')})"
            )
        except Exception as e:
            logger.error(f"Error handling discrepancy_tolerance_breached: {e}")

    # ------------------------------------------------------------------
    # Expansión 6: tránsito
    # ------------------------------------------------------------------

    def handle_in_transit_added(self, data: Dict[str, Any]):
        """
        Expansión 6 - Reacciona a inventory.in_transit_added.
        """
        try:
            logger.info(
                f"EN TRÁNSITO: inventory={data.get('inventory_id')}, "
                f"product={data.get('product_id')}, branch={data.get('branch_id')}, "
                f"+{data.get('quantity_added')} (total={data.get('total_in_transit')})"
            )
        except Exception as e:
            logger.error(f"Error handling in_transit_added: {e}")

    def handle_in_transit_received(self, data: Dict[str, Any]):
        """
        Expansión 6 - Reacciona a inventory.in_transit_received.
        """
        try:
            logger.info(
                f"TRÁNSITO RECIBIDO: inventory={data.get('inventory_id')}, "
                f"product={data.get('product_id')}, branch={data.get('branch_id')}, "
                f"recibido={data.get('quantity_received')}, "
                f"nuevo_stock={data.get('new_digital_stock')}, "
                f"restante_tránsito={data.get('remaining_in_transit')}"
            )
        except Exception as e:
            logger.error(f"Error handling in_transit_received: {e}")

    # ------------------------------------------------------------------
    # Workflow de conteos (sesiones)
    # ------------------------------------------------------------------

    def handle_count_session_created(self, data: Dict[str, Any]):
        """Reacciona a inventory.count_session_created."""
        try:
            logger.info(
                f"SESIÓN DE CONTEO CREADA: session={data.get('session_id')}, "
                f"branch={data.get('branch_id')}, "
                f"scheduled={data.get('scheduled_date')}"
            )
        except Exception as e:
            logger.error(f"Error handling count_session_created: {e}")

    def handle_count_session_started(self, data: Dict[str, Any]):
        """Reacciona a inventory.count_session_started."""
        try:
            logger.info(
                f"SESIÓN DE CONTEO INICIADA: session={data.get('session_id')}, "
                f"branch={data.get('branch_id')}"
            )
        except Exception as e:
            logger.error(f"Error handling count_session_started: {e}")

    def handle_count_session_completed(self, data: Dict[str, Any]):
        """Reacciona a inventory.count_session_completed."""
        try:
            logger.info(
                f"SESIÓN DE CONTEO COMPLETADA: session={data.get('session_id')}, "
                f"branch={data.get('branch_id')}, "
                f"validadores={data.get('validator_count', 1)}"
            )
        except Exception as e:
            logger.error(f"Error handling count_session_completed: {e}")

    def handle_count_item_recorded(self, data: Dict[str, Any]):
        """Reacciona a inventory.count_item_recorded."""
        try:
            diff = data.get("difference", 0)
            if data.get("is_discrepancy"):
                logger.warning(
                    f"DISCREPANCIA EN CONTEO: session={data.get('session_id')}, "
                    f"inventory={data.get('inventory_id')}, "
                    f"contado={data.get('counted_physical')}, diferencia={diff}"
                )
            else:
                logger.debug(
                    f"Item contado: session={data.get('session_id')}, "
                    f"inventory={data.get('inventory_id')}, "
                    f"contado={data.get('counted_physical')}"
                )
        except Exception as e:
            logger.error(f"Error handling count_item_recorded: {e}")

    # ------------------------------------------------------------------
    # Lotes y fechas de caducidad
    # ------------------------------------------------------------------

    def handle_batch_added(self, data: Dict[str, Any]):
        """Reacciona a inventory.batch_added."""
        try:
            logger.info(
                f"LOTE AGREGADO: batch={data.get('batch_id')}, "
                f"inventory={data.get('inventory_id')}, "
                f"número={data.get('batch_number')}, "
                f"cantidad={data.get('quantity')}"
            )
        except Exception as e:
            logger.error(f"Error handling batch_added: {e}")

    def handle_batch_expiring(self, data: Dict[str, Any]):
        """Reacciona a inventory.batch_expiring — lote próximo a vencer."""
        try:
            logger.warning(
                f"LOTE POR VENCER: batch={data.get('batch_id')}, "
                f"inventory={data.get('inventory_id')}, "
                f"vence={data.get('expiration_date')}, "
                f"días_restantes={data.get('days_remaining')}"
            )
        except Exception as e:
            logger.error(f"Error handling batch_expiring: {e}")

    def handle_batch_consumed(self, data: Dict[str, Any]):
        """Reacciona a inventory.batch_consumed."""
        try:
            logger.info(
                f"LOTE CONSUMIDO: batch={data.get('batch_id')}, "
                f"inventory={data.get('inventory_id')}, "
                f"consumido={data.get('quantity_consumed')}, "
                f"restante={data.get('remaining_in_batch')}"
            )
        except Exception as e:
            logger.error(f"Error handling batch_consumed: {e}")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def unregister_handlers(self):
        """Unregister all event handlers."""
        event_bus.unsubscribe(settings.Events.MOVEMENT_VALIDATED, self.handle_movement_validated)
        event_bus.unsubscribe(settings.Events.INVENTORY_COUNTED, self.handle_inventory_counted)
        event_bus.unsubscribe(settings.Events.TRANSFER_RECEIVED, self.handle_transfer_received)
        event_bus.unsubscribe(settings.Events.STOCK_REORDER_NEEDED, self.handle_stock_reorder_needed)
        event_bus.unsubscribe(settings.Events.STOCK_CRITICAL, self.handle_stock_critical)
        event_bus.unsubscribe(settings.Events.STOCK_EXCEEDED_MAX, self.handle_stock_exceeded_max)
        event_bus.unsubscribe(
            settings.Events.DISCREPANCY_TOLERANCE_BREACHED,
            self.handle_discrepancy_tolerance_breached,
        )
        event_bus.unsubscribe(settings.Events.STOCK_IN_TRANSIT_ADDED, self.handle_in_transit_added)
        event_bus.unsubscribe(
            settings.Events.STOCK_IN_TRANSIT_RECEIVED, self.handle_in_transit_received
        )
        # Workflow de conteos
        event_bus.unsubscribe(settings.Events.COUNT_SESSION_CREATED, self.handle_count_session_created)
        event_bus.unsubscribe(settings.Events.COUNT_SESSION_STARTED, self.handle_count_session_started)
        event_bus.unsubscribe(settings.Events.COUNT_SESSION_COMPLETED, self.handle_count_session_completed)
        event_bus.unsubscribe(settings.Events.COUNT_ITEM_RECORDED, self.handle_count_item_recorded)
        # Lotes
        event_bus.unsubscribe(settings.Events.BATCH_ADDED, self.handle_batch_added)
        event_bus.unsubscribe(settings.Events.BATCH_EXPIRING, self.handle_batch_expiring)
        event_bus.unsubscribe(settings.Events.BATCH_CONSUMED, self.handle_batch_consumed)
        logger.info("Inventory handlers unregistered")


def setup_inventory_handlers(db: Session) -> InventoryHandlers:
    """Setup and return inventory handlers."""
    return InventoryHandlers(db)
