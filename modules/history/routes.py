"""
History GUI routes/controllers for PyQt6 interface.

Expansiones implementadas en la UI:
  1  – Filtro por sucursal (combo selector)
  2  – Detalle expandido (panel lateral + botón "Ver Detalles")
  3  – Nombres legibles en tabla (usuario, entidad)
  4  – Diff de cambios (tabla Antes/Después en panel de detalles)
  5  – Búsqueda avanzada en details (checkbox "Buscar en detalles")
  6  – Historial de movimientos por producto (tab separado)
  7  – Archivado antes de limpieza (botón "Archivar y Limpiar")
  8  – Integridad referencial (badge "(Eliminado)" en filas huérfanas)
  9  – Logs del sistema (filtro "Solo sistema" en combo Tipo de Entidad)
"""

from __future__ import annotations

import logging
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QFrame, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSplitter,
    QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit,
    QVBoxLayout, QWidget,
)

from modules.history.service import HistoryService

logger = logging.getLogger(__name__)

# ── Paleta de colores por tipo de entidad ────────────────────────────────────
_ENTITY_COLOR: Dict[str, str] = {
    "product":   "#dbeafe",   # azul claro
    "branch":    "#dcfce7",   # verde claro
    "movement":  "#fef9c3",   # amarillo claro
    "inventory": "#f3e8ff",   # morado claro
    "alert":     "#fee2e2",   # rojo claro
    "user":      "#ffedd5",   # naranja claro
    "system":    "#f1f5f9",   # gris claro
}

_ENTITY_LABEL: Dict[str, str] = {
    "product":   "Producto",
    "branch":    "Sucursal",
    "movement":  "Movimiento",
    "inventory": "Inventario",
    "alert":     "Alerta",
    "user":      "Usuario",
    "system":    "Sistema",
}

# sentinel para combo "todos"
_ALL = "__all__"


# ════════════════════════════════════════════════════════════════════════════
# Helper – item con color de fondo
# ════════════════════════════════════════════════════════════════════════════

def _colored_item(text: str, bg_color: str = None) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    if bg_color:
        item.setBackground(QColor(bg_color))
    return item


def _deleted_item(text: str) -> QTableWidgetItem:
    """Item con texto tachado para entidades eliminadas (Expansión 8)."""
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    item.setForeground(QColor("#ef4444"))
    font = item.font()
    font.setStrikeOut(True)
    item.setFont(font)
    return item


# ════════════════════════════════════════════════════════════════════════════
# DetailPanel – panel lateral con detalles y diff (Expansiones 2 y 4)
# ════════════════════════════════════════════════════════════════════════════

