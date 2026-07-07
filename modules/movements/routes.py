"""
Movement GUI routes/controllers for PyQt6 interface.

Expansiones incluidas en la GUI:
  Exp 1 - Botón Cancelar + Botón Revertir en movimientos validados/rechazados
  Exp 2 - Botón Confirmar Recepción + Botón Rechazar Recepción en transferencias validadas
  Exp 3 - Filtro por prioridad + campo Prioridad al crear + botón Cambiar Prioridad
  Exp 4 - Campo Origen al crear movimiento
  Exp 5 - Campos Nro. Referencia y Tipo Referencia al crear + búsqueda por referencia
  Exp 6 - Costo unitario visible en detalles
  Exp 7 - Botón Ver Historial de Estados
  Exp 8 - Botón Confirmar Recepción Física en movimientos validados
"""

from typing import Optional
from sqlalchemy.orm import Session
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel, QLineEdit,
    QMessageBox, QDialog, QFormLayout, QSpinBox, QComboBox,
    QTextEdit, QGroupBox, QDateEdit, QInputDialog, QDoubleSpinBox,
    QTabWidget, QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate
from PyQt6.QtGui import QColor
from modules.movements.service import MovementService
from modules.products.service import ProductService
from modules.branches.service import BranchService
from config import MOVEMENT_TYPES, MOVEMENT_STATES
import logging

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Constantes locales para campos nuevos
# ------------------------------------------------------------------
MOVEMENT_PRIORITIES = {
    "baja": "Baja",
    "normal": "Normal",
    "alta": "Alta",
    "urgente": "Urgente",
}

MOVEMENT_SOURCES = {
    "app": "Aplicación",
    "web": "Web",
    "import": "Importación",
    "api": "API",
    "system": "Sistema",
    "scheduled": "Programado",
}

REFERENCE_TYPES = {
    "factura": "Factura",
    "orden_compra": "Orden de Compra",
    "nota_remision": "Nota de Remisión",
    "otro": "Otro",
}

# Color de fondo para filas canceladas
_COLOR_CANCELLED = QColor(220, 220, 220)   # gris claro
_COLOR_VALIDATED = QColor(200, 230, 200)   # verde claro
_COLOR_REJECTED  = QColor(255, 200, 200)   # rojo claro
_COLOR_PENDING   = QColor(255, 255, 190)   # amarillo claro
_COLOR_URGENT    = QColor(255, 180, 100)   # naranja (urgente)


