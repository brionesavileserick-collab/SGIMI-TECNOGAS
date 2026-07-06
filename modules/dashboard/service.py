"""
Dashboard service layer - Aggregates data from multiple modules.
"""

from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from modules.inventory.repository import InventoryRepository
from modules.movements.repository import MovementRepository
from modules.products.repository import ProductRepository
from modules.branches.repository import BranchRepository
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class DashboardService:
    """Service for dashboard metrics and KPIs."""

    def __init__(self, db: Session):
        self.db = db
        self.inventory_repo = InventoryRepository(db)
        self.movement_repo = MovementRepository(db)
        self.product_repo = ProductRepository(db)
        self.branch_repo = BranchRepository(db)

    def get_dashboard_metrics(self, branch_id: int = None) -> Dict[str, Any]:
        """Get all dashboard metrics."""
        return {
            "total_products": self.product_repo.count(),
            "total_branches": self.branch_repo.count(),
            "total_physical_stock": self.inventory_repo.get_total_physical_stock(branch_id),
            "total_digital_stock": self.inventory_repo.get_total_digital_stock(branch_id),
            "discrepancy_count": self.inventory_repo.get_discrepancy_count(branch_id),
            "low_stock_count": self.inventory_repo.get_low_stock_count(branch_id),
            "pending_movements": self.movement_repo.get_pending_count(branch_id),
            "movement_stats": self.movement_repo.get_stats_by_type(branch_id),
            "kpi_eri": self.calculate_kpi_eri(branch_id),
            "kpi_eru": self.calculate_kpi_eru(branch_id)
        }

    def calculate_kpi_eri(self, branch_id: int = None) -> float:
        """
        Calculate ERI (Exactitud de Registros de Inventario).
        ERI = (Items without discrepancy / Total items) * 100
        """
        total_items = self.inventory_repo.count(branch_id)
        if total_items == 0:
            return 100.0

        discrepancy_count = self.inventory_repo.get_discrepancy_count(branch_id)
        accurate_items = total_items - discrepancy_count

        eri = (accurate_items / total_items) * 100
        return round(eri, 2)

    def calculate_kpi_eru(self, branch_id: int = None) -> float:
        """
        Calculate ERU (Exactitud de Registros de Ubicacion).
        Simplified: Based on inventory update frequency.
        """
        from models.inventory import Inventory

        # Get items updated in last 30 days
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        query = self.db.query(func.count(Inventory.id)).filter(
            Inventory.is_active == True,
            Inventory.updated_at >= thirty_days_ago
        )

        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)

        recently_updated = query.scalar()

        total_items = self.inventory_repo.count(branch_id)
        if total_items == 0:
            return 100.0

        eru = (recently_updated / total_items) * 100
        return round(eru, 2)

    def get_movement_summary(self, days: int = 30, branch_id: int = None) -> Dict[str, Any]:
        """Get movement summary for the last N days."""
        date_from = datetime.utcnow() - timedelta(days=days)

        stats = self.movement_repo.get_stats_by_type(branch_id, date_from)

        return {
            "period_days": days,
            "stats_by_type": stats,
            "total_movements": sum(s.get("count", 0) for s in stats.values())
        }

    def get_low_stock_alerts(self, branch_id: int = None) -> List[Dict[str, Any]]:
        """Get items with low stock."""
        items = self.inventory_repo.get_all(
            limit=50,
            branch_id=branch_id,
            low_stock_only=True
        )

        alerts = []
        for item in items:
            details = self.inventory_repo.get_inventory_with_details(item.id)
            if details:
                alerts.append({
                    "product": details["product"]["name"],
                    "branch": details["branch"]["name"],
                    "current_stock": item.digital_stock,
                    "min_stock": item.min_stock
                })

        return alerts

    def get_discrepancy_alerts(self, branch_id: int = None) -> List[Dict[str, Any]]:
        """Get items with discrepancies."""
        items = self.inventory_repo.get_all(
            limit=50,
            branch_id=branch_id,
            discrepancy_only=True
        )

        alerts = []
        for item in items:
            details = self.inventory_repo.get_inventory_with_details(item.id)
            if details:
                alerts.append({
                    "product": details["product"]["name"],
                    "branch": details["branch"]["name"],
                    "physical_stock": item.physical_stock,
                    "digital_stock": item.digital_stock,
                    "difference": item.difference
                })

        return alerts

    def get_recent_movements(self, limit: int = 10, branch_id: int = None) -> List[Dict[str, Any]]:
        """Get recent movements."""
        movements = self.movement_repo.get_all(
            limit=limit,
            branch_id=branch_id
        )

        result = []
        for movement in movements:
            details = self.movement_repo.get_movement_with_details(movement.id)
            if details:
                result.append({
                    "id": movement.id,
                    "type": movement.movement_type,
                    "product": details["product"]["name"],
                    "branch": details["branch"]["name"],
                    "quantity": movement.quantity,
                    "state": movement.state,
                    "created_at": movement.created_at.isoformat() if movement.created_at else None
                })

        return result

    def get_branch_comparison(self) -> List[Dict[str, Any]]:
        """Compare metrics across branches."""
        from models.branch import Branch

        branches = self.db.query(Branch).filter(Branch.is_active == True).all()

        comparison = []
        for branch in branches:
            metrics = {
                "branch_id": branch.id,
                "branch_name": branch.name,
                "total_stock": self.inventory_repo.get_total_digital_stock(branch.id),
                "discrepancies": self.inventory_repo.get_discrepancy_count(branch.id),
                "low_stock": self.inventory_repo.get_low_stock_count(branch.id),
                "pending_movements": self.movement_repo.get_pending_count(branch.id)
            }
            comparison.append(metrics)

        return comparison
