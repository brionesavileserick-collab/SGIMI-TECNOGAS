# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for SGIMI TECNOGAS

Build executable with:
    pyinstaller sgimi_tecnogas.spec

Or build single file with:
    pyinstaller --onefile --windowed --name SGIMI_TECNOGAS main.py
"""

import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# Collect all necessary modules
hiddenimports = [
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'sqlalchemy',
    'sqlalchemy.orm',
    'sqlalchemy.sql',
    'sqlalchemy.sql.schema',
    'sqlalchemy.ext.declarative',
    'dateutil',
    'dateutil.relativedelta',
    'logging',
    'logging.handlers',
    'json',
    'hashlib',
    'secrets',
    'typing',
    'enum',
]

# Add project modules
project_modules = [
    'core',
    'core.event_bus',
    'core.database',
    'core.settings',
    'models',
    'models.user',
    'models.branch',
    'models.product',
    'models.inventory',
    'models.movement',
    'modules',
    'modules.products',
    'modules.products.repository',
    'modules.products.service',
    'modules.products.routes',
    'modules.branches',
    'modules.branches.repository',
    'modules.branches.service',
    'modules.branches.routes',
    'modules.inventory',
    'modules.inventory.repository',
    'modules.inventory.service',
    'modules.inventory.routes',
    'modules.inventory.handlers',
    'modules.movements',
    'modules.movements.repository',
    'modules.movements.service',
    'modules.movements.routes',
    'modules.movements.handlers',
    'modules.dashboard',
    'modules.dashboard.service',
    'modules.dashboard.routes',
    'modules.dashboard.handlers',
    'modules.alerts',
    'modules.alerts.service',
    'modules.alerts.handlers',
    'modules.history',
    'modules.history.service',
    'modules.history.handlers',
    'modules.reports',
    'modules.reports.service',
    'utils',
    'utils.validators',
    'utils.helpers',
    'database',
    'database.seed',
]

hiddenimports.extend(project_modules)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SGIMI_TECNOGAS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Set to False for GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SGIMI_TECNOGAS',
)
