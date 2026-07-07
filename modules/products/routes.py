"""
Product GUI routes/controllers for PyQt6 interface.

ProductDialog now shows ALL fields from the expansion plan:
  – Original: SKU, Nombre, Descripción, Unidad de Medida, Precio Unitario
  – Exp 1:  Categoría       (QComboBox populated from CategoryService)
  – Exp 2:  Marca           (QLineEdit)
  – Exp 3:  Proveedor       (QComboBox populated from SupplierService)
  – Exp 4:  Detalles        (QTextEdit)
  – Exp 5:  Notas Internas  (QTextEdit)
  – Exp 6:  Stock Mín. Global (QSpinBox)

The dialog is organized in two tabs to avoid a very tall form:
  Tab 1 – "General":  SKU, Nombre, Categoría, Marca, Proveedor,
                       Unidad de Medida, Precio Unitario
  Tab 2 – "Detalle":  Descripción, Detalles, Notas Internas,
                       Stock Mínimo Global

ProductListView table gains two extra visible columns: Marca, Categoría.
Filter bar gains a category combo and a brand combo.
"""

import logging
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
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

from modules.products.service import CategoryService, ProductService, SupplierService

logger = logging.getLogger(__name__)

# Sentinel value used in the "sin categoría / sin proveedor" combo entry
_NONE_ID = -1


def _combo_current_id(combo: QComboBox) -> Optional[int]:
    """Return the integer item-data of the current combo selection, or None."""
    value = combo.currentData()
    if value is None or value == _NONE_ID:
        return None
    return int(value)


