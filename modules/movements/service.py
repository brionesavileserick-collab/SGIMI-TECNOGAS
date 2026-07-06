"""
Movement service layer - Business logic and event emission.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from modules.movements.repository import MovementRepository
from modules.inventory.repository import InventoryRepository
from core.event_bus import event_bus
from core.settings import settings
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MovementService:
    """Service for movement business logic."""

    def __init__(self, db: Session):
        self.repository = MovementRepository(db)
        self.inventory_repository = InventoryRepository(db)

    def create_movement(self, movement_data: dict) -> Dict[str, Any]:
        """Create a new movement and emit event."""
        # Validate movement type
        valid_types = ["entrada", "salida", "ajuste", "transferencia"]
        if movement_data.get("movement_type") not in valid_types:
            raise ValueError(f"Tipo de movimiento invalido: {movement_data.get('movement_type')}")

        # Validate transfer destination
        if movement_data.get("movement_type") == "transferencia":
            if not movement_data.get("destination_branch_id"):
                raise ValueError("La transferencia requiere sucursal destino")
            if movement_data.get("branch_id") == movement_data.get("destination_branch_id"):
                raise ValueError("La sucursal origen y destino no pueden ser la misma")

        # Validate stock for salida
        if movement_data.get("movement_type") == "salida":
            inventory = self.inventory_repository.get_by_product_branch(
                movement_data.get("product_id"),
                movement_data.get("branch_id")
            )
            if not inventory or inventory.digital_stock < movement_data.get("quantity", 0):
                raise ValueError("Stock insuficiente para esta salida")

        # Create movement
        movement = self.repository.create(movement_data)

        # Emit event
        event_data = {
            "movement_id": movement.id,
            "product_id": movement.product_id,
            "branch_id": movement.branch_id,
            "destination_branch_id": movement.destination_branch_id,
            "movement_type": movement.movement_type,
            "quantity": movement.quantity,
            "user_id": movement.user_id
        }
        event_bus.emit(settings.Events.MOVEMENT_CREATED, event_data)

        logger.info(f"Movement created: ID {movement.id}, Type {movement.movement_type}")
        return movement.to_dict()

    def get_movement(self, movement_id: int) -> Optional[Dict[str, Any]]:
        """Get movement by ID."""
        movement = self.repository.get_by_id(movement_id)
        return movement.to_dict() if movement else None

    def get_movement_details(self, movement_id: int) -> Optional[Dict[str, Any]]:
        """Get movement with full details."""
        details = self.repository.get_movement_with_details(movement_id)
        if not details:
            return None

        result = details["movement"]
        result["product"] = details["product"]
        result["branch"] = details["branch"]
        result["user"] = details["user"]
        return result

    def list_movements(self, page: int = 1, page_size: int = 20,
                       branch_id: int = None, product_id: int = None,
                       user_id: int = None, movement_type: str = None,
                       state: str = None, date_from: datetime = None,
                       date_to: datetime = None) -> Dict[str, Any]:
        """List movements with pagination and filtering."""
        skip = (page - 1) * page_size
        movements = self.repository.get_all(
            skip=skip,
            limit=page_size,
            branch_id=branch_id,
            product_id=product_id,
            user_id=user_id,
            movement_type=movement_type,
            state=state,
            date_from=date_from,
            date_to=date_to
        )

        total = self.repository.count(
            branch_id=branch_id,
            product_id=product_id,
            user_id=user_id,
            movement_type=movement_type,
            state=state
        )

        return {
            "movements": [self._enrich_movement(m) for m in movements],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }

    def validate_movement(self, movement_id: int, validator_id: int) -> Optional[Dict[str, Any]]:
        """Validate a pending movement and emit event."""
        movement = self.repository.get_by_id(movement_id)
        if not movement:
            return None

        if movement.state != "pendiente":
            raise ValueError("Solo movimientos pendientes pueden ser validados")

        # Validate movement
        movement = self.repository.validate(movement_id, validator_id)

        # Emit validated event
        event_data = {
            "movement_id": movement.id,
            "product_id": movement.product_id,
            "branch_id": movement.branch_id,
            "destination_branch_id": movement.destination_branch_id,
            "movement_type": movement.movement_type,
            "quantity": movement.quantity,
            "validator_id": validator_id
        }
        event_bus.emit(settings.Events.MOVEMENT_VALIDATED, event_data)

        # For transfers, emit transfer sent event
        if movement.movement_type == "transferencia":
            transfer_data = {
                "movement_id": movement.id,
                "product_id": movement.product_id,
                "origin_branch_id": movement.branch_id,
                "destination_branch_id": movement.destination_branch_id,
                "quantity": movement.quantity
            }
            event_bus.emit(settings.Events.TRANSFER_SENT, transfer_data)

        logger.info(f"Movement validated: ID {movement_id}")
        return movement.to_dict()

    def reject_movement(self, movement_id: int, validator_id: int, reason: str = None) -> Optional[Dict[str, Any]]:
        """Reject a pending movement and emit event."""
        movement = self.repository.get_by_id(movement_id)
        if not movement:
            return None

        if movement.state != "pendiente":
            raise ValueError("Solo movimientos pendientes pueden ser rechazados")

        # Reject movement
        movement = self.repository.reject(movement_id, validator_id, reason)

        # Emit rejected event
        event_data = {
            "movement_id": movement.id,
            "product_id": movement.product_id,
            "branch_id": movement.branch_id,
            "movement_type": movement.movement_type,
            "quantity": movement.quantity,
            "validator_id": validator_id,
            "reason": reason
        }
        event_bus.emit(settings.Events.MOVEMENT_REJECTED, event_data)

        logger.info(f"Movement rejected: ID {movement_id}")
        return movement.to_dict()

    def delete_movement(self, movement_id: int) -> bool:
        """Delete a pending movement."""
        success = self.repository.delete(movement_id)
        if success:
            logger.info(f"Movement deleted: ID {movement_id}")
        return success

    def get_pending_movements(self, branch_id: int = None) -> List[Dict[str, Any]]:
        """Get all pending movements."""
        movements = self.repository.get_all(
            limit=1000,
            branch_id=branch_id,
            state="pendiente"
        )
        return [self._enrich_movement(m) for m in movements]

    def get_pending_count(self, branch_id: int = None) -> int:
        """Count pending movements."""
        return self.repository.get_pending_count(branch_id)

    def get_movement_stats(self, branch_id: int = None, date_from: datetime = None) -> Dict[str, Any]:
        """Get movement statistics."""
        return self.repository.get_stats_by_type(branch_id, date_from)

    def _enrich_movement(self, movement) -> Dict[str, Any]:
        """Enrich movement with related entity details."""
        details = self.repository.get_movement_with_details(movement.id)
        if not details:
            return movement.to_dict()

        result = movement.to_dict()
        result["product"] = details["product"]
        result["branch"] = details["branch"]
        result["user"] = details["user"]
        return result
