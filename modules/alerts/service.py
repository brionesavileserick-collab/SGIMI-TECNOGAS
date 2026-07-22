"""
Alerts service layer - Detects issues and generates alerts.

Expansions implemented:
  Exp 1  – Nombres legibles (enrich_alert, get_product_name, get_branch_name)
  Exp 2  – Notificaciones visuales (get_unread_alerts_for_user)
  Exp 3  – Acciones desde la alerta (get_alert_with_actions)
  Exp 4  – Filtro por sucursal (list_alerts acepta branch_id)
  Exp 5  – Filtro por fecha (list_alerts acepta date_from, date_to)
  Exp 6  – Alerta manual (create_manual_alert)
  Exp 7  – Notas de resolución (campo resolution_notes, resolve_alert_with_notes,
            get_resolved_with_notes)
  Exp 8  – Historial de resueltas (list_resolved_alerts, get_alert_statistics)
  Exp 9  – Asignación (campo assigned_to, assign_alert, unassign_alert,
            get_alerts_by_assignee)
  Exp 10 – Prioridad y expiración (campos priority, due_date, is_expired_flag;
            set_priority, set_due_date, get_overdue_alerts, escalate_alert,
            mark_expired_alerts)
"""

from typing import List, Dict, Any, Optional
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, inspect, text
from sqlalchemy.sql import func
from core.database import Base
from datetime import datetime, timezone, timedelta, date
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class Alert(Base):
    """Alert model – stores every generated alert with all expansion fields."""

    __tablename__ = "alerts"

    # ------------------------------------------------------------------
    # Original fields
    # ------------------------------------------------------------------
    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False)          # info | warning | critical
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    product_id = Column(Integer, nullable=True)
    branch_id = Column(Integer, nullable=True)
    movement_id = Column(Integer, nullable=True)
    is_read = Column(Boolean, default=False)
    is_resolved = Column(Boolean, default=False)
    group_key = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # ------------------------------------------------------------------
    # Exp 7 – Notas de resolución
    # ------------------------------------------------------------------
    resolution_notes = Column(Text, nullable=True)

    # ------------------------------------------------------------------
    # Exp 9 – Asignación a usuario
    # ------------------------------------------------------------------
    assigned_to = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ------------------------------------------------------------------
    # Exp 10 – Prioridad y expiración
    # ------------------------------------------------------------------
    priority = Column(String(20), nullable=False, default="normal")  # low | normal | high
    due_date = Column(DateTime(timezone=True), nullable=True)
    is_expired_flag = Column(Boolean, default=False)

    # ------------------------------------------------------------------
    # Suppression system
    # ------------------------------------------------------------------
    suppressed_until = Column(DateTime(timezone=True), nullable=True, index=True)
    suppression_reason = Column(Text, nullable=True)

    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary (all fields, new ones included)."""
        return {
            # Original
            "id": self.id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "product_id": self.product_id,
            "branch_id": self.branch_id,
            "movement_id": self.movement_id,
            "is_read": self.is_read,
            "is_resolved": self.is_resolved,
            "group_key": self.group_key,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            # Expansions
            "resolution_notes": self.resolution_notes,
            "assigned_to": self.assigned_to,
            "priority": self.priority,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "is_expired_flag": self.is_expired_flag,
            "suppressed_until": self.suppressed_until.isoformat() if self.suppressed_until else None,
            "suppression_reason": self.suppression_reason,
        }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class AlertService:
    """Service for alert management (all expansions)."""

    _ALERT_TEMPLATES: Dict[str, Dict[str, str]] = {
        "low_stock": {
            "title": "Stock Bajo Detectado",
            "message": "El stock actual ({current}) ha caído por debajo del mínimo ({min})",
        },
        "discrepancy": {
            "title": "Discrepancia de Inventario Detectada",
            "message": "Diferencia detectada: Físico={physical}, Digital={digital}, Diferencia={diff}",
        },
        "count_overdue": {
            "title": "Conteo de Inventario Vencido",
            "message": "La sucursal {branch} tiene un conteo pendiente desde {date}",
        },
        "count_due_soon": {
            "title": "Conteo de Inventario Próximo a Vencer",
            "message": "El conteo programado para {date} vence en {days} día(s)",
        },
        "approval_pending_admin": {
            "title": "Transferencia Pendiente de Aprobación (Admin)",
            "message": "Transferencia #{movement_id} de {product_name} requiere aprobación de Admin",
        },
        "approval_pending_manager": {
            "title": "Transferencia Pendiente de Aprobación (Gerente)",
            "message": "Transferencia #{movement_id} de {product_name} requiere aprobación de Gerente",
        },
        "capacity_warning": {
            "title": "Capacidad de Sucursal WARNING",
            "message": "{branch} tiene {current_skus} SKUs de {max_products} ({usage_percent}%)",
        },
        "capacity_critical": {
            "title": "Capacidad de Sucursal CRITICAL",
            "message": "{branch} tiene {current_skus} SKUs de {max_products} ({usage_percent}%)",
        },
        "capacity_exceeded": {
            "title": "Capacidad de Sucursal EXCEEDED",
            "message": "{branch} supera la capacidad máxima con {current_skus} SKUs de {max_products} ({usage_percent}%)",
        },
        "batch_expiring_urgent": {
            "title": "Lote Próximo a Vencer",
            "message": "El lote {batch_number} de {product_name} vence el {expiration_date} (en {days_until_expiry} días)",
        },
        "batch_expiring_warning": {
            "title": "Lote Próximo a Vencer",
            "message": "El lote {batch_number} de {product_name} vence el {expiration_date} (en {days_until_expiry} días)",
        },
    }

    _AUTO_RESOLVE_RULES: Dict[str, Dict[str, Any]] = {
        "low_stock": {
            "condition": "stock_recovered",
            "check": lambda data: (data or {}).get("digital_stock", 0) > (data or {}).get("min_stock", 0),
        },
        "discrepancy": {
            "condition": "discrepancy_resolved",
            "check": lambda data: not (data or {}).get("has_discrepancy", False),
        },
        "count_overdue": {
            "condition": "count_completed",
            "check": lambda data: bool((data or {}).get("session_completed") or (data or {}).get("completed")),
        },
        "approval_pending_admin": {
            "condition": "approval_resolved",
            "check": lambda data: bool((data or {}).get("approved") or (data or {}).get("rejected") or (data or {}).get("resolved")),
        },
        "approval_pending_manager": {
            "condition": "approval_resolved",
            "check": lambda data: bool((data or {}).get("approved") or (data or {}).get("rejected") or (data or {}).get("resolved")),
        },
    }

    def __init__(self, db: Session):
        self.db = db
        self._ensure_alert_schema()

    def _ensure_alert_schema(self):
        """Ensure the alerts table has the optional group_key column, unique index, and suppression fields."""
        if not self.db or not self.db.bind:
            return
        try:
            inspector = inspect(self.db.bind)
            if not inspector.has_table("alerts"):
                return
            columns = {col["name"] for col in inspector.get_columns("alerts")}
            if "group_key" not in columns:
                self.db.execute(text("ALTER TABLE alerts ADD COLUMN group_key VARCHAR(100)"))
                logger.info("Added group_key column to alerts table")

            # Add suppression fields
            if "suppressed_until" not in columns:
                self.db.execute(text("ALTER TABLE alerts ADD COLUMN suppressed_until DATETIME"))
                logger.info("Added suppressed_until column to alerts table")
            if "suppression_reason" not in columns:
                self.db.execute(text("ALTER TABLE alerts ADD COLUMN suppression_reason TEXT"))
                logger.info("Added suppression_reason column to alerts table")

            # Add unique index for preventing duplicate active alerts
            indexes = {idx["name"] for idx in inspector.get_indexes("alerts")}
            if "idx_unique_active_alert" not in indexes:
                # SQLite doesn't support partial indexes with WHERE, so we create a regular unique index
                # The application logic already handles the is_resolved check
                self.db.execute(text("""
                    CREATE UNIQUE INDEX idx_unique_active_alert
                    ON alerts(alert_type, product_id, branch_id, movement_id)
                """))
                logger.info("Added unique index for active alerts")
            self.db.commit()
        except Exception as exc:
            logger.warning(f"Could not ensure alerts schema: {exc}")

    # ------------------------------------------------------------------ #
    # Core CRUD                                                           #
    # ------------------------------------------------------------------ #

    def create_alert(self, alert_type: str, severity: str, title: str,
                     message: str, product_id: int = None,
                     branch_id: int = None, movement_id: int = None,
                     priority: str = "normal", due_date: datetime = None,
                     assigned_to: int = None,
                     group_key: Optional[str] = None) -> Dict[str, Any]:
        """Create a new alert with reference validation."""
        # Validate product_id exists and is active
        if product_id is not None:
            from models.product import Product
            product = self.db.query(Product).filter(Product.id == product_id).first()
            if not product:
                raise ValueError(f"Product with id {product_id} does not exist")
            if not product.is_active:
                raise ValueError(f"Product with id {product_id} is not active")

        # Validate branch_id exists and is active
        if branch_id is not None:
            from models.branch import Branch
            branch = self.db.query(Branch).filter(Branch.id == branch_id).first()
            if not branch:
                raise ValueError(f"Branch with id {branch_id} does not exist")
            if not branch.is_active:
                raise ValueError(f"Branch with id {branch_id} is not active")

        # Validate movement_id exists
        if movement_id is not None:
            from models.movement import Movement
            movement = self.db.query(Movement).filter(Movement.id == movement_id).first()
            if not movement:
                raise ValueError(f"Movement with id {movement_id} does not exist")

        alert = Alert(
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            product_id=product_id,
            branch_id=branch_id,
            movement_id=movement_id,
            priority=priority,
            due_date=due_date,
            assigned_to=assigned_to,
            group_key=group_key,
        )
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        logger.info(f"Alert created: {title}")
        return alert.to_dict()

    def get_template(self, alert_type: str, **kwargs) -> Dict[str, str]:
        """Return a formatted template for a supported alert type."""
        template = self._ALERT_TEMPLATES.get(alert_type)
        if not template:
            return {"title": kwargs.get("title", ""), "message": kwargs.get("message", "")}
        values = defaultdict(str, kwargs)
        return {
            "title": template.get("title", "").format_map(values),
            "message": template.get("message", "").format_map(values),
        }

    def _build_message(self, alert_type: str, data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, str]:
        """Build title/message for an alert using templates when available."""
        payload = dict(data or {})
        payload.update(kwargs)
        template = self.get_template(alert_type, **payload)
        if template.get("title") or template.get("message"):
            return template
        return {
            "title": payload.get("title", ""),
            "message": payload.get("message", ""),
        }

    def add_custom_template(self, alert_type: str, title: str, message: str) -> bool:
        """Add or update a custom alert template."""
        self._ALERT_TEMPLATES[alert_type] = {
            "title": title,
            "message": message,
        }
        logger.info(f"Added custom template for alert type: {alert_type}")
        return True

    def get_available_templates(self) -> Dict[str, Dict[str, str]]:
        """Get all available alert templates."""
        return self._ALERT_TEMPLATES.copy()

    def remove_template(self, alert_type: str) -> bool:
        """Remove a custom template (only if it's not a core template)."""
        core_templates = {
            "low_stock", "discrepancy", "stock_critical", "transfer_rejected",
            "transfer_pending", "count_overdue", "count_due_soon",
            "approval_pending_admin", "approval_pending_manager",
            "capacity_warning", "capacity_critical", "capacity_exceeded",
            "batch_expiring_urgent", "batch_expiring_warning",
        }
        if alert_type in core_templates:
            logger.warning(f"Cannot remove core template: {alert_type}")
            return False
        if alert_type in self._ALERT_TEMPLATES:
            del self._ALERT_TEMPLATES[alert_type]
            logger.info(f"Removed custom template: {alert_type}")
            return True
        return False

    def create_count_overdue_alert(self, branch_id: int, scheduled_date: Any, session_id: int = None) -> Optional[Dict[str, Any]]:
        """Create a count-overdue or due-soon alert when a scheduled count is stale."""
        if scheduled_date is None:
            return None
        if isinstance(scheduled_date, str):
            try:
                scheduled_date = datetime.fromisoformat(scheduled_date.replace("Z", "+00:00"))
            except ValueError:
                try:
                    scheduled_date = datetime.combine(date.fromisoformat(scheduled_date), datetime.min.time(), tzinfo=timezone.utc)
                except ValueError:
                    return None
        if isinstance(scheduled_date, date) and not isinstance(scheduled_date, datetime):
            due_date = datetime.combine(scheduled_date, datetime.min.time(), tzinfo=timezone.utc)
        else:
            due_date = scheduled_date
            if getattr(due_date, "tzinfo", None) is None:
                due_date = due_date.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        if due_date < now:
            days_late = (now.date() - due_date.date()).days
            alert_type = "count_overdue"
            severity = "critical" if days_late > 3 else "warning"
            title = "Conteo de Inventario Vencido"
            message = f"La sucursal {self.get_branch_name(branch_id)} tiene un conteo programado desde {due_date.date().isoformat()}"
            group_key = f"count_overdue_{branch_id}_{session_id or 'default'}"
        else:
            days_until = (due_date.date() - now.date()).days
            if days_until > 3:
                return None
            alert_type = "count_due_soon"
            severity = "info"
            title = "Conteo de Inventario Próximo a Vencer"
            message = f"El conteo programado para {due_date.date().isoformat()} vence en {days_until} día(s)"
            group_key = f"count_due_soon_{branch_id}_{session_id or 'default'}"

        return self.create_alert(
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            branch_id=branch_id,
            movement_id=session_id,
            priority="high" if alert_type == "count_overdue" else "normal",
            due_date=due_date,
            group_key=group_key,
        )

    def create_approval_pending_alert(self, movement_id: int, branch_id: int, approval_level: str, product_name: str) -> Dict[str, Any]:
        """Create an alert for a transfer waiting for approval."""
        approval_level = (approval_level or "admin").lower()
        if approval_level == "manager":
            alert_type = "approval_pending_manager"
            title = "Transferencia Pendiente de Aprobación (Gerente)"
            message = f"Transferencia #{movement_id} de {product_name} requiere aprobación de Gerente"
        else:
            alert_type = "approval_pending_admin"
            title = "Transferencia Pendiente de Aprobación (Admin)"
            message = f"Transferencia #{movement_id} de {product_name} requiere aprobación de Admin"
        return self.create_alert(
            alert_type=alert_type,
            severity="warning",
            title=title,
            message=message,
            branch_id=branch_id,
            movement_id=movement_id,
            group_key=f"approval_pending_{approval_level}_{movement_id}",
        )

    def create_capacity_alert(self, branch_id: int, current_skus: int, max_products: int, usage_percent: float) -> Dict[str, Any]:
        """Create a branch-capacity alert based on usage percentage."""
        branch_name = self.get_branch_name(branch_id)
        if usage_percent >= 100:
            alert_type = "capacity_exceeded"
            severity = "critical"
        elif usage_percent > 90:
            alert_type = "capacity_critical"
            severity = "critical"
        elif usage_percent >= 70:
            alert_type = "capacity_warning"
            severity = "warning"
        else:
            return None
        message = f"{branch_name} tiene {current_skus} SKUs de {max_products} ({usage_percent:.0f}%)"
        return self.create_alert(
            alert_type=alert_type,
            severity=severity,
            title=f"Capacidad de Sucursal {'CRITICAL' if alert_type != 'capacity_warning' else 'WARNING'}",
            message=message,
            branch_id=branch_id,
            group_key=f"capacity_{branch_id}",
        )

    def create_batch_expiring_alert(self, batch_id: int, branch_id: int, product_name: str, expiration_date: Any, days_until_expiry: int) -> Dict[str, Any]:
        """Create a batch-expiring alert for urgent or warning thresholds."""
        if expiration_date is None:
            return None
        if isinstance(expiration_date, str):
            try:
                expiration_date = datetime.fromisoformat(expiration_date.replace("Z", "+00:00"))
            except ValueError:
                try:
                    expiration_date = datetime.combine(date.fromisoformat(expiration_date), datetime.min.time(), tzinfo=timezone.utc)
                except ValueError:
                    return None
        if isinstance(expiration_date, date) and not isinstance(expiration_date, datetime):
            expiry_date = datetime.combine(expiration_date, datetime.min.time(), tzinfo=timezone.utc)
        else:
            expiry_date = expiration_date
            if getattr(expiry_date, "tzinfo", None) is None:
                expiry_date = expiry_date.replace(tzinfo=timezone.utc)
        if days_until_expiry <= 7:
            alert_type = "batch_expiring_urgent"
            severity = "critical"
        elif days_until_expiry <= 30:
            alert_type = "batch_expiring_warning"
            severity = "warning"
        else:
            return None
        return self.create_alert(
            alert_type=alert_type,
            severity=severity,
            title="Lote Próximo a Vencer",
            message=f"El lote {batch_id} de {product_name} vence el {expiry_date.date().isoformat()} (en {days_until_expiry} días)",
            branch_id=branch_id,
            product_id=None,
            group_key=f"batch_expiring_{branch_id}_{batch_id}",
        )

    def get_alert_group(self, group_key: str) -> List[Dict[str, Any]]:
        """Return alerts grouped under a common key."""
        alerts = (
            self.db.query(Alert)
            .filter(Alert.group_key == group_key)
            .order_by(Alert.created_at.desc())
            .all()
        )
        return [self.enrich_alert(a.to_dict()) for a in alerts]

    def get_alert_group_summary(self, group_key: str) -> Dict[str, Any]:
        """Return a lightweight summary for alerts sharing a group key."""
        alerts = self.get_alert_group(group_key)
        severities = {}
        for alert in alerts:
            severities[alert.get("severity", "info")] = severities.get(alert.get("severity", "info"), 0) + 1
        return {
            "count": len(alerts),
            "severities": severities,
            "oldest": alerts[-1] if alerts else None,
            "newest": alerts[0] if alerts else None,
        }

    def check_and_resolve(self, alert_type: str, product_id: int = None,
                          branch_id: int = None,
                          movement_id: int = None,
                          context_data: Optional[Dict[str, Any]] = None) -> bool:
        """Resolve an open alert when an auto-resolve rule is satisfied."""
        rule = self._AUTO_RESOLVE_RULES.get(alert_type)
        if not rule and alert_type.startswith("approval_pending_"):
            rule = self._AUTO_RESOLVE_RULES.get("approval_pending_admin")
        if not rule:
            return False
        if not rule.get("check", lambda data: False)(context_data or {}):
            return False
        return self.resolve_open_alert(alert_type, product_id=product_id, branch_id=branch_id, movement_id=movement_id)

    def get_open_alert(self, alert_type: str, product_id: int = None,
                       branch_id: int = None,
                       movement_id: int = None,
                       group_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get an existing unresolved alert for the same operational condition."""
        query = self.db.query(Alert).filter(
            Alert.alert_type == alert_type,
            Alert.is_resolved == False,
        )
        
        if product_id is None:
            query = query.filter(Alert.product_id.is_(None))
        else:
            query = query.filter(Alert.product_id == product_id)

        if branch_id is None:
            query = query.filter(Alert.branch_id.is_(None))
        else:
            query = query.filter(Alert.branch_id == branch_id)

        if movement_id is None:
            query = query.filter(Alert.movement_id.is_(None))
        else:
            query = query.filter(Alert.movement_id == movement_id)

        if group_key is not None:
            query = query.filter(Alert.group_key == group_key)

        alert = query.order_by(Alert.created_at.desc()).first()
        return alert.to_dict() if alert else None

    def get_alert(self, alert_id: int) -> Optional[Dict[str, Any]]:
        """Get alert by ID."""
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        return alert.to_dict() if alert else None

    def list_alerts(self, skip: int = 0, limit: int = 100,
                    is_unread_only: bool = False,
                    severity: str = None,
                    alert_type: str = None,
                    branch_id: int = None,          # Exp 4
                    date_from: datetime = None,     # Exp 5
                    date_to: datetime = None) -> List[Dict[str, Any]]:    # Exp 5
        """List alerts with optional filtering (Exp 4 + 5 added)."""
        query = self.db.query(Alert)

        if is_unread_only:
            query = query.filter(Alert.is_read == False)
        if severity:
            query = query.filter(Alert.severity == severity)
        if alert_type:
            query = query.filter(Alert.alert_type == alert_type)
        # Exp 4 – filtro por sucursal
        if branch_id is not None:
            query = query.filter(Alert.branch_id == branch_id)
        # Exp 5 – filtro por fecha
        if date_from:
            query = query.filter(Alert.created_at >= date_from)
        if date_to:
            query = query.filter(Alert.created_at <= date_to)

        alerts = query.order_by(Alert.created_at.desc()).offset(skip).limit(limit).all()
        return [a.to_dict() for a in alerts]

    def mark_as_read(self, alert_id: int) -> bool:
        """Mark alert as read."""
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return False
        alert.is_read = True
        self.db.commit()
        return True

    def resolve_alert(self, alert_id: int) -> bool:
        """Resolve alert (without notes)."""
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return False
        alert.is_resolved = True
        alert.resolved_at = datetime.now(timezone.utc)
        self.db.commit()
        return True

    def resolve_open_alert(self, alert_type: str, product_id: int = None,
                           branch_id: int = None,
                           movement_id: int = None) -> bool:
        """Resolve an existing unresolved alert for the same operational condition."""
        alert = self.get_open_alert(alert_type, product_id, branch_id, movement_id)
        if not alert:
            return False
        return self.resolve_alert(alert["id"])

    def delete_alert(self, alert_id: int) -> bool:
        """Delete alert."""
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return False
        self.db.delete(alert)
        self.db.commit()
        return True

    def get_unread_count(self) -> int:
        """Count unread alerts (only unresolved alerts)."""
        return self.db.query(Alert).filter(
            Alert.is_read == False,
            Alert.is_resolved == False,
        ).count()

    def get_critical_count(self) -> int:
        """Count critical unresolved alerts."""
        return self.db.query(Alert).filter(
            Alert.severity == "critical",
            Alert.is_resolved == False,
        ).count()

    def clear_old_alerts(self, days: int = 30) -> int:
        """Clear resolved alerts older than *days* days."""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        count = self.db.query(Alert).filter(
            Alert.is_resolved == True,
            Alert.created_at < cutoff,
        ).delete()
        self.db.commit()
        logger.info(f"Cleared {count} old alerts")
        return count

    # ------------------------------------------------------------------ #
    # Suppression system methods
    # ------------------------------------------------------------------ #

    def suppress_alert(self, alert_id: int, until: datetime, reason: str = None) -> bool:
        """Suppress an alert until a specific datetime."""
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return False
        alert.suppressed_until = until
        alert.suppression_reason = reason
        self.db.commit()
        logger.info(f"Alert {alert_id} suppressed until {until}")
        return True

    def unsuppress_alert(self, alert_id: int) -> bool:
        """Remove suppression from an alert."""
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return False
        alert.suppressed_until = None
        alert.suppression_reason = None
        self.db.commit()
        logger.info(f"Alert {alert_id} unsuppressed")
        return True

    def get_suppressed_alerts(self) -> List[Dict[str, Any]]:
        """Get all currently suppressed alerts."""
        now = datetime.now(timezone.utc)
        alerts = self.db.query(Alert).filter(
            Alert.suppressed_until.isnot(None),
            Alert.suppressed_until > now,
            Alert.is_resolved == False,
        ).all()
        return [a.to_dict() for a in alerts]

    def check_expired_suppressions(self) -> int:
        """Check and remove expired suppressions, returning count of reactivated alerts."""
        now = datetime.now(timezone.utc)
        alerts = self.db.query(Alert).filter(
            Alert.suppressed_until.isnot(None),
            Alert.suppressed_until <= now,
            Alert.is_resolved == False,
        ).all()
        count = len(alerts)
        for alert in alerts:
            alert.suppressed_until = None
            alert.suppression_reason = None
        if count > 0:
            self.db.commit()
            logger.info(f"Reactivated {count} alerts with expired suppressions")
        return count

    # ------------------------------------------------------------------ #
    # Snooze system with context
    # ------------------------------------------------------------------ #

    def snooze_alert(self, alert_id: int, until: datetime, context: str = None,
                    changed_by: str = None) -> bool:
        """Snooze an alert with context (reason for snoozing)."""
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return False

        old_suppressed = alert.suppressed_until
        alert.suppressed_until = until
        alert.suppression_reason = context

        # Log the change
        self._log_alert_change(
            alert_id=alert_id,
            field_name="suppressed_until",
            old_value=old_suppressed,
            new_value=until,
            changed_by=changed_by,
            change_reason=f"Snoozed: {context}" if context else "Snoozed"
        )

        self.db.commit()
        logger.info(f"Alert {alert_id} snoozed until {until} with context: {context}")
        return True

    def snooze_alert_for_duration(self, alert_id: int, minutes: int = 60,
                                 context: str = None, changed_by: str = None) -> bool:
        """Snooze an alert for a specific duration in minutes."""
        until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        return self.snooze_alert(alert_id, until, context, changed_by)

    def get_snoozed_alerts(self) -> List[Dict[str, Any]]:
        """Get all currently snoozed alerts (same as suppressed, with context)."""
        return self.get_suppressed_alerts()

    # ------------------------------------------------------------------ #
    # Auto-resolution based on conditions
    # ------------------------------------------------------------------ #

    def check_and_auto_resolve_alerts(self) -> int:
        """Check active alerts and resolve those whose conditions are no longer met."""
        resolved_count = 0

        # Check low_stock alerts
        low_stock_alerts = self.db.query(Alert).filter(
            Alert.alert_type == "low_stock",
            Alert.is_resolved == False,
            Alert.product_id.isnot(None),
            Alert.branch_id.isnot(None),
        ).all()

        for alert in low_stock_alerts:
            from models.inventory import Inventory
            inventory = self.db.query(Inventory).filter(
                Inventory.product_id == alert.product_id,
                Inventory.branch_id == alert.branch_id,
            ).first()
            if inventory and inventory.physical_stock >= (inventory.min_stock or 0):
                alert.is_resolved = True
                alert.resolved_at = datetime.now(timezone.utc)
                resolved_count += 1

        # Check discrepancy alerts
        discrepancy_alerts = self.db.query(Alert).filter(
            Alert.alert_type == "discrepancy",
            Alert.is_resolved == False,
            Alert.product_id.isnot(None),
            Alert.branch_id.isnot(None),
        ).all()

        for alert in discrepancy_alerts:
            from models.inventory import Inventory
            inventory = self.db.query(Inventory).filter(
                Inventory.product_id == alert.product_id,
                Inventory.branch_id == alert.branch_id,
            ).first()
            if inventory and inventory.physical_stock == inventory.digital_stock:
                alert.is_resolved = True
                alert.resolved_at = datetime.now(timezone.utc)
                resolved_count += 1

        if resolved_count > 0:
            self.db.commit()
            logger.info(f"Auto-resolved {resolved_count} alerts based on current conditions")
        return resolved_count

    # ------------------------------------------------------------------ #
    # Alert grouping system
    # ------------------------------------------------------------------ #

    def get_grouped_alerts(self, alert_type: str = None, branch_id: int = None) -> List[Dict[str, Any]]:
        """Get alerts grouped by type and branch for summary view."""
        query = self.db.query(Alert).filter(
            Alert.is_resolved == False,
            Alert.suppressed_until.is_(None),
        )

        if alert_type:
            query = query.filter(Alert.alert_type == alert_type)
        if branch_id:
            query = query.filter(Alert.branch_id == branch_id)

        alerts = query.all()

        # Group by (alert_type, branch_id)
        groups = {}
        for alert in alerts:
            key = (alert.alert_type, alert.branch_id)
            if key not in groups:
                groups[key] = {
                    "alert_type": alert.alert_type,
                    "branch_id": alert.branch_id,
                    "branch_name": self.get_branch_name(alert.branch_id),
                    "count": 0,
                    "severity": alert.severity,
                    "oldest_created": alert.created_at,
                    "alert_ids": [],
                }
            groups[key]["count"] += 1
            groups[key]["alert_ids"].append(alert.id)
            if alert.created_at < groups[key]["oldest_created"]:
                groups[key]["oldest_created"] = alert.created_at

        return list(groups.values())

    def get_alerts_for_group(self, alert_type: str, branch_id: int) -> List[Dict[str, Any]]:
        """Get all individual alerts for a specific group."""
        alerts = self.db.query(Alert).filter(
            Alert.alert_type == alert_type,
            Alert.branch_id == branch_id,
            Alert.is_resolved == False,
            Alert.suppressed_until.is_(None),
        ).all()
        return [a.to_dict() for a in alerts]

    # ------------------------------------------------------------------ #
    # Alert history tracking
    # ------------------------------------------------------------------ #

    def _log_alert_change(self, alert_id: int, field_name: str, old_value, new_value,
                         changed_by: str = None, change_reason: str = None):
        """Log a change to an alert for audit trail."""
        try:
            from models.alert_history import AlertHistory
            history = AlertHistory(
                alert_id=alert_id,
                field_name=field_name,
                old_value=str(old_value) if old_value is not None else None,
                new_value=str(new_value) if new_value is not None else None,
                changed_by=changed_by,
                change_reason=change_reason,
            )
            self.db.add(history)
            self.db.commit()
        except Exception as e:
            logger.warning(f"Could not log alert change: {e}")

    def log_alert_changes(self, alert_id: int, changes: Dict[str, tuple],
                         changed_by: str = None, change_reason: str = None):
        """Log multiple changes to an alert."""
        for field_name, (old_val, new_val) in changes.items():
            self._log_alert_change(alert_id, field_name, old_val, new_val, changed_by, change_reason)

    def get_alert_history(self, alert_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get change history for a specific alert."""
        from models.alert_history import AlertHistory
        history = self.db.query(AlertHistory).filter(
            AlertHistory.alert_id == alert_id
        ).order_by(AlertHistory.changed_at.desc()).limit(limit).all()
        return [h.to_dict() for h in history]

    # ------------------------------------------------------------------ #
    # Integrity validation job
    # ------------------------------------------------------------------ #

    def validate_alert_integrity(self) -> Dict[str, int]:
        """Validate alert integrity and fix orphaned alerts. Returns statistics."""
        stats = {
            "orphaned_product_alerts_resolved": 0,
            "orphaned_branch_alerts_resolved": 0,
            "orphaned_movement_alerts_resolved": 0,
            "total_fixed": 0,
        }

        # Check alerts with product_id that doesn't exist or is inactive
        from models.product import Product
        orphaned_product_alerts = self.db.query(Alert).filter(
            Alert.product_id.isnot(None),
            Alert.is_resolved == False
        ).all()

        for alert in orphaned_product_alerts:
            product = self.db.query(Product).filter(Product.id == alert.product_id).first()
            if not product or not product.is_active:
                alert.is_resolved = True
                alert.resolved_at = datetime.now(timezone.utc)
                stats["orphaned_product_alerts_resolved"] += 1
                stats["total_fixed"] += 1

        # Check alerts with branch_id that doesn't exist or is inactive
        from models.branch import Branch
        orphaned_branch_alerts = self.db.query(Alert).filter(
            Alert.branch_id.isnot(None),
            Alert.is_resolved == False
        ).all()

        for alert in orphaned_branch_alerts:
            branch = self.db.query(Branch).filter(Branch.id == alert.branch_id).first()
            if not branch or not branch.is_active:
                alert.is_resolved = True
                alert.resolved_at = datetime.now(timezone.utc)
                stats["orphaned_branch_alerts_resolved"] += 1
                stats["total_fixed"] += 1

        # Check alerts with movement_id that doesn't exist
        from models.movement import Movement
        orphaned_movement_alerts = self.db.query(Alert).filter(
            Alert.movement_id.isnot(None),
            Alert.is_resolved == False
        ).all()

        for alert in orphaned_movement_alerts:
            movement = self.db.query(Movement).filter(Movement.id == alert.movement_id).first()
            if not movement:
                alert.is_resolved = True
                alert.resolved_at = datetime.now(timezone.utc)
                stats["orphaned_movement_alerts_resolved"] += 1
                stats["total_fixed"] += 1

        if stats["total_fixed"] > 0:
            self.db.commit()
            logger.info(f"Integrity validation fixed {stats['total_fixed']} orphaned alerts: {stats}")

        return stats

    # ------------------------------------------------------------------ #
    # Exp 1 – Nombres legibles                                            #
    # ------------------------------------------------------------------ #

    def get_product_name(self, product_id: int) -> str:
        """Return the product name for a given ID, or a fallback string."""
        if product_id is None:
            return "—"
        try:
            from models.product import Product
            product = self.db.query(Product).filter(Product.id == product_id).first()
            return product.name if product else f"Producto #{product_id}"
        except Exception as e:
            logger.warning(f"Could not fetch product name for id={product_id}: {e}")
            return f"Producto #{product_id}"

    def get_branch_name(self, branch_id: int) -> str:
        """Return the branch name for a given ID, or a fallback string."""
        if branch_id is None:
            return "—"
        try:
            from models.branch import Branch
            branch = self.db.query(Branch).filter(Branch.id == branch_id).first()
            return branch.name if branch else f"Sucursal #{branch_id}"
        except Exception as e:
            logger.warning(f"Could not fetch branch name for id={branch_id}: {e}")
            return f"Sucursal #{branch_id}"

    def get_user_name(self, user_id: int) -> str:
        """Return the user name for a given ID, or a fallback string."""
        if user_id is None:
            return "—"
        try:
            from models.user import User
            user = self.db.query(User).filter(User.id == user_id).first()
            return user.name if user else f"Usuario #{user_id}"
        except Exception as e:
            logger.warning(f"Could not fetch user name for id={user_id}: {e}")
            return f"Usuario #{user_id}"

    def enrich_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """Add human-readable names to an alert dict (non-destructive copy)."""
        enriched = dict(alert)
        enriched["product_name"] = self.get_product_name(alert.get("product_id"))
        enriched["branch_name"] = self.get_branch_name(alert.get("branch_id"))
        enriched["assigned_to_name"] = self.get_user_name(alert.get("assigned_to"))
        return enriched

    # ------------------------------------------------------------------ #
    # Exp 2 – Notificaciones visuales                                     #
    # ------------------------------------------------------------------ #

    def get_unread_alerts_for_user(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Return unread, unresolved alerts ordered by severity (critical first)
        then by creation date.  Used to feed badges / toasts.
        """
        from sqlalchemy import case
        severity_order = case(
            (Alert.severity == "critical", 0),
            (Alert.severity == "warning", 1),
            else_=2,
        )
        alerts = (
            self.db.query(Alert)
            .filter(Alert.is_read == False, Alert.is_resolved == False)
            .order_by(severity_order, Alert.created_at.desc())
            .limit(limit)
            .all()
        )
        return [self.enrich_alert(a.to_dict()) for a in alerts]

    # ------------------------------------------------------------------ #
    # Exp 3 – Acciones desde la alerta                                    #
    # ------------------------------------------------------------------ #

    _ACTIONS_BY_TYPE: Dict[str, List[Dict[str, str]]] = {
        "low_stock": [
            {"label": "Crear Entrada", "action": "open_movement_entrada"},
            {"label": "Ver Inventario", "action": "open_inventory"},
        ],
        "discrepancy": [
            {"label": "Hacer Conteo", "action": "open_inventory_count"},
            {"label": "Ver Inventario", "action": "open_inventory"},
        ],
        "transfer_pending": [
            {"label": "Ver Transferencia", "action": "open_movement"},
        ],
        "validation_failed": [
            {"label": "Ver Movimiento", "action": "open_movement"},
        ],
        "manual": [],
    }

    def get_alert_with_actions(self, alert_id: int) -> Optional[Dict[str, Any]]:
        """Return an enriched alert dict that includes available quick-actions."""
        alert = self.get_alert(alert_id)
        if not alert:
            return None
        enriched = self.enrich_alert(alert)
        actions = list(self._ACTIONS_BY_TYPE.get(alert["alert_type"], []))
        enriched["available_actions"] = actions
        return enriched

    # ------------------------------------------------------------------ #
    # Exp 6 – Alerta manual                                               #
    # ------------------------------------------------------------------ #

    def create_manual_alert(self, title: str, message: str,
                            severity: str = "info",
                            branch_id: int = None,
                            priority: str = "normal") -> Dict[str, Any]:
        """Create a free-form manual alert (no product_id / movement_id)."""
        return self.create_alert(
            alert_type="manual",
            severity=severity,
            title=title,
            message=message,
            branch_id=branch_id,
            priority=priority,
        )

    # ------------------------------------------------------------------ #
    # Exp 7 – Notas de resolución                                         #
    # ------------------------------------------------------------------ #

    def resolve_alert_with_notes(self, alert_id: int, notes: str) -> bool:
        """Resolve alert and persist resolution notes."""
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return False
        alert.is_resolved = True
        alert.resolved_at = datetime.now(timezone.utc)
        alert.resolution_notes = notes.strip() if notes else None
        self.db.commit()
        return True

    def get_resolved_with_notes(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return resolved alerts that have resolution notes."""
        alerts = (
            self.db.query(Alert)
            .filter(
                Alert.is_resolved == True,
                Alert.resolution_notes.isnot(None),
            )
            .order_by(Alert.resolved_at.desc())
            .limit(limit)
            .all()
        )
        return [self.enrich_alert(a.to_dict()) for a in alerts]

    # ------------------------------------------------------------------ #
    # Exp 8 – Historial de resueltas                                      #
    # ------------------------------------------------------------------ #

    def list_resolved_alerts(self, skip: int = 0, limit: int = 100,
                             date_from: datetime = None,
                             date_to: datetime = None,
                             branch_id: int = None) -> List[Dict[str, Any]]:
        """List only resolved alerts with optional filters."""
        query = self.db.query(Alert).filter(Alert.is_resolved == True)
        if branch_id is not None:
            query = query.filter(Alert.branch_id == branch_id)
        if date_from:
            query = query.filter(Alert.created_at >= date_from)
        if date_to:
            query = query.filter(Alert.created_at <= date_to)
        alerts = query.order_by(Alert.resolved_at.desc()).offset(skip).limit(limit).all()
        return [self.enrich_alert(a.to_dict()) for a in alerts]

    def get_alert_statistics(self) -> Dict[str, Any]:
        """Return counts grouped by type and severity."""
        from sqlalchemy import func as sa_func

        type_counts: Dict[str, int] = {}
        for row in self.db.query(Alert.alert_type, sa_func.count(Alert.id)).group_by(Alert.alert_type).all():
            type_counts[row[0]] = row[1]

        severity_counts: Dict[str, int] = {}
        for row in self.db.query(Alert.severity, sa_func.count(Alert.id)).group_by(Alert.severity).all():
            severity_counts[row[0]] = row[1]

        return {
            "total": self.db.query(Alert).count(),
            "unresolved": self.db.query(Alert).filter(Alert.is_resolved == False).count(),
            "resolved": self.db.query(Alert).filter(Alert.is_resolved == True).count(),
            "unread": self.db.query(Alert).filter(Alert.is_read == False).count(),
            "by_type": type_counts,
            "by_severity": severity_counts,
        }

    # ------------------------------------------------------------------ #
    # Exp 9 – Asignación                                                  #
    # ------------------------------------------------------------------ #

    def assign_alert(self, alert_id: int, user_id: int) -> bool:
        """Assign alert to a user."""
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return False
        alert.assigned_to = user_id
        self.db.commit()
        return True

    def unassign_alert(self, alert_id: int) -> bool:
        """Remove assignment from an alert."""
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return False
        alert.assigned_to = None
        self.db.commit()
        return True

    def get_alerts_by_assignee(self, user_id: int,
                               include_resolved: bool = False) -> List[Dict[str, Any]]:
        """Return alerts assigned to a specific user."""
        query = self.db.query(Alert).filter(Alert.assigned_to == user_id)
        if not include_resolved:
            query = query.filter(Alert.is_resolved == False)
        alerts = query.order_by(Alert.created_at.desc()).all()
        return [self.enrich_alert(a.to_dict()) for a in alerts]

    # ------------------------------------------------------------------ #
    # Exp 10 – Prioridad y expiración                                     #
    # ------------------------------------------------------------------ #

    def set_priority(self, alert_id: int, priority: str) -> bool:
        """Set alert priority (low | normal | high)."""
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return False
        alert.priority = priority
        self.db.commit()
        return True

    def set_due_date(self, alert_id: int, due_date: datetime) -> bool:
        """Set the due date (deadline) for an alert."""
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return False
        alert.due_date = due_date
        self.db.commit()
        return True

    def get_overdue_alerts(self) -> List[Dict[str, Any]]:
        """Return unresolved alerts whose due_date has passed."""
        now = datetime.now(timezone.utc)
        alerts = (
            self.db.query(Alert)
            .filter(
                Alert.is_resolved == False,
                Alert.due_date.isnot(None),
                Alert.due_date < now,
            )
            .order_by(Alert.due_date.asc())
            .all()
        )
        return [self.enrich_alert(a.to_dict()) for a in alerts]

    def escalate_alert(self, alert_id: int) -> bool:
        """Escalate alert priority one step up (low→normal→high)."""
        alert = self.db.query(Alert).filter(Alert.id == alert_id).first()
        if not alert:
            return False
        ladder = {"low": "normal", "normal": "high", "high": "high"}
        alert.priority = ladder.get(alert.priority, "high")
        self.db.commit()
        return True

    def mark_expired_alerts(self) -> int:
        """
        Mark as is_expired_flag=True all unresolved alerts whose due_date has
        passed but are not yet flagged.  Called periodically by the timer in
        handlers.  Returns the number of alerts updated.
        """
        now = datetime.now(timezone.utc)
        count = (
            self.db.query(Alert)
            .filter(
                Alert.is_resolved == False,
                Alert.is_expired_flag == False,
                Alert.due_date.isnot(None),
                Alert.due_date < now,
            )
            .update({"is_expired_flag": True})
        )
        self.db.commit()
        if count:
            logger.info(f"Marked {count} alerts as expired")
        return count
