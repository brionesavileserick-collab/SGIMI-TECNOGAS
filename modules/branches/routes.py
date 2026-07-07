"""
Branch GUI routes/controllers for PyQt6 interface.

Includes:
  - BranchDialog      : create/edit with tabs (General, Ubicación, Inventario, Capacidad)
  - StatusDialog      : change operational status
  - ManagerDialog     : assign / remove branch manager
  - BranchListView    : main list with enriched columns and all actions
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel, QLineEdit,
    QMessageBox, QDialog, QFormLayout, QTextEdit,
    QTabWidget, QComboBox, QSpinBox, QDoubleSpinBox,
    QCheckBox, QHeaderView, QSizePolicy, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from modules.branches.service import BranchService
from models.branch import OPERATIONAL_STATUS_VALUES, COUNT_FREQUENCY_VALUES
import logging

logger = logging.getLogger(__name__)

# ── Etiquetas legibles para los valores de dominio cerrado ──────────────────
STATUS_LABELS: Dict[str, str] = {
    "operativa":             "Operativa",
    "en_mantenimiento":      "En mantenimiento",
    "temporalmente_cerrada": "Temporalmente cerrada",
    "en_renovacion":         "En renovación",
}
STATUS_COLORS: Dict[str, str] = {
    "operativa":             "#2e7d32",   # green
    "en_mantenimiento":      "#e65100",   # orange
    "temporalmente_cerrada": "#b71c1c",   # red
    "en_renovacion":         "#1565c0",   # blue
}
FREQUENCY_LABELS: Dict[str, str] = {
    "mensual":    "Mensual",
    "bimestral":  "Bimestral",
    "trimestral": "Trimestral",
    "semestral":  "Semestral",
    "anual":      "Anual",
}


# ═══════════════════════════════════════════════════════════════════════════
# BranchDialog  –  Crear / Editar sucursal (con pestañas)
# ═══════════════════════════════════════════════════════════════════════════
class BranchDialog(QDialog):
    """Dialog for creating/editing branches.

    Organises fields into four tabs so the form doesn't feel overwhelming:
      Tab 1 – General      : nombre, dirección, estado activo
      Tab 2 – Ubicación    : latitud, longitud, zona, ciudad, estado, país
      Tab 3 – Inventario   : stock mínimo/máximo propios, alertas habilitadas
      Tab 4 – Capacidad    : capacidad de almacén, max SKUs, frecuencia conteo
    """

    def __init__(self, parent=None, branch_data: dict = None):
        super().__init__(parent)
        self.branch_data = branch_data or {}
        self._setup_ui()

    # ── UI setup ────────────────────────────────────────────────────────────
    def _setup_ui(self):
        is_edit = bool(self.branch_data.get("id"))
        self.setWindowTitle("Editar Sucursal" if is_edit else "Nueva Sucursal")
        self.setMinimumWidth(480)

        root = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._tab_general(),    "General")
        tabs.addTab(self._tab_ubicacion(),  "Ubicación")
        tabs.addTab(self._tab_inventario(), "Inventario")
        tabs.addTab(self._tab_capacidad(),  "Capacidad")
        root.addWidget(tabs)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        save = QPushButton("Guardar")
        save.setDefault(True)
        save.clicked.connect(self.accept)
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(save)
        btn_row.addWidget(cancel)
        root.addLayout(btn_row)

    # ── Tab 1: General ───────────────────────────────────────────────────
    def _tab_general(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(12, 12, 12, 12)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self.name_input = QLineEdit(self.branch_data.get("name", ""))
        form.addRow("Nombre *:", self.name_input)

        self.address_input = QTextEdit()
        self.address_input.setPlainText(self.branch_data.get("address") or "")
        self.address_input.setMaximumHeight(80)
        form.addRow("Dirección:", self.address_input)

        self.active_check = QCheckBox("Sucursal activa")
        self.active_check.setChecked(self.branch_data.get("is_active", True))
        form.addRow("", self.active_check)

        return w

    # ── Tab 2: Ubicación ─────────────────────────────────────────────────
    def _tab_ubicacion(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(12, 12, 12, 12)

        self.zone_input = QLineEdit(self.branch_data.get("zone") or "")
        self.zone_input.setPlaceholderText("ej. Norte, Sur, Zona Industrial")
        form.addRow("Zona:", self.zone_input)

        self.city_input = QLineEdit(self.branch_data.get("city") or "")
        form.addRow("Ciudad:", self.city_input)

        self.state_input = QLineEdit(self.branch_data.get("state") or "")
        form.addRow("Estado / Provincia:", self.state_input)

        self.country_input = QLineEdit(self.branch_data.get("country") or "México")
        form.addRow("País:", self.country_input)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        form.addRow(sep)

        # Latitude
        self.lat_input = QDoubleSpinBox()
        self.lat_input.setRange(-90.0, 90.0)
        self.lat_input.setDecimals(6)
        self.lat_input.setSingleStep(0.000001)
        self.lat_input.setSpecialValueText("(no definida)")
        self.lat_input.setMinimum(-999.0)   # sentinel for "empty"
        lat_val = self.branch_data.get("latitude")
        self.lat_input.setValue(lat_val if lat_val is not None else -999.0)
        form.addRow("Latitud:", self.lat_input)

        # Longitude
        self.lon_input = QDoubleSpinBox()
        self.lon_input.setRange(-180.0, 180.0)
        self.lon_input.setDecimals(6)
        self.lon_input.setSingleStep(0.000001)
        self.lon_input.setSpecialValueText("(no definida)")
        self.lon_input.setMinimum(-999.0)
        lon_val = self.branch_data.get("longitude")
        self.lon_input.setValue(lon_val if lon_val is not None else -999.0)
        form.addRow("Longitud:", self.lon_input)

        return w

    # ── Tab 3: Inventario ────────────────────────────────────────────────
    def _tab_inventario(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(12, 12, 12, 12)

        note = QLabel(
            "Deja en 0 para usar los umbrales globales del sistema."
        )
        note.setStyleSheet("color: gray; font-size: 11px;")
        note.setWordWrap(True)
        form.addRow(note)

        self.min_stock_input = QSpinBox()
        self.min_stock_input.setRange(0, 999999)
        self.min_stock_input.setSpecialValueText("(global)")
        self.min_stock_input.setValue(self.branch_data.get("default_min_stock") or 0)
        form.addRow("Stock mínimo propio:", self.min_stock_input)

        self.max_stock_input = QSpinBox()
        self.max_stock_input.setRange(0, 999999)
        self.max_stock_input.setSpecialValueText("(no definido)")
        self.max_stock_input.setValue(self.branch_data.get("default_max_stock") or 0)
        form.addRow("Stock máximo propio:", self.max_stock_input)

        self.alert_check = QCheckBox("Recibir alertas de stock")
        self.alert_check.setChecked(self.branch_data.get("stock_alert_enabled", True))
        form.addRow("", self.alert_check)

        return w

    # ── Tab 4: Capacidad ─────────────────────────────────────────────────
    def _tab_capacidad(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(12, 12, 12, 12)

        self.capacity_input = QLineEdit(self.branch_data.get("storage_capacity") or "")
        self.capacity_input.setPlaceholderText("ej. chica, mediana, grande, 500m²")
        form.addRow("Capacidad de almacén:", self.capacity_input)

        self.max_products_input = QSpinBox()
        self.max_products_input.setRange(0, 999999)
        self.max_products_input.setSpecialValueText("(sin límite)")
        self.max_products_input.setValue(self.branch_data.get("max_products") or 0)
        form.addRow("Máx. SKUs:", self.max_products_input)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        form.addRow(sep)

        self.freq_combo = QComboBox()
        self.freq_combo.addItem("(no definida)", None)
        for val in COUNT_FREQUENCY_VALUES:
            self.freq_combo.addItem(FREQUENCY_LABELS.get(val, val), val)
        current_freq = self.branch_data.get("count_frequency")
        if current_freq:
            idx = self.freq_combo.findData(current_freq)
            if idx >= 0:
                self.freq_combo.setCurrentIndex(idx)
        form.addRow("Frecuencia de conteo:", self.freq_combo)

        return w

    # ── Collect data ─────────────────────────────────────────────────────
    def get_data(self) -> dict:
        """Return a dict with all form values, ready for the service."""
        lat = self.lat_input.value()
        lon = self.lon_input.value()

        return {
            # General
            "name":    self.name_input.text().strip(),
            "address": self.address_input.toPlainText().strip() or None,
            "is_active": self.active_check.isChecked(),
            # Ubicación
            "zone":      self.zone_input.text().strip() or None,
            "city":      self.city_input.text().strip() or None,
            "state":     self.state_input.text().strip() or None,
            "country":   self.country_input.text().strip() or None,
            "latitude":  lat if lat >= -90.0 else None,
            "longitude": lon if lon >= -180.0 else None,
            # Inventario
            "default_min_stock": self.min_stock_input.value() or None,
            "default_max_stock": self.max_stock_input.value() or None,
            "stock_alert_enabled": self.alert_check.isChecked(),
            # Capacidad / frecuencia
            "storage_capacity": self.capacity_input.text().strip() or None,
            "max_products":     self.max_products_input.value() or None,
            "count_frequency":  self.freq_combo.currentData(),
        }


# ═══════════════════════════════════════════════════════════════════════════
# StatusDialog  –  Cambiar estado operativo
# ═══════════════════════════════════════════════════════════════════════════
class StatusDialog(QDialog):
    """Small dialog to change the operational status of a branch."""

    def __init__(self, branch_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Estado operativo — {branch_data['name']}")
        self.setFixedWidth(360)
        self._setup_ui(branch_data.get("operational_status", "operativa"))

    def _setup_ui(self, current: str):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Selecciona el nuevo estado operativo:"))

        self.combo = QComboBox()
        for val in OPERATIONAL_STATUS_VALUES:
            self.combo.addItem(STATUS_LABELS.get(val, val), val)
        idx = self.combo.findData(current)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)
        layout.addWidget(self.combo)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok = QPushButton("Guardar")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)
        layout.addLayout(btn_row)

    def get_status(self) -> str:
        return self.combo.currentData()


# ═══════════════════════════════════════════════════════════════════════════
# ManagerDialog  –  Asignar / remover responsable
# ═══════════════════════════════════════════════════════════════════════════
class ManagerDialog(QDialog):
    """Dialog to assign or remove the manager of a branch."""

    def __init__(self, branch_data: dict, db: Session, parent=None):
        super().__init__(parent)
        self.db = db
        self.branch_data = branch_data
        self.setWindowTitle(f"Responsable — {branch_data['name']}")
        self.setFixedWidth(400)
        self._setup_ui()

    def _setup_ui(self):
        from models.user import User
        layout = QVBoxLayout(self)

        current_id = self.branch_data.get("manager_user_id")

        # Load active users
        users = (
            self.db.query(User)
            .filter(User.is_active == True)
            .order_by(User.name)
            .all()
        )

        layout.addWidget(QLabel("Asignar responsable de esta sucursal:"))

        self.user_combo = QComboBox()
        self.user_combo.addItem("(sin responsable)", None)
        for u in users:
            self.user_combo.addItem(f"{u.name}  ({u.email})", u.id)
        if current_id:
            idx = self.user_combo.findData(current_id)
            if idx >= 0:
                self.user_combo.setCurrentIndex(idx)
        layout.addWidget(self.user_combo)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok = QPushButton("Guardar")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)
        layout.addLayout(btn_row)

    def get_user_id(self) -> Optional[int]:
        """Returns selected user_id, or None if 'sin responsable'."""
        return self.user_combo.currentData()


# ═══════════════════════════════════════════════════════════════════════════
# BranchListView  –  Main view
# ═══════════════════════════════════════════════════════════════════════════
class BranchListView(QWidget):
    """Branch list view widget."""

    branch_selected = pyqtSignal(int)

    # Table columns: (header_label, data_key_or_None)
    _COLUMNS = [
        ("ID",               "id"),           # 0 – hidden
        ("Nombre",           "name"),          # 1
        ("Dirección",        "address"),       # 2
        ("Zona",             "zone"),          # 3
        ("Ciudad",           "city"),          # 4
        ("Estado operativo", "operational_status"),  # 5
        ("Responsable",      None),            # 6 – resolved separately
        ("Alertas stock",    "stock_alert_enabled"),  # 7
        ("Estado",           "is_active"),     # 8
        ("Acciones",         None),            # 9
    ]

    def __init__(self, db: Session, parent=None):
        super().__init__(parent)
        self.db = db
        self.service = BranchService(db)
        self._setup_ui()
        self.load_branches()

    # ── Setup ────────────────────────────────────────────────────────────
    def _setup_ui(self):
        root = QVBoxLayout(self)

        # ── Header row ──────────────────────────────────────────────────
        header = QHBoxLayout()

        title = QLabel("Gestión de Sucursales")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar sucursales…")
        self.search_input.setMaximumWidth(280)
        self.search_input.textChanged.connect(self._on_search)
        header.addWidget(self.search_input)

        add_btn = QPushButton("Nueva Sucursal")
        add_btn.clicked.connect(self._on_add)
        header.addWidget(add_btn)

        root.addLayout(header)

        # ── Table ────────────────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(len(self._COLUMNS))
        self.table.setHorizontalHeaderLabels([c[0] for c in self._COLUMNS])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnHidden(0, True)   # hide ID
        self.table.verticalHeader().setVisible(False)

        root.addWidget(self.table)

    # ── Load data ─────────────────────────────────────────────────────────
    def load_branches(self, search: str = None):
        """Populate the table with branches (and optional search filter)."""
        try:
            result = self.service.list_branches(page=1, page_size=200, search=search)
            branches = result["branches"]
        except Exception as e:
            logger.exception("Error loading branches")
            QMessageBox.critical(self, "Error", f"No se pudieron cargar las sucursales: {e}")
            return

        self.table.setRowCount(0)
        self.table.setRowCount(len(branches))

        for row, branch in enumerate(branches):
            bid = branch["id"]

            # 0 – ID (hidden)
            self.table.setItem(row, 0, QTableWidgetItem(str(bid)))

            # 1 – Nombre
            self.table.setItem(row, 1, QTableWidgetItem(branch["name"]))

            # 2 – Dirección
            self.table.setItem(row, 2, QTableWidgetItem(branch.get("address") or "—"))

            # 3 – Zona
            self.table.setItem(row, 3, QTableWidgetItem(branch.get("zone") or "—"))

            # 4 – Ciudad
            city_parts = [p for p in [branch.get("city"), branch.get("state")] if p]
            self.table.setItem(row, 4, QTableWidgetItem(", ".join(city_parts) or "—"))

            # 5 – Estado operativo (colored)
            op_status = branch.get("operational_status") or "operativa"
            op_item = QTableWidgetItem(STATUS_LABELS.get(op_status, op_status))
            color = STATUS_COLORS.get(op_status, "#000000")
            op_item.setForeground(QColor(color))
            self.table.setItem(row, 5, op_item)

            # 6 – Responsable
            manager_id = branch.get("manager_user_id")
            if manager_id:
                try:
                    detail = self.service.get_branch_with_manager(bid)
                    mgr = detail.get("manager") if detail else None
                    mgr_text = mgr["name"] if mgr else f"ID {manager_id}"
                except Exception:
                    mgr_text = f"ID {manager_id}"
            else:
                mgr_text = "—"
            self.table.setItem(row, 6, QTableWidgetItem(mgr_text))

            # 7 – Alertas stock
            alert_on = branch.get("stock_alert_enabled", True)
            alert_item = QTableWidgetItem("Sí" if alert_on else "No")
            alert_item.setForeground(QColor("#2e7d32" if alert_on else "#b71c1c"))
            self.table.setItem(row, 7, alert_item)

            # 8 – Activa
            active_item = QTableWidgetItem("Activa" if branch["is_active"] else "Inactiva")
            active_item.setForeground(
                QColor("#2e7d32" if branch["is_active"] else "#b71c1c")
            )
            self.table.setItem(row, 8, active_item)

            # 9 – Acciones
            self.table.setCellWidget(row, 9, self._make_actions(bid))

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(
            9, QHeaderView.ResizeMode.Fixed
        )
        self.table.setColumnWidth(9, 280)

    # ── Actions widget per row ─────────────────────────────────────────────
    def _make_actions(self, branch_id: int) -> QWidget:
        """Build the 'Editar / Estado / Responsable / Eliminar' button group."""
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(4)

        edit_btn = QPushButton("Editar")
        edit_btn.setFixedWidth(60)
        edit_btn.clicked.connect(lambda _, bid=branch_id: self._on_edit(bid))

        status_btn = QPushButton("Estado")
        status_btn.setFixedWidth(60)
        status_btn.clicked.connect(lambda _, bid=branch_id: self._on_change_status(bid))

        manager_btn = QPushButton("Responsable")
        manager_btn.setFixedWidth(90)
        manager_btn.clicked.connect(lambda _, bid=branch_id: self._on_assign_manager(bid))

        delete_btn = QPushButton("Eliminar")
        delete_btn.setFixedWidth(65)
        delete_btn.setStyleSheet("color: #b71c1c;")
        delete_btn.clicked.connect(lambda _, bid=branch_id: self._on_delete(bid))

        for btn in (edit_btn, status_btn, manager_btn, delete_btn):
            lay.addWidget(btn)

        return w

    # ── Handlers ──────────────────────────────────────────────────────────
    def _on_search(self, text: str):
        self.load_branches(search=text.strip() or None)

    def _on_add(self):
        dialog = BranchDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        if not data["name"]:
            QMessageBox.warning(self, "Error", "El nombre es requerido")
            return
        try:
            self.service.create_branch(data)
            QMessageBox.information(self, "Éxito", "Sucursal creada exitosamente")
            self.load_branches(self.search_input.text().strip() or None)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al crear sucursal:\n{e}")

    def _on_edit(self, branch_id: int):
        branch = self.service.get_branch(branch_id)
        if not branch:
            QMessageBox.warning(self, "Error", "Sucursal no encontrada")
            return
        dialog = BranchDialog(self, branch)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        if not data["name"]:
            QMessageBox.warning(self, "Error", "El nombre es requerido")
            return
        try:
            self.service.update_branch(branch_id, data)
            QMessageBox.information(self, "Éxito", "Sucursal actualizada")
            self.load_branches(self.search_input.text().strip() or None)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al actualizar sucursal:\n{e}")

    def _on_change_status(self, branch_id: int):
        branch = self.service.get_branch(branch_id)
        if not branch:
            return
        dialog = StatusDialog(branch, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        new_status = dialog.get_status()
        try:
            self.service.update_operational_status(branch_id, new_status)
            self.load_branches(self.search_input.text().strip() or None)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cambiar estado:\n{e}")

    def _on_assign_manager(self, branch_id: int):
        branch = self.service.get_branch(branch_id)
        if not branch:
            return
        dialog = ManagerDialog(branch, self.db, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        user_id = dialog.get_user_id()
        try:
            if user_id is None:
                self.service.remove_manager(branch_id)
                QMessageBox.information(self, "Éxito", "Responsable removido")
            else:
                self.service.assign_manager(branch_id, user_id)
                QMessageBox.information(self, "Éxito", "Responsable asignado")
            self.load_branches(self.search_input.text().strip() or None)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al asignar responsable:\n{e}")

    def _on_delete(self, branch_id: int):
        reply = QMessageBox.question(
            self, "Confirmar eliminación",
            "¿Está seguro de eliminar esta sucursal?\nSe desactivará (eliminación lógica).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete_branch(branch_id)
            QMessageBox.information(self, "Éxito", "Sucursal eliminada")
            self.load_branches(self.search_input.text().strip() or None)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al eliminar sucursal:\n{e}")

    # Kept for compatibility with MainWindow.refresh_current_view()
    def load_data(self):
        self.load_branches(self.search_input.text().strip() or None)