class ProductDialog(QDialog):
    """Dialog for creating / editing a product.

    Accepts an optional *product_data* dict (from ``Product.to_dict()``) for
    edit mode.  All new fields default to None / empty so existing records
    without them open without errors.
    """

    def __init__(self, db: Session, parent=None, product_data: dict = None):
        super().__init__(parent)
        self.db = db
        self.product_data = product_data or {}
        self._cat_service = CategoryService(db)
        self._sup_service = SupplierService(db)
        self.setup_ui()
        self._populate_combos()
        self._fill_fields()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def setup_ui(self):
        """Build the two-tab form layout."""
        title = "Editar Producto" if self.product_data else "Nuevo Producto"
        self.setWindowTitle(title)
        self.setMinimumWidth(480)

        root = QVBoxLayout(self)

        tabs = QTabWidget()
        root.addWidget(tabs)

        # ── Tab 1: General ──────────────────────────────────────────────
        tab_general = QWidget()
        form_general = QFormLayout(tab_general)
        form_general.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form_general.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.sku_input = QLineEdit()
        self.sku_input.setPlaceholderText("Ej.: TEC-001 / 12345 / ABCDE")
        form_general.addRow("SKU *:", self.sku_input)

        self.name_input = QLineEdit()
        form_general.addRow("Nombre *:", self.name_input)

        self.category_combo = QComboBox()
        self.category_combo.setMinimumWidth(200)
        form_general.addRow("Categoría:", self.category_combo)

        self.brand_input = QLineEdit()
        self.brand_input.setPlaceholderText("Ej.: Bosch, Mabe, Genérico…")
        form_general.addRow("Marca:", self.brand_input)

        self.supplier_combo = QComboBox()
        self.supplier_combo.setMinimumWidth(200)
        form_general.addRow("Proveedor:", self.supplier_combo)

        self.unit_input = QLineEdit()
        self.unit_input.setPlaceholderText("unidad, kg, litro, caja…")
        form_general.addRow("Unidad de Medida *:", self.unit_input)

        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0, 9_999_999.99)
        self.price_input.setDecimals(2)
        self.price_input.setPrefix("$ ")
        form_general.addRow("Precio Unitario:", self.price_input)

        tabs.addTab(tab_general, "General")

        # ── Tab 2: Detalle ──────────────────────────────────────────────
        tab_detail = QWidget()
        form_detail = QFormLayout(tab_detail)
        form_detail.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form_detail.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.description_input = QTextEdit()
        self.description_input.setMaximumHeight(80)
        self.description_input.setPlaceholderText("Descripción breve del producto…")
        form_detail.addRow("Descripción:", self.description_input)

        self.details_input = QTextEdit()
        self.details_input.setMaximumHeight(90)
        self.details_input.setPlaceholderText(
            "Color, tamaño, presentación, especificaciones técnicas…"
        )
        form_detail.addRow("Detalles:", self.details_input)

        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(80)
        self.notes_input.setPlaceholderText(
            "Notas internas (solo para empleados)…"
        )
        form_detail.addRow("Notas Internas:", self.notes_input)

        self.min_stock_input = QSpinBox()
        self.min_stock_input.setRange(0, 999_999)
        self.min_stock_input.setSpecialValueText("Sin umbral")  # value=0 shows label
        self.min_stock_input.setToolTip(
            "Stock mínimo global sugerido. 0 = sin umbral definido."
        )
        form_detail.addRow("Stock Mín. Global:", self.min_stock_input)

        tabs.addTab(tab_detail, "Detalle")

        # ── Botones ─────────────────────────────────────────────────────
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

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _populate_combos(self):
        """Fill category and supplier combos from the database."""
        # Categories
        self.category_combo.clear()
        self.category_combo.addItem("— Sin categoría —", _NONE_ID)
        try:
            for cat in self._cat_service.get_all_categories():
                self.category_combo.addItem(cat["name"], cat["id"])
        except Exception as exc:
            logger.warning(f"Could not load categories: {exc}")

        # Suppliers
        self.supplier_combo.clear()
        self.supplier_combo.addItem("— Sin proveedor —", _NONE_ID)
        try:
            for sup in self._sup_service.get_all_suppliers():
                self.supplier_combo.addItem(sup["name"], sup["id"])
        except Exception as exc:
            logger.warning(f"Could not load suppliers: {exc}")

    def _fill_fields(self):
        """Populate all form fields from product_data (edit mode)."""
        d = self.product_data

        self.sku_input.setText(d.get("sku") or "")
        self.name_input.setText(d.get("name") or "")
        self.unit_input.setText(d.get("unit_of_measure") or "unidad")
        self.price_input.setValue(d.get("unit_price") or 0.0)
        self.brand_input.setText(d.get("brand") or "")
        self.description_input.setPlainText(d.get("description") or "")
        self.details_input.setPlainText(d.get("details") or "")
        self.notes_input.setPlainText(d.get("internal_notes") or "")

        # Stock mínimo: None → leave at 0 (shows "Sin umbral")
        self.min_stock_input.setValue(d.get("global_min_stock") or 0)

        # Category combo – select matching entry if set
        cat_id = d.get("category_id")
        if cat_id is not None:
            for i in range(self.category_combo.count()):
                if self.category_combo.itemData(i) == cat_id:
                    self.category_combo.setCurrentIndex(i)
                    break

        # Supplier combo
        sup_id = d.get("default_supplier_id")
        if sup_id is not None:
            for i in range(self.supplier_combo.count()):
                if self.supplier_combo.itemData(i) == sup_id:
                    self.supplier_combo.setCurrentIndex(i)
                    break

    def get_data(self) -> dict:
        """Return all form values as a dict ready for ProductService."""
        min_stock_value = self.min_stock_input.value()

        return {
            "sku": self.sku_input.text().strip(),
            "name": self.name_input.text().strip(),
            "description": self.description_input.toPlainText().strip() or None,
            "unit_of_measure": self.unit_input.text().strip() or "unidad",
            "unit_price": self.price_input.value(),
            # Expansions
            "category_id": _combo_current_id(self.category_combo),
            "brand": self.brand_input.text().strip() or None,
            "default_supplier_id": _combo_current_id(self.supplier_combo),
            "details": self.details_input.toPlainText().strip() or None,
            "internal_notes": self.notes_input.toPlainText().strip() or None,
            "global_min_stock": min_stock_value if min_stock_value > 0 else None,
        }


# ======================================================================
# Product list view
# ======================================================================

