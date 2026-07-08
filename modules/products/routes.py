"""
Product GUI routes/controllers for PyQt6 interface.

ProductDialog organises ALL fields across five tabs:
  Tab "General"   – SKU, Nombre, Categoría (jerarquía), Marca, Proveedor,
                    Unidad de Medida, Precio Unitario
  Tab "Detalle"   – Descripción, Detalles, Notas Internas, Stock Mín. Global
  Tab "Variante"  – Producto Padre, Grupo Variante, Atributos Variante
  Tab "Kit"       – checkbox Es Kit, tabla de componentes, agregar/quitar
  Tab "Fiscal"    – Código SAT, Fracción Arancelaria, País de Origen

ProductListView gains:
  - Status column (badge) and status filter combo
  - Variant indicator in Nombre column
  - Kit indicator in Nombre column
  - "Ver Historial" button in action cell
  - Category filter uses flat indented list (hierarchy-aware)
"""

import logging
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal  # noqa: F401 – pyqtSignal used in ProductListView
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import Session

from modules.products.service import (
    CategoryService,
    KitService,
    ProductService,
    SupplierService,
)

logger = logging.getLogger(__name__)

_NONE_ID = -1

# Human-readable labels for product_status values
_STATUS_LABELS = {
    "active":                 "Activo",
    "discontinued":           "Descontinuado",
    "temporarily_unavailable": "No disponible temporalmente",
    "on_hold":                "En espera",
}
_STATUS_VALUES = list(_STATUS_LABELS.keys())


def _combo_current_id(combo: QComboBox) -> Optional[int]:
    """Return the integer item-data of the current combo selection, or None."""
    value = combo.currentData()
    if value is None or value == _NONE_ID:
        return None
    return int(value)


def _set_combo_by_id(combo: QComboBox, target_id) -> None:
    """Select the combo entry whose data matches target_id."""
    if target_id is None:
        return
    for i in range(combo.count()):
        if combo.itemData(i) == target_id:
            combo.setCurrentIndex(i)
            return


def _set_combo_by_value(combo: QComboBox, value: str) -> None:
    """Select the combo entry whose data matches a string value."""
    if value is None:
        return
    for i in range(combo.count()):
        if combo.itemData(i) == value:
            combo.setCurrentIndex(i)
            return


# ======================================================================
# ProductDialog
# ======================================================================

