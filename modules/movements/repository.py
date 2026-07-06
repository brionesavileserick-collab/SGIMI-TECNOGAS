"""
Movement repository for database operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from sqlalchemy.sql import func as sql_func
from models.movement import Movement, MovementType, MovementState
from datetime import datetime


class MovementRepository:
    """Repository for movement database operations."""

    def __init__(self, db: Session):
        self.db = db

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

    def get_all(self, skip: int = 0, limit: int = 100,
                branch_id: int = None, product_id: int = None,
                user_id: int = None, movement_type: str = None,
                state: str = None, date_from: datetime = None,
                date_to: datetime = None) -> List[Movement]:
        """Get all movements with filtering."""
        query = self.db.query(Movement)

        if branch_id:
            query = query.filter(
                or_(
                    Movement.branch_id == branch_id,
                    Movement.destination_branch_id == branch_id
                )
            )

        if product_id:
            query = query.filter(Movement.product_id == product_id)

        if user_id:
            query = query.filter(Movement.user_id == user_id)

        if movement_type:
            query = query.filter(Movement.movement_type == movement_type)

        if state:
            query = query.filter(Movement.state == state)

        if date_from:
            query = query.filter(Movement.created_at >= date_from)

        if date_to:
            query = query.filter(Movement.created_at <= date_to)

        return query.order_by(Movement.created_at.desc()).offset(skip).limit(limit).all()

    def count(self, branch_id: int = None, product_id: int = None,
              user_id: int = None, movement_type: str = None,
              state: str = None, date_from: datetime = None,
              date_to: datetime = None) -> int:
        """Count movements with filtering."""
        query = self.db.query(Movement)

        if branch_id:
            query = query.filter(
                or_(
                    Movement.branch_id == branch_id,
                    Movement.destination_branch_id == branch_id
                )
            )

        if product_id:
            query = query.filter(Movement.product_id == product_id)

        if user_id:
            query = query.filter(Movement.user_id == user_id)

        if movement_type:
            query = query.filter(Movement.movement_type == movement_type)

        if state:
            query = query.filter(Movement.state == state)

        if date_from:
            query = query.filter(Movement.created_at >= date_from)

        if date_to:
            query = query.filter(Movement.created_at <= date_to)

        return query.count()

    def update(self, movement_id: int, update_data: dict) -> Optional[Movement]:
        """Update movement."""
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
        """Validate a movement."""
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
        """Reject a movement."""
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
        """Delete movement (only if pending)."""
        movement = self.get_by_id(movement_id)
        if not movement or movement.state != MovementState.PENDIENTE.value:
            return False

        self.db.delete(movement)
        self.db.commit()
        return True

    def get_pending_count(self, branch_id: int = None) -> int:
        """Count pending movements."""
        query = self.db.query(Movement).filter(
            Movement.state == MovementState.PENDIENTE.value
        )

        if branch_id:
            query = query.filter(
                or_(
                    Movement.branch_id == branch_id,
                    Movement.destination_branch_id == branch_id
                )
            )

        return query.count()

    def get_movement_with_details(self, movement_id: int) -> Optional[dict]:
        """Get movement with related entity details."""
        from models.product import Product
        from models.branch import Branch
        from models.user import User

        # Get movement first
        movement = self.db.query(Movement).filter(Movement.id == movement_id).first()
        if not movement:
            return None

        # Get related entities
        product = self.db.query(Product).filter(Product.id == movement.product_id).first()
        branch = self.db.query(Branch).filter(Branch.id == movement.branch_id).first()
        user = self.db.query(User).filter(User.id == movement.user_id).first() if movement.user_id else None
        dest_branch = self.db.query(Branch).filter(Branch.id == movement.destination_branch_id).first() if movement.destination_branch_id else None

        return {
            "movement": movement.to_dict(),
            "product": product.to_dict() if product else None,
            "branch": branch.to_dict() if branch else None,
            "user": user.to_dict() if user else None,
            "destination_branch": dest_branch.to_dict() if dest_branch else None
        }

    def get_stats_by_type(self, branch_id: int = None, date_from: datetime = None) -> dict:
        """Get movement statistics by type."""
        query = self.db.query(
            Movement.movement_type,
            sql_func.count(Movement.id).label('count'),
            sql_func.sum(Movement.quantity).label('total_quantity')
        ).filter(Movement.state == MovementState.VALIDADO.value)

        if branch_id:
            query = query.filter(Movement.branch_id == branch_id)

        if date_from:
            query = query.filter(Movement.created_at >= date_from)

        query = query.group_by(Movement.movement_type)

        results = {}
        for row in query.all():
            results[row.movement_type] = {
                "count": row.count,
                "total_quantity": row.total_quantity or 0
            }

        return results
