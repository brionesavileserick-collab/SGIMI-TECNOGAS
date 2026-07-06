"""
Movement GUI routes/controllers for PyQt6 interface.
"""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel, QLineEdit,
    QMessageBox, QDialog, QFormLayout, QSpinBox, QComboBox,
    QTextEdit, QGroupBox, QDateEdit, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate
from modules.movements.service import MovementService
from modules.products.service import ProductService
from modules.branches.service import BranchService
from config import MOVEMENT_TYPES, MOVEMENT_STATES
import logging

logger = logging.getLogger(__name__)


class MovementDialog(QDialog):
    """Dialog for creating movements."""

    def __init__(self, db: Session, user_id: int, parent=None):
        super().__init__(parent)
        self.db = db
        self.user_id = user_id
        self.product_service = ProductService(db)
        self.branch_service = BranchService(db)
        self.setup_ui()

    def setup_ui(self):
        """Setup dialog UI."""
        self.setWindowTitle("Nuevo Movimiento")
        self.setMinimumWidth(500)

        layout = QFormLayout()

        # Movement type
        self.type_combo = QComboBox()
        for type_key, type_label in MOVEMENT_TYPES.items():
            self.type_combo.addItem(type_label, type_key)
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        layout.addRow("Tipo de Movimiento*:", self.type_combo)

        # Product
        self.product_combo = QComboBox()
        products = self.product_service.get_all_active_products()
        for p in products:
            self.product_combo.addItem(f"{p['sku']} - {p['name']}", p['id'])
        layout.addRow("Producto*:", self.product_combo)

        # Origin branch
        self.branch_combo = QComboBox()
        branches = self.branch_service.get_all_active_branches()
        for b in branches:
            self.branch_combo.addItem(b['name'], b['id'])
        layout.addRow("Sucursal Origen*:", self.branch_combo)

        # Destination branch (for transfers)
        self.dest_branch_label = QLabel("Sucursal Destino*:")
        self.dest_branch_combo = QComboBox()
        for b in branches:
            self.dest_branch_combo.addItem(b['name'], b['id'])
        layout.addRow(self.dest_branch_label, self.dest_branch_combo)
        self.dest_branch_label.hide()
        self.dest_branch_combo.hide()

        # Quantity
        self.quantity_spin = QSpinBox()
        self.quantity_spin.setRange(1, 999999)
        self.quantity_spin.setValue(1)
        layout.addRow("Cantidad*:", self.quantity_spin)

        # Reason
        self.reason_input = QTextEdit()
        self.reason_input.setMaximumHeight(80)
        layout.addRow("Razon:", self.reason_input)

        # Notes
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(80)
        layout.addRow("Notas:", self.notes_input)

        # Buttons
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Crear")
        self.save_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        layout.addRow(button_layout)

        self.setLayout(layout)
        self.on_type_changed(0)

    def on_type_changed(self, index: int):
        """Handle movement type change."""
        movement_type = self.type_combo.currentData()
        show_destination = movement_type == "transferencia"

        self.dest_branch_label.setVisible(show_destination)
        self.dest_branch_combo.setVisible(show_destination)

    def get_data(self) -> dict:
        """Get form data."""
        return {
            "movement_type": self.type_combo.currentData(),
            "product_id": self.product_combo.currentData(),
            "branch_id": self.branch_combo.currentData(),
            "destination_branch_id": self.dest_branch_combo.currentData() if self.type_combo.currentData() == "transferencia" else None,
            "quantity": self.quantity_spin.value(),
            "reason": self.reason_input.toPlainText().strip(),
            "notes": self.notes_input.toPlainText().strip(),
            "user_id": self.user_id
        }