# ======================================================================
# Diálogo: Crear movimiento (extendido con Exp 3, 4, 5)
# ======================================================================
class MovementDialog(QDialog):
    """Dialog for creating movements."""

    def __init__(self, db: Session, user_id: int, parent=None):
        super().__init__(parent)
        self.db = db
        self.user_id = user_id
        self.product_service = ProductService(db)
        self.branch_service = BranchService(db)
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Nuevo Movimiento")
        self.setMinimumWidth(520)
        layout = QFormLayout()

        # Tipo de movimiento
        self.type_combo = QComboBox()
        for key, label in MOVEMENT_TYPES.items():
            self.type_combo.addItem(label, key)
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        layout.addRow("Tipo de Movimiento*:", self.type_combo)

        # Producto
        self.product_combo = QComboBox()
        for p in self.product_service.get_all_active_products():
            self.product_combo.addItem(f"{p['sku']} - {p['name']}", p['id'])
        layout.addRow("Producto*:", self.product_combo)

        # Sucursal origen
        self.branch_combo = QComboBox()
        branches = self.branch_service.get_all_active_branches()
        for b in branches:
            self.branch_combo.addItem(b['name'], b['id'])
        layout.addRow("Sucursal Origen*:", self.branch_combo)

        # Sucursal destino (transferencias)
        self.dest_branch_label = QLabel("Sucursal Destino*:")
        self.dest_branch_combo = QComboBox()
        for b in branches:
            self.dest_branch_combo.addItem(b['name'], b['id'])
        layout.addRow(self.dest_branch_label, self.dest_branch_combo)
        self.dest_branch_label.hide()
        self.dest_branch_combo.hide()

        # Cantidad
        self.quantity_spin = QSpinBox()
        self.quantity_spin.setRange(1, 999999)
        self.quantity_spin.setValue(1)
        layout.addRow("Cantidad*:", self.quantity_spin)

        # Exp 3 – Prioridad
        self.priority_combo = QComboBox()
        for key, label in MOVEMENT_PRIORITIES.items():
            self.priority_combo.addItem(label, key)
        self.priority_combo.setCurrentIndex(1)  # "normal" por defecto
        layout.addRow("Prioridad:", self.priority_combo)

        # Exp 4 – Origen/fuente
        self.source_combo = QComboBox()
        for key, label in MOVEMENT_SOURCES.items():
            self.source_combo.addItem(label, key)
        layout.addRow("Fuente/Origen:", self.source_combo)

        # Separador referencia
        sep = QLabel("— Documento de Referencia (opcional) —")
        sep.setStyleSheet("color: gray; font-size: 11px;")
        layout.addRow(sep)

        # Exp 5 – Número de referencia
        self.reference_number_input = QLineEdit()
        self.reference_number_input.setPlaceholderText("Ej: FAC-2025-001")
        layout.addRow("Nro. Referencia:", self.reference_number_input)

        # Exp 5 – Tipo de referencia
        self.reference_type_combo = QComboBox()
        self.reference_type_combo.addItem("(ninguno)", None)
        for key, label in REFERENCE_TYPES.items():
            self.reference_type_combo.addItem(label, key)
        layout.addRow("Tipo Referencia:", self.reference_type_combo)

        # Razón
        self.reason_input = QTextEdit()
        self.reason_input.setMaximumHeight(70)
        layout.addRow("Razón:", self.reason_input)

        # Notas
        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(70)
        layout.addRow("Notas:", self.notes_input)

        # Botones
        btn_layout = QHBoxLayout()
        self.save_button = QPushButton("Crear")
        self.save_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.reject)
        btn_layout.addWidget(self.save_button)
        btn_layout.addWidget(self.cancel_button)
        layout.addRow(btn_layout)

        self.setLayout(layout)
        self.on_type_changed(0)

    def on_type_changed(self, index: int):
        is_transfer = self.type_combo.currentData() == "transferencia"
        self.dest_branch_label.setVisible(is_transfer)
        self.dest_branch_combo.setVisible(is_transfer)

    def get_data(self) -> dict:
        ref_type = self.reference_type_combo.currentData()
        ref_num = self.reference_number_input.text().strip() or None
        return {
            "movement_type": self.type_combo.currentData(),
            "product_id": self.product_combo.currentData(),
            "branch_id": self.branch_combo.currentData(),
            "destination_branch_id": (
                self.dest_branch_combo.currentData()
                if self.type_combo.currentData() == "transferencia" else None
            ),
            "quantity": self.quantity_spin.value(),
            "priority": self.priority_combo.currentData(),
            "source": self.source_combo.currentData(),
            "reference_number": ref_num,
            "reference_type": ref_type if ref_num else None,
            "reason": self.reason_input.toPlainText().strip() or None,
            "notes": self.notes_input.toPlainText().strip() or None,
            "user_id": self.user_id,
        }


