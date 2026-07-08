"""
User GUI routes/controllers for PyQt6 interface.
"""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel, QLineEdit,
    QMessageBox, QDialog, QFormLayout, QTextEdit, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from modules.user.service import UserService
from models.branch import Branch
import logging

logger = logging.getLogger(__name__)


class UserDetailDialog(QDialog):
    """Simple read-only user detail dialog."""

    def __init__(self, parent=None, user_data: dict = None, branch_name: str = "Sin sucursal"):
        super().__init__(parent)
        self.user_data = user_data or {}
        self.branch_name = branch_name
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Detalle de Usuario")
        self.setMinimumWidth(360)
        layout = QFormLayout()

        role_label = {"admin": "Administrador", "gerente": "Gerente", "empleado": "Empleado"}.get(
            self.user_data.get("role", "empleado"), "Empleado"
        )
        layout.addRow("Nombre:", QLabel(self.user_data.get("name", "")))
        layout.addRow("Correo:", QLabel(self.user_data.get("email", "")))
        layout.addRow("Rol:", QLabel(role_label))
        layout.addRow("Sucursal:", QLabel(self.branch_name or "Sin sucursal"))
        layout.addRow("Estado:", QLabel("Activo" if self.user_data.get("is_active", True) else "Inactivo"))

        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(self.accept)
        layout.addRow(close_button)
        self.setLayout(layout)


class UserDialog(QDialog):
    """Dialog for creating/editing users."""

    def __init__(self, parent=None, user_data: dict = None, db=None):
        super().__init__(parent)
        self.user_data = user_data or {}
        self.db = db
        self.setup_ui()

    def setup_ui(self):
        """Setup dialog UI."""
        self.setWindowTitle("Usuario" if not self.user_data else "Editar Usuario")
        self.setMinimumWidth(420)

        layout = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setText(self.user_data.get("name", ""))
        layout.addRow("Nombre*:", self.name_input)

        self.email_input = QLineEdit()
        self.email_input.setText(self.user_data.get("email", ""))
        layout.addRow("Correo*:", self.email_input)

        if not self.user_data:
            self.role_combo = QComboBox()
            self.role_combo.addItems(["Administrador", "Gerente", "Empleado"])
            layout.addRow("Rol*:", self.role_combo)
            self.role_combo.currentIndexChanged.connect(self._refresh_branch_field)
        else:
            current_role = self.user_data.get("role", "empleado")
            self.role_display = QLineEdit()
            self.role_display.setReadOnly(True)
            self.role_display.setText({"admin": "Administrador", "gerente": "Gerente", "empleado": "Empleado"}.get(current_role, "Empleado"))
            layout.addRow("Rol:", self.role_display)
            layout.addRow(QLabel("Para cambiar el rol, elimine el usuario y cree uno nuevo."))

        self.branch_combo = QComboBox()
        self.branch_combo.addItem("Sin sucursal", None)
        if self.db is not None:
            branches = self.db.query(Branch).filter(Branch.is_active == True).order_by(Branch.name).all()
            for branch in branches:
                self.branch_combo.addItem(branch.name, branch.id)
        if self.user_data:
            current_branch_id = self.user_data.get("assigned_branch_id")
            if current_branch_id is not None:
                index = self.branch_combo.findData(current_branch_id)
                if index >= 0:
                    self.branch_combo.setCurrentIndex(index)
        layout.addRow("Sucursal:", self.branch_combo)

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

        self._refresh_branch_field()

        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Guardar")
        self.save_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        layout.addRow(button_layout)

        self.setLayout(layout)

    def _refresh_branch_field(self):
        is_admin = False
        if not self.user_data:
            is_admin = self.role_combo.currentText() == "Administrador"
        else:
            is_admin = self.user_data.get("role") == "admin"
        self.branch_combo.setEnabled(not is_admin)
        self.branch_combo.setVisible(not is_admin)

    def get_data(self) -> dict:
        """Get form data."""
        data = {
            "name": self.name_input.text().strip(),
            "email": self.email_input.text().strip()
        }

        if not self.user_data:
            role_map = {"Administrador": "admin", "Gerente": "gerente", "Empleado": "empleado"}
            data["role"] = role_map.get(self.role_combo.currentText(), "empleado")
            branch_id = self.branch_combo.currentData()
            if self.role_combo.currentText() != "Administrador":
                data["assigned_branch_id"] = branch_id
            data["password"] = self.password_input.text()
            data["confirm_password"] = self.confirm_password_input.text()
        else:
            password = self.password_input.text()
            if password:
                data["password"] = password

        return data


class UserListView(QWidget):
    """User list view widget."""

    user_selected = pyqtSignal(int)  # Emits user ID

    def __init__(self, db: Session, current_user=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.current_user = current_user
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
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ID", "Nombre", "Correo", "Rol", "Sucursal", "Estado", "Acciones"
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

            role_label = {"admin": "Administrador", "gerente": "Gerente", "empleado": "Empleado"}.get(user.get("role"), "Empleado")
            self.table.setItem(row, 3, QTableWidgetItem(role_label))

            branch_name = self._get_branch_name(user.get("assigned_branch_id"))
            self.table.setItem(row, 4, QTableWidgetItem(branch_name))

            status = "Activo" if user["is_active"] else "Inactivo"
            self.table.setItem(row, 5, QTableWidgetItem(status))

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(5, 5, 5, 5)

            detail_btn = QPushButton("Ver Detalle")
            detail_btn.clicked.connect(lambda checked, uid=user["id"]: self.on_view_user(uid))
            actions_layout.addWidget(detail_btn)

            edit_btn = QPushButton("Editar")
            edit_btn.clicked.connect(lambda checked, uid=user["id"]: self.on_edit_user(uid))
            actions_layout.addWidget(edit_btn)

            delete_btn = QPushButton("Eliminar")
            delete_btn.clicked.connect(lambda checked, uid=user["id"]: self.on_delete_user(uid))
            actions_layout.addWidget(delete_btn)

            self.table.setCellWidget(row, 6, actions_widget)

        self.table.resizeColumnsToContents()

    def on_search(self, text: str):
        """Handle search."""
        self.load_users(search=text if text else None)

    def on_add_user(self):
        """Handle add user."""
        dialog = UserDialog(self, db=self.db)
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

                # Ensure role is preserved
                if "role" not in data:
                    data["role"] = "empleado"

                self.service.create_user(data, password, created_by_user=self.current_user)
                QMessageBox.information(self, "Exito", "Usuario creado exitosamente")
                self.load_users()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al crear usuario: {str(e)}")

    def on_edit_user(self, user_id: int):
        """Handle edit user."""
        user = self.service.get_user(user_id)
        if not user:
            return

        dialog = UserDialog(self, user, self.db)
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

    def on_view_user(self, user_id: int):
        """Show a read-only user detail dialog."""
        user = self.service.get_user(user_id)
        if not user:
            return
        branch_name = self._get_branch_name(user.get("assigned_branch_id"))
        dialog = UserDetailDialog(self, user, branch_name)
        dialog.exec()

    def _get_branch_name(self, branch_id: Optional[int]) -> str:
        """Resolve branch name from ID."""
        if not branch_id:
            return "Sin sucursal"
        branch = self.db.query(Branch).filter(Branch.id == branch_id).first()
        return branch.name if branch else "Sin sucursal"

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