class ProductDialog(QDialog):
    """Dialog for creating / editing a product (5 tabs)."""

    def __init__(self, db: Session, parent=None, product_data: dict = None):
        super().__init__(parent)
        self.db = db
        self.product_data = product_data or {}
        self._cat_service = CategoryService(db)
        self._sup_service = SupplierService(db)
        self._kit_service = KitService(db)
        self._product_service = ProductService(db)
        # Tracks components added during this dialog session (kit tab)
        self._pending_components: list = []
        self.setup_ui()
        self._populate_combos()
        self._fill_fields()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def setup_ui(self):
        title = "Editar Producto" if self.product_data else "Nuevo Producto"
        self.setWindowTitle(title)
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs)

        tabs.addTab(self._build_tab_general(), "General")
        tabs.addTab(self._build_tab_detail(), "Detalle")
        tabs.addTab(self._build_tab_variant(), "Variante")
        tabs.addTab(self._build_tab_kit(), "Kit")
        tabs.addTab(self._build_tab_fiscal(), "Fiscal")

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.save_button = QPushButton("Guardar")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self.accept)
        btn_layout.addWidget(self.save_button)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_button)
        root.addLayout(btn_layout)

    def _form(self) -> QFormLayout:
        f = QFormLayout()
        f.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        f.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        return f

    def _build_tab_general(self) -> QWidget:
        tab = QWidget()
        form = self._form()
        tab.setLayout(form)

        self.sku_input = QLineEdit()
        self.sku_input.setPlaceholderText("Ej.: TEC-001")
        form.addRow("SKU *:", self.sku_input)

        self.name_input = QLineEdit()
        form.addRow("Nombre *:", self.name_input)

        self.category_combo = QComboBox()
        self.category_combo.setMinimumWidth(200)
        form.addRow("Categoría:", self.category_combo)

        self.brand_input = QLineEdit()
        self.brand_input.setPlaceholderText("Ej.: Bosch, Mabe, Genérico…")
        form.addRow("Marca:", self.brand_input)

        self.supplier_combo = QComboBox()
        self.supplier_combo.setMinimumWidth(200)
        form.addRow("Proveedor:", self.supplier_combo)

        self.unit_input = QLineEdit()
        self.unit_input.setPlaceholderText("unidad, kg, litro, caja…")
        form.addRow("Unidad de Medida *:", self.unit_input)

        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0, 9_999_999.99)
        self.price_input.setDecimals(2)
        self.price_input.setPrefix("$ ")
        form.addRow("Precio Unitario:", self.price_input)

        self.status_combo = QComboBox()
        for val, label in _STATUS_LABELS.items():
            self.status_combo.addItem(label, val)
        form.addRow("Estado:", self.status_combo)

        self.replacement_combo = QComboBox()
        self.replacement_combo.setMinimumWidth(200)
        self.replacement_combo.setToolTip(
            "Producto que reemplaza a este cuando está descontinuado"
        )
        form.addRow("Producto Reemplazo:", self.replacement_combo)

        return tab

    def _build_tab_detail(self) -> QWidget:
        tab = QWidget()
        form = self._form()
        tab.setLayout(form)

        self.description_input = QTextEdit()
        self.description_input.setMaximumHeight(80)
        self.description_input.setPlaceholderText("Descripción breve del producto…")
        form.addRow("Descripción:", self.description_input)

        self.details_input = QTextEdit()
        self.details_input.setMaximumHeight(90)
        self.details_input.setPlaceholderText(
            "Color, tamaño, presentación, especificaciones técnicas…"
        )
        form.addRow("Detalles:", self.details_input)

        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(80)
        self.notes_input.setPlaceholderText("Notas internas (solo para empleados)…")
        form.addRow("Notas Internas:", self.notes_input)

        self.min_stock_input = QSpinBox()
        self.min_stock_input.setRange(0, 999_999)
        self.min_stock_input.setSpecialValueText("Sin umbral")
        self.min_stock_input.setToolTip("Stock mínimo global sugerido. 0 = sin umbral.")
        form.addRow("Stock Mín. Global:", self.min_stock_input)

        return tab

    def _build_tab_variant(self) -> QWidget:
        tab = QWidget()
        form = self._form()
        tab.setLayout(form)

        lbl = QLabel(
            "Completa estos campos solo si este producto es una <b>variante</b> "
            "de otro (ej. misma camisa en talla M).\n"
            "Déjalos vacíos para un producto normal."
        )
        lbl.setWordWrap(True)
        form.addRow(lbl)

        self.parent_product_combo = QComboBox()
        self.parent_product_combo.setMinimumWidth(220)
        self.parent_product_combo.setToolTip("Producto padre del que deriva esta variante")
        form.addRow("Producto Padre:", self.parent_product_combo)

        self.variant_group_input = QLineEdit()
        self.variant_group_input.setPlaceholderText("Ej.: CAMISA-2024")
        self.variant_group_input.setToolTip(
            "Identificador de grupo que une todas las variantes del mismo producto"
        )
        form.addRow("Grupo Variante:", self.variant_group_input)

        self.variant_attributes_input = QLineEdit()
        self.variant_attributes_input.setPlaceholderText(
            "Ej.: color:rojo,talla:M"
        )
        self.variant_attributes_input.setToolTip(
            "Atributos que diferencian esta variante. Formato libre: clave:valor,clave:valor"
        )
        form.addRow("Atributos:", self.variant_attributes_input)

        return tab

    def _build_tab_kit(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel(
            "Un <b>Kit</b> es un producto compuesto por otros productos. "
            "Marca la casilla y agrega componentes con su cantidad."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.is_kit_check = QCheckBox("Este producto es un Kit")
        self.is_kit_check.toggled.connect(self._on_kit_toggled)
        layout.addWidget(self.is_kit_check)

        # Component search row
        search_row = QHBoxLayout()
        self.kit_component_combo = QComboBox()
        self.kit_component_combo.setMinimumWidth(200)
        self.kit_component_combo.setEnabled(False)
        search_row.addWidget(QLabel("Componente:"))
        search_row.addWidget(self.kit_component_combo)

        self.kit_qty_spin = QSpinBox()
        self.kit_qty_spin.setRange(1, 9999)
        self.kit_qty_spin.setValue(1)
        self.kit_qty_spin.setEnabled(False)
        search_row.addWidget(QLabel("Cant.:"))
        search_row.addWidget(self.kit_qty_spin)

        self.kit_add_btn = QPushButton("Agregar")
        self.kit_add_btn.setEnabled(False)
        self.kit_add_btn.clicked.connect(self._on_kit_add_component)
        search_row.addWidget(self.kit_add_btn)
        layout.addLayout(search_row)

        # Components table
        self.kit_table = QTableWidget()
        self.kit_table.setColumnCount(4)
        self.kit_table.setHorizontalHeaderLabels(["ID", "SKU", "Nombre", "Cantidad"])
        self.kit_table.setColumnHidden(0, True)
        self.kit_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.kit_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.kit_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.kit_table)

        self.kit_remove_btn = QPushButton("Quitar componente seleccionado")
        self.kit_remove_btn.setEnabled(False)
        self.kit_remove_btn.clicked.connect(self._on_kit_remove_component)
        layout.addWidget(self.kit_remove_btn)

        return tab

    def _build_tab_fiscal(self) -> QWidget:
        tab = QWidget()
        form = self._form()
        tab.setLayout(form)

        lbl = QLabel(
            "Campos opcionales para cumplimiento fiscal (SAT México). "
            "El sistema guarda los códigos tal como se ingresan; "
            "no valida contra el catálogo del SAT."
        )
        lbl.setWordWrap(True)
        form.addRow(lbl)

        self.sat_code_input = QLineEdit()
        self.sat_code_input.setPlaceholderText("Ej.: 43211500")
        self.sat_code_input.setToolTip(
            "Clave de Producto/Servicio del catálogo SAT (claveProdServ)"
        )
        form.addRow("Código SAT:", self.sat_code_input)

        self.tariff_code_input = QLineEdit()
        self.tariff_code_input.setPlaceholderText("Ej.: 8414.59.99")
        self.tariff_code_input.setToolTip("Fracción arancelaria del producto")
        form.addRow("Fracción Arancelaria:", self.tariff_code_input)

        self.country_input = QLineEdit()
        self.country_input.setPlaceholderText("México")
        self.country_input.setToolTip("País de origen del producto")
        form.addRow("País de Origen:", self.country_input)

        return tab

    # ------------------------------------------------------------------
    # Combo population
    # ------------------------------------------------------------------

    def _populate_combos(self):
        """Fill all combo boxes from the database."""
        # ── Categories (hierarchical flat list) ────────────────────────
        self.category_combo.clear()
        self.category_combo.addItem("— Sin categoría —", _NONE_ID)
        try:
            for cat in self._cat_service.get_flat_category_list():
                self.category_combo.addItem(cat["display_name"], cat["id"])
        except Exception as exc:
            logger.warning(f"Could not load categories: {exc}")

        # ── Suppliers ─────────────────────────────────────────────────
        self.supplier_combo.clear()
        self.supplier_combo.addItem("— Sin proveedor —", _NONE_ID)
        try:
            for sup in self._sup_service.get_all_suppliers():
                self.supplier_combo.addItem(sup["name"], sup["id"])
        except Exception as exc:
            logger.warning(f"Could not load suppliers: {exc}")

        # ── Replacement product ────────────────────────────────────────
        self.replacement_combo.clear()
        self.replacement_combo.addItem("— Sin reemplazo —", _NONE_ID)
        try:
            for p in self._product_service.get_all_active_products():
                pid = self.product_data.get("id")
                if pid and p["id"] == pid:
                    continue  # skip self
                self.replacement_combo.addItem(f"{p['sku']} – {p['name']}", p["id"])
        except Exception as exc:
            logger.warning(f"Could not load replacement products: {exc}")

        # ── Parent product (variant tab) ───────────────────────────────
        self.parent_product_combo.clear()
        self.parent_product_combo.addItem("— Sin padre (producto normal) —", _NONE_ID)
        try:
            for p in self._product_service.get_parent_products():
                pid = self.product_data.get("id")
                if pid and p["id"] == pid:
                    continue
                self.parent_product_combo.addItem(f"{p['sku']} – {p['name']}", p["id"])
        except Exception as exc:
            logger.warning(f"Could not load parent products: {exc}")

        # ── Kit component search combo ─────────────────────────────────
        self.kit_component_combo.clear()
        try:
            for p in self._product_service.get_all_active_products():
                pid = self.product_data.get("id")
                if pid and p["id"] == pid:
                    continue
                self.kit_component_combo.addItem(f"{p['sku']} – {p['name']}", p["id"])
        except Exception as exc:
            logger.warning(f"Could not load kit components: {exc}")

    # ------------------------------------------------------------------
    # Field fill (edit mode)
    # ------------------------------------------------------------------

    def _fill_fields(self):
        d = self.product_data

        # General
        self.sku_input.setText(d.get("sku") or "")
        self.name_input.setText(d.get("name") or "")
        self.unit_input.setText(d.get("unit_of_measure") or "unidad")
        self.price_input.setValue(d.get("unit_price") or 0.0)
        self.brand_input.setText(d.get("brand") or "")
        _set_combo_by_id(self.category_combo, d.get("category_id"))
        _set_combo_by_id(self.supplier_combo, d.get("default_supplier_id"))
        _set_combo_by_value(self.status_combo, d.get("product_status") or "active")
        _set_combo_by_id(self.replacement_combo, d.get("replacement_product_id"))

        # Detail
        self.description_input.setPlainText(d.get("description") or "")
        self.details_input.setPlainText(d.get("details") or "")
        self.notes_input.setPlainText(d.get("internal_notes") or "")
        self.min_stock_input.setValue(d.get("global_min_stock") or 0)

        # Variant
        _set_combo_by_id(self.parent_product_combo, d.get("parent_product_id"))
        self.variant_group_input.setText(d.get("variant_group_id") or "")
        self.variant_attributes_input.setText(d.get("variant_attributes") or "")

        # Kit
        is_kit = bool(d.get("is_kit", False))
        self.is_kit_check.setChecked(is_kit)
        self._on_kit_toggled(is_kit)
        if is_kit and d.get("id"):
            self._load_kit_components(d["id"])

        # Fiscal
        self.sat_code_input.setText(d.get("sat_product_code") or "")
        self.tariff_code_input.setText(d.get("customs_tariff_code") or "")
        self.country_input.setText(d.get("country_of_origin") or "México")

    # ------------------------------------------------------------------
    # Kit tab helpers
    # ------------------------------------------------------------------

    def _on_kit_toggled(self, checked: bool):
        self.kit_component_combo.setEnabled(checked)
        self.kit_qty_spin.setEnabled(checked)
        self.kit_add_btn.setEnabled(checked)
        self.kit_remove_btn.setEnabled(checked)

    def _load_kit_components(self, product_id: int):
        """Populate kit table from the database (edit mode)."""
        try:
            components = self._kit_service.get_kit_components(product_id)
        except Exception as exc:
            logger.warning(f"Could not load kit components: {exc}")
            return
        self.kit_table.setRowCount(0)
        for comp in components:
            cp = comp.get("component_product") or {}
            self._kit_table_add_row(
                comp_id=comp["component_product_id"],
                sku=cp.get("sku", ""),
                name=cp.get("name", ""),
                qty=comp["quantity"],
            )

    def _kit_table_add_row(self, comp_id: int, sku: str, name: str, qty: int):
        row = self.kit_table.rowCount()
        self.kit_table.insertRow(row)
        self.kit_table.setItem(row, 0, QTableWidgetItem(str(comp_id)))
        self.kit_table.setItem(row, 1, QTableWidgetItem(sku))
        self.kit_table.setItem(row, 2, QTableWidgetItem(name))
        self.kit_table.setItem(row, 3, QTableWidgetItem(str(qty)))

    def _on_kit_add_component(self):
        comp_id = _combo_current_id(self.kit_component_combo)
        if comp_id is None:
            QMessageBox.warning(self, "Error", "Selecciona un componente")
            return
        qty = self.kit_qty_spin.value()

        # Check for duplicate in table
        for row in range(self.kit_table.rowCount()):
            if int(self.kit_table.item(row, 0).text()) == comp_id:
                QMessageBox.warning(self, "Duplicado", "Este componente ya está en el kit")
                return

        sku_name = self.kit_component_combo.currentText()
        parts = sku_name.split(" – ", 1)
        sku = parts[0] if parts else ""
        name = parts[1] if len(parts) > 1 else sku_name

        self._kit_table_add_row(comp_id=comp_id, sku=sku, name=name, qty=qty)
        self._pending_components.append({"component_product_id": comp_id, "quantity": qty})

    def _on_kit_remove_component(self):
        selected = self.kit_table.selectedItems()
        if not selected:
            QMessageBox.information(self, "Info", "Selecciona un componente para quitar")
            return
        row = self.kit_table.currentRow()
        self.kit_table.removeRow(row)

    def _get_kit_components_from_table(self) -> list:
        """Return all kit component rows from the table widget."""
        components = []
        for row in range(self.kit_table.rowCount()):
            comp_id = int(self.kit_table.item(row, 0).text())
            qty = int(self.kit_table.item(row, 3).text())
            components.append({"component_product_id": comp_id, "quantity": qty})
        return components

    # ------------------------------------------------------------------
    # get_data
    # ------------------------------------------------------------------

    def get_data(self) -> dict:
        """Return all form values as a dict ready for ProductService."""
        min_stock = self.min_stock_input.value()
        return {
            # General
            "sku": self.sku_input.text().strip(),
            "name": self.name_input.text().strip(),
            "unit_of_measure": self.unit_input.text().strip() or "unidad",
            "unit_price": self.price_input.value(),
            "category_id": _combo_current_id(self.category_combo),
            "brand": self.brand_input.text().strip() or None,
            "default_supplier_id": _combo_current_id(self.supplier_combo),
            "product_status": self.status_combo.currentData() or "active",
            "replacement_product_id": _combo_current_id(self.replacement_combo),
            # Detail
            "description": self.description_input.toPlainText().strip() or None,
            "details": self.details_input.toPlainText().strip() or None,
            "internal_notes": self.notes_input.toPlainText().strip() or None,
            "global_min_stock": min_stock if min_stock > 0 else None,
            # Variant
            "parent_product_id": _combo_current_id(self.parent_product_combo),
            "variant_group_id": self.variant_group_input.text().strip() or None,
            "variant_attributes": self.variant_attributes_input.text().strip() or None,
            # Kit
            "is_kit": self.is_kit_check.isChecked(),
            "_kit_components": self._get_kit_components_from_table(),
            # Fiscal
            "sat_product_code": self.sat_code_input.text().strip() or None,
            "customs_tariff_code": self.tariff_code_input.text().strip() or None,
            "country_of_origin": self.country_input.text().strip() or "México",
        }


# ======================================================================
# Change History Dialog
# ======================================================================

class ProductChangeHistoryDialog(QDialog):
    """Read-only dialog showing field-level change log for a product."""

    def __init__(self, db: Session, product_id: int, product_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Historial de Cambios – {product_name}")
        self.setMinimumSize(640, 400)

        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Campo", "Valor Anterior", "Valor Nuevo", "Fecha", "Modificado por"]
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.table)

        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

        self._load(db, product_id)

    def _load(self, db: Session, product_id: int):
        try:
            service = ProductService(db)
            entries = service.get_product_change_history(product_id, limit=200)
        except Exception as exc:
            logger.error(f"Could not load change history: {exc}")
            return

        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self.table.setItem(row, 0, QTableWidgetItem(entry.get("field_name") or ""))
            self.table.setItem(row, 1, QTableWidgetItem(entry.get("old_value") or ""))
            self.table.setItem(row, 2, QTableWidgetItem(entry.get("new_value") or ""))
            changed_at = entry.get("changed_at") or ""
            if changed_at and "T" in changed_at:
                changed_at = changed_at.replace("T", " ")[:19]
            self.table.setItem(row, 3, QTableWidgetItem(changed_at))
            self.table.setItem(row, 4, QTableWidgetItem(entry.get("changed_by_name") or ""))


# ======================================================================
# Variant Summary Dialog
# ======================================================================

class VariantSummaryDialog(QDialog):
    """Shows the parent product and all its variants."""

    def __init__(self, db: Session, product_id: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Variantes del Producto")
        self.setMinimumSize(560, 340)

        layout = QVBoxLayout(self)
        try:
            service = ProductService(db)
            summary = service.get_variant_summary(product_id)
        except Exception as exc:
            layout.addWidget(QLabel(f"Error: {exc}"))
            return

        parent_p = summary.get("parent") or {}
        layout.addWidget(
            QLabel(f"<b>Producto base:</b> {parent_p.get('sku','')} – {parent_p.get('name','')}")
        )
        layout.addWidget(
            QLabel(f"Total variantes: {summary.get('total_variants', 0)}")
        )

        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["SKU", "Nombre", "Atributos", "Estado"])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        variants = summary.get("variants", [])
        table.setRowCount(len(variants))
        for row, v in enumerate(variants):
            table.setItem(row, 0, QTableWidgetItem(v.get("sku") or ""))
            table.setItem(row, 1, QTableWidgetItem(v.get("name") or ""))
            table.setItem(row, 2, QTableWidgetItem(v.get("variant_attributes") or ""))
            status = v.get("product_status") or "active"
            table.setItem(row, 3, QTableWidgetItem(_STATUS_LABELS.get(status, status)))
        layout.addWidget(table)

        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)


