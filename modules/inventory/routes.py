"""
Inventory GUI routes/controllers for PyQt6 interface.
Expansiones 1-9 integradas en la interfaz gráfica.
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel, QLineEdit,
    QMessageBox, QDialog, QFormLayout, QSpinBox, QComboBox,
    QGroupBox, QTabWidget, QTextEdit, QDoubleSpinBox,
    QCheckBox, QHeaderView, QFrame, QDialogButtonBox,
    QSizePolicy, QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from modules.inventory.service import InventoryService
from modules.products.service import ProductService
from modules.branches.service import BranchService
import logging

logger = logging.getLogger(__name__)

PRIORITY_LABELS = {"urgente": "🔴 Urgente", "normal": "🟡 Normal", "bajo": "🟢 Bajo"}
PRIORITY_COLORS = {"urgente": "#ffcccc", "normal": "#fff9cc", "bajo": "#ccffcc"}


# ═══════════════════════════════════════════════════════════════════════════
# InventoryItemDialog  –  Ver / editar un registro de inventario (con tabs)
# Cubre Expansiones 1, 2, 3, 4, 5, 6, 8
# ═══════════════════════════════════════════════════════════════════════════
class InventoryItemDialog(QDialog):
    """
    Diálogo para ver y editar todos los campos de un registro de inventario.
    Organizado en pestañas para no abrumar al usuario.
    """

    def __init__(self, db: Session, inventory_data: dict, parent=None):
        super().__init__(parent)
        self.db = db
        self.inventory_data = inventory_data
        self.service = InventoryService(db)
        self.setWindowTitle(
            f"Inventario — {inventory_data.get('product', {}).get('name', 'Producto')}"
            f" @ {inventory_data.get('branch', {}).get('name', 'Sucursal')}"
        )
        self.setMinimumWidth(520)
        self._setup_ui()


    def _setup_ui(self):
        root = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._tab_stock(),      "Stock")
        tabs.addTab(self._tab_ubicacion(),  "Ubicación")
        tabs.addTab(self._tab_tags(),       "Tags")
        tabs.addTab(self._tab_reposicion(), "Reposición")
        tabs.addTab(self._tab_alertas(),    "Alertas")
        tabs.addTab(self._tab_transito(),   "Tránsito")
        tabs.addTab(self._tab_valor(),      "Valor")
        root.addWidget(tabs)

        btns = QHBoxLayout()
        btns.addStretch()
        save = QPushButton("Guardar")
        save.setDefault(True)
        save.clicked.connect(self._on_save)
        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        btns.addWidget(save)
        btns.addWidget(cancel)
        root.addLayout(btns)

    # ── Tab 1: Stock (conteo físico + notas) ────────────────────────────
    def _tab_stock(self) -> QWidget:
        d = self.inventory_data
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(12, 12, 12, 12)

        form.addRow(QLabel(f"<b>Stock digital:</b> {d.get('digital_stock', 0)}"))
        form.addRow(QLabel(f"<b>Stock físico:</b>  {d.get('physical_stock', 0)}"))
        form.addRow(QLabel(f"<b>Diferencia:</b>    {d.get('difference', 0)}"))

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        form.addRow(sep)

        self.new_physical = QSpinBox()
        self.new_physical.setRange(0, 999999)
        self.new_physical.setValue(d.get("physical_stock", 0))
        form.addRow("Nuevo conteo físico:", self.new_physical)

        self.count_notes = QTextEdit()
        self.count_notes.setPlaceholderText("Notas del conteo (opcional)...")
        self.count_notes.setMaximumHeight(80)
        self.count_notes.setPlainText(d.get("last_count_notes") or "")
        form.addRow("Notas del conteo:", self.count_notes)

        self.min_stock = QSpinBox()
        self.min_stock.setRange(0, 999999)
        self.min_stock.setValue(d.get("min_stock", 0))
        form.addRow("Stock mínimo:", self.min_stock)

        return w

    # ── Tab 2: Ubicación física ──────────────────────────────────────────
    def _tab_ubicacion(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(12, 12, 12, 12)

        self.location_input = QLineEdit(self.inventory_data.get("location") or "")
        self.location_input.setPlaceholderText("ej. Pasillo 3, Anaquel B")
        form.addRow("Ubicación:", self.location_input)

        hint = QLabel("Indica dónde físicamente se encuentra este producto en la sucursal.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        form.addRow(hint)
        return w

    # ── Tab 3: Tags ──────────────────────────────────────────────────────
    def _tab_tags(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)

        layout.addWidget(QLabel("Tags actuales (separados por coma):"))
        self.tags_input = QLineEdit(self.inventory_data.get("tags") or "")
        self.tags_input.setPlaceholderText("fragil,alta-rotacion,perecedero")
        layout.addWidget(self.tags_input)

        hint = QLabel("Escribe los tags separados por coma. Se guardan en minúsculas.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(hint)
        layout.addStretch()
        return w

    # ── Tab 4: Reposición ────────────────────────────────────────────────
    def _tab_reposicion(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(12, 12, 12, 12)

        self.priority_combo = QComboBox()
        for value, label in PRIORITY_LABELS.items():
            self.priority_combo.addItem(label, value)
        current = self.inventory_data.get("reorder_priority", "normal")
        idx = self.priority_combo.findData(current)
        if idx >= 0:
            self.priority_combo.setCurrentIndex(idx)
        form.addRow("Prioridad de reposición:", self.priority_combo)

        hint = QLabel(
            "Urgente: reabastecer de inmediato.\n"
            "Normal: reabastecer en el próximo ciclo.\n"
            "Bajo: no urgente, stock de seguridad."
        )
        hint.setStyleSheet("color: gray; font-size: 11px;")
        form.addRow(hint)
        return w


    # ── Tab 5: Alertas personalizadas ────────────────────────────────────
    def _tab_alertas(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(12, 12, 12, 12)

        self.critical_thresh = QSpinBox()
        self.critical_thresh.setRange(0, 999999)
        self.critical_thresh.setSpecialValueText("(usar global)")
        val = self.inventory_data.get("critical_stock_threshold")
        self.critical_thresh.setValue(val if val is not None else 0)
        self._critical_enabled = QCheckBox("Activar umbral crítico personalizado")
        self._critical_enabled.setChecked(val is not None)
        self._critical_enabled.toggled.connect(self.critical_thresh.setEnabled)
        self.critical_thresh.setEnabled(val is not None)
        form.addRow(self._critical_enabled)
        form.addRow("Stock crítico (≤):", self.critical_thresh)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        form.addRow(sep)

        self.max_thresh = QSpinBox()
        self.max_thresh.setRange(0, 999999)
        self.max_thresh.setSpecialValueText("(desactivado)")
        max_val = self.inventory_data.get("max_stock_threshold")
        self.max_thresh.setValue(max_val if max_val is not None else 0)
        self._max_enabled = QCheckBox("Activar alerta de stock excedido")
        self._max_enabled.setChecked(max_val is not None)
        self._max_enabled.toggled.connect(self.max_thresh.setEnabled)
        self.max_thresh.setEnabled(max_val is not None)
        form.addRow(self._max_enabled)
        form.addRow("Stock máximo (>):", self.max_thresh)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        form.addRow(sep2)

        self.discrepancy_tol = QSpinBox()
        self.discrepancy_tol.setRange(0, 999999)
        self.discrepancy_tol.setValue(self.inventory_data.get("discrepancy_tolerance", 0))
        form.addRow("Tolerancia de discrepancia (unidades):", self.discrepancy_tol)

        hint = QLabel("Solo se marca discrepancia si |físico − digital| supera la tolerancia.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        form.addRow(hint)
        return w

    # ── Tab 6: Stock en tránsito ─────────────────────────────────────────
    def _tab_transito(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)

        current = self.inventory_data.get("in_transit_quantity", 0)
        layout.addWidget(QLabel(f"<b>En tránsito actual:</b> {current} unidades"))
        layout.addWidget(QLabel(f"<b>Stock disponible:</b> {self.inventory_data.get('available_stock', 0)} unidades"))

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        add_box = QGroupBox("Agregar al tránsito")
        add_form = QFormLayout(add_box)
        self.transit_add_spin = QSpinBox()
        self.transit_add_spin.setRange(1, 999999)
        add_form.addRow("Cantidad a agregar:", self.transit_add_spin)
        add_btn = QPushButton("Registrar envío en tránsito")
        add_btn.clicked.connect(self._on_add_transit)
        add_form.addRow(add_btn)
        layout.addWidget(add_box)

        recv_box = QGroupBox("Recibir del tránsito")
        recv_form = QFormLayout(recv_box)
        self.transit_recv_spin = QSpinBox()
        self.transit_recv_spin.setRange(1, 999999)
        recv_form.addRow("Cantidad a recibir:", self.transit_recv_spin)
        recv_btn = QPushButton("Confirmar recepción")
        recv_btn.clicked.connect(self._on_receive_transit)
        recv_form.addRow(recv_btn)
        layout.addWidget(recv_box)

        layout.addStretch()
        return w

    # ── Tab 7: Valor de inventario ────────────────────────────────────────
    def _tab_valor(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(12, 12, 12, 12)

        current_cost = self.inventory_data.get("unit_cost")
        current_value = self.inventory_data.get("inventory_value", 0.0)

        form.addRow(QLabel(f"<b>Valor actual del item:</b> ${current_value:,.2f}"))

        self.unit_cost_input = QDoubleSpinBox()
        self.unit_cost_input.setRange(0.0, 9999999.99)
        self.unit_cost_input.setDecimals(2)
        self.unit_cost_input.setPrefix("$ ")
        self.unit_cost_input.setSpecialValueText("(no definido)")
        self.unit_cost_input.setValue(current_cost if current_cost is not None else 0.0)
        form.addRow("Costo unitario:", self.unit_cost_input)

        hint = QLabel("El costo unitario puede diferir por sucursal.")
        hint.setStyleSheet("color: gray; font-size: 11px;")
        form.addRow(hint)
        return w


    # ── Acciones de tránsito (dentro del diálogo) ────────────────────────
    def _on_add_transit(self):
        qty = self.transit_add_spin.value()
        try:
            self.service.add_to_transit(
                self.inventory_data["product_id"],
                self.inventory_data["branch_id"],
                qty,
            )
            QMessageBox.information(self, "Éxito", f"+{qty} unidades registradas en tránsito.")
            self.inventory_data = self.service.get_inventory(self.inventory_data["id"]) or self.inventory_data
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_receive_transit(self):
        qty = self.transit_recv_spin.value()
        try:
            self.service.receive_transit(
                self.inventory_data["product_id"],
                self.inventory_data["branch_id"],
                qty,
            )
            QMessageBox.information(self, "Éxito", f"{qty} unidades recibidas del tránsito.")
            self.inventory_data = self.service.get_inventory(self.inventory_data["id"]) or self.inventory_data
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    # ── Guardar todos los cambios ────────────────────────────────────────
    def _on_save(self):
        inv_id = self.inventory_data["id"]
        product_id = self.inventory_data["product_id"]
        branch_id = self.inventory_data["branch_id"]
        try:
            # Stock físico + notas (Expansión 1 y 2)
            new_phys = self.new_physical.value()
            notes = self.count_notes.toPlainText().strip() or None
            if new_phys != self.inventory_data.get("physical_stock"):
                self.service.adjust_physical_stock(product_id, branch_id, new_phys, notes=notes)
            elif notes and notes != self.inventory_data.get("last_count_notes"):
                self.service.update_inventory(inv_id, {"last_count_notes": notes})

            # Campos de actualización directa
            update_fields: dict = {}

            # Ubicación (E1)
            loc = self.location_input.text().strip() or None
            update_fields["location"] = loc

            # Tags (E3) — normalizar a minúsculas sin espacios
            raw_tags = self.tags_input.text().strip()
            if raw_tags:
                cleaned = ",".join(t.strip().lower() for t in raw_tags.split(",") if t.strip())
                update_fields["tags"] = cleaned or None
            else:
                update_fields["tags"] = None

            # Prioridad (E4)
            update_fields["reorder_priority"] = self.priority_combo.currentData()

            # Alertas (E5)
            update_fields["critical_stock_threshold"] = (
                self.critical_thresh.value() if self._critical_enabled.isChecked() else None
            )
            update_fields["max_stock_threshold"] = (
                self.max_thresh.value() if self._max_enabled.isChecked() else None
            )
            update_fields["discrepancy_tolerance"] = self.discrepancy_tol.value()

            # Min stock
            update_fields["min_stock"] = self.min_stock.value()

            # Costo unitario (E8)
            cost_val = self.unit_cost_input.value()
            update_fields["unit_cost"] = cost_val if cost_val > 0 else None

            self.service.update_inventory(inv_id, update_fields)
            QMessageBox.information(self, "Éxito", "Cambios guardados correctamente.")
            self.accept()
        except Exception as e:
            logger.exception("Error saving inventory item")
            QMessageBox.critical(self, "Error", f"No se pudieron guardar los cambios:\n{e}")

    def get_data(self) -> dict:
        """Compatibilidad con código existente — retorna datos del diálogo."""
        return {
            "product_id": self.inventory_data["product_id"],
            "branch_id": self.inventory_data["branch_id"],
            "physical_stock": self.new_physical.value(),
        }


# ═══════════════════════════════════════════════════════════════════════════
# InventoryCountDialog  –  Conteo rápido (retrocompatible)
# ═══════════════════════════════════════════════════════════════════════════
class InventoryCountDialog(QDialog):
    """Dialog for recording inventory counts (quick entry, retrocompatible)."""

    def __init__(self, db: Session, parent=None, inventory_data: dict = None):
        super().__init__(parent)
        self.db = db
        self.inventory_data = inventory_data or {}
        self.product_service = ProductService(db)
        self.branch_service = BranchService(db)
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Conteo de Inventario")
        self.setMinimumWidth(420)
        layout = QFormLayout()

        self.product_combo = QComboBox()
        products = self.product_service.get_all_active_products()
        sel_p = 0
        for i, p in enumerate(products):
            self.product_combo.addItem(f"{p['sku']} - {p['name']}", p["id"])
            if p["id"] == self.inventory_data.get("product_id"):
                sel_p = i
        self.product_combo.setCurrentIndex(sel_p)
        layout.addRow("Producto:", self.product_combo)

        self.branch_combo = QComboBox()
        branches = self.branch_service.get_all_active_branches()
        sel_b = 0
        for i, b in enumerate(branches):
            self.branch_combo.addItem(b["name"], b["id"])
            if b["id"] == self.inventory_data.get("branch_id"):
                sel_b = i
        self.branch_combo.setCurrentIndex(sel_b)
        layout.addRow("Sucursal:", self.branch_combo)

        self.physical_stock = QSpinBox()
        self.physical_stock.setRange(0, 999999)
        self.physical_stock.setValue(self.inventory_data.get("physical_stock", 0))
        layout.addRow("Stock Físico:", self.physical_stock)

        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("Notas del conteo (opcional)")
        layout.addRow("Notas:", self.notes_input)

        btn_row = QHBoxLayout()
        save = QPushButton("Guardar"); save.clicked.connect(self.accept)
        cancel = QPushButton("Cancelar"); cancel.clicked.connect(self.reject)
        btn_row.addWidget(save); btn_row.addWidget(cancel)
        layout.addRow(btn_row)
        self.setLayout(layout)

    def get_data(self) -> dict:
        return {
            "product_id": self.product_combo.currentData(),
            "branch_id": self.branch_combo.currentData(),
            "physical_stock": self.physical_stock.value(),
            "notes": self.notes_input.text().strip() or None,
        }


# ═══════════════════════════════════════════════════════════════════════════
# InventoryHistoryDialog  –  Historial de cambios de un item (Expansión 7)
# ═══════════════════════════════════════════════════════════════════════════
class InventoryHistoryDialog(QDialog):
    """Muestra el historial de cambios de stock de un item."""

    def __init__(self, db: Session, inventory_id: int, product_name: str, parent=None):
        super().__init__(parent)
        self.db = db
        self.inventory_id = inventory_id
        self.service = InventoryService(db)
        self.setWindowTitle(f"Historial de stock — {product_name}")
        self.setMinimumSize(700, 420)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Fecha", "Tipo", "Físico antes", "Físico nuevo",
            "Digital antes", "Digital nuevo", "Razón / Notas",
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        close = QPushButton("Cerrar")
        close.clicked.connect(self.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)

        self._load()

    def _load(self):
        try:
            result = self.service.get_stock_history(self.inventory_id, limit=100)
            records = result.get("records", [])
            self.table.setRowCount(len(records))
            for row, r in enumerate(records):
                created = (r.get("created_at") or "")[:19].replace("T", " ")
                self.table.setItem(row, 0, QTableWidgetItem(created))
                self.table.setItem(row, 1, QTableWidgetItem(r.get("change_type", "")))
                self.table.setItem(row, 2, QTableWidgetItem(str(r.get("previous_physical", 0))))
                self.table.setItem(row, 3, QTableWidgetItem(str(r.get("new_physical", 0))))
                self.table.setItem(row, 4, QTableWidgetItem(str(r.get("previous_digital", 0))))
                self.table.setItem(row, 5, QTableWidgetItem(str(r.get("new_digital", 0))))
                self.table.setItem(row, 6, QTableWidgetItem(r.get("reason") or ""))
            self.table.resizeColumnsToContents()
        except Exception as e:
            logger.exception("Error loading inventory history")
            QMessageBox.critical(self, "Error", f"No se pudo cargar el historial:\n{e}")


# ═══════════════════════════════════════════════════════════════════════════
# InventoryMetricsDialog  –  Métricas y reportes del módulo (Expansión 9)
# ═══════════════════════════════════════════════════════════════════════════
class InventoryMetricsDialog(QDialog):
    """Diálogo de métricas, reportes y sugerencias de reposición."""

    def __init__(self, db: Session, branch_id: Optional[int], branch_name: str, parent=None):
        super().__init__(parent)
        self.db = db
        self.branch_id = branch_id
        self.service = InventoryService(db)
        self.setWindowTitle(f"Métricas de Inventario — {branch_name or 'Todas las sucursales'}")
        self.setMinimumSize(760, 520)
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._tab_reorden(),    "Sugerencias de Reposición")
        tabs.addTab(self._tab_valor(),      "Valor de Inventario")
        tabs.addTab(self._tab_sin_movim(),  "Sin Movimiento")
        tabs.addTab(self._tab_discrepancias(), "Tasa de Discrepancias")
        tabs.addTab(self._tab_edad(),       "Antigüedad de Stocks")
        root.addWidget(tabs)
        close = QPushButton("Cerrar")
        close.clicked.connect(self.accept)
        root.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)

    def _make_table(self, headers: list) -> QTableWidget:
        t = QTableWidget()
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        t.horizontalHeader().setStretchLastSection(True)
        return t

    def _tab_reorden(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        if not self.branch_id:
            layout.addWidget(QLabel("Selecciona una sucursal para ver sugerencias."))
            return w
        try:
            items = self.service.get_reorder_suggestions(self.branch_id)
            t = self._make_table(["Producto", "SKU", "Stock Digital", "Min Stock", "Prioridad", "Sugerido pedir"])
            t.setRowCount(len(items))
            for row, item in enumerate(items):
                p = item.get("product", {})
                t.setItem(row, 0, QTableWidgetItem(p.get("name", "")))
                t.setItem(row, 1, QTableWidgetItem(p.get("sku", "")))
                t.setItem(row, 2, QTableWidgetItem(str(item.get("digital_stock", 0))))
                t.setItem(row, 3, QTableWidgetItem(str(item.get("min_stock", 0))))
                prio = item.get("reorder_priority", "normal")
                prio_item = QTableWidgetItem(PRIORITY_LABELS.get(prio, prio))
                color = PRIORITY_COLORS.get(prio, "#ffffff")
                prio_item.setBackground(QColor(color))
                t.setItem(row, 4, prio_item)
                t.setItem(row, 5, QTableWidgetItem(str(item.get("suggested_order_qty", 0))))
            t.resizeColumnsToContents()
            layout.addWidget(t)
        except Exception as e:
            layout.addWidget(QLabel(f"Error: {e}"))
        return w

    def _tab_valor(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        try:
            val = self.service.get_inventory_value(self.branch_id)
            lbl = QLabel(f"<b>Valor total del inventario: ${val['total_value']:,.2f}</b>")
            lbl.setStyleSheet("font-size: 16px; padding: 8px;")
            layout.addWidget(lbl)
            if self.branch_id:
                top = self.service.get_most_valuable_items(self.branch_id, limit=15)
                t = self._make_table(["Producto", "SKU", "Stock", "Costo unit.", "Valor total"])
                t.setRowCount(len(top))
                for row, item in enumerate(top):
                    t.setItem(row, 0, QTableWidgetItem(item.get("product_name", "")))
                    t.setItem(row, 1, QTableWidgetItem(item.get("product_sku", "")))
                    t.setItem(row, 2, QTableWidgetItem(str(item.get("digital_stock", 0))))
                    t.setItem(row, 3, QTableWidgetItem(f"${item.get('unit_cost', 0):,.2f}"))
                    t.setItem(row, 4, QTableWidgetItem(f"${item.get('total_value', 0):,.2f}"))
                t.resizeColumnsToContents()
                layout.addWidget(QLabel("Top 15 items por valor:"))
                layout.addWidget(t)
        except Exception as e:
            layout.addWidget(QLabel(f"Error: {e}"))
        return w

    def _tab_sin_movim(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        if not self.branch_id:
            layout.addWidget(QLabel("Selecciona una sucursal para ver esta métrica."))
            return w
        try:
            items = self.service.get_no_movement_products(self.branch_id, days=30)
            t = self._make_table(["Producto", "SKU", "Stock Digital", "Última fecha de conteo"])
            t.setRowCount(len(items))
            for row, item in enumerate(items):
                p = item.get("product", {})
                t.setItem(row, 0, QTableWidgetItem(p.get("name", "")))
                t.setItem(row, 1, QTableWidgetItem(p.get("sku", "")))
                t.setItem(row, 2, QTableWidgetItem(str(item.get("digital_stock", 0))))
                lc = (item.get("last_count_date") or "Sin conteo")[:10]
                t.setItem(row, 3, QTableWidgetItem(lc))
            t.resizeColumnsToContents()
            layout.addWidget(QLabel(f"Productos sin movimiento en los últimos 30 días: {len(items)}"))
            layout.addWidget(t)
        except Exception as e:
            layout.addWidget(QLabel(f"Error: {e}"))
        return w

    def _tab_discrepancias(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        if not self.branch_id:
            layout.addWidget(QLabel("Selecciona una sucursal para ver esta métrica."))
            return w
        try:
            rate = self.service.get_discrepancy_rate_by_branch(self.branch_id)
            lbl = QLabel(
                f"<b>Tasa de discrepancia: {rate['discrepancy_rate_percent']}%</b><br>"
                f"Items totales: {rate['total_items']} | "
                f"Con discrepancia: {rate['items_with_discrepancy']}"
            )
            lbl.setStyleSheet("font-size: 13px; padding: 8px;")
            layout.addWidget(lbl)
        except Exception as e:
            layout.addWidget(QLabel(f"Error: {e}"))
        layout.addStretch()
        return w

    def _tab_edad(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        if not self.branch_id:
            layout.addWidget(QLabel("Selecciona una sucursal para ver esta métrica."))
            return w
        try:
            data = self.service.get_inventory_age_distribution(self.branch_id)
            dist = data.get("distribution", {})
            total = data.get("total", 0)
            text = (
                f"<b>Antigüedad de stocks (total: {total} items)</b><br><br>"
                f"🔵 Sin conteo registrado: <b>{dist.get('sin_conteo', 0)}</b><br>"
                f"🟢 Conteo reciente (≤7 días): <b>{dist.get('reciente_7d', 0)}</b><br>"
                f"🟡 Moderado (7–30 días): <b>{dist.get('moderado_7_30d', 0)}</b><br>"
                f"🔴 Antiguo (>30 días): <b>{dist.get('antiguo_mas_30d', 0)}</b>"
            )
            lbl = QLabel(text)
            lbl.setStyleSheet("font-size: 13px; padding: 8px;")
            layout.addWidget(lbl)
        except Exception as e:
            layout.addWidget(QLabel(f"Error: {e}"))
        layout.addStretch()
        return w


# ═══════════════════════════════════════════════════════════════════════════
# InventoryListView  –  Vista principal (tabla expandida + todos los botones)
# ═══════════════════════════════════════════════════════════════════════════
class InventoryListView(QWidget):
    """Inventory list view widget — with all expansion features visible."""

    inventory_selected = pyqtSignal(int)

    # Columnas visibles de la tabla principal
    _COLUMNS = [
        ("ID",            "id"),                  # 0 – oculto
        ("Sucursal",      None),                  # 1
        ("Producto",      None),                  # 2
        ("Físico",        "physical_stock"),       # 3
        ("Digital",       "digital_stock"),        # 4
        ("Diferencia",    "difference"),           # 5
        ("Tránsito",      "in_transit_quantity"),  # 6
        ("Disponible",    "available_stock"),      # 7
        ("Min",           "min_stock"),            # 8
        ("Prioridad",     "reorder_priority"),     # 9
        ("Ubicación",     "location"),             # 10
        ("Tags",          "tags"),                 # 11
        ("Estado",        None),                   # 12
        ("Acciones",      None),                   # 13
    ]

    def __init__(self, db: Session, parent=None):
        super().__init__(parent)
        self.db = db
        self.service = InventoryService(db)
        self.branch_service = BranchService(db)
        self.product_service = ProductService(db)
        self.current_branch_id = None
        self.show_discrepancies_only = False
        self.show_low_stock_only = False
        self.setup_ui()
        self.load_inventory()

    # ── UI setup ─────────────────────────────────────────────────────────
    def setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Header ───────────────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("Gestión de Inventario")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        self.branch_combo = QComboBox()
        self.branch_combo.addItem("Todas las sucursales", None)
        for b in self.branch_service.get_all_active_branches():
            self.branch_combo.addItem(b["name"], b["id"])
        self.branch_combo.currentIndexChanged.connect(self.on_branch_changed)
        header.addWidget(QLabel("Sucursal:"))
        header.addWidget(self.branch_combo)
        layout.addLayout(header)

        # ── Barra de filtros ─────────────────────────────────────────────
        filters = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar producto, SKU o sucursal…")
        self.search_input.setMaximumWidth(260)
        self.search_input.textChanged.connect(self.on_search)
        filters.addWidget(self.search_input)

        self.discrepancy_btn = QPushButton("Solo Discrepancias")
        self.discrepancy_btn.setCheckable(True)
        self.discrepancy_btn.clicked.connect(self.toggle_discrepancy_filter)
        filters.addWidget(self.discrepancy_btn)

        self.low_stock_btn = QPushButton("Solo Stock Bajo")
        self.low_stock_btn.setCheckable(True)
        self.low_stock_btn.clicked.connect(self.toggle_low_stock_filter)
        filters.addWidget(self.low_stock_btn)

        filters.addStretch()
        layout.addLayout(filters)

        # ── Barra de acciones ────────────────────────────────────────────
        actions = QHBoxLayout()

        self.count_button = QPushButton("📋 Registrar Conteo")
        self.count_button.clicked.connect(self.on_count_inventory)
        actions.addWidget(self.count_button)

        self.global_view_btn = QPushButton("🌐 Vista Global")
        self.global_view_btn.setCheckable(True)
        self.global_view_btn.clicked.connect(self.toggle_global_view)
        actions.addWidget(self.global_view_btn)

        self.distribution_btn = QPushButton("📊 Distribución por Producto")
        self.distribution_btn.clicked.connect(self.show_product_distribution)
        actions.addWidget(self.distribution_btn)

        self.metrics_btn = QPushButton("📈 Métricas")
        self.metrics_btn.clicked.connect(self.show_metrics)
        actions.addWidget(self.metrics_btn)

        self.reorder_btn = QPushButton("🔄 Reposición Urgente")
        self.reorder_btn.clicked.connect(self.show_reorder_report)
        actions.addWidget(self.reorder_btn)

        actions.addStretch()
        layout.addLayout(actions)

        # ── Tabla ─────────────────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(len(self._COLUMNS))
        self.table.setHorizontalHeaderLabels([c[0] for c in self._COLUMNS])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setColumnHidden(0, True)   # ID oculto
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        # ── Resumen ───────────────────────────────────────────────────────
        summary_box = QGroupBox("Resumen")
        summary_row = QHBoxLayout(summary_box)
        self.total_physical_label  = QLabel("Físico Total: 0")
        self.total_digital_label   = QLabel("Digital Total: 0")
        self.discrepancy_label     = QLabel("Discrepancias: 0")
        self.low_stock_label       = QLabel("Stock Bajo: 0")
        self.value_label           = QLabel("Valor: $0.00")
        for lbl in [self.total_physical_label, self.total_digital_label,
                    self.discrepancy_label, self.low_stock_label, self.value_label]:
            summary_row.addWidget(lbl)
        layout.addWidget(summary_box)

    # ── Carga y renderizado de datos ──────────────────────────────────────
    def load_inventory(self, search: str = None):
        """Carga el inventario en la tabla con todos los campos nuevos."""
        try:
            result = self.service.list_inventory(
                page=1, page_size=200,
                branch_id=self.current_branch_id,
                low_stock_only=self.show_low_stock_only,
                discrepancy_only=self.show_discrepancies_only,
                search=search,
            )
        except Exception as e:
            logger.exception("Error loading inventory")
            QMessageBox.critical(self, "Error", f"No se pudo cargar el inventario:\n{e}")
            return

        items = result["inventory"]
        self.table.setRowCount(len(items))

        for row, item in enumerate(items):
            self.table.setItem(row, 0, QTableWidgetItem(str(item["id"])))

            branch_name = item.get("branch", {}).get("name", "N/A")
            self.table.setItem(row, 1, QTableWidgetItem(branch_name))

            p = item.get("product", {})
            self.table.setItem(row, 2, QTableWidgetItem(f"{p.get('sku','')} - {p.get('name','')}"))

            self.table.setItem(row, 3, QTableWidgetItem(str(item["physical_stock"])))
            self.table.setItem(row, 4, QTableWidgetItem(str(item["digital_stock"])))

            diff = item["difference"]
            diff_cell = QTableWidgetItem(str(diff))
            if diff != 0:
                diff_cell.setBackground(QColor("#ffee88") if diff > 0 else QColor("#ffaaaa"))
            self.table.setItem(row, 5, diff_cell)

            transit = item.get("in_transit_quantity", 0)
            t_cell = QTableWidgetItem(str(transit))
            if transit > 0:
                t_cell.setBackground(QColor("#cce5ff"))
            self.table.setItem(row, 6, t_cell)

            self.table.setItem(row, 7, QTableWidgetItem(str(item.get("available_stock", item["digital_stock"]))))
            self.table.setItem(row, 8, QTableWidgetItem(str(item.get("min_stock", 0))))

            prio = item.get("reorder_priority", "normal")
            prio_cell = QTableWidgetItem(PRIORITY_LABELS.get(prio, prio))
            prio_cell.setBackground(QColor(PRIORITY_COLORS.get(prio, "#ffffff")))
            self.table.setItem(row, 9, prio_cell)

            self.table.setItem(row, 10, QTableWidgetItem(item.get("location") or ""))
            self.table.setItem(row, 11, QTableWidgetItem(item.get("tags") or ""))

            # Estado compuesto
            if item.get("is_critical_stock"):
                status, color = "🔴 Crítico", "#ffcccc"
            elif item["has_discrepancy"]:
                status, color = "⚠ Discrepancia", "#fff3cd"
            elif item["is_low_stock"]:
                status, color = "📉 Stock Bajo", "#ffeeba"
            elif item.get("is_exceeding_max"):
                status, color = "📈 Excedido", "#d4edda"
            else:
                status, color = "✅ OK", "#d4edda"
            st_cell = QTableWidgetItem(status)
            st_cell.setBackground(QColor(color))
            self.table.setItem(row, 12, st_cell)

            # Botones de acción por fila
            self.table.setCellWidget(row, 13, self._make_actions(item))

        self.table.resizeColumnsToContents()
        self.update_summary()

    def _make_actions(self, item: dict) -> QWidget:
        """Crea el widget de botones de acción para una fila."""
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(4)

        edit_btn = QPushButton("✏ Editar")
        edit_btn.setFixedHeight(26)
        edit_btn.clicked.connect(lambda _, i=item: self._on_edit_item(i))
        lay.addWidget(edit_btn)

        hist_btn = QPushButton("📜 Historial")
        hist_btn.setFixedHeight(26)
        hist_btn.clicked.connect(lambda _, i=item: self._on_show_history(i))
        lay.addWidget(hist_btn)

        return w

    def update_summary(self):
        totals = self.service.get_totals(self.current_branch_id)
        self.total_physical_label.setText(f"Físico Total: {totals['total_physical_stock']}")
        self.total_digital_label.setText(f"Digital Total: {totals['total_digital_stock']}")
        self.discrepancy_label.setText(f"Discrepancias: {totals['discrepancy_count']}")
        self.low_stock_label.setText(f"Stock Bajo: {totals['low_stock_count']}")
        try:
            val = self.service.get_inventory_value(self.current_branch_id)
            self.value_label.setText(f"Valor: ${val['total_value']:,.2f}")
        except Exception:
            self.value_label.setText("Valor: N/D")

    # Alias para el refresh genérico de MainWindow
    def load_data(self):
        self.load_inventory(self.search_input.text() or None)

    # ── Handlers de filtros ───────────────────────────────────────────────
    def on_branch_changed(self, _):
        self.current_branch_id = self.branch_combo.currentData()
        self.load_inventory(self.search_input.text() or None)

    def on_search(self, text: str):
        self.load_inventory(search=text if text else None)

    def toggle_discrepancy_filter(self, checked: bool):
        self.show_discrepancies_only = checked
        if checked:
            self.show_low_stock_only = False
            self.low_stock_btn.setChecked(False)
        self.load_inventory(self.search_input.text() or None)

    def toggle_low_stock_filter(self, checked: bool):
        self.show_low_stock_only = checked
        if checked:
            self.show_discrepancies_only = False
            self.discrepancy_btn.setChecked(False)
        self.load_inventory(self.search_input.text() or None)

    def toggle_global_view(self, checked: bool):
        if checked:
            self.load_global_inventory()
        else:
            self.load_inventory(self.search_input.text() or None)


    # ── Acciones del toolbar ──────────────────────────────────────────────
    def on_count_inventory(self):
        """Registrar conteo rápido (retrocompatible)."""
        dialog = InventoryCountDialog(self.db, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                data = dialog.get_data()
                self.service.adjust_physical_stock(
                    data["product_id"],
                    data["branch_id"],
                    data["physical_stock"],
                    notes=data.get("notes"),
                )
                QMessageBox.information(self, "Éxito", "Conteo registrado exitosamente.")
                self.load_inventory(self.search_input.text() or None)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al registrar conteo:\n{e}")

    def show_metrics(self):
        """Abrir diálogo de métricas (Expansión 9)."""
        branch_id = self.current_branch_id
        branch_name = self.branch_combo.currentText()
        dialog = InventoryMetricsDialog(self.db, branch_id, branch_name, parent=self)
        dialog.exec()

    def show_reorder_report(self):
        """Mostrar reporte de reposición ordenado por prioridad (Expansión 4)."""
        branch_id = self.current_branch_id
        if not branch_id:
            QMessageBox.information(self, "Info", "Selecciona una sucursal para ver el reporte de reposición.")
            return
        try:
            report = self.service.get_reorder_report(branch_id)
            total = report["total"]
            if total == 0:
                QMessageBox.information(self, "Reposición", "No hay items con stock bajo en esta sucursal.")
                return
            # Reutilizar el diálogo de métricas abierto en la pestaña de reposición
            dialog = InventoryMetricsDialog(self.db, branch_id, self.branch_combo.currentText(), parent=self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    # ── Acciones por fila ─────────────────────────────────────────────────
    def _on_edit_item(self, item: dict):
        """Abrir diálogo de edición completo (tabs con todas las expansiones)."""
        # Enriquecer con detalles si no están incluidos
        if "product" not in item or "branch" not in item:
            full = self.service.get_inventory(item["id"])
            if full:
                item = full
        dialog = InventoryItemDialog(self.db, item, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_inventory(self.search_input.text() or None)

    def _on_show_history(self, item: dict):
        """Abrir diálogo de historial de cambios (Expansión 7)."""
        product_name = item.get("product", {}).get("name", f"ID {item['id']}")
        dialog = InventoryHistoryDialog(self.db, item["id"], product_name, parent=self)
        dialog.exec()

    # ── Ajustar (retrocompatible — usado desde código externo) ─────────────
    def on_adjust_inventory(self, inventory_id: int):
        inventory = self.service.get_inventory(inventory_id)
        if not inventory:
            QMessageBox.warning(self, "Error", "No se encontró el registro de inventario.")
            return
        self._on_edit_item(inventory)

    # ── Vista global ──────────────────────────────────────────────────────
    def load_global_inventory(self, search: str = None):
        try:
            result = self.service.get_global_inventory(page=1, page_size=200, search=search)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        items = result["inventory"]
        self.table.setRowCount(len(items))

        for row, item in enumerate(items):
            self.table.setItem(row, 0, QTableWidgetItem(str(item["product_id"])))
            self.table.setItem(row, 1, QTableWidgetItem("Todas"))
            self.table.setItem(row, 2, QTableWidgetItem(f"{item.get('sku','')} - {item.get('name','')}"))
            self.table.setItem(row, 3, QTableWidgetItem(str(item["total_physical_stock"])))
            self.table.setItem(row, 4, QTableWidgetItem(str(item["total_digital_stock"])))
            diff = item["total_physical_stock"] - item["total_digital_stock"]
            diff_cell = QTableWidgetItem(str(diff))
            if diff != 0:
                diff_cell.setBackground(QColor("#ffee88") if diff > 0 else QColor("#ffaaaa"))
            self.table.setItem(row, 5, diff_cell)
            # Columnas no aplican en vista global
            for col in [6, 7, 8, 9, 10, 11]:
                self.table.setItem(row, col, QTableWidgetItem("—"))
            self.table.setItem(row, 12, QTableWidgetItem("Global"))

            w = QWidget()
            lay = QHBoxLayout(w); lay.setContentsMargins(4, 2, 4, 2)
            dist_btn = QPushButton("Ver distribución")
            dist_btn.setFixedHeight(26)
            dist_btn.clicked.connect(
                lambda _, pid=item["product_id"]: self.show_product_distribution_for_product(pid)
            )
            lay.addWidget(dist_btn)
            self.table.setCellWidget(row, 13, w)

        self.table.resizeColumnsToContents()

    # ── Distribución por producto ─────────────────────────────────────────
    def show_product_distribution(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Seleccionar Producto")
        layout = QFormLayout()
        combo = QComboBox()
        for p in self.product_service.get_all_active_products():
            combo.addItem(f"{p['sku']} - {p['name']}", p["id"])
        layout.addRow("Producto:", combo)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)
        dialog.setLayout(layout)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.show_product_distribution_for_product(combo.currentData())

    def show_product_distribution_for_product(self, product_id: int):
        dist = self.service.get_product_stock_across_branches(product_id)
        if not dist:
            QMessageBox.information(self, "Info", "No hay stock de este producto en ninguna sucursal.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Distribución por Sucursal")
        dialog.setMinimumWidth(560)
        layout = QVBoxLayout(dialog)
        t = QTableWidget()
        t.setColumnCount(5)
        t.setHorizontalHeaderLabels(["Sucursal", "Físico", "Digital", "Diferencia", "Estado"])
        t.setRowCount(len(dist))
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row, item in enumerate(dist):
            t.setItem(row, 0, QTableWidgetItem(item.get("branch_name", "")))
            t.setItem(row, 1, QTableWidgetItem(str(item["physical_stock"])))
            t.setItem(row, 2, QTableWidgetItem(str(item["digital_stock"])))
            diff = item["difference"]
            dc = QTableWidgetItem(str(diff))
            if diff != 0:
                dc.setBackground(QColor("#ffee88") if diff > 0 else QColor("#ffaaaa"))
            t.setItem(row, 3, dc)
            status = "⚠ Discrepancia" if item["has_discrepancy"] else ("📉 Bajo" if item["is_low_stock"] else "✅ OK")
            t.setItem(row, 4, QTableWidgetItem(status))
        t.resizeColumnsToContents()
        layout.addWidget(t)
        close = QPushButton("Cerrar")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        dialog.exec()
