"""
Dashboard GUI routes/controllers for PyQt6 interface.
"""

from typing import Dict, Any
from sqlalchemy.orm import Session
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QGroupBox, QGridLayout, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer
from modules.dashboard.service import DashboardService
from modules.branches.service import BranchService
from modules.dashboard.handlers import setup_dashboard_handlers
import logging

logger = logging.getLogger(__name__)


class DashboardWidget(QWidget):
    """Dashboard main widget."""

    def __init__(self, db: Session, parent=None):
        super().__init__(parent)
        self.db = db
        self.service = DashboardService(db)
        self.branch_service = BranchService(db)
        self.handlers = None
        self.setup_ui()
        # Setup event handlers for reactive updates
        self.handlers = setup_dashboard_handlers(self.db)
        self.handlers.set_refresh_callback(self.load_data)
        self.load_data()
        # Auto-refresh every 30 seconds as fallback
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.load_data)
        self.refresh_timer.start(30000)

    def setup_ui(self):
        """Setup UI components."""
        main_layout = QVBoxLayout()

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Dashboard - SGIMI TECNOGAS")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self.refresh_button = QPushButton("Actualizar")
        self.refresh_button.clicked.connect(self.load_data)
        header_layout.addWidget(self.refresh_button)

        main_layout.addLayout(header_layout)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # KPI Section
        kpi_group = QGroupBox("Indicadores Clave de Rendimiento (KPIs)")
        kpi_layout = QGridLayout()

        # KPI Cards
        self.eri_card = self.create_kpi_card("ERI", "0%", "Exactitud de Registros de Inventario")
        self.eru_card = self.create_kpi_card("ERU", "0%", "Exactitud de Registros de Ubicacion")
        self.products_card = self.create_kpi_card("Productos", "0", "Total de productos")
        self.branches_card = self.create_kpi_card("Sucursales", "0", "Total de sucursales")

        kpi_layout.addWidget(self.eri_card, 0, 0)
        kpi_layout.addWidget(self.eru_card, 0, 1)
        kpi_layout.addWidget(self.products_card, 0, 2)
        kpi_layout.addWidget(self.branches_card, 0, 3)

        kpi_group.setLayout(kpi_layout)
        scroll_layout.addWidget(kpi_group)

        # Stock Summary
        stock_group = QGroupBox("Resumen de Stock")
        stock_layout = QGridLayout()

        self.physical_stock_card = self.create_metric_card("Stock Fisico Total", "0")
        self.digital_stock_card = self.create_metric_card("Stock Digital Total", "0")
        self.discrepancy_card = self.create_metric_card("Discrepancias", "0")
        self.low_stock_card = self.create_metric_card("Stock Bajo", "0")

        stock_layout.addWidget(self.physical_stock_card, 0, 0)
        stock_layout.addWidget(self.digital_stock_card, 0, 1)
        stock_layout.addWidget(self.discrepancy_card, 0, 2)
        stock_layout.addWidget(self.low_stock_card, 0, 3)

        stock_group.setLayout(stock_layout)
        scroll_layout.addWidget(stock_group)

        # Movements Section
        movements_group = QGroupBox("Movimientos")
        movements_layout = QGridLayout()

        self.pending_card = self.create_metric_card("Pendientes", "0")
        self.entradas_card = self.create_metric_card("Entradas", "0")
        self.salidas_card = self.create_metric_card("Salidas", "0")
        self.ajustes_card = self.create_metric_card("Ajustes", "0")

        movements_layout.addWidget(self.pending_card, 0, 0)
        movements_layout.addWidget(self.entradas_card, 0, 1)
        movements_layout.addWidget(self.salidas_card, 0, 2)
        movements_layout.addWidget(self.ajustes_card, 0, 3)

        movements_group.setLayout(movements_layout)
        scroll_layout.addWidget(movements_group)

        # Alerts Section
        alerts_group = QGroupBox("Alertas Recientes")
        alerts_layout = QVBoxLayout()

        self.alerts_label = QLabel("Cargando alertas...")
        self.alerts_label.setWordWrap(True)
        alerts_layout.addWidget(self.alerts_label)

        alerts_group.setLayout(alerts_layout)
        scroll_layout.addWidget(alerts_group)

        # Recent Movements Section
        recent_group = QGroupBox("Movimientos Recientes")
        recent_layout = QVBoxLayout()

        self.recent_label = QLabel("Cargando movimientos...")
        self.recent_label.setWordWrap(True)
        recent_layout.addWidget(self.recent_label)

        recent_group.setLayout(recent_layout)
        scroll_layout.addWidget(recent_group)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        self.setLayout(main_layout)

    def create_kpi_card(self, title: str, value: str, description: str) -> QFrame:
        """Create a KPI card widget."""
        card = QFrame()
        card.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        card.setStyleSheet("""
            QFrame {
                background-color: #2196F3;
                border-radius: 10px;
                padding: 10px;
            }
            QLabel {
                color: white;
            }
        """)

        layout = QVBoxLayout(card)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        value_label = QLabel(value)
        value_label.setStyleSheet("font-size: 32px; font-weight: bold;")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        desc_label = QLabel(description)
        desc_label.setStyleSheet("font-size: 11px;")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(desc_label)

        # Store reference to value label for updating
        card.value_label = value_label

        return card

    def create_metric_card(self, title: str, value: str) -> QFrame:
        """Create a metric card widget."""
        card = QFrame()
        card.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        card.setStyleSheet("""
            QFrame {
                background-color: #607D8B;
                border-radius: 8px;
                padding: 8px;
            }
            QLabel {
                color: white;
            }
        """)

        layout = QVBoxLayout(card)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 12px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        value_label = QLabel(value)
        value_label.setStyleSheet("font-size: 24px; font-weight: bold;")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title_label)
        layout.addWidget(value_label)

        card.value_label = value_label

        return card

    def load_data(self):
        """Load dashboard data."""
        try:
            metrics = self.service.get_dashboard_metrics()

            # Update KPIs
            self.eri_card.value_label.setText(f"{metrics['kpi_eri']}%")
            self.eru_card.value_label.setText(f"{metrics['kpi_eru']}%")
            self.products_card.value_label.setText(str(metrics['total_products']))
            self.branches_card.value_label.setText(str(metrics['total_branches']))

            # Update metrics
            self.physical_stock_card.value_label.setText(str(metrics['total_physical_stock']))
            self.digital_stock_card.value_label.setText(str(metrics['total_digital_stock']))
            self.discrepancy_card.value_label.setText(str(metrics['discrepancy_count']))
            self.low_stock_card.value_label.setText(str(metrics['low_stock_count']))

            # Update pending
            self.pending_card.value_label.setText(str(metrics['pending_movements']))

            # Update movement stats
            stats = metrics.get('movement_stats', {})
            self.entradas_card.value_label.setText(str(stats.get('entrada', {}).get('count', 0)))
            self.salidas_card.value_label.setText(str(stats.get('salida', {}).get('count', 0)))
            self.ajustes_card.value_label.setText(str(stats.get('ajuste', {}).get('count', 0)))

            # Update alerts
            self.load_alerts()

            # Update recent movements
            self.load_recent_movements()

        except Exception as e:
            logger.error(f"Error loading dashboard data: {e}")

    def load_alerts(self):
        """Load alerts data."""
        try:
            low_stock = self.service.get_low_stock_alerts()
            discrepancies = self.service.get_discrepancy_alerts()

            alert_text = ""

            if low_stock:
                alert_text += "<b>Stock Bajo:</b><br>"
                for item in low_stock[:5]:
                    alert_text += f"• {item['product']} ({item['branch']}): {item['current_stock']} unidades<br>"

            if discrepancies:
                alert_text += "<br><b>Discrepancias:</b><br>"
                for item in discrepancies[:5]:
                    alert_text += f"• {item['product']} ({item['branch']}): Fis={item['physical_stock']}, Dig={item['digital_stock']}, Dif={item['difference']}<br>"

            if not alert_text:
                alert_text = "No hay alertas activas."

            self.alerts_label.setText(alert_text)

        except Exception as e:
            logger.error(f"Error loading alerts: {e}")

    def load_recent_movements(self):
        """Load recent movements."""
        try:
            movements = self.service.get_recent_movements(limit=10)

            if not movements:
                self.recent_label.setText("No hay movimientos recientes.")
                return

            text = "<table style='width:100%'>"
            text += "<tr><th>ID</th><th>Tipo</th><th>Producto</th><th>Cantidad</th><th>Estado</th><th>Fecha</th></tr>"

            for m in movements:
                text += f"<tr>"
                text += f"<td>{m['id']}</td>"
                text += f"<td>{m['type']}</td>"
                text += f"<td>{m['product']}</td>"
                text += f"<td>{m['quantity']}</td>"
                text += f"<td>{m['state']}</td>"
                text += f"<td>{m['created_at'][:16] if m['created_at'] else 'N/A'}</td>"
                text += f"</tr>"

            text += "</table>"
            self.recent_label.setText(text)

        except Exception as e:
            logger.error(f"Error loading recent movements: {e}")

    def cleanup(self):
        """Cleanup before destroying widget."""
        self.refresh_timer.stop()
        if self.handlers:
            self.handlers.unregister_handlers()