class MovementListView(QWidget):
    """Movement list view widget."""

    movement_selected = pyqtSignal(int)

    def __init__(self, db: Session, current_user_id: int, parent=None):
        super().__init__(parent)
        self.db = db
        self.current_user_id = current_user_id
        self.service = MovementService(db)
        self.branch_service = BranchService(db)
        self.current_branch_id = None
        self.current_type = None
        self.current_state = None
        self.setup_ui()
        self.load_movements()

    def setup_ui(self):
        """Setup UI components."""
        layout = QVBoxLayout()

        # Header
        header_layout = QHBoxLayout()

        title = QLabel("Gestion de Movimientos")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self.add_button = QPushButton("Nuevo Movimiento")
        self.add_button.clicked.connect(self.on_add_movement)
        header_layout.addWidget(self.add_button)

        layout.addLayout(header_layout)

        # Filters
        filter_layout = QHBoxLayout()

        # Branch filter
        self.branch_combo = QComboBox()
        self.branch_combo.addItem("Todas las sucursales", None)
        branches = self.branch_service.get_all_active_branches()
        for b in branches:
            self.branch_combo.addItem(b['name'], b['id'])
        self.branch_combo.currentIndexChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(QLabel("Sucursal:"))
        filter_layout.addWidget(self.branch_combo)

        # Type filter
        self.type_combo = QComboBox()
        self.type_combo.addItem("Todos los tipos", None)
        for type_key, type_label in MOVEMENT_TYPES.items():
            self.type_combo.addItem(type_label, type_key)
        self.type_combo.currentIndexChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(QLabel("Tipo:"))
        filter_layout.addWidget(self.type_combo)

        # State filter
        self.state_combo = QComboBox()
        self.state_combo.addItem("Todos los estados", None)
        for state_key, state_label in MOVEMENT_STATES.items():
            self.state_combo.addItem(state_label, state_key)
        self.state_combo.currentIndexChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(QLabel("Estado:"))
        filter_layout.addWidget(self.state_combo)

        filter_layout.addStretch()

        layout.addLayout(filter_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "ID", "Tipo", "Producto", "Sucursal", "Cantidad",
            "Estado", "Usuario", "Fecha", "Acciones"
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setColumnHidden(0, True)

        layout.addWidget(self.table)

        self.setLayout(layout)

    def load_movements(self):
        """Load movements into table."""
        result = self.service.list_movements(
            page=1,
            page_size=100,
            branch_id=self.current_branch_id,
            movement_type=self.current_type,
            state=self.current_state
        )

        movements = result["movements"]
        self.table.setRowCount(len(movements))

        for row, movement in enumerate(movements):
            # ID (hidden)
            self.table.setItem(row, 0, QTableWidgetItem(str(movement["id"])))

            # Type
            type_label = MOVEMENT_TYPES.get(movement["movement_type"], movement["movement_type"])
            self.table.setItem(row, 1, QTableWidgetItem(type_label))

            # Product
            product_name = movement.get("product", {}).get("name", "N/A")
            self.table.setItem(row, 2, QTableWidgetItem(product_name))

            # Branch
            branch_name = movement.get("branch", {}).get("name", "N/A")
            self.table.setItem(row, 3, QTableWidgetItem(branch_name))

            # Quantity
            self.table.setItem(row, 4, QTableWidgetItem(str(movement["quantity"])))

            # State
            state_label = MOVEMENT_STATES.get(movement["state"], movement["state"])
            state_item = QTableWidgetItem(state_label)
            if movement["state"] == "validado":
                state_item.setBackground(Qt.GlobalColor.green)
            elif movement["state"] == "rechazado":
                state_item.setBackground(Qt.GlobalColor.red)
            else:
                state_item.setBackground(Qt.GlobalColor.yellow)
            self.table.setItem(row, 5, state_item)

            # User
            user_name = movement.get("user", {}).get("name", "N/A") if movement.get("user") else "N/A"
            self.table.setItem(row, 6, QTableWidgetItem(user_name))

            # Date
            date_str = movement.get("created_at", "")
            if date_str:
                date_str = date_str[:19]  # Remove timezone
            self.table.setItem(row, 7, QTableWidgetItem(date_str))

            # Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(5, 5, 5, 5)

            if movement["state"] == "pendiente":
                validate_btn = QPushButton("Validar")
                validate_btn.setStyleSheet("background-color: #4CAF50; color: white;")
                validate_btn.clicked.connect(
                    lambda checked, mid=movement["id"]: self.on_validate_movement(mid)
                )
                actions_layout.addWidget(validate_btn)

                reject_btn = QPushButton("Rechazar")
                reject_btn.setStyleSheet("background-color: #f44336; color: white;")
                reject_btn.clicked.connect(
                    lambda checked, mid=movement["id"]: self.on_reject_movement(mid)
                )
                actions_layout.addWidget(reject_btn)

                delete_btn = QPushButton("Eliminar")
                delete_btn.clicked.connect(
                    lambda checked, mid=movement["id"]: self.on_delete_movement(mid)
                )
                actions_layout.addWidget(delete_btn)
            else:
                view_btn = QPushButton("Ver Detalles")
                view_btn.clicked.connect(
                    lambda checked, mid=movement["id"]: self.on_view_movement(mid)
                )
                actions_layout.addWidget(view_btn)

            self.table.setCellWidget(row, 8, actions_widget)

        self.table.resizeColumnsToContents()

    def on_filter_changed(self):
        """Handle filter change."""
        self.current_branch_id = self.branch_combo.currentData()
        self.current_type = self.type_combo.currentData()
        self.current_state = self.state_combo.currentData()
        self.load_movements()

    def on_add_movement(self):
        """Handle add movement."""
        dialog = MovementDialog(self.db, self.current_user_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                data = dialog.get_data()
                if not data["movement_type"] or not data["product_id"] or not data["branch_id"]:
                    QMessageBox.warning(self, "Error", "Complete los campos requeridos")
                    return

                self.service.create_movement(data)
                QMessageBox.information(self, "Exito", "Movimiento creado exitosamente")
                self.load_movements()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al crear movimiento: {str(e)}")

    def on_validate_movement(self, movement_id: int):
        """Handle validate movement."""
        reply = QMessageBox.question(
            self,
            "Confirmar",
            "¿Validar este movimiento?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.service.validate_movement(movement_id, self.current_user_id)
                QMessageBox.information(self, "Exito", "Movimiento validado exitosamente")
                self.load_movements()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al validar movimiento: {str(e)}")

    def on_reject_movement(self, movement_id: int):
        """Handle reject movement."""
        reason, ok = QInputDialog.getText(self, "Razon de Rechazo", "Ingrese la razon del rechazo:")
        if ok:
            try:
                self.service.reject_movement(movement_id, self.current_user_id, reason)
                QMessageBox.information(self, "Exito", "Movimiento rechazado")
                self.load_movements()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al rechazar movimiento: {str(e)}")

    def on_delete_movement(self, movement_id: int):
        """Handle delete movement."""
        reply = QMessageBox.question(
            self,
            "Confirmar",
            "¿Eliminar este movimiento?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.service.delete_movement(movement_id)
                QMessageBox.information(self, "Exito", "Movimiento eliminado")
                self.load_movements()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al eliminar movimiento: {str(e)}")

    def on_view_movement(self, movement_id: int):
        """Handle view movement details."""
        movement = self.service.get_movement_details(movement_id)
        if movement:
            details = f"""
ID: {movement['id']}
Tipo: {MOVEMENT_TYPES.get(movement['movement_type'], movement['movement_type'])}
Producto: {movement.get('product', {}).get('name', 'N/A')}
Sucursal: {movement.get('branch', {}).get('name', 'N/A')}
Cantidad: {movement['quantity']}
Estado: {MOVEMENT_STATES.get(movement['state'], movement['state'])}
Usuario: {movement.get('user', {}).get('name', 'N/A') if movement.get('user') else 'N/A'}
Razon: {movement.get('reason', 'N/A')}
Notas: {movement.get('notes', 'N/A')}
Fecha: {movement.get('created_at', 'N/A')}
"""
            QMessageBox.information(self, "Detalles del Movimiento", details)