# ======================================================================
# Diálogo: Traslado directo (extendido con Exp 3, 4, 5)
# ======================================================================
class DirectTransferDialog(QDialog):
    """Dialog for direct transfers between branches (simplified flow)."""

    def __init__(self, db: Session, user_id: int, parent=None):
        super().__init__(parent)
        self.db = db
        self.user_id = user_id
        self.product_service = ProductService(db)
        self.branch_service = BranchService(db)
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Traslado Directo entre Sucursales")
        self.setMinimumWidth(520)
        layout = QFormLayout()

        self.product_combo = QComboBox()
        for p in self.product_service.get_all_active_products():
            self.product_combo.addItem(f"{p['sku']} - {p['name']}", p['id'])
        self.product_combo.currentIndexChanged.connect(self.on_selection_changed)
        layout.addRow("Producto*:", self.product_combo)

        self.branch_combo = QComboBox()
        branches = self.branch_service.get_all_active_branches()
        for b in branches:
            self.branch_combo.addItem(b['name'], b['id'])
        self.branch_combo.currentIndexChanged.connect(self.on_selection_changed)
        layout.addRow("Sucursal Origen*:", self.branch_combo)

        self.dest_branch_combo = QComboBox()
        for b in branches:
            self.dest_branch_combo.addItem(b['name'], b['id'])
        layout.addRow("Sucursal Destino*:", self.dest_branch_combo)

        self.quantity_spin = QSpinBox()
        self.quantity_spin.setRange(1, 999999)
        self.quantity_spin.setValue(1)
        layout.addRow("Cantidad*:", self.quantity_spin)

        # Exp 3 – Prioridad
        self.priority_combo = QComboBox()
        for key, label in MOVEMENT_PRIORITIES.items():
            self.priority_combo.addItem(label, key)
        self.priority_combo.setCurrentIndex(1)
        layout.addRow("Prioridad:", self.priority_combo)

        # Exp 5 – Referencia
        self.reference_number_input = QLineEdit()
        self.reference_number_input.setPlaceholderText("Nro. documento externo (opcional)")
        layout.addRow("Nro. Referencia:", self.reference_number_input)

        self.reference_type_combo = QComboBox()
        self.reference_type_combo.addItem("(ninguno)", None)
        for key, label in REFERENCE_TYPES.items():
            self.reference_type_combo.addItem(label, key)
        layout.addRow("Tipo Referencia:", self.reference_type_combo)

        self.reason_input = QTextEdit()
        self.reason_input.setMaximumHeight(70)
        layout.addRow("Razón:", self.reason_input)

        self.stock_label = QLabel("Stock disponible en origen: -")
        self.stock_label.setStyleSheet("color: #0055aa; font-weight: bold;")
        layout.addRow(self.stock_label)

        btn_layout = QHBoxLayout()
        self.save_button = QPushButton("Ejecutar Traslado")
        self.save_button.setStyleSheet("background-color: #1565C0; color: white; font-weight: bold;")
        self.save_button.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.save_button)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

        self.setLayout(layout)
        self.on_selection_changed(0)

    def on_selection_changed(self, _index=None):
        branch_id = self.branch_combo.currentData()
        product_id = self.product_combo.currentData()
        if branch_id and product_id:
            from modules.inventory.service import InventoryService
            inv = InventoryService(self.db).get_inventory_by_product_branch(product_id, branch_id)
            stock = inv['digital_stock'] if inv else 0
            self.stock_label.setText(f"Stock disponible en origen: {stock}")

    def get_data(self) -> dict:
        ref_num = self.reference_number_input.text().strip() or None
        return {
            "movement_type": "transferencia",
            "product_id": self.product_combo.currentData(),
            "branch_id": self.branch_combo.currentData(),
            "destination_branch_id": self.dest_branch_combo.currentData(),
            "quantity": self.quantity_spin.value(),
            "priority": self.priority_combo.currentData(),
            "reference_number": ref_num,
            "reference_type": self.reference_type_combo.currentData() if ref_num else None,
            "reason": self.reason_input.toPlainText().strip() or None,
            "notes": None,
            "user_id": self.user_id,
        }


