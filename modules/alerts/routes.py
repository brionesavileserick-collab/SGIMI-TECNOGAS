"""
Alerts GUI routes/controllers for PyQt6 interface.
"""

from sqlalchemy.orm import Session
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QLabel, QComboBox, QMessageBox
)
from PyQt6.QtCore import Qt
from modules.alerts.service import AlertService
from config import ALERT_TYPES, ALERT_SEVERITIES
import logging

logger = logging.getLogger(__name__)


class AlertListView(QWidget):
    """Alert list view widget."""

    def __init__(self, db: Session, parent=None):
        super().__init__(parent)
        self.db = db
        self.service = AlertService(db)
        self.current_status = "open"
        self.current_severity = None
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        """Setup UI components."""
        layout = QVBoxLayout()

        header_layout = QHBoxLayout()
        title = QLabel("Alertas")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.status_combo = QComboBox()
        self.status_combo.addItem("Abiertas", "open")
        self.status_combo.addItem("Todas", "all")
        self.status_combo.currentIndexChanged.connect(self.on_filter_changed)
        header_layout.addWidget(QLabel("Estado:"))
        header_layout.addWidget(self.status_combo)

        self.severity_combo = QComboBox()
        self.severity_combo.addItem("Todas", None)
        for key, label in ALERT_SEVERITIES.items():
            self.severity_combo.addItem(label, key)
        self.severity_combo.currentIndexChanged.connect(self.on_filter_changed)
        header_layout.addWidget(QLabel("Severidad:"))
        header_layout.addWidget(self.severity_combo)

        refresh_button = QPushButton("Actualizar")
        refresh_button.clicked.connect(self.load_data)
        header_layout.addWidget(refresh_button)
        layout.addLayout(header_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Tipo", "Severidad", "Titulo", "Mensaje", "Leida", "Resuelta", "Acciones"
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setColumnHidden(0, True)
        layout.addWidget(self.table)

        self.setLayout(layout)

    def load_data(self):
        """Load alerts into table."""
        alerts = self.service.list_alerts(
            limit=500,
            severity=self.current_severity
        )
        if self.current_status == "open":
            alerts = [alert for alert in alerts if not alert["is_resolved"]]

        self.table.setRowCount(len(alerts))
        for row, alert in enumerate(alerts):
            self.table.setItem(row, 0, QTableWidgetItem(str(alert["id"])))
            self.table.setItem(row, 1, QTableWidgetItem(ALERT_TYPES.get(alert["alert_type"], alert["alert_type"])))
            self.table.setItem(row, 2, QTableWidgetItem(ALERT_SEVERITIES.get(alert["severity"], alert["severity"])))
            self.table.setItem(row, 3, QTableWidgetItem(alert["title"]))
            self.table.setItem(row, 4, QTableWidgetItem(alert["message"]))
            self.table.setItem(row, 5, QTableWidgetItem("Si" if alert["is_read"] else "No"))
            self.table.setItem(row, 6, QTableWidgetItem("Si" if alert["is_resolved"] else "No"))

            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(5, 5, 5, 5)

            read_btn = QPushButton("Leida")
            read_btn.setEnabled(not alert["is_read"])
            read_btn.clicked.connect(lambda checked, aid=alert["id"]: self.on_mark_read(aid))
            actions_layout.addWidget(read_btn)

            resolve_btn = QPushButton("Resolver")
            resolve_btn.setEnabled(not alert["is_resolved"])
            resolve_btn.clicked.connect(lambda checked, aid=alert["id"]: self.on_resolve(aid))
            actions_layout.addWidget(resolve_btn)

            self.table.setCellWidget(row, 7, actions_widget)

        self.table.resizeColumnsToContents()

    def on_filter_changed(self):
        """Handle filter change."""
        self.current_status = self.status_combo.currentData()
        self.current_severity = self.severity_combo.currentData()
        self.load_data()

    def on_mark_read(self, alert_id: int):
        """Mark alert as read."""
        if self.service.mark_as_read(alert_id):
            self.load_data()
        else:
            QMessageBox.warning(self, "Error", "No se pudo marcar la alerta como leida")

    def on_resolve(self, alert_id: int):
        """Resolve alert."""
        if self.service.resolve_alert(alert_id):
            self.load_data()
        else:
            QMessageBox.warning(self, "Error", "No se pudo resolver la alerta")
