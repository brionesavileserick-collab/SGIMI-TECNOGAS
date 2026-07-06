"""
SGIMI TECNOGAS - Sistema de Gestion de Inventario Multi-Sucursal
Main application entry point with PyQt6 GUI.

Event-Driven Architecture Implementation
"""

import sys
import logging
from typing import Optional
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QMessageBox, QStackedWidget,
    QMenuBar, QMenu, QToolBar, QStatusBar, QDialog, QFormLayout,
    QTabWidget, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QIcon, QFont

from config import setup_logging, APP_TITLE, APP_VERSION
from core.database import init_db, SessionLocal
from core.event_bus import event_bus

# Module handlers
from modules.inventory.handlers import setup_inventory_handlers
from modules.movements.handlers import setup_movement_handlers
from modules.alerts.handlers import setup_alert_handlers
from modules.history.handlers import setup_history_handlers
from modules.dashboard.handlers import setup_dashboard_handlers

# Services
from modules.user import User
from modules.branches.service import BranchService
from modules.products.service import ProductService
from modules.alerts.service import AlertService

# Views
from modules.dashboard.routes import DashboardWidget
from modules.products.routes import ProductListView
from modules.branches.routes import BranchListView
from modules.inventory.routes import InventoryListView
from modules.movements.routes import MovementListView

logger = logging.getLogger(__name__)

LOGOUT_TEXT = "Cerrar Sesion"