class ProductListView(QWidget):
    """Product list view widget.

    Table columns: SKU | Nombre | Marca | Categoría | Unidad | Precio | Acciones
    Filter bar: text search + category filter combo + brand filter combo.
    """

    product_selected = pyqtSignal(int)

    def __init__(self, db: Session, parent=None):
        super().__init__(parent)
        self.db = db
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

        # ── Header ──────────────────────────────────────────────────────
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

        layout.addLayout(header)

        # ── Filter bar ──────────────────────────────────────────────────
        filter_bar = QHBoxLayout()

        filter_bar.addWidget(QLabel("Categoría:"))
        self.cat_filter = QComboBox()
        self.cat_filter.setMinimumWidth(160)
        self.cat_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_bar.addWidget(self.cat_filter)

        filter_bar.addSpacing(12)

        filter_bar.addWidget(QLabel("Marca:"))
        self.brand_filter = QComboBox()
        self.brand_filter.setMinimumWidth(140)
        self.brand_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_bar.addWidget(self.brand_filter)

        filter_bar.addStretch()

        layout.addLayout(filter_bar)

        # ── Table ────────────────────────────────────────────────────────
        self.table = QTableWidget()
        # Columns: 0=ID(hidden), 1=SKU, 2=Nombre, 3=Marca, 4=Categoría,
        #           5=Unidad, 6=Precio, 7=Acciones
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "SKU", "Nombre", "Marca", "Categoría",
            "Unidad", "Precio", "Acciones",
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setStretchLastSection(False)

        layout.addWidget(self.table)

    # ------------------------------------------------------------------
    # Filter combos
    # ------------------------------------------------------------------

    def _populate_filter_combos(self):
        """Fill category and brand filter combos."""
        # Categories
        self.cat_filter.blockSignals(True)
        self.cat_filter.clear()
        self.cat_filter.addItem("Todas las categorías", _NONE_ID)
        try:
            for cat in self._cat_service.get_all_categories():
                self.cat_filter.addItem(cat["name"], cat["id"])
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

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def load_products(self):
        """Reload the table applying current filters."""
        search = self.search_input.text().strip() or None
        category_id = _combo_current_id(self.cat_filter)
        brand = self.brand_filter.currentData()  # str or None

        # Build a category name → id lookup from current combo for display
        cat_names: dict = {}
        for i in range(self.cat_filter.count()):
            cid = self.cat_filter.itemData(i)
            if cid and cid != _NONE_ID:
                cat_names[cid] = self.cat_filter.itemText(i)

        try:
            result = self.service.list_products(
                page=1,
                page_size=200,
                search=search,
                category_id=category_id,
                brand=brand,
            )
        except Exception as exc:
            logger.error(f"Error loading products: {exc}")
            return

        products = result["products"]
        self.table.setRowCount(len(products))

        for row, p in enumerate(products):
            # 0 – ID (hidden)
            self.table.setItem(row, 0, QTableWidgetItem(str(p["id"])))
            # 1 – SKU
            self.table.setItem(row, 1, QTableWidgetItem(p["sku"]))
            # 2 – Nombre
            self.table.setItem(row, 2, QTableWidgetItem(p["name"]))
            # 3 – Marca
            self.table.setItem(row, 3, QTableWidgetItem(p.get("brand") or ""))
            # 4 – Categoría (resolve name from combo cache)
            cid = p.get("category_id")
            cat_label = cat_names.get(cid, "") if cid else ""
            self.table.setItem(row, 4, QTableWidgetItem(cat_label))
            # 5 – Unidad
            self.table.setItem(row, 5, QTableWidgetItem(p["unit_of_measure"]))
            # 6 – Precio
            price = p.get("unit_price") or 0.0
            self.table.setItem(row, 6, QTableWidgetItem(f"${price:.2f}"))
            # 7 – Acciones
            self.table.setCellWidget(row, 7, self._make_action_widget(p["id"]))

        self.table.resizeColumnsToContents()

    def _make_action_widget(self, product_id: int) -> QWidget:
        """Create the Edit / Delete buttons cell widget."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        edit_btn = QPushButton("Editar")
        edit_btn.setFixedHeight(26)
        edit_btn.clicked.connect(lambda: self.on_edit_product(product_id))
        layout.addWidget(edit_btn)

        del_btn = QPushButton("Eliminar")
        del_btn.setFixedHeight(26)
        del_btn.setStyleSheet("color: #c62828;")
        del_btn.clicked.connect(lambda: self.on_delete_product(product_id))
        layout.addWidget(del_btn)

        return widget

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_filter_changed(self, *_):
        """Reload whenever any filter changes."""
        self.load_products()

    def on_add_product(self):
        dialog = ProductDialog(self.db, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if not data["sku"] or not data["name"]:
                QMessageBox.warning(self, "Error", "SKU y Nombre son requeridos")
                return
            try:
                self.service.create_product(data)
                QMessageBox.information(self, "Éxito", "Producto creado exitosamente")
                self._populate_filter_combos()  # brand list may have grown
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
                self.service.update_product(product_id, data)
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
