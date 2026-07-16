"""
Inventory repository for database operations.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from models.inventory import Inventory
from models.inventory_history import InventoryHistory
from models.inventory_count_session import InventoryCountSession
from models.inventory_count_item import InventoryCountItem
from models.inventory_batch import InventoryBatch
from models.product import Product
from models.branch import Branch
from datetime import datetime, date, timedelta


class InventoryRepository:
    """Repository for inventory database operations."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # CRUD base (sin cambios - retrocompatible)
    # ------------------------------------------------------------------

    def create(self, inventory_data: dict) -> Inventory:
        """Create a new inventory record."""
        inventory = Inventory(**inventory_data)
        self.db.add(inventory)
        try:
            self.db.commit()
            self.db.refresh(inventory)
            return inventory
        except Exception as e:
            self.db.rollback()
            raise e

    def get_by_id(self, inventory_id: int) -> Optional[Inventory]:
        """Get inventory by ID."""
        return self.db.query(Inventory).filter(Inventory.id == inventory_id).first()

    def get_by_product_branch(self, product_id: int, branch_id: int) -> Optional[Inventory]:
        """Get inventory by product and branch."""
        return self.db.query(Inventory).filter(
            and_(
                Inventory.product_id == product_id,
                Inventory.branch_id == branch_id,
            )
        ).first()

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        branch_id: int = None,
        product_id: int = None,
        low_stock_only: bool = False,
        discrepancy_only: bool = False,
        search: str = None,
    ) -> List[Inventory]:
        """Get all inventory records with filtering."""
        query = self.db.query(Inventory).join(Product).join(Branch)

        query = query.filter(Inventory.is_active == True)
        query = query.filter(Product.is_active == True)
        query = query.filter(Branch.is_active == True)

        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)

        if product_id:
            query = query.filter(Inventory.product_id == product_id)

        if search:
            query = query.filter(
                or_(
                    Product.name.ilike(f"%{search}%"),
                    Product.sku.ilike(f"%{search}%"),
                    Branch.name.ilike(f"%{search}%"),
                )
            )

        if low_stock_only:
            query = query.filter(Inventory.digital_stock <= Inventory.min_stock)

        if discrepancy_only:
            query = query.filter(Inventory.physical_stock != Inventory.digital_stock)

        return query.offset(skip).limit(limit).all()

    def count(
        self,
        branch_id: int = None,
        product_id: int = None,
        low_stock_only: bool = False,
        discrepancy_only: bool = False,
        search: str = None,
    ) -> int:
        """Count inventory records with filtering."""
        query = self.db.query(Inventory).join(Product).join(Branch)

        query = query.filter(Inventory.is_active == True)
        query = query.filter(Product.is_active == True)
        query = query.filter(Branch.is_active == True)

        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)

        if product_id:
            query = query.filter(Inventory.product_id == product_id)

        if search:
            query = query.filter(
                or_(
                    Product.name.ilike(f"%{search}%"),
                    Product.sku.ilike(f"%{search}%"),
                    Branch.name.ilike(f"%{search}%"),
                )
            )

        if low_stock_only:
            query = query.filter(Inventory.digital_stock <= Inventory.min_stock)

        if discrepancy_only:
            query = query.filter(Inventory.physical_stock != Inventory.digital_stock)

        return query.count()

    def update(self, inventory_id: int, update_data: dict) -> Optional[Inventory]:
        """Update inventory record."""
        inventory = self.get_by_id(inventory_id)
        if not inventory:
            return None

        for key, value in update_data.items():
            if hasattr(inventory, key):
                setattr(inventory, key, value)

        self.db.commit()
        self.db.refresh(inventory)
        return inventory

    def update_stock(
        self,
        product_id: int,
        branch_id: int,
        physical_change: int = 0,
        digital_change: int = 0,
    ) -> Optional[Inventory]:
        """Update stock quantities for a product at a branch."""
        inventory = self.get_by_product_branch(product_id, branch_id)
        if not inventory:
            return None

        # Validate stock won't go negative
        if inventory.digital_stock + digital_change < 0:
            raise ValueError("Stock digital insuficiente para realizar esta operación")

        inventory.physical_stock += physical_change
        inventory.digital_stock += digital_change
        inventory.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(inventory)
        return inventory

    def set_stock(
        self,
        product_id: int,
        branch_id: int,
        physical_stock: int = None,
        digital_stock: int = None,
        notes: str = None,
    ) -> Inventory:
        """
        Set absolute stock values.
        Expansión 2: acepta parámetro opcional `notes` para last_count_notes.
        If inventory does not exist, it will be created automatically.
        """
        inventory = self.get_by_product_branch(product_id, branch_id)
        
        if not inventory:
            # Create inventory record if it doesn't exist
            inventory_data = {
                "product_id": product_id,
                "branch_id": branch_id,
                "physical_stock": physical_stock if physical_stock is not None else 0,
                "digital_stock": digital_stock if digital_stock is not None else 0,
                "min_stock": 0,
            }
            inventory = self.create(inventory_data)
            if notes is not None:
                inventory.last_count_notes = notes
                inventory.last_count_date = datetime.utcnow()
            return inventory

        if physical_stock is not None:
            inventory.physical_stock = physical_stock
            inventory.last_count_date = datetime.utcnow()
            if notes is not None:
                inventory.last_count_notes = notes

        if digital_stock is not None:
            inventory.digital_stock = digital_stock

        inventory.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(inventory)
        return inventory

    def delete(self, inventory_id: int) -> bool:
        """Soft delete inventory record."""
        inventory = self.get_by_id(inventory_id)
        if not inventory:
            return False

        inventory.is_active = False
        self.db.commit()
        return True

    def exists(self, product_id: int, branch_id: int) -> bool:
        """Check if inventory record exists."""
        return self.get_by_product_branch(product_id, branch_id) is not None

    # ------------------------------------------------------------------
    # Aggregate helpers (base - sin cambios)
    # ------------------------------------------------------------------

    def get_total_physical_stock(self, branch_id: int = None) -> int:
        """Get total physical stock."""
        query = self.db.query(func.sum(Inventory.physical_stock)).join(Product).join(Branch)
        query = query.filter(Inventory.is_active == True)
        query = query.filter(Product.is_active == True)
        query = query.filter(Branch.is_active == True)
        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)
        return query.scalar() or 0

    def get_total_digital_stock(self, branch_id: int = None) -> int:
        """Get total digital stock."""
        query = self.db.query(func.sum(Inventory.digital_stock)).join(Product).join(Branch)
        query = query.filter(Inventory.is_active == True)
        query = query.filter(Product.is_active == True)
        query = query.filter(Branch.is_active == True)
        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)
        return query.scalar() or 0

    def get_discrepancy_count(self, branch_id: int = None) -> int:
        """Count items with discrepancies (respects discrepancy_tolerance)."""
        query = self.db.query(Inventory).join(Product).join(Branch)
        query = query.filter(Inventory.is_active == True)
        query = query.filter(Product.is_active == True)
        query = query.filter(Branch.is_active == True)
        # Use absolute difference > tolerance
        query = query.filter(
            func.abs(Inventory.physical_stock - Inventory.digital_stock)
            > Inventory.discrepancy_tolerance
        )
        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)
        return query.count()

    def get_low_stock_count(self, branch_id: int = None) -> int:
        """Count items with low stock."""
        query = self.db.query(Inventory).join(Product).join(Branch)
        query = query.filter(Inventory.is_active == True)
        query = query.filter(Product.is_active == True)
        query = query.filter(Branch.is_active == True)
        query = query.filter(Inventory.digital_stock <= Inventory.min_stock)
        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)
        return query.count()

    def get_inventory_with_details(self, inventory_id: int) -> Optional[Dict[str, Any]]:
        """Get inventory with product and branch details."""
        result = self.db.query(Inventory, Product, Branch).join(
            Product, Inventory.product_id == Product.id
        ).join(
            Branch, Inventory.branch_id == Branch.id
        ).filter(Inventory.id == inventory_id).first()

        if not result:
            return None

        inventory, product, branch = result
        return {
            "inventory": inventory.to_dict(),
            "product": product.to_dict(),
            "branch": branch.to_dict(),
        }

    def get_global_inventory(
        self,
        skip: int = 0,
        limit: int = 100,
        product_id: int = None,
        search: str = None,
    ) -> List[Dict[str, Any]]:
        """Get global inventory (sum of stock across all branches)."""
        query = self.db.query(
            Product.id,
            Product.sku,
            Product.name,
            Product.unit_of_measure,
            Product.unit_price,
            func.sum(Inventory.physical_stock).label("total_physical_stock"),
            func.sum(Inventory.digital_stock).label("total_digital_stock"),
            func.count(Inventory.branch_id).label("branch_count"),
        ).join(
            Inventory, Product.id == Inventory.product_id
        ).join(
            Branch, Inventory.branch_id == Branch.id
        ).filter(
            Inventory.is_active == True,
            Product.is_active == True,
            Branch.is_active == True,
        ).group_by(
            Product.id, Product.sku, Product.name, Product.unit_of_measure, Product.unit_price
        )

        if product_id:
            query = query.filter(Product.id == product_id)

        if search:
            query = query.filter(
                or_(
                    Product.name.ilike(f"%{search}%"),
                    Product.sku.ilike(f"%{search}%"),
                )
            )

        results = query.offset(skip).limit(limit).all()
        return [
            {
                "product_id": r.id,
                "sku": r.sku,
                "name": r.name,
                "unit_of_measure": r.unit_of_measure,
                "unit_price": r.unit_price,
                "total_physical_stock": r.total_physical_stock or 0,
                "total_digital_stock": r.total_digital_stock or 0,
                "branch_count": r.branch_count,
            }
            for r in results
        ]

    def count_global_inventory(self, product_id: int = None, search: str = None) -> int:
        """Count distinct products in global inventory."""
        query = self.db.query(
            func.count(func.distinct(Inventory.product_id))
        ).join(
            Product, Inventory.product_id == Product.id
        ).join(
            Branch, Inventory.branch_id == Branch.id
        ).filter(
            Inventory.is_active == True,
            Product.is_active == True,
            Branch.is_active == True,
        )

        if product_id:
            query = query.filter(Product.id == product_id)

        if search:
            query = query.filter(
                or_(
                    Product.name.ilike(f"%{search}%"),
                    Product.sku.ilike(f"%{search}%"),
                )
            )

        return query.scalar() or 0

    def get_product_stock_across_branches(self, product_id: int) -> List[Dict[str, Any]]:
        """Get stock for a specific product across all branches."""
        results = self.db.query(
            Inventory,
            Branch.name,
            Branch.address,
        ).join(
            Branch, Inventory.branch_id == Branch.id
        ).join(
            Product, Inventory.product_id == Product.id
        ).filter(
            Inventory.product_id == product_id,
            Inventory.is_active == True,
            Product.is_active == True,
            Branch.is_active == True,
        ).all()

        return [
            {
                "inventory_id": inv.id,
                "branch_id": inv.branch_id,
                "branch_name": branch_name,
                "branch_address": branch_address,
                "physical_stock": inv.physical_stock,
                "digital_stock": inv.digital_stock,
                "difference": inv.difference,
                "has_discrepancy": inv.has_discrepancy,
                "is_low_stock": inv.is_low_stock,
            }
            for inv, branch_name, branch_address in results
        ]

    # ------------------------------------------------------------------
    # Expansión 1: Ubicación física
    # ------------------------------------------------------------------

    def get_by_location(self, branch_id: int, location: str) -> List[Inventory]:
        """
        Expansión 1 - Filtrar items por ubicación física dentro de una sucursal.
        La búsqueda es parcial e insensible a mayúsculas.
        """
        return (
            self.db.query(Inventory)
            .join(Product)
            .join(Branch)
            .filter(
                Inventory.branch_id == branch_id,
                Inventory.is_active == True,
                Product.is_active == True,
                Branch.is_active == True,
                Inventory.location_free.ilike(f"%{location}%"),
            )
            .all()
        )

    # ------------------------------------------------------------------
    # Expansión 3: Tags
    # ------------------------------------------------------------------

    def get_by_tag(self, tag: str, branch_id: int = None) -> List[Inventory]:
        """
        Expansión 3 - Filtrar items que contienen el tag dado.
        Busca la palabra exacta dentro del campo tags separado por comas.
        """
        query = (
            self.db.query(Inventory)
            .join(Product)
            .join(Branch)
            .filter(
                Inventory.is_active == True,
                Product.is_active == True,
                Branch.is_active == True,
                Inventory.tags.ilike(f"%{tag}%"),
            )
        )
        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)
        return query.all()

    # ------------------------------------------------------------------
    # Expansión 4: Prioridad de reposición
    # ------------------------------------------------------------------

    def get_by_priority(self, priority: str, branch_id: int = None) -> List[Inventory]:
        """
        Expansión 4 - Items filtrados por prioridad de reposición.
        priority: "urgente" | "normal" | "bajo"
        """
        query = (
            self.db.query(Inventory)
            .join(Product)
            .join(Branch)
            .filter(
                Inventory.is_active == True,
                Product.is_active == True,
                Branch.is_active == True,
                Inventory.reorder_priority == priority,
            )
        )
        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)
        return query.all()

    def get_urgent_reorders(self, branch_id: int) -> List[Inventory]:
        """
        Expansión 4 - Items con prioridad urgente Y stock bajo en una sucursal.
        """
        return (
            self.db.query(Inventory)
            .join(Product)
            .join(Branch)
            .filter(
                Inventory.branch_id == branch_id,
                Inventory.is_active == True,
                Product.is_active == True,
                Branch.is_active == True,
                Inventory.reorder_priority == "urgente",
                Inventory.digital_stock <= Inventory.min_stock,
            )
            .all()
        )

    # ------------------------------------------------------------------
    # Expansión 5: Alertas personalizadas
    # ------------------------------------------------------------------

    def get_items_with_active_alerts(self, branch_id: int) -> List[Inventory]:
        """
        Expansión 5 - Items que tienen al menos un umbral personalizado configurado.
        """
        return (
            self.db.query(Inventory)
            .join(Product)
            .join(Branch)
            .filter(
                Inventory.branch_id == branch_id,
                Inventory.is_active == True,
                Product.is_active == True,
                Branch.is_active == True,
                or_(
                    Inventory.critical_stock_threshold.isnot(None),
                    Inventory.max_stock_threshold.isnot(None),
                ),
            )
            .all()
        )

    # ------------------------------------------------------------------
    # Expansión 6: Stock en tránsito
    # ------------------------------------------------------------------

    def get_in_transit(self, branch_id: int) -> List[Inventory]:
        """
        Expansión 6 - Items con stock en tránsito hacia una sucursal.
        """
        return (
            self.db.query(Inventory)
            .join(Product)
            .join(Branch)
            .filter(
                Inventory.branch_id == branch_id,
                Inventory.is_active == True,
                Product.is_active == True,
                Branch.is_active == True,
                Inventory.in_transit_quantity > 0,
            )
            .all()
        )

    def update_in_transit(self, inventory_id: int, quantity: int) -> Optional[Inventory]:
        """
        Expansión 6 - Establece el valor absoluto de in_transit_quantity.
        """
        inventory = self.get_by_id(inventory_id)
        if not inventory:
            return None

        inventory.in_transit_quantity = max(0, quantity)
        inventory.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(inventory)
        return inventory

    # ------------------------------------------------------------------
    # Expansión 7: Historial de cambios
    # ------------------------------------------------------------------

    def create_history_record(
        self,
        inventory_id: int,
        previous_physical: int,
        new_physical: int,
        previous_digital: int,
        new_digital: int,
        change_type: str,
        movement_id: int = None,
        reason: str = None,
        digital_adjustment_notes: str = None,
        adjusted_by_name: str = None,
    ) -> InventoryHistory:
        """
        Expansión 7 - Registra un cambio de stock en el historial de auditoría.
        change_type: "count" | "movement" | "transfer" | "adjustment"
        """
        record = InventoryHistory(
            inventory_id=inventory_id,
            previous_physical=previous_physical,
            new_physical=new_physical,
            previous_digital=previous_digital,
            new_digital=new_digital,
            change_type=change_type,
            movement_id=movement_id,
            reason=reason,
            digital_adjustment_notes=digital_adjustment_notes,
            adjusted_by_name=adjusted_by_name,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_history(
        self,
        inventory_id: int,
        limit: int = 50,
        date_from: datetime = None,
        date_to: datetime = None,
    ) -> List[InventoryHistory]:
        """
        Expansión 7 - Historial de cambios de un item, con paginación y filtro de fechas.
        """
        query = (
            self.db.query(InventoryHistory)
            .filter(InventoryHistory.inventory_id == inventory_id)
        )
        if date_from:
            query = query.filter(InventoryHistory.created_at >= date_from)
        if date_to:
            query = query.filter(InventoryHistory.created_at <= date_to)

        return query.order_by(InventoryHistory.created_at.desc()).limit(limit).all()

    def get_history_by_change_type(
        self,
        inventory_id: int,
        change_type: str,
        limit: int = 50,
    ) -> List[InventoryHistory]:
        """
        Expansión 7 - Historial filtrado por tipo de cambio.
        """
        return (
            self.db.query(InventoryHistory)
            .filter(
                InventoryHistory.inventory_id == inventory_id,
                InventoryHistory.change_type == change_type,
            )
            .order_by(InventoryHistory.created_at.desc())
            .limit(limit)
            .all()
        )

    # ------------------------------------------------------------------
    # Expansión 8: Valor de inventario
    # ------------------------------------------------------------------

    def get_total_inventory_value(self, branch_id: int = None) -> float:
        """
        Expansión 8 - Valor total del inventario: SUM(digital_stock * unit_cost).
        Solo incluye items que tienen unit_cost configurado.
        """
        query = (
            self.db.query(
                func.sum(Inventory.digital_stock * Inventory.unit_cost)
            )
            .join(Product)
            .join(Branch)
            .filter(
                Inventory.is_active == True,
                Product.is_active == True,
                Branch.is_active == True,
                Inventory.unit_cost.isnot(None),
            )
        )
        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)

        return query.scalar() or 0.0

    def get_most_valuable_items(self, branch_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Expansión 8 - Top N items por valor total (digital_stock * unit_cost).
        """
        results = (
            self.db.query(
                Inventory,
                Product.name,
                Product.sku,
                (Inventory.digital_stock * Inventory.unit_cost).label("total_value"),
            )
            .join(Product, Inventory.product_id == Product.id)
            .join(Branch, Inventory.branch_id == Branch.id)
            .filter(
                Inventory.branch_id == branch_id,
                Inventory.is_active == True,
                Product.is_active == True,
                Branch.is_active == True,
                Inventory.unit_cost.isnot(None),
            )
            .order_by((Inventory.digital_stock * Inventory.unit_cost).desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "inventory_id": inv.id,
                "product_id": inv.product_id,
                "product_name": name,
                "product_sku": sku,
                "digital_stock": inv.digital_stock,
                "unit_cost": inv.unit_cost,
                "total_value": float(total_value) if total_value else 0.0,
            }
            for inv, name, sku, total_value in results
        ]

    # ------------------------------------------------------------------
    # Expansión 9: Métricas - helpers de agregación SQL
    # ------------------------------------------------------------------

    def get_items_with_discrepancy_in_period(
        self,
        branch_id: int,
        date_from: datetime,
        date_to: datetime,
    ) -> List[Dict[str, Any]]:
        """
        Expansión 9 - Items que tuvieron cambios tipo 'count' (discrepancia) en un período.
        Retorna inventory_id y número de conteos con discrepancia.
        """
        results = (
            self.db.query(
                InventoryHistory.inventory_id,
                func.count(InventoryHistory.id).label("count_events"),
            )
            .join(Inventory, InventoryHistory.inventory_id == Inventory.id)
            .filter(
                Inventory.branch_id == branch_id,
                InventoryHistory.change_type == "count",
                InventoryHistory.created_at >= date_from,
                InventoryHistory.created_at <= date_to,
                func.abs(
                    InventoryHistory.new_physical - InventoryHistory.new_digital
                ) > Inventory.discrepancy_tolerance,
            )
            .group_by(InventoryHistory.inventory_id)
            .order_by(func.count(InventoryHistory.id).desc())
            .all()
        )
        return [
            {"inventory_id": r.inventory_id, "discrepancy_count": r.count_events}
            for r in results
        ]

    def get_items_with_no_history_since(
        self,
        branch_id: int,
        since: datetime,
    ) -> List[Inventory]:
        """
        Expansión 9 - Items sin ningún movimiento en el historial desde `since`.
        Útil para detectar productos sin rotación.
        """
        # Subquery: inventory_ids que SÍ tuvieron cambios
        active_ids = (
            self.db.query(InventoryHistory.inventory_id)
            .filter(InventoryHistory.created_at >= since)
            .distinct()
            .subquery()
        )

        return (
            self.db.query(Inventory)
            .join(Product)
            .join(Branch)
            .filter(
                Inventory.branch_id == branch_id,
                Inventory.is_active == True,
                Product.is_active == True,
                Branch.is_active == True,
                ~Inventory.id.in_(active_ids),
            )
            .all()
        )

    def get_discrepancy_rate_data(self, branch_id: int) -> Dict[str, int]:
        """
        Expansión 9 - Datos crudos para calcular la tasa de discrepancia de la sucursal.
        Retorna total de items y cuántos tienen discrepancia.
        """
        base = (
            self.db.query(Inventory)
            .join(Product)
            .join(Branch)
            .filter(
                Inventory.branch_id == branch_id,
                Inventory.is_active == True,
                Product.is_active == True,
                Branch.is_active == True,
            )
        )
        total = base.count()
        with_discrepancy = base.filter(
            func.abs(Inventory.physical_stock - Inventory.digital_stock)
            > Inventory.discrepancy_tolerance
        ).count()

        return {"total": total, "with_discrepancy": with_discrepancy}

    def get_low_stock_ordered_by_priority(self, branch_id: int) -> List[Inventory]:
        """
        Expansión 9 - Items con stock bajo, ordenados por prioridad de reposición.
        Orden: urgente > normal > bajo.
        """
        from sqlalchemy import case

        priority_order = case(
            (Inventory.reorder_priority == "urgente", 1),
            (Inventory.reorder_priority == "normal", 2),
            (Inventory.reorder_priority == "bajo", 3),
            else_=4,
        )

        return (
            self.db.query(Inventory)
            .join(Product)
            .join(Branch)
            .filter(
                Inventory.branch_id == branch_id,
                Inventory.is_active == True,
                Product.is_active == True,
                Branch.is_active == True,
                Inventory.digital_stock <= Inventory.min_stock,
            )
            .order_by(priority_order)
            .all()
        )

    def get_all_tags_in_branch(self, branch_id: int) -> List[str]:
        """
        Expansión 3/9 - Retorna todos los tags únicos en uso dentro de la sucursal.
        """
        results = (
            self.db.query(Inventory.tags)
            .join(Branch)
            .filter(
                Inventory.branch_id == branch_id,
                Inventory.is_active == True,
                Inventory.tags.isnot(None),
                Inventory.tags != "",
            )
            .all()
        )

        # Descomponer el campo CSV en tags individuales y deduplicar
        tag_set = set()
        for (tags_str,) in results:
            for tag in tags_str.split(","):
                tag = tag.strip()
                if tag:
                    tag_set.add(tag)

        return sorted(tag_set)

    # ------------------------------------------------------------------
    # Workflow de conteos (sesiones)
    # ------------------------------------------------------------------

    def create_count_session(self, session_data: dict) -> InventoryCountSession:
        """Crear sesión de conteo."""
        session = InventoryCountSession(**session_data)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_count_session_by_id(self, session_id: int) -> Optional[InventoryCountSession]:
        """Obtener sesión por ID."""
        return (
            self.db.query(InventoryCountSession)
            .filter(InventoryCountSession.id == session_id)
            .first()
        )

    def get_count_sessions_by_branch(
        self, branch_id: int, status: str = None
    ) -> List[InventoryCountSession]:
        """Sesiones de conteo por sucursal."""
        query = self.db.query(InventoryCountSession).filter(
            InventoryCountSession.branch_id == branch_id
        )
        if status:
            query = query.filter(InventoryCountSession.status == status)
        return query.order_by(InventoryCountSession.scheduled_date.desc()).all()

    def update_count_session(
        self, session_id: int, data: dict
    ) -> Optional[InventoryCountSession]:
        """Actualizar sesión de conteo."""
        session = self.get_count_session_by_id(session_id)
        if not session:
            return None
        for key, value in data.items():
            if hasattr(session, key):
                setattr(session, key, value)
        self.db.commit()
        self.db.refresh(session)
        return session

    def add_count_item(self, session_id: int, item_data: dict) -> InventoryCountItem:
        """Agregar item a sesión de conteo."""
        item_data["session_id"] = session_id
        item = InventoryCountItem(**item_data)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_count_items(self, session_id: int) -> List[InventoryCountItem]:
        """Items de una sesión de conteo."""
        return (
            self.db.query(InventoryCountItem)
            .filter(InventoryCountItem.session_id == session_id)
            .order_by(InventoryCountItem.id)
            .all()
        )

    def get_count_item_by_inventory(
        self, session_id: int, inventory_id: int
    ) -> Optional[InventoryCountItem]:
        """Item de conteo para un inventario en una sesión."""
        return (
            self.db.query(InventoryCountItem)
            .filter(
                InventoryCountItem.session_id == session_id,
                InventoryCountItem.inventory_id == inventory_id,
            )
            .first()
        )

    def update_count_item(
        self, item_id: int, data: dict
    ) -> Optional[InventoryCountItem]:
        """Actualizar item de conteo."""
        item = self.db.query(InventoryCountItem).filter(
            InventoryCountItem.id == item_id
        ).first()
        if not item:
            return None
        for key, value in data.items():
            if hasattr(item, key):
                setattr(item, key, value)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_active_count_session(self, branch_id: int) -> Optional[InventoryCountSession]:
        """Sesión en progreso para una sucursal."""
        return (
            self.db.query(InventoryCountSession)
            .filter(
                InventoryCountSession.branch_id == branch_id,
                InventoryCountSession.status == "in_progress",
            )
            .first()
        )

    def get_pending_count_sessions(self) -> List[InventoryCountSession]:
        """Sesiones pendientes programadas para hoy o antes."""
        today_end = datetime.utcnow().replace(hour=23, minute=59, second=59)
        return (
            self.db.query(InventoryCountSession)
            .filter(
                InventoryCountSession.status == "pending",
                InventoryCountSession.scheduled_date <= today_end,
            )
            .order_by(InventoryCountSession.scheduled_date)
            .all()
        )

    def get_overdue_count_sessions(self) -> List[InventoryCountSession]:
        """Sesiones pendientes con fecha programada vencida."""
        now = datetime.utcnow()
        return (
            self.db.query(InventoryCountSession)
            .filter(
                InventoryCountSession.status == "pending",
                InventoryCountSession.scheduled_date < now,
            )
            .order_by(InventoryCountSession.scheduled_date)
            .all()
        )

    def populate_count_items_for_session(self, session_id: int, branch_id: int) -> int:
        """Pre-poblar items de conteo con inventario activo de la sucursal."""
        existing = {
            i.inventory_id
            for i in self.get_count_items(session_id)
            if i.inventory_id is not None
        }
        items = self.get_all(limit=10000, branch_id=branch_id)
        added = 0
        for inv in items:
            if inv.id in existing:
                continue
            self.add_count_item(session_id, {
                "inventory_id": inv.id,
                "product_id": inv.product_id,
                "expected_physical": inv.physical_stock,
            })
            added += 1
        return added

    # ------------------------------------------------------------------
    # Lotes y fechas de caducidad
    # ------------------------------------------------------------------

    def add_batch(self, inventory_id: int, batch_data: dict) -> InventoryBatch:
        """Agregar lote a un item de inventario."""
        batch_data["inventory_id"] = inventory_id
        batch = InventoryBatch(**batch_data)
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)
        return batch

    def get_batches_by_inventory(self, inventory_id: int) -> List[InventoryBatch]:
        """Lotes de un item."""
        return (
            self.db.query(InventoryBatch)
            .filter(InventoryBatch.inventory_id == inventory_id)
            .order_by(InventoryBatch.expiration_date.asc().nullslast())
            .all()
        )

    def get_batch_by_id(self, batch_id: int) -> Optional[InventoryBatch]:
        """Obtener lote por ID."""
        return self.db.query(InventoryBatch).filter(InventoryBatch.id == batch_id).first()

    def get_batch_by_number(
        self, inventory_id: int, batch_number: str
    ) -> Optional[InventoryBatch]:
        """Buscar lote por número."""
        return (
            self.db.query(InventoryBatch)
            .filter(
                InventoryBatch.inventory_id == inventory_id,
                InventoryBatch.batch_number == batch_number,
            )
            .first()
        )

    def get_batches_near_expiration(
        self, branch_id: int = None, days: int = 30
    ) -> List[InventoryBatch]:
        """Lotes próximos a vencer."""
        cutoff = date.today() + timedelta(days=days)
        query = (
            self.db.query(InventoryBatch)
            .join(Inventory, InventoryBatch.inventory_id == Inventory.id)
            .filter(
                Inventory.is_active == True,
                InventoryBatch.expiration_date.isnot(None),
                InventoryBatch.expiration_date <= cutoff,
                InventoryBatch.quantity > 0,
            )
        )
        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)
        return query.order_by(InventoryBatch.expiration_date).all()

    def consume_from_batch(self, batch_id: int, quantity: int) -> Optional[InventoryBatch]:
        """Consumir cantidad de un lote (FIFO)."""
        batch = self.get_batch_by_id(batch_id)
        if not batch or batch.quantity < quantity:
            return None
        batch.quantity -= quantity
        self.db.commit()
        self.db.refresh(batch)
        return batch

    def update_batch(self, batch_id: int, data: dict) -> Optional[InventoryBatch]:
        """Actualizar lote."""
        batch = self.get_batch_by_id(batch_id)
        if not batch:
            return None
        for key, value in data.items():
            if hasattr(batch, key):
                setattr(batch, key, value)
        self.db.commit()
        self.db.refresh(batch)
        return batch

    def inventory_has_batches(self, inventory_id: int) -> bool:
        """True si el item tiene al menos un lote."""
        return (
            self.db.query(InventoryBatch)
            .filter(InventoryBatch.inventory_id == inventory_id)
            .count() > 0
        )

    # ------------------------------------------------------------------
    # Ubicación jerárquica
    # ------------------------------------------------------------------

    def get_by_hierarchical_location(
        self,
        branch_id: int,
        aisle: str = None,
        shelf: str = None,
        level: str = None,
        bin: str = None,
    ) -> List[Inventory]:
        """Buscar items por componentes de ubicación jerárquica."""
        query = (
            self.db.query(Inventory)
            .join(Product)
            .join(Branch)
            .filter(
                Inventory.branch_id == branch_id,
                Inventory.is_active == True,
                Product.is_active == True,
                Branch.is_active == True,
            )
        )
        if aisle:
            query = query.filter(Inventory.aisle == aisle)
        if shelf:
            query = query.filter(Inventory.shelf == shelf)
        if level:
            query = query.filter(Inventory.level == level)
        if bin:
            query = query.filter(Inventory.bin == bin)
        return query.all()

    def get_all_aisles_in_branch(self, branch_id: int) -> List[str]:
        """Lista de pasillos únicos en una sucursal."""
        results = (
            self.db.query(Inventory.aisle)
            .filter(
                Inventory.branch_id == branch_id,
                Inventory.is_active == True,
                Inventory.aisle.isnot(None),
                Inventory.aisle != "",
            )
            .distinct()
            .all()
        )
        return sorted(r[0] for r in results if r[0])

    def get_items_in_aisle(self, branch_id: int, aisle: str) -> List[Inventory]:
        """Items en un pasillo."""
        return self.get_by_hierarchical_location(branch_id, aisle=aisle)

    def get_location_summary(self, branch_id: int) -> List[Dict[str, Any]]:
        """Resumen de distribución por pasillo."""
        results = (
            self.db.query(
                Inventory.aisle,
                func.count(Inventory.id).label("item_count"),
            )
            .filter(
                Inventory.branch_id == branch_id,
                Inventory.is_active == True,
            )
            .group_by(Inventory.aisle)
            .all()
        )
        return [
            {
                "aisle": r.aisle or "(sin pasillo)",
                "item_count": r.item_count,
            }
            for r in results
        ]

    def search_by_location_text(self, branch_id: int, query_text: str) -> List[Inventory]:
        """Buscar por cualquier parte de la ubicación (libre o jerárquica)."""
        pattern = f"%{query_text}%"
        return (
            self.db.query(Inventory)
            .join(Product)
            .join(Branch)
            .filter(
                Inventory.branch_id == branch_id,
                Inventory.is_active == True,
                Product.is_active == True,
                Branch.is_active == True,
                or_(
                    Inventory.location_free.ilike(pattern),
                    Inventory.aisle.ilike(pattern),
                    Inventory.shelf.ilike(pattern),
                    Inventory.level.ilike(pattern),
                    Inventory.bin.ilike(pattern),
                ),
            )
            .all()
        )

    def get_valuation_by_category(self, branch_id: int) -> List[Dict[str, Any]]:
        """Valor de inventario agrupado por categoría de producto."""
        from models.category import Category
        results = (
            self.db.query(
                Category.id,
                Category.name,
                func.sum(Inventory.digital_stock * Inventory.unit_cost).label("total_value"),
                func.count(Inventory.id).label("item_count"),
            )
            .join(Product, Inventory.product_id == Product.id)
            .outerjoin(Category, Product.category_id == Category.id)
            .filter(
                Inventory.branch_id == branch_id,
                Inventory.is_active == True,
                Product.is_active == True,
                Inventory.unit_cost.isnot(None),
            )
            .group_by(Category.id, Category.name)
            .all()
        )
        return [
            {
                "category_id": r.id,
                "category_name": r.name or "(sin categoría)",
                "total_value": float(r.total_value or 0),
                "item_count": r.item_count,
            }
            for r in results
        ]
