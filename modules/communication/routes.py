"""PyQt6 communication views."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QStringListModel
from PyQt6.QtWidgets import (
    QComboBox,
    QCompleter,
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
    QTabWidget,
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
        self.to_input.setPlaceholderText("Nombres, IDs o sucursales separados por coma")
        self.to_input.textEdited.connect(self._update_recipient_suggestions)
        self._recipient_model = QStringListModel(self)
        self._recipient_completer = QCompleter(self._recipient_model, self)
        self._recipient_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._recipient_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.to_input.setCompleter(self._recipient_completer)
        form.addRow("Para:", self.to_input)
        self.type_combo = QComboBox()
        self.type_combo.addItem("mensaje", "mensaje")
        self.type_combo.addItem("anuncio", "anuncio")
        self.type_combo.addItem("alerta", "alerta")
        self.type_combo.addItem("recordatorio", "recordatorio")
        form.addRow("Tipo:", self.type_combo)
        self.priority_combo = QComboBox()
        self.priority_combo.addItem("baja", "baja")
        self.priority_combo.addItem("normal", "normal")
        self.priority_combo.addItem("alta", "alta")
        self.priority_combo.addItem("urgente", "urgente")
        form.addRow("Prioridad:", self.priority_combo)
        self.template_combo = QComboBox()
        self.template_combo.addItem("Sin plantilla", None)
        self._load_templates()
        form.addRow("Plantilla:", self.template_combo)
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

    def _load_templates(self):
        try:
            for template in self.service.get_common_templates():
                self.template_combo.addItem(template.get("name", "Plantilla"), template.get("id"))
        except Exception:
            pass

    def _update_recipient_suggestions(self, text: str):
        suggestions = self.service.get_recipient_suggestions(text)
        labels = [item.get("label", "") for item in suggestions]
        self._recipient_model.setStringList(labels)

    def _send(self):
        if not self.subject_input.text().strip() or not self.body_input.toPlainText().strip():
            QMessageBox.warning(self, "Campos requeridos", "Asunto y mensaje son obligatorios")
            return
        recipients = []
        for token in self.to_input.text().split(","):
            token = token.strip()
            if token:
                recipients.append(token)
        if not recipients:
            QMessageBox.warning(self, "Destinatario requerido", "Debe indicar al menos un destinatario")
            return

        resolved_recipients = self.service.resolve_recipient_ids(recipients)
        if not resolved_recipients:
            QMessageBox.warning(self, "Destinatario no válido", "No se pudo resolver el destinatario indicado. Prueba con un nombre o una sucursal existente.")
            return

        template_id = self.template_combo.currentData()
        if template_id:
            try:
                template_payload = self.service.use_template(template_id)
                self.subject_input.setText(template_payload.get("subject", self.subject_input.text().strip()))
                self.body_input.setPlainText(template_payload.get("body", self.body_input.toPlainText().strip()))
            except Exception:
                pass
        if self.type_combo.currentData() == "anuncio":
            self.service.send_announcement(
                sender_id=self.user.id,
                subject=self.subject_input.text().strip(),
                body=self.body_input.toPlainText().strip(),
                priority=self.priority_combo.currentData(),
            )
        else:
            self.service.send_message(
                sender_id=self.user.id,
                subject=self.subject_input.text().strip(),
                body=self.body_input.toPlainText().strip(),
                recipients=resolved_recipients,
                priority=self.priority_combo.currentData(),
                communication_type=self.type_combo.currentData(),
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

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar mensajes")
        search_button = QPushButton("Buscar")
        search_button.clicked.connect(self.load_data)
        search_row = QHBoxLayout()
        search_row.addWidget(self.search_input)
        search_row.addWidget(search_button)
        layout.addLayout(search_row)

        self.tabs = QTabWidget()
        self.inbox_list = QListWidget()
        self.inbox_list.itemDoubleClicked.connect(self._open_detail)
        self.sent_list = QListWidget()
        self.sent_list.itemDoubleClicked.connect(self._open_detail)
        self.announcements_list = QListWidget()
        self.announcements_list.itemDoubleClicked.connect(self._open_detail)
        self.tabs.addTab(self.inbox_list, "Entrada")
        self.tabs.addTab(self.sent_list, "Enviados")
        self.tabs.addTab(self.announcements_list, "Anuncios")
        layout.addWidget(self.tabs)

    def load_data(self):
        query = self.search_input.text().strip() if hasattr(self, "search_input") else ""
        inbox = self.service.get_inbox(self.user.id, None, 1, {})
        self._populate_list(self.inbox_list, inbox.get("items", []))

        sent = self.service.get_sent_items(self.user.id, 1, {})
        self._populate_list(self.sent_list, sent.get("items", []))

        announcements = self.service.get_announcements(self.user.id, include_archived=False)
        self._populate_list(self.announcements_list, announcements)

        if query:
            inbox_results = self.service.search_messages(query, self.user.id)
            self._populate_list(self.inbox_list, inbox_results)

    def _populate_list(self, widget: QListWidget, items):
        widget.clear()
        for item in items:
            title = f"{item.get('subject', '')} — {item.get('communication_type', '')}"
            detail = f"Prioridad: {item.get('priority', 'normal')}"
            if item.get('recipient_status'):
                detail += f" | Estado: {item.get('recipient_status', 'pendiente')}"
            list_item = QListWidgetItem(title, widget)
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            list_item.setToolTip(detail)

    def _open_compose(self):
        dialog = ComposeMessageDialog(self.db, self.user, self)
        dialog.exec()
        self.load_data()

    def _open_detail(self, item: QListWidgetItem):
        payload = item.data(Qt.ItemDataRole.UserRole)
        if not payload:
            return
        if payload.get("recipient_id") and payload.get("recipient_status") != "leido":
            self.service.mark_as_read(payload.get("id"), self.user.id)
        dialog = MessageDetailDialog(self.service, payload, self)
        dialog.exec()


class MessageDetailDialog(QDialog):
    """Detailed view for a communication message."""

    def __init__(self, service: CommunicationService, payload: dict, parent=None):
        super().__init__(parent)
        self.service = service
        self.payload = payload
        self.user = getattr(parent, "user", None) if parent else None
        self.setWindowTitle(payload.get("subject", "Mensaje"))
        self.setMinimumWidth(460)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>{self.payload.get('subject', '')}</b>"))
        layout.addWidget(QLabel(f"Tipo: {self.payload.get('communication_type', '')}"))
        layout.addWidget(QLabel(f"Prioridad: {self.payload.get('priority', 'normal')}"))
        body = QTextEdit()
        body.setPlainText(self.payload.get("body", ""))
        body.setReadOnly(True)
        layout.addWidget(body)
        actions = QHBoxLayout()
        archive_button = QPushButton("Archivar")
        archive_button.clicked.connect(self._archive)
        actions.addWidget(archive_button)
        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(self.accept)
        actions.addWidget(close_button)
        layout.addLayout(actions)

    def _archive(self):
        try:
            if self.user is None:
                raise ValueError("Usuario no disponible")
            self.service.archive_message(self.payload.get("id"), self.user.id)
            QMessageBox.information(self, "Listo", "Mensaje archivado")
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
