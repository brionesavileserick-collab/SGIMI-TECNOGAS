"""
History service layer - Records all events for traceability.

Expansions implemented here:
  1 - Filtro por sucursal (branch_id in list_history)
  2 - Detalle expandido (get_entry_details)
  3 - Nombres en vez de IDs (enrich_entry, get_user_name, get_entity_name)
  4 - Diff de cambios (get_change_summary)
  5 - Búsqueda avanzada en details (search_in_details)
  6 - Historial de movimientos por producto (get_product_movement_history)
  7 - Respaldo / archivado (archive_history, get_archived_history)
  8 - Integridad referencial (sanitize_entry, cleanup_orphaned_references)
  9 - Logs del sistema (record_system_event, record_login, record_logout,
                        record_error, record_config_change)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from core.database import Base

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# ORM Models
# ══════════════════════════════════════════════════════════════════════════════

class HistoryEntry(Base):
    """Registro principal del historial de eventos del sistema."""

    __tablename__ = "history"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(50), nullable=True)  # product | movement | inventory | branch | alert | system
    entity_id = Column(Integer, nullable=True)
    user_id = Column(Integer, nullable=True)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)            # JSON string con payload completo
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _parsed_details(self) -> Optional[Dict[str, Any]]:
        """Parse details JSON; returns dict or None on failure."""
        if not self.details:
            return None
        try:
            return json.loads(self.details)
        except (json.JSONDecodeError, TypeError):
            return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert history entry to dictionary."""
        return {
            "id": self.id,
            "event_type": self.event_type,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "user_id": self.user_id,
            "action": self.action,
            "details": self._parsed_details(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ArchiveHistory(Base):
    """
    Expansión 7 - Tabla de archivo.
    Misma estructura que history; se rellena antes de la limpieza de registros antiguos.
    """

    __tablename__ = "archive_history"

    id = Column(Integer, primary_key=True, index=True)
    original_id = Column(Integer, nullable=False, index=True)   # id en history original
    event_type = Column(String(100), nullable=False, index=True)
    entity_type = Column(String(50), nullable=True)
    entity_id = Column(Integer, nullable=True)
    user_id = Column(Integer, nullable=True)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=True)
    archived_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        details = None
        if self.details:
            try:
                details = json.loads(self.details)
            except (json.JSONDecodeError, TypeError):
                details = self.details
        return {
            "id": self.id,
            "original_id": self.original_id,
            "event_type": self.event_type,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "user_id": self.user_id,
            "action": self.action,
            "details": details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
        }


# ══════════════════════════════════════════════════════════════════════════════
# Service
# ══════════════════════════════════════════════════════════════════════════════

class HistoryService:
    """Service for history/audit trail management."""

    # Tipos de entidad reconocidos para resolución de nombres
    _ENTITY_TABLES = {
        "product":   ("products",  "name"),
        "branch":    ("branches",  "name"),
        "user":      ("users",     "name"),
        "movement":  ("movements", "id"),   # los movimientos no tienen nombre propio
        "inventory": ("inventory", "id"),
        "alert":     ("alerts",    "title"),
    }

    def __init__(self, db: Session):
        self.db = db

    # ─────────────────────────────────────────────────────────────────────────
    # Escritura
    # ─────────────────────────────────────────────────────────────────────────

    def record_event(
        self,
        event_type: str,
        entity_type: str = None,
        entity_id: int = None,
        user_id: int = None,
        action: str = None,
        details: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Record an event in history."""
        entry = HistoryEntry(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            action=action or event_type,
            details=json.dumps(details) if details else None,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        logger.info(f"History recorded: {event_type}")
        return entry.to_dict()

    # ─────────────────────────────────────────────────────────────────────────
    # Expansión 9 – Logs del sistema
    # ─────────────────────────────────────────────────────────────────────────

    def record_system_event(
        self,
        event_type: str,
        action: str,
        details: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Record a system-level event (no entity_type / entity_id).

        event_type examples: "session_start", "session_end", "error",
                             "config_change", "backup", "login", "logout"
        """
        return self.record_event(
            event_type=event_type,
            entity_type="system",
            entity_id=None,
            user_id=None,
            action=action,
            details=details,
        )

    def record_login(self, user_id: int, user_name: str = None) -> Dict[str, Any]:
        """Record a user login event."""
        return self.record_event(
            event_type="session.login",
            entity_type="system",
            entity_id=None,
            user_id=user_id,
            action=f"Inicio de sesión: {user_name or user_id}",
            details={"user_id": user_id, "user_name": user_name},
        )

    def record_logout(self, user_id: int, user_name: str = None) -> Dict[str, Any]:
        """Record a user logout event."""
        return self.record_event(
            event_type="session.logout",
            entity_type="system",
            entity_id=None,
            user_id=user_id,
            action=f"Cierre de sesión: {user_name or user_id}",
            details={"user_id": user_id, "user_name": user_name},
        )

    def record_error(self, error_message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Record an application error."""
        details = {"error": error_message}
        if context:
            details.update(context)
        return self.record_system_event(
            event_type="system.error",
            action=f"Error del sistema: {error_message[:80]}",
            details=details,
        )

    def record_config_change(
        self, setting_name: str, old_value: Any, new_value: Any, user_id: int = None
    ) -> Dict[str, Any]:
        """Record a configuration change."""
        entry = self.record_event(
            event_type="system.config_change",
            entity_type="system",
            entity_id=None,
            user_id=user_id,
            action=f"Configuración modificada: {setting_name}",
            details={
                "setting": setting_name,
                "changes": {setting_name: {"before": old_value, "after": new_value}},
            },
        )
        return entry

    # ─────────────────────────────────────────────────────────────────────────
    # Lectura individual
    # ─────────────────────────────────────────────────────────────────────────

    def get_entry(self, entry_id: int) -> Optional[Dict[str, Any]]:
        """Get history entry by ID."""
        entry = self.db.query(HistoryEntry).filter(HistoryEntry.id == entry_id).first()
        return entry.to_dict() if entry else None

    # ─────────────────────────────────────────────────────────────────────────
    # Expansión 2 – Detalle expandido
    # ─────────────────────────────────────────────────────────────────────────

    def get_entry_details(self, entry_id: int) -> Optional[Dict[str, Any]]:
        """
        Return a single history entry with its details JSON parsed and
        the change summary pre-computed.
        """
        entry = self.db.query(HistoryEntry).filter(HistoryEntry.id == entry_id).first()
        if not entry:
            return None

        result = entry.to_dict()
        result["change_summary"] = self.get_change_summary(result)
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Expansión 4 – Diff de cambios
    # ─────────────────────────────────────────────────────────────────────────

    def get_change_summary(self, entry: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Extract the "before / after" diff from an entry's details.

        Expects details to contain a "changes" key structured as:
            { "field_name": {"before": old_val, "after": new_val} }
        or the flat format some services use:
            { "changes": { "field": value_after } }  ← shows only new value

        Returns a list of dicts: [{"campo": ..., "antes": ..., "despues": ...}]
        If no diff data is available, returns an empty list.
        """
        details = entry.get("details") if isinstance(entry, dict) else None
        if not details or not isinstance(details, dict):
            return []

        raw_changes = details.get("changes")
        if not raw_changes or not isinstance(raw_changes, dict):
            return []

        rows: List[Dict[str, str]] = []
        for field, value in raw_changes.items():
            if isinstance(value, dict) and ("before" in value or "after" in value):
                rows.append({
                    "campo": field,
                    "antes": str(value.get("before", "—")),
                    "despues": str(value.get("after", "—")),
                })
            else:
                # Flat format: only the new value is known
                rows.append({
                    "campo": field,
                    "antes": "—",
                    "despues": str(value),
                })
        return rows

    # ─────────────────────────────────────────────────────────────────────────
    # Expansión 3 – Nombres en vez de IDs
    # ─────────────────────────────────────────────────────────────────────────

    def get_user_name(self, user_id: int) -> str:
        """Resolve a user_id to a human-readable name."""
        if not user_id:
            return "—"
        try:
            from models.user import User
            user = self.db.query(User).filter(User.id == user_id).first()
            if user:
                return user.name
        except Exception as exc:
            logger.debug(f"get_user_name({user_id}): {exc}")
        return f"Usuario #{user_id}"

    def get_entity_name(self, entity_type: str, entity_id: int) -> str:
        """
        Resolve (entity_type, entity_id) to a human-readable name.
        Falls back gracefully if the entity no longer exists.
        """
        if not entity_type or not entity_id:
            return "—"
        if entity_type == "system":
            return "Sistema"
        try:
            from sqlalchemy import text
            table_info = self._ENTITY_TABLES.get(entity_type)
            if not table_info:
                return f"{entity_type} #{entity_id}"
            table, name_col = table_info
            if name_col == "id":
                return f"{entity_type.capitalize()} #{entity_id}"
            row = self.db.execute(
                text(f"SELECT {name_col} FROM {table} WHERE id = :eid"),
                {"eid": entity_id},
            ).fetchone()
            if row and row[0]:
                return str(row[0])
            return f"{entity_type.capitalize()} #{entity_id} (eliminado)"
        except Exception as exc:
            logger.debug(f"get_entity_name({entity_type}, {entity_id}): {exc}")
            return f"{entity_type} #{entity_id}"

    def enrich_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Augment a history entry dict with resolved human-readable names:
          - user_name  (from user_id)
          - entity_name (from entity_type + entity_id)

        The original entry dict is NOT mutated; a new dict is returned.
        """
        enriched = dict(entry)
        enriched["user_name"] = self.get_user_name(entry.get("user_id"))
        enriched["entity_name"] = self.get_entity_name(
            entry.get("entity_type"), entry.get("entity_id")
        )
        return enriched

    # ─────────────────────────────────────────────────────────────────────────
    # Expansión 1 – Filtro por sucursal  +  Listado principal
    # ─────────────────────────────────────────────────────────────────────────

    def list_history(
        self,
        skip: int = 0,
        limit: int = 100,
        event_type: str = None,
        entity_type: str = None,
        entity_id: int = None,
        user_id: int = None,
        branch_id: int = None,          # Expansión 1
        date_from: datetime = None,
        date_to: datetime = None,
        enrich: bool = False,           # Expansión 3
    ) -> Dict[str, Any]:
        """
        List history entries with filtering.

        branch_id (Expansión 1):
            Filtra entradas donde el campo details JSON contenga
            "branch_id": <branch_id>.  Aplica OR sobre los campos
            branch_id y destination_branch_id para capturar
            transferencias.

        enrich (Expansión 3):
            Si True, cada entrada lleva user_name y entity_name resueltos.
        """
        query = self.db.query(HistoryEntry)

        if event_type:
            query = query.filter(HistoryEntry.event_type == event_type)

        if entity_type:
            query = query.filter(HistoryEntry.entity_type == entity_type)

        if entity_id:
            query = query.filter(HistoryEntry.entity_id == entity_id)

        if user_id:
            query = query.filter(HistoryEntry.user_id == user_id)

        if date_from:
            query = query.filter(HistoryEntry.created_at >= date_from)

        if date_to:
            query = query.filter(HistoryEntry.created_at <= date_to)

        # Expansión 1 – filtro por sucursal sobre el campo JSON details
        if branch_id is not None:
            branch_pattern = f'%"branch_id": {branch_id}%'
            dest_pattern = f'%"destination_branch_id": {branch_id}%'
            from sqlalchemy import or_
            query = query.filter(
                or_(
                    HistoryEntry.details.ilike(branch_pattern),
                    HistoryEntry.details.ilike(dest_pattern),
                )
            )

        total = query.count()
        entries_orm = (
            query.order_by(HistoryEntry.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        entries = [e.to_dict() for e in entries_orm]
        if enrich:
            entries = [self.enrich_entry(e) for e in entries]

        return {
            "entries": entries,
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Búsquedas
    # ─────────────────────────────────────────────────────────────────────────

    def get_entity_history(self, entity_type: str, entity_id: int) -> List[Dict[str, Any]]:
        """Get complete history for an entity."""
        entries = (
            self.db.query(HistoryEntry)
            .filter(
                HistoryEntry.entity_type == entity_type,
                HistoryEntry.entity_id == entity_id,
            )
            .order_by(HistoryEntry.created_at.desc())
            .all()
        )
        return [e.to_dict() for e in entries]

    def search_history(
        self,
        search_term: str,
        limit: int = 50,
        search_in_details: bool = False,   # Expansión 5
        enrich: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Search history entries.

        search_in_details (Expansión 5):
            If True, also searches inside the details JSON column so any
            matching JSON field value surfaces the row.
        """
        from sqlalchemy import or_
        conditions = [HistoryEntry.action.ilike(f"%{search_term}%")]
        if search_in_details:
            conditions.append(HistoryEntry.details.ilike(f"%{search_term}%"))

        entries = (
            self.db.query(HistoryEntry)
            .filter(or_(*conditions))
            .order_by(HistoryEntry.created_at.desc())
            .limit(limit)
            .all()
        )
        result = [e.to_dict() for e in entries]
        if enrich:
            result = [self.enrich_entry(e) for e in result]
        return result

    # Expansión 5 – método dedicado
    def search_in_details(self, search_term: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search inside the details JSON column exclusively.
        Useful when looking for a specific product name, SKU, reason, etc.
        """
        entries = (
            self.db.query(HistoryEntry)
            .filter(HistoryEntry.details.ilike(f"%{search_term}%"))
            .order_by(HistoryEntry.created_at.desc())
            .limit(limit)
            .all()
        )
        return [e.to_dict() for e in entries]

    def get_user_activity(self, user_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get activity history for a user."""
        entries = (
            self.db.query(HistoryEntry)
            .filter(HistoryEntry.user_id == user_id)
            .order_by(HistoryEntry.created_at.desc())
            .limit(limit)
            .all()
        )
        return [e.to_dict() for e in entries]

    # ─────────────────────────────────────────────────────────────────────────
    # Expansión 6 – Historial de movimientos por producto
    # ─────────────────────────────────────────────────────────────────────────

    def get_product_movement_history(
        self,
        product_id: int,
        limit: int = 200,
        date_from: datetime = None,
        date_to: datetime = None,
    ) -> List[Dict[str, Any]]:
        """
        Return all history entries where entity_type='movement' and the
        details JSON contains the given product_id.

        This covers entries emitted by MOVEMENT_CREATED, MOVEMENT_VALIDATED,
        MOVEMENT_REJECTED, MOVEMENT_CANCELLED, MOVEMENT_REVERSED, TRANSFER_SENT,
        and TRANSFER_RECEIVED — all of which include product_id in their payload.
        """
        pattern = f'%"product_id": {product_id}%'
        query = (
            self.db.query(HistoryEntry)
            .filter(
                HistoryEntry.entity_type == "movement",
                HistoryEntry.details.ilike(pattern),
            )
        )
        if date_from:
            query = query.filter(HistoryEntry.created_at >= date_from)
        if date_to:
            query = query.filter(HistoryEntry.created_at <= date_to)

        entries = query.order_by(HistoryEntry.created_at.desc()).limit(limit).all()
        return [e.to_dict() for e in entries]

    # ─────────────────────────────────────────────────────────────────────────
    # Expansión 8 – Integridad referencial
    # ─────────────────────────────────────────────────────────────────────────

    def sanitize_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check whether the entity referenced by an entry still exists.
        Adds an "entity_deleted" boolean flag to the dict.
        If the entity is gone, the original details are preserved for audit.
        """
        entity_type = entry.get("entity_type")
        entity_id = entry.get("entity_id")

        # System entries have no entity to check
        if not entity_type or entity_type == "system" or not entity_id:
            entry["entity_deleted"] = False
            return entry

        table_info = self._ENTITY_TABLES.get(entity_type)
        if not table_info:
            entry["entity_deleted"] = False
            return entry

        try:
            from sqlalchemy import text
            table, _ = table_info
            row = self.db.execute(
                text(f"SELECT id FROM {table} WHERE id = :eid"),
                {"eid": entity_id},
            ).fetchone()
            entry["entity_deleted"] = row is None
        except Exception as exc:
            logger.debug(f"sanitize_entry check failed: {exc}")
            entry["entity_deleted"] = False

        return entry

    def cleanup_orphaned_references(self) -> int:
        """
        Scan all history entries and tag (via the in-memory dict) those
        whose entity no longer exists.  Because we never mutate history rows,
        this method returns the COUNT of orphaned entries found.

        Use this to understand data integrity; the UI displays the "(Eliminado)"
        badge per entry using sanitize_entry().
        """
        entries = self.db.query(HistoryEntry).all()
        orphan_count = 0
        for entry in entries:
            result = self.sanitize_entry(entry.to_dict())
            if result.get("entity_deleted"):
                orphan_count += 1
        logger.info(f"Orphaned history references found: {orphan_count}")
        return orphan_count

    # ─────────────────────────────────────────────────────────────────────────
    # Limpieza
    # ─────────────────────────────────────────────────────────────────────────

    def clear_old_history(self, days: int = 90) -> int:
        """Clear history entries older than specified days."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        count = (
            self.db.query(HistoryEntry)
            .filter(HistoryEntry.created_at < cutoff)
            .delete()
        )
        self.db.commit()
        logger.info(f"Cleared {count} old history entries")
        return count

    # ─────────────────────────────────────────────────────────────────────────
    # Expansión 7 – Respaldo / archivado antes de limpieza
    # ─────────────────────────────────────────────────────────────────────────

    def archive_history(self, date_from: datetime = None, date_to: datetime = None) -> int:
        """
        Copy matching history entries into archive_history, then delete them
        from the live history table.

        If neither date_from nor date_to are given, nothing is archived (safety
        guard to prevent accidental full-archive).

        Returns the number of entries archived.
        """
        if date_from is None and date_to is None:
            logger.warning("archive_history called with no date range — skipped")
            return 0

        query = self.db.query(HistoryEntry)
        if date_from:
            query = query.filter(HistoryEntry.created_at >= date_from)
        if date_to:
            query = query.filter(HistoryEntry.created_at <= date_to)

        entries = query.all()
        if not entries:
            return 0

        archived = []
        for entry in entries:
            archived.append(ArchiveHistory(
                original_id=entry.id,
                event_type=entry.event_type,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                user_id=entry.user_id,
                action=entry.action,
                details=entry.details,
                created_at=entry.created_at,
            ))

        self.db.bulk_save_objects(archived)

        # Delete from live table
        ids_to_delete = [e.id for e in entries]
        self.db.query(HistoryEntry).filter(HistoryEntry.id.in_(ids_to_delete)).delete(
            synchronize_session=False
        )

        self.db.commit()
        logger.info(f"Archived {len(entries)} history entries")
        return len(entries)

    def get_archived_history(
        self,
        skip: int = 0,
        limit: int = 100,
        date_from: datetime = None,
        date_to: datetime = None,
    ) -> Dict[str, Any]:
        """Query the archive table."""
        query = self.db.query(ArchiveHistory)
        if date_from:
            query = query.filter(ArchiveHistory.created_at >= date_from)
        if date_to:
            query = query.filter(ArchiveHistory.created_at <= date_to)

        total = query.count()
        entries = (
            query.order_by(ArchiveHistory.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return {
            "entries": [e.to_dict() for e in entries],
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Expansión 10 – Integración con Historial de Configuración de Sucursal (Fase 1)
    # ─────────────────────────────────────────────────────────────────────────

    def record_branch_config_change(
        self,
        branch_id: int,
        field: str,
        old_value: Any,
        new_value: Any,
        changed_by_name: str = None,
        user_id: int = None,
        reason: str = None,
    ) -> Dict[str, Any]:
        """
        Record a branch configuration change in the history.

        This method is called from BranchService when config is modified.
        Allows unified audit trail of all branch config changes.

        Args:
            branch_id: ID of the branch being modified
            field: Field name that changed (e.g., "min_stock", "operational_status")
            old_value: Previous value
            new_value: New value
            changed_by_name: Human-readable name of who made the change
            user_id: User ID (if available)
            reason: Optional reason for the change
        """
        details = {
            "branch_id": branch_id,
            "field": field,
            "changes": {
                field: {
                    "before": old_value,
                    "after": new_value,
                }
            },
        }
        if reason:
            details["reason"] = reason
        if changed_by_name:
            details["changed_by_name"] = changed_by_name

        return self.record_event(
            event_type="branch.config_changed",
            entity_type="branch_config",
            entity_id=branch_id,
            user_id=user_id,
            action=f"Configuración de sucursal {field}: {old_value} → {new_value}",
            details=details,
        )

    def get_branch_config_history(
        self,
        branch_id: int,
        limit: int = 100,
        date_from: datetime = None,
        date_to: datetime = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all configuration changes for a specific branch.

        Returns entries with entity_type='branch_config' and entity_id=branch_id,
        sorted by date descending.
        """
        query = (
            self.db.query(HistoryEntry)
            .filter(
                HistoryEntry.entity_type == "branch_config",
                HistoryEntry.entity_id == branch_id,
            )
        )
        if date_from:
            query = query.filter(HistoryEntry.created_at >= date_from)
        if date_to:
            query = query.filter(HistoryEntry.created_at <= date_to)

        entries = query.order_by(HistoryEntry.created_at.desc()).limit(limit).all()
        return [e.to_dict() for e in entries]

    # ─────────────────────────────────────────────────────────────────────────
    # Expansión 11 – Filtro por Múltiples Sucursales (Fase 2)
    # Modificación a list_history() para soportar branch_ids (list) además de branch_id (int)
    # ─────────────────────────────────────────────────────────────────────────

    def list_history_with_multi_branch(
        self,
        skip: int = 0,
        limit: int = 100,
        event_type: str = None,
        entity_type: str = None,
        entity_id: int = None,
        user_id: int = None,
        branch_id: int = None,          # Single branch (backward compat)
        branch_ids: List[int] = None,   # Multiple branches
        date_from: datetime = None,
        date_to: datetime = None,
        enrich: bool = False,
    ) -> Dict[str, Any]:
        """
        Extended list_history that supports filtering by multiple branch IDs.

        branch_id: For backward compatibility, single branch filter
        branch_ids: New parameter, list of branch IDs to filter by (OR logic)

        If branch_ids is provided, it takes precedence over branch_id.
        If neither is provided, no branch filtering is applied.
        """
        query = self.db.query(HistoryEntry)

        if event_type:
            query = query.filter(HistoryEntry.event_type == event_type)

        if entity_type:
            query = query.filter(HistoryEntry.entity_type == entity_type)

        if entity_id:
            query = query.filter(HistoryEntry.entity_id == entity_id)

        if user_id:
            query = query.filter(HistoryEntry.user_id == user_id)

        if date_from:
            query = query.filter(HistoryEntry.created_at >= date_from)

        if date_to:
            query = query.filter(HistoryEntry.created_at <= date_to)

        # Multi-branch filter (Expansión 11)
        if branch_ids:
            # Build OR conditions for each branch_id in the list
            from sqlalchemy import or_
            conditions = []
            for bid in branch_ids:
                branch_pattern = f'%"branch_id": {bid}%'
                dest_pattern = f'%"destination_branch_id": {bid}%'
                conditions.append(HistoryEntry.details.ilike(branch_pattern))
                conditions.append(HistoryEntry.details.ilike(dest_pattern))
            if conditions:
                query = query.filter(or_(*conditions))
        elif branch_id is not None:
            # Single branch (backward compat)
            branch_pattern = f'%"branch_id": {branch_id}%'
            dest_pattern = f'%"destination_branch_id": {branch_id}%'
            from sqlalchemy import or_
            query = query.filter(
                or_(
                    HistoryEntry.details.ilike(branch_pattern),
                    HistoryEntry.details.ilike(dest_pattern),
                )
            )

        total = query.count()
        entries_orm = (
            query.order_by(HistoryEntry.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        entries = [e.to_dict() for e in entries_orm]
        if enrich:
            entries = [self.enrich_entry(e) for e in entries]

        return {
            "entries": entries,
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Expansión 12 – Retención Personalizada por Tipo de Entidad (Fase 3)
    # ─────────────────────────────────────────────────────────────────────────

    # Default retention days by entity type
    _DEFAULT_RETENTION: Dict[str, int] = {
        "system": 180,
        "movement": 365,
        "inventory": 180,
        "product": 99999,      # Essentially never (25+ years)
        "branch": 99999,
        "branch_config": 365,
        "alert": 90,
        "user": 99999,
    }

    def get_retention_days(self, entity_type: str) -> int:
        """
        Get retention days for an entity type.

        Checks config.py for RETENTION_DAYS override, falls back to defaults.
        """
        try:
            from config import RETENTION_DAYS
            if entity_type in RETENTION_DAYS:
                return RETENTION_DAYS[entity_type]
        except ImportError:
            pass
        return self._DEFAULT_RETENTION.get(entity_type, 180)

    def clear_by_entity_type(
        self,
        entity_type: str,
        days: int = None,
        move_to_archive: bool = True,
    ) -> Dict[str, int]:
        """
        Clear history entries of a specific entity_type older than specified days.

        If days is None, uses the retention period for that entity_type.
        If move_to_archive is True, archives before deleting.

        Returns: {"archived": count, "deleted": count}
        """
        if days is None:
            days = self.get_retention_days(entity_type)

        cutoff = datetime.utcnow() - timedelta(days=days)

        query = self.db.query(HistoryEntry).filter(
            HistoryEntry.entity_type == entity_type,
            HistoryEntry.created_at < cutoff,
        )

        entries = query.all()
        if not entries:
            return {"archived": 0, "deleted": 0}

        archived_count = 0
        if move_to_archive:
            archived = [
                ArchiveHistory(
                    original_id=e.id,
                    event_type=e.event_type,
                    entity_type=e.entity_type,
                    entity_id=e.entity_id,
                    user_id=e.user_id,
                    action=e.action,
                    details=e.details,
                    created_at=e.created_at,
                )
                for e in entries
            ]
            self.db.bulk_save_objects(archived)
            archived_count = len(entries)

        ids_to_delete = [e.id for e in entries]
        deleted_count = (
            self.db.query(HistoryEntry)
            .filter(HistoryEntry.id.in_(ids_to_delete))
            .delete(synchronize_session=False)
        )
        self.db.commit()

        logger.info(
            f"Cleared {deleted_count} entries of type '{entity_type}' "
            f"(archived {archived_count})"
        )
        return {"archived": archived_count, "deleted": deleted_count}

    def estimate_retention_cleanup(self) -> Dict[str, int]:
        """
        Estimate how many entries would be deleted for each entity_type
        based on current retention policy.

        Useful for showing user estimates before cleanup.
        Returns: {entity_type: count_to_be_deleted, ...}
        """
        estimates = {}
        for entity_type in self._DEFAULT_RETENTION.keys():
            retention_days = self.get_retention_days(entity_type)
            cutoff = datetime.utcnow() - timedelta(days=retention_days)
            count = (
                self.db.query(HistoryEntry)
                .filter(
                    HistoryEntry.entity_type == entity_type,
                    HistoryEntry.created_at < cutoff,
                )
                .count()
            )
            if count > 0:
                estimates[entity_type] = count
        return estimates

    # ─────────────────────────────────────────────────────────────────────────
    # Expansión 13 – Vista de Línea de Tiempo por Entidad (Fase 4)
    # ─────────────────────────────────────────────────────────────────────────

    def get_entity_timeline(
        self,
        entity_type: str,
        entity_id: int,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get complete timeline for a specific entity (chronological order).

        Returns list of entries with additional computed fields:
          - timeline_label: Human-readable event summary
          - timeline_category: Event classification for visual grouping

        Sorted by created_at ascending (earliest first) for timeline view.
        """
        entries = (
            self.db.query(HistoryEntry)
            .filter(
                HistoryEntry.entity_type == entity_type,
                HistoryEntry.entity_id == entity_id,
            )
            .order_by(HistoryEntry.created_at.asc())
            .limit(limit)
            .all()
        )

        result = []
        for entry in entries:
            entry_dict = entry.to_dict()
            # Enrich with timeline-specific fields
            entry_dict["user_name"] = self.get_user_name(entry.user_id)
            entry_dict["timeline_label"] = entry.action or entry.event_type
            # Categorize for UI grouping
            if entry.event_type.startswith("movement"):
                entry_dict["timeline_category"] = "Movimiento"
            elif entry.event_type.startswith("inventory"):
                entry_dict["timeline_category"] = "Inventario"
            elif entry.event_type.startswith("alert"):
                entry_dict["timeline_category"] = "Alerta"
            elif entry.event_type.startswith("product"):
                entry_dict["timeline_category"] = "Producto"
            elif entry.event_type.startswith("branch"):
                entry_dict["timeline_category"] = "Sucursal"
            else:
                entry_dict["timeline_category"] = "Otro"

            result.append(entry_dict)

        return result
