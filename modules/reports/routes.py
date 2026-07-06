"""
Reports GUI routes/controllers for PyQt6 interface.
"""

import json
from sqlalchemy.orm import Session
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QComboBox, QTextEdit
)
from modules.reports.service import ReportsService
from modules.branches.service import BranchService
import logging

logger = logging.getLogger(__name__)


class ReportsView(QWidget):
    """Reports view widget."""

    def __init__(self, db: Session, parent=None):
        super().__init__(parent)
        self.db = db
        self.service = ReportsService(db)
        self.branch_service = BranchService(db)
        self.setup_ui()

    def setup_ui(self):
        """Setup UI components."""
        layout = QVBoxLayout()

        header_layout = QHBoxLayout()
        title = QLabel("Reportes")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.report_combo = QComboBox()
        self.report_combo.addItem("Inventario", "inventory")
        self.report_combo.addItem("Movimientos", "movements")
        self.report_combo.addItem("Discrepancias", "discrepancies")
        self.report_combo.addItem("KPIs", "kpis")
        header_layout.addWidget(QLabel("Reporte:"))
        header_layout.addWidget(self.report_combo)

        self.branch_combo = QComboBox()
        self.branch_combo.addItem("Todas las sucursales", None)
        for branch in self.branch_service.get_all_active_branches():
            self.branch_combo.addItem(branch["name"], branch["id"])
        header_layout.addWidget(QLabel("Sucursal:"))
        header_layout.addWidget(self.branch_combo)

        generate_button = QPushButton("Generar")
        generate_button.clicked.connect(self.load_data)
        header_layout.addWidget(generate_button)
        layout.addLayout(header_layout)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)

        self.setLayout(layout)

    def load_data(self):
        """Generate selected report."""
        self.refresh_branches()
        report_type = self.report_combo.currentData()
        branch_id = self.branch_combo.currentData()

        if report_type == "inventory":
            report = self.service.generate_inventory_report(branch_id)
        elif report_type == "movements":
            report = self.service.generate_movement_report(branch_id=branch_id)
        elif report_type == "discrepancies":
            report = self.service.generate_discrepancy_report(branch_id)
        else:
            report = self.service.generate_kpi_report(branch_id)

        self.output.setPlainText(json.dumps(report, indent=2, ensure_ascii=False))

    def refresh_branches(self):
        """Refresh branch filter while preserving current selection."""
        selected_branch_id = self.branch_combo.currentData()
        self.branch_combo.blockSignals(True)
        self.branch_combo.clear()
        self.branch_combo.addItem("Todas las sucursales", None)
        selected_index = 0
        for index, branch in enumerate(self.branch_service.get_all_active_branches(), start=1):
            self.branch_combo.addItem(branch["name"], branch["id"])
            if branch["id"] == selected_branch_id:
                selected_index = index
        self.branch_combo.setCurrentIndex(selected_index)
        self.branch_combo.blockSignals(False)
