"""
User GUI routes/controllers for PyQt6 interface.
"""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel, QLineEdit,
    QMessageBox, QDialog, QFormLayout, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from modules.user.service import UserService
import logging

logger = logging.getLogger(__name__)


class UserDialog(QDialog):
    """Dialog for creating/editing users."""

    def __init__(self, parent=None, user_data: dict = None):
        super().__init__(parent)
        self.user_data = user_data or {}
        self.setup_ui()

    def setup_ui(self):
        """Setup dialog UI."""
        self.setWindowTitle("Usuario" if not self.user_data else "Editar Usuario")
        self.setMinimumWidth(400)

        layout = QFormLayout()

        # Name
        self.name_input = QLineEdit()
        self.name_input.setText(self.user_data.get("name", ""))
        layout.addRow("Nombre*:", self.name_input)

        # Email
        self.email_input = QLineEdit()
        self.email_input.setText(self.user_data.get("email", ""))
        layout.addRow("Correo*:", self.email_input)

        # Password (only for new users)
        if not self.user_data:
            self.password_input = QLineEdit()
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            layout.addRow("Contrasena*:", self.password_input)

            self.confirm_password_input = QLineEdit()
            self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
            layout.addRow("Confirmar*:", self.confirm_password_input)
        else:
            self.password_input = QLineEdit()
            self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.password_input.setPlaceholderText("Dejar vacio para no cambiar")
            layout.addRow("Nueva Contrasena:", self.password_input)

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
        data = {
            "name": self.name_input.text().strip(),
            "email": self.email_input.text().strip()
        }
        
        if not self.user_data:
            # New user - password is required
            data["password"] = self.password_input.text()
            data["confirm_password"] = self.confirm_password_input.text()
        else:
            # Edit user - password is optional
            password = self.password_input.text()
            if password:
                data["password"] = password
        
        return data


class UserListView(QWidget):
    """User list view widget."""

    user_selected = pyqtSignal(int)  # Emits user ID

    def __init__(self, db: Session, parent=None):
        super().__init__(parent)
        self.db = db
        self.service = UserService(db)
        self.setup_ui()
        self.load_users()

    def setup_ui(self):
        """Setup UI components."""
        layout = QVBoxLayout()

        # Header
        header_layout = QHBoxLayout()

        title = QLabel("Gestion de Usuarios")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # Search
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar usuarios...")
        self.search_input.setMaximumWidth(300)
        self.search_input.textChanged.connect(self.on_search)
        header_layout.addWidget(self.search_input)

        # Add button
        self.add_button = QPushButton("Nuevo Usuario")
        self.add_button.clicked.connect(self.on_add_user)
        header_layout.addWidget(self.add_button)

        layout.addLayout(header_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "ID", "Nombre", "Correo", "Estado", "Acciones"
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setColumnHidden(0, True)  # Hide ID column

        layout.addWidget(self.table)

        self.setLayout(layout)

    def load_users(self, search: str = None):
        """Load users into table."""
        result = self.service.list_users(page=1, page_size=100, search=search)
        users = result["users"]

        self.table.setRowCount(len(users))

        for row, user in enumerate(users):
            # ID (hidden)
            self.table.setItem(row, 0, QTableWidgetItem(str(user["id"])))

            # Name
            self.table.setItem(row, 1, QTableWidgetItem(user["name"]))

            # Email
            self.table.setItem(row, 2, QTableWidgetItem(user["email"]))

            # State
            status = "Activo" if user["is_active"] else "Inactivo"
            self.table.setItem(row, 3, QTableWidgetItem(status))

            # Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(5, 5, 5, 5)

            edit_btn = QPushButton("Editar")
            edit_btn.clicked.connect(lambda checked, uid=user["id"]: self.on_edit_user(uid))
            actions_layout.addWidget(edit_btn)

            delete_btn = QPushButton("Eliminar")
            delete_btn.clicked.connect(lambda checked, uid=user["id"]: self.on_delete_user(uid))
            actions_layout.addWidget(delete_btn)

            self.table.setCellWidget(row, 4, actions_widget)

        self.table.resizeColumnsToContents()

    def on_search(self, text: str):
        """Handle search."""
        self.load_users(search=text if text else None)

    def on_add_user(self):
        """Handle add user."""
        dialog = UserDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                data = dialog.get_data()
                if not data["name"] or not data["email"]:
                    QMessageBox.warning(self, "Error", "Nombre y correo son requeridos")
                    return

                if not data["password"] or not data["confirm_password"]:
                    QMessageBox.warning(self, "Error", "Contrasena es requerida")
                    return

                if data["password"] != data["confirm_password"]:
                    QMessageBox.warning(self, "Error", "Las contrasenas no coinciden")
                    return

                password = data.pop("password", None)
                data.pop("confirm_password", None)
                
                self.service.create_user(data, password)
                QMessageBox.information(self, "Exito", "Usuario creado exitosamente")
                self.load_users()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al crear usuario: {str(e)}")

    def on_edit_user(self, user_id: int):
        """Handle edit user."""
        user = self.service.get_user(user_id)
        if not user:
            return

        dialog = UserDialog(self, user)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                data = dialog.get_data()
                if not data["name"] or not data["email"]:
                    QMessageBox.warning(self, "Error", "Nombre y correo son requeridos")
                    return

                password = data.pop("password", None)
                
                self.service.update_user(user_id, data, password)
                QMessageBox.information(self, "Exito", "Usuario actualizado exitosamente")
                self.load_users(self.search_input.text() or None)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al actualizar usuario: {str(e)}")

    def on_delete_user(self, user_id: int):
        """Handle delete user."""
        reply = QMessageBox.question(
            self,
            "Confirmar",
            "¿Esta seguro de eliminar este usuario?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.service.delete_user(user_id)
                QMessageBox.information(self, "Exito", "Usuario eliminado exitosamente")
                self.load_users(self.search_input.text() or None)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al eliminar usuario: {str(e)}")
