"""
Inventory service layer - Business logic and event emission.
Expansiones 1-9 implementadas. Todos los métodos originales son retrocompatibles.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from modules.inventory.repository import InventoryRepository
from core.event_bus import event_bus
from core.settings import settings
from datetime import datetime, timedelta, date
import logging

logger = logging.getLogger(__name__)


class InventoryService:
    """Service for inventory business logic."""

    def __init__(self, db: Session):
        self.repository = InventoryRepository(db)

    # ------------------------------------------------------------------
    # CRUD base (retrocompatible sin cambios de firma)
    # ------------------------------------------------------------------

    def create_inventory(self, inventory_data: dict) -> Dict[str, Any]:
        """Create a new inventory record."""
        product_id = inventory_data.get("product_id")
        branch_id = inventory_data.get("branch_id")

        if self.repository.exists(product_id, branch_id):
            raise ValueError("El inventario para este producto y sucursal ya existe")

        inventory = self.repository.create(inventory_data)
        self._emit_inventory_updated(inventory)
        logger.info(f"Inventory created: Product {product_id} at Branch {branch_id}")
        return inventory.to_dict()

    def get_inventory(self, inventory_id: int) -> Optional[Dict[str, Any]]:
        """Get inventory by ID."""
        inventory = self.repository.get_by_id(inventory_id)
        return inventory.to_dict() if inventory else None

    def get_inventory_by_product_branch(
        self, product_id: int, branch_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get inventory by product and branch."""
        inventory = self.repository.get_by_product_branch(product_id, branch_id)
        return inventory.to_dict() if inventory else None


    def list_inventory(
        self,
        page: int = 1,
        page_size: int = 20,
        branch_id: int = None,
        product_id: int = None,
        low_stock_only: bool = False,
        discrepancy_only: bool = False,
        search: str = None,
    ) -> Dict[str, Any]:
        """List inventory with pagination and filtering."""
        skip = (page - 1) * page_size
        inventory_items = self.repository.get_all(
            skip=skip,
            limit=page_size,
            branch_id=branch_id,
            product_id=product_id,
            low_stock_only=low_stock_only,
            discrepancy_only=discrepancy_only,
            search=search,
        )
        total = self.repository.count(
            branch_id=branch_id,
            product_id=product_id,
            low_stock_only=low_stock_only,
            discrepancy_only=discrepancy_only,
            search=search,
        )
        return {
            "inventory": [self._enrich_inventory(i) for i in inventory_items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }

    def update_inventory(
        self, inventory_id: int, update_data: dict
    ) -> Optional[Dict[str, Any]]:
        """Update inventory record."""
        inventory = self.repository.update(inventory_id, update_data)
        if not inventory:
            return None
        self._emit_inventory_updated(inventory)
        logger.info(f"Inventory updated: ID {inventory_id}")
        return inventory.to_dict()

    def delete_inventory(self, inventory_id: int) -> bool:
        """Soft delete inventory record."""
        success = self.repository.delete(inventory_id)
        if success:
            logger.info(f"Inventory deleted: ID {inventory_id}")
        return success

    def get_totals(self, branch_id: int = None) -> Dict[str, int]:
        """Get inventory totals."""
        return {
            "total_physical_stock": self.repository.get_total_physical_stock(branch_id),
            "total_digital_stock": self.repository.get_total_digital_stock(branch_id),
            "discrepancy_count": self.repository.get_discrepancy_count(branch_id),
            "low_stock_count": self.repository.get_low_stock_count(branch_id),
        }


    def get_discrepancies(self, branch_id: int = None) -> List[Dict[str, Any]]:
        """Get all items with discrepancies."""
        items = self.repository.get_all(
            limit=1000, branch_id=branch_id, discrepancy_only=True
        )
        return [self._enrich_inventory(i) for i in items]

    def get_low_stock_items(self, branch_id: int = None) -> List[Dict[str, Any]]:
        """Get all items with low stock."""
        items = self.repository.get_all(
            limit=1000, branch_id=branch_id, low_stock_only=True
        )
        return [self._enrich_inventory(i) for i in items]

    def get_global_inventory(
        self,
        page: int = 1,
        page_size: int = 20,
        product_id: int = None,
        search: str = None,
    ) -> Dict[str, Any]:
        """Get global inventory (sum of stock across all branches)."""
        skip = (page - 1) * page_size
        inventory_items = self.repository.get_global_inventory(
            skip=skip, limit=page_size, product_id=product_id, search=search
        )
        total = self.repository.count_global_inventory(
            product_id=product_id, search=search
        )
        return {
            "inventory": inventory_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }

    def get_product_stock_across_branches(
        self, product_id: int
    ) -> List[Dict[str, Any]]:
        """Get stock for a specific product across all branches."""
        return self.repository.get_product_stock_across_branches(product_id)

    # ------------------------------------------------------------------
    # adjust_physical_stock — Expansión 2: acepta notes opcionales
    # Expansión 7: registra cambio en historial
    # Expansión 4: emite STOCK_REORDER_NEEDED si stock baja de min
    # Expansión 5: revisa alertas personalizadas
    # ------------------------------------------------------------------

    def adjust_physical_stock(
        self,
        product_id: int,
        branch_id: int,
        quantity: int,
        notes: str = None,
        validator_name: str = None,
        skip_session_sync: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """
        Adjust physical stock (for inventory counts).
        Expansión 2: parámetro opcional `notes`.
        Expansión 7: registra en historial con change_type='count'.
        Expansión 5: emite alertas si hay discrepancia por encima de tolerancia.
        """
        inventory = self.repository.get_by_product_branch(product_id, branch_id)

        if not inventory:
            inventory = self.repository.create({
                "product_id": product_id,
                "branch_id": branch_id,
                "physical_stock": quantity,
                "digital_stock": 0,
                "min_stock": 0,
            })
        else:
            prev_physical = inventory.physical_stock
            prev_digital = inventory.digital_stock

            inventory = self.repository.set_stock(
                product_id, branch_id, physical_stock=quantity, notes=notes
            )

            # Expansión 7: historial
            self._log_stock_change(
                inventory_id=inventory.id,
                previous_physical=prev_physical,
                new_physical=inventory.physical_stock,
                previous_digital=prev_digital,
                new_digital=inventory.digital_stock,
                change_type="count",
                reason=notes,
            )

        # Vincular a sesión de conteo activa si existe
        if not skip_session_sync:
            active_session = self.repository.get_active_count_session(branch_id)
            if active_session and inventory:
                self._link_physical_count_to_session(
                    active_session.id,
                    inventory.id,
                    product_id,
                    quantity,
                    notes=notes,
                    validator_name=validator_name,
                )
                self.repository.update(inventory.id, {"count_session_id": active_session.id})

        event_data = {
            "product_id": product_id,
            "branch_id": branch_id,
            "physical_stock": quantity,
            "inventory_id": inventory.id,
            "notes": notes,
        }
        event_bus.emit(settings.Events.INVENTORY_COUNTED, event_data)
        self._emit_inventory_updated(inventory)

        # Expansión 5: alertas personalizadas
        self.check_and_emit_alerts(inventory.id)

        logger.info(
            f"Physical stock adjusted: Product {product_id}, Branch {branch_id}, Qty {quantity}"
        )
        return inventory.to_dict() if inventory else None


    def adjust_digital_stock(
        self,
        product_id: int,
        branch_id: int,
        quantity: int,
        is_absolute: bool = False,
        movement_id: int = None,
        reason: str = None,
        adjusted_by_name: str = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Adjust digital stock.
        Expansión 7: registra en historial con change_type='movement' o 'adjustment'.
        Expansión 4: emite STOCK_REORDER_NEEDED si stock baja de min_stock.
        Expansión 5: revisa alertas personalizadas.
        """
        inventory = self.repository.get_by_product_branch(product_id, branch_id)

        if not inventory:
            if not is_absolute and quantity < 0:
                return None
            inventory = self.repository.create({
                "product_id": product_id,
                "branch_id": branch_id,
                "physical_stock": 0,
                "digital_stock": quantity,
                "min_stock": 0,
            })
            self._emit_inventory_updated(inventory)
            logger.info(
                f"Inventory created from stock event: Product {product_id}, "
                f"Branch {branch_id}, Digital {quantity}"
            )
            return inventory.to_dict()

        prev_physical = inventory.physical_stock
        prev_digital = inventory.digital_stock

        if is_absolute:
            inventory = self.repository.set_stock(
                product_id, branch_id, digital_stock=quantity
            )
            change_type = "adjustment"
        else:
            inventory = self.repository.update_stock(
                product_id, branch_id, digital_change=quantity
            )
            change_type = "movement"

        if inventory:
            # Expansión 7: historial
            self._log_stock_change(
                inventory_id=inventory.id,
                previous_physical=prev_physical,
                new_physical=inventory.physical_stock,
                previous_digital=prev_digital,
                new_digital=inventory.digital_stock,
                change_type=change_type,
                movement_id=movement_id,
                reason=reason if change_type == "movement" else None,
                digital_adjustment_notes=reason if change_type == "adjustment" else None,
                adjusted_by_name=adjusted_by_name if change_type == "adjustment" else None,
            )

            self._emit_inventory_updated(inventory)

            # Expansión 4: reorder needed
            if inventory.is_low_stock:
                self._emit_reorder_needed(inventory)

            # Expansión 5: alertas personalizadas
            self.check_and_emit_alerts(inventory.id)

            logger.info(
                f"Digital stock adjusted: Product {product_id}, Branch {branch_id}, "
                f"Change {quantity}"
            )

        return inventory.to_dict() if inventory else None

    # ------------------------------------------------------------------
    # Helpers de emisión internos
    # ------------------------------------------------------------------

    def _emit_inventory_updated(self, inventory) -> None:
        """Emit inventory.updated — retrocompatible."""
        event_data = {
            "inventory_id": inventory.id,
            "product_id": inventory.product_id,
            "branch_id": inventory.branch_id,
            "physical_stock": inventory.physical_stock,
            "digital_stock": inventory.digital_stock,
            "difference": inventory.difference,
            "has_discrepancy": inventory.has_discrepancy,
            "is_low_stock": inventory.is_low_stock,
            "min_stock": inventory.min_stock,
            "max_stock": inventory.max_stock,
        }
        event_bus.emit(settings.Events.INVENTORY_UPDATED, event_data)

    def _emit_reorder_needed(self, inventory) -> None:
        """Expansión 4 - Emite STOCK_REORDER_NEEDED."""
        event_bus.emit(settings.Events.STOCK_REORDER_NEEDED, {
            "inventory_id": inventory.id,
            "product_id": inventory.product_id,
            "branch_id": inventory.branch_id,
            "digital_stock": inventory.digital_stock,
            "min_stock": inventory.min_stock,
            "reorder_priority": inventory.reorder_priority,
        })

    def _enrich_inventory(self, inventory) -> Dict[str, Any]:
        """Enrich inventory with product and branch details."""
        details = self.repository.get_inventory_with_details(inventory.id)
        if not details:
            return inventory.to_dict()
        result = inventory.to_dict()
        result["product"] = details["product"]
        result["branch"] = details["branch"]
        return result


    # ------------------------------------------------------------------
    # Expansión 1: Ubicación física
    # ------------------------------------------------------------------

    def get_inventory_by_location(
        self, branch_id: int, location: str
    ) -> List[Dict[str, Any]]:
        """
        Expansión 1 - Retorna items en una ubicación física (búsqueda parcial).
        """
        items = self.repository.get_by_location(branch_id, location)
        return [i.to_dict() for i in items]

    # ------------------------------------------------------------------
    # Expansión 2: Notas en conteos (integrado en adjust_physical_stock)
    # ------------------------------------------------------------------

    def get_count_history(
        self,
        inventory_id: int,
        limit: int = 50,
        date_from: datetime = None,
        date_to: datetime = None,
    ) -> List[Dict[str, Any]]:
        """
        Expansión 2/7 - Retorna historial de conteos físicos de un item.
        """
        records = self.repository.get_history_by_change_type(
            inventory_id, "count", limit=limit
        )
        return [r.to_dict() for r in records]

    # ------------------------------------------------------------------
    # Expansión 3: Tags
    # ------------------------------------------------------------------

    def add_tag(self, inventory_id: int, tag: str) -> Optional[Dict[str, Any]]:
        """
        Expansión 3 - Agrega un tag al item sin afectar los existentes.
        """
        tag = tag.strip().lower()
        if not tag:
            raise ValueError("El tag no puede estar vacío")

        inventory = self.repository.get_by_id(inventory_id)
        if not inventory:
            return None

        existing = [t.strip() for t in (inventory.tags or "").split(",") if t.strip()]
        if tag not in existing:
            existing.append(tag)

        updated = self.repository.update(inventory_id, {"tags": ",".join(existing)})
        return updated.to_dict() if updated else None

    def remove_tag(self, inventory_id: int, tag: str) -> Optional[Dict[str, Any]]:
        """
        Expansión 3 - Elimina un tag específico sin afectar los demás.
        """
        tag = tag.strip().lower()
        inventory = self.repository.get_by_id(inventory_id)
        if not inventory:
            return None

        existing = [t.strip() for t in (inventory.tags or "").split(",") if t.strip()]
        existing = [t for t in existing if t != tag]

        updated = self.repository.update(
            inventory_id, {"tags": ",".join(existing) if existing else None}
        )
        return updated.to_dict() if updated else None

    def get_all_tags(self, branch_id: int) -> List[str]:
        """
        Expansión 3 - Retorna todos los tags únicos en uso en una sucursal.
        """
        return self.repository.get_all_tags_in_branch(branch_id)

    def filter_by_tags(
        self, tags_list: List[str], branch_id: int = None
    ) -> List[Dict[str, Any]]:
        """
        Expansión 3 - Filtra items que tengan TODOS los tags de la lista.
        """
        if not tags_list:
            return []

        # Buscar por el primer tag y filtrar el resto en Python
        # (SQLite no tiene soporte nativo para arrays)
        items = self.repository.get_by_tag(tags_list[0], branch_id=branch_id)

        result = []
        for item in items:
            item_tags = {t.strip().lower() for t in (item.tags or "").split(",") if t.strip()}
            if all(t.strip().lower() in item_tags for t in tags_list):
                result.append(item.to_dict())

        return result


    # ------------------------------------------------------------------
    # Expansión 4: Prioridad de reposición
    # ------------------------------------------------------------------

    def update_reorder_priority(
        self, inventory_id: int, priority: str
    ) -> Optional[Dict[str, Any]]:
        """
        Expansión 4 - Actualiza la prioridad de reposición.
        priority: "urgente" | "normal" | "bajo"
        """
        valid = {"urgente", "normal", "bajo"}
        if priority not in valid:
            raise ValueError(f"Prioridad inválida '{priority}'. Valores: {valid}")

        updated = self.repository.update(inventory_id, {"reorder_priority": priority})
        return updated.to_dict() if updated else None

    def get_items_needing_reorder(self, branch_id: int) -> List[Dict[str, Any]]:
        """
        Expansión 4 - Items con is_low_stock=True ordenados por prioridad.
        """
        items = self.repository.get_low_stock_ordered_by_priority(branch_id)
        return [self._enrich_inventory(i) for i in items]

    def get_reorder_report(self, branch_id: int = None) -> Dict[str, Any]:
        """
        Expansión 4 - Reporte de todos los items bajo stock con sus prioridades.
        """
        urgente = self.repository.get_all(
            limit=500, branch_id=branch_id, low_stock_only=True
        )
        by_priority: Dict[str, List] = {"urgente": [], "normal": [], "bajo": []}
        for item in urgente:
            prio = item.reorder_priority or "normal"
            if prio in by_priority:
                by_priority[prio].append(item.to_dict())
            else:
                by_priority["normal"].append(item.to_dict())

        return {
            "branch_id": branch_id,
            "total": sum(len(v) for v in by_priority.values()),
            "by_priority": by_priority,
        }

    # ------------------------------------------------------------------
    # Expansión 5: Alertas personalizadas por item
    # ------------------------------------------------------------------

    def get_effective_thresholds(self, inventory_id: int) -> Optional[Dict[str, Any]]:
        """
        Expansión 5 - Retorna los umbrales efectivos: del item si están configurados,
        o los globales del sistema como fallback.
        """
        inventory = self.repository.get_by_id(inventory_id)
        if not inventory:
            return None

        return {
            "inventory_id": inventory_id,
            "critical_stock_threshold": (
                inventory.critical_stock_threshold
                if inventory.critical_stock_threshold is not None
                else settings.LOW_STOCK_THRESHOLD
            ),
            "max_stock_threshold": inventory.max_stock_threshold,
            "discrepancy_tolerance": inventory.discrepancy_tolerance,
            "source": {
                "critical": "item" if inventory.critical_stock_threshold is not None else "global",
                "max": "item" if inventory.max_stock_threshold is not None else "none",
            },
        }

    def check_and_emit_alerts(self, inventory_id: int) -> List[str]:
        """
        Expansión 5 - Revisa umbrales personalizados y emite eventos si aplica.
        Retorna lista de eventos emitidos (útil para logging/testing).
        """
        inventory = self.repository.get_by_id(inventory_id)
        if not inventory:
            return []

        emitted = []

        # Alerta de stock crítico
        if inventory.is_critical_stock:
            event_bus.emit(settings.Events.STOCK_CRITICAL, {
                "inventory_id": inventory_id,
                "product_id": inventory.product_id,
                "branch_id": inventory.branch_id,
                "digital_stock": inventory.digital_stock,
                "critical_stock_threshold": inventory.critical_stock_threshold,
            })
            emitted.append(settings.Events.STOCK_CRITICAL)
            logger.warning(
                f"STOCK CRÍTICO: inventory_id={inventory_id}, stock={inventory.digital_stock}, "
                f"umbral={inventory.critical_stock_threshold}"
            )

        # Alerta de stock excedido
        if inventory.is_exceeding_max:
            event_bus.emit(settings.Events.STOCK_EXCEEDED_MAX, {
                "inventory_id": inventory_id,
                "product_id": inventory.product_id,
                "branch_id": inventory.branch_id,
                "digital_stock": inventory.digital_stock,
                "max_stock_threshold": inventory.max_stock_threshold,
            })
            emitted.append(settings.Events.STOCK_EXCEEDED_MAX)

        # Alerta de discrepancia fuera de tolerancia
        if inventory.has_discrepancy:
            event_bus.emit(settings.Events.DISCREPANCY_TOLERANCE_BREACHED, {
                "inventory_id": inventory_id,
                "product_id": inventory.product_id,
                "branch_id": inventory.branch_id,
                "physical_stock": inventory.physical_stock,
                "digital_stock": inventory.digital_stock,
                "difference": inventory.difference,
                "discrepancy_tolerance": inventory.discrepancy_tolerance,
            })
            emitted.append(settings.Events.DISCREPANCY_TOLERANCE_BREACHED)

        return emitted

    def get_items_exceeding_max(self, branch_id: int) -> List[Dict[str, Any]]:
        """
        Expansión 5 - Items cuyo digital_stock supera max_stock_threshold.
        """
        items = self.repository.get_items_with_active_alerts(branch_id)
        return [
            i.to_dict() for i in items
            if i.max_stock_threshold is not None and i.digital_stock > i.max_stock_threshold
        ]


    # ------------------------------------------------------------------
    # Expansión 6: Stock en tránsito
    # ------------------------------------------------------------------

    def add_to_transit(
        self, product_id: int, branch_id: int, quantity: int
    ) -> Optional[Dict[str, Any]]:
        """
        Expansión 6 - Incrementa el stock en tránsito hacia una sucursal.
        """
        if quantity <= 0:
            raise ValueError("La cantidad en tránsito debe ser positiva")

        inventory = self.repository.get_by_product_branch(product_id, branch_id)
        if not inventory:
            raise ValueError(
                f"No existe inventario para producto {product_id} en sucursal {branch_id}"
            )

        new_transit = (inventory.in_transit_quantity or 0) + quantity
        updated = self.repository.update_in_transit(inventory.id, new_transit)

        event_bus.emit(settings.Events.STOCK_IN_TRANSIT_ADDED, {
            "inventory_id": updated.id,
            "product_id": product_id,
            "branch_id": branch_id,
            "quantity_added": quantity,
            "total_in_transit": updated.in_transit_quantity,
        })

        logger.info(
            f"Transit added: Product {product_id}, Branch {branch_id}, +{quantity} "
            f"(total={updated.in_transit_quantity})"
        )
        return updated.to_dict()

    def remove_from_transit(
        self, product_id: int, branch_id: int, quantity: int
    ) -> Optional[Dict[str, Any]]:
        """
        Expansión 6 - Decrementa stock en tránsito (sin actualizar digital_stock).
        """
        if quantity <= 0:
            raise ValueError("La cantidad debe ser positiva")

        inventory = self.repository.get_by_product_branch(product_id, branch_id)
        if not inventory:
            return None

        new_transit = max(0, (inventory.in_transit_quantity or 0) - quantity)
        updated = self.repository.update_in_transit(inventory.id, new_transit)
        return updated.to_dict() if updated else None

    def receive_transit(
        self, product_id: int, branch_id: int, quantity: int
    ) -> Optional[Dict[str, Any]]:
        """
        Expansión 6 - Recibe mercancía en tránsito: descuenta in_transit y suma digital_stock.
        """
        if quantity <= 0:
            raise ValueError("La cantidad debe ser positiva")

        inventory = self.repository.get_by_product_branch(product_id, branch_id)
        if not inventory:
            return None

        prev_digital = inventory.digital_stock
        prev_physical = inventory.physical_stock

        # Decrementar tránsito
        new_transit = max(0, (inventory.in_transit_quantity or 0) - quantity)
        self.repository.update_in_transit(inventory.id, new_transit)

        # Incrementar digital stock
        inventory = self.repository.update_stock(
            product_id, branch_id, digital_change=quantity
        )

        if inventory:
            # Expansión 7: historial
            self._log_stock_change(
                inventory_id=inventory.id,
                previous_physical=prev_physical,
                new_physical=inventory.physical_stock,
                previous_digital=prev_digital,
                new_digital=inventory.digital_stock,
                change_type="transfer",
                reason=f"Recepción de tránsito: +{quantity}",
            )

            self._emit_inventory_updated(inventory)

            event_bus.emit(settings.Events.STOCK_IN_TRANSIT_RECEIVED, {
                "inventory_id": inventory.id,
                "product_id": product_id,
                "branch_id": branch_id,
                "quantity_received": quantity,
                "new_digital_stock": inventory.digital_stock,
                "remaining_in_transit": inventory.in_transit_quantity,
            })

            logger.info(
                f"Transit received: Product {product_id}, Branch {branch_id}, +{quantity}"
            )

        return inventory.to_dict() if inventory else None

    def get_available_stock(self, inventory_id: int) -> Optional[Dict[str, Any]]:
        """
        Expansión 6 - Retorna el stock disponible (digital - in_transit).
        """
        inventory = self.repository.get_by_id(inventory_id)
        if not inventory:
            return None
        return {
            "inventory_id": inventory_id,
            "digital_stock": inventory.digital_stock,
            "in_transit_quantity": inventory.in_transit_quantity,
            "available_stock": inventory.available_stock,
        }


    # ------------------------------------------------------------------
    # Expansión 7: Historial de cambios
    # ------------------------------------------------------------------

    def _log_stock_change(
        self,
        inventory_id: int,
        previous_physical: int,
        new_physical: int,
        previous_digital: int,
        new_digital: int,
        change_type: str,
        movement_id: int = None,
        reason: str = None,
        digital_adjustment_notes: str = None,
        adjusted_by_name: str = None,
    ) -> None:
        """
        Expansión 7 - Registra cualquier cambio de stock en el historial.
        Llamado internamente por los métodos que modifican stock.
        """
        try:
            self.repository.create_history_record(
                inventory_id=inventory_id,
                previous_physical=previous_physical,
                new_physical=new_physical,
                previous_digital=previous_digital,
                new_digital=new_digital,
                change_type=change_type,
                movement_id=movement_id,
                reason=reason,
                digital_adjustment_notes=digital_adjustment_notes,
                adjusted_by_name=adjusted_by_name,
            )
        except Exception as e:
            # El historial nunca debe interrumpir el flujo principal
            logger.error(f"Error registrando historial para inventory {inventory_id}: {e}")

    def get_stock_history(
        self,
        inventory_id: int,
        limit: int = 50,
        date_from: datetime = None,
        date_to: datetime = None,
    ) -> Dict[str, Any]:
        """
        Expansión 7 - Retorna historial de cambios con paginación básica.
        """
        records = self.repository.get_history(
            inventory_id, limit=limit, date_from=date_from, date_to=date_to
        )
        return {
            "inventory_id": inventory_id,
            "total": len(records),
            "records": [r.to_dict() for r in records],
        }

    def get_discrepancy_history(
        self, inventory_id: int, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Expansión 7 - Historial de conteos que introdujeron discrepancia.
        """
        records = self.repository.get_history_by_change_type(
            inventory_id, "count", limit=limit
        )
        # Filtrar solo los que sí tenían discrepancia post-cambio
        return [
            r.to_dict()
            for r in records
            if abs(r.new_physical - r.new_digital) > 0
        ]

    # ------------------------------------------------------------------
    # Expansión 8: Valor de inventario
    # ------------------------------------------------------------------

    def update_unit_cost(
        self, inventory_id: int, cost: float
    ) -> Optional[Dict[str, Any]]:
        """
        Expansión 8 - Actualiza el costo unitario de un item.
        """
        if cost < 0:
            raise ValueError("El costo no puede ser negativo")
        updated = self.repository.update(inventory_id, {"unit_cost": cost})
        return updated.to_dict() if updated else None

    def get_inventory_value(self, branch_id: int = None) -> Dict[str, Any]:
        """
        Expansión 8 - Valor total del inventario por sucursal o global.
        """
        total_value = self.repository.get_total_inventory_value(branch_id)
        return {
            "branch_id": branch_id,
            "scope": "branch" if branch_id else "global",
            "total_value": round(total_value, 2),
        }

    def get_most_valuable_items(
        self, branch_id: int, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Expansión 8 - Top N items por valor total (digital_stock * unit_cost).
        """
        return self.repository.get_most_valuable_items(branch_id, limit=limit)


    # ------------------------------------------------------------------
    # Expansión 9: Métricas propias del service
    # ------------------------------------------------------------------

    def get_discrepancy_report(
        self, branch_id: int, days: int = 30
    ) -> Dict[str, Any]:
        """
        Expansión 9 - Items con más discrepancias en los últimos N días.
        """
        date_from = datetime.utcnow() - timedelta(days=days)
        date_to = datetime.utcnow()
        rows = self.repository.get_items_with_discrepancy_in_period(
            branch_id, date_from, date_to
        )
        return {
            "branch_id": branch_id,
            "period_days": days,
            "items": rows,
        }

    def get_no_movement_products(
        self, branch_id: int, days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Expansión 9 - Productos sin ningún movimiento registrado en los últimos N días.
        """
        since = datetime.utcnow() - timedelta(days=days)
        items = self.repository.get_items_with_no_history_since(branch_id, since)
        return [self._enrich_inventory(i) for i in items]

    def get_rotation_rate(
        self, product_id: int, branch_id: int, days: int = 30
    ) -> Dict[str, Any]:
        """
        Expansión 9 - Tasa de rotación: cantidad de registros en historial / días.
        """
        inventory = self.repository.get_by_product_branch(product_id, branch_id)
        if not inventory:
            return {"product_id": product_id, "branch_id": branch_id, "rotation_rate": 0}

        date_from = datetime.utcnow() - timedelta(days=days)
        records = self.repository.get_history(
            inventory.id, limit=10000, date_from=date_from
        )
        rate = len(records) / days if days > 0 else 0
        return {
            "product_id": product_id,
            "branch_id": branch_id,
            "inventory_id": inventory.id,
            "period_days": days,
            "movement_count": len(records),
            "rotation_rate": round(rate, 4),
        }

    def get_stock_turnover(
        self, branch_id: int, days: int = 30
    ) -> Dict[str, Any]:
        """
        Expansión 9 - Rotación general de la sucursal: movimientos totales / items activos.
        """
        date_from = datetime.utcnow() - timedelta(days=days)
        date_to = datetime.utcnow()
        discrepancy_rows = self.repository.get_items_with_discrepancy_in_period(
            branch_id, date_from, date_to
        )
        total_events = sum(r["discrepancy_count"] for r in discrepancy_rows)
        total_items = self.repository.count(branch_id=branch_id)

        turnover = total_events / total_items if total_items > 0 else 0
        return {
            "branch_id": branch_id,
            "period_days": days,
            "total_stock_events": total_events,
            "total_items": total_items,
            "turnover_rate": round(turnover, 4),
        }

    def get_discrepancy_rate_by_branch(self, branch_id: int) -> Dict[str, Any]:
        """
        Expansión 9 - Porcentaje de items con discrepancia en la sucursal.
        """
        data = self.repository.get_discrepancy_rate_data(branch_id)
        total = data["total"]
        with_disc = data["with_discrepancy"]
        rate = (with_disc / total * 100) if total > 0 else 0.0
        return {
            "branch_id": branch_id,
            "total_items": total,
            "items_with_discrepancy": with_disc,
            "discrepancy_rate_percent": round(rate, 2),
        }

    def get_reorder_suggestions(self, branch_id: int) -> List[Dict[str, Any]]:
        """
        Expansión 9 - Combina low stock + reorder_priority para sugerencias de reposición.
        """
        items = self.repository.get_low_stock_ordered_by_priority(branch_id)
        result = []
        for item in items:
            enriched = self._enrich_inventory(item)
            enriched["suggested_order_qty"] = max(
                0, (item.min_stock * 2) - item.digital_stock
            )
            result.append(enriched)
        return result

    def get_inventory_age_distribution(
        self, branch_id: int
    ) -> Dict[str, Any]:
        """
        Expansión 9 - Distribución de antigüedad de stocks basada en last_count_date.
        Grupos: sin_conteo, reciente (<=7d), moderado (7-30d), antiguo (>30d).
        """
        items = self.repository.get_all(limit=10000, branch_id=branch_id)
        now = datetime.utcnow()
        buckets: Dict[str, int] = {
            "sin_conteo": 0,
            "reciente_7d": 0,
            "moderado_7_30d": 0,
            "antiguo_mas_30d": 0,
        }
        for item in items:
            if item.last_count_date is None:
                buckets["sin_conteo"] += 1
            else:
                # last_count_date puede ser timezone-aware; normalizar a naive
                lcd = item.last_count_date
                if hasattr(lcd, "tzinfo") and lcd.tzinfo is not None:
                    lcd = lcd.replace(tzinfo=None)
                delta = (now - lcd).days
                if delta <= 7:
                    buckets["reciente_7d"] += 1
                elif delta <= 30:
                    buckets["moderado_7_30d"] += 1
                else:
                    buckets["antiguo_mas_30d"] += 1

        return {"branch_id": branch_id, "total": len(items), "distribution": buckets}

    # ------------------------------------------------------------------
    # Registro de ajustes digitales
    # ------------------------------------------------------------------

    def get_digital_adjustments(
        self, inventory_id: int, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Historial filtrado solo de ajustes digitales."""
        records = self.repository.get_history_by_change_type(
            inventory_id, "adjustment", limit=limit
        )
        return [r.to_dict() for r in records]

    # ------------------------------------------------------------------
    # Workflow de conteos (sesiones)
    # ------------------------------------------------------------------

    def create_count_session(
        self,
        branch_id: int,
        scheduled_date: datetime,
        notes: str = None,
    ) -> Dict[str, Any]:
        """Crear sesión de conteo programada."""
        session = self.repository.create_count_session({
            "branch_id": branch_id,
            "scheduled_date": scheduled_date,
            "notes": notes,
            "status": "pending",
            "validator_count": 1,
        })
        event_bus.emit(settings.Events.COUNT_SESSION_CREATED, {
            "session_id": session.id,
            "branch_id": branch_id,
            "scheduled_date": scheduled_date.isoformat() if scheduled_date else None,
        })
        logger.info(f"Count session created: {session.id} for branch {branch_id}")
        return session.to_dict()

    def start_count_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Iniciar sesión de conteo (status → in_progress)."""
        session = self.repository.get_count_session_by_id(session_id)
        if not session:
            return None
        if session.status not in ("pending",):
            raise ValueError(f"No se puede iniciar sesión en estado '{session.status}'")

        updated = self.repository.update_count_session(session_id, {
            "status": "in_progress",
            "started_at": datetime.utcnow(),
        })
        if updated and updated.branch_id:
            self.repository.populate_count_items_for_session(session_id, updated.branch_id)

        event_bus.emit(settings.Events.COUNT_SESSION_STARTED, {
            "session_id": session_id,
            "branch_id": updated.branch_id if updated else None,
        })
        logger.info(f"Count session started: {session_id}")
        return updated.to_dict() if updated else None

    def record_count_item(
        self,
        session_id: int,
        inventory_id: int,
        counted_physical: int,
        validator_name: str = None,
        notes: str = None,
    ) -> Optional[Dict[str, Any]]:
        """Registrar conteo de un item en la sesión."""
        session = self.repository.get_count_session_by_id(session_id)
        if not session or session.status != "in_progress":
            raise ValueError("La sesión no está en progreso")

        inventory = self.repository.get_by_id(inventory_id)
        if not inventory:
            raise ValueError("Item de inventario no encontrado")

        item = self.repository.get_count_item_by_inventory(session_id, inventory_id)
        expected = item.expected_physical if item else inventory.physical_stock
        difference = counted_physical - expected
        is_discrepancy = difference != 0

        item_data = {
            "counted_physical": counted_physical,
            "difference": difference,
            "is_discrepancy": is_discrepancy,
            "counted_at": datetime.utcnow(),
            "validator_name": validator_name,
            "notes": notes,
        }

        if item:
            updated_item = self.repository.update_count_item(item.id, item_data)
        else:
            item_data.update({
                "inventory_id": inventory_id,
                "product_id": inventory.product_id,
                "expected_physical": expected,
            })
            updated_item = self.repository.add_count_item(session_id, item_data)

        # Aplicar conteo físico real (sin re-sincronizar item de sesión)
        self.adjust_physical_stock(
            inventory.product_id,
            inventory.branch_id,
            counted_physical,
            notes=notes,
            validator_name=validator_name,
            skip_session_sync=True,
        )

        event_bus.emit(settings.Events.COUNT_ITEM_RECORDED, {
            "session_id": session_id,
            "inventory_id": inventory_id,
            "counted_physical": counted_physical,
            "difference": difference,
            "is_discrepancy": is_discrepancy,
        })

        return updated_item.to_dict() if updated_item else None

    def complete_count_session(
        self, session_id: int, validator_count: int = 1
    ) -> Optional[Dict[str, Any]]:
        """Completar sesión de conteo."""
        session = self.repository.get_count_session_by_id(session_id)
        if not session:
            return None
        if session.status != "in_progress":
            raise ValueError(f"No se puede completar sesión en estado '{session.status}'")

        updated = self.repository.update_count_session(session_id, {
            "status": "completed",
            "completed_at": datetime.utcnow(),
            "validator_count": max(1, validator_count),
        })

        # Limpiar vínculo de sesión activa en inventario
        items = self.repository.get_count_items(session_id)
        for item in items:
            if item.inventory_id:
                inv = self.repository.get_by_id(item.inventory_id)
                if inv and inv.count_session_id == session_id:
                    self.repository.update(item.inventory_id, {"count_session_id": None})

        event_bus.emit(settings.Events.COUNT_SESSION_COMPLETED, {
            "session_id": session_id,
            "branch_id": session.branch_id,
            "validator_count": max(1, validator_count),
        })
        logger.info(f"Count session completed: {session_id}")
        return updated.to_dict() if updated else None

    def cancel_count_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Cancelar sesión de conteo."""
        session = self.repository.get_count_session_by_id(session_id)
        if not session:
            return None
        if session.status == "completed":
            raise ValueError("No se puede cancelar una sesión completada")

        updated = self.repository.update_count_session(session_id, {
            "status": "cancelled",
            "completed_at": datetime.utcnow(),
        })
        return updated.to_dict() if updated else None

    def get_count_session_summary(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Resumen de una sesión de conteo."""
        session = self.repository.get_count_session_by_id(session_id)
        if not session:
            return None

        items = self.repository.get_count_items(session_id)
        total = len(items)
        counted = sum(1 for i in items if i.counted_physical is not None)
        discrepancies = sum(1 for i in items if i.is_discrepancy)

        return {
            "session": session.to_dict(),
            "total_items": total,
            "counted_items": counted,
            "pending_items": total - counted,
            "discrepancy_count": discrepancies,
            "items": [i.to_dict() for i in items],
        }

    def get_pending_count_sessions(
        self, branch_id: int = None
    ) -> List[Dict[str, Any]]:
        """Sesiones pendientes (hoy o vencidas)."""
        sessions = self.repository.get_pending_count_sessions()
        if branch_id:
            sessions = [s for s in sessions if s.branch_id == branch_id]
        return [s.to_dict() for s in sessions]

    def get_overdue_count_sessions(
        self, branch_id: int = None
    ) -> List[Dict[str, Any]]:
        """Sesiones vencidas."""
        sessions = self.repository.get_overdue_count_sessions()
        if branch_id:
            sessions = [s for s in sessions if s.branch_id == branch_id]
        return [s.to_dict() for s in sessions]

    def get_count_sessions_by_branch(
        self, branch_id: int, status: str = None
    ) -> List[Dict[str, Any]]:
        """Listar sesiones de una sucursal."""
        sessions = self.repository.get_count_sessions_by_branch(branch_id, status)
        return [s.to_dict() for s in sessions]

    def _link_physical_count_to_session(
        self,
        session_id: int,
        inventory_id: int,
        product_id: int,
        counted_physical: int,
        notes: str = None,
        validator_name: str = None,
    ) -> None:
        """Vincula un conteo físico directo a la sesión activa sin re-aplicar stock."""
        item = self.repository.get_count_item_by_inventory(session_id, inventory_id)
        inventory = self.repository.get_by_id(inventory_id)
        expected = item.expected_physical if item else (inventory.physical_stock if inventory else 0)
        difference = counted_physical - expected

        item_data = {
            "counted_physical": counted_physical,
            "difference": difference,
            "is_discrepancy": difference != 0,
            "counted_at": datetime.utcnow(),
            "validator_name": validator_name,
            "notes": notes,
        }
        if item:
            self.repository.update_count_item(item.id, item_data)
        else:
            item_data.update({
                "inventory_id": inventory_id,
                "product_id": product_id,
                "expected_physical": expected,
            })
            self.repository.add_count_item(session_id, item_data)

        event_bus.emit(settings.Events.COUNT_ITEM_RECORDED, {
            "session_id": session_id,
            "inventory_id": inventory_id,
            "counted_physical": counted_physical,
            "difference": difference,
            "is_discrepancy": difference != 0,
        })

    # ------------------------------------------------------------------
    # Lotes y fechas de caducidad
    # ------------------------------------------------------------------

    def add_batch(
        self,
        inventory_id: int,
        batch_number: str = None,
        manufacturing_date: date = None,
        expiration_date: date = None,
        quantity: int = 0,
        unit_cost: float = None,
        notes: str = None,
    ) -> Dict[str, Any]:
        """Agregar lote a un item de inventario."""
        if quantity < 0:
            raise ValueError("La cantidad del lote no puede ser negativa")

        batch = self.repository.add_batch(inventory_id, {
            "batch_number": batch_number,
            "manufacturing_date": manufacturing_date,
            "expiration_date": expiration_date,
            "quantity": quantity,
            "unit_cost": unit_cost,
            "notes": notes,
        })

        event_bus.emit(settings.Events.BATCH_ADDED, {
            "batch_id": batch.id,
            "inventory_id": inventory_id,
            "batch_number": batch_number,
            "quantity": quantity,
        })

        if expiration_date:
            days_left = (expiration_date - date.today()).days
            if 0 <= days_left <= 30:
                event_bus.emit(settings.Events.BATCH_EXPIRING, {
                    "batch_id": batch.id,
                    "inventory_id": inventory_id,
                    "expiration_date": expiration_date.isoformat(),
                    "days_remaining": days_left,
                })

        return batch.to_dict()

    def get_inventory_batches(self, inventory_id: int) -> List[Dict[str, Any]]:
        """Obtener todos los lotes de un item."""
        batches = self.repository.get_batches_by_inventory(inventory_id)
        return [b.to_dict() for b in batches]

    def consume_batch(self, inventory_id: int, quantity: int) -> Dict[str, Any]:
        """Consumir del lote más antiguo (FIFO)."""
        if quantity <= 0:
            raise ValueError("La cantidad debe ser positiva")

        batches = self.repository.get_batches_by_inventory(inventory_id)
        remaining = quantity
        consumed = []

        for batch in batches:
            if remaining <= 0:
                break
            if batch.quantity <= 0:
                continue
            take = min(batch.quantity, remaining)
            updated = self.repository.consume_from_batch(batch.id, take)
            if updated:
                consumed.append({"batch_id": batch.id, "quantity": take})
                remaining -= take
                event_bus.emit(settings.Events.BATCH_CONSUMED, {
                    "batch_id": batch.id,
                    "inventory_id": inventory_id,
                    "quantity_consumed": take,
                    "remaining_in_batch": updated.quantity,
                })

        return {
            "inventory_id": inventory_id,
            "requested": quantity,
            "consumed": quantity - remaining,
            "batches": consumed,
        }

    def get_expiring_batches(
        self, branch_id: int = None, days: int = 30
    ) -> List[Dict[str, Any]]:
        """Lotes próximos a vencer."""
        batches = self.repository.get_batches_near_expiration(branch_id, days)
        result = []
        for b in batches:
            data = b.to_dict()
            if b.expiration_date:
                data["days_remaining"] = (b.expiration_date - date.today()).days
            result.append(data)
        return result

    def get_batch_summary(self, inventory_id: int) -> Dict[str, Any]:
        """Resumen de lotes vs stock total."""
        inventory = self.repository.get_by_id(inventory_id)
        if not inventory:
            return {}

        batches = self.repository.get_batches_by_inventory(inventory_id)
        batch_total = sum(b.quantity for b in batches)

        return {
            "inventory_id": inventory_id,
            "digital_stock": inventory.digital_stock,
            "batch_total_quantity": batch_total,
            "batch_count": len(batches),
            "has_batches": len(batches) > 0,
            "batches": [b.to_dict() for b in batches],
        }

    # ------------------------------------------------------------------
    # Ubicación jerárquica
    # ------------------------------------------------------------------

    def set_hierarchical_location(
        self,
        inventory_id: int,
        aisle: str = None,
        shelf: str = None,
        level: str = None,
        bin: str = None,
        free_text: str = None,
    ) -> Optional[Dict[str, Any]]:
        """Establecer ubicación jerárquica y/o texto libre."""
        update_data = {
            "aisle": aisle,
            "shelf": shelf,
            "level": level,
            "bin": bin,
        }
        if free_text is not None:
            update_data["location_free"] = free_text

        updated = self.repository.update(inventory_id, update_data)
        return updated.to_dict() if updated else None

    def get_location_path(self, inventory_id: int) -> Optional[str]:
        """Obtener path completo formateado de ubicación."""
        inventory = self.repository.get_by_id(inventory_id)
        return inventory.location_path if inventory else None

    def get_items_by_aisle(self, branch_id: int, aisle: str) -> List[Dict[str, Any]]:
        """Items en un pasillo."""
        items = self.repository.get_items_in_aisle(branch_id, aisle)
        return [self._enrich_inventory(i) for i in items]

    def search_by_location(self, branch_id: int, query: str) -> List[Dict[str, Any]]:
        """Buscar por cualquier parte de la ubicación."""
        items = self.repository.search_by_location_text(branch_id, query)
        return [i.to_dict() for i in items]

    def get_location_summary(self, branch_id: int) -> List[Dict[str, Any]]:
        """Resumen de distribución por ubicación."""
        return self.repository.get_location_summary(branch_id)

    def get_all_aisles(self, branch_id: int) -> List[str]:
        """Lista de pasillos en una sucursal."""
        return self.repository.get_all_aisles_in_branch(branch_id)

    # ------------------------------------------------------------------
    # Unidades de medida variables
    # ------------------------------------------------------------------

    def get_stock_in_unit(self, inventory_id: int, unit: str = "base") -> Optional[Dict[str, Any]]:
        """Obtener stock en unidad específica."""
        inventory = self.repository.get_by_id(inventory_id)
        if not inventory:
            return None

        if unit == "base":
            return {
                "inventory_id": inventory_id,
                "unit": "base",
                "quantity": inventory.digital_stock,
            }

        if unit == "alternate":
            if not inventory.alternate_unit or not inventory.conversion_factor:
                return None
            return {
                "inventory_id": inventory_id,
                "unit": inventory.alternate_unit,
                "quantity": inventory.stock_in_alternate_unit,
                "conversion_factor": inventory.conversion_factor,
            }

        return None

    def convert_stock_unit(
        self, inventory_id: int, from_unit: str, to_unit: str
    ) -> Optional[float]:
        """Convertir stock entre unidades base y alternativa."""
        inventory = self.repository.get_by_id(inventory_id)
        if not inventory or not inventory.conversion_factor:
            return None

        if from_unit == "base" and to_unit == "alternate":
            return inventory.stock_in_alternate_unit
        if from_unit == "alternate" and to_unit == "base":
            return inventory.digital_stock

        return None

    def adjust_alternate_stock(
        self, inventory_id: int, quantity: float, unit: str = "alternate"
    ) -> Optional[Dict[str, Any]]:
        """Ajustar stock expresado en unidad alternativa."""
        inventory = self.repository.get_by_id(inventory_id)
        if not inventory or not inventory.conversion_factor:
            raise ValueError("Unidad alternativa no configurada")

        if unit == "alternate":
            base_qty = int(quantity * inventory.conversion_factor)
        else:
            base_qty = int(quantity)

        return self.adjust_digital_stock(
            inventory.product_id,
            inventory.branch_id,
            base_qty,
            is_absolute=True,
            reason=f"Ajuste en unidad alternativa ({quantity} {inventory.alternate_unit or unit})",
        )

    # ------------------------------------------------------------------
    # Valoración ampliada
    # ------------------------------------------------------------------

    def get_valuation_by_category(self, branch_id: int) -> List[Dict[str, Any]]:
        """Valor agrupado por categoría de producto."""
        return self.repository.get_valuation_by_category(branch_id)

    def get_cost_history(self, inventory_id: int) -> List[Dict[str, Any]]:
        """Historial de cambios de costo vía PriceHistory del producto."""
        from models.price_history import PriceHistory

        inventory = self.repository.get_by_id(inventory_id)
        if not inventory:
            return []

        records = (
            self.repository.db.query(PriceHistory)
            .filter(PriceHistory.product_id == inventory.product_id)
            .order_by(PriceHistory.created_at.desc())
            .limit(50)
            .all()
        )
        return [r.to_dict() for r in records]
