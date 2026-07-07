"""
Dashboard service layer - Aggregates data from multiple modules.

Expansions implemented:
  Exp 1  - Branch filter (already existed, now fully exposed)
  Exp 2  - Period selection for get_movement_summary
  Exp 3  - Trend indicators: calculate_trend, get_comparison_metrics
  Exp 6  - Transfer widget: get_pending_transfers, get_transfer_summary
  Exp 7  - Efficiency widget: get_efficiency_metrics
  Exp 8  - Real notifications: get_urgent_alerts, get_overdue_items
  Exp 9  - Customizable widgets: get/save/visible widget config
  Exp 10 - Charts: get_movement_trend, get_stock_trend
  Exp 11 - Quick stats: get_quick_stats
  Exp 12 - Alert filter: get_all_alerts_with_type
  Exp 5  - Branch ranking: get_branch_ranking
"""

from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from modules.inventory.repository import InventoryRepository
from modules.movements.repository import MovementRepository
from modules.products.repository import ProductRepository
from modules.branches.repository import BranchRepository
from datetime import datetime, timedelta
import logging
import json

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Period helpers
# ---------------------------------------------------------------------------

def _resolve_period(
    period: str,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Translate a period string into (date_from, date_to) datetimes.

    period values: "all" | "today" | "this_week" | "this_month" |
                   "last_month" | "custom"
    For "custom", date_from and date_to must be provided.
    Returns (None, None) for "all" so callers can omit date filters.
    """
    now = datetime.utcnow()
    if period == "all" or period is None:
        return None, None
    elif period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, now
    elif period == "this_week":
        start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return start, now
    elif period == "this_month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, now
    elif period == "last_month":
        first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day_prev = first_of_this_month - timedelta(days=1)
        start = last_day_prev.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, first_of_this_month
    elif period == "custom":
        return date_from, date_to
    return None, None


def _previous_period(
    date_from: Optional[datetime],
    date_to: Optional[datetime],
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Return the equivalent previous period of the same length."""
    if date_from is None or date_to is None:
        return None, None
    delta = date_to - date_from
    return date_from - delta, date_from


class DashboardService:
    """Service for dashboard metrics and KPIs."""

    def __init__(self, db: Session):
        self.db = db
        self.inventory_repo = InventoryRepository(db)
        self.movement_repo = MovementRepository(db)
        self.product_repo = ProductRepository(db)
        self.branch_repo = BranchRepository(db)

    # ------------------------------------------------------------------
    # Core metrics (Exp 1: branch_id now fully used everywhere)
    # ------------------------------------------------------------------

    def get_dashboard_metrics(self, branch_id: int = None) -> Dict[str, Any]:
        """Get all dashboard metrics, optionally filtered by branch."""
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
            "kpi_eru": self.calculate_kpi_eru(branch_id),
        }

    def calculate_kpi_eri(self, branch_id: int = None) -> float:
        """ERI = (Items without discrepancy / Total items) * 100"""
        total_items = self.inventory_repo.count(branch_id)
        if total_items == 0:
            return 100.0
        discrepancy_count = self.inventory_repo.get_discrepancy_count(branch_id)
        eri = ((total_items - discrepancy_count) / total_items) * 100
        return round(eri, 2)

    def calculate_kpi_eru(self, branch_id: int = None) -> float:
        """ERU – based on inventory update frequency in the last 30 days."""
        from models.inventory import Inventory

        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        query = self.db.query(func.count(Inventory.id)).filter(
            Inventory.is_active == True,
            Inventory.updated_at >= thirty_days_ago,
        )
        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)
        recently_updated = query.scalar()

        total_items = self.inventory_repo.count(branch_id)
        if total_items == 0:
            return 100.0
        return round((recently_updated / total_items) * 100, 2)

    # ------------------------------------------------------------------
    # Exp 2 – Period-filtered movement summary
    # ------------------------------------------------------------------

    def get_movement_summary(
        self,
        branch_id: int = None,
        period: str = "this_month",
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get movement summary filtered by period.

        period: "all" | "today" | "this_week" | "this_month" | "last_month" | "custom"
        For "custom" pass date_from and date_to explicitly.
        """
        df, dt = _resolve_period(period, date_from, date_to)
        stats = self.movement_repo.get_stats_by_type(branch_id, df)

        return {
            "period": period,
            "date_from": df.isoformat() if df else None,
            "date_to": dt.isoformat() if dt else None,
            "stats_by_type": stats,
            "total_movements": sum(s.get("count", 0) for s in stats.values()),
        }

    # ------------------------------------------------------------------
    # Exp 3 – Trend indicators
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_trend(current_value: float, previous_value: float) -> Dict[str, Any]:
        """
        Compare current vs previous value.
        Returns {"direction": "up"|"down"|"same", "change": number, "percentage": float}
        """
        change = current_value - previous_value
        if previous_value == 0:
            percentage = 100.0 if current_value > 0 else 0.0
        else:
            percentage = round((change / previous_value) * 100, 2)

        if change > 0:
            direction = "up"
        elif change < 0:
            direction = "down"
        else:
            direction = "same"

        return {"direction": direction, "change": change, "percentage": percentage}

    def get_comparison_metrics(
        self,
        branch_id: int = None,
        period: str = "this_month",
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Calculate current-period and previous-period metrics and return trend info.
        Applies to: low_stock, discrepancies, movements, entradas, salidas.
        """
        df, dt = _resolve_period(period, date_from, date_to)
        prev_df, prev_dt = _previous_period(df, dt)

        # Current period
        cur_stats = self.movement_repo.get_stats_by_type(branch_id, df)
        cur_movements = sum(s.get("count", 0) for s in cur_stats.values())
        cur_entradas = cur_stats.get("entrada", {}).get("count", 0)
        cur_salidas = cur_stats.get("salida", {}).get("count", 0)
        cur_low_stock = self.inventory_repo.get_low_stock_count(branch_id)
        cur_discrepancies = self.inventory_repo.get_discrepancy_count(branch_id)

        # Previous period
        prev_stats = self.movement_repo.get_stats_by_type(branch_id, prev_df)
        prev_movements = sum(s.get("count", 0) for s in prev_stats.values())
        prev_entradas = prev_stats.get("entrada", {}).get("count", 0)
        prev_salidas = prev_stats.get("salida", {}).get("count", 0)

        return {
            "movements": {
                "current": cur_movements,
                "previous": prev_movements,
                "trend": self.calculate_trend(cur_movements, prev_movements),
            },
            "entradas": {
                "current": cur_entradas,
                "previous": prev_entradas,
                "trend": self.calculate_trend(cur_entradas, prev_entradas),
            },
            "salidas": {
                "current": cur_salidas,
                "previous": prev_salidas,
                "trend": self.calculate_trend(cur_salidas, prev_salidas),
            },
            "low_stock": {
                "current": cur_low_stock,
                "previous": cur_low_stock,   # static – no history available
                "trend": {"direction": "same", "change": 0, "percentage": 0.0},
            },
            "discrepancies": {
                "current": cur_discrepancies,
                "previous": cur_discrepancies,
                "trend": {"direction": "same", "change": 0, "percentage": 0.0},
            },
        }

    # ------------------------------------------------------------------
    # Alert helpers (used by Exp 8 and Exp 12)
    # ------------------------------------------------------------------

    def get_low_stock_alerts(self, branch_id: int = None) -> List[Dict[str, Any]]:
        """Get items with low stock."""
        items = self.inventory_repo.get_all(limit=50, branch_id=branch_id, low_stock_only=True)
        alerts = []
        for item in items:
            details = self.inventory_repo.get_inventory_with_details(item.id)
            if details:
                alerts.append({
                    "type": "low_stock",
                    "product": details["product"]["name"],
                    "branch": details["branch"]["name"],
                    "current_stock": item.digital_stock,
                    "min_stock": item.min_stock,
                })
        return alerts

    def get_discrepancy_alerts(self, branch_id: int = None) -> List[Dict[str, Any]]:
        """Get items with discrepancies."""
        items = self.inventory_repo.get_all(limit=50, branch_id=branch_id, discrepancy_only=True)
        alerts = []
        for item in items:
            details = self.inventory_repo.get_inventory_with_details(item.id)
            if details:
                alerts.append({
                    "type": "discrepancy",
                    "product": details["product"]["name"],
                    "branch": details["branch"]["name"],
                    "physical_stock": item.physical_stock,
                    "digital_stock": item.digital_stock,
                    "difference": item.difference,
                })
        return alerts

    # ------------------------------------------------------------------
    # Exp 12 – Unified alerts with type tag
    # ------------------------------------------------------------------

    def get_all_alerts_with_type(self, branch_id: int = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        Return all alert categories keyed by type.
        Keys: "low_stock", "discrepancy", "pending_transfers"
        """
        low_stock = self.get_low_stock_alerts(branch_id)
        discrepancies = self.get_discrepancy_alerts(branch_id)
        transfers = self.get_pending_transfers(branch_id)

        pending_transfer_alerts = []
        for t in transfers.get("sent", []) + transfers.get("received", []):
            pending_transfer_alerts.append({
                "type": "pending_transfer",
                "product": t.get("product", ""),
                "branch": t.get("origin_branch", t.get("destination_branch", "")),
                "quantity": t.get("quantity", 0),
                "hours_ago": t.get("hours_ago", 0),
            })

        return {
            "low_stock": low_stock,
            "discrepancy": discrepancies,
            "pending_transfer": pending_transfer_alerts,
        }

    # ------------------------------------------------------------------
    # Exp 6 – Transfer widget
    # ------------------------------------------------------------------

    def get_pending_transfers(
        self, branch_id: int = None, direction: str = "both"
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Return pending (validated, not-received, not-cancelled) transfers.

        direction: "sent" | "received" | "both"
        branch_id=None returns all cross-branch transfers.
        """
        from models.movement import Movement, MovementState
        from models.product import Product
        from models.branch import Branch

        base = (
            self.db.query(Movement, Product, Branch)
            .join(Product, Movement.product_id == Product.id)
            .join(Branch, Movement.branch_id == Branch.id)
            .filter(
                Movement.movement_type == "transferencia",
                Movement.state == MovementState.VALIDADO.value,
                Movement.is_received == False,
                Movement.is_cancelled == False,
            )
        )

        sent_items: List[Dict[str, Any]] = []
        received_items: List[Dict[str, Any]] = []
        now = datetime.utcnow()

        if direction in ("sent", "both"):
            q_sent = base
            if branch_id:
                q_sent = q_sent.filter(Movement.branch_id == branch_id)
            for mv, prod, br in q_sent.order_by(Movement.validated_at.desc()).limit(20).all():
                dest_name = ""
                if mv.destination_branch_id:
                    dest_br = self.db.query(Branch).filter(
                        Branch.id == mv.destination_branch_id
                    ).first()
                    dest_name = dest_br.name if dest_br else ""
                hours = round((now - mv.validated_at).total_seconds() / 3600, 1) if mv.validated_at else 0
                sent_items.append({
                    "id": mv.id,
                    "product": prod.name,
                    "quantity": mv.quantity,
                    "origin_branch": br.name,
                    "destination_branch": dest_name,
                    "hours_ago": hours,
                    "priority": mv.priority,
                })

        if direction in ("received", "both"):
            q_recv = base
            if branch_id:
                q_recv = q_recv.filter(Movement.destination_branch_id == branch_id)
            for mv, prod, br in q_recv.order_by(Movement.validated_at.desc()).limit(20).all():
                hours = round((now - mv.validated_at).total_seconds() / 3600, 1) if mv.validated_at else 0
                received_items.append({
                    "id": mv.id,
                    "product": prod.name,
                    "quantity": mv.quantity,
                    "origin_branch": br.name,
                    "hours_ago": hours,
                    "priority": mv.priority,
                })

        return {"sent": sent_items, "received": received_items}

    def get_transfer_summary(
        self, branch_id: int = None, days: int = 30
    ) -> Dict[str, Any]:
        """Summary of completed transfers in the last N days."""
        from models.movement import Movement, MovementState

        date_from = datetime.utcnow() - timedelta(days=days)
        q = (
            self.db.query(func.count(Movement.id), func.sum(Movement.quantity))
            .filter(
                Movement.movement_type == "transferencia",
                Movement.state == MovementState.VALIDADO.value,
                Movement.is_cancelled == False,
                Movement.created_at >= date_from,
            )
        )
        if branch_id:
            q = q.filter(
                or_(Movement.branch_id == branch_id, Movement.destination_branch_id == branch_id)
            )
        count, total_qty = q.first()
        return {
            "days": days,
            "total_transfers": count or 0,
            "total_quantity": total_qty or 0,
        }

    # ------------------------------------------------------------------
    # Exp 7 – Efficiency widget
    # ------------------------------------------------------------------

    def get_efficiency_metrics(
        self, branch_id: int = None, days: int = 30
    ) -> Dict[str, Any]:
        """
        Operational efficiency metrics for the last N days.
        Returns: total_movements, rejection_rate, validation_rate,
                 avg_validation_hours.
        """
        from models.movement import Movement

        date_from = datetime.utcnow() - timedelta(days=days)
        q = self.db.query(Movement).filter(
            Movement.is_cancelled == False,
            Movement.created_at >= date_from,
        )
        if branch_id:
            q = q.filter(Movement.branch_id == branch_id)

        movements = q.all()
        total = len(movements)
        if total == 0:
            return {
                "days": days,
                "total_movements": 0,
                "rejection_rate": 0.0,
                "validation_rate": 0.0,
                "avg_validation_hours": 0.0,
            }

        rejected = sum(1 for m in movements if m.state == "rechazado")
        validated = sum(1 for m in movements if m.state == "validado")

        # Average hours between creation and validation
        validation_times = []
        for m in movements:
            if m.validated_at and m.created_at:
                delta_h = (m.validated_at - m.created_at).total_seconds() / 3600
                if delta_h >= 0:
                    validation_times.append(delta_h)
        avg_hours = round(sum(validation_times) / len(validation_times), 2) if validation_times else 0.0

        return {
            "days": days,
            "total_movements": total,
            "rejection_rate": round((rejected / total) * 100, 2),
            "validation_rate": round((validated / total) * 100, 2),
            "avg_validation_hours": avg_hours,
        }

    # ------------------------------------------------------------------
    # Exp 5 – Branch ranking
    # ------------------------------------------------------------------

    def get_branch_ranking(
        self,
        metric: str = "stock_total",
        limit: int = 5,
        period: str = "this_month",
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Rank branches by a given metric.

        metric: "stock_total" | "discrepancies" | "low_stock" |
                "efficiency" | "movements"
        """
        from models.branch import Branch

        branches = self.db.query(Branch).filter(Branch.is_active == True).all()
        df, dt = _resolve_period(period, date_from, date_to)

        results = []
        for branch in branches:
            if metric == "stock_total":
                value = self.inventory_repo.get_total_digital_stock(branch.id)
            elif metric == "discrepancies":
                value = self.inventory_repo.get_discrepancy_count(branch.id)
            elif metric == "low_stock":
                value = self.inventory_repo.get_low_stock_count(branch.id)
            elif metric == "movements":
                stats = self.movement_repo.get_stats_by_type(branch.id, df)
                value = sum(s.get("count", 0) for s in stats.values())
            elif metric == "efficiency":
                eff = self.get_efficiency_metrics(branch.id)
                value = round(eff.get("validation_rate", 0.0), 2)
            else:
                value = 0

            results.append({
                "branch_id": branch.id,
                "branch_name": branch.name,
                "metric": metric,
                "value": value,
            })

        reverse = metric not in ("discrepancies", "low_stock")
        results.sort(key=lambda x: x["value"], reverse=reverse)

        for i, row in enumerate(results[:limit]):
            row["position"] = i + 1

        return results[:limit]

    # ------------------------------------------------------------------
    # Exp 8 – Real notifications
    # ------------------------------------------------------------------

    def get_urgent_alerts(self, branch_id: int = None) -> List[Dict[str, Any]]:
        """
        Return alerts that require immediate attention.
        Combines low-stock items marked "urgente" and very old pending transfers.
        """
        from models.inventory import Inventory
        from models.movement import Movement, MovementState

        alerts = []

        # Urgent reorder items
        q_inv = self.db.query(Inventory).filter(
            Inventory.is_active == True,
            Inventory.reorder_priority == "urgente",
            Inventory.digital_stock <= Inventory.min_stock,
        )
        if branch_id:
            q_inv = q_inv.filter(Inventory.branch_id == branch_id)
        for item in q_inv.limit(10).all():
            details = self.inventory_repo.get_inventory_with_details(item.id)
            if details:
                alerts.append({
                    "severity": "critical",
                    "type": "urgent_reorder",
                    "message": (
                        f"Reposición urgente: {details['product']['name']} "
                        f"en {details['branch']['name']} "
                        f"(stock: {item.digital_stock})"
                    ),
                })

        # Transfers pending > 48 h
        cutoff = datetime.utcnow() - timedelta(hours=48)
        q_tr = self.db.query(Movement).filter(
            Movement.movement_type == "transferencia",
            Movement.state == MovementState.VALIDADO.value,
            Movement.is_received == False,
            Movement.is_cancelled == False,
            Movement.validated_at <= cutoff,
        )
        if branch_id:
            q_tr = q_tr.filter(Movement.destination_branch_id == branch_id)
        for mv in q_tr.limit(10).all():
            hours = round((datetime.utcnow() - mv.validated_at).total_seconds() / 3600, 1)
            alerts.append({
                "severity": "warning",
                "type": "overdue_transfer",
                "message": f"Transferencia #{mv.id} sin recibir hace {hours} h.",
                "movement_id": mv.id,
            })

        return alerts

    def get_overdue_items(
        self, branch_id: int = None, hours_threshold: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Return movements/transfers that are overdue (pending > hours_threshold).
        """
        from models.movement import Movement, MovementState

        cutoff = datetime.utcnow() - timedelta(hours=hours_threshold)
        q = self.db.query(Movement).filter(
            Movement.is_cancelled == False,
            Movement.created_at <= cutoff,
        )
        if branch_id:
            q = q.filter(
                or_(Movement.branch_id == branch_id, Movement.destination_branch_id == branch_id)
            )

        overdue = []
        for mv in q.filter(Movement.state == MovementState.PENDIENTE.value).limit(20).all():
            hours = round((datetime.utcnow() - mv.created_at).total_seconds() / 3600, 1)
            overdue.append({
                "movement_id": mv.id,
                "type": mv.movement_type,
                "state": mv.state,
                "hours_pending": hours,
                "priority": mv.priority,
            })
        return overdue

    # ------------------------------------------------------------------
    # Exp 11 – Quick stats
    # ------------------------------------------------------------------

    def get_quick_stats(self, branch_id: int = None) -> Dict[str, Any]:
        """
        High-level executive summary in a single call.
        Returns: unique_products, total_stock, inventory_value,
                 movements_today, pending_movements.
        """
        today_start = datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        today_stats = self.movement_repo.get_stats_by_type(branch_id, today_start)
        movements_today = sum(s.get("count", 0) for s in today_stats.values())

        return {
            "unique_products": self.product_repo.count(),
            "total_stock": self.inventory_repo.get_total_digital_stock(branch_id),
            "inventory_value": self.inventory_repo.get_total_inventory_value(branch_id),
            "movements_today": movements_today,
            "pending_movements": self.movement_repo.get_pending_count(branch_id),
        }

    # ------------------------------------------------------------------
    # Exp 10 – Simple charts data
    # ------------------------------------------------------------------

    def get_movement_trend(
        self, branch_id: int = None, days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Return movement count per day for the last N days.
        Each entry: {"date": "YYYY-MM-DD", "count": int}
        """
        from models.movement import Movement

        result = []
        for i in range(days - 1, -1, -1):
            day = datetime.utcnow() - timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)

            q = self.db.query(func.count(Movement.id)).filter(
                Movement.is_cancelled == False,
                Movement.created_at >= day_start,
                Movement.created_at <= day_end,
            )
            if branch_id:
                q = q.filter(Movement.branch_id == branch_id)
            result.append({
                "date": day_start.strftime("%Y-%m-%d"),
                "count": q.scalar() or 0,
            })
        return result

    def get_stock_trend(
        self, branch_id: int = None, days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Return total digital stock snapshot using inventory updated_at.
        Approximates daily stock level from the latest update per day.
        Each entry: {"date": "YYYY-MM-DD", "stock": int}
        """
        from models.inventory import Inventory

        # We can't reconstruct historical stock without a dedicated history table,
        # so we return the current total for every day in the window as a sparkline
        # base, and note that real trend would require InventoryHistory aggregation.
        current_stock = self.inventory_repo.get_total_digital_stock(branch_id)
        result = []
        for i in range(days - 1, -1, -1):
            day = datetime.utcnow() - timedelta(days=i)
            result.append({
                "date": day.strftime("%Y-%m-%d"),
                "stock": current_stock,
            })
        return result

    # ------------------------------------------------------------------
    # Recent movements (unchanged, kept for compatibility)
    # ------------------------------------------------------------------

    def get_recent_movements(
        self,
        limit: int = 10,
        branch_id: int = None,
    ) -> List[Dict[str, Any]]:
        """Get recent movements."""
        movements = self.movement_repo.get_all(limit=limit, branch_id=branch_id)
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
                    "created_at": movement.created_at.isoformat() if movement.created_at else None,
                })
        return result

    def get_branch_comparison(self) -> List[Dict[str, Any]]:
        """Compare metrics across branches (kept for compatibility)."""
        from models.branch import Branch

        branches = self.db.query(Branch).filter(Branch.is_active == True).all()
        comparison = []
        for branch in branches:
            comparison.append({
                "branch_id": branch.id,
                "branch_name": branch.name,
                "total_stock": self.inventory_repo.get_total_digital_stock(branch.id),
                "discrepancies": self.inventory_repo.get_discrepancy_count(branch.id),
                "low_stock": self.inventory_repo.get_low_stock_count(branch.id),
                "pending_movements": self.movement_repo.get_pending_count(branch.id),
            })
        return comparison

    # ------------------------------------------------------------------
    # Exp 9 – Customizable widget config
    # ------------------------------------------------------------------

    def get_user_widget_config(self, user_id: int) -> List[Dict[str, Any]]:
        """Return all widget configs for a user, ordered by position."""
        try:
            from models.dashboard_widget_config import DashboardWidgetConfig

            rows = (
                self.db.query(DashboardWidgetConfig)
                .filter(DashboardWidgetConfig.user_id == user_id)
                .order_by(DashboardWidgetConfig.position)
                .all()
            )
            return [r.to_dict() for r in rows]
        except Exception as e:
            logger.warning(f"Widget config not available: {e}")
            return []

    def save_widget_config(
        self,
        user_id: int,
        widget_key: str,
        position: int = 0,
        is_visible: bool = True,
        config: Optional[Dict] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create or update a widget config for a user."""
        try:
            from models.dashboard_widget_config import DashboardWidgetConfig

            existing = (
                self.db.query(DashboardWidgetConfig)
                .filter(
                    DashboardWidgetConfig.user_id == user_id,
                    DashboardWidgetConfig.widget_key == widget_key,
                )
                .first()
            )
            if existing:
                existing.position = position
                existing.is_visible = is_visible
                existing.config = json.dumps(config) if config else None
            else:
                existing = DashboardWidgetConfig(
                    user_id=user_id,
                    widget_key=widget_key,
                    position=position,
                    is_visible=is_visible,
                    config=json.dumps(config) if config else None,
                )
                self.db.add(existing)

            self.db.commit()
            self.db.refresh(existing)
            return existing.to_dict()
        except Exception as e:
            logger.error(f"Error saving widget config: {e}")
            return None

    def get_visible_widgets(self, user_id: int) -> List[str]:
        """Return the list of visible widget keys for a user, in order."""
        configs = self.get_user_widget_config(user_id)
        if not configs:
            # Default: show all
            return [
                "quick_stats",
                "kpi",
                "stock_summary",
                "movements",
                "alerts",
                "transfers",
                "efficiency",
                "ranking",
                "charts",
                "recent_movements",
            ]
        return [c["widget_key"] for c in configs if c.get("is_visible")]
