"""
Alerts GUI routes/controllers for PyQt6 interface.

Expansions implemented:
  Exp 1  – Nombres legibles en tabla (product_name, branch_name)
  Exp 2  – Badge de no leídas en header
  Exp 3  – Botones de acciones rápidas por tipo de alerta
  Exp 4  – Filtro por sucursal
  Exp 5  – Filtro por rango de fechas
  Exp 6  – Botón "Crear Alerta Manual" con diálogo
  Exp 7  – Diálogo de notas al resolver
  Exp 8  – Tab "Historial de Resueltas"
  Exp 9  – Selector de asignación + filtro "Mis Alertas"
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QLabel, QComboBox, QMessageBox, QDialog,
    QFormLayout, QLineEdit, QTextEdit, QDialogButtonBox, QTabWidget,
    QDateEdit, QCheckBox, QSizePolicy, QFrame,
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont, QColor
from modules.alerts.service import AlertService
from config import ALERT_SEVERITIES, ALERT_PRIORITIES
import logging

_ALERT_TYPE_LABELS = {
    "low_stock": "Stock bajo",
    "discrepancy": "Discrepancia detectada",
    "validation_failed": "Validación fallida",
    "transfer_pending": "Transferencia pendiente",
    "count_overdue": "Conteo vencido",
    "count_due_soon": "Conteo próximo a vencer",
    "approval_pending_admin": "Aprobación pendiente (Admin)",
    "approval_pending_manager": "Aprobación pendiente (Gerente)",
    "capacity_warning": "Capacidad de sucursal (warning)",
    "capacity_critical": "Capacidad de sucursal (critical)",
    "capacity_exceeded": "Capacidad de sucursal (excedida)",
    "batch_expiring_urgent": "Lote por vencer (urgente)",
    "batch_expiring_warning": "Lote por vencer (warning)",
    "manual": "Alerta manual",
}

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: severity → row background color
# ---------------------------------------------------------------------------
_SEVERITY_COLORS = {
    "critical": QColor(255, 220, 220),   # light red
    "warning":  QColor(255, 245, 200),   # light yellow
    "info":     QColor(220, 240, 255),   # light blue
}


# ---------------------------------------------------------------------------
# Exp 6 – Diálogo: Crear Alerta Manual
# ---------------------------------------------------------------------------
class ManualAlertDialog(QDialog):
    """Dialog for creating a free-form manual alert."""

    def __init__(self, service: AlertService, parent=None):
        super().__init__(parent)
        self.service = service
        self.setWindowTitle("Crear Alerta Manual")
        self.setMinimumWidth(420)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Título de la alerta…")
        form.addRow("Título *:", self.title_edit)

        self.message_edit = QTextEdit()
        self.message_edit.setMaximumHeight(90)
        self.message_edit.setPlaceholderText("Descripción de la alerta…")
        form.addRow("Mensaje *:", self.message_edit)

        self.severity_combo = QComboBox()
        for key, label in ALERT_SEVERITIES.items():
            self.severity_combo.addItem(label, key)
        form.addRow("Severidad:", self.severity_combo)

        self.priority_combo = QComboBox()
        for key, label in ALERT_PRIORITIES.items():
            self.priority_combo.addItem(label, key)
        form.addRow("Prioridad:", self.priority_combo)

        self.branch_combo = QComboBox()
        self.branch_combo.addItem("Ninguna", None)
        self._load_branches()
        form.addRow("Sucursal:", self.branch_combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_branches(self):
        try:
            from models.branch import Branch
            branches = self.service.db.query(Branch).filter(Branch.is_active == True).all()
            for b in branches:
                self.branch_combo.addItem(b.name, b.id)
        except Exception as e:
            logger.warning(f"Could not load branches for dialog: {e}")

    def _accept(self):
        title = self.title_edit.text().strip()
        message = self.message_edit.toPlainText().strip()
        if not title or not message:
            QMessageBox.warning(self, "Campos requeridos", "Título y mensaje son obligatorios.")
            return
        self.service.create_manual_alert(
            title=title,
            message=message,
            severity=self.severity_combo.currentData(),
            branch_id=self.branch_combo.currentData(),
            priority=self.priority_combo.currentData(),
        )
        self.accept()


# ---------------------------------------------------------------------------
# Exp 7 – Diálogo: Notas de resolución
# ---------------------------------------------------------------------------
class ResolveWithNotesDialog(QDialog):
    """Dialog shown when resolving an alert to capture resolution notes."""

    def __init__(self, alert: dict, parent=None):
        super().__init__(parent)
        self.alert = alert
        self.setWindowTitle("Resolver Alerta")
        self.setMinimumWidth(400)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(f"<b>{self.alert.get('title', '')}</b>")
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addWidget(QLabel("Notas de resolución (opcional):"))
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(100)
        self.notes_edit.setPlaceholderText("¿Por qué se resuelve? ¿Qué acción se tomó?")
        layout.addWidget(self.notes_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_notes(self) -> str:
        return self.notes_edit.toPlainText().strip()


# ---------------------------------------------------------------------------
# Exp 9 – Diálogo: Asignar alerta a usuario
# ---------------------------------------------------------------------------
class AssignAlertDialog(QDialog):
    """Dialog to assign an alert to a system user."""

    def __init__(self, service: AlertService, alert: dict, parent=None):
        super().__init__(parent)
        self.service = service
        self.alert = alert
        self.setWindowTitle("Asignar Alerta")
        self.setMinimumWidth(360)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Asignar: <b>{self.alert.get('title', '')}</b>"))

        self.user_combo = QComboBox()
        self.user_combo.addItem("Sin asignar", None)
        self._load_users()
        layout.addWidget(QLabel("Usuario:"))
        layout.addWidget(self.user_combo)

        # Pre-select current assignee
        current = self.alert.get("assigned_to")
        if current:
            idx = self.user_combo.findData(current)
            if idx >= 0:
                self.user_combo.setCurrentIndex(idx)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_users(self):
        try:
            from models.user import User
            users = self.service.db.query(User).filter(User.is_active == True).all()
            for u in users:
                self.user_combo.addItem(u.name, u.id)
        except Exception as e:
            logger.warning(f"Could not load users for assignment dialog: {e}")

    def get_user_id(self):
        return self.user_combo.currentData()


# ---------------------------------------------------------------------------
# Exp 2 – Badge de no leídas
# ---------------------------------------------------------------------------
class UnreadBadgeLabel(QLabel):
    """Small badge label that shows the unread alert count."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_style(0)

    def update_count(self, count: int):
        self._apply_style(count)
        self.setText(str(count) if count > 0 else "")

    def _apply_style(self, count: int):
        if count == 0:
            self.setStyleSheet("background: transparent; border: none;")
        else:
            color = "#e74c3c" if count > 0 else "#95a5a6"
            self.setStyleSheet(
                f"background: {color}; color: white; border-radius: 9px;"
                " padding: 1px 6px; font-size: 11px; font-weight: bold;"
            )


