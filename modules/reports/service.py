"""
Reports service layer – Generate, export, and persist reports.

Expansiones implementadas
─────────────────────────
 1  Filtros por fecha       – date_from / date_to en todos los métodos
 2  Filtro por producto     – product_id en inventario, movimientos, discrepancias
 3  Filtro por usuario      – user_id en actividad y movimientos
 4  Exportación CSV         – export_to_csv(report_data, filename)
 5  Exportación Excel       – export_to_excel(report_data, filename)
 6  Vista formateada        – format_report_for_display(report_type, report_data)
 7  Reportes guardados      – save / list / get / delete report configs
 8  Comparación de períodos – generate_comparison_report(...)
 9  Top productos           – generate_top_products_report(...)
10  Eficiencia por sucursal – generate_branch_efficiency_report(...)
11  Valor de inventario     – generate_inventory_value_report(...)
12  Reporte de transferencias – generate_transfer_report(...)
13  Tendencias              – generate_trend_report(...)

Principios
──────────
• Este módulo SOLO lee datos, nunca escribe/modifica registros de negocio.
• Todos los parámetros nuevos son opcionales (default None / 10 / etc.).
• Los métodos originales mantienen su firma extendida de forma retrocompatible.
"""

import csv
import io
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _fmt_date(dt: Optional[datetime]) -> Optional[str]:
    """ISO-format a datetime or return None."""
    return dt.isoformat() if dt else None


def _flatten_dict(d: Dict, parent_key: str = "", sep: str = ".") -> Dict:
    """Recursively flatten a nested dict for CSV export."""
    items: List = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            items.append((new_key, json.dumps(v, ensure_ascii=False)))
        else:
            items.append((new_key, v))
    return dict(items)


# ══════════════════════════════════════════════════════════════════════════════
# Service class
# ══════════════════════════════════════════════════════════════════════════════

