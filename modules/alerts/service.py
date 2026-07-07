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
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.sql import func
from core.database import Base
from datetime import datetime, timezone
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
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            # Expansions
            "resolution_notes": self.resolution_notes,
            "assigned_to": self.assigned_to,
            "priority": self.priority,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "is_expired_flag": self.is_expired_flag,
        }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class AlertService:
    """Service for alert management (all expansions)."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ #
    # Core CRUD                                                           #
    # ------------------------------------------------------------------ #

    def create_alert(self, alert_type: str, severity: str, title: str,
                     message: str, product_id: int = None,
                     branch_id: int = None, movement_id: int = None,
                     priority: str = "normal", due_date: datetime = None,
                     assigned_to: int = None) -> Dict[str, Any]:
        """Create a new alert."""
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
        )
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        logger.info(f"Alert created: {title}")
        return alert.to_dict()

    def get_open_alert(self, alert_type: str, product_id: int = None,
                       branch_id: int = None,
                       movement_id: int = None) -> Optional[Dict[str, Any]]:
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
        """Count unread alerts."""
        return self.db.query(Alert).filter(Alert.is_read == False).count()

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
