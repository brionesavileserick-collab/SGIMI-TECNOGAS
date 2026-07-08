# -*- mode: python ; coding: utf-8 -*-
"""
Portable PyInstaller spec for SGIMI TECNOGAS.

Use build_exe.py for normal builds. This file is kept as a source-controlled
fallback and intentionally avoids machine-specific absolute paths.
"""

from pathlib import Path


project_root = Path.cwd()
icon_path = project_root / "assets" / "icon.ico"
icon_arg = [str(icon_path)] if icon_path.exists() else None

hiddenimports = [
    "PyQt6",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "sqlalchemy",
    "dateutil",
    "modules.alerts.routes",
    "modules.alerts.handlers",
    "modules.alerts.service",
    "modules.history.routes",
    "modules.history.handlers",
    "modules.history.service",
    "modules.reports.routes",
    "modules.dashboard.routes",
    "modules.dashboard.handlers",
    "modules.dashboard.service",
    "modules.products.routes",
    "modules.products.service",
    "modules.branches.routes",
    "modules.branches.service",
    "modules.inventory.routes",
    "modules.inventory.handlers",
    "modules.inventory.service",
    "modules.movements.routes",
    "modules.movements.handlers",
    "modules.movements.service",
    "modules.communication.routes",
    "modules.communication.handlers",
    "modules.communication.service",
    "modules.communication.models",
    "modules.user.routes",
    "modules.user.service",
    "core.settings",
    "core.database",
    "core.event_bus",
    "core.operation_mode",
]

a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "scipy"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SGIMI_TECNOGAS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_arg,
)
