"""
Inventory GUI routes/controllers for PyQt6 interface.
Expansiones 1-9 integradas en la interfaz gráfica.
Operation-mode aware: Matrix = all branches visible; Branch = scoped to one branch.
"""

from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel, QLineEdit,
    QMessageBox, QDialog, QFormLayout, QSpinBox, QComboBox,
    QGroupBox, QTabWidget, QTextEdit, QDoubleSpinBox,
    QCheckBox, QHeaderView, QFrame, QDialogButtonBox,
    QSizePolicy, QScrollArea, QDateEdit, QDateTimeEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QDate, QDateTime
from PyQt6.QtGui import QColor, QFont

from modules.inventory.service import InventoryService
from modules.products.service import ProductService
from modules.branches.service import BranchService
from core.operation_mode import operation_mode, MODE_MATRIX, MODE_BRANCH
from core.event_bus import event_bus
from core.settings import settings
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
        tabs.addTab(self._tab_lotes(),      "Lotes")
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

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        form.addRow(sep2)

        self.new_digital = QSpinBox()
        self.new_digital.setRange(0, 999999)
        self.new_digital.setValue(d.get("digital_stock", 0))
        self.new_digital.valueChanged.connect(self._on_digital_changed)
        form.addRow("Ajustar stock digital:", self.new_digital)

        self.adjustment_reason = QLineEdit()
        self.adjustment_reason.setPlaceholderText("Motivo del ajuste digital (opcional)")
        self.adjustment_reason.setEnabled(False)
        form.addRow("Motivo del ajuste:", self.adjustment_reason)

        self.adjusted_by_name = QLineEdit()
        self.adjusted_by_name.setPlaceholderText("Nombre de quien ajusta (opcional)")
        self.adjusted_by_name.setEnabled(False)
        form.addRow("Ajustado por:", self.adjusted_by_name)

        sep3 = QFrame(); sep3.setFrameShape(QFrame.Shape.HLine)
        form.addRow(sep3)

        self.alternate_unit_input = QLineEdit(d.get("alternate_unit") or "")
        self.alternate_unit_input.setPlaceholderText("ej. caja, kg, litro")
        form.addRow("Unidad alternativa:", self.alternate_unit_input)

        self.conversion_factor_input = QDoubleSpinBox()
        self.conversion_factor_input.setRange(0.0, 999999.99)
        self.conversion_factor_input.setDecimals(4)
        self.conversion_factor_input.setSpecialValueText("(no definido)")
        cf = d.get("conversion_factor")
        self.conversion_factor_input.setValue(cf if cf else 0.0)
        form.addRow("Factor de conversión:", self.conversion_factor_input)

        if d.get("alternate_unit") and d.get("stock_in_alternate_unit") is not None:
            form.addRow(
                QLabel(
                    f"<b>Stock en {d['alternate_unit']}:</b> "
                    f"{d['stock_in_alternate_unit']:.2f}"
                )
            )

        return w

    def _on_digital_changed(self, value):
        original = self.inventory_data.get("digital_stock", 0)
        changed = value != original
        self.adjustment_reason.setEnabled(changed)
        self.adjusted_by_name.setEnabled(changed)

    # ── Tab 2: Ubicación física ──────────────────────────────────────────
    def _tab_ubicacion(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(12, 12, 12, 12)

        d = self.inventory_data

        self.location_input = QLineEdit(d.get("location_free") or d.get("location") or "")
        self.location_input.setPlaceholderText("ej. Bodega principal, Refrigerador 2")
        form.addRow("Ubicación libre:", self.location_input)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        form.addRow(sep)
        form.addRow(QLabel("<b>Ubicación jerárquica (opcional)</b>"))

        self.aisle_input = QLineEdit(d.get("aisle") or "")
        self.aisle_input.setPlaceholderText("Pasillo")
        form.addRow("Pasillo:", self.aisle_input)

        self.shelf_input = QLineEdit(d.get("shelf") or "")
        self.shelf_input.setPlaceholderText("Anaquel")
        form.addRow("Anaquel:", self.shelf_input)

        self.level_input = QLineEdit(d.get("level") or "")
        self.level_input.setPlaceholderText("Nivel")
        form.addRow("Nivel:", self.level_input)

        self.bin_input = QLineEdit(d.get("bin") or "")
        self.bin_input.setPlaceholderText("Posición")
        form.addRow("Posición:", self.bin_input)

        path = d.get("location_path") or ""
        self.location_path_label = QLabel(path or "(sin ubicación definida)")
        self.location_path_label.setStyleSheet("color: #1565c0; font-style: italic;")
        form.addRow("Vista previa:", self.location_path_label)

        for widget in (self.aisle_input, self.shelf_input, self.level_input, self.bin_input):
            widget.textChanged.connect(self._update_location_preview)

        hint = QLabel("Usa ubicación libre, jerárquica, o ambas según necesites.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        form.addRow(hint)
        return w

    def _update_location_preview(self):
        parts = []
        if self.aisle_input.text().strip():
            parts.append(f"Pasillo {self.aisle_input.text().strip()}")
        if self.shelf_input.text().strip():
            parts.append(f"Anaquel {self.shelf_input.text().strip()}")
        if self.level_input.text().strip():
            parts.append(f"Nivel {self.level_input.text().strip()}")
        if self.bin_input.text().strip():
            parts.append(f"Posición {self.bin_input.text().strip()}")
        if parts:
            self.location_path_label.setText(" > ".join(parts))
        else:
            free = self.location_input.text().strip()
            self.location_path_label.setText(free or "(sin ubicación definida)")

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

    # ── Tab 7: Lotes y fechas de caducidad ──────────────────────────────
    def _tab_lotes(self) -> QWidget:
        """Tab de gestión de lotes para el item de inventario."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(12, 12, 12, 12)

        inv_id = self.inventory_data.get("id")

        # Resumen de lotes
        try:
            summary = self.service.get_batch_summary(inv_id) if inv_id else {}
        except Exception:
            summary = {}

        batch_count = summary.get("batch_count", 0)
        batch_total = summary.get("batch_total_quantity", 0)
        info_lbl = QLabel(
            f"<b>Lotes registrados:</b> {batch_count} | "
            f"<b>Cantidad total en lotes:</b> {batch_total}"
        )
        layout.addWidget(info_lbl)

        # Botón agregar lote
        add_btn = QPushButton("+ Agregar Lote")
        add_btn.setFixedWidth(160)
        add_btn.clicked.connect(lambda: self._on_add_batch(inv_id, lotes_table))
        layout.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # Tabla de lotes existentes
        lotes_table = QTableWidget()
        lotes_table.setColumnCount(6)
        lotes_table.setHorizontalHeaderLabels([
            "Nº Lote", "Fabricación", "Caducidad", "Cantidad", "Costo unit.", "Notas"
        ])
        lotes_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lotes_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        lotes_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(lotes_table)

        # Botón FIFO consume
        consume_box = QGroupBox("Consumir (FIFO)")
        consume_form = QFormLayout(consume_box)
        self._batch_consume_spin = QSpinBox()
        self._batch_consume_spin.setRange(1, 999999)
        consume_form.addRow("Cantidad:", self._batch_consume_spin)
        consume_btn = QPushButton("Consumir del lote más antiguo")
        consume_btn.clicked.connect(lambda: self._on_consume_batch(inv_id, lotes_table, info_lbl))
        consume_form.addRow(consume_btn)
        layout.addWidget(consume_box)

        hint = QLabel(
            "Los lotes son informativos y no afectan el cálculo de stock principal. "
            "FIFO consume del lote con caducidad más próxima primero."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(hint)

        # Poblar tabla
        self._reload_batches_table(inv_id, lotes_table)

        return w

    def _reload_batches_table(self, inv_id: int, table: QTableWidget):
        """Recargar la tabla de lotes desde el servicio."""
        if not inv_id:
            table.setRowCount(0)
            return
        try:
            batches = self.service.get_inventory_batches(inv_id)
            table.setRowCount(len(batches))
            today_str = __import__("datetime").date.today().isoformat()
            for row, b in enumerate(batches):
                table.setItem(row, 0, QTableWidgetItem(b.get("batch_number") or "—"))
                table.setItem(row, 1, QTableWidgetItem((b.get("manufacturing_date") or "")[:10] or "—"))
                exp = b.get("expiration_date") or ""
                exp_cell = QTableWidgetItem(exp[:10] if exp else "—")
                if exp and exp[:10] < today_str:
                    exp_cell.setBackground(QColor("#ffaaaa"))  # vencido
                elif exp and exp[:10] <= __import__("datetime").date.today().replace(
                    day=__import__("datetime").date.today().day
                ).isoformat()[:7] + "-" + str(
                    __import__("datetime").date.today().day + 30
                ).zfill(2) if exp else False:
                    pass  # caducidad lejana
                table.setItem(row, 2, exp_cell)
                table.setItem(row, 3, QTableWidgetItem(str(b.get("quantity", 0))))
                cost = b.get("unit_cost")
                table.setItem(row, 4, QTableWidgetItem(f"${cost:,.2f}" if cost is not None else "—"))
                table.setItem(row, 5, QTableWidgetItem(b.get("notes") or ""))
            table.resizeColumnsToContents()
        except Exception as e:
            logger.error(f"Error recargando lotes: {e}")

    def _on_add_batch(self, inv_id: int, table: QTableWidget):
        """Abrir BatchDialog para agregar un lote nuevo."""
        if not inv_id:
            QMessageBox.warning(self, "Error", "Guarda el item primero antes de agregar lotes.")
            return
        dlg = BatchDialog(self.db, inv_id, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._reload_batches_table(inv_id, table)

    def _on_consume_batch(self, inv_id: int, table: QTableWidget, info_lbl: QLabel):
        """Consumir stock del lote más antiguo (FIFO)."""
        qty = self._batch_consume_spin.value()
        try:
            result = self.service.consume_batch(inv_id, qty)
            consumed = result.get("consumed", 0)
            QMessageBox.information(
                self, "Éxito",
                f"Se consumieron {consumed} unidades de {len(result.get('batches', []))} lote(s)."
            )
            self._reload_batches_table(inv_id, table)
            summary = self.service.get_batch_summary(inv_id)
            info_lbl.setText(
                f"<b>Lotes registrados:</b> {summary.get('batch_count', 0)} | "
                f"<b>Cantidad total en lotes:</b> {summary.get('batch_total_quantity', 0)}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    # ── Tab 8: Valor de inventario ────────────────────────────────────────
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

        # Filter bar
        filter_bar = QHBoxLayout()
        filter_bar.addWidget(QLabel("Filtrar por tipo:"))
        self._type_filter = QComboBox()
        self._type_filter.addItem("Todos", None)
        for t in ("count", "movement", "adjustment", "transfer"):
            self._type_filter.addItem(t, t)
        self._type_filter.currentIndexChanged.connect(self._load)
        filter_bar.addWidget(self._type_filter)
        filter_bar.addStretch()
        layout.addLayout(filter_bar)

        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Fecha", "Tipo",
            "Físico antes", "Físico nuevo",
            "Digital antes", "Digital nuevo",
            "Razón / Notas", "Motivo ajuste", "Ajustado por",
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
            result = self.service.get_stock_history(self.inventory_id, limit=200)
            records = result.get("records", [])
            # Apply type filter
            filter_type = self._type_filter.currentData()
            if filter_type:
                records = [r for r in records if r.get("change_type") == filter_type]

            self.table.setRowCount(len(records))
            for row, r in enumerate(records):
                created = (r.get("created_at") or "")[:19].replace("T", " ")
                self.table.setItem(row, 0, QTableWidgetItem(created))

                change_type = r.get("change_type", "")
                type_cell = QTableWidgetItem(change_type)
                type_colors = {
                    "count": "#e3f2fd", "movement": "#e8f5e9",
                    "adjustment": "#fff9c4", "transfer": "#fce4ec",
                }
                type_cell.setBackground(QColor(type_colors.get(change_type, "#ffffff")))
                self.table.setItem(row, 1, type_cell)

                self.table.setItem(row, 2, QTableWidgetItem(str(r.get("previous_physical", 0))))
                self.table.setItem(row, 3, QTableWidgetItem(str(r.get("new_physical", 0))))
                self.table.setItem(row, 4, QTableWidgetItem(str(r.get("previous_digital", 0))))
                self.table.setItem(row, 5, QTableWidgetItem(str(r.get("new_digital", 0))))
                self.table.setItem(row, 6, QTableWidgetItem(r.get("reason") or ""))
                self.table.setItem(row, 7, QTableWidgetItem(r.get("digital_adjustment_notes") or ""))
                self.table.setItem(row, 8, QTableWidgetItem(r.get("adjusted_by_name") or ""))

                # Highlight rows with discrepancy
                if r.get("introduced_discrepancy"):
                    for col in range(9):
                        cell = self.table.item(row, col)
                        if cell:
                            cell.setBackground(QColor("#fff3cd"))

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

        # Debounce timer: collapses bursts of event-bus notifications into
        # a single reload 400 ms after the last signal arrives.
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(400)
        self._refresh_timer.timeout.connect(self._on_refresh_timeout)

        self.setup_ui()
        self.apply_operation_mode(operation_mode.mode, operation_mode.current_branch_id)

        # Subscribe to operation-mode changes
        operation_mode.subscribe(self._on_mode_changed)

        # Subscribe to relevant event-bus events for real-time refresh
        self._subscribe_events()

        self.load_inventory()

    # ── UI setup ─────────────────────────────────────────────────────────
    def setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Header ───────────────────────────────────────────────────────
        header = QHBoxLayout()
        title = QLabel("Gestión de Inventario")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)

        # Mode indicator — updated by apply_operation_mode()
        self.mode_label = QLabel("")
        self.mode_label.setStyleSheet("font-size: 12px; font-weight: bold; padding: 4px 8px; border-radius: 4px;")
        header.addWidget(self.mode_label)
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

        self.count_session_btn = QPushButton("📅 Sesiones de Conteo")
        self.count_session_btn.clicked.connect(self.on_count_sessions)
        actions.addWidget(self.count_session_btn)

        # Global-view toggle — only shown in matrix mode
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

    # ── Operation-mode integration ───────────────────────────────────────
    def apply_operation_mode(self, mode: str, branch_id):
        """Apply visual and data-scope changes for the current operation mode.

        Called on init and every time operation_mode changes.
        """
        if mode == MODE_BRANCH and branch_id:
            # Lock the branch selector to the active branch
            self.branch_combo.setEnabled(False)
            idx = self.branch_combo.findData(branch_id)
            if idx >= 0:
                self.branch_combo.blockSignals(True)
                self.branch_combo.setCurrentIndex(idx)
                self.branch_combo.blockSignals(False)
            self.current_branch_id = branch_id

            # Branch mode: hide global-view toggle (not meaningful for a single branch)
            self.global_view_btn.setVisible(False)
            if self.global_view_btn.isChecked():
                self.global_view_btn.setChecked(False)

            self.mode_label.setText(f"🏢 Sucursal: {operation_mode.current_branch_name}")
            self.mode_label.setStyleSheet(
                "font-size: 12px; font-weight: bold; padding: 4px 8px; "
                "border-radius: 4px; background: #e3f2fd; color: #0d47a1;"
            )
        else:
            # Matrix mode: unlock branch selector, show global-view toggle
            self.branch_combo.setEnabled(True)
            self.global_view_btn.setVisible(True)

            self.mode_label.setText("🌐 Modo: Matriz")
            self.mode_label.setStyleSheet(
                "font-size: 12px; font-weight: bold; padding: 4px 8px; "
                "border-radius: 4px; background: #e8f5e9; color: #1b5e20;"
            )

    def _on_mode_changed(self, mode: str, branch_id):
        """Callback from operation_mode singleton — runs on mode switch."""
        self.apply_operation_mode(mode, branch_id)
        # Reset manual filters so the new scope is applied cleanly
        self.show_discrepancies_only = False
        self.show_low_stock_only = False
        self.discrepancy_btn.setChecked(False)
        self.low_stock_btn.setChecked(False)
        self.search_input.clear()
        self.load_data()

    # ── Event-bus subscriptions for real-time refresh (Task 5) ───────────
    def _subscribe_events(self):
        """Subscribe to inventory and movement events that affect stock display."""
        for event in (
            settings.Events.INVENTORY_UPDATED,
            settings.Events.INVENTORY_COUNTED,
            settings.Events.MOVEMENT_VALIDATED,
            settings.Events.TRANSFER_SENT,
            settings.Events.TRANSFER_RECEIVED,
            settings.Events.STOCK_IN_TRANSIT_ADDED,
            settings.Events.STOCK_IN_TRANSIT_RECEIVED,
        ):
            event_bus.subscribe(event, self._on_stock_event)

    def _unsubscribe_events(self):
        """Clean up all event subscriptions."""
        for event in (
            settings.Events.INVENTORY_UPDATED,
            settings.Events.INVENTORY_COUNTED,
            settings.Events.MOVEMENT_VALIDATED,
            settings.Events.TRANSFER_SENT,
            settings.Events.TRANSFER_RECEIVED,
            settings.Events.STOCK_IN_TRANSIT_ADDED,
            settings.Events.STOCK_IN_TRANSIT_RECEIVED,
        ):
            event_bus.unsubscribe(event, self._on_stock_event)

    def _on_stock_event(self, data):
        """Event-bus callback: schedule a debounced table refresh.

        In branch mode, only reload when the event concerns the active branch.
        In matrix mode, always reload.
        """
        if operation_mode.is_branch and operation_mode.current_branch_id:
            event_branch = data.get("branch_id") or data.get("destination_branch_id")
            if event_branch not in (
                operation_mode.current_branch_id,
                None,  # events without branch_id always trigger reload
            ):
                return  # event is for a different branch — ignore
        self._refresh_timer.start()  # restart debounce window

    def _on_refresh_timeout(self):
        """Actually reload data after the debounce window expires."""
        if not self.global_view_btn.isChecked():
            self.load_inventory(self.search_input.text() or None)
        else:
            self.load_global_inventory(self.search_input.text() or None)

    def closeEvent(self, event):
        """Clean up when the widget is destroyed."""
        operation_mode.unsubscribe(self._on_mode_changed)
        self._unsubscribe_events()
        super().closeEvent(event)

    # ── Carga y renderizado de datos ──────────────────────────────────────
    def load_inventory(self, search: str = None):
        """Carga el inventario en la tabla con todos los campos nuevos.

        In branch mode the scope is always the active branch, regardless of
        what the branch combo shows.  In matrix mode the user controls the
        combo freely.
        """
        # Determine effective branch: operation mode overrides the combo in
        # branch mode so all data queries are scoped correctly.
        effective_branch_id = (
            operation_mode.current_branch_id
            if operation_mode.is_branch
            else self.current_branch_id
        )
        try:
            result = self.service.list_inventory(
                page=1, page_size=200,
                branch_id=effective_branch_id,
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
        effective_branch_id = (
            operation_mode.current_branch_id
            if operation_mode.is_branch
            else self.current_branch_id
        )
        totals = self.service.get_totals(effective_branch_id)
        self.total_physical_label.setText(f"Físico Total: {totals['total_physical_stock']}")
        self.total_digital_label.setText(f"Digital Total: {totals['total_digital_stock']}")
        self.discrepancy_label.setText(f"Discrepancias: {totals['discrepancy_count']}")
        self.low_stock_label.setText(f"Stock Bajo: {totals['low_stock_count']}")
        try:
            val = self.service.get_inventory_value(effective_branch_id)
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
        # Pre-populate branch when in branch mode
        pre_data = {}
        if operation_mode.is_branch and operation_mode.current_branch_id:
            pre_data["branch_id"] = operation_mode.current_branch_id
        dialog = InventoryCountDialog(self.db, self, inventory_data=pre_data)
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

    def on_count_sessions(self):
        """Abrir gestor de sesiones de conteo formal."""
        effective_branch_id = (
            operation_mode.current_branch_id
            if operation_mode.is_branch
            else self.current_branch_id
        )
        if not effective_branch_id:
            QMessageBox.information(
                self, "Sesiones de Conteo",
                "Selecciona una sucursal para gestionar sesiones de conteo."
            )
            return
        dialog = InventoryCountSessionDialog(self.db, effective_branch_id, parent=self)
        dialog.exec()
        # Reload in case a count was completed
        self.load_inventory(self.search_input.text() or None)

    def show_metrics(self):
        """Abrir diálogo de métricas (Expansión 9)."""
        effective_branch_id = (
            operation_mode.current_branch_id
            if operation_mode.is_branch
            else self.current_branch_id
        )
        branch_name = (
            operation_mode.current_branch_name
            if operation_mode.is_branch
            else self.branch_combo.currentText()
        )
        dialog = InventoryMetricsDialog(self.db, effective_branch_id, branch_name, parent=self)
        dialog.exec()

    def show_reorder_report(self):
        """Mostrar reporte de reposición ordenado por prioridad (Expansión 4)."""
        effective_branch_id = (
            operation_mode.current_branch_id
            if operation_mode.is_branch
            else self.current_branch_id
        )
        if not effective_branch_id:
            QMessageBox.information(self, "Info", "Selecciona una sucursal para ver el reporte de reposición.")
            return
        try:
            report = self.service.get_reorder_report(effective_branch_id)
            total = report["total"]
            if total == 0:
                QMessageBox.information(self, "Reposición", "No hay items con stock bajo en esta sucursal.")
                return
            branch_name = (
                operation_mode.current_branch_name
                if operation_mode.is_branch
                else self.branch_combo.currentText()
            )
            dialog = InventoryMetricsDialog(self.db, effective_branch_id, branch_name, parent=self)
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


# ═══════════════════════════════════════════════════════════════════════════
# BatchDialog  –  Crear o editar un lote de inventario
# ═══════════════════════════════════════════════════════════════════════════
class BatchDialog(QDialog):
    """Diálogo para crear un nuevo lote en un item de inventario."""

    def __init__(self, db: Session, inventory_id: int, batch_data: dict = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.inventory_id = inventory_id
        self.batch_data = batch_data or {}
        self.service = InventoryService(db)
        self.setWindowTitle("Agregar Lote" if not batch_data else "Editar Lote")
        self.setMinimumWidth(420)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setContentsMargins(12, 12, 12, 12)

        self.batch_number = QLineEdit(self.batch_data.get("batch_number") or "")
        self.batch_number.setPlaceholderText("Número de lote (opcional)")
        form.addRow("Número de lote:", self.batch_number)

        self.quantity = QSpinBox()
        self.quantity.setRange(0, 999999)
        self.quantity.setValue(self.batch_data.get("quantity", 0))
        form.addRow("Cantidad:", self.quantity)

        self.manufacturing_date = QDateEdit()
        self.manufacturing_date.setCalendarPopup(True)
        self.manufacturing_date.setSpecialValueText("(no definida)")
        self.manufacturing_date.setDate(QDate.currentDate())
        self._mfg_enabled = QCheckBox("Definir fecha de fabricación")
        mfg = self.batch_data.get("manufacturing_date")
        self._mfg_enabled.setChecked(bool(mfg))
        self.manufacturing_date.setEnabled(bool(mfg))
        if mfg:
            parts = str(mfg)[:10].split("-")
            self.manufacturing_date.setDate(QDate(int(parts[0]), int(parts[1]), int(parts[2])))
        self._mfg_enabled.toggled.connect(self.manufacturing_date.setEnabled)
        form.addRow(self._mfg_enabled)
        form.addRow("Fecha fabricación:", self.manufacturing_date)

        self.expiration_date = QDateEdit()
        self.expiration_date.setCalendarPopup(True)
        self.expiration_date.setDate(QDate.currentDate().addYears(1))
        self._exp_enabled = QCheckBox("Definir fecha de caducidad")
        exp = self.batch_data.get("expiration_date")
        self._exp_enabled.setChecked(bool(exp))
        self.expiration_date.setEnabled(bool(exp))
        if exp:
            parts = str(exp)[:10].split("-")
            self.expiration_date.setDate(QDate(int(parts[0]), int(parts[1]), int(parts[2])))
        self._exp_enabled.toggled.connect(self.expiration_date.setEnabled)
        form.addRow(self._exp_enabled)
        form.addRow("Fecha caducidad:", self.expiration_date)

        self.unit_cost = QDoubleSpinBox()
        self.unit_cost.setRange(0.0, 9999999.99)
        self.unit_cost.setDecimals(2)
        self.unit_cost.setPrefix("$ ")
        self.unit_cost.setSpecialValueText("(no definido)")
        uc = self.batch_data.get("unit_cost")
        self.unit_cost.setValue(uc if uc is not None else 0.0)
        form.addRow("Costo unitario:", self.unit_cost)

        self.notes = QTextEdit(self.batch_data.get("notes") or "")
        self.notes.setPlaceholderText("Notas del lote (opcional)...")
        self.notes.setMaximumHeight(60)
        form.addRow("Notas:", self.notes)

        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_accept(self):
        try:
            from datetime import date as _date
            mfg = None
            if self._mfg_enabled.isChecked():
                qd = self.manufacturing_date.date()
                mfg = _date(qd.year(), qd.month(), qd.day())
            exp = None
            if self._exp_enabled.isChecked():
                qd = self.expiration_date.date()
                exp = _date(qd.year(), qd.month(), qd.day())
            uc = self.unit_cost.value()
            self.service.add_batch(
                self.inventory_id,
                batch_number=self.batch_number.text().strip() or None,
                manufacturing_date=mfg,
                expiration_date=exp,
                quantity=self.quantity.value(),
                unit_cost=uc if uc > 0 else None,
                notes=self.notes.toPlainText().strip() or None,
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar el lote:\n{e}")


# ═══════════════════════════════════════════════════════════════════════════
# InventoryCountSessionDialog  –  Gestionar sesiones de conteo de una sucursal
# ═══════════════════════════════════════════════════════════════════════════
class InventoryCountSessionDialog(QDialog):
    """
    Lista las sesiones de conteo de una sucursal y permite crear nuevas,
    iniciarlas y ver sus resultados.
    """

    def __init__(self, db: Session, branch_id: int, parent=None):
        super().__init__(parent)
        self.db = db
        self.branch_id = branch_id
        self.service = InventoryService(db)
        self.setWindowTitle("Sesiones de Conteo Físico")
        self.setMinimumSize(720, 480)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Toolbar ──────────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        new_btn = QPushButton("+ Nueva Sesión")
        new_btn.clicked.connect(self._on_new_session)
        toolbar.addWidget(new_btn)

        self._status_filter = QComboBox()
        self._status_filter.addItem("Todas", None)
        for s in ("pending", "in_progress", "completed", "cancelled"):
            self._status_filter.addItem(s.replace("_", " ").capitalize(), s)
        self._status_filter.currentIndexChanged.connect(self._load)
        toolbar.addWidget(QLabel("Estado:"))
        toolbar.addWidget(self._status_filter)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # ── Tabla de sesiones ─────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ID", "Programada", "Iniciada", "Completada", "Estado", "Validadores", "Acciones"
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        close = QPushButton("Cerrar")
        close.clicked.connect(self.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)

        self._load()

    def _load(self):
        status = self._status_filter.currentData()
        try:
            sessions = self.service.get_count_sessions_by_branch(self.branch_id, status)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        STATUS_COLORS = {
            "pending": "#fff9c4", "in_progress": "#cce5ff",
            "completed": "#d4edda", "cancelled": "#f8d7da",
        }

        self.table.setRowCount(len(sessions))
        for row, s in enumerate(sessions):
            self.table.setItem(row, 0, QTableWidgetItem(str(s["id"])))
            self.table.setItem(row, 1, QTableWidgetItem((s.get("scheduled_date") or "")[:16].replace("T", " ")))
            self.table.setItem(row, 2, QTableWidgetItem((s.get("started_at") or "—")[:16].replace("T", " ")))
            self.table.setItem(row, 3, QTableWidgetItem((s.get("completed_at") or "—")[:16].replace("T", " ")))

            status_val = s.get("status", "")
            st_cell = QTableWidgetItem(status_val.replace("_", " ").capitalize())
            st_cell.setBackground(QColor(STATUS_COLORS.get(status_val, "#ffffff")))
            self.table.setItem(row, 4, st_cell)

            self.table.setItem(row, 5, QTableWidgetItem(str(s.get("validator_count", 1))))
            self.table.setCellWidget(row, 6, self._make_session_actions(s))

        self.table.resizeColumnsToContents()

    def _make_session_actions(self, session: dict) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(4)
        status = session.get("status", "")

        if status == "pending":
            start_btn = QPushButton("▶ Iniciar")
            start_btn.setFixedHeight(26)
            start_btn.clicked.connect(lambda _, s=session: self._on_start_session(s["id"]))
            lay.addWidget(start_btn)

            cancel_btn = QPushButton("✖ Cancelar")
            cancel_btn.setFixedHeight(26)
            cancel_btn.clicked.connect(lambda _, s=session: self._on_cancel_session(s["id"]))
            lay.addWidget(cancel_btn)

        elif status == "in_progress":
            exec_btn = QPushButton("📋 Ejecutar Conteo")
            exec_btn.setFixedHeight(26)
            exec_btn.clicked.connect(lambda _, s=session: self._on_execute_session(s["id"]))
            lay.addWidget(exec_btn)

            complete_btn = QPushButton("✔ Completar")
            complete_btn.setFixedHeight(26)
            complete_btn.clicked.connect(lambda _, s=session: self._on_complete_session(s["id"]))
            lay.addWidget(complete_btn)

        elif status in ("completed", "cancelled"):
            view_btn = QPushButton("🔍 Ver Resumen")
            view_btn.setFixedHeight(26)
            view_btn.clicked.connect(lambda _, s=session: self._on_view_summary(s["id"]))
            lay.addWidget(view_btn)

        return w

    def _on_new_session(self):
        dlg = _NewCountSessionForm(self.db, self.branch_id, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._load()

    def _on_start_session(self, session_id: int):
        try:
            self.service.start_count_session(session_id)
            QMessageBox.information(self, "Éxito", "Sesión iniciada. El inventario ha sido pre-cargado.")
            self._load()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_execute_session(self, session_id: int):
        dlg = InventoryCountExecutionDialog(self.db, session_id, parent=self)
        dlg.exec()
        self._load()

    def _on_complete_session(self, session_id: int):
        from PyQt6.QtWidgets import QInputDialog
        validators, ok = QInputDialog.getInt(
            self, "Completar Sesión",
            "Número de personas que validaron el conteo:", 1, 1, 99
        )
        if not ok:
            return
        try:
            self.service.complete_count_session(session_id, validator_count=validators)
            QMessageBox.information(self, "Éxito", "Sesión completada correctamente.")
            self._load()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_cancel_session(self, session_id: int):
        reply = QMessageBox.question(
            self, "Cancelar Sesión",
            "¿Cancelar esta sesión de conteo? Esta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.cancel_count_session(session_id)
            self._load()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_view_summary(self, session_id: int):
        dlg = InventoryCountSummaryDialog(self.db, session_id, parent=self)
        dlg.exec()


# ═══════════════════════════════════════════════════════════════════════════
# _NewCountSessionForm  –  Formulario interno para crear una sesión nueva
# ═══════════════════════════════════════════════════════════════════════════
class _NewCountSessionForm(QDialog):
    """Formulario compacto para programar una nueva sesión de conteo."""

    def __init__(self, db: Session, branch_id: int, parent=None):
        super().__init__(parent)
        self.db = db
        self.branch_id = branch_id
        self.service = InventoryService(db)
        self.setWindowTitle("Nueva Sesión de Conteo")
        self.setMinimumWidth(380)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setContentsMargins(12, 12, 12, 12)

        self.scheduled_dt = QDateTimeEdit(QDateTime.currentDateTime())
        self.scheduled_dt.setCalendarPopup(True)
        self.scheduled_dt.setDisplayFormat("dd/MM/yyyy HH:mm")
        form.addRow("Fecha programada:", self.scheduled_dt)

        self.notes = QTextEdit()
        self.notes.setPlaceholderText("Notas o instrucciones para el conteo (opcional)...")
        self.notes.setMaximumHeight(80)
        form.addRow("Notas:", self.notes)

        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_accept(self):
        try:
            from datetime import datetime as _dt
            qdt = self.scheduled_dt.dateTime()
            scheduled = _dt(
                qdt.date().year(), qdt.date().month(), qdt.date().day(),
                qdt.time().hour(), qdt.time().minute()
            )
            self.service.create_count_session(
                branch_id=self.branch_id,
                scheduled_date=scheduled,
                notes=self.notes.toPlainText().strip() or None,
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo crear la sesión:\n{e}")


# ═══════════════════════════════════════════════════════════════════════════
# InventoryCountExecutionDialog  –  Registrar conteos item a item
# ═══════════════════════════════════════════════════════════════════════════
class InventoryCountExecutionDialog(QDialog):
    """
    Permite recorrer item a item dentro de una sesión en progreso
    y registrar el conteo físico de cada uno.
    """

    def __init__(self, db: Session, session_id: int, parent=None):
        super().__init__(parent)
        self.db = db
        self.session_id = session_id
        self.service = InventoryService(db)
        self.setWindowTitle(f"Ejecutar Conteo — Sesión #{session_id}")
        self.setMinimumSize(860, 560)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Progress banner
        self.progress_lbl = QLabel()
        self.progress_lbl.setStyleSheet(
            "font-weight: bold; font-size: 13px; padding: 4px 8px; "
            "background: #e3f2fd; border-radius: 4px;"
        )
        layout.addWidget(self.progress_lbl)

        # Search filter
        filter_bar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Buscar por producto o SKU…")
        self._search.setMaximumWidth(300)
        self._search.textChanged.connect(self._filter_table)
        filter_bar.addWidget(self._search)

        self._only_pending = QCheckBox("Solo pendientes")
        self._only_pending.setChecked(True)
        self._only_pending.toggled.connect(self._load)
        filter_bar.addWidget(self._only_pending)
        filter_bar.addStretch()
        layout.addLayout(filter_bar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "inv_id", "Producto / SKU", "Esperado", "Contado", "Diferencia", "Validador", "Acción"
        ])
        self.table.setColumnHidden(0, True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        # Quick-entry row
        entry_box = QGroupBox("Registrar conteo rápido")
        entry_form = QHBoxLayout(entry_box)

        entry_form.addWidget(QLabel("Item seleccionado:"))
        self._selected_lbl = QLabel("(ninguno)")
        self._selected_lbl.setStyleSheet("font-weight: bold;")
        entry_form.addWidget(self._selected_lbl)

        entry_form.addWidget(QLabel("Contado:"))
        self._counted_spin = QSpinBox()
        self._counted_spin.setRange(0, 999999)
        self._counted_spin.setFixedWidth(90)
        entry_form.addWidget(self._counted_spin)

        entry_form.addWidget(QLabel("Validador:"))
        self._validator_input = QLineEdit()
        self._validator_input.setPlaceholderText("Nombre (opcional)")
        self._validator_input.setMaximumWidth(180)
        entry_form.addWidget(self._validator_input)

        save_btn = QPushButton("Registrar")
        save_btn.setFixedWidth(100)
        save_btn.clicked.connect(self._on_record_selected)
        entry_form.addWidget(save_btn)

        layout.addWidget(entry_box)

        # Connect row selection → populate entry row
        self.table.selectionModel().selectionChanged.connect(self._on_row_selected)

        close = QPushButton("Cerrar")
        close.clicked.connect(self.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)

        self._all_items = []
        self._load()

    def _load(self):
        try:
            summary = self.service.get_count_session_summary(self.session_id)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        if not summary:
            QMessageBox.warning(self, "Error", "No se encontró la sesión.")
            self.reject()
            return

        total = summary["total_items"]
        counted = summary["counted_items"]
        discrepancies = summary["discrepancy_count"]
        self.progress_lbl.setText(
            f"Progreso: {counted}/{total} items contados  |  "
            f"Discrepancias: {discrepancies}  |  "
            f"Pendientes: {total - counted}"
        )

        self._all_items = summary["items"]
        self._render_table(self._all_items)

    def _render_table(self, items: list):
        only_pending = self._only_pending.isChecked()
        if only_pending:
            items = [i for i in items if i.get("counted_physical") is None]

        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            inv_id = item.get("inventory_id") or 0
            self.table.setItem(row, 0, QTableWidgetItem(str(inv_id)))

            # Resolve product name via inventory_id
            prod_name = f"inventory #{inv_id}"
            try:
                inv = self.service.get_inventory(inv_id)
                if inv and inv.get("product"):
                    p = inv["product"]
                    prod_name = f"{p.get('sku', '')} — {p.get('name', '')}"
            except Exception:
                pass
            self.table.setItem(row, 1, QTableWidgetItem(prod_name))

            expected = item.get("expected_physical", 0)
            counted = item.get("counted_physical")
            diff = item.get("difference")

            self.table.setItem(row, 2, QTableWidgetItem(str(expected)))
            self.table.setItem(row, 3, QTableWidgetItem(str(counted) if counted is not None else "—"))
            diff_cell = QTableWidgetItem(str(diff) if diff is not None else "—")
            if diff is not None and diff != 0:
                diff_cell.setBackground(QColor("#ffaaaa"))
            elif diff == 0 and counted is not None:
                diff_cell.setBackground(QColor("#d4edda"))
            self.table.setItem(row, 4, diff_cell)
            self.table.setItem(row, 5, QTableWidgetItem(item.get("validator_name") or ""))

            # Inline action button
            btn = QPushButton("Contar")
            btn.setFixedHeight(26)
            btn.clicked.connect(lambda _, i=item, r=row: self._on_inline_count(i, r))
            self.table.setCellWidget(row, 6, btn)

        self.table.resizeColumnsToContents()

    def _filter_table(self, text: str):
        text = text.lower()
        for row in range(self.table.rowCount()):
            cell = self.table.item(row, 1)
            visible = not text or (cell and text in cell.text().lower())
            self.table.setRowHidden(row, not visible)

    def _on_row_selected(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self._selected_lbl.setText("(ninguno)")
            return
        row = rows[0].row()
        prod_cell = self.table.item(row, 1)
        expected_cell = self.table.item(row, 2)
        self._selected_lbl.setText(prod_cell.text() if prod_cell else "")
        if expected_cell:
            try:
                self._counted_spin.setValue(int(expected_cell.text()))
            except ValueError:
                pass

    def _on_inline_count(self, item: dict, _row: int):
        inv_id = item.get("inventory_id")
        if not inv_id:
            QMessageBox.warning(self, "Error", "Este item no tiene inventario asignado.")
            return
        from PyQt6.QtWidgets import QInputDialog
        counted, ok = QInputDialog.getInt(
            self, "Registrar Conteo",
            f"Cantidad contada para:\n{self.table.item(_row, 1).text() if self.table.item(_row, 1) else inv_id}",
            value=item.get("expected_physical", 0), min=0, max=999999,
        )
        if not ok:
            return
        try:
            self.service.record_count_item(
                session_id=self.session_id,
                inventory_id=inv_id,
                counted_physical=counted,
            )
            self._load()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_record_selected(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "Info", "Selecciona una fila primero.")
            return
        row = rows[0].row()
        inv_id_cell = self.table.item(row, 0)
        if not inv_id_cell or not inv_id_cell.text().isdigit():
            QMessageBox.warning(self, "Error", "No se pudo determinar el item.")
            return
        inv_id = int(inv_id_cell.text())
        counted = self._counted_spin.value()
        validator = self._validator_input.text().strip() or None
        try:
            self.service.record_count_item(
                session_id=self.session_id,
                inventory_id=inv_id,
                counted_physical=counted,
                validator_name=validator,
            )
            self._load()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


# ═══════════════════════════════════════════════════════════════════════════
# InventoryCountSummaryDialog  –  Ver resultado de una sesión completada
# ═══════════════════════════════════════════════════════════════════════════
class InventoryCountSummaryDialog(QDialog):
    """
    Muestra el resumen detallado de una sesión de conteo completada o cancelada.
    Incluye estadísticas globales, lista de items y detalle de discrepancias.
    """

    def __init__(self, db: Session, session_id: int, parent=None):
        super().__init__(parent)
        self.db = db
        self.session_id = session_id
        self.service = InventoryService(db)
        self.setWindowTitle(f"Resumen de Sesión #{session_id}")
        self.setMinimumSize(820, 560)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        try:
            summary = self.service.get_count_session_summary(self.session_id)
        except Exception as e:
            layout.addWidget(QLabel(f"Error al cargar sesión: {e}"))
            close = QPushButton("Cerrar")
            close.clicked.connect(self.accept)
            layout.addWidget(close)
            return

        if not summary:
            layout.addWidget(QLabel("Sesión no encontrada."))
            close = QPushButton("Cerrar")
            close.clicked.connect(self.accept)
            layout.addWidget(close)
            return

        session = summary["session"]
        total = summary["total_items"]
        counted = summary["counted_items"]
        pending = summary["pending_items"]
        discrepancies = summary["discrepancy_count"]

        # ── Encabezado con estadísticas ───────────────────────────────────
        status = session.get("status", "")
        STATUS_COLORS = {
            "pending": "#fff9c4", "in_progress": "#cce5ff",
            "completed": "#d4edda", "cancelled": "#f8d7da",
        }
        header_color = STATUS_COLORS.get(status, "#f5f5f5")

        header_box = QGroupBox("Información de la sesión")
        header_box.setStyleSheet(f"QGroupBox {{ background: {header_color}; border-radius: 4px; }}")
        header_form = QFormLayout(header_box)
        header_form.addRow("Estado:", QLabel(f"<b>{status.replace('_', ' ').upper()}</b>"))
        header_form.addRow("Programada:", QLabel((session.get("scheduled_date") or "")[:16].replace("T", " ")))
        header_form.addRow("Iniciada:", QLabel((session.get("started_at") or "—")[:16].replace("T", " ")))
        header_form.addRow("Completada:", QLabel((session.get("completed_at") or "—")[:16].replace("T", " ")))
        header_form.addRow("Validadores:", QLabel(str(session.get("validator_count", 1))))
        if session.get("notes"):
            header_form.addRow("Notas:", QLabel(session["notes"]))
        layout.addWidget(header_box)

        # ── Métricas rápidas ──────────────────────────────────────────────
        metrics_bar = QHBoxLayout()
        for label, value, color in [
            ("Total items", str(total), "#1565c0"),
            ("Contados", str(counted), "#2e7d32"),
            ("Pendientes", str(pending), "#f57c00"),
            ("Discrepancias", str(discrepancies), "#c62828"),
        ]:
            box = QGroupBox(label)
            box_lay = QVBoxLayout(box)
            val_lbl = QLabel(value)
            val_lbl.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {color};")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box_lay.addWidget(val_lbl)
            metrics_bar.addWidget(box)
        layout.addLayout(metrics_bar)

        # ── Tabs: todos los items / solo discrepancias ────────────────────
        tabs = QTabWidget()
        tabs.addTab(self._build_items_table(summary["items"], only_discrepancies=False), "Todos los items")
        tabs.addTab(self._build_items_table(summary["items"], only_discrepancies=True), f"Discrepancias ({discrepancies})")
        layout.addWidget(tabs)

        close = QPushButton("Cerrar")
        close.clicked.connect(self.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)

    def _build_items_table(self, items: list, only_discrepancies: bool) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        if only_discrepancies:
            items = [i for i in items if i.get("is_discrepancy")]

        t = QTableWidget()
        t.setColumnCount(7)
        t.setHorizontalHeaderLabels([
            "Inventario", "Producto", "Esperado", "Contado", "Diferencia", "Validador", "Notas"
        ])
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        t.horizontalHeader().setStretchLastSection(True)
        t.setRowCount(len(items))

        for row, item in enumerate(items):
            inv_id = item.get("inventory_id") or ""
            t.setItem(row, 0, QTableWidgetItem(str(inv_id)))

            # Resolve product name
            prod_name = f"inv #{inv_id}"
            try:
                inv = self.service.get_inventory(int(inv_id)) if inv_id else None
                if inv and inv.get("product"):
                    p = inv["product"]
                    prod_name = f"{p.get('sku', '')} — {p.get('name', '')}"
            except Exception:
                pass
            t.setItem(row, 1, QTableWidgetItem(prod_name))

            expected = item.get("expected_physical", 0)
            counted = item.get("counted_physical")
            diff = item.get("difference")

            t.setItem(row, 2, QTableWidgetItem(str(expected)))
            t.setItem(row, 3, QTableWidgetItem(str(counted) if counted is not None else "—"))

            diff_cell = QTableWidgetItem(str(diff) if diff is not None else "—")
            if item.get("is_discrepancy"):
                diff_cell.setBackground(QColor("#ffaaaa"))
            elif counted is not None:
                diff_cell.setBackground(QColor("#d4edda"))
            t.setItem(row, 4, diff_cell)

            t.setItem(row, 5, QTableWidgetItem(item.get("validator_name") or ""))
            t.setItem(row, 6, QTableWidgetItem(item.get("notes") or ""))

        t.resizeColumnsToContents()
        lay.addWidget(t)
        return w