# ======================================================================
# ProductListView
# ======================================================================

class ProductListView(QWidget):
    """Product list view widget.

    Columns: SKU | Nombre | Marca | Categoría | Unidad | Precio | Estado | Acciones
    Filter bar: text search + category filter + brand filter + status filter
    """

    product_selected = pyqtSignal(int)

    def __init__(self, db: Session, current_user=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.current_user = current_user
        self.is_employee = bool(getattr(current_user, "role", None) == "empleado")
        self.service = ProductService(db)
        self._cat_service = CategoryService(db)
        self._sup_service = SupplierService(db)
        self.setup_ui()
        self._populate_filter_combos()
        self.load_products()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Header
        header = QHBoxLayout()
        title = QLabel("Gestión de Productos")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar productos…")
        self.search_input.setMaximumWidth(220)
        self.search_input.textChanged.connect(self._on_filter_changed)
        header.addWidget(self.search_input)

        self.add_button = QPushButton("+ Nuevo Producto")
        self.add_button.clicked.connect(self.on_add_product)
        header.addWidget(self.add_button)
        if self.is_employee:
            self.add_button.setVisible(False)
        layout.addLayout(header)

        # Filter bar
        filter_bar = QHBoxLayout()

        filter_bar.addWidget(QLabel("Categoría:"))
        self.cat_filter = QComboBox()
        self.cat_filter.setMinimumWidth(160)
        self.cat_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_bar.addWidget(self.cat_filter)

        filter_bar.addSpacing(8)
        filter_bar.addWidget(QLabel("Marca:"))
        self.brand_filter = QComboBox()
        self.brand_filter.setMinimumWidth(130)
        self.brand_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_bar.addWidget(self.brand_filter)

        filter_bar.addSpacing(8)
        filter_bar.addWidget(QLabel("Estado:"))
        self.status_filter = QComboBox()
        self.status_filter.setMinimumWidth(150)
        self.status_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_bar.addWidget(self.status_filter)

        filter_bar.addStretch()
        layout.addLayout(filter_bar)

        # Table: 0=ID(hidden), 1=SKU, 2=Nombre, 3=Marca, 4=Categoría,
        #        5=Unidad, 6=Precio, 7=Estado, 8=Acciones
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "ID", "SKU", "Nombre", "Marca", "Categoría",
            "Unidad", "Precio", "Estado", "Acciones",
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.table)

    # ------------------------------------------------------------------
    # Filter combos
    # ------------------------------------------------------------------

    def _populate_filter_combos(self):
        # Categories – hierarchical flat list
        self.cat_filter.blockSignals(True)
        self.cat_filter.clear()
        self.cat_filter.addItem("Todas las categorías", _NONE_ID)
        try:
            for cat in self._cat_service.get_flat_category_list():
                self.cat_filter.addItem(cat["display_name"], cat["id"])
        except Exception as exc:
            logger.warning(f"Could not load category filters: {exc}")
        self.cat_filter.blockSignals(False)

        # Brands
        self.brand_filter.blockSignals(True)
        self.brand_filter.clear()
        self.brand_filter.addItem("Todas las marcas", None)
        try:
            for brand in self.service.get_distinct_brands():
                self.brand_filter.addItem(brand, brand)
        except Exception as exc:
            logger.warning(f"Could not load brand filters: {exc}")
        self.brand_filter.blockSignals(False)

        # Status
        self.status_filter.blockSignals(True)
        self.status_filter.clear()
        self.status_filter.addItem("Todos los estados", None)
        for val, label in _STATUS_LABELS.items():
            self.status_filter.addItem(label, val)
        self.status_filter.blockSignals(False)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def load_products(self):
        search = self.search_input.text().strip() or None
        category_id = _combo_current_id(self.cat_filter)
        brand = self.brand_filter.currentData()
        status_filter = self.status_filter.currentData()

        # Build category name lookup
        cat_names: dict = {}
        for i in range(self.cat_filter.count()):
            cid = self.cat_filter.itemData(i)
            if cid and cid != _NONE_ID:
                cat_names[cid] = self.cat_filter.itemText(i).strip()

        try:
            result = self.service.list_products(
                page=1,
                page_size=500,
                search=search,
                category_id=category_id,
                brand=brand,
            )
        except Exception as exc:
            logger.error(f"Error loading products: {exc}")
            return

        products = result["products"]

        # Apply status filter client-side (no extra DB query needed)
        if status_filter:
            products = [p for p in products if p.get("product_status") == status_filter]

        self.table.setRowCount(len(products))

        for row, p in enumerate(products):
            self.table.setItem(row, 0, QTableWidgetItem(str(p["id"])))
            self.table.setItem(row, 1, QTableWidgetItem(p["sku"]))

            # Nombre with variant / kit badges
            name_text = p["name"]
            badges = []
            if p.get("parent_product_id"):
                badges.append("[VAR]")
            if p.get("is_kit"):
                badges.append("[KIT]")
            if badges:
                name_text = " ".join(badges) + " " + name_text
            self.table.setItem(row, 2, QTableWidgetItem(name_text))

            self.table.setItem(row, 3, QTableWidgetItem(p.get("brand") or ""))

            cid = p.get("category_id")
            cat_label = cat_names.get(cid, "") if cid else ""
            self.table.setItem(row, 4, QTableWidgetItem(cat_label))

            self.table.setItem(row, 5, QTableWidgetItem(p["unit_of_measure"]))
            price = p.get("unit_price") or 0.0
            self.table.setItem(row, 6, QTableWidgetItem(f"${price:.2f}"))

            status = p.get("product_status") or "active"
            self.table.setItem(row, 7, QTableWidgetItem(_STATUS_LABELS.get(status, status)))

            self.table.setCellWidget(row, 8, self._make_action_widget(p["id"], p))

        self.table.resizeColumnsToContents()
        # Keep Nombre stretched after resize
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )

    def _make_action_widget(self, product_id: int, product_data: dict) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        if not self.is_employee:
            edit_btn = QPushButton("Editar")
            edit_btn.setFixedHeight(24)
            edit_btn.clicked.connect(lambda: self.on_edit_product(product_id))
            layout.addWidget(edit_btn)

        hist_btn = QPushButton("Historial")
        hist_btn.setFixedHeight(24)
        hist_btn.setToolTip("Ver historial de cambios")
        hist_btn.clicked.connect(
            lambda: self.on_view_history(product_id, product_data.get("name", ""))
        )
        layout.addWidget(hist_btn)

        # "Variantes" button only for products that have/could have variants
        if product_data.get("variant_group_id") or product_data.get("parent_product_id") is None:
            var_btn = QPushButton("Variantes")
            var_btn.setFixedHeight(24)
            var_btn.clicked.connect(lambda: self.on_view_variants(product_id))
            layout.addWidget(var_btn)

        if not self.is_employee:
            del_btn = QPushButton("Eliminar")
            del_btn.setFixedHeight(24)
            del_btn.setStyleSheet("color: #c62828;")
            del_btn.clicked.connect(lambda: self.on_delete_product(product_id))
            layout.addWidget(del_btn)

        return widget

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_filter_changed(self, *_):
        self.load_products()

    def on_add_product(self):
        dialog = ProductDialog(self.db, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data["sku"] or not data["name"]:
                QMessageBox.warning(self, "Error", "SKU y Nombre son requeridos")
                return
            try:
                kit_components = data.pop("_kit_components", [])
                product = self.service.create_product(data)
                # Persist kit components if any
                if data.get("is_kit") and kit_components:
                    self._save_kit_components(product["id"], kit_components)
                QMessageBox.information(self, "Éxito", "Producto creado exitosamente")
                self._populate_filter_combos()
                self.load_products()
            except Exception as exc:
                QMessageBox.critical(self, "Error", f"Error al crear producto:\n{exc}")

    def on_edit_product(self, product_id: int):
        product = self.service.get_product(product_id)
        if not product:
            return
        dialog = ProductDialog(self.db, parent=self, product_data=product)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data["sku"] or not data["name"]:
                QMessageBox.warning(self, "Error", "SKU y Nombre son requeridos")
                return
            try:
                kit_components = data.pop("_kit_components", [])
                self.service.update_product(product_id, data)
                # Sync kit components: replace all
                if data.get("is_kit"):
                    self._replace_kit_components(product_id, kit_components)
                QMessageBox.information(self, "Éxito", "Producto actualizado exitosamente")
                self._populate_filter_combos()
                self.load_products()
            except Exception as exc:
                QMessageBox.critical(self, "Error", f"Error al actualizar producto:\n{exc}")

    def on_delete_product(self, product_id: int):
        reply = QMessageBox.question(
            self,
            "Confirmar eliminación",
            "¿Está seguro de eliminar este producto?\nEsta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.service.delete_product(product_id)
                QMessageBox.information(self, "Éxito", "Producto eliminado exitosamente")
                self._populate_filter_combos()
                self.load_products()
            except Exception as exc:
                QMessageBox.critical(self, "Error", f"Error al eliminar producto:\n{exc}")

    def on_view_history(self, product_id: int, product_name: str):
        dialog = ProductChangeHistoryDialog(
            self.db, product_id, product_name, parent=self
        )
        dialog.exec()

    def on_view_variants(self, product_id: int):
        dialog = VariantSummaryDialog(self.db, product_id, parent=self)
        dialog.exec()

    # ------------------------------------------------------------------
    # Kit component persistence helpers
    # ------------------------------------------------------------------

    def _save_kit_components(self, product_id: int, components: list):
        """Add all components from the table to an existing kit product."""
        kit_service = KitService(self.db)
        for comp in components:
            try:
                kit_service.add_component(
                    kit_product_id=product_id,
                    component_product_id=comp["component_product_id"],
                    quantity=comp["quantity"],
                )
            except Exception as exc:
                logger.warning(f"Could not add kit component: {exc}")

    def _replace_kit_components(self, product_id: int, components: list):
        """Replace all kit components for a product (used on edit save)."""
        from modules.products.repository import KitComponentRepository
        repo = KitComponentRepository(self.db)
        repo.remove_all(product_id)
        self._save_kit_components(product_id, components)
