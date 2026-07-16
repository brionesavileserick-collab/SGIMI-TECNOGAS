"""
Movement repository for database operations.

Expansiones incluidas:
  Exp 1 - cancel(), get_active_movements()
  Exp 2 - confirm_reception(), get_pending_receptions()
  Exp 3 - filtro por priority en get_all/count, get_by_priority()
  Exp 4 - filtro por source en get_all/count, get_by_source()
  Exp 5 - filtros por reference_number/type, get_by_reference(), get_by_reference_type()
  Exp 6 - get_total_cost_by_branch()
  Exp 7 - MovementStateHistory CRUD: log_state_change(), get_state_history()
  Exp 8 - confirm_reception_with_signature(), get_pending_signature()
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func as sql_func
from models.movement import Movement, MovementState
from models.movement_state_history import MovementStateHistory
from datetime import datetime, timedelta


class MovementRepository:
    """Repository for movement database operations."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Core CRUD
    # ------------------------------------------------------------------

    def create(self, movement_data: dict) -> Movement:
        """Create a new movement."""
        movement = Movement(**movement_data)
        self.db.add(movement)
        self.db.commit()
        self.db.refresh(movement)
        return movement

    def get_by_id(self, movement_id: int) -> Optional[Movement]:
        """Get movement by ID."""
        return self.db.query(Movement).filter(Movement.id == movement_id).first()

    def get_by_id_for_update(self, movement_id: int) -> Optional[Movement]:
        """Get movement by ID with row lock (SELECT FOR UPDATE)."""
        return self.db.query(Movement).filter(
            Movement.id == movement_id
        ).with_for_update().first()

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
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
        # Exp 1 – excluir cancelados por defecto
        include_cancelled: bool = True,
    ) -> List[Movement]:
        """Get all movements with filtering."""
        query = self.db.query(Movement)

        if branch_id:
            query = query.filter(
                or_(
                    Movement.branch_id == branch_id,
                    Movement.destination_branch_id == branch_id,
                )
            )
        if product_id:
            query = query.filter(Movement.product_id == product_id)
        if user_id:
            query = query.filter(Movement.user_id == user_id)
        if movement_type:
            query = query.filter(Movement.movement_type == movement_type)
        if date_from:
            query = query.filter(Movement.created_at >= date_from)
        if date_to:
            query = query.filter(Movement.created_at <= date_to)
        # Exp 3
        if priority:
            query = query.filter(Movement.priority == priority)
        # Exp 4
        if source:
            query = query.filter(Movement.source == source)
        # Exp 5
        if reference_type:
            query = query.filter(Movement.reference_type == reference_type)
        # Exp 9 – filter by approval_level if provided via state alias
        if state:
            if state in ("pending_admin", "pending_manager", "approved", "rejected"):
                query = query.filter(Movement.approval_level == state)
            else:
                query = query.filter(Movement.state == state)
        if not include_cancelled:
            query = query.filter(Movement.is_cancelled == False)

        return query.order_by(Movement.created_at.desc()).offset(skip).limit(limit).all()

    def count(
        self,
        branch_id: int = None,
        product_id: int = None,
        user_id: int = None,
        movement_type: str = None,
        state: str = None,
        date_from: datetime = None,
        date_to: datetime = None,
        priority: str = None,
        source: str = None,
        reference_type: str = None,
        include_cancelled: bool = True,
    ) -> int:
        """Count movements with filtering."""
        query = self.db.query(Movement)

        if branch_id:
            query = query.filter(
                or_(
                    Movement.branch_id == branch_id,
                    Movement.destination_branch_id == branch_id,
                )
            )
        if product_id:
            query = query.filter(Movement.product_id == product_id)
        if user_id:
            query = query.filter(Movement.user_id == user_id)
        if movement_type:
            query = query.filter(Movement.movement_type == movement_type)
        if state:
            if state in ("pending_admin", "pending_manager", "approved", "rejected"):
                query = query.filter(Movement.approval_level == state)
            else:
                query = query.filter(Movement.state == state)
        if date_from:
            query = query.filter(Movement.created_at >= date_from)
        if date_to:
            query = query.filter(Movement.created_at <= date_to)
        if priority:
            query = query.filter(Movement.priority == priority)
        if source:
            query = query.filter(Movement.source == source)
        if reference_type:
            query = query.filter(Movement.reference_type == reference_type)
        if not include_cancelled:
            query = query.filter(Movement.is_cancelled == False)

        return query.count()

    def update(self, movement_id: int, update_data: dict) -> Optional[Movement]:
        """Generic field update."""
        movement = self.get_by_id(movement_id)
        if not movement:
            return None
        for key, value in update_data.items():
            if hasattr(movement, key):
                setattr(movement, key, value)
        self.db.commit()
        self.db.refresh(movement)
        return movement

    def validate(self, movement_id: int, validator_id: int) -> Optional[Movement]:
        """Mark movement as validated."""
        movement = self.get_by_id(movement_id)
        if not movement:
            return None
        movement.state = MovementState.VALIDADO.value
        movement.validated_at = datetime.utcnow()
        movement.validated_by = validator_id
        self.db.commit()
        self.db.refresh(movement)
        return movement

    def reject(self, movement_id: int, validator_id: int, reason: str = None) -> Optional[Movement]:
        """Mark movement as rejected."""
        movement = self.get_by_id(movement_id)
        if not movement:
            return None
        movement.state = MovementState.RECHAZADO.value
        movement.validated_at = datetime.utcnow()
        movement.validated_by = validator_id
        movement.reason = reason
        if reason:
            movement.notes = f"{movement.notes or ''}\nRechazado: {reason}".strip()
        self.db.commit()
        self.db.refresh(movement)
        return movement

    def delete(self, movement_id: int) -> bool:
        """Delete movement (only if pending and not cancelled)."""
        movement = self.get_by_id(movement_id)
        if not movement or movement.state != MovementState.PENDIENTE.value:
            return False
        self.db.delete(movement)
        self.db.commit()
        return True

    def get_pending_count(self, branch_id: int = None) -> int:
        """Count pending (non-cancelled) movements."""
        query = self.db.query(Movement).filter(
            Movement.state == MovementState.PENDIENTE.value,
            Movement.is_cancelled == False,
        )
        if branch_id:
            query = query.filter(
                or_(
                    Movement.branch_id == branch_id,
                    Movement.destination_branch_id == branch_id,
                )
            )
        return query.count()

    def get_pending_admin_approval(self, branch_id: int = None) -> List[Movement]:
        """Get movements pending admin approval."""
        query = self.db.query(Movement).filter(
            Movement.requires_approval == True,
            Movement.approval_level == "pending_admin",
            Movement.is_cancelled == False,
        )
        if branch_id:
            query = query.filter(
                or_(
                    Movement.branch_id == branch_id,
                    Movement.destination_branch_id == branch_id,
                )
            )
        return query.order_by(Movement.created_at.desc()).all()

    def get_pending_manager_approval(self, branch_id: int) -> List[Movement]:
        """Get movements pending manager approval for a branch."""
        query = self.db.query(Movement).filter(
            Movement.requires_approval == True,
            Movement.approval_level == "pending_manager",
            Movement.destination_branch_id == branch_id,
            Movement.is_cancelled == False,
        )
        return query.order_by(Movement.created_at.desc()).all()

    def approve_by_admin(self, movement_id: int, admin_name: str) -> Optional[Movement]:
        """Approve a movement at admin level."""
        movement = self.get_by_id(movement_id)
        if not movement:
            return None
        movement.admin_approved = True
        movement.admin_approved_at = datetime.utcnow()
        movement.admin_approved_by = admin_name
        movement.approval_level = "pending_manager" if movement.requires_approval else "approved"
        self.db.commit()
        self.db.refresh(movement)
        return movement

    def approve_by_manager(self, movement_id: int, manager_name: str) -> Optional[Movement]:
        """Approve a movement at manager level."""
        movement = self.get_by_id(movement_id)
        if not movement:
            return None
        movement.manager_approved = True
        movement.manager_approved_at = datetime.utcnow()
        movement.manager_approved_by = manager_name
        movement.approval_level = "approved"
        self.db.commit()
        self.db.refresh(movement)
        return movement

    def reject_by_admin(self, movement_id: int, admin_name: str, reason: str) -> Optional[Movement]:
        """Reject a movement at admin level."""
        movement = self.get_by_id(movement_id)
        if not movement:
            return None
        movement.admin_approved = False
        movement.admin_approved_at = datetime.utcnow()
        movement.admin_approved_by = admin_name
        movement.state = MovementState.RECHAZADO.value
        movement.approval_level = "rejected"
        movement.reason = reason
        if reason:
            movement.notes = f"{movement.notes or ''}\nRechazado por admin: {reason}".strip()
        self.db.commit()
        self.db.refresh(movement)
        return movement

    def reject_by_manager(self, movement_id: int, manager_name: str, reason: str) -> Optional[Movement]:
        """Reject a movement at manager level."""
        movement = self.get_by_id(movement_id)
        if not movement:
            return None
        movement.manager_approved = False
        movement.manager_approved_at = datetime.utcnow()
        movement.manager_approved_by = manager_name
        movement.state = MovementState.RECHAZADO.value
        movement.approval_level = "rejected"
        movement.reason = reason
        if reason:
            movement.notes = f"{movement.notes or ''}\nRechazado por gerente: {reason}".strip()
        self.db.commit()
        self.db.refresh(movement)
        return movement

    def get_movements_pending_my_approval(self, approver_type: str, branch_id: int = None) -> List[Movement]:
        """Get pending approvals for admin or manager."""
        if approver_type == "admin":
            return self.get_pending_admin_approval(branch_id)
        if approver_type == "manager" and branch_id is not None:
            return self.get_pending_manager_approval(branch_id)
        return []

    def get_scheduled_movements(self, branch_id: int = None) -> List[Movement]:
        """Get scheduled movements."""
        query = self.db.query(Movement).filter(
            Movement.is_scheduled == True,
            Movement.is_cancelled == False,
        )
        if branch_id:
            query = query.filter(
                or_(
                    Movement.branch_id == branch_id,
                    Movement.destination_branch_id == branch_id,
                )
            )
        return query.order_by(Movement.scheduled_date.asc()).all()

    def get_movements_due_today(self) -> List[Movement]:
        """Get scheduled movements due today."""
        today = datetime.utcnow().date()
        return (
            self.db.query(Movement)
            .filter(
                Movement.is_scheduled == True,
                Movement.scheduled_date >= datetime(today.year, today.month, today.day),
                Movement.scheduled_date < datetime(today.year, today.month, today.day, 23, 59, 59),
                Movement.is_cancelled == False,
            )
            .order_by(Movement.scheduled_date.asc())
            .all()
        )

    def execute_scheduled_movement(self, movement_id: int) -> Optional[Movement]:
        """Execute a scheduled movement by marking it pending or approved as required."""
        movement = self.get_by_id(movement_id)
        if not movement:
            return None
        movement.is_scheduled = False
        movement.scheduled_date = None
        if movement.requires_approval:
            if movement.approval_level == "approved":
                movement.state = MovementState.VALIDADO.value
                movement.sent_at = movement.sent_at or datetime.utcnow()
                if movement.estimated_transit_days is not None:
                    movement.expected_arrival = movement.sent_at + timedelta(days=movement.estimated_transit_days)
            else:
                movement.state = MovementState.PENDIENTE.value
        else:
            movement.state = MovementState.PENDIENTE.value
        self.db.commit()
        self.db.refresh(movement)
        return movement

    def get_delayed_transfers(self) -> List[Movement]:
        """Get transfers with expected arrival passed."""
        now = datetime.utcnow()
        return (
            self.db.query(Movement)
            .filter(
                Movement.movement_type == "transferencia",
                Movement.expected_arrival.isnot(None),
                Movement.expected_arrival < now,
                Movement.state == MovementState.VALIDADO.value,
                Movement.is_cancelled == False,
            )
            .all()
        )

    def get_average_transit_time(self, origin_branch_id: int, dest_branch_id: int) -> Optional[float]:
        """Calculate average actual transit days for transfers between two branches."""
        query = self.db.query(
            sql_func.avg(Movement.actual_transit_days)
        ).filter(
            Movement.movement_type == "transferencia",
            Movement.branch_id == origin_branch_id,
            Movement.destination_branch_id == dest_branch_id,
            Movement.actual_transit_days.isnot(None),
            Movement.is_cancelled == False,
        )
        result = query.first()
        return float(result[0]) if result and result[0] is not None else None

    def get_movement_with_details(self, movement_id: int) -> Optional[dict]:
        """Get movement with related entity details."""
        from models.product import Product
        from models.branch import Branch
        from models.user import User

        movement = self.db.query(Movement).filter(Movement.id == movement_id).first()
        if not movement:
            return None

        product = self.db.query(Product).filter(Product.id == movement.product_id).first()
        branch = self.db.query(Branch).filter(Branch.id == movement.branch_id).first()
        user = (
            self.db.query(User).filter(User.id == movement.user_id).first()
            if movement.user_id
            else None
        )
        dest_branch = (
            self.db.query(Branch).filter(Branch.id == movement.destination_branch_id).first()
            if movement.destination_branch_id
            else None
        )

        return {
            "movement": movement.to_dict(),
            "product": product.to_dict() if product else None,
            "branch": branch.to_dict() if branch else None,
            "user": user.to_dict() if user else None,
            "destination_branch": dest_branch.to_dict() if dest_branch else None,
        }

    def get_stats_by_type(self, branch_id: int = None, date_from: datetime = None) -> dict:
        """Get movement statistics by type (only validated, non-cancelled)."""
        query = self.db.query(
            Movement.movement_type,
            sql_func.count(Movement.id).label("count"),
            sql_func.sum(Movement.quantity).label("total_quantity"),
        ).filter(
            Movement.state == MovementState.VALIDADO.value,
            Movement.is_cancelled == False,
        )
        if branch_id:
            query = query.filter(Movement.branch_id == branch_id)
        if date_from:
            query = query.filter(Movement.created_at >= date_from)
        query = query.group_by(Movement.movement_type)

        results = {}
        for row in query.all():
            results[row.movement_type] = {
                "count": row.count,
                "total_quantity": row.total_quantity or 0,
            }
        return results

    # ------------------------------------------------------------------
    # Expansión 1 – Cancelación
    # ------------------------------------------------------------------

    def cancel(self, movement_id: int, user_id: int, reason: str = None) -> Optional[Movement]:
        """Mark movement as cancelled."""
        movement = self.get_by_id(movement_id)
        if not movement:
            return None
        movement.is_cancelled = True
        movement.cancelled_at = datetime.utcnow()
        movement.cancelled_by = user_id
        movement.cancellation_reason = reason
        self.db.commit()
        self.db.refresh(movement)
        return movement

    def get_active_movements(
        self,
        branch_id: int = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Movement]:
        """Return only non-cancelled movements."""
        return self.get_all(
            skip=skip,
            limit=limit,
            branch_id=branch_id,
            include_cancelled=False,
        )

    # ------------------------------------------------------------------
    # Expansión 2 – Confirmación de recepción en transferencias
    # ------------------------------------------------------------------

    def confirm_reception(
        self,
        movement_id: int,
        user_id: int,
        notes: str = None,
    ) -> Optional[Movement]:
        """Mark transfer as received by destination branch."""
        movement = self.get_by_id(movement_id)
        if not movement:
            return None
        movement.is_received = True
        movement.received_at = datetime.utcnow()
        movement.received_by = user_id
        movement.received_notes = notes
        self.db.commit()
        self.db.refresh(movement)
        return movement

    def get_pending_receptions(self, branch_id: int) -> List[Movement]:
        """Get validated transfers pending reception at given destination branch."""
        return (
            self.db.query(Movement)
            .filter(
                Movement.movement_type == "transferencia",
                Movement.state == MovementState.VALIDADO.value,
                Movement.is_received == False,
                Movement.is_cancelled == False,
                Movement.destination_branch_id == branch_id,
            )
            .order_by(Movement.validated_at.desc())
            .all()
        )

    # ------------------------------------------------------------------
    # Expansión 3 – Prioridad
    # ------------------------------------------------------------------

    def get_by_priority(self, priority: str, branch_id: int = None) -> List[Movement]:
        """Get movements filtered by priority."""
        return self.get_all(branch_id=branch_id, priority=priority, include_cancelled=False)

    def set_priority(self, movement_id: int, priority: str) -> Optional[Movement]:
        """Update the priority of a movement."""
        return self.update(movement_id, {"priority": priority})

    # ------------------------------------------------------------------
    # Expansión 4 – Origen
    # ------------------------------------------------------------------

    def get_by_source(self, source: str, branch_id: int = None) -> List[Movement]:
        """Get movements filtered by source."""
        return self.get_all(branch_id=branch_id, source=source)

    # ------------------------------------------------------------------
    # Expansión 5 – Documento de referencia
    # ------------------------------------------------------------------

    def get_by_reference(self, reference_number: str) -> List[Movement]:
        """Search movements by reference number (partial match)."""
        return (
            self.db.query(Movement)
            .filter(Movement.reference_number.ilike(f"%{reference_number}%"))
            .order_by(Movement.created_at.desc())
            .all()
        )

    def get_by_reference_type(self, reference_type: str, branch_id: int = None) -> List[Movement]:
        """Get movements filtered by reference type."""
        return self.get_all(branch_id=branch_id, reference_type=reference_type)

    # ------------------------------------------------------------------
    # Expansión 6 – Costo
    # ------------------------------------------------------------------

    def get_total_cost_by_branch(
        self,
        branch_id: int,
        date_from: datetime = None,
        date_to: datetime = None,
    ) -> dict:
        """
        Return cost summary per movement_type for a given branch.
        Only considers validated, non-cancelled movements that have cost data.
        """
        query = self.db.query(
            Movement.movement_type,
            sql_func.count(Movement.id).label("count"),
            sql_func.sum(Movement.total_cost).label("total_cost"),
            sql_func.sum(Movement.quantity).label("total_quantity"),
        ).filter(
            Movement.branch_id == branch_id,
            Movement.state == MovementState.VALIDADO.value,
            Movement.is_cancelled == False,
            Movement.total_cost.isnot(None),
        )

        if date_from:
            query = query.filter(Movement.created_at >= date_from)
        if date_to:
            query = query.filter(Movement.created_at <= date_to)

        query = query.group_by(Movement.movement_type)

        results = {}
        for row in query.all():
            results[row.movement_type] = {
                "count": row.count,
                "total_cost": float(row.total_cost or 0),
                "total_quantity": row.total_quantity or 0,
            }
        return results

    # ------------------------------------------------------------------
    # Expansión 7 – Historial de cambios de estado
    # ------------------------------------------------------------------

    def log_state_change(
        self,
        movement_id: int,
        new_state: str,
        previous_state: str = None,
        changed_by: int = None,
        change_reason: str = None,
    ) -> MovementStateHistory:
        """Persist a state-change record for a movement."""
        entry = MovementStateHistory(
            movement_id=movement_id,
            previous_state=previous_state,
            new_state=new_state,
            changed_by=changed_by,
            change_reason=change_reason,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def get_state_history(self, movement_id: int) -> List[MovementStateHistory]:
        """Return the full state-change history for a movement."""
        return (
            self.db.query(MovementStateHistory)
            .filter(MovementStateHistory.movement_id == movement_id)
            .order_by(MovementStateHistory.created_at.asc())
            .all()
        )

    # ------------------------------------------------------------------
    # Expansión 8 – Confirmación física / firma
    # ------------------------------------------------------------------

    def confirm_physical_reception(
        self,
        movement_id: int,
        receiver_name: str,
        signature: str = None,
    ) -> Optional[Movement]:
        """Register who physically received the goods."""
        return self.update(
            movement_id,
            {"receiver_name": receiver_name, "receiver_signature": signature},
        )

    def get_pending_signature(self, branch_id: int = None) -> List[Movement]:
        """Return validated movements without a recorded physical receiver."""
        query = self.db.query(Movement).filter(
            Movement.state == MovementState.VALIDADO.value,
            Movement.is_cancelled == False,
            Movement.receiver_name.is_(None),
        )
        if branch_id:
            query = query.filter(
                or_(
                    Movement.branch_id == branch_id,
                    Movement.destination_branch_id == branch_id,
                )
            )
        return query.order_by(Movement.validated_at.desc()).all()
