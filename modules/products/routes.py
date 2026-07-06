"""
Product GUI routes/controllers for PyQt6 interface.
"""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel, QLineEdit,
    QMessageBox, QDialog, QFormLayout, QTextEdit, QDoubleSpinBox,
    QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from modules.products.service import ProductService
import logging

logger = logging.getLogger(__name__)


class ProductDialog(QDialog):
    """Dialog for creating/editing products."""

    def __init__(self, parent=None, product_data: dict = None):
        super().__init__(parent)
        self.product_data = product_data or {}
        self.setup_ui()

    def setup_ui(self):
        """Setup dialog UI."""
        self.setWindowTitle("Producto" if not self.product_data else "Editar Producto")
        self.setMinimumWidth(400)

        layout = QFormLayout()

        # SKU
        self.sku_input = QLineEdit()
        self.sku_input.setText(self.product_data.get("sku", ""))
        layout.addRow("SKU*:", self.sku_input)

        # Name
        self.name_input = QLineEdit()
        self.name_input.setText(self.product_data.get("name", ""))
        layout.addRow("Nombre*:", self.name_input)

        # Description
        self.description_input = QTextEdit()
        self.description_input.setPlainText(self.product_data.get("description", ""))
        self.description_input.setMaximumHeight(100)
        layout.addRow("Descripcion:", self.description_input)

        # Unit of measure
        self.unit_input = QLineEdit()
        self.unit_input.setText(self.product_data.get("unit_of_measure", "unidad"))
        layout.addRow("Unidad de Medida*:", self.unit_input)

        # Unit price
        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0, 9999999.99)
        self.price_input.setDecimals(2)
        self.price_input.setValue(self.product_data.get("unit_price", 0.0))
        layout.addRow("Precio Unitario:", self.price_input)

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
            "sku": self.sku_input.text().strip(),
            "name": self.name_input.text().strip(),
            "description": self.description_input.toPlainText().strip(),
            "unit_of_measure": self.unit_input.text().strip(),
            "unit_price": self.price_input.value()
        }


class ProductListView(QWidget):
    """Product list view widget."""

    product_selected = pyqtSignal(int)  # Emits product ID

    def __init__(self, db: Session, parent=None):
        super().__init__(parent)
        self.db = db
        self.service = ProductService(db)
        self.setup_ui()
        self.load_products()

    def setup_ui(self):
        """Setup UI components."""
        layout = QVBoxLayout()

        # Header
        header_layout = QHBoxLayout()

        title = QLabel("Gestion de Productos")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar productos...")
        self.search_input.setMaximumWidth(300)
        self.search_input.textChanged.connect(self.on_search)
        header_layout.addWidget(self.search_input)

        # Add button
        self.add_button = QPushButton("Nuevo Producto")
        self.add_button.clicked.connect(self.on_add_product)
        header_layout.addWidget(self.add_button)

        layout.addLayout(header_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "SKU", "Nombre", "Unidad", "Precio", "Acciones"
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setColumnHidden(0, True)  # Hide ID column

        layout.addWidget(self.table)

        self.setLayout(layout)

    def load_products(self, search: str = None):
        """Load products into table."""
        result = self.service.list_products(page=1, page_size=100, search=search)
        products = result["products"]

        self.table.setRowCount(len(products))

        for row, product in enumerate(products):
            # ID (hidden)
            self.table.setItem(row, 0, QTableWidgetItem(str(product["id"])))

            # SKU
            self.table.setItem(row, 1, QTableWidgetItem(product["sku"]))

            # Name
            self.table.setItem(row, 2, QTableWidgetItem(product["name"]))

            # Unit
            self.table.setItem(row, 3, QTableWidgetItem(product["unit_of_measure"]))

            # Price
            price = product.get("unit_price", 0.0) or 0.0
            self.table.setItem(row, 4, QTableWidgetItem(f"${price:.2f}"))

            # Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(5, 5, 5, 5)

            edit_btn = QPushButton("Editar")
            edit_btn.clicked.connect(lambda checked, pid=product["id"]: self.on_edit_product(pid))
            actions_layout.addWidget(edit_btn)

            delete_btn = QPushButton("Eliminar")
            delete_btn.clicked.connect(lambda checked, pid=product["id"]: self.on_delete_product(pid))
            actions_layout.addWidget(delete_btn)

            self.table.setCellWidget(row, 5, actions_widget)

        self.table.resizeColumnsToContents()

    def on_search(self, text: str):
        """Handle search."""
        self.load_products(search=text if text else None)

    def on_add_product(self):
        """Handle add product."""
        dialog = ProductDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                data = dialog.get_data()
                if not data["sku"] or not data["name"]:
                    QMessageBox.warning(self, "Error", "SKU y Nombre son requeridos")
                    return

                self.service.create_product(data)
                QMessageBox.information(self, "Exito", "Producto creado exitosamente")
                self.load_products()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al crear producto: {str(e)}")

    def on_edit_product(self, product_id: int):
        """Handle edit product."""
        product = self.service.get_product(product_id)
        if not product:
            return

        dialog = ProductDialog(self, product)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                data = dialog.get_data()
                if not data["sku"] or not data["name"]:
                    QMessageBox.warning(self, "Error", "SKU y Nombre son requeridos")
                    return

                self.service.update_product(product_id, data)
                QMessageBox.information(self, "Exito", "Producto actualizado exitosamente")
                self.load_products(self.search_input.text() or None)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al actualizar producto: {str(e)}")

    def on_delete_product(self, product_id: int):
        """Handle delete product."""
        reply = QMessageBox.question(
            self,
            "Confirmar",
            "¿Esta seguro de eliminar este producto?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.service.delete_product(product_id)
                QMessageBox.information(self, "Exito", "Producto eliminado exitosamente")
                self.load_products(self.search_input.text() or None)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al eliminar producto: {str(e)}")
