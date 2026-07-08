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

        # Schedule first count if a frequency was provided
        if branch.count_frequency:
            self.schedule_next_count(branch.id)
            branch = self.repository.get_by_id(branch.id)

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

        # Reschedule count if count_frequency was part of the update
        if "count_frequency" in update_data:
            self.schedule_next_count(branch_id)
            branch = self.repository.get_by_id(branch_id)

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

    # ------------------------------------------------------------------
    # Expansión A – Sesión de trabajo (Fase 1, Prioridad Alta)
    # ------------------------------------------------------------------
    # La sesión es un estado volátil a nivel de aplicación.
    # Se almacena como variable de clase para que todas las instancias
    # del servicio compartan la misma sucursal activa en memoria.
    # ------------------------------------------------------------------

    _session_branch_id: Optional[int] = None   # volátil – se pierde al cerrar la app

    def get_current_session_branch(self) -> Optional[Dict[str, Any]]:
        """
        Return the branch currently active for this working session.
        Returns None when no session branch has been set.
        """
        if BranchService._session_branch_id is None:
            return None
        return self.get_branch(BranchService._session_branch_id)

    def set_current_session_branch(self, branch_id: int) -> Dict[str, Any]:
        """
        Set the working branch for the current session.
        Validates the branch exists and is active before accepting.
        Returns the branch dict on success.
        """
        branch = self.repository.get_by_id(branch_id)
        if not branch:
            raise ValueError(f"Sucursal con id={branch_id} no existe")
        if not branch.is_active:
            raise ValueError(
                f"Sucursal '{branch.name}' está inactiva y no puede usarse como sucursal de trabajo"
            )
        BranchService._session_branch_id = branch_id
        logger.info(f"Session branch set: {branch.name} (id={branch_id})")
        return branch.to_dict()

    def clear_session_branch(self) -> None:
        """Remove the current session branch (reset to unset state)."""
        BranchService._session_branch_id = None
        logger.info("Session branch cleared")

    # ------------------------------------------------------------------
    # Expansión B – Programación de conteos (Fase 1, Prioridad Alta)
    # ------------------------------------------------------------------

    # Mapping: count_frequency value → number of days between counts
    _FREQUENCY_DAYS: Dict[str, int] = {
        "diario":     1,
        "semanal":    7,
        "mensual":    30,
        "bimestral":  60,
        "trimestral": 90,
        "semestral":  180,
        "anual":      365,
    }

    def schedule_next_count(self, branch_id: int) -> Optional[Dict[str, Any]]:
        """
        Calculate and persist next_scheduled_count based on count_frequency.
        Uses last_count_date as the base; falls back to today when not set.
        Emits BRANCH_COUNT_SCHEDULED on success.
        Returns updated branch dict, or None when branch doesn't exist.
        """
        from datetime import datetime, timedelta

        branch = self.repository.get_by_id(branch_id)
        if not branch:
            return None

        if not branch.count_frequency:
            # Nothing to schedule without a frequency
            return branch.to_dict()

        days = self._FREQUENCY_DAYS.get(branch.count_frequency)
        if days is None:
            raise ValueError(
                f"Frecuencia de conteo desconocida: '{branch.count_frequency}'"
            )

        base = branch.last_count_date or datetime.utcnow()
        if hasattr(base, "replace"):
            base = base.replace(tzinfo=None)  # normalise to naïve UTC

        next_date = base + timedelta(days=days)
        updated = self.repository.update_next_scheduled_count(branch_id, next_date)
        if not updated:
            return None

        event_bus.emit(settings.Events.BRANCH_COUNT_SCHEDULED, {
            "branch_id": branch_id,
            "branch_name": updated.name,
            "count_frequency": updated.count_frequency,
            "next_scheduled_count": next_date.isoformat(),
        })

        logger.info(
            f"Branch '{updated.name}' next count scheduled: {next_date.date()}"
        )
        return updated.to_dict()

    def record_count_done(
        self, branch_id: int, count_date=None
    ) -> Optional[Dict[str, Any]]:
        """
        Mark a count as completed: persist last_count_date and reschedule.
        count_date defaults to now (UTC) when not provided.
        """
        from datetime import datetime

        branch = self.repository.get_by_id(branch_id)
        if not branch:
            return None

        when = count_date or datetime.utcnow()
        self.repository.update_last_count_date(branch_id, when)
        return self.schedule_next_count(branch_id)

    def get_overdue_count_branches(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Return branches whose scheduled count is overdue by at least *days* days.
        Emits BRANCH_COUNT_OVERDUE for each overdue branch found.
        """
        branches = self.repository.get_branches_with_overdue_counts(days=days)
        result = []
        for b in branches:
            event_bus.emit(settings.Events.BRANCH_COUNT_OVERDUE, {
                "branch_id": b.id,
                "branch_name": b.name,
                "next_scheduled_count": b.next_scheduled_count.isoformat()
                    if b.next_scheduled_count else None,
                "overdue_days": days,
            })
            result.append(b.to_dict())
        return result

    def get_upcoming_counts(self, days: int = 30) -> List[Dict[str, Any]]:
        """Return branches with a count scheduled within the next *days* days."""
        branches = self.repository.get_upcoming_counts(days=days)
        return [b.to_dict() for b in branches]

    def get_due_for_count_branches(self) -> List[Dict[str, Any]]:
        """Return branches whose next_scheduled_count is today or in the past."""
        branches = self.repository.get_branches_due_for_count()
        return [b.to_dict() for b in branches]

    # ------------------------------------------------------------------
    # Expansión C – Historial de configuración (Fase 1, Prioridad Alta)
    # ------------------------------------------------------------------

    # Fields tracked for audit (excludes timestamps and FK-resolved fields)
    _AUDITED_FIELDS = frozenset({
        "name", "address", "is_active", "zone", "city", "state", "country",
        "latitude", "longitude", "default_min_stock", "default_max_stock",
        "stock_alert_enabled", "operational_status", "count_frequency",
        "storage_capacity", "max_products",
        # Phase-2 fields
        "last_count_date", "next_scheduled_count", "count_enabled",
        "contact_phone", "contact_email", "emergency_contact", "emergency_phone",
        "opening_time", "closing_time", "timezone", "operational_days",
        "connection_status",
    })

    def update_branch_with_history(
        self,
        branch_id: int,
        update_data: dict,
        changed_by: str = None,
        reason: str = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Update a branch and log every changed field to branch_config_history.
        Wraps update_branch() with before/after comparison.
        changed_by should be the user's name or email (plain text).
        """
        current = self.repository.get_by_id(branch_id)
        if not current:
            return None

        # Capture current values for audited fields before the update
        before: Dict[str, Any] = {
            f: getattr(current, f, None)
            for f in self._AUDITED_FIELDS
            if f in update_data
        }

        updated = self.update_branch(branch_id, update_data)
        if not updated:
            return None

        # Log each field that actually changed
        for field, old_val in before.items():
            new_val = update_data.get(field)
            if str(old_val) != str(new_val):
                self.repository.log_config_change(
                    branch_id=branch_id,
                    field_name=field,
                    old_value=old_val,
                    new_value=new_val,
                    changed_by=changed_by,
                    reason=reason,
                )

        return updated

    def get_branch_change_history(
        self, branch_id: int, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Return the last *limit* config change records for a branch."""
        entries = self.repository.get_branch_config_history(branch_id, limit=limit)
        return [e.to_dict() for e in entries]

    # ------------------------------------------------------------------
    # Expansión D – Horarios de operación (Fase 2, Prioridad Media)
    # ------------------------------------------------------------------

    def is_branch_open_now(self, branch_id: int) -> Dict[str, Any]:
        """
        Determine whether a branch is currently within its operating hours.

        Returns a dict with:
          is_open       – bool (None when hours are not configured)
          opening_time  – str  "HH:MM"
          closing_time  – str  "HH:MM"
          current_time  – str  "HH:MM" (local or UTC when no timezone)
          reason        – human-readable explanation
        """
        branch = self.repository.get_by_id(branch_id)
        if not branch:
            raise ValueError(f"Sucursal con id={branch_id} no existe")

        opening = branch.opening_time
        closing = branch.closing_time

        if not opening or not closing:
            return {
                "branch_id": branch_id,
                "branch_name": branch.name,
                "is_open": None,
                "opening_time": opening,
                "closing_time": closing,
                "current_time": None,
                "reason": "Horario no configurado",
            }

        try:
            from datetime import datetime
            now_utc = datetime.utcnow()

            # Try to apply the branch timezone if pytz/zoneinfo is available
            tz_name = branch.timezone or "America/Mexico_City"
            try:
                try:
                    from zoneinfo import ZoneInfo
                    import datetime as _dt
                    tz = ZoneInfo(tz_name)
                    now_local = _dt.datetime.now(tz)
                except ImportError:
                    import pytz
                    tz = pytz.timezone(tz_name)
                    now_local = datetime.now(tz)
            except Exception:
                now_local = now_utc   # fallback to UTC

            current_hhmm = now_local.strftime("%H:%M")

            open_h, open_m = map(int, opening.split(":"))
            close_h, close_m = map(int, closing.split(":"))
            cur_h, cur_m = map(int, current_hhmm.split(":"))

            open_mins = open_h * 60 + open_m
            close_mins = close_h * 60 + close_m
            cur_mins = cur_h * 60 + cur_m

            # Handle overnight ranges (closing < opening, e.g. 22:00-06:00)
            if close_mins < open_mins:
                is_open = cur_mins >= open_mins or cur_mins < close_mins
            else:
                is_open = open_mins <= cur_mins < close_mins

            return {
                "branch_id": branch_id,
                "branch_name": branch.name,
                "is_open": is_open,
                "opening_time": opening,
                "closing_time": closing,
                "current_time": current_hhmm,
                "reason": "Dentro del horario" if is_open else "Fuera del horario",
            }

        except Exception as exc:
            logger.warning(f"Could not determine open status for branch {branch_id}: {exc}")
            return {
                "branch_id": branch_id,
                "branch_name": branch.name,
                "is_open": None,
                "opening_time": opening,
                "closing_time": closing,
                "current_time": None,
                "reason": f"Error al calcular horario: {exc}",
            }

    # ------------------------------------------------------------------
    # Expansión E – Validación de capacidad en transferencias (Fase 3)
    # ------------------------------------------------------------------

    def check_transfer_capacity(
        self, destination_branch_id: int, incoming_quantity: int
    ) -> Dict[str, Any]:
        """
        Check whether a destination branch can accommodate *incoming_quantity*
        additional SKUs without exceeding its max_products limit.

        Returns:
          allowed          – bool: True when transfer is within limits
          current          – int: current SKU count
          max              – int | None: configured limit
          would_exceed     – bool
          percent          – float | None: projected utilisation after transfer
          warning          – bool: projected utilisation >= 80 %
        """
        branch = self.repository.get_by_id(destination_branch_id)
        if not branch:
            raise ValueError(f"Sucursal destino con id={destination_branch_id} no existe")

        capacity = self.repository.get_branch_capacity_usage(destination_branch_id)
        current = capacity["current_count"]
        max_p = capacity["max_products"]

        if max_p is None:
            # No limit configured – always allowed
            result = {
                "branch_id": destination_branch_id,
                "branch_name": branch.name,
                "allowed": True,
                "current": current,
                "max": None,
                "would_exceed": False,
                "percent": None,
                "warning": False,
            }
            return result

        projected = current + incoming_quantity
        would_exceed = projected > max_p
        projected_pct = round((projected / max_p) * 100, 1)
        warning = projected_pct >= 80.0
        allowed = not would_exceed

        if not allowed:
            event_bus.emit(settings.Events.BRANCH_CAPACITY_EXCEEDED, {
                "branch_id": destination_branch_id,
                "branch_name": branch.name,
                "current": current,
                "max": max_p,
                "incoming_quantity": incoming_quantity,
                "projected": projected,
            })
        elif warning:
            event_bus.emit(settings.Events.BRANCH_CAPACITY_WARNING, {
                "branch_id": destination_branch_id,
                "branch_name": branch.name,
                "current": current,
                "max": max_p,
                "projected_pct": projected_pct,
            })

        return {
            "branch_id": destination_branch_id,
            "branch_name": branch.name,
            "allowed": allowed,
            "current": current,
            "max": max_p,
            "would_exceed": would_exceed,
            "percent": projected_pct,
            "warning": warning,
        }

    # ------------------------------------------------------------------
    # Expansión F – Estado de conectividad (Fase 3)
    # ------------------------------------------------------------------

    def mark_branch_online(self, branch_id: int) -> Optional[Dict[str, Any]]:
        """Mark a branch as online and update last_seen_at to now (UTC)."""
        from datetime import datetime

        branch = self.repository.get_by_id(branch_id)
        if not branch:
            return None

        updated = self.repository.update(branch_id, {
            "connection_status": "online",
            "last_seen_at": datetime.utcnow(),
        })
        return updated.to_dict() if updated else None

    def mark_branch_offline(self, branch_id: int) -> Optional[Dict[str, Any]]:
        """Mark a branch as offline."""
        branch = self.repository.get_by_id(branch_id)
        if not branch:
            return None

        updated = self.repository.update(branch_id, {"connection_status": "offline"})
        return updated.to_dict() if updated else None

    def get_offline_branches(
        self, offline_threshold_minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """Return branches considered offline (status='offline' or no recent ping)."""
        branches = self.repository.get_offline_branches(
            offline_threshold_minutes=offline_threshold_minutes
        )
        return [b.to_dict() for b in branches]

    def _update_connection_status(
        self, offline_threshold_minutes: int = 60
    ) -> int:
        """
        Internal helper: set connection_status='offline' for branches whose
        last_seen_at is older than *offline_threshold_minutes*.
        Returns the number of branches updated.
        """
        from datetime import datetime, timedelta

        cutoff = datetime.utcnow() - timedelta(minutes=offline_threshold_minutes)
        branches = self.repository.get_all(limit=10000)
        count = 0
        for b in branches:
            if (
                b.connection_status == "online"
                and b.last_seen_at
                and b.last_seen_at.replace(tzinfo=None) < cutoff
            ):
                self.repository.update(b.id, {"connection_status": "offline"})
                count += 1

        if count:
            logger.info(f"_update_connection_status: marked {count} branch(es) offline")
        return count

    # ------------------------------------------------------------------
    # Expansión G – Ranking y métricas comparativas (Fase 2, Prioridad Media)
    # ------------------------------------------------------------------

    def get_branch_comparative_report(self) -> List[Dict[str, Any]]:
        """
        Build a comparative report for all active branches.

        Each entry contains:
          branch_id, name, total_skus, discrepancy_count, discrepancy_rate,
          low_stock_count, movement_velocity (30-day), rank_by_discrepancy,
          rank_by_activity.
        """
        summaries = self.repository.get_all_branches_inventory_summary()
        movement_data = self.repository.get_movement_counts_per_branch(days=30)
        movement_map = {m["branch_id"]: m["movement_count"] for m in movement_data}

        branches = self.repository.get_all(limit=10000)
        summary_map = {s["branch_id"]: s for s in summaries}

        report = []
        for b in branches:
            s = summary_map.get(b.id, {
                "total_skus": 0,
                "total_physical_stock": 0,
                "total_digital_stock": 0,
                "discrepancy_count": 0,
                "low_stock_count": 0,
            })
            total_skus = s["total_skus"]
            disc_count = s["discrepancy_count"]
            disc_rate = round((disc_count / total_skus) * 100, 2) if total_skus else 0.0
            mv_count = movement_map.get(b.id, 0)
            velocity = round(mv_count / 30, 2)

            report.append({
                "branch_id": b.id,
                "name": b.name,
                "operational_status": b.operational_status,
                "total_skus": total_skus,
                "discrepancy_count": disc_count,
                "discrepancy_rate": disc_rate,
                "low_stock_count": s["low_stock_count"],
                "movement_count_30d": mv_count,
                "movement_velocity": velocity,
            })

        # Compute ranks
        sorted_by_disc = sorted(
            report, key=lambda x: x["discrepancy_rate"], reverse=True
        )
        sorted_by_activity = sorted(
            report, key=lambda x: x["movement_velocity"], reverse=True
        )

        rank_disc = {entry["branch_id"]: i + 1 for i, entry in enumerate(sorted_by_disc)}
        rank_act = {entry["branch_id"]: i + 1 for i, entry in enumerate(sorted_by_activity)}

        for entry in report:
            entry["rank_by_discrepancy"] = rank_disc[entry["branch_id"]]
            entry["rank_by_activity"] = rank_act[entry["branch_id"]]

        # Final sort: best performance first (lowest discrepancy_rate)
        report.sort(key=lambda x: x["discrepancy_rate"])
        return report

    def get_worst_discrepancy_branches(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Return the top *limit* branches with the highest discrepancy rate."""
        report = self.get_branch_comparative_report()
        report.sort(key=lambda x: x["discrepancy_rate"], reverse=True)
        return report[:limit]

    def get_best_performing_branches(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Return the top *limit* branches with the lowest discrepancy rate."""
        report = self.get_branch_comparative_report()
        report.sort(key=lambda x: x["discrepancy_rate"])
        return report[:limit]