# ---------------------------------------------------------------------------
# Tab: Alertas Abiertas
# ---------------------------------------------------------------------------
class OpenAlertsTab(QWidget):
    """Tab that lists open (unresolved) alerts with all filter/action controls."""

    # Columns: hidden ID + visible columns
    _HEADERS = [
        "ID", "Tipo", "Severidad", "Prioridad", "Producto", "Sucursal",
        "Título", "Días vencido", "Asignada a", "Leída", "Vencida", "Acciones",
    ]
    _COL_ID       = 0
    _COL_TIPO     = 1
    _COL_SEV      = 2
    _COL_PRIO     = 3
    _COL_PROD     = 4
    _COL_BRANCH   = 5
    _COL_TITLE    = 6
    _COL_DAYS     = 7
    _COL_ASSIGN   = 8
    _COL_READ     = 9
    _COL_EXPIRED  = 10
    _COL_ACTIONS  = 11

    def __init__(self, db: Session, badge: UnreadBadgeLabel, parent=None):
        super().__init__(parent)
        self.db = db
        self.service = AlertService(db)
        self.badge = badge
        self.current_severity = None
        self.current_alert_type = None
        self.current_branch_id = None
        self.current_date_from = None
        self.current_date_to = None
        self.show_mine_only = False
        self.current_user_id = None   # set externally if session user is known
        self._build_ui()
        self.load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ---- Filter bar ----
        filter_layout = QHBoxLayout()

        # Severidad
        self.severity_combo = QComboBox()
        self.severity_combo.addItem("Todas las severidades", None)
        for key, label in ALERT_SEVERITIES.items():
            self.severity_combo.addItem(label, key)
        self.severity_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(QLabel("Severidad:"))
        filter_layout.addWidget(self.severity_combo)

        # Tipo de alerta
        self.alert_type_combo = QComboBox()
        self.alert_type_combo.addItem("Todos los tipos", None)
        for key, label in _ALERT_TYPE_LABELS.items():
            self.alert_type_combo.addItem(label, key)
        self.alert_type_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(QLabel("Tipo:"))
        filter_layout.addWidget(self.alert_type_combo)

        # Sucursal – Exp 4
        self.branch_combo = QComboBox()
        self.branch_combo.addItem("Todas las sucursales", None)
        self._load_branches()
        self.branch_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(QLabel("Sucursal:"))
        filter_layout.addWidget(self.branch_combo)

        # Mis alertas – Exp 9
        self.mine_check = QCheckBox("Mis alertas")
        self.mine_check.stateChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.mine_check)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # ---- Date range – Exp 5 ----
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("Desde:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setSpecialValueText("Sin filtro")
        self.date_from.setDate(QDate(2000, 1, 1))
        self.date_from.dateChanged.connect(self._on_filter_changed)
        date_layout.addWidget(self.date_from)

        date_layout.addWidget(QLabel("Hasta:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setSpecialValueText("Sin filtro")
        self.date_to.setDate(QDate.currentDate())
        self.date_to.dateChanged.connect(self._on_filter_changed)
        date_layout.addWidget(self.date_to)

        self.use_date_filter = QCheckBox("Filtrar por fecha")
        self.use_date_filter.stateChanged.connect(self._on_filter_changed)
        date_layout.addWidget(self.use_date_filter)
        date_layout.addStretch()
        layout.addLayout(date_layout)

        # ---- Table ----
        self.table = QTableWidget()
        self.table.setColumnCount(len(self._HEADERS))
        self.table.setHorizontalHeaderLabels(self._HEADERS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setColumnHidden(self._COL_ID, True)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

    def _load_branches(self):
        try:
            from models.branch import Branch
            branches = self.service.db.query(Branch).filter(Branch.is_active == True).all()
            for b in branches:
                self.branch_combo.addItem(b.name, b.id)
        except Exception as e:
            logger.warning(f"Could not load branches for filter: {e}")

    def _on_filter_changed(self):
        self.current_severity = self.severity_combo.currentData()
        self.current_alert_type = self.alert_type_combo.currentData()
        self.current_branch_id = self.branch_combo.currentData()
        self.show_mine_only = self.mine_check.isChecked()

        if self.use_date_filter.isChecked():
            df = self.date_from.date()
            dt = self.date_to.date()
            self.current_date_from = datetime(df.year(), df.month(), df.day(), tzinfo=timezone.utc)
            self.current_date_to = datetime(dt.year(), dt.month(), dt.day(), 23, 59, 59, tzinfo=timezone.utc)
        else:
            self.current_date_from = None
            self.current_date_to = None

        self.load_data()

    def load_data(self):
        """Load open alerts into table."""
        alerts = self.service.list_alerts(
            limit=500,
            severity=self.current_severity,
            alert_type=self.current_alert_type,
            branch_id=self.current_branch_id,
            date_from=self.current_date_from,
            date_to=self.current_date_to,
        )
        # Keep only unresolved
        alerts = [a for a in alerts if not a["is_resolved"]]

        # Exp 9 – filter "mine"
        if self.show_mine_only and self.current_user_id:
            alerts = [a for a in alerts if a.get("assigned_to") == self.current_user_id]

        # Enrich with names
        alerts = [self.service.enrich_alert(a) for a in alerts]

        self.table.setRowCount(len(alerts))
        for row, alert in enumerate(alerts):
            self._fill_row(row, alert)

        self.table.resizeColumnsToContents()

        # Update badge
        unread_count = self.service.get_unread_count()
        self.badge.update_count(unread_count)

    def _fill_row(self, row: int, alert: dict):
        """Populate a single table row."""
        sev = alert.get("severity", "")
        bg = _SEVERITY_COLORS.get(sev)

        def _item(text: str) -> QTableWidgetItem:
            item = QTableWidgetItem(str(text) if text is not None else "—")
            if bg:
                item.setBackground(bg)
            return item

        prio_labels = ALERT_PRIORITIES
        expired_text = "⚠ Vencida" if alert.get("is_expired_flag") else ""

        self.table.setItem(row, self._COL_ID,     QTableWidgetItem(str(alert["id"])))
        self.table.setItem(row, self._COL_TIPO,   _item(_ALERT_TYPE_LABELS.get(alert["alert_type"], alert["alert_type"])))
        self.table.setItem(row, self._COL_SEV,    _item(ALERT_SEVERITIES.get(sev, sev)))
        self.table.setItem(row, self._COL_PRIO,   _item(prio_labels.get(alert.get("priority", "normal"), alert.get("priority", ""))))
        self.table.setItem(row, self._COL_PROD,   _item(alert.get("product_name", "—")))
        self.table.setItem(row, self._COL_BRANCH, _item(alert.get("branch_name", "—")))
        self.table.setItem(row, self._COL_TITLE,  _item(alert.get("title", "")))
        self.table.setItem(row, self._COL_DAYS,   _item(self._get_overdue_days(alert)))
        self.table.setItem(row, self._COL_ASSIGN, _item(alert.get("assigned_to_name", "—")))
        self.table.setItem(row, self._COL_READ,   _item("Sí" if alert["is_read"] else "No"))
        self.table.setItem(row, self._COL_EXPIRED, _item(expired_text))

        # ---- Actions widget ----
        actions_widget = QWidget()
        al = QHBoxLayout(actions_widget)
        al.setContentsMargins(3, 2, 3, 2)
        al.setSpacing(3)

        # Mark read
        read_btn = QPushButton("Leída")
        read_btn.setEnabled(not alert["is_read"])
        read_btn.setMaximumWidth(60)
        read_btn.clicked.connect(lambda _, aid=alert["id"]: self._on_mark_read(aid))
        al.addWidget(read_btn)

        # Resolve (Exp 7 – with notes dialog)
        resolve_btn = QPushButton("Resolver")
        resolve_btn.setMaximumWidth(70)
        resolve_btn.clicked.connect(lambda _, a=alert: self._on_resolve(a))
        al.addWidget(resolve_btn)

        # Assign (Exp 9)
        assign_btn = QPushButton("Asignar")
        assign_btn.setMaximumWidth(65)
        assign_btn.clicked.connect(lambda _, a=alert: self._on_assign(a))
        al.addWidget(assign_btn)

        context_action = self._get_context_action(alert)
        if context_action:
            btn = QPushButton(context_action["label"])
            btn.setMaximumWidth(120)
            btn.clicked.connect(lambda _, a=alert, action=context_action: self._on_context_action(a, action))
            al.addWidget(btn)

        # Quick actions (Exp 3)
        full_alert = self.service.get_alert_with_actions(alert["id"])
        if full_alert:
            for action_def in full_alert.get("available_actions", []):
                btn = QPushButton(action_def["label"])
                btn.setMaximumWidth(110)
                btn.clicked.connect(
                    lambda _, ad=action_def, a=alert: self._on_quick_action(ad, a)
                )
                al.addWidget(btn)

        al.addStretch()
        self.table.setCellWidget(row, self._COL_ACTIONS, actions_widget)

    # ---- Handlers ----

    def _on_mark_read(self, alert_id: int):
        if not self.service.mark_as_read(alert_id):
            QMessageBox.warning(self, "Error", "No se pudo marcar la alerta como leída.")
        self.load_data()

    def _on_resolve(self, alert: dict):
        dlg = ResolveWithNotesDialog(alert, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            notes = dlg.get_notes()
            ok = (
                self.service.resolve_alert_with_notes(alert["id"], notes)
                if notes
                else self.service.resolve_alert(alert["id"])
            )
            if not ok:
                QMessageBox.warning(self, "Error", "No se pudo resolver la alerta.")
            self.load_data()

    def _on_assign(self, alert: dict):
        dlg = AssignAlertDialog(self.service, alert, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            user_id = dlg.get_user_id()
            if user_id is None:
                self.service.unassign_alert(alert["id"])
            else:
                self.service.assign_alert(alert["id"], user_id)
            self.load_data()

    def _get_overdue_days(self, alert: dict) -> str:
        alert_type = alert.get("alert_type")
        if alert_type not in {"count_overdue", "count_due_soon"}:
            return "—"
        due_date = alert.get("due_date")
        if not due_date:
            return "—"
        try:
            if isinstance(due_date, str):
                due_dt = datetime.fromisoformat(due_date.replace("Z", "+00:00"))
            else:
                due_dt = due_date
            if due_dt.tzinfo is None:
                due_dt = due_dt.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta = now.date() - due_dt.date()
            return str(delta.days if delta.days >= 0 else 0)
        except Exception:
            return "—"

    def _get_context_action(self, alert: dict) -> dict | None:
        alert_type = alert.get("alert_type")
        if alert_type in {"count_overdue", "count_due_soon"}:
            return {"label": "Ver Conteo", "target": "count"}
        if alert_type in {"approval_pending_admin", "approval_pending_manager"}:
            return {"label": "Ver Transferencia", "target": "movement"}
        if alert_type in {"capacity_warning", "capacity_critical", "capacity_exceeded"}:
            return {"label": "Ver Sucursal", "target": "branch"}
        if alert_type in {"batch_expiring_urgent", "batch_expiring_warning"}:
            return {"label": "Ver Lote", "target": "batch"}
        return None

    def _on_context_action(self, alert: dict, action: dict):
        target = action.get("target", "")
        target_label = {
            "count": "módulo de conteos",
            "movement": "movimiento",
            "branch": "configuración de sucursal",
            "batch": "detalle del lote",
        }.get(target, "módulo correspondiente")
        QMessageBox.information(
            self,
            "Abrir detalle",
            f"Se abriría el {target_label} para la alerta #{alert['id']}",
        )

    def _on_quick_action(self, action_def: dict, alert: dict):
        """Notify parent that a quick-action was triggered (Exp 3)."""
        action = action_def.get("action", "")
        QMessageBox.information(
            self,
            "Acción rápida",
            f"Acción: {action_def.get('label', action)}\n"
            f"(Abrir módulo correspondiente para alerta #{alert['id']})",
        )


# ---------------------------------------------------------------------------
# Tab: Historial de Resueltas – Exp 8
# ---------------------------------------------------------------------------
class ResolvedAlertsTab(QWidget):
    """Tab that shows the archive of resolved alerts."""

    _HEADERS = [
        "ID", "Tipo", "Severidad", "Producto", "Sucursal",
        "Título", "Resuelta el", "Notas de resolución",
    ]
    _COL_ID     = 0
    _COL_TIPO   = 1
    _COL_SEV    = 2
    _COL_PROD   = 3
    _COL_BRANCH = 4
    _COL_TITLE  = 5
    _COL_DATE   = 6
    _COL_NOTES  = 7

    def __init__(self, db: Session, parent=None):
        super().__init__(parent)
        self.db = db
        self.service = AlertService(db)
        self.current_branch_id = None
        self.current_date_from = None
        self.current_date_to = None
        self._build_ui()
        self.load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        filter_layout = QHBoxLayout()

        # Sucursal
        self.branch_combo = QComboBox()
        self.branch_combo.addItem("Todas las sucursales", None)
        self._load_branches()
        self.branch_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(QLabel("Sucursal:"))
        filter_layout.addWidget(self.branch_combo)

        # Fechas
        filter_layout.addWidget(QLabel("Desde:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate(2000, 1, 1))
        self.date_from.dateChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.date_from)

        filter_layout.addWidget(QLabel("Hasta:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.dateChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.date_to)

        self.use_date_filter = QCheckBox("Filtrar por fecha")
        self.use_date_filter.stateChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.use_date_filter)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self._HEADERS))
        self.table.setHorizontalHeaderLabels(self._HEADERS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setColumnHidden(self._COL_ID, True)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

    def _load_branches(self):
        try:
            from models.branch import Branch
            branches = self.service.db.query(Branch).filter(Branch.is_active == True).all()
            for b in branches:
                self.branch_combo.addItem(b.name, b.id)
        except Exception as e:
            logger.warning(f"Could not load branches for history filter: {e}")

    def _on_filter_changed(self):
        self.current_branch_id = self.branch_combo.currentData()
        if self.use_date_filter.isChecked():
            df = self.date_from.date()
            dt = self.date_to.date()
            self.current_date_from = datetime(df.year(), df.month(), df.day(), tzinfo=timezone.utc)
            self.current_date_to = datetime(dt.year(), dt.month(), dt.day(), 23, 59, 59, tzinfo=timezone.utc)
        else:
            self.current_date_from = None
            self.current_date_to = None
        self.load_data()

    def load_data(self):
        alerts = self.service.list_resolved_alerts(
            limit=500,
            branch_id=self.current_branch_id,
            date_from=self.current_date_from,
            date_to=self.current_date_to,
        )
        self.table.setRowCount(len(alerts))
        for row, alert in enumerate(alerts):
            self._fill_row(row, alert)
        self.table.resizeColumnsToContents()

    def _fill_row(self, row: int, alert: dict):
        def _item(text) -> QTableWidgetItem:
            return QTableWidgetItem(str(text) if text is not None else "—")

        resolved_str = ""
        if alert.get("resolved_at"):
            try:
                resolved_str = alert["resolved_at"][:19].replace("T", " ")
            except Exception:
                resolved_str = str(alert["resolved_at"])

        self.table.setItem(row, self._COL_ID,     _item(alert["id"]))
        self.table.setItem(row, self._COL_TIPO,   _item(_ALERT_TYPE_LABELS.get(alert["alert_type"], alert["alert_type"])))
        self.table.setItem(row, self._COL_SEV,    _item(ALERT_SEVERITIES.get(alert["severity"], alert["severity"])))
        self.table.setItem(row, self._COL_PROD,   _item(alert.get("product_name", "—")))
        self.table.setItem(row, self._COL_BRANCH, _item(alert.get("branch_name", "—")))
        self.table.setItem(row, self._COL_TITLE,  _item(alert.get("title", "")))
        self.table.setItem(row, self._COL_DATE,   _item(resolved_str))
        self.table.setItem(row, self._COL_NOTES,  _item(alert.get("resolution_notes", "")))


# ---------------------------------------------------------------------------
# Main view – AlertListView (tabs: Abiertas + Historial)
# ---------------------------------------------------------------------------
class AlertListView(QWidget):
    """
    Main alert management widget.

    Layout:
      Header: title | badge de no leídas | botón Crear Manual | botón Actualizar
      Body  : QTabWidget
                Tab 0 – Alertas Abiertas  (OpenAlertsTab)
                Tab 1 – Historial         (ResolvedAlertsTab)
    """

    def __init__(self, db: Session, parent=None):
        super().__init__(parent)
        self.db = db
        self.service = AlertService(db)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # ---- Header ----
        header = QHBoxLayout()

        title_lbl = QLabel("Alertas")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title_lbl)

        # Exp 2 – Badge
        self.badge = UnreadBadgeLabel()
        self.badge.setMinimumWidth(24)
        self.badge.setMinimumHeight(18)
        header.addWidget(self.badge)

        header.addStretch()

        # Exp 6 – Botón alerta manual
        manual_btn = QPushButton("+ Crear Alerta Manual")
        manual_btn.setStyleSheet("font-weight: bold;")
        manual_btn.clicked.connect(self._on_create_manual)
        header.addWidget(manual_btn)

        refresh_btn = QPushButton("Actualizar")
        refresh_btn.clicked.connect(self._on_refresh)
        header.addWidget(refresh_btn)

        layout.addLayout(header)

        # ---- Separator ----
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # ---- Tabs ----
        self.tabs = QTabWidget()

        self.open_tab = OpenAlertsTab(self.db, self.badge, self)
        self.tabs.addTab(self.open_tab, "Alertas Abiertas")

        self.history_tab = ResolvedAlertsTab(self.db, self)
        self.tabs.addTab(self.history_tab, "Historial de Resueltas")

        layout.addWidget(self.tabs)

    # ---- Slots ----

    def _on_create_manual(self):
        """Open dialog to create a manual alert (Exp 6)."""
        dlg = ManualAlertDialog(self.service, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._on_refresh()

    def _on_refresh(self):
        """Reload whichever tab is visible, plus the badge."""
        self.open_tab.load_data()
        if self.tabs.currentIndex() == 1:
            # Clean up old resolved alerts when refreshing history tab
            try:
                deleted_count = self.service.clear_old_alerts(days=30)
                if deleted_count > 0:
                    QMessageBox.information(
                        self,
                        "Limpieza de Historial",
                        f"Se eliminaron {deleted_count} alertas resueltas viejas (más de 30 días)."
                    )
            except Exception as e:
                logger.error(f"Error clearing old alerts: {e}")
            self.history_tab.load_data()

    def refresh(self):
        """Public method called by external code (e.g. ALERT_GENERATED handler)."""
        self._on_refresh()
