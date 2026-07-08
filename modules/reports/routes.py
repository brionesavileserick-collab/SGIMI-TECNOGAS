"""
Reports GUI routes/controllers for PyQt6 interface.

Expansiones implementadas
─────────────────────────
 1  Filtros por fecha       – QDateEdit inicio / fin
 2  Filtro por producto     – QComboBox de productos (donde aplica)
 3  Filtro por usuario      – QComboBox de usuarios (donde aplica)
 4  Exportación CSV         – Botón "Exportar CSV"
 5  Exportación Excel       – Botón "Exportar Excel"
 6  Vista formateada        – Texto legible en vez de JSON crudo
 7  Reportes guardados      – Panel lateral: guardar / cargar / eliminar
 8  Comparación períodos    – Tipo de reporte "Comparar Períodos"
 9  Top productos           – Tipo de reporte "Top Productos"
10  Eficiencia sucursal     – Tipo de reporte "Eficiencia por Sucursal"
11  Valor de inventario     – Tipo de reporte "Valor de Inventario"
12  Transferencias          – Tipo de reporte "Transferencias"
13  Tendencias              – Tipo de reporte "Tendencias"
"""

import json
import logging
import threading
from datetime import datetime

from PyQt6.QtCore import QDate, Qt, QTime
from PyQt6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QSplitter, QTextEdit,
    QTimeEdit, QVBoxLayout, QWidget,
)
from sqlalchemy.orm import Session

from modules.branches.service import BranchService
from modules.reports.service import ReportsService

logger = logging.getLogger(__name__)

# ── Report type catalogue ────────────────────────────────────────────────────
#   (display_label, internal_key, needs_product, needs_user)
_REPORT_TYPES = [
    ("Inventario",             "inventory",          True,  False),
    ("Movimientos",            "movements",          True,  True),
    ("Discrepancias",          "discrepancies",      True,  False),
    ("KPIs",                   "kpis",               False, False),
    ("Actividad de Usuarios",  "user_activity",      False, True),
    ("Top Productos",          "top_products",       False, False),
    ("Eficiencia por Sucursal","branch_efficiency",  False, False),
    ("Valor de Inventario",    "inventory_value",    False, False),
    ("Transferencias",         "transfers",          False, False),
    ("Tendencias",             "trends",             False, False),
    ("Comparar Períodos",      "comparison",         False, False),
    ("Auditoría de Historial", "history_audit",      False, True),
    ("Conteos de Inventario",  "count_sessions",     True,  False),
    ("Aprobaciones",           "approvals",          True,  False),
    ("Alertas",                "alerts",             True,  False),
    ("Capacidad de Sucursal",  "branch_capacity",    False, False),
    ("Cambios de Configuración","config_changes",    True,  False),
    ("Lotes",                  "batches",            True,  False),
    ("Kits",                   "kits",               False, False),
    ("Análisis ABC",           "abc_analysis",       True,  False),
]


