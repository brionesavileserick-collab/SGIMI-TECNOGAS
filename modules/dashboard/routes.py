"""
Dashboard GUI routes/controllers for PyQt6 interface.

Expansions implemented:
  Exp 1  – Branch filter selector in header
  Exp 2  – Period selector (Hoy / Semana / Mes / Mes anterior / Personalizado)
  Exp 3  – Trend indicators (↑↓) on metric cards
  Exp 4  – Quick action buttons (Nuevo Movimiento, Ver Inventario,
            Transferencias Pendientes, Stock Bajo)
  Exp 5  – Branch ranking widget with metric selector
  Exp 6  – Transfers widget (Por Enviar / Por Recibir)
  Exp 7  – Efficiency widget with color-coded rates
  Exp 8  – Alert badge counts and urgent-alert banner
  Exp 9  – "Configurar Dashboard" dialog (show/hide widgets)
  Exp 10 – Simple text-based trend sparklines
  Exp 11 – Quick-stats banner at the very top
  Exp 12 – Alert filter tabs (Todas / Stock Bajo / Discrepancias / Transferencias)

Design constraints:
  • This widget ONLY reads data, never writes.
  • All new sections are collapsible and optional.
  • Auto-refresh (30 s) kept as fallback.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime

from sqlalchemy.orm import Session

from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from modules.dashboard.handlers import setup_dashboard_handlers
from modules.dashboard.service import DashboardService
from modules.branches.service import BranchService

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
COLOR_BLUE        = "#2196F3"
COLOR_SLATE       = "#607D8B"
COLOR_GREEN       = "#388E3C"
COLOR_AMBER       = "#F57C00"
COLOR_RED         = "#D32F2F"
COLOR_TEAL        = "#00796B"
COLOR_PURPLE      = "#6A1B9A"
COLOR_HEADER_BG   = "#1A237E"
COLOR_CARD_BG     = "#37474F"
COLOR_QUICK_BG    = "#263238"
COLOR_BANNER_WARN = "#E65100"
COLOR_BANNER_OK   = "#1B5E20"

# ---------------------------------------------------------------------------
# Helper: generic card factories
# ---------------------------------------------------------------------------

def _make_frame(bg: str, radius: int = 8) -> QFrame:
    """Return a styled QFrame with the given background colour."""
    f = QFrame()
    f.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
    f.setStyleSheet(
        f"QFrame{{background-color:{bg};border-radius:{radius}px;padding:6px;}}"
        f"QLabel{{color:white;}}"
    )
    return f


def _make_label(text: str, size: int = 12, bold: bool = False,
                align=Qt.AlignmentFlag.AlignCenter,
                wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    weight = "bold" if bold else "normal"
    lbl.setStyleSheet(f"font-size:{size}px;font-weight:{weight};")
    lbl.setAlignment(align)
    lbl.setWordWrap(wrap)
    return lbl


def _trend_html(trend: Dict[str, Any]) -> str:
    """Return a small HTML span with ↑/↓ arrow and percentage."""
    direction = trend.get("direction", "same")
    pct = trend.get("percentage", 0.0)
    if direction == "up":
        return f'<span style="color:#81C784;">↑ {abs(pct):.1f}%</span>'
    elif direction == "down":
        return f'<span style="color:#EF9A9A;">↓ {abs(pct):.1f}%</span>'
    return '<span style="color:#B0BEC5;">→ 0%</span>'


def _efficiency_color(rate: float) -> str:
    if rate >= 90:
        return COLOR_GREEN
    if rate >= 70:
        return COLOR_AMBER
    return COLOR_RED


def _sparkline(data: List[Dict[str, Any]], key: str = "count") -> str:
    """Build a simple ASCII sparkline from a list of {date, <key>} dicts."""
    bars = " ▁▂▃▄▅▆▇█"
    values = [d.get(key, 0) for d in data]
    if not values or max(values) == 0:
        return "▁" * len(values)
    mx = max(values)
    return "".join(bars[min(int(v / mx * 8), 8)] for v in values)


# ---------------------------------------------------------------------------
# Exp 10 – Matplotlib chart renderer (module-level helper)
# ---------------------------------------------------------------------------

def _render_chart_to_label(
    label: "QLabel",
    dates: List[str],
    values: List[float],
    title: str,
    color: str = "#2196F3",
    ylabel: str = "",
    width_px: int = 460,
    height_px: int = 200,
) -> None:
    """
    Render a bar chart with matplotlib (Agg backend, no Qt event loop needed),
    convert the result to a QPixmap, and display it inside *label*.

    Falls back silently to a plain text sparkline if matplotlib is not
    available or rendering fails.
    """
    try:
        import matplotlib
        # Force Agg only if no backend has been set yet (safe to call multiple times)
        if matplotlib.get_backend().lower() not in ("agg",):
            try:
                matplotlib.use("Agg")
            except Exception:
                pass
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        import io
        from PyQt6.QtGui import QPixmap

        dpi = 96
        fig_w = width_px / dpi
        fig_h = height_px / dpi

        fig = Figure(figsize=(fig_w, fig_h), dpi=dpi, facecolor="#263238")
        canvas = FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)

        # Shorten date labels to MM-DD
        short_dates = [d[-5:] for d in dates]
        x = range(len(values))

        # Bar chart for movements, line+fill for stock
        if ylabel.lower().startswith("unidad"):
            ax.plot(list(x), values, color=color, linewidth=2, marker="o", markersize=4)
            ax.fill_between(list(x), values, alpha=0.25, color=color)
        else:
            bars = ax.bar(list(x), values, color=color, width=0.6)
            # Value labels on bars (skip if too many points)
            if len(values) <= 14:
                for bar, val in zip(bars, values):
                    if val > 0:
                        ax.text(
                            bar.get_x() + bar.get_width() / 2,
                            bar.get_height() + max(values) * 0.02,
                            str(int(val)),
                            ha="center", va="bottom",
                            color="white", fontsize=7,
                        )

        # Styling — dark theme to match the app
        ax.set_facecolor("#37474F")
        ax.set_title(title, color="white", fontsize=9, pad=4)
        ax.set_ylabel(ylabel, color="#B0BEC5", fontsize=8)
        ax.tick_params(colors="#B0BEC5", labelsize=7)
        ax.set_xticks(list(x))
        ax.set_xticklabels(short_dates, rotation=45, ha="right", fontsize=7)
        for spine in ax.spines.values():
            spine.set_edgecolor("#546E7A")
        ax.yaxis.grid(True, color="#546E7A", linestyle="--", linewidth=0.5, alpha=0.7)
        ax.set_axisbelow(True)

        fig.tight_layout(pad=0.4)

        # Render to PNG bytes in memory
        buf = io.BytesIO()
        canvas.print_png(buf)
        buf.seek(0)
        png_bytes = buf.read()

        # Load into QPixmap
        pixmap = QPixmap()
        pixmap.loadFromData(png_bytes, "PNG")
        label.setPixmap(pixmap)
        label.setScaledContents(False)
        import matplotlib.pyplot as plt
        plt.close(fig)

    except Exception as exc:
        logger.warning(f"matplotlib chart rendering failed ({exc}); using sparkline")
        # Plain text fallback
        bars_txt = " ▁▂▃▄▅▆▇█"
        mx = max(values) if values and max(values) > 0 else 1
        spark = "".join(bars_txt[min(int(v / mx * 8), 8)] for v in values)
        label.setText(f"<b>{title}</b><br><code style='font-size:16px;'>{spark}</code>")
        label.setTextFormat(Qt.TextFormat.RichText)

# ---------------------------------------------------------------------------
# Widget Config Dialog  (Exp 9)
# ---------------------------------------------------------------------------

_WIDGET_LABELS: Dict[str, str] = {
    "quick_stats":      "En un Vistazo (Quick Stats)",
    "kpi":              "Indicadores KPI (ERI / ERU)",
    "stock_summary":    "Resumen de Stock",
    "movements":        "Movimientos",
    "alerts":           "Alertas Recientes",
    "transfers":        "Transferencias",
    "efficiency":       "Eficiencia Operativa",
    "ranking":          "Ranking de Sucursales",
    "charts":           "Tendencias (Gráficos)",
    "recent_movements": "Movimientos Recientes",
}


class WidgetConfigDialog(QDialog):
    """
    Dialog for choosing which dashboard widgets to display (Exp 9).
    Does NOT persist to DB on its own — the caller does that via the service.
    """

    def __init__(self, visible_keys: List[str], parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Dashboard")
        self.setMinimumWidth(340)
        self._checks: Dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(_make_label(
            "Selecciona los widgets que deseas ver:", 13, bold=True,
            align=Qt.AlignmentFlag.AlignLeft,
        ))

        from models.dashboard_widget_config import WIDGET_KEYS
        for key in WIDGET_KEYS:
            cb = QCheckBox(_WIDGET_LABELS.get(key, key))
            cb.setChecked(key in visible_keys)
            self._checks[key] = cb
            layout.addWidget(cb)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_visible_keys(self) -> List[str]:
        return [k for k, cb in self._checks.items() if cb.isChecked()]

# ---------------------------------------------------------------------------
# Main Dashboard Widget
# ---------------------------------------------------------------------------

class DashboardWidget(QWidget):
    """
    Dashboard main widget — reads-only, reactive, fully expandable.

    State tracked per instance:
        _branch_id   – currently selected branch (None = all)
        _period      – currently selected period string
        _date_from   – custom period start
        _date_to     – custom period end
        _alert_tab   – currently selected alert filter tab index
        _visible_widgets – set of widget keys currently shown
    """

    # ----------------------------------------------------------------
    # Construction
    # ----------------------------------------------------------------

    def __init__(self, db: Session, parent: QWidget = None, user_id: int = None):
        super().__init__(parent)
        self.db = db
        self.user_id = user_id  # optional; used for widget config persistence
        self.service = DashboardService(db)
        self.branch_service = BranchService(db)
        self.handlers: Any = None

        # Filter state
        self._branch_id: Optional[int] = None
        self._period: str = "this_month"
        self._date_from: Optional[datetime] = None
        self._date_to: Optional[datetime] = None
        self._alert_tab: int = 0   # 0=all 1=low_stock 2=discrepancy 3=transfers

        # Which widgets to show (Exp 9)
        self._visible_widgets: List[str] = self.service.get_visible_widgets(
            user_id or 0
        )

        self._setup_ui()

        # Event-driven reactive updates
        self.handlers = setup_dashboard_handlers(self.db)
        self.handlers.set_refresh_callback(self.load_data)
        self.handlers.set_alert_badge_callback(self._refresh_alert_badge)
        self.handlers.set_transfer_callback(self._refresh_transfers)

        self.load_data()

        # 30-second auto-refresh fallback
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.load_data)
        self._timer.start(30_000)

    # ----------------------------------------------------------------
    # UI setup
    # ----------------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(6)

        root.addLayout(self._build_header())

        # Scroll container for all sections
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setSpacing(8)

        # Urgent alert banner (always visible)
        self._urgent_banner = self._build_urgent_banner()
        self._content_layout.addWidget(self._urgent_banner)

        # Ordered sections — visibility controlled by _visible_widgets
        self._sections: Dict[str, QWidget] = {}

        self._sections["quick_stats"]      = self._build_quick_stats()
        self._sections["kpi"]              = self._build_kpi()
        self._sections["stock_summary"]    = self._build_stock_summary()
        self._sections["movements"]        = self._build_movements()
        self._sections["alerts"]           = self._build_alerts()
        self._sections["transfers"]        = self._build_transfers()
        self._sections["efficiency"]       = self._build_efficiency()
        self._sections["ranking"]          = self._build_ranking()
        self._sections["charts"]           = self._build_charts()
        self._sections["recent_movements"] = self._build_recent_movements()

        for key, widget in self._sections.items():
            self._content_layout.addWidget(widget)

        self._content_layout.addStretch()
        scroll.setWidget(content)

        # Exp 4: quick-action bar lives between header and scroll
        root.addWidget(self._build_quick_actions())

        root.addWidget(scroll)

        self._apply_visibility()

    # ----------------------------------------------------------------
    # Header  (Exp 1 branch selector, Exp 2 period selector, Exp 9 config btn)
    # ----------------------------------------------------------------

    def _build_header(self) -> QHBoxLayout:
        h = QHBoxLayout()

        title = QLabel("Dashboard — SGIMI TECNOGAS")
        title.setStyleSheet(
            f"font-size:22px;font-weight:bold;color:{COLOR_HEADER_BG};"
        )
        h.addWidget(title)
        h.addStretch()

        # --- Exp 1: branch selector ---
        h.addWidget(QLabel("Sucursal:"))
        self._branch_combo = QComboBox()
        self._branch_combo.setMinimumWidth(160)
        self._branch_combo.addItem("Todas las sucursales", None)
        try:
            for br in self.branch_service.get_all():
                self._branch_combo.addItem(br["name"], br["id"])
        except Exception:
            pass
        self._branch_combo.currentIndexChanged.connect(self._on_branch_changed)
        h.addWidget(self._branch_combo)

        # --- Exp 2: period selector ---
        h.addWidget(QLabel("Período:"))
        self._period_combo = QComboBox()
        self._period_combo.addItems([
            "Este mes", "Hoy", "Esta semana",
            "Mes anterior", "Todo", "Personalizado",
        ])
        self._period_combo.currentIndexChanged.connect(self._on_period_changed)
        h.addWidget(self._period_combo)

        # Custom date range (hidden unless "Personalizado")
        self._date_from_edit = QDateEdit(QDate.currentDate().addDays(-30))
        self._date_from_edit.setCalendarPopup(True)
        self._date_from_edit.setVisible(False)
        self._date_from_edit.dateChanged.connect(self._on_custom_date_changed)
        h.addWidget(self._date_from_edit)

        self._date_to_edit = QDateEdit(QDate.currentDate())
        self._date_to_edit.setCalendarPopup(True)
        self._date_to_edit.setVisible(False)
        self._date_to_edit.dateChanged.connect(self._on_custom_date_changed)
        h.addWidget(self._date_to_edit)

        # --- Exp 9: config button ---
        cfg_btn = QPushButton("⚙ Configurar")
        cfg_btn.setToolTip("Mostrar u ocultar secciones del dashboard")
        cfg_btn.clicked.connect(self._open_config_dialog)
        h.addWidget(cfg_btn)

        # Refresh
        refresh_btn = QPushButton("↺ Actualizar")
        refresh_btn.clicked.connect(self.load_data)
        h.addWidget(refresh_btn)

        return h

    # ----------------------------------------------------------------
    # Urgent alert banner  (Exp 8)
    # ----------------------------------------------------------------

    def _build_urgent_banner(self) -> QFrame:
        frame = _make_frame(COLOR_BANNER_OK, radius=6)
        layout = QHBoxLayout(frame)
        self._banner_label = QLabel("✓  Sin alertas urgentes")
        self._banner_label.setStyleSheet("font-size:13px;font-weight:bold;color:white;")
        layout.addWidget(self._banner_label)
        frame.setVisible(True)
        return frame

    def _refresh_urgent_banner(self) -> None:
        try:
            alerts = self.service.get_urgent_alerts(self._branch_id)
            if alerts:
                n = len(alerts)
                self._urgent_banner.setStyleSheet(
                    f"QFrame{{background-color:{COLOR_BANNER_WARN};border-radius:6px;padding:6px;}}"
                    f"QLabel{{color:white;}}"
                )
                first = alerts[0]["message"]
                self._banner_label.setText(
                    f"⚠  {n} alerta(s) urgente(s)  —  {first}"
                )
            else:
                self._urgent_banner.setStyleSheet(
                    f"QFrame{{background-color:{COLOR_BANNER_OK};border-radius:6px;padding:6px;}}"
                    f"QLabel{{color:white;}}"
                )
                self._banner_label.setText("✓  Sin alertas urgentes")
        except Exception as e:
            logger.error(f"Error refreshing urgent banner: {e}")

    # ----------------------------------------------------------------
    # Exp 11 – Quick stats
    # ----------------------------------------------------------------

    def _build_quick_stats(self) -> QGroupBox:
        group = QGroupBox("En un Vistazo")
        layout = QHBoxLayout(group)

        self._qs_products  = self._make_metric_card("Productos únicos", "0", COLOR_TEAL)
        self._qs_stock     = self._make_metric_card("Stock total", "0", COLOR_BLUE)
        self._qs_value     = self._make_metric_card("Valor inventario", "$0", COLOR_PURPLE)
        self._qs_today     = self._make_metric_card("Movimientos hoy", "0", COLOR_SLATE)
        self._qs_pending   = self._make_metric_card("Pendientes", "0", COLOR_AMBER)

        for card in (self._qs_products, self._qs_stock, self._qs_value,
                     self._qs_today, self._qs_pending):
            layout.addWidget(card)

        return group

    def _refresh_quick_stats(self) -> None:
        try:
            qs = self.service.get_quick_stats(self._branch_id)
            self._qs_products.value_label.setText(str(qs["unique_products"]))
            self._qs_stock.value_label.setText(str(qs["total_stock"]))
            val = qs.get("inventory_value", 0.0)
            self._qs_value.value_label.setText(
                f"${val:,.0f}" if val else "N/D"
            )
            self._qs_today.value_label.setText(str(qs["movements_today"]))
            self._qs_pending.value_label.setText(str(qs["pending_movements"]))
        except Exception as e:
            logger.error(f"Error in quick stats: {e}")

    # ----------------------------------------------------------------
    # KPI section  (Exp 3 trend indicators added)
    # ----------------------------------------------------------------

    def _build_kpi(self) -> QGroupBox:
        group = QGroupBox("Indicadores Clave de Rendimiento (KPIs)")
        layout = QGridLayout(group)

        self._eri_card      = self._make_kpi_card("ERI",  "0%", "Exactitud de Registros de Inventario")
        self._eru_card      = self._make_kpi_card("ERU",  "0%", "Exactitud de Registros de Ubicación")
        self._products_card = self._make_kpi_card("Productos", "0", "Total de productos")
        self._branches_card = self._make_kpi_card("Sucursales", "0", "Total de sucursales")

        layout.addWidget(self._eri_card,      0, 0)
        layout.addWidget(self._eru_card,      0, 1)
        layout.addWidget(self._products_card, 0, 2)
        layout.addWidget(self._branches_card, 0, 3)

        return group

    def _refresh_kpi(self, metrics: Dict) -> None:
        self._eri_card.value_label.setText(f"{metrics['kpi_eri']}%")
        self._eru_card.value_label.setText(f"{metrics['kpi_eru']}%")
        self._products_card.value_label.setText(str(metrics["total_products"]))
        self._branches_card.value_label.setText(str(metrics["total_branches"]))

    # ----------------------------------------------------------------
    # Stock summary  (Exp 3 trend indicators)
    # ----------------------------------------------------------------

    def _build_stock_summary(self) -> QGroupBox:
        group = QGroupBox("Resumen de Stock")
        layout = QGridLayout(group)

        self._physical_card     = self._make_metric_card("Stock Físico Total",  "0", COLOR_SLATE)
        self._digital_card      = self._make_metric_card("Stock Digital Total", "0", COLOR_SLATE)
        self._discrepancy_card  = self._make_metric_card("Discrepancias",       "0", COLOR_AMBER)
        self._low_stock_card    = self._make_metric_card("Stock Bajo",          "0", COLOR_RED)

        layout.addWidget(self._physical_card,    0, 0)
        layout.addWidget(self._digital_card,     0, 1)
        layout.addWidget(self._discrepancy_card, 0, 2)
        layout.addWidget(self._low_stock_card,   0, 3)

        return group

    def _refresh_stock_summary(self, metrics: Dict, trends: Dict) -> None:
        self._physical_card.value_label.setText(str(metrics["total_physical_stock"]))
        self._digital_card.value_label.setText(str(metrics["total_digital_stock"]))
        self._discrepancy_card.value_label.setText(str(metrics["discrepancy_count"]))
        self._low_stock_card.value_label.setText(str(metrics["low_stock_count"]))
        # Trend labels
        if hasattr(self._discrepancy_card, "trend_label") and trends:
            t = trends.get("discrepancies", {}).get("trend", {})
            self._discrepancy_card.trend_label.setText(_trend_html(t))
            self._discrepancy_card.trend_label.setTextFormat(
                Qt.TextFormat.RichText
            )
        if hasattr(self._low_stock_card, "trend_label") and trends:
            t = trends.get("low_stock", {}).get("trend", {})
            self._low_stock_card.trend_label.setText(_trend_html(t))
            self._low_stock_card.trend_label.setTextFormat(
                Qt.TextFormat.RichText
            )

    # ----------------------------------------------------------------
    # Movements section  (Exp 3 trend indicators)
    # ----------------------------------------------------------------

    def _build_movements(self) -> QGroupBox:
        group = QGroupBox("Movimientos")
        layout = QGridLayout(group)

        self._pending_card   = self._make_metric_card("Pendientes", "0", COLOR_AMBER)
        self._entradas_card  = self._make_metric_card("Entradas",   "0", COLOR_GREEN)
        self._salidas_card   = self._make_metric_card("Salidas",    "0", COLOR_RED)
        self._ajustes_card   = self._make_metric_card("Ajustes",    "0", COLOR_SLATE)
        self._transfer_count_card = self._make_metric_card("Transferencias", "0", COLOR_TEAL)

        layout.addWidget(self._pending_card,        0, 0)
        layout.addWidget(self._entradas_card,        0, 1)
        layout.addWidget(self._salidas_card,         0, 2)
        layout.addWidget(self._ajustes_card,         0, 3)
        layout.addWidget(self._transfer_count_card,  0, 4)

        return group

    def _refresh_movements(self, metrics: Dict, trends: Dict) -> None:
        self._pending_card.value_label.setText(str(metrics["pending_movements"]))
        stats = metrics.get("movement_stats", {})
        self._entradas_card.value_label.setText(
            str(stats.get("entrada", {}).get("count", 0))
        )
        self._salidas_card.value_label.setText(
            str(stats.get("salida", {}).get("count", 0))
        )
        self._ajustes_card.value_label.setText(
            str(stats.get("ajuste", {}).get("count", 0))
        )
        self._transfer_count_card.value_label.setText(
            str(stats.get("transferencia", {}).get("count", 0))
        )
        # Trend labels
        for card, key in (
            (self._entradas_card, "entradas"),
            (self._salidas_card,  "salidas"),
        ):
            if hasattr(card, "trend_label") and trends:
                t = trends.get(key, {}).get("trend", {})
                card.trend_label.setText(_trend_html(t))
                card.trend_label.setTextFormat(Qt.TextFormat.RichText)

    # ----------------------------------------------------------------
    # Exp 4 – Quick action buttons
    # ----------------------------------------------------------------

    def _build_quick_actions(self) -> QGroupBox:
        group = QGroupBox("Acciones Rápidas")
        layout = QHBoxLayout(group)

        actions = [
            ("➕ Nuevo Movimiento",          self._action_new_movement),
            ("📦 Ver Inventario",             self._action_view_inventory),
            ("🔄 Transferencias Pendientes",  self._action_pending_transfers),
            ("⚠ Stock Bajo",                 self._action_low_stock),
        ]
        for label, slot in actions:
            btn = QPushButton(label)
            btn.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            btn.setStyleSheet(
                f"QPushButton{{background-color:{COLOR_TEAL};color:white;"
                f"border-radius:6px;padding:8px;font-size:13px;}}"
                f"QPushButton:hover{{background-color:#00897B;}}"
            )
            btn.clicked.connect(slot)
            layout.addWidget(btn)

        return group

    # Action stubs — emit signals or call parent navigation if available
    def _action_new_movement(self) -> None:
        self._navigate("movements", action="new")

    def _action_view_inventory(self) -> None:
        self._navigate("inventory")

    def _action_pending_transfers(self) -> None:
        self._navigate("movements", filter="transferencia_pendiente")

    def _action_low_stock(self) -> None:
        self._navigate("inventory", filter="low_stock")

    def _navigate(self, module: str, **kwargs) -> None:
        """
        Request navigation to another module.
        Walks up the parent chain looking for a navigate() method
        (as implemented by the main window / tab manager).
        """
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "navigate"):
                parent.navigate(module, **kwargs)
                return
            parent = parent.parent()
        logger.debug(f"Navigation requested: module={module}, kwargs={kwargs}")

    # ----------------------------------------------------------------
    # Exp 12 – Alerts with filter tabs
    # ----------------------------------------------------------------

    def _build_alerts(self) -> QGroupBox:
        # Badge label is embedded in the group title dynamically
        self._alerts_group = QGroupBox("Alertas Recientes")
        outer = QVBoxLayout(self._alerts_group)

        # Tab bar: Todas / Stock Bajo / Discrepancias / Transferencias
        self._alert_tabs = QTabWidget()
        self._alert_tabs.setTabPosition(QTabWidget.TabPosition.North)

        self._tab_all          = QLabel()
        self._tab_low_stock    = QLabel()
        self._tab_discrepancy  = QLabel()
        self._tab_transfer_al  = QLabel()

        for label_widget in (
            self._tab_all, self._tab_low_stock,
            self._tab_discrepancy, self._tab_transfer_al,
        ):
            label_widget.setWordWrap(True)
            label_widget.setTextFormat(Qt.TextFormat.RichText)
            label_widget.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            label_widget.setContentsMargins(6, 6, 6, 6)

        self._alert_tabs.addTab(self._tab_all,         "Todas")
        self._alert_tabs.addTab(self._tab_low_stock,   "Stock Bajo")
        self._alert_tabs.addTab(self._tab_discrepancy, "Discrepancias")
        self._alert_tabs.addTab(self._tab_transfer_al, "Transferencias")
        self._alert_tabs.currentChanged.connect(self._on_alert_tab_changed)

        outer.addWidget(self._alert_tabs)
        return self._alerts_group

    def _refresh_alerts(self) -> None:
        try:
            all_alerts = self.service.get_all_alerts_with_type(self._branch_id)
            low  = all_alerts.get("low_stock", [])
            disc = all_alerts.get("discrepancy", [])
            tran = all_alerts.get("pending_transfer", [])
            everything = low + disc + tran

            # Update tab labels with counts
            self._alert_tabs.setTabText(0, f"Todas ({len(everything)})")
            self._alert_tabs.setTabText(1, f"Stock Bajo ({len(low)})")
            self._alert_tabs.setTabText(2, f"Discrepancias ({len(disc)})")
            self._alert_tabs.setTabText(3, f"Transferencias ({len(tran)})")

            # Update group title badge
            total = len(everything)
            title = f"Alertas Recientes  [{total}]" if total else "Alertas Recientes"
            self._alerts_group.setTitle(title)

            # Populate tab content
            self._tab_all.setText(self._format_all_alerts(everything))
            self._tab_low_stock.setText(self._format_low_stock_alerts(low))
            self._tab_discrepancy.setText(self._format_discrepancy_alerts(disc))
            self._tab_transfer_al.setText(self._format_transfer_alerts(tran))

        except Exception as e:
            logger.error(f"Error refreshing alerts: {e}")

    def _refresh_alert_badge(self) -> None:
        """Lightweight badge-only refresh (called from handlers)."""
        self._refresh_alerts()

    @staticmethod
    def _format_low_stock_alerts(items: List[Dict]) -> str:
        if not items:
            return "<i>Sin alertas de stock bajo.</i>"
        lines = ["<b>Stock Bajo:</b>"]
        for it in items[:10]:
            lines.append(
                f"• {it['product']} ({it['branch']}): "
                f"{it['current_stock']} / mín {it['min_stock']}"
            )
        return "<br>".join(lines)

    @staticmethod
    def _format_discrepancy_alerts(items: List[Dict]) -> str:
        if not items:
            return "<i>Sin discrepancias.</i>"
        lines = ["<b>Discrepancias:</b>"]
        for it in items[:10]:
            lines.append(
                f"• {it['product']} ({it['branch']}): "
                f"Fís={it['physical_stock']} Dig={it['digital_stock']} "
                f"Dif={it['difference']}"
            )
        return "<br>".join(lines)

    @staticmethod
    def _format_transfer_alerts(items: List[Dict]) -> str:
        if not items:
            return "<i>Sin transferencias pendientes.</i>"
        lines = ["<b>Transferencias pendientes:</b>"]
        for it in items[:10]:
            lines.append(
                f"• {it['product']} — {it['quantity']} u. "
                f"(hace {it['hours_ago']} h)"
            )
        return "<br>".join(lines)

    @staticmethod
    def _format_all_alerts(items: List[Dict]) -> str:
        if not items:
            return "<i>No hay alertas activas.</i>"
        TYPE_ICON = {
            "low_stock":        "⚠",
            "discrepancy":      "⚡",
            "pending_transfer": "🔄",
        }
        lines = []
        for it in items[:15]:
            icon = TYPE_ICON.get(it.get("type", ""), "•")
            lines.append(f"{icon} {it.get('product', '')} ({it.get('branch', '')})")
        return "<br>".join(lines)

    # ----------------------------------------------------------------
    # Exp 6 – Transfers widget
    # ----------------------------------------------------------------

    def _build_transfers(self) -> QGroupBox:
        group = QGroupBox("Transferencias")
        layout = QVBoxLayout(group)

        # Summary row
        summary_layout = QHBoxLayout()
        self._xfer_summary_label = QLabel("Cargando...")
        summary_layout.addWidget(self._xfer_summary_label)
        layout.addLayout(summary_layout)

        # Two-column pending lists
        cols = QHBoxLayout()

        left_group = QGroupBox("Por Enviar")
        self._xfer_sent_label = QLabel()
        self._xfer_sent_label.setWordWrap(True)
        self._xfer_sent_label.setTextFormat(Qt.TextFormat.RichText)
        self._xfer_sent_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        left_layout = QVBoxLayout(left_group)
        left_layout.addWidget(self._xfer_sent_label)
        cols.addWidget(left_group)

        right_group = QGroupBox("Por Recibir")
        self._xfer_recv_label = QLabel()
        self._xfer_recv_label.setWordWrap(True)
        self._xfer_recv_label.setTextFormat(Qt.TextFormat.RichText)
        self._xfer_recv_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        right_layout = QVBoxLayout(right_group)
        right_layout.addWidget(self._xfer_recv_label)
        cols.addWidget(right_group)

        layout.addLayout(cols)
        return group

    def _refresh_transfers(self) -> None:
        try:
            data    = self.service.get_pending_transfers(self._branch_id)
            summary = self.service.get_transfer_summary(self._branch_id)

            total_p = summary.get("total_transfers", 0)
            total_q = summary.get("total_quantity", 0)
            days    = summary.get("days", 30)
            self._xfer_summary_label.setText(
                f"Últimos {days} días: <b>{total_p}</b> transferencias completadas  |  "
                f"<b>{total_q}</b> unidades"
            )
            self._xfer_summary_label.setTextFormat(Qt.TextFormat.RichText)

            sent = data.get("sent", [])
            recv = data.get("received", [])

            def _fmt(items: List[Dict], direction: str) -> str:
                if not items:
                    return "<i>Sin pendientes.</i>"
                lines = []
                for it in items[:8]:
                    other = it.get(
                        "destination_branch" if direction == "sent" else "origin_branch", ""
                    )
                    pri = it.get("priority", "normal")
                    icon = "🔴" if pri == "urgente" else "🟡" if pri == "alta" else "•"
                    lines.append(
                        f"{icon} <b>{it['product']}</b> — {it['quantity']} u.  "
                        f"→ {other}  <i>({it['hours_ago']} h)</i>"
                    )
                return "<br>".join(lines)

            self._xfer_sent_label.setText(_fmt(sent, "sent"))
            self._xfer_recv_label.setText(_fmt(recv, "received"))

        except Exception as e:
            logger.error(f"Error refreshing transfers: {e}")

    # ----------------------------------------------------------------
    # Exp 7 – Efficiency widget
    # ----------------------------------------------------------------

    def _build_efficiency(self) -> QGroupBox:
        group = QGroupBox("Eficiencia Operativa")
        layout = QGridLayout(group)

        self._eff_total_card      = self._make_metric_card("Total movimientos",    "0",    COLOR_SLATE)
        self._eff_validation_card = self._make_metric_card("Tasa validación",      "0%",   COLOR_GREEN)
        self._eff_rejection_card  = self._make_metric_card("Tasa rechazo",         "0%",   COLOR_RED)
        self._eff_avg_hours_card  = self._make_metric_card("Tiempo prom. valid.",  "0 h",  COLOR_BLUE)

        layout.addWidget(self._eff_total_card,      0, 0)
        layout.addWidget(self._eff_validation_card, 0, 1)
        layout.addWidget(self._eff_rejection_card,  0, 2)
        layout.addWidget(self._eff_avg_hours_card,  0, 3)

        return group

    def _refresh_efficiency(self) -> None:
        try:
            eff = self.service.get_efficiency_metrics(self._branch_id)
            self._eff_total_card.value_label.setText(str(eff["total_movements"]))

            val_rate = eff["validation_rate"]
            rej_rate = eff["rejection_rate"]

            self._eff_validation_card.value_label.setText(f"{val_rate:.1f}%")
            self._eff_validation_card.setStyleSheet(
                f"QFrame{{background-color:{_efficiency_color(val_rate)};"
                f"border-radius:8px;padding:8px;}}QLabel{{color:white;}}"
            )

            self._eff_rejection_card.value_label.setText(f"{rej_rate:.1f}%")
            reject_color = COLOR_GREEN if rej_rate < 10 else (COLOR_AMBER if rej_rate < 25 else COLOR_RED)
            self._eff_rejection_card.setStyleSheet(
                f"QFrame{{background-color:{reject_color};"
                f"border-radius:8px;padding:8px;}}QLabel{{color:white;}}"
            )

            self._eff_avg_hours_card.value_label.setText(f"{eff['avg_validation_hours']} h")

        except Exception as e:
            logger.error(f"Error refreshing efficiency: {e}")

    # ----------------------------------------------------------------
    # Exp 5 – Branch ranking widget
    # ----------------------------------------------------------------

    def _build_ranking(self) -> QGroupBox:
        group = QGroupBox("Ranking de Sucursales")
        layout = QVBoxLayout(group)

        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Métrica:"))
        self._ranking_metric_combo = QComboBox()
        for label, key in [
            ("Stock Total",   "stock_total"),
            ("Discrepancias", "discrepancies"),
            ("Stock Bajo",    "low_stock"),
            ("Movimientos",   "movements"),
            ("Eficiencia",    "efficiency"),
        ]:
            self._ranking_metric_combo.addItem(label, key)

        self._ranking_metric_combo.currentIndexChanged.connect(self._refresh_ranking)
        ctrl.addWidget(self._ranking_metric_combo)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        self._ranking_label = QLabel("Cargando...")
        self._ranking_label.setWordWrap(True)
        self._ranking_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self._ranking_label)

        return group

    def _refresh_ranking(self) -> None:
        try:
            metric = self._ranking_metric_combo.currentData() or "stock_total"
            data = self.service.get_branch_ranking(
                metric=metric,
                limit=5,
                period=self._period,
                date_from=self._date_from,
                date_to=self._date_to,
            )
            if not data:
                self._ranking_label.setText("<i>Sin datos.</i>")
                return

            MEDALS = ["🥇", "🥈", "🥉", "4.", "5."]
            unit   = "%" if metric == "efficiency" else ""
            lines  = [f"<b>Top {len(data)} — {self._ranking_metric_combo.currentText()}</b>"]
            max_v  = max(r["value"] for r in data) or 1

            for i, row in enumerate(data):
                bar_len = int(row["value"] / max_v * 20)
                bar     = "█" * bar_len + "░" * (20 - bar_len)
                lines.append(
                    f"{MEDALS[i]}  {row['branch_name']:<20} "
                    f"<code>{bar}</code>  {row['value']}{unit}"
                )

            self._ranking_label.setText("<br>".join(lines))
        except Exception as e:
            logger.error(f"Error refreshing ranking: {e}")

    # ----------------------------------------------------------------
    # Exp 10 – Charts (matplotlib embedded via PNG → QPixmap)
    # ----------------------------------------------------------------

    def _build_charts(self) -> QGroupBox:
        """
        Build the charts section.  Two QLabels hold the rendered PNG images.
        A days selector (7 / 14 / 30) sits in the header row.
        Falls back to a text sparkline when matplotlib is unavailable.
        """
        group = QGroupBox("Tendencias")
        outer = QVBoxLayout(group)

        # Controls row
        ctrl = QHBoxLayout()
        ctrl.addWidget(QLabel("Mostrar últimos:"))
        self._chart_days_combo = QComboBox()
        for label, val in [("7 días", 7), ("14 días", 14), ("30 días", 30)]:
            self._chart_days_combo.addItem(label, val)
        self._chart_days_combo.currentIndexChanged.connect(self._refresh_charts)
        ctrl.addWidget(self._chart_days_combo)
        ctrl.addStretch()
        outer.addLayout(ctrl)

        # Two image labels side by side
        row = QHBoxLayout()

        mv_frame = QGroupBox("Movimientos por día")
        mv_layout = QVBoxLayout(mv_frame)
        self._chart_mv_label = QLabel()
        self._chart_mv_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._chart_mv_label.setMinimumHeight(200)
        mv_layout.addWidget(self._chart_mv_label)
        row.addWidget(mv_frame)

        st_frame = QGroupBox("Stock digital")
        st_layout = QVBoxLayout(st_frame)
        self._chart_st_label = QLabel()
        self._chart_st_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._chart_st_label.setMinimumHeight(200)
        st_layout.addWidget(self._chart_st_label)
        row.addWidget(st_frame)

        outer.addLayout(row)
        return group

    def _refresh_charts(self) -> None:
        """Render charts with matplotlib (Agg) → PNG bytes → QPixmap → QLabel."""
        days = self._chart_days_combo.currentData() or 7
        try:
            mv_data = self.service.get_movement_trend(self._branch_id, days=days)
            st_data = self.service.get_stock_trend(self._branch_id, days=days)
            _render_chart_to_label(
                label=self._chart_mv_label,
                dates=[d["date"] for d in mv_data],
                values=[d["count"] for d in mv_data],
                title="Movimientos por día",
                color="#2196F3",
                ylabel="Movimientos",
            )
            _render_chart_to_label(
                label=self._chart_st_label,
                dates=[d["date"] for d in st_data],
                values=[d["stock"] for d in st_data],
                title="Stock digital total",
                color="#00796B",
                ylabel="Unidades",
            )
        except Exception as e:
            logger.error(f"Error refreshing charts: {e}")
            # Graceful fallback to sparklines
            mv_spark = _sparkline(
                self.service.get_movement_trend(self._branch_id, days=days), "count"
            ) if self.service else "—"
            self._chart_mv_label.setText(
                f"<b>Movimientos:</b> <code>{mv_spark}</code>"
            )
            self._chart_mv_label.setTextFormat(Qt.TextFormat.RichText)

    # ----------------------------------------------------------------
    # Recent movements (Exp 4 quick actions embedded as links)
    # ----------------------------------------------------------------

    def _build_recent_movements(self) -> QGroupBox:
        group = QGroupBox("Movimientos Recientes")
        layout = QVBoxLayout(group)
        self._recent_label = QLabel("Cargando...")
        self._recent_label.setWordWrap(True)
        self._recent_label.setTextFormat(Qt.TextFormat.RichText)
        self._recent_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._recent_label)
        return group

    def _refresh_recent_movements(self) -> None:
        try:
            movements = self.service.get_recent_movements(
                limit=10, branch_id=self._branch_id
            )
            if not movements:
                self._recent_label.setText("Sin movimientos recientes.")
                return

            rows = [
                "<table style='width:100%;border-collapse:collapse;'>"
                "<tr style='background:#37474F;color:white;'>"
                "<th style='padding:4px;'>ID</th>"
                "<th>Tipo</th><th>Producto</th>"
                "<th>Cant.</th><th>Estado</th><th>Fecha</th>"
                "</tr>"
            ]
            STATE_COLOR = {
                "validado":  "#388E3C",
                "rechazado": "#D32F2F",
                "pendiente": "#F57C00",
            }
            for m in movements:
                color = STATE_COLOR.get(m["state"], "#607D8B")
                date  = (m["created_at"] or "")[:16]
                rows.append(
                    f"<tr>"
                    f"<td style='padding:3px;text-align:center;'>{m['id']}</td>"
                    f"<td style='text-align:center;'>{m['type']}</td>"
                    f"<td>{m['product']}</td>"
                    f"<td style='text-align:center;'>{m['quantity']}</td>"
                    f"<td style='text-align:center;color:{color};font-weight:bold;'>{m['state']}</td>"
                    f"<td style='text-align:center;'>{date}</td>"
                    f"</tr>"
                )
            rows.append("</table>")
            self._recent_label.setText("".join(rows))
        except Exception as e:
            logger.error(f"Error loading recent movements: {e}")

    # ----------------------------------------------------------------
    # Card factory methods
    # ----------------------------------------------------------------

    def _make_kpi_card(self, title: str, value: str, description: str) -> QFrame:
        card = _make_frame(COLOR_BLUE, radius=10)
        layout = QVBoxLayout(card)

        layout.addWidget(_make_label(title, 14, bold=True))
        val_lbl = _make_label(value, 32, bold=True)
        layout.addWidget(val_lbl)
        layout.addWidget(_make_label(description, 11, wrap=True))

        card.value_label = val_lbl
        return card

    def _make_metric_card(
        self, title: str, value: str, color: str = COLOR_SLATE
    ) -> QFrame:
        """Metric card with optional trend label (Exp 3)."""
        card = _make_frame(color, radius=8)
        layout = QVBoxLayout(card)

        layout.addWidget(_make_label(title, 12))
        val_lbl = _make_label(value, 24, bold=True)
        layout.addWidget(val_lbl)

        # Exp 3: trend label (starts empty)
        trend_lbl = QLabel("")
        trend_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        trend_lbl.setTextFormat(Qt.TextFormat.RichText)
        trend_lbl.setStyleSheet("font-size:11px;")
        layout.addWidget(trend_lbl)

        card.value_label  = val_lbl
        card.trend_label  = trend_lbl
        return card

    # ----------------------------------------------------------------
    # Exp 9 – Widget visibility
    # ----------------------------------------------------------------

    def _apply_visibility(self) -> None:
        """Show or hide each section based on _visible_widgets."""
        for key, widget in self._sections.items():
            widget.setVisible(key in self._visible_widgets)

    def _open_config_dialog(self) -> None:
        """Open the widget configuration dialog (Exp 9)."""
        dlg = WidgetConfigDialog(self._visible_widgets, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_visible = dlg.get_visible_keys()
            self._visible_widgets = new_visible
            self._apply_visibility()

            # Persist if we have a user_id
            if self.user_id:
                from models.dashboard_widget_config import WIDGET_KEYS
                for pos, key in enumerate(WIDGET_KEYS):
                    self.service.save_widget_config(
                        user_id=self.user_id,
                        widget_key=key,
                        position=pos,
                        is_visible=(key in new_visible),
                    )

    # ----------------------------------------------------------------
    # Exp 1 / 2 – Filter slot callbacks
    # ----------------------------------------------------------------

    _PERIOD_MAP = {
        "Este mes":      "this_month",
        "Hoy":           "today",
        "Esta semana":   "this_week",
        "Mes anterior":  "last_month",
        "Todo":          "all",
        "Personalizado": "custom",
    }

    def _on_branch_changed(self, _index: int) -> None:
        self._branch_id = self._branch_combo.currentData()
        self.load_data()

    def _on_period_changed(self, _index: int) -> None:
        label = self._period_combo.currentText()
        self._period = self._PERIOD_MAP.get(label, "this_month")
        is_custom = self._period == "custom"
        self._date_from_edit.setVisible(is_custom)
        self._date_to_edit.setVisible(is_custom)
        if not is_custom:
            self.load_data()

    def _on_custom_date_changed(self) -> None:
        """Called when either custom date picker changes."""
        qd_from = self._date_from_edit.date()
        qd_to   = self._date_to_edit.date()
        self._date_from = datetime(qd_from.year(), qd_from.month(), qd_from.day())
        self._date_to   = datetime(qd_to.year(),   qd_to.month(),   qd_to.day(),
                                   23, 59, 59)
        self.load_data()

    def _on_alert_tab_changed(self, index: int) -> None:
        self._alert_tab = index

    # ----------------------------------------------------------------
    # Master load_data  (orchestrates all section refreshes)
    # ----------------------------------------------------------------

    def load_data(self) -> None:
        """Refresh all visible dashboard sections from the service layer."""
        try:
            # Always refresh banner and quick stats regardless of visibility
            self._refresh_urgent_banner()

            metrics = self.service.get_dashboard_metrics(self._branch_id)

            # Attempt to get trend comparison; gracefully degrade on error
            try:
                trends = self.service.get_comparison_metrics(
                    branch_id=self._branch_id,
                    period=self._period,
                    date_from=self._date_from,
                    date_to=self._date_to,
                )
            except Exception:
                trends = {}

            # Section refreshes — only run if widget is visible
            if self._sections["quick_stats"].isVisible():
                self._refresh_quick_stats()

            if self._sections["kpi"].isVisible():
                self._refresh_kpi(metrics)

            if self._sections["stock_summary"].isVisible():
                self._refresh_stock_summary(metrics, trends)

            if self._sections["movements"].isVisible():
                self._refresh_movements(metrics, trends)

            if self._sections["alerts"].isVisible():
                self._refresh_alerts()

            if self._sections["transfers"].isVisible():
                self._refresh_transfers()

            if self._sections["efficiency"].isVisible():
                self._refresh_efficiency()

            if self._sections["ranking"].isVisible():
                self._refresh_ranking()

            if self._sections["charts"].isVisible():
                self._refresh_charts()

            if self._sections["recent_movements"].isVisible():
                self._refresh_recent_movements()

        except Exception as e:
            logger.error(f"Error in load_data: {e}", exc_info=True)

    # ----------------------------------------------------------------
    # Cleanup
    # ----------------------------------------------------------------

    def cleanup(self) -> None:
        """Stop timer and unregister event handlers before widget is destroyed."""
        self._timer.stop()
        if self.handlers:
            self.handlers.unregister_handlers()
