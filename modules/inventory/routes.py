"""
Inventory GUI routes/controllers for PyQt6 interface.
"""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel, QLineEdit,
    QMessageBox, QDialog, QFormLayout, QSpinBox, QComboBox,
    QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from modules.inventory.service import InventoryService
from modules.products.service import ProductService
from modules.branches.service import BranchService
import logging

logger = logging.getLogger(__name__)


class InventoryCountDialog(QDialog):
    """Dialog for recording inventory counts."""

    def __init__(self, db: Session, parent=None, inventory_data: dict = None):
        super().__init__(parent)
        self.db = db
        self.inventory_data = inventory_data or {}
        self.product_service = ProductService(db)
        self.branch_service = BranchService(db)
        self.setup_ui()

    def setup_ui(self):
        """Setup dialog UI."""
        self.setWindowTitle("Conteo de Inventario")
        self.setMinimumWidth(400)

        layout = QFormLayout()

        # Product selection
        self.product_combo = QComboBox()
        products = self.product_service.get_all_active_products()
        for product in products:
            self.product_combo.addItem(f"{product['sku']} - {product['name']}", product['id'])
        layout.addRow("Producto:", self.product_combo)

        # Branch selection
        self.branch_combo = QComboBox()
        branches = self.branch_service.get_all_active_branches()
        for branch in branches:
            self.branch_combo.addItem(branch['name'], branch['id'])
        layout.addRow("Sucursal:", self.branch_combo)

        # Physical stock
        self.physical_stock = QSpinBox()
        self.physical_stock.setRange(0, 999999)
        self.physical_stock.setValue(self.inventory_data.get("physical_stock", 0))
        layout.addRow("Stock Fisico:", self.physical_stock)

        # Buttons
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Guardar")
        self.save_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        layout.addRow(button_layout)

        self.setLayout(layout)

    def get_data(self) -> dict:
        """Get form data."""
        return {
            "product_id": self.product_combo.currentData(),
            "branch_id": self.branch_combo.currentData(),
            "physical_stock": self.physical_stock.value()
        }