class DetailPanel(QFrame):
    """
    Panel lateral que muestra el detalle completo de un registro seleccionado.
    Incluye: metadatos, JSON formateado y tabla de cambios Antes/Después.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumWidth(320)
        self._build_ui()
        self.clear()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        # Título
        self._title = QLabel("Detalle del evento")
        self._title.setStyleSheet("font-weight: bold; font-size: 13px;")
        root.addWidget(self._title)

        # Metadatos básicos
        meta_box = QGroupBox("Información general")
        meta_layout = QVBoxLayout(meta_box)
        self._meta_label = QLabel()
        self._meta_label.setWordWrap(True)
        self._meta_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        meta_layout.addWidget(self._meta_label)
        root.addWidget(meta_box)

        # Tabla de cambios – Expansión 4
        self._changes_box = QGroupBox("Cambios realizados")
        changes_layout = QVBoxLayout(self._changes_box)
        self._changes_table = QTableWidget(0, 3)
        self._changes_table.setHorizontalHeaderLabels(["Campo", "Antes", "Después"])
        self._changes_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._changes_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self._changes_table.setAlternatingRowColors(True)
        self._changes_table.setMaximumHeight(180)
        changes_layout.addWidget(self._changes_table)
        root.addWidget(self._changes_box)

        # JSON completo – Expansión 2
        json_box = QGroupBox("Datos completos (JSON)")
        json_layout = QVBoxLayout(json_box)
        self._json_text = QTextEdit()
        self._json_text.setReadOnly(True)
        self._json_text.setFont(QFont("Courier New", 9))
        self._json_text.setMinimumHeight(120)
        json_layout.addWidget(self._json_text)
        root.addWidget(json_box)
        root.addStretch()

    def clear(self):
        self._title.setText("Detalle del evento")
        self._meta_label.clear()
        self._changes_table.setRowCount(0)
        self._changes_box.setVisible(False)
        self._json_text.clear()

    def load(self, entry: Dict[str, Any], service: HistoryService):
        """Populate panel with data from a history entry dict."""
        import json as _json

        # ── Título ───────────────────────────────────────────────────────
        self._title.setText(entry.get("action", "Evento"))

        # ── Metadatos ────────────────────────────────────────────────────
        entity_name = service.get_entity_name(
            entry.get("entity_type"), entry.get("entity_id")
        )
        user_name = service.get_user_name(entry.get("user_id"))
        created = (entry.get("created_at") or "")[:19].replace("T", " ")
        deleted_flag = entry.get("entity_deleted", False)
        deleted_badge = "  ⚠ <b style='color:#ef4444'>(Eliminado)</b>" if deleted_flag else ""

        meta_lines = [
            f"<b>Tipo de evento:</b> {entry.get('event_type', '—')}",
            f"<b>Entidad:</b> {_ENTITY_LABEL.get(entry.get('entity_type',''), entry.get('entity_type',''))} "
            f"#{entry.get('entity_id', '—')} — {entity_name}{deleted_badge}",
            f"<b>Usuario:</b> {user_name}",
            f"<b>Fecha:</b> {created}",
        ]
        self._meta_label.setText("<br>".join(meta_lines))

        # ── Tabla de cambios (Expansión 4) ───────────────────────────────
        changes = service.get_change_summary(entry)
        if changes:
            self._changes_table.setRowCount(len(changes))
            for row, change in enumerate(changes):
                self._changes_table.setItem(
                    row, 0, QTableWidgetItem(change.get("campo", ""))
                )
                self._changes_table.setItem(
                    row, 1, QTableWidgetItem(str(change.get("antes", "—")))
                )
                self._changes_table.setItem(
                    row, 2, QTableWidgetItem(str(change.get("despues", "—")))
                )
            self._changes_box.setVisible(True)
        else:
            self._changes_table.setRowCount(0)
            self._changes_box.setVisible(False)

        # ── JSON completo (Expansión 2) ───────────────────────────────────
        details = entry.get("details")
        if details:
            try:
                self._json_text.setPlainText(_json.dumps(details, indent=2, ensure_ascii=False))
            except Exception:
                self._json_text.setPlainText(str(details))
        else:
            self._json_text.setPlainText("Sin datos adicionales.")


# ════════════════════════════════════════════════════════════════════════════
# ArchiveDialog – confirmar archivado y limpieza (Expansión 7)
# ════════════════════════════════════════════════════════════════════════════

class ArchiveDialog(QDialog):
    """
    Dialog to choose a date range for archiving + deleting history entries.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Archivar y Limpiar Historial")
        self.setFixedWidth(420)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            "Los registros dentro del rango seleccionado se copiarán a la tabla "
            "de archivo y luego se eliminarán del historial activo.\n\n"
            "Esta acción <b>no se puede deshacer</b>."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        date_row = QHBoxLayout()

        date_row.addWidget(QLabel("Desde:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addMonths(-3))
        date_row.addWidget(self.date_from)

        date_row.addWidget(QLabel("Hasta:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate().addDays(-1))
        date_row.addWidget(self.date_to)

        layout.addLayout(date_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Archivar y Limpiar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_range(self):
        """Return (date_from, date_to) as Python datetime objects."""
        d_from = self.date_from.date().toPyDate()
        d_to = self.date_to.date().toPyDate()
        return (
            datetime.combine(d_from, datetime.min.time()),
            datetime.combine(d_to, datetime.max.time()),
        )


# ════════════════════════════════════════════════════════════════════════════
# ProductMovementView – historial de movimientos por producto (Expansión 6)
# ════════════════════════════════════════════════════════════════════════════

class ProductMovementView(QWidget):
    """
    Tab that shows all movement-related history entries for a specific product.
    """

    # Columns: 0=ID(hidden), 1=Fecha, 2=Evento, 3=Movimiento#, 4=Acción
    _COLUMNS = ["ID", "Fecha", "Evento", "Movimiento #", "Acción"]

    def __init__(self, db: Session, parent=None):
        super().__init__(parent)
        self.db = db
        self.service = HistoryService(db)
        self._build_ui()
        self._populate_product_combo()

    def _build_ui(self):
        root = QVBoxLayout(self)

        # ── Barra de filtro ──────────────────────────────────────────────
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Producto:"))

        self.product_combo = QComboBox()
        self.product_combo.setMinimumWidth(260)
        bar.addWidget(self.product_combo)

        bar.addWidget(QLabel("Desde:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        bar.addWidget(self.date_from)

        bar.addWidget(QLabel("Hasta:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        bar.addWidget(self.date_to)

        search_btn = QPushButton("Buscar")
        search_btn.clicked.connect(self._load)
        bar.addWidget(search_btn)

        bar.addStretch()
        root.addLayout(bar)

        # ── Tabla ────────────────────────────────────────────────────────
        self.table = QTableWidget()
        self.table.setColumnCount(len(self._COLUMNS))
        self.table.setHorizontalHeaderLabels(self._COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table)

        self._count_label = QLabel("Sin resultados")
        root.addWidget(self._count_label)

    def _populate_product_combo(self):
        self.product_combo.clear()
        self.product_combo.addItem("Selecciona un producto…", None)
        try:
            from models.product import Product
            products = (
                self.db.query(Product)
                .filter(Product.is_active == True)
                .order_by(Product.name)
                .all()
            )
            for p in products:
                self.product_combo.addItem(f"{p.name}  ({p.sku})", p.id)
        except Exception as exc:
            logger.warning(f"ProductMovementView: could not load products: {exc}")

    def _load(self):
        product_id = self.product_combo.currentData()
        if not product_id:
            QMessageBox.information(self, "Aviso", "Selecciona un producto primero.")
            return

        d_from = datetime.combine(
            self.date_from.date().toPyDate(), datetime.min.time()
        )
        d_to = datetime.combine(
            self.date_to.date().toPyDate(), datetime.max.time()
        )

        try:
            entries = self.service.get_product_movement_history(
                product_id, limit=500, date_from=d_from, date_to=d_to
            )
        except Exception as exc:
            logger.exception("ProductMovementView load error")
            QMessageBox.critical(self, "Error", str(exc))
            return

        self.table.setRowCount(len(entries))
        for row, e in enumerate(entries):
            self.table.setItem(row, 0, QTableWidgetItem(str(e["id"])))
            self.table.setItem(
                row, 1,
                QTableWidgetItem((e["created_at"] or "")[:19].replace("T", " "))
            )
            self.table.setItem(row, 2, QTableWidgetItem(e["event_type"]))
            self.table.setItem(
                row, 3,
                QTableWidgetItem(str(e["entity_id"] or ""))
            )
            self.table.setItem(row, 4, QTableWidgetItem(e["action"]))

        self.table.resizeColumnsToContents()
        self._count_label.setText(f"{len(entries)} registros encontrados")


# ════════════════════════════════════════════════════════════════════════════
# HistoryListView – vista principal del historial (tab "Historial General")
# ════════════════════════════════════════════════════════════════════════════

class HistoryListView(QWidget):
    """
    Main history view with full filter bar, enriched table and detail panel.

    Columns (visible):
      Fecha | Evento | Tipo entidad | Entidad (nombre) | Usuario (nombre) | Acción

    Hidden: ID (col 0) for internal use.
    """

    _COLUMNS = [
        ("ID",           "id"),            # 0 – hidden
        ("Fecha",        "created_at"),    # 1
        ("Evento",       "event_type"),    # 2
        ("Tipo",         "entity_type"),   # 3
        ("Entidad",      "entity_name"),   # 4  enriched
        ("Usuario",      "user_name"),     # 5  enriched
        ("Acción",       "action"),        # 6
    ]

    def __init__(self, db: Session, parent=None):
        super().__init__(parent)
        self.db = db
        self.service = HistoryService(db)
        self._entries: List[Dict[str, Any]] = []
        self._build_ui()
        self._populate_filter_combos()
        self.load_data()

    # ─────────────────────────────────────────────────────────────────────────
    # UI Construction
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)

        # ── Título ───────────────────────────────────────────────────────
        title = QLabel("Historial General")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        root.addWidget(title)

        # ── Barra de filtros ─────────────────────────────────────────────
        root.addWidget(self._build_filter_bar())

        # ── Splitter: tabla + panel de detalles ──────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Tabla
        table_widget = QWidget()
        table_layout = QVBoxLayout(table_widget)
        table_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget()
        self.table.setColumnCount(len(self._COLUMNS))
        self.table.setHorizontalHeaderLabels([c[0] for c in self._COLUMNS])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        table_layout.addWidget(self.table)

        self._count_label = QLabel("Cargando…")
        table_layout.addWidget(self._count_label)

        splitter.addWidget(table_widget)

        # Panel de detalles (Expansiones 2 y 4)
        self.detail_panel = DetailPanel()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.detail_panel)
        scroll.setMinimumWidth(340)
        scroll.setMaximumWidth(480)
        splitter.addWidget(scroll)
        splitter.setSizes([680, 360])

        root.addWidget(splitter, stretch=1)

    def _build_filter_bar(self) -> QWidget:
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(4)

        # ── Fila 1: búsqueda y botones ───────────────────────────────────
        row1 = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar en acciones…")
        self.search_input.setMaximumWidth(280)
        self.search_input.returnPressed.connect(self.load_data)
        row1.addWidget(self.search_input)

        # Expansión 5 – checkbox búsqueda en details
        self.search_details_check = QCheckBox("Buscar en detalles")
        self.search_details_check.setToolTip(
            "Amplía la búsqueda al contenido completo del campo JSON de detalles"
        )
        row1.addWidget(self.search_details_check)

        row1.addStretch()

        refresh_btn = QPushButton("Actualizar")
        refresh_btn.clicked.connect(self.load_data)
        row1.addWidget(refresh_btn)

        # Expansión 7 – archivo
        archive_btn = QPushButton("Archivar y Limpiar…")
        archive_btn.setToolTip("Archiva registros de un rango de fechas y los elimina del historial activo")
        archive_btn.clicked.connect(self._on_archive)
        row1.addWidget(archive_btn)

        vbox.addLayout(row1)

        # ── Fila 2: filtros combinados ────────────────────────────────────
        row2 = QHBoxLayout()

        # Tipo de entidad (Expansión 9 incluye "Sistema")
        row2.addWidget(QLabel("Tipo:"))
        self.entity_type_combo = QComboBox()
        self.entity_type_combo.setMinimumWidth(140)
        self.entity_type_combo.currentIndexChanged.connect(self.load_data)
        row2.addWidget(self.entity_type_combo)

        # Expansión 1 – sucursal
        row2.addWidget(QLabel("Sucursal:"))
        self.branch_combo = QComboBox()
        self.branch_combo.setMinimumWidth(180)
        self.branch_combo.currentIndexChanged.connect(self.load_data)
        row2.addWidget(self.branch_combo)

        # Filtro por usuario
        row2.addWidget(QLabel("Usuario:"))
        self.user_combo = QComboBox()
        self.user_combo.setMinimumWidth(160)
        self.user_combo.currentIndexChanged.connect(self.load_data)
        row2.addWidget(self.user_combo)

        row2.addStretch()
        vbox.addLayout(row2)

        # ── Fila 3: rango de fechas ──────────────────────────────────────
        row3 = QHBoxLayout()

        row3.addWidget(QLabel("Desde:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_from.setSpecialValueText(" ")   # empty = no filter
        row3.addWidget(self.date_from)

        row3.addWidget(QLabel("Hasta:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        row3.addWidget(self.date_to)

        self.date_filter_check = QCheckBox("Filtrar por fechas")
        self.date_filter_check.setChecked(False)
        self.date_filter_check.stateChanged.connect(self.load_data)
        row3.addWidget(self.date_filter_check)

        row3.addStretch()
        vbox.addLayout(row3)

        return container

    # ─────────────────────────────────────────────────────────────────────────
    # Poblar combos de filtro
    # ─────────────────────────────────────────────────────────────────────────

    def _populate_filter_combos(self):
        """Fill entity type, branch and user combos."""
        # ── Tipo de entidad ──────────────────────────────────────────────
        self.entity_type_combo.blockSignals(True)
        self.entity_type_combo.clear()
        self.entity_type_combo.addItem("Todos los tipos", _ALL)
        for key, label in _ENTITY_LABEL.items():
            self.entity_type_combo.addItem(label, key)
        self.entity_type_combo.blockSignals(False)

        # ── Sucursales (Expansión 1) ─────────────────────────────────────
        self.branch_combo.blockSignals(True)
        self.branch_combo.clear()
        self.branch_combo.addItem("Todas las sucursales", None)
        try:
            from models.branch import Branch
            branches = (
                self.db.query(Branch)
                .filter(Branch.is_active == True)
                .order_by(Branch.name)
                .all()
            )
            for b in branches:
                self.branch_combo.addItem(b.name, b.id)
        except Exception as exc:
            logger.warning(f"Could not load branch filter: {exc}")
        self.branch_combo.blockSignals(False)

        # ── Usuarios ─────────────────────────────────────────────────────
        self.user_combo.blockSignals(True)
        self.user_combo.clear()
        self.user_combo.addItem("Todos los usuarios", None)
        try:
            from models.user import User
            users = (
                self.db.query(User)
                .filter(User.is_active == True)
                .order_by(User.name)
                .all()
            )
            for u in users:
                self.user_combo.addItem(u.name, u.id)
        except Exception as exc:
            logger.warning(f"Could not load user filter: {exc}")
        self.user_combo.blockSignals(False)

    # ─────────────────────────────────────────────────────────────────────────
    # Carga de datos
    # ─────────────────────────────────────────────────────────────────────────

    def load_data(self):
        """Reload history table applying all active filters."""
        search_term = self.search_input.text().strip() or None
        search_in_details = self.search_details_check.isChecked()

        entity_type = self.entity_type_combo.currentData()
        if entity_type == _ALL:
            entity_type = None

        branch_id = self.branch_combo.currentData()
        user_id = self.user_combo.currentData()

        date_from = None
        date_to = None
        if self.date_filter_check.isChecked():
            date_from = datetime.combine(
                self.date_from.date().toPyDate(), datetime.min.time()
            )
            date_to = datetime.combine(
                self.date_to.date().toPyDate(), datetime.max.time()
            )

        try:
            if search_term:
                entries = self.service.search_history(
                    search_term,
                    limit=500,
                    search_in_details=search_in_details,
                    enrich=True,
                )
                # Apply remaining filters client-side when using search
                if entity_type:
                    entries = [e for e in entries if e.get("entity_type") == entity_type]
                if user_id:
                    entries = [e for e in entries if e.get("user_id") == user_id]
            else:
                result = self.service.list_history(
                    limit=500,
                    entity_type=entity_type,
                    user_id=user_id,
                    branch_id=branch_id,
                    date_from=date_from,
                    date_to=date_to,
                    enrich=True,
                )
                entries = result["entries"]
        except Exception as exc:
            logger.exception("HistoryListView load_data error")
            QMessageBox.critical(self, "Error", f"No se pudo cargar el historial:\n{exc}")
            return

        # Expansión 8 – marcar entidades eliminadas
        entries = [self.service.sanitize_entry(e) for e in entries]

        self._entries = entries
        self._populate_table(entries)
        self._count_label.setText(f"{len(entries)} registro(s)")
        self.detail_panel.clear()

    def _populate_table(self, entries: List[Dict[str, Any]]):
        self.table.setRowCount(len(entries))
        for row, e in enumerate(entries):
            entity_type = e.get("entity_type") or ""
            bg_color = _ENTITY_COLOR.get(entity_type)
            deleted = e.get("entity_deleted", False)

            def item(text: str) -> QTableWidgetItem:
                if deleted:
                    return _deleted_item(text)
                return _colored_item(text, bg_color)

            self.table.setItem(row, 0, QTableWidgetItem(str(e["id"])))
            self.table.setItem(
                row, 1,
                item((e["created_at"] or "")[:19].replace("T", " "))
            )
            self.table.setItem(row, 2, item(e.get("event_type") or ""))

            # Tipo de entidad con label legible
            type_label = _ENTITY_LABEL.get(entity_type, entity_type)
            type_item = item(type_label)
            self.table.setItem(row, 3, type_item)

            # Expansión 3 – nombre de entidad
            entity_name = e.get("entity_name") or str(e.get("entity_id") or "")
            if deleted:
                entity_name = f"{entity_name}  (Eliminado)"
            self.table.setItem(row, 4, item(entity_name))

            # Expansión 3 – nombre de usuario
            self.table.setItem(row, 5, item(e.get("user_name") or "—"))

            self.table.setItem(row, 6, item(e.get("action") or ""))

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(
            6, QHeaderView.ResizeMode.Stretch
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Eventos UI
    # ─────────────────────────────────────────────────────────────────────────

    def _on_row_selected(self):
        """Show detail panel when a row is selected."""
        selected = self.table.selectedItems()
        if not selected:
            self.detail_panel.clear()
            return
        row = self.table.currentRow()
        if row < 0 or row >= len(self._entries):
            return
        entry = self._entries[row]
        try:
            self.detail_panel.load(entry, self.service)
        except Exception as exc:
            logger.exception("DetailPanel load error")

    def _on_archive(self):
        """Handle Archivar y Limpiar button (Expansión 7)."""
        dlg = ArchiveDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        date_from, date_to = dlg.get_range()
        confirm = QMessageBox.question(
            self,
            "Confirmar archivado",
            f"¿Archivar y eliminar registros entre\n"
            f"{date_from.date()} y {date_to.date()}?\n\n"
            f"Esta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            count = self.service.archive_history(date_from, date_to)
            QMessageBox.information(
                self, "Archivado completado",
                f"{count} registros archivados y eliminados del historial activo."
            )
            self.load_data()
        except Exception as exc:
            logger.exception("Archive error")
            QMessageBox.critical(self, "Error en archivado", str(exc))


# ════════════════════════════════════════════════════════════════════════════
# HistoryView – widget raíz con tabs
# ════════════════════════════════════════════════════════════════════════════

class HistoryView(QWidget):
    """
    Contenedor principal del módulo de historial.

    Tabs:
      1. Historial General   – HistoryListView (filtros, tabla enriquecida, panel)
      2. Movimientos por Producto – ProductMovementView (Expansión 6)
    """

    def __init__(self, db: Session, parent=None):
        super().__init__(parent)
        self.db = db
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()

        self.history_tab = HistoryListView(self.db)
        self.tabs.addTab(self.history_tab, "Historial General")

        self.product_movement_tab = ProductMovementView(self.db)
        self.tabs.addTab(self.product_movement_tab, "Movimientos por Producto")

        root.addWidget(self.tabs)

    def load_data(self):
        """Delegate refresh to the active tab (called by main window F5 / Actualizar)."""
        self.history_tab.load_data()
        # ProductMovementView only loads on explicit search; no auto-refresh needed.
