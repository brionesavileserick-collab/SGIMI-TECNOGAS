"""
Branch repository for database operations.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from models.branch import Branch
from models.inventory import Inventory
from models.movement import Movement
from models.user import User


class BranchRepository:
    """Repository for branch database operations."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # CRUD base (sin cambios funcionales)
    # ------------------------------------------------------------------

    def create(self, branch_data: dict) -> Branch:
        """Create a new branch."""
        branch = Branch(**branch_data)
        self.db.add(branch)
        self.db.commit()
        self.db.refresh(branch)
        return branch

    def get_by_id(self, branch_id: int) -> Optional[Branch]:
        """Get branch by ID."""
        return self.db.query(Branch).filter(Branch.id == branch_id).first()

    def get_by_name(self, name: str) -> Optional[Branch]:
        """Get branch by name."""
        return self.db.query(Branch).filter(Branch.name == name).first()

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        search: str = None,
        active_only: bool = True,
    ) -> List[Branch]:
        """Get all branches with optional filtering."""
        query = self.db.query(Branch)

        if active_only:
            query = query.filter(Branch.is_active == True)

        if search:
            query = query.filter(
                or_(
                    Branch.name.ilike(f"%{search}%"),
                    Branch.address.ilike(f"%{search}%"),
                )
            )

        return query.offset(skip).limit(limit).all()

    def count(self, active_only: bool = True, search: str = None) -> int:
        """Count branches with optional filtering."""
        query = self.db.query(Branch)

        if active_only:
            query = query.filter(Branch.is_active == True)

        if search:
            query = query.filter(
                or_(
                    Branch.name.ilike(f"%{search}%"),
                    Branch.address.ilike(f"%{search}%"),
                )
            )

        return query.count()

    def update(self, branch_id: int, update_data: dict) -> Optional[Branch]:
        """Update branch."""
        branch = self.get_by_id(branch_id)
        if not branch:
            return None

        for key, value in update_data.items():
            if hasattr(branch, key):
                setattr(branch, key, value)

        self.db.commit()
        self.db.refresh(branch)
        return branch

    def delete(self, branch_id: int) -> bool:
        """Soft delete branch by setting is_active to False."""
        branch = self.get_by_id(branch_id)
        if not branch:
            return False

        branch.is_active = False
        self.db.commit()
        return True

    def hard_delete(self, branch_id: int) -> bool:
        """Permanently delete branch."""
        branch = self.get_by_id(branch_id)
        if not branch:
            return False

        self.db.delete(branch)
        self.db.commit()
        return True

    def name_exists(self, name: str, exclude_id: int = None) -> bool:
        """Check if name already exists."""
        query = self.db.query(Branch).filter(func.lower(Branch.name) == name.lower())
        if exclude_id:
            query = query.filter(Branch.id != exclude_id)
        return query.first() is not None

    # ------------------------------------------------------------------
    # Expansión 1 – Filtros geográficos
    # ------------------------------------------------------------------

    def get_by_zone(self, zone: str, active_only: bool = True) -> List[Branch]:
        """Get all branches in a given zone."""
        query = self.db.query(Branch).filter(
            func.lower(Branch.zone) == zone.lower()
        )
        if active_only:
            query = query.filter(Branch.is_active == True)
        return query.all()

    def get_by_city(self, city: str, active_only: bool = True) -> List[Branch]:
        """Get all branches in a given city."""
        query = self.db.query(Branch).filter(
            func.lower(Branch.city) == city.lower()
        )
        if active_only:
            query = query.filter(Branch.is_active == True)
        return query.all()

    def get_by_state(self, state: str, active_only: bool = True) -> List[Branch]:
        """Get all branches in a given state/province."""
        query = self.db.query(Branch).filter(
            func.lower(Branch.state) == state.lower()
        )
        if active_only:
            query = query.filter(Branch.is_active == True)
        return query.all()

    def get_distinct_zones(self, active_only: bool = True) -> List[str]:
        """Return sorted list of distinct non-null zones."""
        query = self.db.query(Branch.zone).filter(Branch.zone.isnot(None))
        if active_only:
            query = query.filter(Branch.is_active == True)
        rows = query.distinct().order_by(Branch.zone).all()
        return [r[0] for r in rows]

    # ------------------------------------------------------------------
    # Expansión 2 – Configuración de inventario personalizada
    # ------------------------------------------------------------------

    def get_branches_with_custom_stock_config(self, active_only: bool = True) -> List[Branch]:
        """Return branches that have at least one custom stock threshold set."""
        query = self.db.query(Branch).filter(
            or_(
                Branch.default_min_stock.isnot(None),
                Branch.default_max_stock.isnot(None),
            )
        )
        if active_only:
            query = query.filter(Branch.is_active == True)
        return query.all()

    # ------------------------------------------------------------------
    # Expansión 3 – Filtro por estado operativo
    # ------------------------------------------------------------------

    def get_by_operational_status(
        self, status: str, active_only: bool = True
    ) -> List[Branch]:
        """Get branches filtered by operational_status."""
        query = self.db.query(Branch).filter(
            Branch.operational_status == status
        )
        if active_only:
            query = query.filter(Branch.is_active == True)
        return query.all()

    def get_distinct_operational_statuses(self) -> List[str]:
        """Return sorted list of operational status values in use."""
        rows = (
            self.db.query(Branch.operational_status)
            .filter(Branch.operational_status.isnot(None))
            .distinct()
            .order_by(Branch.operational_status)
            .all()
        )
        return [r[0] for r in rows]

    # ------------------------------------------------------------------
    # Expansión 4 – Responsable de sucursal
    # ------------------------------------------------------------------

    def get_branch_manager(self, branch_id: int) -> Optional[User]:
        """Return the User assigned as manager for the given branch, or None."""
        branch = self.get_by_id(branch_id)
        if not branch or not branch.manager_user_id:
            return None
        return self.db.query(User).filter(User.id == branch.manager_user_id).first()

    def get_branches_by_manager(self, user_id: int, active_only: bool = True) -> List[Branch]:
        """Return all branches managed by a specific user."""
        query = self.db.query(Branch).filter(Branch.manager_user_id == user_id)
        if active_only:
            query = query.filter(Branch.is_active == True)
        return query.all()

    # ------------------------------------------------------------------
    # Expansión 5 – Frecuencia de conteo
    # ------------------------------------------------------------------

    def get_by_count_frequency(
        self, frequency: str, active_only: bool = True
    ) -> List[Branch]:
        """Get branches filtered by count_frequency."""
        query = self.db.query(Branch).filter(Branch.count_frequency == frequency)
        if active_only:
            query = query.filter(Branch.is_active == True)
        return query.all()

    def get_branches_with_count_frequency(self, active_only: bool = True) -> List[Branch]:
        """Return branches that have a count_frequency set."""
        query = self.db.query(Branch).filter(Branch.count_frequency.isnot(None))
        if active_only:
            query = query.filter(Branch.is_active == True)
        return query.order_by(Branch.count_frequency, Branch.name).all()

    # ------------------------------------------------------------------
    # Expansión 6 – Capacidad
    # ------------------------------------------------------------------

    def get_by_storage_capacity(
        self, capacity: str, active_only: bool = True
    ) -> List[Branch]:
        """Get branches by storage_capacity label (e.g. 'grande')."""
        query = self.db.query(Branch).filter(
            func.lower(Branch.storage_capacity) == capacity.lower()
        )
        if active_only:
            query = query.filter(Branch.is_active == True)
        return query.all()

    def get_all_ordered_by_max_products(self, active_only: bool = True) -> List[Branch]:
        """Return branches ordered descending by max_products (nulls last)."""
        query = self.db.query(Branch)
        if active_only:
            query = query.filter(Branch.is_active == True)
        # Branches without max_products go to the end
        return query.order_by(Branch.max_products.desc().nullslast(), Branch.name).all()

    def get_sku_count_for_branch(self, branch_id: int) -> int:
        """Count distinct active SKUs currently tracked for a branch."""
        return (
            self.db.query(func.count(Inventory.id))
            .filter(
                Inventory.branch_id == branch_id,
                Inventory.is_active == True,
            )
            .scalar()
            or 0
        )

    # ------------------------------------------------------------------
    # Expansión 7 – Agregaciones SQL para métricas
    # ------------------------------------------------------------------

    def get_inventory_totals_for_branch(self, branch_id: int) -> Dict[str, Any]:
        """
        Return aggregated inventory totals for a single branch using SQL.
        Avoids Python-level iteration when only totals are needed.
        """
        row = (
            self.db.query(
                func.count(Inventory.id).label("total_skus"),
                func.coalesce(func.sum(Inventory.physical_stock), 0).label("total_physical"),
                func.coalesce(func.sum(Inventory.digital_stock), 0).label("total_digital"),
            )
            .filter(
                Inventory.branch_id == branch_id,
                Inventory.is_active == True,
            )
            .one()
        )
        return {
            "total_skus": row.total_skus,
            "total_physical_stock": row.total_physical,
            "total_digital_stock": row.total_digital,
        }

    def get_discrepancy_count_for_branch(self, branch_id: int) -> int:
        """Count inventory rows where physical_stock != digital_stock."""
        return (
            self.db.query(func.count(Inventory.id))
            .filter(
                Inventory.branch_id == branch_id,
                Inventory.is_active == True,
                Inventory.physical_stock != Inventory.digital_stock,
            )
            .scalar()
            or 0
        )

    def get_low_stock_count_for_branch(self, branch_id: int) -> int:
        """Count inventory rows where digital_stock <= min_stock."""
        return (
            self.db.query(func.count(Inventory.id))
            .filter(
                Inventory.branch_id == branch_id,
                Inventory.is_active == True,
                Inventory.digital_stock <= Inventory.min_stock,
            )
            .scalar()
            or 0
        )

    def get_movement_count_for_branch(
        self, branch_id: int, days: int = 30
    ) -> int:
        """Count movements originated from a branch in the last N days."""
        from datetime import datetime, timedelta

        since = datetime.utcnow() - timedelta(days=days)
        return (
            self.db.query(func.count(Movement.id))
            .filter(
                Movement.branch_id == branch_id,
                Movement.created_at >= since,
            )
            .scalar()
            or 0
        )

    def get_all_branches_inventory_summary(self) -> List[Dict[str, Any]]:
        """
        Single-query aggregation of inventory totals per branch.
        Returns a list of dicts: {branch_id, total_skus, total_physical,
        total_digital, discrepancy_count, low_stock_count}.
        """
        rows = (
            self.db.query(
                Inventory.branch_id,
                func.count(Inventory.id).label("total_skus"),
                func.coalesce(func.sum(Inventory.physical_stock), 0).label("total_physical"),
                func.coalesce(func.sum(Inventory.digital_stock), 0).label("total_digital"),
                func.sum(
                    func.cast(
                        Inventory.physical_stock != Inventory.digital_stock,
                        type_=func.count(Inventory.id).type,
                    )
                ).label("discrepancy_count"),
                func.sum(
                    func.cast(
                        Inventory.digital_stock <= Inventory.min_stock,
                        type_=func.count(Inventory.id).type,
                    )
                ).label("low_stock_count"),
            )
            .filter(Inventory.is_active == True)
            .group_by(Inventory.branch_id)
            .all()
        )
        return [
            {
                "branch_id": r.branch_id,
                "total_skus": r.total_skus,
                "total_physical_stock": int(r.total_physical),
                "total_digital_stock": int(r.total_digital),
                "discrepancy_count": int(r.discrepancy_count or 0),
                "low_stock_count": int(r.low_stock_count or 0),
            }
            for r in rows
        ]

    def get_movement_counts_per_branch(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Return movement counts grouped by branch for the last N days.
        Returns a list of dicts: {branch_id, movement_count}.
        """
        from datetime import datetime, timedelta

        since = datetime.utcnow() - timedelta(days=days)
        rows = (
            self.db.query(
                Movement.branch_id,
                func.count(Movement.id).label("movement_count"),
            )
            .filter(Movement.created_at >= since)
            .group_by(Movement.branch_id)
            .order_by(func.count(Movement.id).desc())
            .all()
        )
        return [{"branch_id": r.branch_id, "movement_count": r.movement_count} for r in rows]

    # ------------------------------------------------------------------
    # Expansión 7 – Programación de conteos
    # ------------------------------------------------------------------

    def get_branches_due_for_count(self, active_only: bool = True) -> List[Branch]:
        """Return branches whose next_scheduled_count is today or earlier."""
        from datetime import datetime

        now = datetime.utcnow()
        query = self.db.query(Branch).filter(
            Branch.count_enabled == True,
            Branch.next_scheduled_count.isnot(None),
            Branch.next_scheduled_count <= now,
        )
        if active_only:
            query = query.filter(Branch.is_active == True)
        return query.order_by(Branch.next_scheduled_count).all()

    def get_branches_with_overdue_counts(
        self, days: int = 7, active_only: bool = True
    ) -> List[Branch]:
        """Return branches whose next_scheduled_count is overdue by at least *days* days."""
        from datetime import datetime, timedelta

        cutoff = datetime.utcnow() - timedelta(days=days)
        query = self.db.query(Branch).filter(
            Branch.count_enabled == True,
            Branch.next_scheduled_count.isnot(None),
            Branch.next_scheduled_count <= cutoff,
        )
        if active_only:
            query = query.filter(Branch.is_active == True)
        return query.order_by(Branch.next_scheduled_count).all()

    def get_upcoming_counts(
        self, days: int = 30, active_only: bool = True
    ) -> List[Branch]:
        """Return branches with next_scheduled_count within the next *days* days."""
        from datetime import datetime, timedelta

        now = datetime.utcnow()
        future = now + timedelta(days=days)
        query = self.db.query(Branch).filter(
            Branch.count_enabled == True,
            Branch.next_scheduled_count.isnot(None),
            Branch.next_scheduled_count > now,
            Branch.next_scheduled_count <= future,
        )
        if active_only:
            query = query.filter(Branch.is_active == True)
        return query.order_by(Branch.next_scheduled_count).all()

    def update_next_scheduled_count(
        self, branch_id: int, next_date
    ) -> Optional[Branch]:
        """Persist the calculated next_scheduled_count for a branch."""
        branch = self.get_by_id(branch_id)
        if not branch:
            return None
        branch.next_scheduled_count = next_date
        self.db.commit()
        self.db.refresh(branch)
        return branch

    def update_last_count_date(self, branch_id: int, count_date) -> Optional[Branch]:
        """Record the date of the last completed inventory count."""
        branch = self.get_by_id(branch_id)
        if not branch:
            return None
        branch.last_count_date = count_date
        self.db.commit()
        self.db.refresh(branch)
        return branch

    # ------------------------------------------------------------------
    # Expansión 8 – Historial de configuración
    # ------------------------------------------------------------------

    def log_config_change(
        self,
        branch_id: int,
        field_name: str,
        old_value,
        new_value,
        changed_by: str = None,
        reason: str = None,
    ):
        """Append one row to branch_config_history."""
        from models.branch_config_history import BranchConfigHistory

        entry = BranchConfigHistory(
            branch_id=branch_id,
            changed_by=changed_by,
            field_name=field_name,
            old_value=str(old_value) if old_value is not None else None,
            new_value=str(new_value) if new_value is not None else None,
            reason=reason,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def get_branch_config_history(
        self, branch_id: int, limit: int = 100
    ) -> List[Any]:
        """Return the last *limit* config-change records for a branch, newest first."""
        from models.branch_config_history import BranchConfigHistory

        return (
            self.db.query(BranchConfigHistory)
            .filter(BranchConfigHistory.branch_id == branch_id)
            .order_by(BranchConfigHistory.changed_at.desc())
            .limit(limit)
            .all()
        )

    # ------------------------------------------------------------------
    # Expansión 9 – Validación de capacidad
    # ------------------------------------------------------------------

    def get_branch_capacity_usage(self, branch_id: int) -> Dict[str, Any]:
        """
        Return current capacity usage for a branch.
        Dict keys: current_count, max_products, usage_percent, is_near_capacity.
        is_near_capacity is True when usage >= 80 %.
        """
        branch = self.get_by_id(branch_id)
        if not branch:
            return {
                "current_count": 0,
                "max_products": None,
                "usage_percent": None,
                "is_near_capacity": False,
            }

        current_count = self.get_sku_count_for_branch(branch_id)
        max_products = branch.max_products

        if max_products:
            usage_percent = round((current_count / max_products) * 100, 1)
            is_near_capacity = usage_percent >= 80.0
        else:
            usage_percent = None
            is_near_capacity = False

        return {
            "current_count": current_count,
            "max_products": max_products,
            "usage_percent": usage_percent,
            "is_near_capacity": is_near_capacity,
        }

    # ------------------------------------------------------------------
    # Expansión 10 – Métricas comparativas
    # ------------------------------------------------------------------

    def get_branch_discrepancy_rate(
        self, branch_id: int, days: int = 30
    ) -> Dict[str, Any]:
        """
        Return the discrepancy rate for a branch as a percentage.
        discrepancy_rate = discrepancy_count / total_skus * 100 (0 when no SKUs).
        """
        total_skus = self.get_sku_count_for_branch(branch_id)
        discrepancy_count = self.get_discrepancy_count_for_branch(branch_id)
        rate = round((discrepancy_count / total_skus) * 100, 2) if total_skus else 0.0

        return {
            "branch_id": branch_id,
            "total_skus": total_skus,
            "discrepancy_count": discrepancy_count,
            "discrepancy_rate": rate,
        }

    def get_branch_movement_velocity(
        self, branch_id: int, days: int = 30
    ) -> Dict[str, Any]:
        """
        Return movement velocity (movements per day) for a branch.
        velocity = movement_count / days.
        """
        movement_count = self.get_movement_count_for_branch(branch_id, days=days)
        velocity = round(movement_count / days, 2) if days else 0.0

        return {
            "branch_id": branch_id,
            "period_days": days,
            "movement_count": movement_count,
            "velocity_per_day": velocity,
        }

    # ------------------------------------------------------------------
    # Expansión 11 – Estado de conectividad
    # ------------------------------------------------------------------

    def get_offline_branches(
        self, offline_threshold_minutes: int = 60, active_only: bool = True
    ) -> List[Branch]:
        """
        Return branches whose last_seen_at is older than *offline_threshold_minutes*
        minutes ago, or whose connection_status is 'offline'.
        """
        from datetime import datetime, timedelta

        cutoff = datetime.utcnow() - timedelta(minutes=offline_threshold_minutes)
        query = self.db.query(Branch).filter(
            or_(
                Branch.connection_status == "offline",
                Branch.last_seen_at < cutoff,
            )
        )
        if active_only:
            query = query.filter(Branch.is_active == True)
        return query.order_by(Branch.last_seen_at.asc().nullsfirst()).all()