class ReportScheduleDialog(QDialog):
    """Simple dialog to define a recurring report schedule."""

    def __init__(self, service: ReportsService, parent=None):
        super().__init__(parent)
        self.service = service
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Programación de reporte")
        form = QFormLayout(self)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Ej. Alertas diarias")
        self.report_type_combo = QComboBox()
        for label, key, _, __ in _REPORT_TYPES:
            self.report_type_combo.addItem(label, key)
        self.freq_combo = QComboBox()
        self.freq_combo.addItem("Diaria", "daily")
        self.freq_combo.addItem("Semanal", "weekly")
        self.freq_combo.addItem("Mensual", "monthly")
        self.time_edit = QTimeEdit()
        self.time_edit.setTime(QTime(8, 0))
        self.weekday_combo = QComboBox()
        self.weekday_combo.addItem("Lunes", 0)
        self.weekday_combo.addItem("Martes", 1)
        self.weekday_combo.addItem("Miércoles", 2)
        self.weekday_combo.addItem("Jueves", 3)
        self.weekday_combo.addItem("Viernes", 4)
        self.weekday_combo.addItem("Sábado", 5)
        self.weekday_combo.addItem("Domingo", 6)
        self.day_spin = QSpinBox()
        self.day_spin.setRange(1, 31)
        self.day_spin.setValue(1)
        self.params_edit = QLineEdit()
        self.params_edit.setPlaceholderText('{"branch_id": 1, "days_until_expiry": 30}')

        form.addRow("Nombre:", self.name_edit)
        form.addRow("Tipo de reporte:", self.report_type_combo)
        form.addRow("Frecuencia:", self.freq_combo)
        form.addRow("Hora:", self.time_edit)
        form.addRow("Día de la semana:", self.weekday_combo)
        form.addRow("Día del mes:", self.day_spin)
        form.addRow("Parámetros (JSON):", self.params_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _save(self):
        try:
            params = json.loads(self.params_edit.text().strip() or "{}") if self.params_edit.text().strip() else {}
        except Exception as exc:
            QMessageBox.critical(self, "Parámetros inválidos", str(exc))
            return
        data = {
            "name": self.name_edit.text().strip(),
            "report_type": self.report_type_combo.currentData(),
            "schedule_type": self.freq_combo.currentData(),
            "schedule_time": self.time_edit.time().toString("HH:mm"),
            "schedule_day_of_week": self.weekday_combo.currentData(),
            "schedule_day_of_month": self.day_spin.value(),
            "parameters": params,
            "is_active": True,
        }
        self.service.create_report_schedule(data)
        self.accept()


class ReportScheduler(threading.Thread):
    """Background thread that runs due report schedules every hour."""

    def __init__(self, service: ReportsService):
        super().__init__(daemon=True)
        self.service = service
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            try:
                self.service.process_due_schedules()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Scheduled reports processing error: %s", exc)
            self._stop_event.wait(3600)


class ReportsView(QWidget):
    """Main reports view widget."""

    def __init__(self, db: Session, current_user_id: int = None, current_user=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.service = ReportsService(db)
        self.branch_service = BranchService(db)
        self.current_user_id = current_user_id
        self.current_user = current_user
        self.is_employee = bool(getattr(current_user, "role", None) == "empleado")
        self._last_report_data: dict = {}
        self._last_report_type: str = ""
        self._setup_ui()
        self._scheduler = ReportScheduler(self.service)
        self._scheduler.start()

    # ──────────────────────────────────────────────────────────────────────────
    # UI SETUP
    # ──────────────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        if self.is_employee:
            placeholder = QLabel("No tiene permisos para ver reportes.")
            placeholder.setStyleSheet("font-size: 16px; font-weight: bold; color: #666;")
            root.addWidget(placeholder, alignment=Qt.AlignmentFlag.AlignCenter)
            self.setLayout(root)
            return

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_controls_panel())
        splitter.addWidget(self._build_output_panel())
        splitter.addWidget(self._build_saved_panel())
        splitter.setSizes([300, 700, 220])

        root.addWidget(splitter)
        self.setLayout(root)

    # ── Left panel: filters + actions ────────────────────────────────────────

    def _build_controls_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Reportes")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # Report type
        grp_type = QGroupBox("Tipo de reporte")
        fl = QFormLayout(grp_type)
        self.report_combo = QComboBox()
        for label, key, _, __ in _REPORT_TYPES:
            self.report_combo.addItem(label, key)
        self.report_combo.currentIndexChanged.connect(self._on_report_type_changed)
        fl.addRow("Reporte:", self.report_combo)
        layout.addWidget(grp_type)

        # Branch filter
        grp_branch = QGroupBox("Sucursal")
        fl2 = QFormLayout(grp_branch)
        self.branch_combo = QComboBox()
        self._reload_branches()
        fl2.addRow("Sucursal:", self.branch_combo)
        layout.addWidget(grp_branch)

        # Date filters
        grp_dates = QGroupBox("Rango de fechas (opcional)")
        fl3 = QFormLayout(grp_dates)
        self.date_from_edit = QDateEdit()
        self.date_from_edit.setCalendarPopup(True)
        self.date_from_edit.setSpecialValueText("Sin límite")
        self.date_from_edit.setDate(QDate(2000, 1, 1))
        self.date_to_edit = QDateEdit()
        self.date_to_edit.setCalendarPopup(True)
        self.date_to_edit.setSpecialValueText("Sin límite")
        self.date_to_edit.setDate(QDate.currentDate())
        self.chk_use_dates = QPushButton("Usar fechas")
        self.chk_use_dates.setCheckable(True)
        self.chk_use_dates.setChecked(False)
        fl3.addRow("Desde:", self.date_from_edit)
        fl3.addRow("Hasta:", self.date_to_edit)
        fl3.addRow("", self.chk_use_dates)
        layout.addWidget(grp_dates)

        # Product filter (shown only when applicable)
        self.grp_product = QGroupBox("Producto (opcional)")
        fl4 = QFormLayout(self.grp_product)
        self.product_combo = QComboBox()
        self.product_combo.addItem("Todos los productos", None)
        self._reload_products()
        fl4.addRow("Producto:", self.product_combo)
        layout.addWidget(self.grp_product)

        # User filter (shown only when applicable)
        self.grp_user = QGroupBox("Usuario (opcional)")
        fl5 = QFormLayout(self.grp_user)
        self.user_combo = QComboBox()
        self.user_combo.addItem("Todos los usuarios", None)
        self._reload_users()
        fl5.addRow("Usuario:", self.user_combo)
        layout.addWidget(self.grp_user)

        # Top-products specific options
        self.grp_top = QGroupBox("Opciones Top Productos")
        fl6 = QFormLayout(self.grp_top)
        self.top_metric_combo = QComboBox()
        for lbl, val in [
            ("Más movidos",           "most_moved"),
            ("Menos movidos",         "least_moved"),
            ("Mayor stock",           "most_stock"),
            ("Menor stock",           "lowest_stock"),
            ("Más discrepancias",     "most_discrepancies"),
        ]:
            self.top_metric_combo.addItem(lbl, val)
        self.top_limit_spin = QSpinBox()
        self.top_limit_spin.setRange(1, 100)
        self.top_limit_spin.setValue(10)
        fl6.addRow("Métrica:", self.top_metric_combo)
        fl6.addRow("Límite:", self.top_limit_spin)
        layout.addWidget(self.grp_top)

        # Trends specific options
        self.grp_trends = QGroupBox("Opciones Tendencias")
        fl7 = QFormLayout(self.grp_trends)
        self.trend_metric_combo = QComboBox()
        for lbl, val in [
            ("Total movimientos",     "movimientos_total"),
            ("Stock total",           "stock_total"),
            ("Discrepancias",         "discrepancias_count"),
        ]:
            self.trend_metric_combo.addItem(lbl, val)
        self.trend_period_spin = QSpinBox()
        self.trend_period_spin.setRange(1, 365)
        self.trend_period_spin.setValue(7)
        self.trend_period_spin.setSuffix(" días")
        self.trend_back_spin = QSpinBox()
        self.trend_back_spin.setRange(2, 52)
        self.trend_back_spin.setValue(8)
        self.trend_back_spin.setSuffix(" períodos")
        fl7.addRow("Métrica:", self.trend_metric_combo)
        fl7.addRow("Ventana:", self.trend_period_spin)
        fl7.addRow("Períodos atrás:", self.trend_back_spin)
        layout.addWidget(self.grp_trends)

        # Comparison specific options
        self.grp_compare = QGroupBox("Comparación – Período 2")
        fl8 = QFormLayout(self.grp_compare)
        self.cmp_report_combo = QComboBox()
        for lbl, key, _, __ in _REPORT_TYPES[:4]:  # only base types
            self.cmp_report_combo.addItem(lbl, key)
        self.cmp_from2 = QDateEdit()
        self.cmp_from2.setCalendarPopup(True)
        self.cmp_from2.setDate(QDate.currentDate().addDays(-60))
        self.cmp_to2 = QDateEdit()
        self.cmp_to2.setCalendarPopup(True)
        self.cmp_to2.setDate(QDate.currentDate().addDays(-30))
        fl8.addRow("Tipo base:", self.cmp_report_combo)
        fl8.addRow("Período 2 desde:", self.cmp_from2)
        fl8.addRow("Período 2 hasta:", self.cmp_to2)
        layout.addWidget(self.grp_compare)

        # History audit specific options
        self.grp_history_audit = QGroupBox("Opciones Auditoría de Historial")
        fl9 = QFormLayout(self.grp_history_audit)

        self.audit_entity_type_combo = QComboBox()
        self.audit_entity_type_combo.addItem("Todos los tipos", None)
        for key, label in [
            ("product",   "Producto"),
            ("branch",    "Sucursal"),
            ("movement",  "Movimiento"),
            ("inventory", "Inventario"),
            ("alert",     "Alerta"),
            ("user",      "Usuario"),
            ("system",    "Sistema"),
        ]:
            self.audit_entity_type_combo.addItem(label, key)

        self.audit_event_type_input = QLineEdit()
        self.audit_event_type_input.setPlaceholderText("ej. product.updated  (vacío = todos)")
        self.audit_event_type_input.setMaximumWidth(220)

        self.audit_limit_spin = QSpinBox()
        self.audit_limit_spin.setRange(10, 5000)
        self.audit_limit_spin.setValue(500)
        self.audit_limit_spin.setSuffix(" registros")

        fl9.addRow("Tipo de entidad:", self.audit_entity_type_combo)
        fl9.addRow("Evento exacto:", self.audit_event_type_input)
        fl9.addRow("Límite detalle:", self.audit_limit_spin)
        layout.addWidget(self.grp_history_audit)

        self.grp_count_sessions = QGroupBox("Opciones Conteos")
        fl10 = QFormLayout(self.grp_count_sessions)
        self.count_status_combo = QComboBox()
        self.count_status_combo.addItem("Todos", None)
        for value, label in [("pending", "Pendientes"), ("in_progress", "En progreso"), ("completed", "Completados"), ("cancelled", "Cancelados")]:
            self.count_status_combo.addItem(label, value)
        fl10.addRow("Estado:", self.count_status_combo)
        layout.addWidget(self.grp_count_sessions)

        self.grp_approvals = QGroupBox("Opciones Aprobaciones")
        fl11 = QFormLayout(self.grp_approvals)
        self.approval_level_combo = QComboBox()
        self.approval_level_combo.addItem("Todos", None)
        for value, label in [("admin", "Admin"), ("manager", "Manager")]:
            self.approval_level_combo.addItem(label, value)
        fl11.addRow("Nivel:", self.approval_level_combo)
        layout.addWidget(self.grp_approvals)

        self.grp_alerts = QGroupBox("Opciones Alertas")
        fl12 = QFormLayout(self.grp_alerts)
        self.alert_severity_combo = QComboBox()
        self.alert_severity_combo.addItem("Todas", None)
        for value, label in [("critical", "Critical"), ("warning", "Warning"), ("info", "Info")]:
            self.alert_severity_combo.addItem(label, value)
        fl12.addRow("Severidad:", self.alert_severity_combo)
        layout.addWidget(self.grp_alerts)

        self.grp_config_changes = QGroupBox("Opciones Cambios")
        fl13 = QFormLayout(self.grp_config_changes)
        self.config_entity_combo = QComboBox()
        self.config_entity_combo.addItem("Todos", None)
        for value, label in [("branch", "Sucursal"), ("product", "Producto"), ("branch_config", "Configuración de sucursal")]:
            self.config_entity_combo.addItem(label, value)
        fl13.addRow("Entidad:", self.config_entity_combo)
        layout.addWidget(self.grp_config_changes)

        self.grp_batches = QGroupBox("Opciones Lotes")
        fl14 = QFormLayout(self.grp_batches)
        self.batch_days_spin = QSpinBox()
        self.batch_days_spin.setRange(1, 365)
        self.batch_days_spin.setValue(30)
        self.batch_days_spin.setSuffix(" días")
        fl14.addRow("Días hasta vencimiento:", self.batch_days_spin)
        layout.addWidget(self.grp_batches)

        self.grp_abc = QGroupBox("Opciones Análisis ABC")
        fl15 = QFormLayout(self.grp_abc)
        self.abc_days_spin = QSpinBox()
        self.abc_days_spin.setRange(7, 365)
        self.abc_days_spin.setValue(90)
        self.abc_days_spin.setSuffix(" días")
        fl15.addRow("Sin movimiento desde:", self.abc_days_spin)
        layout.addWidget(self.grp_abc)

        self.grp_schedules = QGroupBox("Programaciones")
        fl16 = QVBoxLayout(self.grp_schedules)
        self.schedule_list = QListWidget()
        self.schedule_list.setMaximumHeight(140)
        fl16.addWidget(self.schedule_list)
        row_sched = QHBoxLayout()
        btn_new_schedule = QPushButton("➕ Crear")
        btn_new_schedule.clicked.connect(self._create_schedule)
        btn_run_schedule = QPushButton("▶ Ejecutar")
        btn_run_schedule.clicked.connect(self._run_selected_schedule)
        btn_delete_schedule = QPushButton("🗑 Eliminar")
        btn_delete_schedule.clicked.connect(self._delete_selected_schedule)
        row_sched.addWidget(btn_new_schedule)
        row_sched.addWidget(btn_run_schedule)
        row_sched.addWidget(btn_delete_schedule)
        fl16.addLayout(row_sched)
        layout.addWidget(self.grp_schedules)

        # Generate button
        btn_generate = QPushButton("▶  Generar reporte")
        btn_generate.setStyleSheet(
            "QPushButton { background: #1F4E78; color: white; "
            "font-weight: bold; padding: 6px; border-radius: 4px; }"
            "QPushButton:hover { background: #2E75B6; }"
        )
        btn_generate.clicked.connect(self.load_data)
        layout.addWidget(btn_generate)

        layout.addStretch()
        self._on_report_type_changed()  # initial visibility
        self._refresh_schedule_list()
        return panel

    # ── Right panel: output + export buttons ─────────────────────────────────

    def _build_output_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toggle raw JSON / formatted view
        top_bar = QHBoxLayout()
        self.lbl_status = QLabel("Selecciona un reporte y presiona Generar.")
        self.lbl_status.setStyleSheet("color: gray;")
        top_bar.addWidget(self.lbl_status)
        top_bar.addStretch()

        self.btn_toggle_view = QPushButton("Ver JSON")
        self.btn_toggle_view.setCheckable(True)
        self.btn_toggle_view.clicked.connect(self._toggle_view)
        top_bar.addWidget(self.btn_toggle_view)

        layout.addLayout(top_bar)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(self.output.font())
        layout.addWidget(self.output)

        # Export buttons
        export_bar = QHBoxLayout()
        self.btn_csv = QPushButton("⬇  Exportar CSV")
        self.btn_csv.setEnabled(False)
        self.btn_csv.clicked.connect(self._export_csv)
        self.btn_excel = QPushButton("⬇  Exportar Excel")
        self.btn_excel.setEnabled(False)
        self.btn_excel.clicked.connect(self._export_excel)
        export_bar.addStretch()
        export_bar.addWidget(self.btn_csv)
        export_bar.addWidget(self.btn_excel)
        layout.addLayout(export_bar)

        return panel

    # ── Far-right panel: saved reports ───────────────────────────────────────

    def _build_saved_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(180)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel("Reportes guardados")
        lbl.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl)

        self.saved_list = QListWidget()
        self.saved_list.itemDoubleClicked.connect(self._load_saved_report)
        layout.addWidget(self.saved_list)

        btn_save = QPushButton("💾  Guardar config actual")
        btn_save.clicked.connect(self._save_current_config)
        btn_delete = QPushButton("🗑  Eliminar seleccionado")
        btn_delete.clicked.connect(self._delete_saved_report)
        layout.addWidget(btn_save)
        layout.addWidget(btn_delete)

        self._refresh_saved_list()
        return panel

    # ──────────────────────────────────────────────────────────────────────────
    # DATA LOADERS
    # ──────────────────────────────────────────────────────────────────────────

    def _reload_branches(self):
        selected = self.branch_combo.currentData() if hasattr(self, "branch_combo") else None
        self.branch_combo.blockSignals(True)
        self.branch_combo.clear()
        self.branch_combo.addItem("Todas las sucursales", None)
        idx = 0
        for i, branch in enumerate(self.branch_service.get_all_active_branches(), start=1):
            self.branch_combo.addItem(branch["name"], branch["id"])
            if branch["id"] == selected:
                idx = i
        self.branch_combo.setCurrentIndex(idx)
        self.branch_combo.blockSignals(False)

    def _reload_products(self):
        try:
            from models.product import Product
            products = (
                self.db.query(Product)
                .filter(Product.is_active == True)
                .order_by(Product.name)
                .all()
            )
            for p in products:
                self.product_combo.addItem(f"{p.sku} – {p.name}", p.id)
        except Exception as exc:
            logger.warning("Could not load products: %s", exc)

    def _reload_users(self):
        try:
            from models.user import User
            users = (
                self.db.query(User)
                .filter(User.is_active == True)
                .order_by(User.name)
                .all()
            )
            for u in users:
                self.user_combo.addItem(u.name, u.id)
        except Exception as exc:
            logger.warning("Could not load users: %s", exc)

    # ──────────────────────────────────────────────────────────────────────────
    # VISIBILITY LOGIC
    # ──────────────────────────────────────────────────────────────────────────

    def _on_report_type_changed(self):
        rtype = self.report_combo.currentData()
        _, _, needs_product, needs_user = _REPORT_TYPES[self.report_combo.currentIndex()]
        self.grp_product.setVisible(bool(needs_product))
        self.grp_user.setVisible(bool(needs_user))
        self.grp_top.setVisible(rtype == "top_products")
        self.grp_trends.setVisible(rtype == "trends")
        self.grp_compare.setVisible(rtype == "comparison")
        self.grp_history_audit.setVisible(rtype == "history_audit")
        self.grp_count_sessions.setVisible(rtype == "count_sessions")
        self.grp_approvals.setVisible(rtype == "approvals")
        self.grp_alerts.setVisible(rtype == "alerts")
        self.grp_config_changes.setVisible(rtype == "config_changes")
        self.grp_batches.setVisible(rtype == "batches")
        self.grp_abc.setVisible(rtype == "abc_analysis")


    def _refresh_schedule_list(self):
        try:
            schedules = self.service.list_report_schedules(include_inactive=False)
        except Exception as exc:
            logger.warning("Could not load schedules: %s", exc)
            schedules = []
        self.schedule_list.clear()
        for schedule in schedules:
            label = f"{schedule['name']} · {schedule['report_type']} · {schedule['schedule_type']}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, schedule['id'])
            self.schedule_list.addItem(item)

    def _create_schedule(self):
        dialog = ReportScheduleDialog(self.service, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._refresh_schedule_list()
            QMessageBox.information(self, "Programación guardada", "La programación se creó correctamente.")

    def _run_selected_schedule(self):
        item = self.schedule_list.currentItem()
        if not item:
            return
        try:
            result = self.service.run_report_schedule(item.data(Qt.ItemDataRole.UserRole))
            QMessageBox.information(self, "Reporte programado ejecutado", f"Archivo generado en:\n{result['file_path']}")
        except Exception as exc:
            QMessageBox.critical(self, "Error al ejecutar programación", str(exc))

    def _delete_selected_schedule(self):
        item = self.schedule_list.currentItem()
        if not item:
            return
        schedule_id = item.data(Qt.ItemDataRole.UserRole)
        try:
            self.service.delete_report_schedule(schedule_id)
            self._refresh_schedule_list()
        except Exception as exc:
            QMessageBox.critical(self, "Error al eliminar programación", str(exc))

    def closeEvent(self, event):
        if getattr(self, "_scheduler", None):
            self._scheduler.stop()
        super().closeEvent(event)

    # ──────────────────────────────────────────────────────────────────────────
    # GENERATE REPORT
    # ──────────────────────────────────────────────────────────────────────────

    def load_data(self):
        """Build filters from UI and call the appropriate service method."""
        self._reload_branches()
        rtype = self.report_combo.currentData()
        branch_id = self.branch_combo.currentData()

        # Dates
        use_dates = self.chk_use_dates.isChecked()
        date_from = None
        date_to = None
        if use_dates:
            d = self.date_from_edit.date()
            date_from = datetime(d.year(), d.month(), d.day())
            d = self.date_to_edit.date()
            date_to = datetime(d.year(), d.month(), d.day(), 23, 59, 59)

        product_id = self.product_combo.currentData()
        user_id = self.user_combo.currentData()

        try:
            report = self._call_service(
                rtype, branch_id, date_from, date_to, product_id, user_id
            )
        except Exception as exc:
            logger.exception("Error generating report '%s'", rtype)
            QMessageBox.critical(self, "Error al generar reporte", str(exc))
            return

        self._last_report_data = report
        self._last_report_type = rtype
        self._render_output()
        self.btn_csv.setEnabled(True)
        self.btn_excel.setEnabled(True)
        self.lbl_status.setText(
            f"Reporte generado: {self.report_combo.currentText()}"
        )

    def _call_service(
        self, rtype, branch_id, date_from, date_to, product_id, user_id
    ) -> dict:
        """Dispatch to the right service method based on *rtype*."""
        svc = self.service

        if rtype == "inventory":
            return svc.generate_inventory_report(
                branch_id=branch_id, product_id=product_id,
                date_from=date_from, date_to=date_to,
            )
        if rtype == "movements":
            return svc.generate_movement_report(
                branch_id=branch_id, product_id=product_id,
                user_id=user_id, date_from=date_from, date_to=date_to,
            )
        if rtype == "discrepancies":
            return svc.generate_discrepancy_report(
                branch_id=branch_id, product_id=product_id,
                date_from=date_from, date_to=date_to,
            )
        if rtype == "kpis":
            return svc.generate_kpi_report(
                branch_id=branch_id, date_from=date_from, date_to=date_to,
            )
        if rtype == "user_activity":
            return svc.generate_user_activity_report(
                user_id=user_id, date_from=date_from, date_to=date_to,
            )
        if rtype == "top_products":
            return svc.generate_top_products_report(
                metric=self.top_metric_combo.currentData(),
                limit=self.top_limit_spin.value(),
                branch_id=branch_id,
                date_from=date_from,
                date_to=date_to,
            )
        if rtype == "branch_efficiency":
            return svc.generate_branch_efficiency_report(
                date_from=date_from, date_to=date_to,
            )
        if rtype == "inventory_value":
            return svc.generate_inventory_value_report(branch_id=branch_id)
        if rtype == "transfers":
            return svc.generate_transfer_report(
                branch_id=branch_id, date_from=date_from, date_to=date_to,
            )
        if rtype == "trends":
            return svc.generate_trend_report(
                metric=self.trend_metric_combo.currentData(),
                period_days=self.trend_period_spin.value(),
                periods_back=self.trend_back_spin.value(),
                branch_id=branch_id,
            )
        if rtype == "comparison":
            d1f = self.date_from_edit.date()
            d1t = self.date_to_edit.date()
            d2f = self.cmp_from2.date()
            d2t = self.cmp_to2.date()
            return svc.generate_comparison_report(
                report_type=self.cmp_report_combo.currentData(),
                period1_from=datetime(d1f.year(), d1f.month(), d1f.day()),
                period1_to=datetime(d1t.year(), d1t.month(), d1t.day(), 23, 59, 59),
                period2_from=datetime(d2f.year(), d2f.month(), d2f.day()),
                period2_to=datetime(d2t.year(), d2t.month(), d2t.day(), 23, 59, 59),
                branch_id=branch_id,
            )
        if rtype == "history_audit":
            audit_entity_type = self.audit_entity_type_combo.currentData()
            audit_event_type = self.audit_event_type_input.text().strip() or None
            return svc.generate_history_audit_report(
                entity_type=audit_entity_type,
                branch_id=branch_id,
                user_id=user_id,
                date_from=date_from,
                date_to=date_to,
                event_type=audit_event_type,
                limit=self.audit_limit_spin.value(),
            )
        if rtype == "count_sessions":
            return svc.generate_count_session_report(
                branch_id=branch_id,
                date_from=date_from,
                date_to=date_to,
                status=self.count_status_combo.currentData(),
            )
        if rtype == "approvals":
            return svc.generate_approval_report(
                branch_id=branch_id,
                date_from=date_from,
                date_to=date_to,
                approval_level=self.approval_level_combo.currentData(),
            )
        if rtype == "alerts":
            return svc.generate_alert_report(
                branch_id=branch_id,
                date_from=date_from,
                date_to=date_to,
                severity=self.alert_severity_combo.currentData(),
            )
        if rtype == "branch_capacity":
            return svc.generate_branch_capacity_report()
        if rtype == "config_changes":
            return svc.generate_config_change_report(
                branch_id=branch_id,
                date_from=date_from,
                date_to=date_to,
                entity_type=self.config_entity_combo.currentData(),
            )
        if rtype == "batches":
            return svc.generate_batch_report(
                branch_id=branch_id,
                days_until_expiry=self.batch_days_spin.value(),
            )
        if rtype == "kits":
            return svc.generate_kit_report(branch_id=branch_id)
        if rtype == "abc_analysis":
            return svc.generate_abc_analysis_report(
                branch_id=branch_id,
                days_without_movement=self.abc_days_spin.value(),
            )
        raise ValueError(f"Tipo de reporte desconocido: {rtype}")

    # ──────────────────────────────────────────────────────────────────────────
    # OUTPUT RENDERING
    # ──────────────────────────────────────────────────────────────────────────

    def _render_output(self):
        if not self._last_report_data:
            return
        if self.btn_toggle_view.isChecked():
            # Raw JSON view
            self.output.setPlainText(
                json.dumps(self._last_report_data, indent=2, ensure_ascii=False)
            )
        else:
            # Human-readable formatted view
            text = self.service.format_report_for_display(
                self._last_report_type, self._last_report_data
            )
            self.output.setPlainText(text)

    def _toggle_view(self):
        label = "Ver Formateado" if self.btn_toggle_view.isChecked() else "Ver JSON"
        self.btn_toggle_view.setText(label)
        self._render_output()


    # ──────────────────────────────────────────────────────────────────────────
    # EXPORT
    # ──────────────────────────────────────────────────────────────────────────

    def _export_csv(self):
        if not self._last_report_data:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "Guardar CSV", f"reporte_{self._last_report_type}.csv",
            "CSV (*.csv)"
        )
        if not filename:
            return
        try:
            self.service.export_to_csv(self._last_report_data, filename)
            QMessageBox.information(self, "Exportado", f"CSV guardado en:\n{filename}")
        except Exception as exc:
            logger.exception("CSV export failed")
            QMessageBox.critical(self, "Error al exportar CSV", str(exc))

    def _export_excel(self):
        if not self._last_report_data:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "Guardar Excel", f"reporte_{self._last_report_type}.xlsx",
            "Excel (*.xlsx)"
        )
        if not filename:
            return
        try:
            self.service.export_to_excel(self._last_report_data, filename)
            QMessageBox.information(self, "Exportado", f"Excel guardado en:\n{filename}")
        except ImportError as exc:
            QMessageBox.critical(
                self, "Dependencia faltante",
                "openpyxl no está instalado.\n"
                "Ejecuta:  pip install openpyxl==3.1.5"
            )
        except Exception as exc:
            logger.exception("Excel export failed")
            QMessageBox.critical(self, "Error al exportar Excel", str(exc))

    # ──────────────────────────────────────────────────────────────────────────
    # SAVED REPORTS
    # ──────────────────────────────────────────────────────────────────────────

    def _refresh_saved_list(self):
        self.saved_list.clear()
        try:
            records = self.service.get_saved_reports(self.current_user_id)
            for r in records:
                item = QListWidgetItem(r["name"])
                item.setData(Qt.ItemDataRole.UserRole, r["id"])
                item.setToolTip(
                    f"Tipo: {r['report_type']}\n"
                    f"Guardado: {r.get('created_at', '')}"
                )
                self.saved_list.addItem(item)
        except Exception as exc:
            logger.warning("Could not load saved reports: %s", exc)

    def _save_current_config(self):
        if not self._last_report_type:
            QMessageBox.information(
                self, "Sin reporte", "Genera un reporte primero antes de guardarlo."
            )
            return
        name, ok = QInputDialog.getText(
            self, "Guardar configuración",
            "Nombre para este reporte guardado:",
            QLineEdit.EchoMode.Normal,
            self.report_combo.currentText(),
        )
        if not ok or not name.strip():
            return

        params = {
            "branch_id": self.branch_combo.currentData(),
            "product_id": self.product_combo.currentData(),
            "user_id": self.user_combo.currentData(),
            "use_dates": self.chk_use_dates.isChecked(),
        }
        if self.chk_use_dates.isChecked():
            d = self.date_from_edit.date()
            params["date_from"] = f"{d.year()}-{d.month():02d}-{d.day():02d}"
            d = self.date_to_edit.date()
            params["date_to"] = f"{d.year()}-{d.month():02d}-{d.day():02d}"

        if self._last_report_type == "top_products":
            params["metric"] = self.top_metric_combo.currentData()
            params["limit"] = self.top_limit_spin.value()
        if self._last_report_type == "trends":
            params["trend_metric"] = self.trend_metric_combo.currentData()
            params["period_days"] = self.trend_period_spin.value()
            params["periods_back"] = self.trend_back_spin.value()
        if self._last_report_type == "history_audit":
            params["audit_entity_type"] = self.audit_entity_type_combo.currentData()
            params["audit_event_type"] = self.audit_event_type_input.text().strip() or None
            params["audit_limit"] = self.audit_limit_spin.value()
        if self._last_report_type == "count_sessions":
            params["count_status"] = self.count_status_combo.currentData()
        if self._last_report_type == "approvals":
            params["approval_level"] = self.approval_level_combo.currentData()
        if self._last_report_type == "alerts":
            params["alert_severity"] = self.alert_severity_combo.currentData()
        if self._last_report_type == "config_changes":
            params["config_entity_type"] = self.config_entity_combo.currentData()
        if self._last_report_type == "batches":
            params["batch_days"] = self.batch_days_spin.value()
        if self._last_report_type == "abc_analysis":
            params["abc_days"] = self.abc_days_spin.value()

        try:
            self.service.save_report_config(
                name=name.strip(),
                report_type=self._last_report_type,
                parameters=params,
                user_id=self.current_user_id,
            )
            self._refresh_saved_list()
            QMessageBox.information(self, "Guardado", f"Configuración '{name}' guardada.")
        except Exception as exc:
            logger.exception("Could not save report config")
            QMessageBox.critical(self, "Error al guardar", str(exc))

    def _load_saved_report(self, item: QListWidgetItem):
        config_id = item.data(Qt.ItemDataRole.UserRole)
        try:
            config = self.service.get_report_config(config_id)
            if not config:
                return
            params = config.get("parameters_dict", {})
            rtype = config["report_type"]

            # Select report type in combo
            for i in range(self.report_combo.count()):
                if self.report_combo.itemData(i) == rtype:
                    self.report_combo.setCurrentIndex(i)
                    break

            # Restore branch
            bid = params.get("branch_id")
            for i in range(self.branch_combo.count()):
                if self.branch_combo.itemData(i) == bid:
                    self.branch_combo.setCurrentIndex(i)
                    break

            # Restore dates
            if params.get("use_dates") and params.get("date_from"):
                self.chk_use_dates.setChecked(True)
                parts = params["date_from"].split("-")
                self.date_from_edit.setDate(
                    QDate(int(parts[0]), int(parts[1]), int(parts[2]))
                )
            if params.get("date_to"):
                parts = params["date_to"].split("-")
                self.date_to_edit.setDate(
                    QDate(int(parts[0]), int(parts[1]), int(parts[2]))
                )

            # Restore top/trends options
            if rtype == "top_products" and params.get("metric"):
                for i in range(self.top_metric_combo.count()):
                    if self.top_metric_combo.itemData(i) == params["metric"]:
                        self.top_metric_combo.setCurrentIndex(i)
                        break
                self.top_limit_spin.setValue(params.get("limit", 10))
            if rtype == "trends" and params.get("trend_metric"):
                for i in range(self.trend_metric_combo.count()):
                    if self.trend_metric_combo.itemData(i) == params["trend_metric"]:
                        self.trend_metric_combo.setCurrentIndex(i)
                        break
                self.trend_period_spin.setValue(params.get("period_days", 7))
                self.trend_back_spin.setValue(params.get("periods_back", 8))
            if rtype == "history_audit":
                audit_et = params.get("audit_entity_type")
                for i in range(self.audit_entity_type_combo.count()):
                    if self.audit_entity_type_combo.itemData(i) == audit_et:
                        self.audit_entity_type_combo.setCurrentIndex(i)
                        break
                self.audit_event_type_input.setText(params.get("audit_event_type") or "")
                self.audit_limit_spin.setValue(params.get("audit_limit", 500))
            if rtype == "count_sessions":
                for i in range(self.count_status_combo.count()):
                    if self.count_status_combo.itemData(i) == params.get("count_status"):
                        self.count_status_combo.setCurrentIndex(i)
                        break
            if rtype == "approvals":
                for i in range(self.approval_level_combo.count()):
                    if self.approval_level_combo.itemData(i) == params.get("approval_level"):
                        self.approval_level_combo.setCurrentIndex(i)
                        break
            if rtype == "alerts":
                for i in range(self.alert_severity_combo.count()):
                    if self.alert_severity_combo.itemData(i) == params.get("alert_severity"):
                        self.alert_severity_combo.setCurrentIndex(i)
                        break
            if rtype == "config_changes":
                for i in range(self.config_entity_combo.count()):
                    if self.config_entity_combo.itemData(i) == params.get("config_entity_type"):
                        self.config_entity_combo.setCurrentIndex(i)
                        break
            if rtype == "batches":
                self.batch_days_spin.setValue(params.get("batch_days", 30))
            if rtype == "abc_analysis":
                self.abc_days_spin.setValue(params.get("abc_days", 90))

            # Auto-generate            self.load_data()
        except Exception as exc:
            logger.exception("Could not load saved report config")
            QMessageBox.critical(self, "Error al cargar", str(exc))

    def _delete_saved_report(self):
        item = self.saved_list.currentItem()
        if not item:
            return
        config_id = item.data(Qt.ItemDataRole.UserRole)
        name = item.text()
        reply = QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Eliminar el reporte guardado '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete_report_config(config_id)
            self._refresh_saved_list()
        except Exception as exc:
            logger.exception("Could not delete saved report config")
            QMessageBox.critical(self, "Error al eliminar", str(exc))
