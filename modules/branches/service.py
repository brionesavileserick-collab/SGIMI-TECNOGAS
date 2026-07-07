"""
Branch service layer - Business logic.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from modules.branches.repository import BranchRepository
from modules.inventory.service import InventoryService
from modules.movements.service import MovementService
from core.event_bus import event_bus
from core.settings import settings
from models.branch import OPERATIONAL_STATUS_VALUES, COUNT_FREQUENCY_VALUES
from utils.validators import validate_name
import logging

logger = logging.getLogger(__name__)


class BranchService:
    """Service for branch business logic."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = BranchRepository(db)
        self.inventory_service = InventoryService(db)
        self.movement_service = MovementService(db)

    # ------------------------------------------------------------------
    # CRUD base (sin cambios de comportamiento)
    # ------------------------------------------------------------------

    def create_branch(self, branch_data: dict) -> Dict[str, Any]:
        """Create a new branch."""
        branch_data = self._sanitize_branch_data(branch_data)
        self._validate_branch_data(branch_data, require_required=True)

        if self.repository.name_exists(branch_data.get("name")):
            raise ValueError(f"Sucursal '{branch_data.get('name')}' ya existe")

        branch = self.repository.create(branch_data)

        event_bus.emit(settings.Events.BRANCH_CREATED, {
            "branch_id": branch.id,
            "name": branch.name,
        })

        logger.info(f"Branch created: {branch.name}")
        return branch.to_dict()

    def get_branch(self, branch_id: int) -> Optional[Dict[str, Any]]:
        """Get branch by ID."""
        branch = self.repository.get_by_id(branch_id)
        return branch.to_dict() if branch else None

    def get_branch_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get branch by name."""
        branch = self.repository.get_by_name(name)
        return branch.to_dict() if branch else None

    def list_branches(
        self, page: int = 1, page_size: int = 20, search: str = None
    ) -> Dict[str, Any]:
        """List branches with pagination."""
        skip = (page - 1) * page_size
        branches = self.repository.get_all(skip=skip, limit=page_size, search=search)
        total = self.repository.count(search=search)

        return {
            "branches": [b.to_dict() for b in branches],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }

    def update_branch(self, branch_id: int, update_data: dict) -> Optional[Dict[str, Any]]:
        """Update branch general fields."""
        update_data = self._sanitize_branch_data(update_data)
        self._validate_branch_data(update_data, require_required=False)

        if "name" in update_data:
            if self.repository.name_exists(update_data["name"], exclude_id=branch_id):
                raise ValueError(f"Sucursal '{update_data['name']}' ya existe")

        # operational_status should go through update_operational_status()
        update_data.pop("operational_status", None)

        branch = self.repository.update(branch_id, update_data)
        if not branch:
            return None

        event_bus.emit(settings.Events.BRANCH_UPDATED, {
            "branch_id": branch.id,
            "name": branch.name,
            "changes": update_data,
        })

        logger.info(f"Branch updated: {branch.name}")
        return branch.to_dict()

    def delete_branch(self, branch_id: int) -> bool:
        """Soft delete branch."""
        branch = self.repository.get_by_id(branch_id)
        if not branch:
            return False

        success = self.repository.delete(branch_id)
        if success:
            event_bus.emit(settings.Events.BRANCH_DELETED, {
                "branch_id": branch_id,
                "name": branch.name,
            })
            logger.info(f"Branch deleted: {branch.name}")

        return success

    def search_branches(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search branches by name or address."""
        branches = self.repository.get_all(limit=limit, search=query)
        return [b.to_dict() for b in branches]

    def get_all_active_branches(self) -> List[Dict[str, Any]]:
        """Get all active branches."""
        branches = self.repository.get_all(limit=1000)
        return [b.to_dict() for b in branches]

    # ------------------------------------------------------------------
    # Expansión 1 – Ubicación geográfica
    # ------------------------------------------------------------------

    def get_branches_by_zone(self, zone: str = None) -> Dict[str, Any]:
        """
        Group active branches by zone.
        If zone is provided, return only branches in that zone.
        Otherwise return a dict {zone: [branches]} for all zones.
        """
        if zone:
            branches = self.repository.get_by_zone(zone)
            return {zone: [b.to_dict() for b in branches]}

        zones = self.repository.get_distinct_zones()
        result: Dict[str, List] = {}
        for z in zones:
            branches = self.repository.get_by_zone(z)
            result[z] = [b.to_dict() for b in branches]

        # Branches with no zone go to a special key
        all_active = self.repository.get_all(limit=10000)
        no_zone = [b.to_dict() for b in all_active if not b.zone]
        if no_zone:
            result["sin_zona"] = no_zone

        return result

    def get_branches_by_city(self, city: str) -> List[Dict[str, Any]]:
        """Return branches in a given city."""
        return [b.to_dict() for b in self.repository.get_by_city(city)]

    def get_branches_by_state(self, state: str) -> List[Dict[str, Any]]:
        """Return branches in a given state/province."""
        return [b.to_dict() for b in self.repository.get_by_state(state)]

    def get_available_zones(self) -> List[str]:
        """Return sorted list of zones currently in use."""
        return self.repository.get_distinct_zones()

    # ------------------------------------------------------------------
    # Expansión 2 – Configuración de inventario por sucursal
    # ------------------------------------------------------------------

    def get_effective_stock_threshold(self, branch_id: int) -> Dict[str, Any]:
        """
        Return the effective stock thresholds for a branch.
        Uses branch-specific values when set, falls back to global settings.
        """
        branch = self.repository.get_by_id(branch_id)
        if not branch:
            raise ValueError(f"Sucursal con id={branch_id} no existe")

        global_min = settings.LOW_STOCK_THRESHOLD

        return {
            "branch_id": branch_id,
            "branch_name": branch.name,
            "min_stock": branch.default_min_stock if branch.default_min_stock is not None else global_min,
            "max_stock": branch.default_max_stock,
            "stock_alert_enabled": branch.stock_alert_enabled,
            "source_min": "sucursal" if branch.default_min_stock is not None else "global",
            "source_max": "sucursal" if branch.default_max_stock is not None else "no_definido",
        }

    def get_branches_with_custom_stock_config(self) -> List[Dict[str, Any]]:
        """Return branches that override the global stock thresholds."""
        branches = self.repository.get_branches_with_custom_stock_config()
        return [b.to_dict() for b in branches]

    # ------------------------------------------------------------------
    # Expansión 3 – Estados operativos
    # ------------------------------------------------------------------

    def update_operational_status(
        self, branch_id: int, new_status: str
    ) -> Optional[Dict[str, Any]]:
        """
        Update operational status of a branch.
        Emits BRANCH_STATUS_CHANGED only when the status actually changes.
        """
        if new_status not in OPERATIONAL_STATUS_VALUES:
            raise ValueError(
                f"Estado operativo inválido: '{new_status}'. "
                f"Valores permitidos: {', '.join(OPERATIONAL_STATUS_VALUES)}"
            )

        branch = self.repository.get_by_id(branch_id)
        if not branch:
            return None

        previous_status = branch.operational_status
        if previous_status == new_status:
            return branch.to_dict()

        updated = self.repository.update(branch_id, {"operational_status": new_status})
        if not updated:
            return None

        event_bus.emit(settings.Events.BRANCH_STATUS_CHANGED, {
            "branch_id": branch_id,
            "name": updated.name,
            "previous_status": previous_status,
            "new_status": new_status,
        })

        logger.info(
            f"Branch '{updated.name}' status changed: {previous_status} -> {new_status}"
        )
        return updated.to_dict()

    def get_branches_by_operational_status(self, status: str) -> List[Dict[str, Any]]:
        """Return branches filtered by operational_status."""
        if status not in OPERATIONAL_STATUS_VALUES:
            raise ValueError(
                f"Estado operativo inválido: '{status}'. "
                f"Valores permitidos: {', '.join(OPERATIONAL_STATUS_VALUES)}"
            )
        branches = self.repository.get_by_operational_status(status)
        return [b.to_dict() for b in branches]

    def get_operational_status_summary(self) -> Dict[str, int]:
        """Return a count of branches per operational_status."""
        summary: Dict[str, int] = {s: 0 for s in OPERATIONAL_STATUS_VALUES}
        for status in self.repository.get_distinct_operational_statuses():
            branches = self.repository.get_by_operational_status(status)
            summary[status] = len(branches)
        return summary

    # ------------------------------------------------------------------
    # Expansión 4 – Responsable de sucursal
    # ------------------------------------------------------------------

    def assign_manager(self, branch_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Assign a user as manager of a branch.
        Validates that the user exists and is active before assigning.
        Emits BRANCH_MANAGER_ASSIGNED on success.
        """
        branch = self.repository.get_by_id(branch_id)
        if not branch:
            raise ValueError(f"Sucursal con id={branch_id} no existe")

        # Validate user exists and is active (query directly to avoid cross-module service)
        from models.user import User
        user = self.db.query(User).filter(User.id == user_id, User.is_active == True).first()
        if not user:
            raise ValueError(
                f"Usuario con id={user_id} no existe o está inactivo"
            )

        updated = self.repository.update(branch_id, {"manager_user_id": user_id})
        if not updated:
            return None

        event_bus.emit(settings.Events.BRANCH_MANAGER_ASSIGNED, {
            "branch_id": branch_id,
            "branch_name": updated.name,
            "manager_user_id": user_id,
            "manager_name": user.name,
        })

        logger.info(
            f"Branch '{updated.name}' manager assigned: {user.name} (id={user_id})"
        )
        return updated.to_dict()

    def remove_manager(self, branch_id: int) -> Optional[Dict[str, Any]]:
        """Remove the current manager from a branch."""
        branch = self.repository.get_by_id(branch_id)
        if not branch:
            return None

        updated = self.repository.update(branch_id, {"manager_user_id": None})
        logger.info(f"Branch '{branch.name}' manager removed")
        return updated.to_dict() if updated else None

    def get_branch_with_manager(self, branch_id: int) -> Optional[Dict[str, Any]]:
        """
        Return branch data enriched with manager user details.
        manager field is None when no manager is assigned.
        """
        branch = self.repository.get_by_id(branch_id)
        if not branch:
            return None

        result = branch.to_dict()
        manager = self.repository.get_branch_manager(branch_id)
        result["manager"] = manager.to_dict() if manager else None
        return result

    def get_branches_managed_by(self, user_id: int) -> List[Dict[str, Any]]:
        """Return all branches where the given user is the assigned manager."""
        branches = self.repository.get_branches_by_manager(user_id)
        return [b.to_dict() for b in branches]

    # ------------------------------------------------------------------
    # Expansión 5 – Frecuencia de conteo
    # ------------------------------------------------------------------

    def get_branches_by_count_frequency(
        self, frequency: str = None
    ) -> Dict[str, Any]:
        """
        Group branches by count_frequency.
        If frequency is provided, return only branches with that frequency.
        Otherwise return a dict {frequency: [branches]}.
        """
        if frequency:
            if frequency not in COUNT_FREQUENCY_VALUES:
                raise ValueError(
                    f"Frecuencia inválida: '{frequency}'. "
                    f"Valores permitidos: {', '.join(COUNT_FREQUENCY_VALUES)}"
                )
            branches = self.repository.get_by_count_frequency(frequency)
            return {frequency: [b.to_dict() for b in branches]}

        result: Dict[str, List] = {}
        for freq in COUNT_FREQUENCY_VALUES:
            branches = self.repository.get_by_count_frequency(freq)
            if branches:
                result[freq] = [b.to_dict() for b in branches]

        # Branches with no frequency set
        all_with_freq = self.repository.get_branches_with_count_frequency()
        ids_with_freq = {b.id for b in all_with_freq}
        no_freq = [
            b.to_dict()
            for b in self.repository.get_all(limit=10000)
            if b.id not in ids_with_freq
        ]
        if no_freq:
            result["sin_frecuencia"] = no_freq

        return result

    def get_branches_needing_count(self, frequency: str) -> List[Dict[str, Any]]:
        """Return branches configured for the given count frequency."""
        if frequency not in COUNT_FREQUENCY_VALUES:
            raise ValueError(
                f"Frecuencia inválida: '{frequency}'. "
                f"Valores permitidos: {', '.join(COUNT_FREQUENCY_VALUES)}"
            )
        branches = self.repository.get_by_count_frequency(frequency)
        return [b.to_dict() for b in branches]

    # ------------------------------------------------------------------
    # Expansión 6 – Capacidad
    # ------------------------------------------------------------------

    def get_branch_capacity_info(self, branch_id: int) -> Dict[str, Any]:
        """
        Return capacity info for a branch: configured max vs actual SKU count.
        capacity_available is None when max_products is not configured.
        """
        branch = self.repository.get_by_id(branch_id)
        if not branch:
            raise ValueError(f"Sucursal con id={branch_id} no existe")

        current_skus = self.repository.get_sku_count_for_branch(branch_id)
        capacity_available = (
            branch.max_products - current_skus
            if branch.max_products is not None
            else None
        )
        utilization_pct = (
            round((current_skus / branch.max_products) * 100, 1)
            if branch.max_products
            else None
        )

        return {
            "branch_id": branch_id,
            "branch_name": branch.name,
            "storage_capacity": branch.storage_capacity,
            "max_products": branch.max_products,
            "current_skus": current_skus,
            "capacity_available": capacity_available,
            "utilization_pct": utilization_pct,
        }

    def get_branches_by_capacity(self, capacity_label: str = None) -> List[Dict[str, Any]]:
        """
        Return branches ordered by max_products descending.
        If capacity_label is provided, filter by that storage_capacity label.
        """
        if capacity_label:
            branches = self.repository.get_by_storage_capacity(capacity_label)
        else:
            branches = self.repository.get_all_ordered_by_max_products()
        return [b.to_dict() for b in branches]

    # ------------------------------------------------------------------
    # Expansión 7 – Métricas propias del service
    # ------------------------------------------------------------------

    def get_branch_stats(self, branch_id: int) -> Dict[str, Any]:
        """
        Return a full stats snapshot for a single branch:
        inventory totals + discrepancy + low stock counts.
        Uses efficient SQL aggregation from the repository.
        """
        branch = self.repository.get_by_id(branch_id)
        if not branch:
            raise ValueError(f"Sucursal con id={branch_id} no existe")

        inv_totals = self.repository.get_inventory_totals_for_branch(branch_id)
        discrepancy_count = self.repository.get_discrepancy_count_for_branch(branch_id)
        low_stock_count = self.repository.get_low_stock_count_for_branch(branch_id)

        return {
            "branch_id": branch_id,
            "branch_name": branch.name,
            "operational_status": branch.operational_status,
            **inv_totals,
            "discrepancy_count": discrepancy_count,
            "low_stock_count": low_stock_count,
        }

    def get_all_branches_stats(self) -> Dict[str, Any]:
        """
        Return stats for every active branch in a single aggregated response.
        Includes a global_totals summary and per-branch list sorted by
        total_physical_stock descending (ranking).
        """
        summaries = self.repository.get_all_branches_inventory_summary()
        summary_map = {s["branch_id"]: s for s in summaries}

        branches = self.repository.get_all(limit=10000)
        branch_stats = []
        global_totals: Dict[str, int] = {
            "total_skus": 0,
            "total_physical_stock": 0,
            "total_digital_stock": 0,
            "discrepancy_count": 0,
            "low_stock_count": 0,
        }

        for branch in branches:
            stats = summary_map.get(
                branch.id,
                {
                    "total_skus": 0,
                    "total_physical_stock": 0,
                    "total_digital_stock": 0,
                    "discrepancy_count": 0,
                    "low_stock_count": 0,
                },
            )
            entry = {
                **branch.to_dict(),
                **stats,
            }
            branch_stats.append(entry)

            for key in global_totals:
                global_totals[key] += stats.get(key, 0)

        # Rank by physical stock (desc)
        branch_stats.sort(key=lambda x: x.get("total_physical_stock", 0), reverse=True)

        return {
            "branches": branch_stats,
            "global_totals": global_totals,
        }

    def get_branch_activity_summary(
        self, branch_id: int, days: int = 30
    ) -> Dict[str, Any]:
        """
        Return a summary of movement activity for a branch in the last N days.
        """
        branch = self.repository.get_by_id(branch_id)
        if not branch:
            raise ValueError(f"Sucursal con id={branch_id} no existe")

        movement_count = self.repository.get_movement_count_for_branch(branch_id, days=days)

        return {
            "branch_id": branch_id,
            "branch_name": branch.name,
            "period_days": days,
            "movement_count": movement_count,
        }

    def get_most_active_branch(self, days: int = 30) -> Optional[Dict[str, Any]]:
        """
        Return the branch with the most movements in the last N days.
        Returns None if no movements exist in the period.
        """
        counts = self.repository.get_movement_counts_per_branch(days=days)
        if not counts:
            return None

        top = counts[0]  # Already sorted desc
        branch = self.repository.get_by_id(top["branch_id"])
        if not branch:
            return None

        return {
            **branch.to_dict(),
            "movement_count": top["movement_count"],
            "period_days": days,
        }

    def get_branch_with_most_discrepancies(self) -> Optional[Dict[str, Any]]:
        """
        Return the branch that has the highest number of inventory discrepancies
        (physical_stock != digital_stock).
        """
        summaries = self.repository.get_all_branches_inventory_summary()
        if not summaries:
            return None

        top = max(summaries, key=lambda s: s["discrepancy_count"])
        if top["discrepancy_count"] == 0:
            return None

        branch = self.repository.get_by_id(top["branch_id"])
        if not branch:
            return None

        return {
            **branch.to_dict(),
            "discrepancy_count": top["discrepancy_count"],
        }

    def get_low_stock_branches(self) -> List[Dict[str, Any]]:
        """
        Return branches sorted by low_stock_count descending.
        Only includes branches with at least one low-stock item.
        """
        summaries = self.repository.get_all_branches_inventory_summary()
        branches = self.repository.get_all(limit=10000)
        branch_map = {b.id: b for b in branches}

        result = []
        for s in summaries:
            if s["low_stock_count"] == 0:
                continue
            branch = branch_map.get(s["branch_id"])
            if not branch:
                continue
            result.append({
                **branch.to_dict(),
                "low_stock_count": s["low_stock_count"],
            })

        result.sort(key=lambda x: x["low_stock_count"], reverse=True)
        return result

    # ------------------------------------------------------------------
    # Matrix-level methods (sin cambios)
    # ------------------------------------------------------------------

    def get_global_inventory(
        self,
        page: int = 1,
        page_size: int = 20,
        product_id: int = None,
        search: str = None,
    ) -> Dict[str, Any]:
        """Get global inventory (sum of stock across all branches)."""
        return self.inventory_service.get_global_inventory(
            page=page,
            page_size=page_size,
            product_id=product_id,
            search=search,
        )

    def get_product_stock_across_branches(self, product_id: int) -> List[Dict[str, Any]]:
        """Get stock for a specific product across all branches."""
        return self.inventory_service.get_product_stock_across_branches(product_id)

    def get_branch_inventory(
        self,
        branch_id: int,
        page: int = 1,
        page_size: int = 20,
        product_id: int = None,
        low_stock_only: bool = False,
        discrepancy_only: bool = False,
        search: str = None,
    ) -> Dict[str, Any]:
        """Get inventory for a specific branch."""
        return self.inventory_service.list_inventory(
            page=page,
            page_size=page_size,
            branch_id=branch_id,
            product_id=product_id,
            low_stock_only=low_stock_only,
            discrepancy_only=discrepancy_only,
            search=search,
        )

    def get_transfers_between_branches(
        self,
        origin_branch_id: int = None,
        destination_branch_id: int = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Get transfer movements between branches."""
        return self.movement_service.list_movements(
            page=page,
            page_size=page_size,
            branch_id=origin_branch_id,
            movement_type="transferencia",
        )

    def get_all_branches_totals(self) -> Dict[str, Any]:
        """Get inventory totals for all branches (global overview)."""
        branches = self.get_all_active_branches()
        result = {
            "branches": [],
            "global_totals": {
                "total_physical_stock": 0,
                "total_digital_stock": 0,
                "discrepancy_count": 0,
                "low_stock_count": 0,
            },
        }

        for branch in branches:
            branch_totals = self.inventory_service.get_totals(branch_id=branch["id"])
            branch["totals"] = branch_totals
            result["branches"].append(branch)

            result["global_totals"]["total_physical_stock"] += branch_totals["total_physical_stock"]
            result["global_totals"]["total_digital_stock"] += branch_totals["total_digital_stock"]
            result["global_totals"]["discrepancy_count"] += branch_totals["discrepancy_count"]
            result["global_totals"]["low_stock_count"] += branch_totals["low_stock_count"]

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sanitize_branch_data(self, branch_data: dict) -> dict:
        """Normalize branch input before persistence."""
        data = branch_data.copy()
        # String fields that need stripping
        for field in ("name", "address", "zone", "city", "state", "country",
                      "storage_capacity", "count_frequency", "operational_status"):
            if field in data and isinstance(data[field], str):
                data[field] = data[field].strip() or None if field != "name" else data[field].strip()
        return data

    def _validate_branch_data(self, branch_data: dict, require_required: bool) -> None:
        """Validate branch fields used by create and update operations."""
        if require_required or "name" in branch_data:
            is_valid, error = validate_name(branch_data.get("name"), "Nombre")
            if not is_valid:
                raise ValueError(error)

        if branch_data.get("address") and len(branch_data["address"]) > 255:
            raise ValueError("La dirección no puede tener más de 255 caracteres")

        if "operational_status" in branch_data and branch_data["operational_status"] is not None:
            if branch_data["operational_status"] not in OPERATIONAL_STATUS_VALUES:
                raise ValueError(
                    f"Estado operativo inválido: '{branch_data['operational_status']}'. "
                    f"Valores permitidos: {', '.join(OPERATIONAL_STATUS_VALUES)}"
                )

        if "count_frequency" in branch_data and branch_data["count_frequency"] is not None:
            if branch_data["count_frequency"] not in COUNT_FREQUENCY_VALUES:
                raise ValueError(
                    f"Frecuencia de conteo inválida: '{branch_data['count_frequency']}'. "
                    f"Valores permitidos: {', '.join(COUNT_FREQUENCY_VALUES)}"
                )

        if "default_min_stock" in branch_data and branch_data["default_min_stock"] is not None:
            if not isinstance(branch_data["default_min_stock"], int) or branch_data["default_min_stock"] < 0:
                raise ValueError("El stock mínimo por defecto debe ser un entero no negativo")

        if "default_max_stock" in branch_data and branch_data["default_max_stock"] is not None:
            if not isinstance(branch_data["default_max_stock"], int) or branch_data["default_max_stock"] < 0:
                raise ValueError("El stock máximo por defecto debe ser un entero no negativo")

        min_s = branch_data.get("default_min_stock")
        max_s = branch_data.get("default_max_stock")
        if min_s is not None and max_s is not None and max_s < min_s:
            raise ValueError("El stock máximo no puede ser menor que el stock mínimo")

        if "max_products" in branch_data and branch_data["max_products"] is not None:
            if not isinstance(branch_data["max_products"], int) or branch_data["max_products"] <= 0:
                raise ValueError("La capacidad máxima de productos debe ser un entero positivo")
