"""
Movement service layer - Business logic and event emission.
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

    def create_movement(self, movement_data: dict) -> Dict[str, Any]:
        """Create a new movement and emit event."""
        movement_data = self._sanitize_movement_data(movement_data)
        self._validate_movement_data(movement_data)

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
            state=state,
            date_from=date_from,
            date_to=date_to
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

        if not self._active_user_exists(validator_id):
            raise ValueError("El usuario validador no existe o esta inactivo")

        validation_error = self._get_validation_error(movement)
        if validation_error:
            movement = self.repository.reject(movement_id, validator_id, validation_error)
            event_data = {
                "movement_id": movement.id,
                "product_id": movement.product_id,
                "branch_id": movement.branch_id,
                "movement_type": movement.movement_type,
                "quantity": movement.quantity,
                "validator_id": validator_id,
                "reason": validation_error
            }
            event_bus.emit(settings.Events.MOVEMENT_REJECTED, event_data)
            logger.info(f"Movement rejected during validation: ID {movement_id}, Reason: {validation_error}")
            return movement.to_dict()

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

    def _get_validation_error(self, movement) -> Optional[str]:
        """Validate movement constraints without updating inventory state."""
        if movement.movement_type not in ("salida", "transferencia"):
            return None

        from models.inventory import Inventory

        inventory = self.db.query(Inventory).filter(
            Inventory.product_id == movement.product_id,
            Inventory.branch_id == movement.branch_id,
            Inventory.is_active == True
        ).first()

        if not inventory or inventory.digital_stock < movement.quantity:
            return "Stock digital insuficiente para validar el movimiento"

        return None

    def reject_movement(self, movement_id: int, validator_id: int, reason: str = None) -> Optional[Dict[str, Any]]:
        """Reject a pending movement and emit event."""
        movement = self.repository.get_by_id(movement_id)
        if not movement:
            return None

        if movement.state != "pendiente":
            raise ValueError("Solo movimientos pendientes pueden ser rechazados")

        if not self._active_user_exists(validator_id):
            raise ValueError("El usuario validador no existe o esta inactivo")

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

    def _sanitize_movement_data(self, movement_data: dict) -> dict:
        """Normalize movement input before persistence."""
        data = movement_data.copy()
        if data.get("movement_type"):
            data["movement_type"] = data["movement_type"].strip().lower()
        if data.get("reason") is not None:
            data["reason"] = data["reason"].strip()
        if data.get("notes") is not None:
            data["notes"] = data["notes"].strip()
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
            destination_branch_id = movement_data.get("destination_branch_id")
            if not destination_branch_id:
                raise ValueError("La transferencia requiere sucursal destino")
            if movement_data.get("branch_id") == destination_branch_id:
                raise ValueError("La sucursal origen y destino no pueden ser la misma")
            if not self._active_branch_exists(destination_branch_id):
                raise ValueError("La sucursal destino no existe o esta inactiva")
        elif movement_data.get("destination_branch_id"):
            raise ValueError("Solo las transferencias pueden tener sucursal destino")

    def _active_product_exists(self, product_id: int) -> bool:
        from models.product import Product

        return self.db.query(Product.id).filter(
            Product.id == product_id,
            Product.is_active == True
        ).first() is not None

    def _active_branch_exists(self, branch_id: int) -> bool:
        from models.branch import Branch

        return self.db.query(Branch.id).filter(
            Branch.id == branch_id,
            Branch.is_active == True
        ).first() is not None

    def _active_user_exists(self, user_id: int) -> bool:
        from models.user import User

        return self.db.query(User.id).filter(
            User.id == user_id,
            User.is_active == True
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

    def execute_direct_transfer(self, transfer_data: dict) -> Dict[str, Any]:
        """
        Execute a direct transfer between branches without approval flow.
        This method:
        1. Creates the movement record
        2. Validates stock availability
        3. Immediately deducts stock from origin
        4. Immediately adds stock to destination
        5. Emits appropriate events for real-time sync
        """
        transfer_data = self._sanitize_movement_data(transfer_data)
        
        # Ensure it's a transfer
        if transfer_data.get("movement_type") != "transferencia":
            raise ValueError("Este metodo es solo para transferencias")
        
        # Validate transfer data
        self._validate_movement_data(transfer_data)
        
        # Check stock availability before proceeding
        from models.inventory import Inventory
        inventory = self.db.query(Inventory).filter(
            Inventory.product_id == transfer_data["product_id"],
            Inventory.branch_id == transfer_data["branch_id"],
            Inventory.is_active == True
        ).first()
        
        if not inventory or inventory.digital_stock < transfer_data["quantity"]:
            raise ValueError("Stock digital insuficiente en la sucursal origen")
        
        # Create movement with validated state
        transfer_data["state"] = "validado"
        movement = self.repository.create(transfer_data)
        
        # Update inventory directly (bypass validation flow)
        from modules.inventory.service import InventoryService
        inventory_service = InventoryService(self.db)
        
        # Deduct from origin
        inventory_service.adjust_digital_stock(
            transfer_data["product_id"],
            transfer_data["branch_id"],
            -transfer_data["quantity"],
            is_absolute=False
        )
        
        # Add to destination
        inventory_service.adjust_digital_stock(
            transfer_data["product_id"],
            transfer_data["destination_branch_id"],
            transfer_data["quantity"],
            is_absolute=False
        )
        
        # Emit events for real-time sync
        event_data = {
            "movement_id": movement.id,
            "product_id": movement.product_id,
            "branch_id": movement.branch_id,
            "destination_branch_id": movement.destination_branch_id,
            "movement_type": movement.movement_type,
            "quantity": movement.quantity,
            "user_id": movement.user_id
        }
        
        # Emit movement validated event
        event_bus.emit(settings.Events.MOVEMENT_VALIDATED, event_data)
        
        # Emit transfer sent event
        transfer_data_event = {
            "movement_id": movement.id,
            "product_id": movement.product_id,
            "origin_branch_id": movement.branch_id,
            "destination_branch_id": movement.destination_branch_id,
            "quantity": movement.quantity
        }
        event_bus.emit(settings.Events.TRANSFER_SENT, transfer_data_event)
        
        # Emit transfer received event (since it's direct)
        event_bus.emit(settings.Events.TRANSFER_RECEIVED, transfer_data_event)
        
        logger.info(f"Direct transfer executed: Product {movement.product_id}, "
                   f"From {movement.branch_id} to {movement.destination_branch_id}, "
                   f"Quantity {movement.quantity}")
        
        return movement.to_dict()