class LoginDialog(QDialog):
    """Login dialog for user authentication."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.authenticated_user = None
        self.setup_ui()

    def setup_ui(self):
        """Setup login dialog UI."""
        self.setWindowTitle("SGIMI TECNOGAS - Iniciar Sesion")
        self.setFixedWidth(400)
        self.setFixedHeight(300)

        layout = QVBoxLayout()

        # Logo/Title
        title = QLabel("SGIMI TECNOGAS")
        title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Sistema de Gestion de Inventario")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(20)

        # Form
        form_layout = QFormLayout()

        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("correo@tecnogas.com")
        form_layout.addRow("Correo:", self.email_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("contrasena")
        self.password_input.returnPressed.connect(self.attempt_login)
        form_layout.addRow("Contrasena:", self.password_input)

        layout.addLayout(form_layout)

        layout.addSpacing(20)

        # Buttons
        button_layout = QHBoxLayout()

        self.login_button = QPushButton("Iniciar Sesion")
        self.login_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 10px;
                font-size: 14px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.login_button.clicked.connect(self.attempt_login)
        button_layout.addWidget(self.login_button)

        layout.addLayout(button_layout)

        # Demo credentials hint
        hint = QLabel("Demo: admin@tecnogas.com / admin123")
        hint.setStyleSheet("color: gray; font-size: 10px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        self.setLayout(layout)

    def attempt_login(self):
        """Attempt to authenticate user."""
        email = self.email_input.text().strip()
        password = self.password_input.text()

        if not email or not password:
            QMessageBox.warning(self, "Error", "Ingrese correo y contrasena")
            return

        # Query user
        user = self.db.query(User).filter(User.email == email).first()

        if user and user.verify_password(password):
            if not user.is_active:
                QMessageBox.warning(self, "Error", "Usuario inactivo")
                return

            self.authenticated_user = user
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Credenciales incorrectas")


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, user, db):
        super().__init__()
        self.user = user
        self.db = db
        self.handlers = []
        self.setup_ui()
        self.setup_handlers()
        self.setWindowTitle(f"{APP_TITLE} - v{APP_VERSION}")

    def setup_ui(self):
        """Setup main window UI."""
        self.setMinimumSize(1200, 800)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Sidebar navigation
        sidebar = self.create_sidebar()
        main_layout.addWidget(sidebar)

        # Main content area
        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack, 1)

        # Create menu bar
        self.create_menubar()

        # Create toolbar
        self.create_toolbar()

        # Create status bar
        self.statusBar().showMessage(f"Usuario: {self.user.name}")

        # Load views
        self.load_views()

    def create_sidebar(self):
        """Create sidebar navigation."""
        sidebar = QFrame()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet("""
            QFrame {
                background-color: #263238;
            }
            QPushButton {
                background-color: transparent;
                color: white;
                text-align: left;
                padding: 15px;
                border: none;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #37474F;
            }
            QPushButton:checked {
                background-color: #2196F3;
            }
            QLabel {
                color: white;
                padding: 10px;
            }
        """)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Logo/Title
        title = QLabel("SGIMI TECNOGAS")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        layout.addSpacing(10)

        # Navigation buttons
        self.nav_buttons = []
        nav_items = [
            ("Dashboard", "📊"),
            ("Productos", "📦"),
            ("Sucursales", "🏢"),
            ("Inventario", "📋"),
            ("Movimientos", "🔄"),
        ]

        for text, icon in nav_items:
            btn = QPushButton(f"{icon}  {text}")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, t=text: self.switch_view(t))
            self.nav_buttons.append(btn)
            layout.addWidget(btn)

        # Set dashboard as default
        self.nav_buttons[0].setChecked(True)

        layout.addStretch()

        # User info
        user_label = QLabel(f"👤 {self.user.name}")
        user_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(user_label)

        # Logout button
        logout_btn = QPushButton(LOGOUT_TEXT)
        logout_btn.clicked.connect(self.logout)
        layout.addWidget(logout_btn)

        return sidebar

    def create_menubar(self):
        """Create menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("Archivo")

        logout_action = QAction(LOGOUT_TEXT, self)
        logout_action.triggered.connect(self.logout)
        file_menu.addAction(logout_action)

        exit_action = QAction("Salir", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menubar.addMenu("Vista")

        refresh_action = QAction("Actualizar", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.refresh_current_view)
        view_menu.addAction(refresh_action)

        # Help menu
        help_menu = menubar.addMenu("Ayuda")

        about_action = QAction("Acerca de", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_toolbar(self):
        """Create toolbar."""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Alerts indicator
        self.alerts_label = QLabel("Alertas: 0")
        self.alerts_label.setStyleSheet("padding: 5px;")
        toolbar.addWidget(self.alerts_label)

        toolbar.addSeparator()

        # Refresh button
        refresh_action = QAction("Actualizar", self)
        refresh_action.triggered.connect(self.refresh_current_view)
        toolbar.addAction(refresh_action)

        # Update alerts count
        self.update_alerts_count()

    def load_views(self):
        """Load all module views."""
        # Dashboard
        self.dashboard_view = DashboardWidget(self.db)
        self.content_stack.addWidget(self.dashboard_view)

        # Products
        self.products_view = ProductListView(self.db)
        self.content_stack.addWidget(self.products_view)

        # Branches
        self.branches_view = BranchListView(self.db)
        self.content_stack.addWidget(self.branches_view)

        # Inventory
        self.inventory_view = InventoryListView(self.db)
        self.content_stack.addWidget(self.inventory_view)

        # Movements
        self.movements_view = MovementListView(self.db, self.user.id)
        self.content_stack.addWidget(self.movements_view)

    def setup_handlers(self):
        """Setup all event handlers."""
        # Initialize handlers from each module
        self.handlers.append(setup_inventory_handlers(self.db))
        self.handlers.append(setup_movement_handlers(self.db))
        self.handlers.append(setup_alert_handlers(self.db))
        self.handlers.append(setup_history_handlers(self.db))
        self.handlers.append(setup_dashboard_handlers(self.db))

        logger.info("All event handlers registered")

    def switch_view(self, view_name):
        """Switch to specified view."""
        view_index = {
            "Dashboard": 0,
            "Productos": 1,
            "Sucursales": 2,
            "Inventario": 3,
            "Movimientos": 4,
        }

        if view_name in view_index:
            # Update nav buttons
            for i, btn in enumerate(self.nav_buttons):
                btn.setChecked(i == view_index[view_name])

            self.content_stack.setCurrentIndex(view_index[view_name])

    def refresh_current_view(self):
        """Refresh current view."""
        current_widget = self.content_stack.currentWidget()
        if hasattr(current_widget, 'load_data'):
            current_widget.load_data()
        elif hasattr(current_widget, 'load_products'):
            current_widget.load_products()
        elif hasattr(current_widget, 'load_branches'):
            current_widget.load_branches()
        elif hasattr(current_widget, 'load_inventory'):
            current_widget.load_inventory()
        elif hasattr(current_widget, 'load_movements'):
            current_widget.load_movements()

        self.update_alerts_count()
        self.statusBar().showMessage("Vista actualizada", 2000)

    def update_alerts_count(self):
        """Update alerts count in toolbar."""
        try:
            service = AlertService(self.db)
            count = service.get_unread_count()
            self.alerts_label.setText(f"Alertas: {count}")

            if count > 0:
                self.alerts_label.setStyleSheet("padding: 5px; color: red; font-weight: bold;")
            else:
                self.alerts_label.setStyleSheet("padding: 5px;")
        except Exception as e:
            logger.exception(f"Error updating alerts count: {e}")

    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "Acerca de SGIMI TECNOGAS",
            f"""
            <h2>SGIMI TECNOGAS</h2>
            <p>Sistema de Gestion de Inventario Multi-Sucursal</p>
            <p>Version: {APP_VERSION}</p>
            <br>
            <p>Arquitectura basada en eventos (Event-Driven)</p>
            <p>Modulos: Productos, Sucursales, Inventario, Movimientos, Dashboard, Alertas, Historial, Reportes</p>
            """
        )

    def logout(self):
        """Logout user and return to login screen."""
        reply = QMessageBox.question(
            self,
            LOGOUT_TEXT,
            "¿Esta seguro de cerrar sesion?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.close()


def run_application():
    """Run the main application."""
    # Setup logging
    setup_logging()
    logger.info("Starting SGIMI TECNOGAS...")

    # Create Qt application
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Set application font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Initialize database
    init_db()
    logger.info("Database initialized")

    # Seed database if empty
    from database.seed import seed_database
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            logger.info("Seeding database...")
            seed_database(db, force=False)
    finally:
        db.close()

    # Create database session for login
    db = SessionLocal()

    try:
        # Show login dialog
        login_dialog = LoginDialog(db)
        if login_dialog.exec() != QDialog.DialogCode.Accepted:
            logger.info("Login cancelled, exiting...")
            sys.exit(0)

        user = login_dialog.authenticated_user
        logger.info(f"User authenticated: {user.email}")

        # Close login session
        db.close()

        # Create new session for main window
        db = SessionLocal()

        # Create and show main window
        window = MainWindow(user, db)
        window.show()

        # Run event loop
        logger.info("Application running...")
        exit_code = app.exec()

        # Cleanup
        window.dashboard_view.cleanup() if hasattr(window, 'dashboard_view') else None
        db.close()
        logger.info("Application closed")

        sys.exit(exit_code)

    except Exception as e:
        logger.exception(f"Application error: {e}")
        QMessageBox.critical(None, "Error", f"Error de aplicacion: {str(e)}")
        db.close()
        sys.exit(1)


if __name__ == "__main__":
    run_application()
