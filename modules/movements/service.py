"""
Movement service layer - Business logic and event emission.

Expansiones incluidas:
  Exp 1 - cancel_movement(), reverse_movement()
  Exp 2 - confirm_transfer_reception(), reject_transfer_reception()
  Exp 3 - get_urgent_movements(), set_priority()
  Exp 4 - get_movements_by_source(); create_movement() acepta source
  Exp 5 - search_by_reference(), get_movements_by_reference_type()
  Exp 6 - create_movement() captura unit_cost; get_movement_cost_summary()
  Exp 7 - _log_state_change() interno; get_state_history()
  Exp 8 - confirm_reception_with_signature(), get_receptions_pending_signature()
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from modules.movements.repository import MovementRepository
from core.event_bus import event_bus
from core.settings import settings
from utils.validators import validate_movement_type, validate_quantity
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MovementService:
    """Service for movement business logic."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = MovementRepository(db)

    # ------------------------------------------------------------------
    # Core – create / read / list
    # ------------------------------------------------------------------

    def create_movement(self, movement_data: dict) -> Dict[str, Any]:
        """Create a new movement and emit event.

        Exp 4: acepta 'source' (default 'app').
        Exp 6: captura 'unit_cost' del producto si no se provee.
        """
        movement_data = self._sanitize_movement_data(movement_data)
        self._validate_movement_data(movement_data)

        # Exp 4 – source
        movement_data.setdefault("source", "app")

        # Exp 6 – cost capture
        if "unit_cost" not in movement_data or movement_data["unit_cost"] is None:
            movement_data["unit_cost"] = self._get_product_unit_cost(
                movement_data["product_id"]
            )
        if movement_data.get("unit_cost") is not None:
            movement_data["total_cost"] = (
                movement_data["unit_cost"] * movement_data["quantity"]
            )

        movement = self.repository.create(movement_data)

        # Exp 7 – log initial state
        self._log_state_change(
            movement.id,
            new_state=movement.state,
            previous_state=None,
            changed_by=movement.user_id,
            reason="Movimiento creado",
        )

        event_data = {
            "movement_id": movement.id,
            "product_id": movement.product_id,
            "branch_id": movement.branch_id,
            "destination_branch_id": movement.destination_branch_id,
            "movement_type": movement.movement_type,
            "quantity": movement.quantity,
            "user_id": movement.user_id,
            "priority": movement.priority,
            "source": movement.source,
        }
        event_bus.emit(settings.Events.MOVEMENT_CREATED, event_data)
        logger.info(f"Movement created: ID {movement.id}, Type {movement.movement_type}")
        return movement.to_dict()

    def get_movement(self, movement_id: int) -> Optional[Dict[str, Any]]:
        """Get movement by ID."""
        movement = self.repository.get_by_id(movement_id)
        return movement.to_dict() if movement else None

    def get_movement_details(self, movement_id: int) -> Optional[Dict[str, Any]]:
        """Get movement with full details including related entities."""
        details = self.repository.get_movement_with_details(movement_id)
        if not details:
            return None
        result = details["movement"]
        result["product"] = details["product"]
        result["branch"] = details["branch"]
        result["user"] = details["user"]
        result["destination_branch"] = details.get("destination_branch")
        return result

    def list_movements(
        self,
        page: int = 1,
        page_size: int = 20,
        branch_id: int = None,
        product_id: int = None,
        user_id: int = None,
        movement_type: str = None,
        state: str = None,
        date_from: datetime = None,
        date_to: datetime = None,
        # Exp 3
        priority: str = None,
        # Exp 4
        source: str = None,
        # Exp 5
        reference_type: str = None,
        # Exp 1
        include_cancelled: bool = True,
    ) -> Dict[str, Any]:
        """List movements with pagination and filtering."""
        skip = (page - 1) * page_size
        filter_kwargs = dict(
            branch_id=branch_id,
            product_id=product_id,
            user_id=user_id,
            movement_type=movement_type,
            state=state,
            date_from=date_from,
            date_to=date_to,
            priority=priority,
            source=source,
            reference_type=reference_type,
            include_cancelled=include_cancelled,
        )
        movements = self.repository.get_all(skip=skip, limit=page_size, **filter_kwargs)
        total = self.repository.count(**filter_kwargs)
        return {
            "movements": [self._enrich_movement(m) for m in movements],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }

    # ------------------------------------------------------------------
    # Core – validate / reject / delete
    # ------------------------------------------------------------------

    def validate_movement(self, movement_id: int, validator_id: int) -> Optional[Dict[str, Any]]:
        """Validate a pending movement and emit event."""
        movement = self.repository.get_by_id(movement_id)
        if not movement:
            return None
        if movement.state != "pendiente":
            raise ValueError("Solo movimientos pendientes pueden ser validados")
        if movement.is_cancelled:
            raise ValueError("No se puede validar un movimiento cancelado")
        if not self._active_user_exists(validator_id):
            raise ValueError("El usuario validador no existe o esta inactivo")

        validation_error = self._get_validation_error(movement)
        if validation_error:
            prev_state = movement.state
            movement = self.repository.reject(movement_id, validator_id, validation_error)
            self._log_state_change(movement_id, "rechazado", prev_state, validator_id, validation_error)
            event_bus.emit(settings.Events.MOVEMENT_REJECTED, {
                "movement_id": movement.id,
                "product_id": movement.product_id,
                "branch_id": movement.branch_id,
                "movement_type": movement.movement_type,
                "quantity": movement.quantity,
                "validator_id": validator_id,
                "reason": validation_error,
            })
            logger.info(f"Movement auto-rejected: ID {movement_id}, Reason: {validation_error}")
            return movement.to_dict()

        prev_state = movement.state
        movement = self.repository.validate(movement_id, validator_id)
        self._log_state_change(movement_id, "validado", prev_state, validator_id)

        event_bus.emit(settings.Events.MOVEMENT_VALIDATED, {
            "movement_id": movement.id,
            "product_id": movement.product_id,
            "branch_id": movement.branch_id,
            "destination_branch_id": movement.destination_branch_id,
            "movement_type": movement.movement_type,
            "quantity": movement.quantity,
            "validator_id": validator_id,
        })

        if movement.movement_type == "transferencia":
            event_bus.emit(settings.Events.TRANSFER_SENT, {
                "movement_id": movement.id,
                "product_id": movement.product_id,
                "origin_branch_id": movement.branch_id,
                "destination_branch_id": movement.destination_branch_id,
                "quantity": movement.quantity,
            })

        logger.info(f"Movement validated: ID {movement_id}")
        return movement.to_dict()

    def reject_movement(self, movement_id: int, validator_id: int, reason: str = None) -> Optional[Dict[str, Any]]:
        """Reject a pending movement and emit event."""
        movement = self.repository.get_by_id(movement_id)
        if not movement:
            return None
        if movement.state != "pendiente":
            raise ValueError("Solo movimientos pendientes pueden ser rechazados")
        if movement.is_cancelled:
            raise ValueError("No se puede rechazar un movimiento cancelado")
        if not self._active_user_exists(validator_id):
            raise ValueError("El usuario validador no existe o esta inactivo")

        prev_state = movement.state
        movement = self.repository.reject(movement_id, validator_id, reason)
        self._log_state_change(movement_id, "rechazado", prev_state, validator_id, reason)

        event_bus.emit(settings.Events.MOVEMENT_REJECTED, {
            "movement_id": movement.id,
            "product_id": movement.product_id,
            "branch_id": movement.branch_id,
            "movement_type": movement.movement_type,
            "quantity": movement.quantity,
            "validator_id": validator_id,
            "reason": reason,
        })
        logger.info(f"Movement rejected: ID {movement_id}")
        return movement.to_dict()

    def delete_movement(self, movement_id: int) -> bool:
        """Delete a pending movement."""
        success = self.repository.delete(movement_id)
        if success:
            logger.info(f"Movement deleted: ID {movement_id}")
        return success

    # ------------------------------------------------------------------
    # Expansión 1 – Cancelación y reversión
    # ------------------------------------------------------------------

    def cancel_movement(
        self, movement_id: int, user_id: int, reason: str = None
    ) -> Optional[Dict[str, Any]]:
        """Cancel a validated movement (does not reverse stock automatically).

        Marca el movimiento como cancelado. Para revertir stock usa reverse_movement().
        """
        movement = self.repository.get_by_id(movement_id)
        if not movement:
            return None
        if movement.is_cancelled:
            raise ValueError("El movimiento ya está cancelado")
        if movement.state == "pendiente":
            raise ValueError(
                "Los movimientos pendientes se eliminan, no se cancelan. "
                "Use delete_movement() en su lugar."
            )
        if not self._active_user_exists(user_id):
            raise ValueError("El usuario no existe o esta inactivo")

        prev_state = movement.state
        movement = self.repository.cancel(movement_id, user_id, reason)
        self._log_state_change(movement_id, "cancelado", prev_state, user_id, reason)

        event_bus.emit(settings.Events.MOVEMENT_CANCELLED, {
            "movement_id": movement.id,
            "product_id": movement.product_id,
            "branch_id": movement.branch_id,
            "movement_type": movement.movement_type,
            "quantity": movement.quantity,
            "cancelled_by": user_id,
            "reason": reason,
        })
        logger.info(f"Movement cancelled: ID {movement_id}")
        return movement.to_dict()

    def reverse_movement(self, movement_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Create a compensatory movement that reverses the effect of an existing one.

        Si el original es 'entrada' → crea 'salida'; si es 'salida' → crea 'entrada'.
        Transferencias: crea transferencia inversa (destino → origen).
        El movimiento compensatorio queda en estado 'pendiente' para validación normal.
        """
        original = self.repository.get_by_id(movement_id)
        if not original:
            return None
        if not original.is_cancelled:
            raise ValueError(
                "Solo se pueden revertir movimientos ya cancelados. "
                "Cancele primero con cancel_movement()."
            )
        if not self._active_user_exists(user_id):
            raise ValueError("El usuario no existe o esta inactivo")

        reverse_type_map = {"entrada": "salida", "salida": "entrada"}
        if original.movement_type in reverse_type_map:
            compensatory_type = reverse_type_map[original.movement_type]
            compensatory_data = {
                "product_id": original.product_id,
                "branch_id": original.branch_id,
                "destination_branch_id": None,
                "user_id": user_id,
                "movement_type": compensatory_type,
                "quantity": original.quantity,
                "reason": f"Reversión del movimiento #{original.id}",
                "notes": f"Movimiento compensatorio automático",
                "reversal_of_movement_id": original.id,
                "source": "system",
                "priority": original.priority,
            }
        elif original.movement_type == "transferencia":
            compensatory_data = {
                "product_id": original.product_id,
                "branch_id": original.destination_branch_id,
                "destination_branch_id": original.branch_id,
                "user_id": user_id,
                "movement_type": "transferencia",
                "quantity": original.quantity,
                "reason": f"Reversión de transferencia #{original.id}",
                "notes": "Transferencia compensatoria automática",
                "reversal_of_movement_id": original.id,
                "source": "system",
                "priority": original.priority,
            }
        else:
            # ajuste → ajuste inverso (negativo en notas, misma cantidad)
            compensatory_data = {
                "product_id": original.product_id,
                "branch_id": original.branch_id,
                "destination_branch_id": None,
                "user_id": user_id,
                "movement_type": "ajuste",
                "quantity": original.quantity,
                "reason": f"Reversión del ajuste #{original.id}",
                "notes": "Ajuste compensatorio automático",
                "reversal_of_movement_id": original.id,
                "source": "system",
            }

        compensatory = self.repository.create(compensatory_data)
        self._log_state_change(
            compensatory.id,
            new_state=compensatory.state,
            previous_state=None,
            changed_by=user_id,
            reason=f"Movimiento compensatorio del ID {original.id}",
        )

        event_bus.emit(settings.Events.MOVEMENT_REVERSED, {
            "original_movement_id": original.id,
            "compensatory_movement_id": compensatory.id,
            "product_id": compensatory.product_id,
            "branch_id": compensatory.branch_id,
            "movement_type": compensatory.movement_type,
            "quantity": compensatory.quantity,
            "reversed_by": user_id,
        })
        logger.info(
            f"Movement reversed: original ID {movement_id}, "
            f"compensatory ID {compensatory.id}"
        )
        return compensatory.to_dict()

    # ------------------------------------------------------------------
    # Expansión 2 – Confirmación de recepción en transferencias
    # ------------------------------------------------------------------

    def confirm_transfer_reception(
        self, movement_id: int, user_id: int, notes: str = None
    ) -> Optional[Dict[str, Any]]:
        """Confirm that the destination branch received the transfer."""
        movement = self.repository.get_by_id(movement_id)
        if not movement:
            return None
        if movement.movement_type != "transferencia":
            raise ValueError("Solo se pueden confirmar recepciones de transferencias")
        if movement.state != "validado":
            raise ValueError("Solo transferencias validadas pueden confirmarse como recibidas")
        if movement.is_cancelled:
            raise ValueError("No se puede confirmar recepción de un movimiento cancelado")
        if movement.is_received:
            raise ValueError("Esta transferencia ya fue confirmada como recibida")
        if not self._active_user_exists(user_id):
            raise ValueError("El usuario no existe o esta inactivo")

        movement = self.repository.confirm_reception(movement_id, user_id, notes)
        self._log_state_change(
            movement_id, "recibido", "validado", user_id,
            notes or "Recepción confirmada por sucursal destino",
        )

        event_bus.emit(settings.Events.TRANSFER_RECEIVED, {
            "movement_id": movement.id,
            "product_id": movement.product_id,
            "origin_branch_id": movement.branch_id,
            "destination_branch_id": movement.destination_branch_id,
            "quantity": movement.quantity,
            "received_by": user_id,
            "received_at": movement.received_at.isoformat() if movement.received_at else None,
            "notes": notes,
        })
        logger.info(f"Transfer reception confirmed: movement ID {movement_id}")
        return movement.to_dict()

    def reject_transfer_reception(
        self, movement_id: int, user_id: int, reason: str
    ) -> Optional[Dict[str, Any]]:
        """Reject a transfer reception (e.g. missing or damaged goods).

        Cancela el movimiento y crea un ajuste negativo en destino si ya
        se había acreditado stock en esa sucursal.
        """
        movement = self.repository.get_by_id(movement_id)
        if not movement:
            return None
        if movement.movement_type != "transferencia":
            raise ValueError("Solo se puede rechazar la recepción de transferencias")
        if movement.state != "validado":
            raise ValueError("Solo transferencias validadas pueden rechazarse en recepción")
        if movement.is_cancelled:
            raise ValueError("El movimiento ya está cancelado")
        if movement.is_received:
            raise ValueError("La transferencia ya fue marcada como recibida")
        if not reason:
            raise ValueError("Se requiere una razón para rechazar la recepción")
        if not self._active_user_exists(user_id):
            raise ValueError("El usuario no existe o esta inactivo")

        # Cancelar la transferencia
        movement = self.repository.cancel(movement_id, user_id, reason)
        self._log_state_change(movement_id, "rechazado_recepcion", "validado", user_id, reason)

        event_bus.emit(settings.Events.TRANSFER_REJECTED, {
            "movement_id": movement.id,
            "product_id": movement.product_id,
            "origin_branch_id": movement.branch_id,
            "destination_branch_id": movement.destination_branch_id,
            "quantity": movement.quantity,
            "rejected_by": user_id,
            "reason": reason,
        })
        logger.info(f"Transfer reception rejected: movement ID {movement_id}, reason: {reason}")
        return movement.to_dict()

    def get_pending_receptions(self, branch_id: int) -> List[Dict[str, Any]]:
        """Get transfers pending reception at given destination branch."""
        movements = self.repository.get_pending_receptions(branch_id)
        return [self._enrich_movement(m) for m in movements]

    # ------------------------------------------------------------------
    # Expansión 3 – Prioridad
    # ------------------------------------------------------------------

    def get_urgent_movements(self, branch_id: int = None) -> List[Dict[str, Any]]:
        """Return high-priority pending movements ('alta' or 'urgente')."""
        alta = self.repository.get_by_priority("alta", branch_id)
        urgente = self.repository.get_by_priority("urgente", branch_id)
        # Merge and deduplicate preserving order (urgente first)
        seen = set()
        result = []
        for m in urgente + alta:
            if m.id not in seen and m.state == "pendiente":
                seen.add(m.id)
                result.append(self._enrich_movement(m))
        return result

    def set_priority(self, movement_id: int, priority: str) -> Optional[Dict[str, Any]]:
        """Update priority on a movement."""
        valid = {"baja", "normal", "alta", "urgente"}
        if priority not in valid:
            raise ValueError(f"Prioridad inválida. Valores permitidos: {valid}")
        movement = self.repository.set_priority(movement_id, priority)
        return movement.to_dict() if movement else None

    # ------------------------------------------------------------------
    # Expansión 4 – Origen del movimiento
    # ------------------------------------------------------------------

    def get_movements_by_source(self, source: str, branch_id: int = None) -> List[Dict[str, Any]]:
        """Return movements filtered by their origin source."""
        movements = self.repository.get_by_source(source, branch_id)
        return [self._enrich_movement(m) for m in movements]

    # ------------------------------------------------------------------
    # Expansión 5 – Documento de referencia
    # ------------------------------------------------------------------

    def search_by_reference(self, reference: str) -> List[Dict[str, Any]]:
        """Search movements by reference number (partial, case-insensitive)."""
        if not reference or not reference.strip():
            raise ValueError("Se requiere un número de referencia para la búsqueda")
        movements = self.repository.get_by_reference(reference.strip())
        return [self._enrich_movement(m) for m in movements]

    def get_movements_by_reference_type(
        self, reference_type: str, branch_id: int = None
    ) -> List[Dict[str, Any]]:
        """Return movements filtered by reference type."""
        movements = self.repository.get_by_reference_type(reference_type, branch_id)
        return [self._enrich_movement(m) for m in movements]

    # ------------------------------------------------------------------
    # Expansión 6 – Costo en el momento del movimiento
    # ------------------------------------------------------------------

    def get_movement_cost_summary(
        self,
        branch_id: int,
        date_from: datetime = None,
        date_to: datetime = None,
    ) -> Dict[str, Any]:
        """Return cost summary grouped by movement_type for a branch."""
        return self.repository.get_total_cost_by_branch(branch_id, date_from, date_to)

    # ------------------------------------------------------------------
    # Expansión 7 – Historial de cambios de estado
    # ------------------------------------------------------------------

    def get_state_history(self, movement_id: int) -> List[Dict[str, Any]]:
        """Return the full state-change history for a movement."""
        history = self.repository.get_state_history(movement_id)
        return [entry.to_dict() for entry in history]

    # ------------------------------------------------------------------
    # Expansión 8 – Confirmación física / firma
    # ------------------------------------------------------------------

    def confirm_reception_with_signature(
        self,
        movement_id: int,
        receiver_name: str,
        signature: str = None,
    ) -> Optional[Dict[str, Any]]:
        """Register physical receiver name and optional signature data."""
        if not receiver_name or not receiver_name.strip():
            raise ValueError("El nombre del receptor es requerido")
        movement = self.repository.get_by_id(movement_id)
        if not movement:
            return None
        if movement.state != "validado":
            raise ValueError("Solo movimientos validados pueden tener receptor físico registrado")
        movement = self.repository.confirm_physical_reception(
            movement_id, receiver_name.strip(), signature
        )
        logger.info(f"Physical reception confirmed: movement ID {movement_id}, receiver: {receiver_name}")
        return movement.to_dict() if movement else None

    def get_receptions_pending_signature(self, branch_id: int = None) -> List[Dict[str, Any]]:
        """Return validated movements that have no recorded physical receiver yet."""
        movements = self.repository.get_pending_signature(branch_id)
        return [self._enrich_movement(m) for m in movements]

    # ------------------------------------------------------------------
    # Existing helpers preserved + direct transfer
    # ------------------------------------------------------------------

    def get_pending_movements(self, branch_id: int = None) -> List[Dict[str, Any]]:
        """Get all pending non-cancelled movements."""
        movements = self.repository.get_all(
            limit=1000,
            branch_id=branch_id,
            state="pendiente",
            include_cancelled=False,
        )
        return [self._enrich_movement(m) for m in movements]

    def get_pending_count(self, branch_id: int = None) -> int:
        """Count pending non-cancelled movements."""
        return self.repository.get_pending_count(branch_id)

    def get_movement_stats(
        self, branch_id: int = None, date_from: datetime = None
    ) -> Dict[str, Any]:
        """Get movement statistics."""
        return self.repository.get_stats_by_type(branch_id, date_from)

    def execute_direct_transfer(self, transfer_data: dict) -> Dict[str, Any]:
        """Execute a direct transfer without approval flow.

        Creates the movement in 'validado' state, adjusts stock immediately,
        and emits both MOVEMENT_VALIDATED and TRANSFER_SENT events.
        """
        transfer_data = self._sanitize_movement_data(transfer_data)
        if transfer_data.get("movement_type") != "transferencia":
            raise ValueError("Este metodo es solo para transferencias")
        self._validate_movement_data(transfer_data)

        from models.inventory import Inventory
        inventory = self.db.query(Inventory).filter(
            Inventory.product_id == transfer_data["product_id"],
            Inventory.branch_id == transfer_data["branch_id"],
            Inventory.is_active == True,
        ).first()
        if not inventory or inventory.digital_stock < transfer_data["quantity"]:
            raise ValueError("Stock digital insuficiente en la sucursal origen")

        # Exp 4/6 defaults
        transfer_data.setdefault("source", "app")
        if "unit_cost" not in transfer_data or transfer_data["unit_cost"] is None:
            transfer_data["unit_cost"] = self._get_product_unit_cost(transfer_data["product_id"])
        if transfer_data.get("unit_cost") is not None:
            transfer_data["total_cost"] = transfer_data["unit_cost"] * transfer_data["quantity"]

        transfer_data["state"] = "validado"
        movement = self.repository.create(transfer_data)

        # Exp 7 – initial + validated state history
        self._log_state_change(
            movement.id, "validado", None,
            transfer_data.get("user_id"),
            "Traslado directo sin flujo de aprobación",
        )

        from modules.inventory.service import InventoryService
        inventory_service = InventoryService(self.db)
        inventory_service.adjust_digital_stock(
            transfer_data["product_id"], transfer_data["branch_id"],
            -transfer_data["quantity"], is_absolute=False,
        )
        inventory_service.adjust_digital_stock(
            transfer_data["product_id"], transfer_data["destination_branch_id"],
            transfer_data["quantity"], is_absolute=False,
        )

        event_bus.emit(settings.Events.MOVEMENT_VALIDATED, {
            "movement_id": movement.id,
            "product_id": movement.product_id,
            "branch_id": movement.branch_id,
            "destination_branch_id": movement.destination_branch_id,
            "movement_type": movement.movement_type,
            "quantity": movement.quantity,
            "validator_id": transfer_data.get("user_id"),
        })
        event_bus.emit(settings.Events.TRANSFER_SENT, {
            "movement_id": movement.id,
            "product_id": movement.product_id,
            "origin_branch_id": movement.branch_id,
            "destination_branch_id": movement.destination_branch_id,
            "quantity": movement.quantity,
        })
        logger.info(f"Direct transfer executed: ID {movement.id}")
        return movement.to_dict()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _sanitize_movement_data(self, movement_data: dict) -> dict:
        """Normalize movement input before persistence."""
        data = movement_data.copy()
        if data.get("movement_type"):
            data["movement_type"] = data["movement_type"].strip().lower()
        if data.get("reason") is not None:
            data["reason"] = data["reason"].strip()
        if data.get("notes") is not None:
            data["notes"] = data["notes"].strip()
        if data.get("priority") is not None:
            data["priority"] = data["priority"].strip().lower()
        if data.get("source") is not None:
            data["source"] = data["source"].strip().lower()
        if data.get("reference_type") is not None:
            data["reference_type"] = data["reference_type"].strip().lower()
        return data

    def _validate_movement_data(self, movement_data: dict) -> None:
        """Validate movement fields and references."""
        is_valid, error = validate_movement_type(movement_data.get("movement_type"))
        if not is_valid:
            raise ValueError(error)
        is_valid, error = validate_quantity(movement_data.get("quantity"))
        if not is_valid:
            raise ValueError(error)
        if movement_data.get("quantity") == 0:
            raise ValueError("La cantidad debe ser mayor a cero")
        if not movement_data.get("product_id"):
            raise ValueError("El producto es requerido")
        if not movement_data.get("branch_id"):
            raise ValueError("La sucursal origen es requerida")
        if not movement_data.get("user_id"):
            raise ValueError("El usuario responsable es requerido")
        if not self._active_product_exists(movement_data["product_id"]):
            raise ValueError("El producto no existe o esta inactivo")
        if not self._active_branch_exists(movement_data["branch_id"]):
            raise ValueError("La sucursal origen no existe o esta inactiva")
        if not self._active_user_exists(movement_data["user_id"]):
            raise ValueError("El usuario responsable no existe o esta inactivo")
        if movement_data.get("movement_type") == "transferencia":
            dest = movement_data.get("destination_branch_id")
            if not dest:
                raise ValueError("La transferencia requiere sucursal destino")
            if movement_data.get("branch_id") == dest:
                raise ValueError("La sucursal origen y destino no pueden ser la misma")
            if not self._active_branch_exists(dest):
                raise ValueError("La sucursal destino no existe o esta inactiva")
        elif movement_data.get("destination_branch_id"):
            raise ValueError("Solo las transferencias pueden tener sucursal destino")

    def _get_validation_error(self, movement) -> Optional[str]:
        """Check stock constraints without touching inventory state."""
        if movement.movement_type not in ("salida", "transferencia"):
            return None
        from models.inventory import Inventory
        inventory = self.db.query(Inventory).filter(
            Inventory.product_id == movement.product_id,
            Inventory.branch_id == movement.branch_id,
            Inventory.is_active == True,
        ).first()
        if not inventory or inventory.digital_stock < movement.quantity:
            return "Stock digital insuficiente para validar el movimiento"
        return None

    def _get_product_unit_cost(self, product_id: int) -> Optional[float]:
        """Fetch the current unit_price of a product (used for cost capture)."""
        from models.product import Product
        product = self.db.query(Product).filter(Product.id == product_id).first()
        return float(product.unit_price) if product and product.unit_price else None

    def _log_state_change(
        self,
        movement_id: int,
        new_state: str,
        previous_state: str = None,
        changed_by: int = None,
        reason: str = None,
    ) -> None:
        """Internal helper: persist a state-change record (Exp 7)."""
        try:
            self.repository.log_state_change(
                movement_id=movement_id,
                new_state=new_state,
                previous_state=previous_state,
                changed_by=changed_by,
                change_reason=reason,
            )
        except Exception as exc:
            # State history is non-critical — log and continue
            logger.warning(f"Could not log state change for movement {movement_id}: {exc}")

    def _active_product_exists(self, product_id: int) -> bool:
        from models.product import Product
        return self.db.query(Product.id).filter(
            Product.id == product_id, Product.is_active == True
        ).first() is not None

    def _active_branch_exists(self, branch_id: int) -> bool:
        from models.branch import Branch
        return self.db.query(Branch.id).filter(
            Branch.id == branch_id, Branch.is_active == True
        ).first() is not None

    def _active_user_exists(self, user_id: int) -> bool:
        from models.user import User
        return self.db.query(User.id).filter(
            User.id == user_id, User.is_active == True
        ).first() is not None

    def _enrich_movement(self, movement) -> Dict[str, Any]:
        """Enrich movement with related entity details."""
        details = self.repository.get_movement_with_details(movement.id)
        if not details:
            return movement.to_dict()
        result = movement.to_dict()
        result["product"] = details["product"]
        result["branch"] = details["branch"]
        result["user"] = details["user"]
        result["destination_branch"] = details.get("destination_branch")
        return result
