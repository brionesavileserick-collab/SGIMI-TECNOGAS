"""
Operation Mode — singleton that tracks whether the application is running
in MATRIX mode (full cross-branch visibility) or BRANCH mode (scoped to one
specific branch).

Design notes
────────────
- Pure-Python singleton: no PyQt dependency at module import time, so it
  can be imported safely from service / repository layers too.
- PyQt6 QObject mixin is only activated once the QApplication exists; the
  views call `OperationMode.instance()` which initialises the QObject side
  lazily on first access inside a Qt context.
- All views subscribe to `mode_changed` signal and reload their data.

Usage
─────
    from core.operation_mode import operation_mode

    # Switch to branch mode
    operation_mode.set_branch_mode(branch_id=3, branch_name="Norte")

    # Switch to matrix (global) mode
    operation_mode.set_matrix_mode()

    # Read current state
    if operation_mode.is_matrix:
        ...
    branch_id = operation_mode.current_branch_id   # None when matrix mode
"""

from __future__ import annotations
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# ── Mode constants ──────────────────────────────────────────────────────────
MODE_MATRIX = "matrix"
MODE_BRANCH = "branch"


class _OperationMode:
    """
    Singleton operation-mode manager.

    Stores the current mode and active branch, and notifies registered
    callbacks whenever either changes.  Qt signals are *not* used here to
    keep this class importable without a running QApplication; views wire
    themselves up via `subscribe()`.
    """

    _instance: Optional["_OperationMode"] = None

    def __new__(cls) -> "_OperationMode":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    # ── Initialisation ──────────────────────────────────────────────────
    def _init(self) -> None:
        self._mode: str = MODE_MATRIX
        self._branch_id: Optional[int] = None
        self._branch_name: Optional[str] = None
        self._callbacks: list = []

    # ── Properties ──────────────────────────────────────────────────────
    @property
    def mode(self) -> str:
        return self._mode

    @property
    def is_matrix(self) -> bool:
        return self._mode == MODE_MATRIX

    @property
    def is_branch(self) -> bool:
        return self._mode == MODE_BRANCH

    @property
    def current_branch_id(self) -> Optional[int]:
        """Return the active branch id, or None when in matrix mode."""
        return self._branch_id

    @property
    def current_branch_name(self) -> Optional[str]:
        """Return the active branch display name, or None when in matrix mode."""
        return self._branch_name

    # ── Mutators ────────────────────────────────────────────────────────
    def set_matrix_mode(self) -> None:
        """Switch to matrix (global) mode."""
        changed = self._mode != MODE_MATRIX or self._branch_id is not None
        self._mode = MODE_MATRIX
        self._branch_id = None
        self._branch_name = None
        if changed:
            logger.info("Operation mode → MATRIX")
            self._notify()

    def set_branch_mode(
        self, branch_id: int, branch_name: str = ""
    ) -> None:
        """Switch to branch mode, scoping all views to *branch_id*."""
        if branch_id <= 0:
            raise ValueError("branch_id must be a positive integer")
        changed = (
            self._mode != MODE_BRANCH
            or self._branch_id != branch_id
        )
        self._mode = MODE_BRANCH
        self._branch_id = branch_id
        self._branch_name = branch_name or str(branch_id)
        if changed:
            logger.info(
                f"Operation mode → BRANCH  id={branch_id}  name={self._branch_name}"
            )
            self._notify()

    # ── Observer pattern ────────────────────────────────────────────────
    def subscribe(self, callback) -> None:
        """
        Register *callback* to be called whenever the mode changes.
        callback signature: callback(mode: str, branch_id: int | None)
        """
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def unsubscribe(self, callback) -> None:
        """Remove a previously registered callback."""
        try:
            self._callbacks.remove(callback)
        except ValueError:
            pass

    def _notify(self) -> None:
        for cb in list(self._callbacks):
            try:
                cb(self._mode, self._branch_id)
            except Exception as exc:
                logger.error(f"OperationMode callback error: {exc}")

    # ── Display helpers ──────────────────────────────────────────────────
    def label(self) -> str:
        """Short human-readable label for toolbar / status bar display."""
        if self.is_matrix:
            return "🌐 Modo: Matriz"
        return f"🏢 Modo: Sucursal — {self._branch_name}"

    def __repr__(self) -> str:
        return (
            f"<OperationMode mode={self._mode} "
            f"branch_id={self._branch_id} "
            f"branch_name={self._branch_name!r}>"
        )


# Module-level singleton — import this everywhere
operation_mode = _OperationMode()
