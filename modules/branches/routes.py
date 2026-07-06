"""
Branch GUI routes/controllers for PyQt6 interface.
"""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel, QLineEdit,
    QMessageBox, QDialog, QFormLayout, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from modules.branches.service import BranchService
import logging

logger = logging.getLogger(__name__)


class BranchDialog(QDialog):
    """Dialog for creating/editing branches."""

    def __init__(self, parent=None, branch_data: dict = None):
        super().__init__(parent)
        self.branch_data = branch_data or {}
        self.setup_ui()

    def setup_ui(self):
        """Setup dialog UI."""
        self.setWindowTitle("Sucursal" if not self.branch_data else "Editar Sucursal")
        self.setMinimumWidth(400)

        layout = QFormLayout()

        # Name
        self.name_input = QLineEdit()
        self.name_input.setText(self.branch_data.get("name", ""))
        layout.addRow("Nombre*:", self.name_input)

        # Address
        self.address_input = QTextEdit()
        self.address_input.setPlainText(self.branch_data.get("address", ""))
        self.address_input.setMaximumHeight(100)
        layout.addRow("Direccion:", self.address_input)

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
            "name": self.name_input.text().strip(),
            "address": self.address_input.toPlainText().strip()
        }


class BranchListView(QWidget):
    """Branch list view widget."""

    branch_selected = pyqtSignal(int)  # Emits branch ID

    def __init__(self, db: Session, parent=None):
        super().__init__(parent)
        self.db = db
        self.service = BranchService(db)
        self.setup_ui()
        self.load_branches()

    def setup_ui(self):
        """Setup UI components."""
        layout = QVBoxLayout()

        # Header
        header_layout = QHBoxLayout()

        title = QLabel("Gestion de Sucursales")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar sucursales...")
        self.search_input.setMaximumWidth(300)
        self.search_input.textChanged.connect(self.on_search)
        header_layout.addWidget(self.search_input)

        # Add button
        self.add_button = QPushButton("Nueva Sucursal")
        self.add_button.clicked.connect(self.on_add_branch)
        header_layout.addWidget(self.add_button)

        layout.addLayout(header_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "ID", "Nombre", "Direccion", "Estado", "Acciones"
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setColumnHidden(0, True)  # Hide ID column

        layout.addWidget(self.table)

        self.setLayout(layout)

    def load_branches(self, search: str = None):
        """Load branches into table."""
        result = self.service.list_branches(page=1, page_size=100, search=search)
        branches = result["branches"]

        self.table.setRowCount(len(branches))

        for row, branch in enumerate(branches):
            # ID (hidden)
            self.table.setItem(row, 0, QTableWidgetItem(str(branch["id"])))

            # Name
            self.table.setItem(row, 1, QTableWidgetItem(branch["name"]))

            # Address
            self.table.setItem(row, 2, QTableWidgetItem(branch["address"] or "N/A"))

            # State
            status = "Activa" if branch["is_active"] else "Inactiva"
            self.table.setItem(row, 3, QTableWidgetItem(status))

            # Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(5, 5, 5, 5)

            edit_btn = QPushButton("Editar")
            edit_btn.clicked.connect(lambda checked, bid=branch["id"]: self.on_edit_branch(bid))
            actions_layout.addWidget(edit_btn)

            delete_btn = QPushButton("Eliminar")
            delete_btn.clicked.connect(lambda checked, bid=branch["id"]: self.on_delete_branch(bid))
            actions_layout.addWidget(delete_btn)

            self.table.setCellWidget(row, 4, actions_widget)

        self.table.resizeColumnsToContents()

    def on_search(self, text: str):
        """Handle search."""
        self.load_branches(search=text if text else None)

    def on_add_branch(self):
        """Handle add branch."""
        dialog = BranchDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                data = dialog.get_data()
                if not data["name"]:
                    QMessageBox.warning(self, "Error", "El nombre es requerido")
                    return

                self.service.create_branch(data)
                QMessageBox.information(self, "Exito", "Sucursal creada exitosamente")
                self.load_branches()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al crear sucursal: {str(e)}")

    def on_edit_branch(self, branch_id: int):
        """Handle edit branch."""
        branch = self.service.get_branch(branch_id)
        if not branch:
            return

        dialog = BranchDialog(self, branch)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                data = dialog.get_data()
                if not data["name"]:
                    QMessageBox.warning(self, "Error", "El nombre es requerido")
                    return

                self.service.update_branch(branch_id, data)
                QMessageBox.information(self, "Exito", "Sucursal actualizada exitosamente")
                self.load_branches(self.search_input.text() or None)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al actualizar sucursal: {str(e)}")

    def on_delete_branch(self, branch_id: int):
        """Handle delete branch."""
        reply = QMessageBox.question(
            self,
            "Confirmar",
            "¿Esta seguro de eliminar esta sucursal?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.service.delete_branch(branch_id)
                QMessageBox.information(self, "Exito", "Sucursal eliminada exitosamente")
                self.load_branches(self.search_input.text() or None)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al eliminar sucursal: {str(e)}")
