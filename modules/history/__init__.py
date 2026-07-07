"""
History module.

Public surface:
  - HistoryService          – service layer (record, query, archive, enrich)
  - HistoryEntry            – ORM model (history table)
  - ArchiveHistory          – ORM model (archive_history table)
  - HistoryHandlers         – event handler class
  - setup_history_handlers  – factory used by main.py
  - HistoryView             – root Qt widget (tabs: General + Movimientos por Producto)
  - HistoryListView         – main history tab widget (accessible for embedding)
"""

from modules.history.service import HistoryService, HistoryEntry, ArchiveHistory
from modules.history.handlers import HistoryHandlers, setup_history_handlers
from modules.history.routes import HistoryView, HistoryListView

__all__ = [
    "HistoryService",
    "HistoryEntry",
    "ArchiveHistory",
    "HistoryHandlers",
    "setup_history_handlers",
    "HistoryView",
    "HistoryListView",
]