# ======================================================================
# Diálogo: Detalles de movimiento (Exp 6 costos, Exp 7 historial)
# ======================================================================
class MovementDetailDialog(QDialog):
    """Read-only dialog showing full movement details + state history."""

    def __init__(self, service: MovementService, movement_id: int, parent=None):
        super().__init__(parent)
        self.service = service
        self.movement_id = movement_id
        self.setWindowTitle(f"Detalles del Movimiento #{movement_id}")
        self.setMinimumWidth(560)
        self.setMinimumHeight(480)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        tabs = QTabWidget()

        # --- Tab 1: Datos generales ---
        general_widget = QWidget()
        general_layout = QFormLayout()
        movement = self.service.get_movement_details(self.movement_id)
        if not movement:
            layout.addWidget(QLabel("Movimiento no encontrado."))
            self.setLayout(layout)
            return

        def _add(label, value):
            lbl = QLabel(str(value) if value is not None else "—")
            lbl.setWordWrap(True)
            general_layout.addRow(f"{label}:", lbl)

        _add("ID", movement['id'])
        _add("Tipo", MOVEMENT_TYPES.get(movement['movement_type'], movement['movement_type']))
        _add("Estado", MOVEMENT_STATES.get(movement['state'], movement['state']))
        _add("Producto", (movement.get('product') or {}).get('name', '—'))
        _add("Sucursal origen", (movement.get('branch') or {}).get('name', '—'))
        _add("Sucursal destino", (movement.get('destination_branch') or {}).get('name', '—'))
        _add("Usuario", (movement.get('user') or {}).get('name', '—'))
        _add("Cantidad", movement['quantity'])
        _add("Prioridad", MOVEMENT_PRIORITIES.get(movement.get('priority', 'normal'), movement.get('priority', '—')))
        _add("Fuente", MOVEMENT_SOURCES.get(movement.get('source', ''), movement.get('source', '—')))
        _add("Razón", movement.get('reason'))
        _add("Notas", movement.get('notes'))
        _add("Fecha creación", (movement.get('created_at') or '')[:19])
        _add("Validado el", (movement.get('validated_at') or '')[:19] or '—')

        # Exp 5 – Referencia
        sep1 = QLabel("Documento de Referencia")
        sep1.setStyleSheet("font-weight: bold; margin-top: 6px;")
        general_layout.addRow(sep1)
        _add("Nro. Referencia", movement.get('reference_number'))
        _add("Tipo Referencia", REFERENCE_TYPES.get(movement.get('reference_type', ''), movement.get('reference_type')))

        # Exp 6 – Costos
        sep2 = QLabel("Costos")
        sep2.setStyleSheet("font-weight: bold; margin-top: 6px;")
        general_layout.addRow(sep2)
        unit_cost = movement.get('unit_cost')
        total_cost = movement.get('total_cost')
        _add("Costo unitario", f"${unit_cost:.4f}" if unit_cost is not None else None)
        _add("Costo total", f"${total_cost:.4f}" if total_cost is not None else None)

        # Exp 1 – Cancelación
        if movement.get('is_cancelled'):
            sep3 = QLabel("Cancelación")
            sep3.setStyleSheet("font-weight: bold; color: red; margin-top: 6px;")
            general_layout.addRow(sep3)
            _add("Cancelado el", (movement.get('cancelled_at') or '')[:19])
            _add("Motivo cancelación", movement.get('cancellation_reason'))

        # Exp 2 – Recepción de transferencia
        if movement.get('movement_type') == 'transferencia':
            sep4 = QLabel("Recepción de Transferencia")
            sep4.setStyleSheet("font-weight: bold; margin-top: 6px;")
            general_layout.addRow(sep4)
            _add("Recibida", "Sí" if movement.get('is_received') else "No")
            if movement.get('is_received'):
                _add("Recibido el", (movement.get('received_at') or '')[:19])
                _add("Notas recepción", movement.get('received_notes'))

        # Exp 8 – Recepción física
        if movement.get('receiver_name'):
            sep5 = QLabel("Recepción Física")
            sep5.setStyleSheet("font-weight: bold; margin-top: 6px;")
            general_layout.addRow(sep5)
            _add("Receptor", movement.get('receiver_name'))

        general_widget.setLayout(general_layout)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(general_widget)
        tabs.addTab(scroll, "General")

        # --- Tab 2: Historial de estados (Exp 7) ---
        history_widget = QWidget()
        history_layout = QVBoxLayout()
        history = self.service.get_state_history(self.movement_id)
        if history:
            hist_table = QTableWidget()
            hist_table.setColumnCount(4)
            hist_table.setHorizontalHeaderLabels(["Estado anterior", "Estado nuevo", "Por", "Fecha"])
            hist_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            hist_table.setRowCount(len(history))
            for row, entry in enumerate(history):
                hist_table.setItem(row, 0, QTableWidgetItem(entry.get('previous_state') or '(inicio)'))
                hist_table.setItem(row, 1, QTableWidgetItem(entry.get('new_state', '')))
                hist_table.setItem(row, 2, QTableWidgetItem(str(entry.get('changed_by') or '—')))
                hist_table.setItem(row, 3, QTableWidgetItem((entry.get('created_at') or '')[:19]))
            hist_table.resizeColumnsToContents()
            history_layout.addWidget(hist_table)
        else:
            history_layout.addWidget(QLabel("No hay historial de estados registrado."))
        history_widget.setLayout(history_layout)
        tabs.addTab(history_widget, "Historial de Estados")

        layout.addWidget(tabs)

        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        self.setLayout(layout)