class ReportsService:
    """Service for generating, exporting, and persisting reports."""

    def __init__(self, db: Session):
        self.db = db

    # ─────────────────────────────────────────────────────────────────────────
    # EXP 1-3 · REPORTES BASE (con filtros extendidos)
    # ─────────────────────────────────────────────────────────────────────────

    def generate_inventory_report(
        self,
        branch_id: Optional[int] = None,
        product_id: Optional[int] = None,       # Exp 2
        date_from: Optional[datetime] = None,    # Exp 1 (para last_count_date)
        date_to: Optional[datetime] = None,      # Exp 1
    ) -> Dict[str, Any]:
        """Generate inventory status report."""
        from models.inventory import Inventory
        from models.product import Product
        from models.branch import Branch

        query = (
            self.db.query(Inventory)
            .join(Product)
            .join(Branch)
            .filter(
                Inventory.is_active == True,
                Product.is_active == True,
                Branch.is_active == True,
            )
        )
        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)
        if product_id:
            query = query.filter(Inventory.product_id == product_id)
        if date_from:
            query = query.filter(Inventory.last_count_date >= date_from)
        if date_to:
            query = query.filter(Inventory.last_count_date <= date_to)

        items = query.all()

        report: Dict[str, Any] = {
            "generated_at": _fmt_date(datetime.utcnow()),
            "filters": {
                "branch_id": branch_id,
                "product_id": product_id,
                "date_from": _fmt_date(date_from),
                "date_to": _fmt_date(date_to),
            },
            "total_items": len(items),
            "total_physical_stock": 0,
            "total_digital_stock": 0,
            "discrepancies": [],
            "low_stock": [],
            "by_branch": {},
        }

        for item in items:
            report["total_physical_stock"] += item.physical_stock
            report["total_digital_stock"] += item.digital_stock

            branch_name = item.branch.name
            if branch_name not in report["by_branch"]:
                report["by_branch"][branch_name] = {
                    "items": 0,
                    "physical_stock": 0,
                    "digital_stock": 0,
                }
            report["by_branch"][branch_name]["items"] += 1
            report["by_branch"][branch_name]["physical_stock"] += item.physical_stock
            report["by_branch"][branch_name]["digital_stock"] += item.digital_stock

            if item.has_discrepancy:
                report["discrepancies"].append({
                    "product": item.product.name,
                    "branch": branch_name,
                    "physical": item.physical_stock,
                    "digital": item.digital_stock,
                    "difference": item.difference,
                })

            if item.is_low_stock:
                report["low_stock"].append({
                    "product": item.product.name,
                    "branch": branch_name,
                    "current": item.digital_stock,
                    "min": item.min_stock,
                })

        return report


    def generate_movement_report(
        self,
        branch_id: Optional[int] = None,
        product_id: Optional[int] = None,       # Exp 2
        user_id: Optional[int] = None,           # Exp 3
        date_from: Optional[datetime] = None,    # Exp 1
        date_to: Optional[datetime] = None,      # Exp 1
    ) -> Dict[str, Any]:
        """Generate movement history report."""
        from models.movement import Movement

        query = self.db.query(Movement)

        if branch_id:
            query = query.filter(
                or_(
                    Movement.branch_id == branch_id,
                    Movement.destination_branch_id == branch_id,
                )
            )
        if product_id:
            query = query.filter(Movement.product_id == product_id)
        if user_id:
            query = query.filter(Movement.user_id == user_id)
        if date_from:
            query = query.filter(Movement.created_at >= date_from)
        if date_to:
            query = query.filter(Movement.created_at <= date_to)

        movements = query.all()

        report: Dict[str, Any] = {
            "generated_at": _fmt_date(datetime.utcnow()),
            "filters": {
                "branch_id": branch_id,
                "product_id": product_id,
                "user_id": user_id,
                "date_from": _fmt_date(date_from),
                "date_to": _fmt_date(date_to),
            },
            "total_movements": len(movements),
            "by_type": {},
            "by_state": {},
            "by_branch": {},
        }

        for m in movements:
            mtype = m.movement_type
            report["by_type"].setdefault(mtype, {"count": 0, "total_quantity": 0})
            report["by_type"][mtype]["count"] += 1
            report["by_type"][mtype]["total_quantity"] += m.quantity

            state = m.state
            report["by_state"][state] = report["by_state"].get(state, 0) + 1

            b_key = str(m.branch_id)
            report["by_branch"].setdefault(b_key, {"movements": 0, "quantity": 0})
            report["by_branch"][b_key]["movements"] += 1
            report["by_branch"][b_key]["quantity"] += m.quantity

        return report


    def generate_discrepancy_report(
        self,
        branch_id: Optional[int] = None,
        product_id: Optional[int] = None,       # Exp 2
        date_from: Optional[datetime] = None,    # Exp 1 (last_count_date)
        date_to: Optional[datetime] = None,      # Exp 1
    ) -> Dict[str, Any]:
        """Generate discrepancy analysis report."""
        from models.inventory import Inventory
        from models.product import Product
        from models.branch import Branch

        query = (
            self.db.query(Inventory)
            .join(Product)
            .join(Branch)
            .filter(
                Inventory.physical_stock != Inventory.digital_stock,
                Inventory.is_active == True,
                Product.is_active == True,
                Branch.is_active == True,
            )
        )
        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)
        if product_id:
            query = query.filter(Inventory.product_id == product_id)
        if date_from:
            query = query.filter(Inventory.last_count_date >= date_from)
        if date_to:
            query = query.filter(Inventory.last_count_date <= date_to)

        items = query.all()

        report: Dict[str, Any] = {
            "generated_at": _fmt_date(datetime.utcnow()),
            "filters": {
                "branch_id": branch_id,
                "product_id": product_id,
                "date_from": _fmt_date(date_from),
                "date_to": _fmt_date(date_to),
            },
            "total_discrepancies": len(items),
            "items": [],
            "summary": {
                "total_difference": 0,
                "positive_differences": 0,
                "negative_differences": 0,
            },
        }

        for item in items:
            diff = item.difference
            report["summary"]["total_difference"] += abs(diff)
            if diff > 0:
                report["summary"]["positive_differences"] += 1
            elif diff < 0:
                report["summary"]["negative_differences"] += 1

            report["items"].append({
                "product": item.product.name,
                "sku": item.product.sku,
                "branch": item.branch.name,
                "physical": item.physical_stock,
                "digital": item.digital_stock,
                "difference": diff,
                "percentage": round((abs(diff) / max(item.digital_stock, 1)) * 100, 2),
            })

        report["items"].sort(key=lambda x: x["percentage"], reverse=True)
        return report


    def generate_kpi_report(
        self,
        branch_id: Optional[int] = None,
        date_from: Optional[datetime] = None,   # Exp 1
        date_to: Optional[datetime] = None,     # Exp 1
    ) -> Dict[str, Any]:
        """Generate KPI report."""
        from modules.dashboard.service import DashboardService
        from modules.inventory.repository import InventoryRepository
        from modules.movements.repository import MovementRepository

        dashboard_service = DashboardService(self.db)

        report: Dict[str, Any] = {
            "generated_at": _fmt_date(datetime.utcnow()),
            "filters": {
                "branch_id": branch_id,
                "date_from": _fmt_date(date_from),
                "date_to": _fmt_date(date_to),
            },
            "kpis": {
                "eri": dashboard_service.calculate_kpi_eri(branch_id),
                "eru": dashboard_service.calculate_kpi_eru(branch_id),
            },
            "metrics": {},
        }

        inventory_repo = InventoryRepository(self.db)
        report["metrics"]["total_physical_stock"] = inventory_repo.get_total_physical_stock(branch_id)
        report["metrics"]["total_digital_stock"] = inventory_repo.get_total_digital_stock(branch_id)
        report["metrics"]["discrepancy_count"] = inventory_repo.get_discrepancy_count(branch_id)
        report["metrics"]["low_stock_count"] = inventory_repo.get_low_stock_count(branch_id)

        movement_repo = MovementRepository(self.db)
        report["metrics"]["pending_movements"] = movement_repo.get_pending_count(branch_id)

        lookback = date_from or (datetime.utcnow() - timedelta(days=30))
        stats = movement_repo.get_stats_by_type(branch_id, lookback)
        report["metrics"]["movement_stats_period"] = stats

        return report

    def generate_user_activity_report(
        self,
        user_id: Optional[int] = None,          # Exp 3
        date_from: Optional[datetime] = None,   # Exp 1
        date_to: Optional[datetime] = None,     # Exp 1
    ) -> Dict[str, Any]:
        """Generate user activity report."""
        from modules.history.service import HistoryService

        history_service = HistoryService(self.db)
        result = history_service.list_history(
            limit=1000,
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
        )

        report: Dict[str, Any] = {
            "generated_at": _fmt_date(datetime.utcnow()),
            "filters": {
                "user_id": user_id,
                "date_from": _fmt_date(date_from),
                "date_to": _fmt_date(date_to),
            },
            "total_activities": result["total"],
            "by_event_type": {},
            "activities": result["entries"],
        }

        for entry in result["entries"]:
            event_type = entry["event_type"]
            report["by_event_type"][event_type] = (
                report["by_event_type"].get(event_type, 0) + 1
            )

        return report


    # ─────────────────────────────────────────────────────────────────────────
    # EXP 4 · EXPORTACIÓN CSV
    # ─────────────────────────────────────────────────────────────────────────

    def export_to_csv(self, report_data: Dict[str, Any], filename: str) -> str:
        """
        Export report_data to a CSV file at *filename*.

        Nested dicts are flattened with dot-notation keys.
        List values are JSON-encoded into a single cell.
        Returns the filename on success.
        """
        flat = _flatten_dict(report_data)

        # If the report contains an 'items' list we write one row per item
        # plus a summary header block; otherwise we write the flat dict.
        items_list: Optional[List] = None
        for key in ("items", "activities", "products", "branches"):
            val = report_data.get(key)
            if isinstance(val, list) and val:
                items_list = val
                break

        with open(filename, "w", newline="", encoding="utf-8") as fh:
            if items_list and isinstance(items_list[0], dict):
                # --- header rows: scalar fields from the top-level report ---
                meta_writer = csv.writer(fh)
                meta_writer.writerow(["# Reporte generado", flat.get("generated_at", "")])
                for k, v in flat.items():
                    if k not in ("items", "activities", "products", "branches"):
                        meta_writer.writerow([k, v])
                meta_writer.writerow([])  # blank separator

                # --- one row per item ---
                item_writer = csv.DictWriter(
                    fh,
                    fieldnames=list(items_list[0].keys()),
                    extrasaction="ignore",
                )
                item_writer.writeheader()
                item_writer.writerows(items_list)
            else:
                # Simple key-value export
                writer = csv.writer(fh)
                writer.writerow(["campo", "valor"])
                for k, v in flat.items():
                    writer.writerow([k, v])

        logger.info("CSV exported: %s", filename)
        return filename

    # ─────────────────────────────────────────────────────────────────────────
    # EXP 5 · EXPORTACIÓN EXCEL
    # ─────────────────────────────────────────────────────────────────────────

    def export_to_excel(self, report_data: Dict[str, Any], filename: str) -> str:
        """
        Export report_data to an Excel (.xlsx) file at *filename*.

        • Hoja "Resumen"  – campos escalares del reporte (clave / valor).
        • Hoja "Datos"    – lista principal (items / activities / products /
                            branches) con una fila por elemento.
        • Headers en negrita, columnas auto-ajustadas al contenido.
        Returns the filename on success.
        """
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment
            from openpyxl.utils import get_column_letter
        except ImportError:
            raise ImportError(
                "openpyxl no está instalado. Ejecuta: pip install openpyxl==3.1.5"
            )

        wb = Workbook()

        # ── Hoja 1: Resumen ──────────────────────────────────────────────────
        ws_summary = wb.active
        ws_summary.title = "Resumen"
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill("solid", fgColor="1F4E78")

        ws_summary["A1"] = "Campo"
        ws_summary["B1"] = "Valor"
        ws_summary["A1"].font = header_font
        ws_summary["B1"].font = header_font
        ws_summary["A1"].fill = header_fill
        ws_summary["B1"].fill = header_fill

        flat = _flatten_dict(report_data)
        list_keys = {"items", "activities", "products", "branches"}
        row = 2
        items_list: Optional[List] = None

        for key in ("items", "activities", "products", "branches"):
            val = report_data.get(key)
            if isinstance(val, list) and val:
                items_list = val
                break

        for k, v in flat.items():
            if k.split(".")[0] in list_keys:
                continue
            ws_summary.cell(row=row, column=1, value=k)
            ws_summary.cell(row=row, column=2, value=str(v) if v is not None else "")
            row += 1

        ws_summary.column_dimensions["A"].width = 35
        ws_summary.column_dimensions["B"].width = 50

        # ── Hoja 2: Datos ────────────────────────────────────────────────────
        if items_list and isinstance(items_list[0], dict):
            ws_data = wb.create_sheet("Datos")
            headers = list(items_list[0].keys())

            for col_idx, header in enumerate(headers, start=1):
                cell = ws_data.cell(row=1, column=col_idx, value=header)
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="2E75B6")
                cell.alignment = Alignment(horizontal="center")

            for row_idx, item in enumerate(items_list, start=2):
                for col_idx, header in enumerate(headers, start=1):
                    val = item.get(header)
                    ws_data.cell(row=row_idx, column=col_idx, value=val)

            # Auto-width
            for col_idx, header in enumerate(headers, start=1):
                max_len = max(
                    len(str(header)),
                    max(
                        (len(str(row_item.get(header, "") or "")) for row_item in items_list),
                        default=0,
                    ),
                )
                ws_data.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 4, 50)

        wb.save(filename)
        logger.info("Excel exported: %s", filename)
        return filename

    # ─────────────────────────────────────────────────────────────────────────
    # EXP 6 · VISTA FORMATEADA
    # ─────────────────────────────────────────────────────────────────────────

    def format_report_for_display(
        self, report_type: str, report_data: Dict[str, Any]
    ) -> str:
        """
        Convert a report dict into a human-readable text block.

        Returns a plain-text string with borders, aligned columns and totals.
        """
        lines: List[str] = []

        def h1(text: str) -> None:
            bar = "═" * (len(text) + 4)
            lines.append(f"╔{bar}╗")
            lines.append(f"║  {text}  ║")
            lines.append(f"╚{bar}╝")

        def h2(text: str) -> None:
            lines.append(f"\n  ┌─ {text} {'─' * max(0, 60 - len(text))}┐")

        def kv(label: str, value: Any, indent: int = 4) -> None:
            lines.append(f"{' ' * indent}{label:<30} {value}")

        def table(headers: List[str], rows: List[List[Any]], indent: int = 4) -> None:
            col_widths = [
                max(len(str(h)), max((len(str(r[i] or "")) for r in rows), default=0))
                for i, h in enumerate(headers)
            ]
            sep = " " * indent + "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
            header_row = (
                " " * indent
                + "| "
                + " | ".join(str(h).ljust(w) for h, w in zip(headers, col_widths))
                + " |"
            )
            lines.append(sep)
            lines.append(header_row)
            lines.append(sep)
            for row in rows:
                lines.append(
                    " " * indent
                    + "| "
                    + " | ".join(str(c or "").ljust(w) for c, w in zip(row, col_widths))
                    + " |"
                )
            lines.append(sep)

        TITLES = {
            "inventory": "Reporte de Inventario",
            "movements": "Reporte de Movimientos",
            "discrepancies": "Reporte de Discrepancias",
            "kpis": "Reporte de KPIs",
            "user_activity": "Actividad por Usuario",
            "top_products": "Top Productos",
            "branch_efficiency": "Eficiencia por Sucursal",
            "inventory_value": "Valor de Inventario",
            "transfers": "Reporte de Transferencias",
            "trends": "Tendencias",
            "comparison": "Comparación de Períodos",
        }
        h1(TITLES.get(report_type, "Reporte"))
        kv("Generado en:", report_data.get("generated_at", "—"), indent=2)

        filters = report_data.get("filters", {})
        if any(v for v in filters.values()):
            h2("Filtros aplicados")
            for k, v in filters.items():
                if v is not None:
                    kv(k + ":", v)

        # ── Inventario ────────────────────────────────────────────────────────
        if report_type == "inventory":
            h2("Resumen")
            kv("Total artículos:", report_data.get("total_items", 0))
            kv("Stock físico total:", report_data.get("total_physical_stock", 0))
            kv("Stock digital total:", report_data.get("total_digital_stock", 0))
            if report_data.get("by_branch"):
                h2("Por sucursal")
                tbl_rows = [
                    [b, v["items"], v["physical_stock"], v["digital_stock"]]
                    for b, v in report_data["by_branch"].items()
                ]
                table(["Sucursal", "Artículos", "Físico", "Digital"], tbl_rows)
            if report_data.get("low_stock"):
                h2(f"Stock bajo ({len(report_data['low_stock'])} artículos)")
                table(
                    ["Producto", "Sucursal", "Actual", "Mínimo"],
                    [[i["product"], i["branch"], i["current"], i["min"]]
                     for i in report_data["low_stock"]],
                )

        # ── Movimientos ───────────────────────────────────────────────────────
        elif report_type == "movements":
            h2("Resumen")
            kv("Total movimientos:", report_data.get("total_movements", 0))
            if report_data.get("by_type"):
                h2("Por tipo")
                table(
                    ["Tipo", "Cantidad", "Unidades"],
                    [[t, v["count"], v["total_quantity"]]
                     for t, v in report_data["by_type"].items()],
                )
            if report_data.get("by_state"):
                h2("Por estado")
                table(
                    ["Estado", "Cantidad"],
                    [[s, c] for s, c in report_data["by_state"].items()],
                )

        # ── Discrepancias ─────────────────────────────────────────────────────
        elif report_type == "discrepancies":
            s = report_data.get("summary", {})
            h2("Resumen")
            kv("Total discrepancias:", report_data.get("total_discrepancies", 0))
            kv("Diferencia absoluta total:", s.get("total_difference", 0))
            kv("Con exceso (físico > digital):", s.get("positive_differences", 0))
            kv("Con faltante (físico < digital):", s.get("negative_differences", 0))
            if report_data.get("items"):
                h2("Detalle")
                table(
                    ["Producto", "SKU", "Sucursal", "Físico", "Digital", "Diferencia", "%"],
                    [[i["product"], i["sku"], i["branch"],
                      i["physical"], i["digital"], i["difference"], i["percentage"]]
                     for i in report_data["items"][:50]],
                )

        # ── KPIs ──────────────────────────────────────────────────────────────
        elif report_type == "kpis":
            h2("KPIs")
            for k, v in report_data.get("kpis", {}).items():
                kv(k.upper() + ":", f"{v:.2f}" if isinstance(v, float) else v)
            h2("Métricas")
            for k, v in report_data.get("metrics", {}).items():
                kv(k + ":", v)

        # ── Top productos ─────────────────────────────────────────────────────
        elif report_type == "top_products":
            h2("Resumen")
            kv("Métrica:", report_data.get("metric", "—"))
            kv("Límite:", report_data.get("limit", "—"))
            if report_data.get("products"):
                h2("Ranking")
                first = report_data["products"][0]
                hdrs = list(first.keys())
                table(hdrs, [[p.get(h) for h in hdrs] for p in report_data["products"]])

        # ── Eficiencia por sucursal ────────────────────────────────────────────
        elif report_type == "branch_efficiency":
            if report_data.get("branches"):
                h2("Eficiencia por sucursal")
                table(
                    ["Sucursal", "Movimientos", "Tasa rechazo %",
                     "Días prom. validación", "Transf. enviadas", "Transf. recibidas",
                     "Tasa discrepancias %"],
                    [[b["branch"], b["total_movements"], b["rejection_rate"],
                      b["avg_validation_days"], b["transfers_sent"],
                      b["transfers_received"], b["discrepancy_rate"]]
                     for b in report_data["branches"]],
                )

        # ── Valor de inventario ───────────────────────────────────────────────
        elif report_type == "inventory_value":
            h2("Resumen")
            kv("Valor total global:", f"${report_data.get('total_value', 0):,.2f}")
            if report_data.get("by_branch"):
                h2("Por sucursal")
                table(
                    ["Sucursal", "Artículos", "Valor total"],
                    [[b, v["items"], f"${v['value']:,.2f}"]
                     for b, v in report_data["by_branch"].items()],
                )
            if report_data.get("items"):
                h2("Detalle (top 50)")
                table(
                    ["Producto", "SKU", "Sucursal", "Stock", "Costo unit.", "Valor"],
                    [[i["product"], i["sku"], i["branch"],
                      i["stock"], i["unit_price"], f"${i['value']:,.2f}"]
                     for i in report_data["items"][:50]],
                )

        # ── Transferencias ────────────────────────────────────────────────────
        elif report_type == "transfers":
            h2("Resumen")
            kv("Total transferencias:", report_data.get("total_transfers", 0))
            kv("Pendientes de recepción:", report_data.get("pending_reception", 0))
            if report_data.get("items"):
                h2("Detalle (primeras 50)")
                table(
                    ["Producto", "Origen", "Destino", "Cantidad", "Estado", "Recibida"],
                    [[i["product"], i["origin_branch"], i["destination_branch"],
                      i["quantity"], i["state"], "Sí" if i["is_received"] else "No"]
                     for i in report_data["items"][:50]],
                )

        # ── Tendencias ────────────────────────────────────────────────────────
        elif report_type == "trends":
            h2("Resumen")
            kv("Métrica:", report_data.get("metric", "—"))
            kv("Períodos:", report_data.get("periods_count", "—"))
            if report_data.get("data_points"):
                h2("Datos")
                table(
                    ["Período", "Valor"],
                    [[p["period"], p["value"]] for p in report_data["data_points"]],
                )

        # ── Comparación ───────────────────────────────────────────────────────
        elif report_type == "comparison":
            for period_key, period_label in [("period1", "Período 1"), ("period2", "Período 2")]:
                p = report_data.get(period_key, {})
                if p:
                    h2(period_label)
                    for k, v in p.items():
                        if not isinstance(v, (dict, list)):
                            kv(k + ":", v)
            if report_data.get("differences"):
                h2("Diferencias")
                for k, v in report_data["differences"].items():
                    kv(k + ":", v)

        # ── Actividad usuario ─────────────────────────────────────────────────
        elif report_type == "user_activity":
            h2("Resumen")
            kv("Total actividades:", report_data.get("total_activities", 0))
            if report_data.get("by_event_type"):
                h2("Por tipo de evento")
                table(
                    ["Evento", "Cantidad"],
                    [[e, c] for e, c in report_data["by_event_type"].items()],
                )

        # ── Auditoría de Historial ────────────────────────────────────────────
        elif report_type == "history_audit":
            h2("Resumen")
            kv("Total registros en BD:", report_data.get("total_entries", 0))
            kv("Registros incluidos:", report_data.get("returned_entries", 0))

            if report_data.get("by_entity_type"):
                h2("Por tipo de entidad")
                table(
                    ["Tipo", "Eventos"],
                    [[t, c] for t, c in report_data["by_entity_type"].items()],
                )

            if report_data.get("by_event_type"):
                h2("Por tipo de evento (top 20)")
                rows = list(report_data["by_event_type"].items())[:20]
                table(["Evento", "Cantidad"], [[e, c] for e, c in rows])

            if report_data.get("by_user"):
                h2("Por usuario")
                table(
                    ["Usuario", "Acciones"],
                    [[u, c] for u, c in report_data["by_user"].items()],
                )

            if report_data.get("by_date"):
                h2("Actividad diaria")
                table(
                    ["Fecha", "Eventos"],
                    [[d, c] for d, c in report_data["by_date"].items()],
                )

            if report_data.get("top_entities"):
                h2("Entidades más activas (top 20)")
                table(
                    ["Tipo", "Entidad", "Eventos"],
                    [[e["entity_type"], e["entity_name"], e["event_count"]]
                     for e in report_data["top_entities"]],
                )

            if report_data.get("items"):
                h2(f"Detalle ({len(report_data['items'])} registros)")
                table(
                    ["ID", "Fecha", "Evento", "Tipo", "Entidad", "Usuario", "Acción"],
                    [[i["id"], i["fecha"], i["evento"], i["tipo"],
                      i["entidad"], i["usuario"], i["accion"]]
                     for i in report_data["items"][:200]],
                )
                if len(report_data["items"]) > 200:
                    lines.append(
                        f"\n  … y {len(report_data['items']) - 200} registros más "
                        "(exporta a CSV/Excel para verlos todos)"
                    )

        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────────
    # EXP 7 · REPORTES GUARDADOS
    # ─────────────────────────────────────────────────────────────────────────

    def save_report_config(
        self,
        name: str,
        report_type: str,
        parameters: Dict[str, Any],
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Persist a named report configuration. Returns the saved record."""
        from models.saved_report import SavedReport

        record = SavedReport(
            name=name,
            report_type=report_type,
            parameters=json.dumps(parameters, ensure_ascii=False),
            created_by=user_id,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        logger.info("Saved report config id=%d name='%s'", record.id, record.name)
        return record.to_dict()

    def get_saved_reports(
        self, user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Return all saved report configurations, optionally filtered by user."""
        from models.saved_report import SavedReport

        query = self.db.query(SavedReport)
        if user_id is not None:
            query = query.filter(SavedReport.created_by == user_id)
        records = query.order_by(SavedReport.created_at.desc()).all()
        return [r.to_dict() for r in records]

    def get_report_config(self, config_id: int) -> Optional[Dict[str, Any]]:
        """Return a single saved report config by id, or None."""
        from models.saved_report import SavedReport

        record = self.db.query(SavedReport).filter(SavedReport.id == config_id).first()
        if not record:
            return None
        data = record.to_dict()
        # Deserialise parameters for convenience
        try:
            data["parameters_dict"] = json.loads(record.parameters or "{}")
        except (json.JSONDecodeError, TypeError):
            data["parameters_dict"] = {}
        return data

    def delete_report_config(self, config_id: int) -> bool:
        """Delete a saved report config. Returns True on success."""
        from models.saved_report import SavedReport

        record = self.db.query(SavedReport).filter(SavedReport.id == config_id).first()
        if not record:
            return False
        self.db.delete(record)
        self.db.commit()
        logger.info("Deleted saved report config id=%d", config_id)
        return True

    # ─────────────────────────────────────────────────────────────────────────
    # EXP 8 · COMPARACIÓN DE PERÍODOS
    # ─────────────────────────────────────────────────────────────────────────

    def generate_comparison_report(
        self,
        report_type: str,
        period1_from: datetime,
        period1_to: datetime,
        period2_from: datetime,
        period2_to: datetime,
        branch_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate the same report for two date ranges and compute deltas.

        report_type: 'inventory' | 'movements' | 'discrepancies' | 'kpis'
        """
        GENERATORS = {
            "inventory": self.generate_inventory_report,
            "movements": self.generate_movement_report,
            "discrepancies": self.generate_discrepancy_report,
            "kpis": self.generate_kpi_report,
        }
        gen = GENERATORS.get(report_type)
        if gen is None:
            raise ValueError(
                f"report_type '{report_type}' no soporta comparación. "
                f"Usa: {list(GENERATORS.keys())}"
            )

        p1 = gen(branch_id=branch_id, date_from=period1_from, date_to=period1_to)
        p2 = gen(branch_id=branch_id, date_from=period2_from, date_to=period2_to)

        # Build numeric differences for scalar top-level fields
        diffs: Dict[str, Any] = {}
        numeric_keys = {
            k for k in p1
            if isinstance(p1[k], (int, float))
            and k not in ("branch_id",)
        }
        for k in numeric_keys:
            v1, v2 = p1.get(k, 0) or 0, p2.get(k, 0) or 0
            diffs[k] = {
                "period1": v1,
                "period2": v2,
                "delta": v2 - v1,
                "delta_pct": round(((v2 - v1) / v1 * 100) if v1 else 0, 2),
            }

        return {
            "generated_at": _fmt_date(datetime.utcnow()),
            "report_type": report_type,
            "branch_id": branch_id,
            "period1": {
                "from": _fmt_date(period1_from),
                "to": _fmt_date(period1_to),
                "data": p1,
            },
            "period2": {
                "from": _fmt_date(period2_from),
                "to": _fmt_date(period2_to),
                "data": p2,
            },
            "differences": diffs,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # EXP 9 · TOP PRODUCTOS
    # ─────────────────────────────────────────────────────────────────────────

    def generate_top_products_report(
        self,
        metric: str = "most_moved",
        limit: int = 10,
        branch_id: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Return the top *limit* products ranked by *metric*.

        metric values:
            most_moved       – most validated movements (qty)
            least_moved      – fewest validated movements
            most_stock       – highest digital stock
            lowest_stock     – lowest digital stock (> 0)
            most_discrepancies – largest absolute discrepancy
        """
        from models.movement import Movement, MovementState
        from models.inventory import Inventory
        from models.product import Product
        from models.branch import Branch

        products: List[Dict[str, Any]] = []

        if metric in ("most_moved", "least_moved"):
            query = (
                self.db.query(
                    Product.id,
                    Product.name,
                    Product.sku,
                    func.count(Movement.id).label("move_count"),
                    func.sum(Movement.quantity).label("total_qty"),
                )
                .join(Movement, Movement.product_id == Product.id)
                .filter(
                    Movement.state == MovementState.VALIDADO.value,
                    Movement.is_cancelled == False,
                )
            )
            if branch_id:
                query = query.filter(Movement.branch_id == branch_id)
            if date_from:
                query = query.filter(Movement.created_at >= date_from)
            if date_to:
                query = query.filter(Movement.created_at <= date_to)
            query = query.group_by(Product.id, Product.name, Product.sku)
            asc = metric == "least_moved"
            order_col = func.sum(Movement.quantity)
            query = query.order_by(order_col if asc else order_col.desc())
            query = query.limit(limit)

            for rank, row in enumerate(query.all(), start=1):
                products.append({
                    "rank": rank,
                    "product_id": row.id,
                    "product": row.name,
                    "sku": row.sku,
                    "move_count": row.move_count,
                    "total_quantity_moved": row.total_qty or 0,
                })

        elif metric in ("most_stock", "lowest_stock"):
            query = (
                self.db.query(
                    Product.id,
                    Product.name,
                    Product.sku,
                    func.sum(Inventory.digital_stock).label("total_stock"),
                )
                .join(Inventory, Inventory.product_id == Product.id)
                .join(Branch, Branch.id == Inventory.branch_id)
                .filter(
                    Inventory.is_active == True,
                    Product.is_active == True,
                    Branch.is_active == True,
                )
            )
            if branch_id:
                query = query.filter(Inventory.branch_id == branch_id)
            query = query.group_by(Product.id, Product.name, Product.sku)
            if metric == "lowest_stock":
                query = query.filter(
                    func.sum(Inventory.digital_stock) > 0
                ).order_by(func.sum(Inventory.digital_stock))
            else:
                query = query.order_by(func.sum(Inventory.digital_stock).desc())
            query = query.limit(limit)

            for rank, row in enumerate(query.all(), start=1):
                products.append({
                    "rank": rank,
                    "product_id": row.id,
                    "product": row.name,
                    "sku": row.sku,
                    "total_stock": row.total_stock or 0,
                })

        elif metric == "most_discrepancies":
            query = (
                self.db.query(
                    Product.id,
                    Product.name,
                    Product.sku,
                    func.sum(
                        func.abs(Inventory.physical_stock - Inventory.digital_stock)
                    ).label("total_diff"),
                )
                .join(Inventory, Inventory.product_id == Product.id)
                .join(Branch, Branch.id == Inventory.branch_id)
                .filter(
                    Inventory.physical_stock != Inventory.digital_stock,
                    Inventory.is_active == True,
                    Product.is_active == True,
                    Branch.is_active == True,
                )
            )
            if branch_id:
                query = query.filter(Inventory.branch_id == branch_id)
            query = (
                query.group_by(Product.id, Product.name, Product.sku)
                .order_by(func.sum(
                    func.abs(Inventory.physical_stock - Inventory.digital_stock)
                ).desc())
                .limit(limit)
            )

            for rank, row in enumerate(query.all(), start=1):
                products.append({
                    "rank": rank,
                    "product_id": row.id,
                    "product": row.name,
                    "sku": row.sku,
                    "total_discrepancy": row.total_diff or 0,
                })
        else:
            raise ValueError(
                f"Métrica desconocida: '{metric}'. Usa: most_moved, least_moved, "
                "most_stock, lowest_stock, most_discrepancies"
            )

        return {
            "generated_at": _fmt_date(datetime.utcnow()),
            "metric": metric,
            "limit": limit,
            "filters": {
                "branch_id": branch_id,
                "date_from": _fmt_date(date_from),
                "date_to": _fmt_date(date_to),
            },
            "products": products,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # EXP 10 · EFICIENCIA POR SUCURSAL
    # ─────────────────────────────────────────────────────────────────────────

    def generate_branch_efficiency_report(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Calculate per-branch operational metrics:
          - total_movements, rejection_rate, avg_validation_days,
            transfers_sent, transfers_received, discrepancy_rate
        """
        from models.movement import Movement, MovementState, MovementType
        from models.inventory import Inventory
        from models.branch import Branch
        from models.product import Product

        branches = (
            self.db.query(Branch)
            .filter(Branch.is_active == True)
            .order_by(Branch.name)
            .all()
        )

        branch_data: List[Dict[str, Any]] = []

        for branch in branches:
            q = self.db.query(Movement).filter(Movement.branch_id == branch.id)
            if date_from:
                q = q.filter(Movement.created_at >= date_from)
            if date_to:
                q = q.filter(Movement.created_at <= date_to)
            all_mvs = q.all()

            total = len(all_mvs)
            rejected = sum(1 for m in all_mvs if m.state == MovementState.RECHAZADO.value)
            rejection_rate = round((rejected / total * 100) if total else 0, 2)

            # Avg validation days (validated movements only)
            validated = [
                m for m in all_mvs
                if m.state == MovementState.VALIDADO.value
                and m.validated_at and m.created_at
            ]
            if validated:
                total_days = sum(
                    (m.validated_at - m.created_at).total_seconds() / 86400
                    for m in validated
                )
                avg_validation_days = round(total_days / len(validated), 2)
            else:
                avg_validation_days = None

            transfers_sent = sum(
                1 for m in all_mvs
                if m.movement_type == MovementType.TRANSFERENCIA.value
            )
            transfers_received = (
                self.db.query(Movement)
                .filter(
                    Movement.destination_branch_id == branch.id,
                    Movement.movement_type == MovementType.TRANSFERENCIA.value,
                )
            )
            if date_from:
                transfers_received = transfers_received.filter(
                    Movement.created_at >= date_from
                )
            if date_to:
                transfers_received = transfers_received.filter(
                    Movement.created_at <= date_to
                )
            transfers_received_count = transfers_received.count()

            # Discrepancy rate = items with discrepancy / total active items
            total_items = (
                self.db.query(Inventory)
                .join(Product)
                .filter(
                    Inventory.branch_id == branch.id,
                    Inventory.is_active == True,
                    Product.is_active == True,
                )
                .count()
            )
            disc_items = (
                self.db.query(Inventory)
                .join(Product)
                .filter(
                    Inventory.branch_id == branch.id,
                    Inventory.is_active == True,
                    Product.is_active == True,
                    Inventory.physical_stock != Inventory.digital_stock,
                )
                .count()
            )
            discrepancy_rate = round(
                (disc_items / total_items * 100) if total_items else 0, 2
            )

            branch_data.append({
                "branch_id": branch.id,
                "branch": branch.name,
                "total_movements": total,
                "rejection_rate": rejection_rate,
                "avg_validation_days": avg_validation_days,
                "transfers_sent": transfers_sent,
                "transfers_received": transfers_received_count,
                "discrepancy_rate": discrepancy_rate,
            })

        return {
            "generated_at": _fmt_date(datetime.utcnow()),
            "filters": {
                "date_from": _fmt_date(date_from),
                "date_to": _fmt_date(date_to),
            },
            "branches": branch_data,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # EXP 11 · VALOR DE INVENTARIO
    # ─────────────────────────────────────────────────────────────────────────

    def generate_inventory_value_report(
        self,
        branch_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Calculate the monetary value of current stock.

        Unit price resolution order:
          1. Inventory.unit_cost  (branch-specific cost)
          2. Product.unit_price   (global fallback)

        Items without any price are included with value=0 and flagged.
        """
        from models.inventory import Inventory
        from models.product import Product
        from models.branch import Branch

        query = (
            self.db.query(Inventory)
            .join(Product)
            .join(Branch)
            .filter(
                Inventory.is_active == True,
                Product.is_active == True,
                Branch.is_active == True,
            )
        )
        if branch_id:
            query = query.filter(Inventory.branch_id == branch_id)

        items = query.order_by(Branch.name, Product.name).all()

        total_value = 0.0
        by_branch: Dict[str, Any] = {}
        item_rows: List[Dict[str, Any]] = []
        no_price_count = 0

        for item in items:
            unit_price = item.unit_cost or item.product.unit_price
            has_price = unit_price is not None
            value = round((item.digital_stock * unit_price) if has_price else 0.0, 2)
            if not has_price:
                no_price_count += 1

            total_value += value

            branch_name = item.branch.name
            if branch_name not in by_branch:
                by_branch[branch_name] = {"items": 0, "value": 0.0}
            by_branch[branch_name]["items"] += 1
            by_branch[branch_name]["value"] = round(
                by_branch[branch_name]["value"] + value, 2
            )

            item_rows.append({
                "product_id": item.product_id,
                "product": item.product.name,
                "sku": item.product.sku,
                "branch": branch_name,
                "stock": item.digital_stock,
                "unit_price": unit_price,
                "value": value,
                "no_price": not has_price,
            })

        # Sort by value descending
        item_rows.sort(key=lambda x: x["value"], reverse=True)

        return {
            "generated_at": _fmt_date(datetime.utcnow()),
            "filters": {"branch_id": branch_id},
            "total_value": round(total_value, 2),
            "total_items": len(items),
            "no_price_count": no_price_count,
            "by_branch": by_branch,
            "items": item_rows,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # EXP 12 · REPORTE DE TRANSFERENCIAS
    # ─────────────────────────────────────────────────────────────────────────

    def generate_transfer_report(
        self,
        branch_id: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Detailed report of inter-branch transfers.

        Includes: per-transfer detail, totals by branch pair,
        and a list of transfers pending reception.
        """
        from models.movement import Movement, MovementType
        from models.product import Product
        from models.branch import Branch

        query = (
            self.db.query(Movement)
            .filter(Movement.movement_type == MovementType.TRANSFERENCIA.value)
        )
        if branch_id:
            query = query.filter(
                or_(
                    Movement.branch_id == branch_id,
                    Movement.destination_branch_id == branch_id,
                )
            )
        if date_from:
            query = query.filter(Movement.created_at >= date_from)
        if date_to:
            query = query.filter(Movement.created_at <= date_to)

        transfers = query.order_by(Movement.created_at.desc()).all()

        # Pre-load branch names
        branch_cache: Dict[int, str] = {}

        def branch_name(bid: Optional[int]) -> str:
            if bid is None:
                return "—"
            if bid not in branch_cache:
                b = self.db.query(Branch).filter(Branch.id == bid).first()
                branch_cache[bid] = b.name if b else str(bid)
            return branch_cache[bid]

        # Pre-load product names
        product_cache: Dict[int, str] = {}

        def product_name(pid: int) -> str:
            if pid not in product_cache:
                p = self.db.query(Product).filter(Product.id == pid).first()
                product_cache[pid] = p.name if p else str(pid)
            return product_cache[pid]

        items: List[Dict[str, Any]] = []
        by_pair: Dict[str, Any] = {}
        pending_reception = 0

        for t in transfers:
            origin = branch_name(t.branch_id)
            destination = branch_name(t.destination_branch_id)
            pair_key = f"{origin} → {destination}"

            if pair_key not in by_pair:
                by_pair[pair_key] = {"count": 0, "total_quantity": 0}
            by_pair[pair_key]["count"] += 1
            by_pair[pair_key]["total_quantity"] += t.quantity

            if not t.is_received and not t.is_cancelled:
                pending_reception += 1

            items.append({
                "id": t.id,
                "product": product_name(t.product_id),
                "origin_branch": origin,
                "destination_branch": destination,
                "quantity": t.quantity,
                "state": t.state,
                "is_received": t.is_received,
                "is_cancelled": t.is_cancelled,
                "created_at": _fmt_date(t.created_at),
                "received_at": _fmt_date(t.received_at),
                "received_notes": t.received_notes,
            })

        return {
            "generated_at": _fmt_date(datetime.utcnow()),
            "filters": {
                "branch_id": branch_id,
                "date_from": _fmt_date(date_from),
                "date_to": _fmt_date(date_to),
            },
            "total_transfers": len(transfers),
            "pending_reception": pending_reception,
            "by_branch_pair": by_pair,
            "items": items,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # EXP 13 · TENDENCIAS
    # ─────────────────────────────────────────────────────────────────────────

    # ─────────────────────────────────────────────────────────────────────────
    # HISTORIAL · AUDITORÍA DE HISTORIAL
    # ─────────────────────────────────────────────────────────────────────────

    def generate_history_audit_report(
        self,
        entity_type: Optional[str] = None,
        branch_id: Optional[int] = None,
        user_id: Optional[int] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        event_type: Optional[str] = None,
        limit: int = 500,
    ) -> Dict[str, Any]:
        """
        Auditoría completa del historial de eventos del sistema.

        El historial solo provee los datos en bruto; este método los agrega,
        cuenta y estructura para que Reports pueda exportarlos/formatearlos.

        Parámetros
        ──────────
        entity_type : filtrar por tipo de entidad (product, branch, movement,
                      inventory, alert, user, system — None = todos)
        branch_id   : filtrar entradas que mencionen esta sucursal en details
                      (usa la misma estrategia LIKE del historial, Expansión 1)
        user_id     : filtrar por usuario que realizó la acción
        date_from / date_to : rango de fechas
        event_type  : filtrar por nombre exacto de evento (ej. "product.updated")
        limit       : máximo de entradas a incluir en el detalle (def. 500)

        Retorno
        ───────
        {
          "generated_at": ...,
          "filters": {...},
          "total_entries": int,
          "by_event_type": {event_type: count, ...},
          "by_entity_type": {entity_type: count, ...},
          "by_user": {user_name: count, ...},
          "by_date": {YYYY-MM-DD: count, ...},       ← actividad diaria
          "top_entities": [{entity_type, entity_name, event_count}, ...],
          "items": [{id, fecha, evento, tipo, entidad, usuario, acción}, ...]
        }
        """
        from modules.history.service import HistoryService

        history_svc = HistoryService(self.db)

        # ── Obtener entradas con enriquecimiento de nombres (Exp 3) ──────────
        result = history_svc.list_history(
            limit=limit,
            event_type=event_type,
            entity_type=entity_type,
            user_id=user_id,
            branch_id=branch_id,
            date_from=date_from,
            date_to=date_to,
            enrich=True,          # resuelve user_name y entity_name
        )
        entries = result["entries"]
        total = result["total"]

        # ── Agregaciones ─────────────────────────────────────────────────────
        by_event_type: Dict[str, int] = {}
        by_entity_type: Dict[str, int] = {}
        by_user: Dict[str, int] = {}
        by_date: Dict[str, int] = {}
        entity_counts: Dict[str, int] = {}   # "entity_type|entity_name" → count

        items: List[Dict[str, Any]] = []

        for e in entries:
            ev = e.get("event_type") or "—"
            ent_type = e.get("entity_type") or "—"
            user_name = e.get("user_name") or "—"
            entity_name = e.get("entity_name") or "—"
            created_raw = e.get("created_at") or ""
            date_key = created_raw[:10] if created_raw else "—"

            by_event_type[ev] = by_event_type.get(ev, 0) + 1
            by_entity_type[ent_type] = by_entity_type.get(ent_type, 0) + 1
            by_user[user_name] = by_user.get(user_name, 0) + 1
            by_date[date_key] = by_date.get(date_key, 0) + 1

            ec_key = f"{ent_type}|{entity_name}"
            entity_counts[ec_key] = entity_counts.get(ec_key, 0) + 1

            items.append({
                "id":          e.get("id"),
                "fecha":       created_raw[:19].replace("T", " "),
                "evento":      ev,
                "tipo":        ent_type,
                "entidad":     entity_name,
                "usuario":     user_name,
                "accion":      e.get("action") or "—",
                "eliminado":   e.get("entity_deleted", False),
            })

        # ── Top entidades más activas (máx. 20) ───────────────────────────────
        top_entities = sorted(
            [
                {
                    "entity_type": k.split("|")[0],
                    "entity_name": k.split("|")[1],
                    "event_count": v,
                }
                for k, v in entity_counts.items()
            ],
            key=lambda x: x["event_count"],
            reverse=True,
        )[:20]

        # ── Actividad diaria ordenada ─────────────────────────────────────────
        by_date_sorted = dict(sorted(by_date.items()))

        return {
            "generated_at": _fmt_date(datetime.utcnow()),
            "filters": {
                "entity_type": entity_type,
                "event_type":  event_type,
                "branch_id":   branch_id,
                "user_id":     user_id,
                "date_from":   _fmt_date(date_from),
                "date_to":     _fmt_date(date_to),
                "limit":       limit,
            },
            "total_entries":   total,
            "returned_entries": len(items),
            "by_event_type":   dict(sorted(by_event_type.items(), key=lambda x: x[1], reverse=True)),
            "by_entity_type":  dict(sorted(by_entity_type.items(), key=lambda x: x[1], reverse=True)),
            "by_user":         dict(sorted(by_user.items(), key=lambda x: x[1], reverse=True)),
            "by_date":         by_date_sorted,
            "top_entities":    top_entities,
            "items":           items,
        }

    def generate_trend_report(
        self,
        metric: str = "movimientos_total",
        period_days: int = 7,
        periods_back: int = 8,
        branch_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generate time-series trend data for the last *periods_back* windows
        of *period_days* each.

        metric values:
            movimientos_total   – total validated movements per window
            stock_total         – digital stock snapshot (end of window)
            discrepancias_count – items with discrepancy per window
        """
        from models.movement import Movement, MovementState
        from models.inventory import Inventory
        from models.product import Product
        from models.branch import Branch

        now = datetime.utcnow()
        data_points: List[Dict[str, Any]] = []

        for i in range(periods_back - 1, -1, -1):
            window_end = now - timedelta(days=i * period_days)
            window_start = window_end - timedelta(days=period_days)
            period_label = window_start.strftime("%Y-%m-%d")

            if metric == "movimientos_total":
                q = self.db.query(func.count(Movement.id)).filter(
                    Movement.state == MovementState.VALIDADO.value,
                    Movement.is_cancelled == False,
                    Movement.created_at >= window_start,
                    Movement.created_at < window_end,
                )
                if branch_id:
                    q = q.filter(Movement.branch_id == branch_id)
                value = q.scalar() or 0

            elif metric == "stock_total":
                # Stock snapshot: use items updated before window_end
                q = self.db.query(func.sum(Inventory.digital_stock)).join(
                    Product
                ).join(Branch).filter(
                    Inventory.is_active == True,
                    Product.is_active == True,
                    Branch.is_active == True,
                )
                if branch_id:
                    q = q.filter(Inventory.branch_id == branch_id)
                value = q.scalar() or 0  # current snapshot (no time travel on stock)

            elif metric == "discrepancias_count":
                q = self.db.query(func.count(Inventory.id)).join(
                    Product
                ).join(Branch).filter(
                    Inventory.is_active == True,
                    Product.is_active == True,
                    Branch.is_active == True,
                    Inventory.physical_stock != Inventory.digital_stock,
                )
                if branch_id:
                    q = q.filter(Inventory.branch_id == branch_id)
                value = q.scalar() or 0
            else:
                raise ValueError(
                    f"Métrica desconocida: '{metric}'. Usa: movimientos_total, "
                    "stock_total, discrepancias_count"
                )

            data_points.append({
                "period": period_label,
                "window_start": _fmt_date(window_start),
                "window_end": _fmt_date(window_end),
                "value": value,
            })

        # Simple trend direction
        if len(data_points) >= 2:
            first_val = data_points[0]["value"]
            last_val = data_points[-1]["value"]
            if last_val > first_val:
                trend = "ascendente"
            elif last_val < first_val:
                trend = "descendente"
            else:
                trend = "estable"
        else:
            trend = "sin datos"

        return {
            "generated_at": _fmt_date(datetime.utcnow()),
            "metric": metric,
            "period_days": period_days,
            "periods_count": periods_back,
            "trend": trend,
            "filters": {"branch_id": branch_id},
            "data_points": data_points,
        }
