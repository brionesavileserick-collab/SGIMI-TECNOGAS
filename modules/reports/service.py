"""
Reports service layer - Generate reports from historical data.
"""

from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ReportsService:
    """Service for generating reports."""

    def __init__(self, db: Session):
        self.db = db

    def generate_inventory_report(self, branch_id: int = None) -> Dict[str, Any]:
        """Generate inventory status report."""
        from models.inventory import Inventory
        from models.product import Product
        from models.branch import Branch

        query = self.db.query(Inventory).join(Product).join(Branch).filter(
            Inventory.is_active == True,
            Product.is_active == True,
            Branch.is_active == True
        )

        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)

        items = query.all()

        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "total_items": len(items),
            "total_physical_stock": 0,
            "total_digital_stock": 0,
            "discrepancies": [],
            "low_stock": [],
            "by_branch": {}
        }

        for item in items:
            report["total_physical_stock"] += item.physical_stock
            report["total_digital_stock"] += item.digital_stock

            branch_name = item.branch.name
            if branch_name not in report["by_branch"]:
                report["by_branch"][branch_name] = {
                    "items": 0,
                    "physical_stock": 0,
                    "digital_stock": 0
                }

            report["by_branch"][branch_name]["items"] += 1
            report["by_branch"][branch_name]["physical_stock"] += item.physical_stock
            report["by_branch"][branch_name]["digital_stock"] += item.digital_stock

            if item.has_discrepancy:
                report["discrepancies"].append({
                    "product": item.product.name,
                    "branch": branch_name,
                    "physical": item.physical_stock,
                    "digital": item.digital_stock,
                    "difference": item.difference
                })

            if item.is_low_stock:
                report["low_stock"].append({
                    "product": item.product.name,
                    "branch": branch_name,
                    "current": item.digital_stock,
                    "min": item.min_stock
                })

        return report

    def generate_movement_report(self, date_from: datetime = None,
                                   date_to: datetime = None,
                                   branch_id: int = None) -> Dict[str, Any]:
        """Generate movement history report."""
        from models.movement import Movement

        query = self.db.query(Movement)

        if date_from:
            query = query.filter(Movement.created_at >= date_from)

        if date_to:
            query = query.filter(Movement.created_at <= date_to)

        if branch_id:
            query = query.filter(
                (Movement.branch_id == branch_id) |
                (Movement.destination_branch_id == branch_id)
            )

        movements = query.all()

        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "period": {
                "from": date_from.isoformat() if date_from else None,
                "to": date_to.isoformat() if date_to else None
            },
            "total_movements": len(movements),
            "by_type": {},
            "by_state": {},
            "by_branch": {}
        }

        for movement in movements:
            # By type
            mtype = movement.movement_type
            if mtype not in report["by_type"]:
                report["by_type"][mtype] = {"count": 0, "total_quantity": 0}
            report["by_type"][mtype]["count"] += 1
            report["by_type"][mtype]["total_quantity"] += movement.quantity

            # By state
            state = movement.state
            if state not in report["by_state"]:
                report["by_state"][state] = 0
            report["by_state"][state] += 1

            # By branch (origin)
            branch_id_key = movement.branch_id
            if branch_id_key not in report["by_branch"]:
                report["by_branch"][branch_id_key] = {"movements": 0, "quantity": 0}
            report["by_branch"][branch_id_key]["movements"] += 1
            report["by_branch"][branch_id_key]["quantity"] += movement.quantity

        return report

    def generate_kpi_report(self, branch_id: int = None) -> Dict[str, Any]:
        """Generate KPI report."""
        from modules.dashboard.service import DashboardService
        from modules.inventory.repository import InventoryRepository
        from modules.movements.repository import MovementRepository

        dashboard_service = DashboardService(self.db)

        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "branch_id": branch_id,
            "kpis": {
                "eri": dashboard_service.calculate_kpi_eri(branch_id),
                "eru": dashboard_service.calculate_kpi_eru(branch_id)
            },
            "metrics": {}
        }

        # Get inventory metrics
        inventory_repo = InventoryRepository(self.db)
        report["metrics"]["total_physical_stock"] = inventory_repo.get_total_physical_stock(branch_id)
        report["metrics"]["total_digital_stock"] = inventory_repo.get_total_digital_stock(branch_id)
        report["metrics"]["discrepancy_count"] = inventory_repo.get_discrepancy_count(branch_id)
        report["metrics"]["low_stock_count"] = inventory_repo.get_low_stock_count(branch_id)

        # Get movement metrics
        movement_repo = MovementRepository(self.db)
        report["metrics"]["pending_movements"] = movement_repo.get_pending_count(branch_id)

        # Last 30 days movement stats
        stats = movement_repo.get_stats_by_type(branch_id, datetime.utcnow() - timedelta(days=30))
        report["metrics"]["movement_stats_30d"] = stats

        return report

    def generate_discrepancy_report(self, branch_id: int = None) -> Dict[str, Any]:
        """Generate discrepancy analysis report."""
        from models.inventory import Inventory
        from models.product import Product
        from models.branch import Branch

        query = self.db.query(Inventory).join(Product).join(Branch).filter(
            Inventory.physical_stock != Inventory.digital_stock,
            Inventory.is_active == True
        )

        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)

        items = query.all()

        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "total_discrepancies": len(items),
            "items": [],
            "summary": {
                "total_difference": 0,
                "positive_differences": 0,
                "negative_differences": 0
            }
        }

        for item in items:
            diff = item.difference
            report["summary"]["total_difference"] += abs(diff)

            if diff > 0:
                report["summary"]["positive_differences"] += 1
            elif diff < 0:
                report["summary"]["negative_differences"] += 1

            report["items"].append({
                "product": item.product.name,
                "sku": item.product.sku,
                "branch": item.branch.name,
                "physical": item.physical_stock,
                "digital": item.digital_stock,
                "difference": diff,
                "percentage": round((abs(diff) / max(item.digital_stock, 1)) * 100, 2)
            })

        # Sort by percentage difference
        report["items"].sort(key=lambda x: x["percentage"], reverse=True)

        return report

    def generate_user_activity_report(self, user_id: int = None,
                                       date_from: datetime = None,
                                       date_to: datetime = None) -> Dict[str, Any]:
        """Generate user activity report."""
        from modules.history.service import HistoryService

        history_service = HistoryService(self.db)

        result = history_service.list_history(
            limit=1000,
            user_id=user_id,
            date_from=date_from,
            date_to=date_to
        )

        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "period": {
                "from": date_from.isoformat() if date_from else None,
                "to": date_to.isoformat() if date_to else None
            },
            "total_activities": result["total"],
            "by_event_type": {},
            "activities": result["entries"]
        }

        for entry in result["entries"]:
            event_type = entry["event_type"]
            if event_type not in report["by_event_type"]:
                report["by_event_type"][event_type] = 0
            report["by_event_type"][event_type] += 1

        return report