class InventoryListView(QWidget):
    """Inventory list view widget."""

    inventory_selected = pyqtSignal(int)

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

    def setup_ui(self):
        """Setup UI components."""
        layout = QVBoxLayout()

        # Header
        header_layout = QHBoxLayout()

        title = QLabel("Gestion de Inventario")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Branch filter
        self.branch_combo = QComboBox()
        self.branch_combo.addItem("Todas las sucursales", None)
        branches = self.branch_service.get_all_active_branches()
        for branch in branches:
            self.branch_combo.addItem(branch['name'], branch['id'])
        self.branch_combo.currentIndexChanged.connect(self.on_branch_changed)
        header_layout.addWidget(QLabel("Sucursal:"))
        header_layout.addWidget(self.branch_combo)

        layout.addLayout(header_layout)

        # Filters
        filter_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar...")
        self.search_input.setMaximumWidth(300)
        self.search_input.textChanged.connect(self.on_search)
        filter_layout.addWidget(self.search_input)

        self.discrepancy_btn = QPushButton("Solo Discrepancias")
        self.discrepancy_btn.setCheckable(True)
        self.discrepancy_btn.clicked.connect(self.toggle_discrepancy_filter)
        filter_layout.addWidget(self.discrepancy_btn)

        self.low_stock_btn = QPushButton("Solo Stock Bajo")
        self.low_stock_btn.setCheckable(True)
        self.low_stock_btn.clicked.connect(self.toggle_low_stock_filter)
        filter_layout.addWidget(self.low_stock_btn)

        self.count_button = QPushButton("Registrar Conteo")
        self.count_button.clicked.connect(self.on_count_inventory)
        filter_layout.addWidget(self.count_button)

        filter_layout.addStretch()

        layout.addLayout(filter_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "ID", "Sucursal", "Producto", "Stock Fisico", "Stock Digital",
            "Diferencia", "Min Stock", "Estado", "Acciones"
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setColumnHidden(0, True)

        layout.addWidget(self.table)

        # Summary
        self.summary_group = QGroupBox("Resumen")
        summary_layout = QHBoxLayout()

        self.total_physical_label = QLabel("Stock Fisico Total: 0")
        self.total_digital_label = QLabel("Stock Digital Total: 0")
        self.discrepancy_label = QLabel("Discrepancias: 0")
        self.low_stock_label = QLabel("Stock Bajo: 0")

        summary_layout.addWidget(self.total_physical_label)
        summary_layout.addWidget(self.total_digital_label)
        summary_layout.addWidget(self.discrepancy_label)
        summary_layout.addWidget(self.low_stock_label)

        self.summary_group.setLayout(summary_layout)
        layout.addWidget(self.summary_group)

        self.setLayout(layout)

    def load_inventory(self, search: str = None):
        """Load inventory into table."""
        result = self.service.list_inventory(
            page=1,
            page_size=100,
            branch_id=self.current_branch_id,
            low_stock_only=self.show_low_stock_only,
            discrepancy_only=self.show_discrepancies_only
        )

        items = result["inventory"]
        self.table.setRowCount(len(items))

        for row, item in enumerate(items):
            # ID (hidden)
            self.table.setItem(row, 0, QTableWidgetItem(str(item["id"])))

            # Branch
            branch_name = item.get("branch", {}).get("name", "N/A")
            self.table.setItem(row, 1, QTableWidgetItem(branch_name))

            # Product
            product_name = item.get("product", {}).get("name", "N/A")
            sku = item.get("product", {}).get("sku", "")
            self.table.setItem(row, 2, QTableWidgetItem(f"{sku} - {product_name}"))

            # Physical stock
            self.table.setItem(row, 3, QTableWidgetItem(str(item["physical_stock"])))

            # Digital stock
            self.table.setItem(row, 4, QTableWidgetItem(str(item["digital_stock"])))

            # Difference
            diff = item["difference"]
            diff_item = QTableWidgetItem(str(diff))
            if diff != 0:
                diff_item.setBackground(Qt.GlobalColor.yellow if diff > 0 else Qt.GlobalColor.red)
            self.table.setItem(row, 5, diff_item)

            # Min stock
            self.table.setItem(row, 6, QTableWidgetItem(str(item["min_stock"])))

            # Status
            status = ""
            if item["has_discrepancy"]:
                status = "Discrepancia"
            elif item["is_low_stock"]:
                status = "Stock Bajo"
            else:
                status = "OK"
            self.table.setItem(row, 7, QTableWidgetItem(status))

            # Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(5, 5, 5, 5)

            adjust_btn = QPushButton("Ajustar")
            adjust_btn.clicked.connect(lambda checked, iid=item["id"]: self.on_adjust_inventory(iid))
            actions_layout.addWidget(adjust_btn)

            self.table.setCellWidget(row, 8, actions_widget)

        self.table.resizeColumnsToContents()
        self.update_summary()

    def update_summary(self):
        """Update summary labels."""
        totals = self.service.get_totals(self.current_branch_id)
        self.total_physical_label.setText(f"Stock Fisico Total: {totals['total_physical_stock']}")
        self.total_digital_label.setText(f"Stock Digital Total: {totals['total_digital_stock']}")
        self.discrepancy_label.setText(f"Discrepancias: {totals['discrepancy_count']}")
        self.low_stock_label.setText(f"Stock Bajo: {totals['low_stock_count']}")

    def on_branch_changed(self, index: int):
        """Handle branch filter change."""
        self.current_branch_id = self.branch_combo.currentData()
        self.load_inventory(self.search_input.text() or None)

    def on_search(self, text: str):
        """Handle search."""
        self.load_inventory(search=text if text else None)

    def toggle_discrepancy_filter(self, checked: bool):
        """Toggle discrepancy filter."""
        self.show_discrepancies_only = checked
        if checked:
            self.show_low_stock_only = False
            self.low_stock_btn.setChecked(False)
        self.load_inventory(self.search_input.text() or None)

    def toggle_low_stock_filter(self, checked: bool):
        """Toggle low stock filter."""
        self.show_low_stock_only = checked
        if checked:
            self.show_discrepancies_only = False
            self.discrepancy_btn.setChecked(False)
        self.load_inventory(self.search_input.text() or None)

    def on_count_inventory(self):
        """Handle inventory count."""
        dialog = InventoryCountDialog(self.db, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                data = dialog.get_data()
                self.service.adjust_physical_stock(
                    data["product_id"],
                    data["branch_id"],
                    data["physical_stock"]
                )
                QMessageBox.information(self, "Exito", "Conteo registrado exitosamente")
                self.load_inventory(self.search_input.text() or None)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al registrar conteo: {str(e)}")

    def on_adjust_inventory(self, inventory_id: int):
        """Handle inventory adjustment."""
        QMessageBox.information(self, "Info", "Use el modulo de movimientos para ajustes de inventario")
