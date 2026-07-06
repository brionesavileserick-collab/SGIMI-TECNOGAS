"""
History GUI routes/controllers for PyQt6 interface.
"""

from sqlalchemy.orm import Session
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QLabel, QLineEdit
)
from modules.history.service import HistoryService
import logging

logger = logging.getLogger(__name__)


class HistoryListView(QWidget):
    """History list view widget."""

    def __init__(self, db: Session, parent=None):
        super().__init__(parent)
        self.db = db
        self.service = HistoryService(db)
        self.search_term = None
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        """Setup UI components."""
        layout = QVBoxLayout()

        header_layout = QHBoxLayout()
        title = QLabel("Historial")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar en acciones...")
        self.search_input.setMaximumWidth(300)
        self.search_input.textChanged.connect(self.on_search)
        header_layout.addWidget(self.search_input)

        refresh_button = QPushButton("Actualizar")
        refresh_button.clicked.connect(self.load_data)
        header_layout.addWidget(refresh_button)
        layout.addLayout(header_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ID", "Evento", "Entidad", "Entidad ID", "Usuario", "Accion", "Fecha"
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setColumnHidden(0, True)
        layout.addWidget(self.table)

        self.setLayout(layout)

    def load_data(self):
        """Load history into table."""
        if self.search_term:
            entries = self.service.search_history(self.search_term, limit=500)
        else:
            result = self.service.list_history(limit=500)
            entries = result["entries"]

        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self.table.setItem(row, 0, QTableWidgetItem(str(entry["id"])))
            self.table.setItem(row, 1, QTableWidgetItem(entry["event_type"]))
            self.table.setItem(row, 2, QTableWidgetItem(entry["entity_type"] or ""))
            self.table.setItem(row, 3, QTableWidgetItem(str(entry["entity_id"] or "")))
            self.table.setItem(row, 4, QTableWidgetItem(str(entry["user_id"] or "")))
            self.table.setItem(row, 5, QTableWidgetItem(entry["action"]))
            self.table.setItem(row, 6, QTableWidgetItem((entry["created_at"] or "")[:19]))

        self.table.resizeColumnsToContents()

    def on_search(self, text: str):
        """Handle search."""
        self.search_term = text.strip() or None
        self.load_data()
