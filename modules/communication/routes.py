"""PyQt6 communication views."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .service import CommunicationService


class ComposeMessageDialog(QDialog):
    """Simple compose dialog for sending a message."""

    def __init__(self, db, user, parent=None):
        super().__init__(parent)
        self.db = db
        self.user = user
        self.service = CommunicationService(db)
        self.setWindowTitle("Redactar mensaje")
        self.setMinimumWidth(480)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.to_input = QLineEdit()
        self.to_input.setPlaceholderText("IDs de destinatarios separados por coma")
        form.addRow("Para:", self.to_input)
        self.subject_input = QLineEdit()
        form.addRow("Asunto:", self.subject_input)
        self.body_input = QTextEdit()
        self.body_input.setMinimumHeight(160)
        form.addRow("Mensaje:", self.body_input)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._send)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _send(self):
        if not self.subject_input.text().strip() or not self.body_input.toPlainText().strip():
            QMessageBox.warning(self, "Campos requeridos", "Asunto y mensaje son obligatorios")
            return
        recipients = []
        for token in self.to_input.text().split(","):
            token = token.strip()
            if token.isdigit():
                recipients.append(int(token))
        self.service.send_message(
            sender_id=self.user.id,
            subject=self.subject_input.text().strip(),
            body=self.body_input.toPlainText().strip(),
            recipients=recipients,
            priority="normal",
            communication_type="mensaje",
            related_ids={},
        )
        self.accept()


class CommunicationListView(QWidget):
    """Simple communication inbox/sent view."""

    def __init__(self, db, user, parent=None):
        super().__init__(parent)
        self.db = db
        self.user = user
        self.service = CommunicationService(db)
        self._build_ui()
        self.load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel("Comunicaciones")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        self.compose_button = QPushButton("Redactar")
        self.compose_button.clicked.connect(self._open_compose)
        header.addWidget(self.compose_button)
        layout.addLayout(header)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

    def load_data(self):
        inbox = self.service.get_inbox(self.user.id, None, 1, {})
        self.list_widget.clear()
        for item in inbox.get("items", []):
            title = f"{item.get('subject', '')} — {item.get('communication_type', '')}"
            QListWidgetItem(title, self.list_widget)

    def _open_compose(self):
        dialog = ComposeMessageDialog(self.db, self.user, self)
        dialog.exec()
        self.load_data()