# ======================================================================
# Vista principal: lista de movimientos (todas las expansiones integradas)
# ======================================================================
class MovementListView(QWidget):
    """Movement list view widget with all expansion features."""

    movement_selected = pyqtSignal(int)

    def __init__(self, db: Session, current_user_id: int, parent=None):
        super().__init__(parent)
        self.db = db
        self.current_user_id = current_user_id
        self.service = MovementService(db)
        self.branch_service = BranchService(db)
        self.current_branch_id = None
        self.current_type = None
        self.current_state = None
        self.current_priority = None      # Exp 3
        self.show_cancelled = False       # Exp 1
        self.setup_ui()
        self.load_movements()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def setup_ui(self):
        layout = QVBoxLayout()

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Gestión de Movimientos")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.add_button = QPushButton("Nuevo Movimiento")
        self.add_button.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold;")
        self.add_button.clicked.connect(self.on_add_movement)
        header_layout.addWidget(self.add_button)

        self.direct_transfer_button = QPushButton("Traslado Directo")
        self.direct_transfer_button.setStyleSheet("background-color: #1565C0; color: white;")
        self.direct_transfer_button.clicked.connect(self.on_direct_transfer)
        header_layout.addWidget(self.direct_transfer_button)

        # Exp 5 – búsqueda por referencia
        self.reference_search = QLineEdit()
        self.reference_search.setPlaceholderText("Buscar por nro. referencia…")
        self.reference_search.setMaximumWidth(200)
        self.reference_search.returnPressed.connect(self.on_search_by_reference)
        header_layout.addWidget(self.reference_search)
        search_btn = QPushButton("Buscar")
        search_btn.clicked.connect(self.on_search_by_reference)
        header_layout.addWidget(search_btn)

        layout.addLayout(header_layout)

        # Filters row 1
        filter_layout = QHBoxLayout()

        self.branch_combo = QComboBox()
        self.branch_combo.addItem("Todas las sucursales", None)
        for b in self.branch_service.get_all_active_branches():
            self.branch_combo.addItem(b['name'], b['id'])
        self.branch_combo.currentIndexChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(QLabel("Sucursal:"))
        filter_layout.addWidget(self.branch_combo)

        self.type_combo = QComboBox()
        self.type_combo.addItem("Todos los tipos", None)
        for key, label in MOVEMENT_TYPES.items():
            self.type_combo.addItem(label, key)
        self.type_combo.currentIndexChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(QLabel("Tipo:"))
        filter_layout.addWidget(self.type_combo)

        self.state_combo = QComboBox()
        self.state_combo.addItem("Todos los estados", None)
        for key, label in MOVEMENT_STATES.items():
            self.state_combo.addItem(label, key)
        self.state_combo.currentIndexChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(QLabel("Estado:"))
        filter_layout.addWidget(self.state_combo)

        # Exp 3 – filtro prioridad
        self.priority_filter_combo = QComboBox()
        self.priority_filter_combo.addItem("Todas las prioridades", None)
        for key, label in MOVEMENT_PRIORITIES.items():
            self.priority_filter_combo.addItem(label, key)
        self.priority_filter_combo.currentIndexChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(QLabel("Prioridad:"))
        filter_layout.addWidget(self.priority_filter_combo)

        # Exp 1 – mostrar cancelados
        self.show_cancelled_btn = QPushButton("Mostrar cancelados")
        self.show_cancelled_btn.setCheckable(True)
        self.show_cancelled_btn.toggled.connect(self.on_cancelled_toggled)
        filter_layout.addWidget(self.show_cancelled_btn)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Table — 10 columnas visibles (ID oculta)
        self.table = QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "ID", "Tipo", "Producto", "Sucursal", "Cantidad",
            "Estado", "Prioridad", "Referencia", "Usuario", "Fecha", "Acciones",
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self.setLayout(layout)

    # ------------------------------------------------------------------
    # Load / Refresh
    # ------------------------------------------------------------------

    def load_movements(self):
        result = self.service.list_movements(
            page=1,
            page_size=200,
            branch_id=self.current_branch_id,
            movement_type=self.current_type,
            state=self.current_state,
            priority=self.current_priority,
            include_cancelled=self.show_cancelled,
        )
        movements = result["movements"]
        self.table.setRowCount(len(movements))

        for row, mv in enumerate(movements):
            self._fill_row(row, mv)

        self.table.resizeColumnsToContents()

    def _fill_row(self, row: int, mv: dict):
        """Populate a single table row from a movement dict."""
        is_cancelled = mv.get("is_cancelled", False)
        priority = mv.get("priority", "normal")

        # --- Cells ---
        self.table.setItem(row, 0, QTableWidgetItem(str(mv["id"])))
        self.table.setItem(row, 1, QTableWidgetItem(MOVEMENT_TYPES.get(mv["movement_type"], mv["movement_type"])))
        self.table.setItem(row, 2, QTableWidgetItem((mv.get("product") or {}).get("name", "N/A")))
        self.table.setItem(row, 3, QTableWidgetItem((mv.get("branch") or {}).get("name", "N/A")))
        self.table.setItem(row, 4, QTableWidgetItem(str(mv["quantity"])))

        # Estado
        state_label = MOVEMENT_STATES.get(mv["state"], mv["state"])
        if is_cancelled:
            state_label += " (cancelado)"
        state_item = QTableWidgetItem(state_label)
        if is_cancelled:
            bg = _COLOR_CANCELLED
        elif mv["state"] == "validado":
            bg = _COLOR_VALIDATED
        elif mv["state"] == "rechazado":
            bg = _COLOR_REJECTED
        else:
            bg = _COLOR_PENDING if priority != "urgente" else _COLOR_URGENT
        state_item.setBackground(bg)
        self.table.setItem(row, 5, state_item)

        # Prioridad (Exp 3)
        pri_label = MOVEMENT_PRIORITIES.get(priority, priority)
        pri_item = QTableWidgetItem(pri_label)
        if priority == "urgente":
            pri_item.setBackground(_COLOR_URGENT)
        elif priority == "alta":
            pri_item.setBackground(QColor(255, 230, 150))
        self.table.setItem(row, 6, pri_item)

        # Referencia (Exp 5)
        ref = mv.get("reference_number") or "—"
        self.table.setItem(row, 7, QTableWidgetItem(ref))

        # Usuario
        user_name = (mv.get("user") or {}).get("name", "N/A")
        self.table.setItem(row, 8, QTableWidgetItem(user_name))

        # Fecha
        date_str = (mv.get("created_at") or "")[:19]
        self.table.setItem(row, 9, QTableWidgetItem(date_str))

        # Acciones
        self.table.setCellWidget(row, 10, self._build_actions(mv))

    def _build_actions(self, mv: dict) -> QWidget:
        """Build action buttons widget for a movement row."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(4)

        mid = mv["id"]
        state = mv["state"]
        is_cancelled = mv.get("is_cancelled", False)
        is_transfer = mv["movement_type"] == "transferencia"
        is_received = mv.get("is_received", False)

        # Siempre: Ver Detalles (Exp 6, 7)
        btn_details = QPushButton("Ver")
        btn_details.setToolTip("Ver detalles y historial de estados")
        btn_details.clicked.connect(lambda _, m=mid: self.on_view_movement(m))
        layout.addWidget(btn_details)

        if is_cancelled:
            # Exp 1 – revertir movimiento cancelado
            btn_reverse = QPushButton("Revertir")
            btn_reverse.setStyleSheet("background-color: #E65100; color: white;")
            btn_reverse.setToolTip("Crear movimiento compensatorio")
            btn_reverse.clicked.connect(lambda _, m=mid: self.on_reverse_movement(m))
            layout.addWidget(btn_reverse)
            return widget

        if state == "pendiente":
            btn_validate = QPushButton("Validar")
            btn_validate.setStyleSheet("background-color: #4CAF50; color: white;")
            btn_validate.clicked.connect(lambda _, m=mid: self.on_validate_movement(m))
            layout.addWidget(btn_validate)

            btn_reject = QPushButton("Rechazar")
            btn_reject.setStyleSheet("background-color: #f44336; color: white;")
            btn_reject.clicked.connect(lambda _, m=mid: self.on_reject_movement(m))
            layout.addWidget(btn_reject)

            # Exp 3 – cambiar prioridad
            btn_priority = QPushButton("Prioridad")
            btn_priority.setToolTip("Cambiar prioridad")
            btn_priority.clicked.connect(lambda _, m=mid: self.on_set_priority(m))
            layout.addWidget(btn_priority)

            btn_delete = QPushButton("Eliminar")
            btn_delete.clicked.connect(lambda _, m=mid: self.on_delete_movement(m))
            layout.addWidget(btn_delete)

        elif state in ("validado", "rechazado"):
            # Exp 1 – cancelar
            btn_cancel = QPushButton("Cancelar")
            btn_cancel.setStyleSheet("background-color: #757575; color: white;")
            btn_cancel.setToolTip("Cancelar este movimiento")
            btn_cancel.clicked.connect(lambda _, m=mid: self.on_cancel_movement(m))
            layout.addWidget(btn_cancel)

            # Exp 2 – confirmar / rechazar recepción en transferencias
            if state == "validado" and is_transfer and not is_received:
                btn_recv = QPushButton("Confirmar Recepción")
                btn_recv.setStyleSheet("background-color: #00796B; color: white;")
                btn_recv.clicked.connect(lambda _, m=mid: self.on_confirm_reception(m))
                layout.addWidget(btn_recv)

                btn_rej_recv = QPushButton("Rechazar Recepción")
                btn_rej_recv.setStyleSheet("background-color: #B71C1C; color: white;")
                btn_rej_recv.clicked.connect(lambda _, m=mid: self.on_reject_reception(m))
                layout.addWidget(btn_rej_recv)

            # Exp 8 – confirmar recepción física si no tiene receptor
            if state == "validado" and not mv.get("receiver_name"):
                btn_sign = QPushButton("Receptor Físico")
                btn_sign.setToolTip("Registrar quién recibió físicamente")
                btn_sign.clicked.connect(lambda _, m=mid: self.on_confirm_physical_reception(m))
                layout.addWidget(btn_sign)

        return widget

    # ------------------------------------------------------------------
    # Filter / search handlers
    # ------------------------------------------------------------------

    def on_filter_changed(self):
        self.current_branch_id = self.branch_combo.currentData()
        self.current_type = self.type_combo.currentData()
        self.current_state = self.state_combo.currentData()
        self.current_priority = self.priority_filter_combo.currentData()
        self.load_movements()

    def on_cancelled_toggled(self, checked: bool):
        self.show_cancelled = checked
        self.show_cancelled_btn.setText(
            "Ocultar cancelados" if checked else "Mostrar cancelados"
        )
        self.load_movements()

    def on_search_by_reference(self):
        """Exp 5 – search by reference number."""
        ref = self.reference_search.text().strip()
        if not ref:
            self.load_movements()
            return
        try:
            movements = self.service.search_by_reference(ref)
            self.table.setRowCount(len(movements))
            for row, mv in enumerate(movements):
                self._fill_row(row, mv)
            self.table.resizeColumnsToContents()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    # ------------------------------------------------------------------
    # Core actions
    # ------------------------------------------------------------------

    def on_add_movement(self):
        dialog = MovementDialog(self.db, self.current_user_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                data = dialog.get_data()
                if not data["movement_type"] or not data["product_id"] or not data["branch_id"]:
                    QMessageBox.warning(self, "Error", "Complete los campos requeridos")
                    return
                self.service.create_movement(data)
                QMessageBox.information(self, "Éxito", "Movimiento creado exitosamente")
                self.load_movements()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al crear movimiento: {e}")

    def on_direct_transfer(self):
        dialog = DirectTransferDialog(self.db, self.current_user_id, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                data = dialog.get_data()
                self.service.execute_direct_transfer(data)
                QMessageBox.information(self, "Éxito", "Traslado ejecutado exitosamente")
                self.load_movements()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al ejecutar traslado: {e}")

    def on_validate_movement(self, movement_id: int):
        reply = QMessageBox.question(self, "Confirmar", "¿Validar este movimiento?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                movement = self.service.validate_movement(movement_id, self.current_user_id)
                if movement and movement.get("state") == "rechazado":
                    QMessageBox.warning(self, "Rechazado automáticamente",
                                        "El movimiento fue rechazado por no cumplir la validación.")
                else:
                    QMessageBox.information(self, "Éxito", "Movimiento validado exitosamente")
                self.load_movements()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al validar: {e}")

    def on_reject_movement(self, movement_id: int):
        reason, ok = QInputDialog.getText(self, "Razón de Rechazo", "Ingrese la razón del rechazo:")
        if ok:
            try:
                self.service.reject_movement(movement_id, self.current_user_id, reason)
                QMessageBox.information(self, "Éxito", "Movimiento rechazado")
                self.load_movements()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al rechazar: {e}")

    def on_delete_movement(self, movement_id: int):
        reply = QMessageBox.question(self, "Confirmar", "¿Eliminar este movimiento pendiente?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.service.delete_movement(movement_id)
                QMessageBox.information(self, "Éxito", "Movimiento eliminado")
                self.load_movements()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al eliminar: {e}")

    def on_view_movement(self, movement_id: int):
        """Exp 6 + Exp 7: show details dialog with costs and state history."""
        dialog = MovementDetailDialog(self.service, movement_id, self)
        dialog.exec()

    # ------------------------------------------------------------------
    # Expansión 1 – Cancelar / Revertir
    # ------------------------------------------------------------------

    def on_cancel_movement(self, movement_id: int):
        reason, ok = QInputDialog.getText(
            self, "Cancelar Movimiento",
            "Ingrese la razón de cancelación (obligatorio):"
        )
        if ok and reason.strip():
            try:
                self.service.cancel_movement(movement_id, self.current_user_id, reason.strip())
                QMessageBox.information(self, "Éxito", "Movimiento cancelado")
                self.load_movements()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al cancelar: {e}")
        elif ok:
            QMessageBox.warning(self, "Requerido", "Debe ingresar una razón de cancelación.")

    def on_reverse_movement(self, movement_id: int):
        reply = QMessageBox.question(
            self, "Revertir Movimiento",
            "Esto creará un movimiento compensatorio que revierte el efecto del original.\n"
            "El movimiento compensatorio quedará pendiente de validación.\n\n¿Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                comp = self.service.reverse_movement(movement_id, self.current_user_id)
                QMessageBox.information(
                    self, "Éxito",
                    f"Movimiento compensatorio creado con ID #{comp['id']}.\n"
                    "Está pendiente de validación."
                )
                self.load_movements()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al revertir: {e}")

    # ------------------------------------------------------------------
    # Expansión 2 – Confirmar / Rechazar recepción de transferencia
    # ------------------------------------------------------------------

    def on_confirm_reception(self, movement_id: int):
        notes, ok = QInputDialog.getText(
            self, "Confirmar Recepción",
            "Notas de recepción (opcional):"
        )
        if ok:
            try:
                self.service.confirm_transfer_reception(
                    movement_id, self.current_user_id,
                    notes.strip() or None,
                )
                QMessageBox.information(self, "Éxito", "Recepción de transferencia confirmada")
                self.load_movements()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al confirmar recepción: {e}")

    def on_reject_reception(self, movement_id: int):
        reason, ok = QInputDialog.getText(
            self, "Rechazar Recepción",
            "Razón del rechazo de recepción (obligatorio):"
        )
        if ok and reason.strip():
            try:
                self.service.reject_transfer_reception(
                    movement_id, self.current_user_id, reason.strip()
                )
                QMessageBox.warning(self, "Recepción rechazada",
                                    "La recepción fue rechazada y el movimiento fue cancelado.")
                self.load_movements()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al rechazar recepción: {e}")
        elif ok:
            QMessageBox.warning(self, "Requerido", "Debe ingresar una razón.")

    # ------------------------------------------------------------------
    # Expansión 3 – Cambiar prioridad
    # ------------------------------------------------------------------

    def on_set_priority(self, movement_id: int):
        options = list(MOVEMENT_PRIORITIES.values())
        keys = list(MOVEMENT_PRIORITIES.keys())
        choice, ok = QInputDialog.getItem(
            self, "Cambiar Prioridad", "Seleccione la nueva prioridad:", options, 1, False
        )
        if ok:
            priority_key = keys[options.index(choice)]
            try:
                self.service.set_priority(movement_id, priority_key)
                self.load_movements()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al cambiar prioridad: {e}")

    # ------------------------------------------------------------------
    # Expansión 8 – Recepción física
    # ------------------------------------------------------------------

    def on_confirm_physical_reception(self, movement_id: int):
        receiver_name, ok = QInputDialog.getText(
            self, "Confirmar Recepción Física",
            "Nombre completo de quien recibió físicamente:"
        )
        if ok and receiver_name.strip():
            try:
                self.service.confirm_reception_with_signature(
                    movement_id, receiver_name.strip()
                )
                QMessageBox.information(self, "Éxito",
                                        f"Recepción física registrada para: {receiver_name.strip()}")
                self.load_movements()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al registrar receptor: {e}")
        elif ok:
            QMessageBox.warning(self, "Requerido", "Debe ingresar el nombre del receptor.")
