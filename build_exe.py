"""
Build script for creating executable packages.

Usage:
    python build_exe.py [options]

Options:
    --onefile    Build as single executable file
    --onedir     Build as directory (default)
    --clean      Clean build artifacts before building
    --all        Build for all platforms (requires appropriate tools)
"""

import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path


def clean_build():
    """Clean build artifacts."""
    print("Cleaning build artifacts...")

    dirs_to_clean = ['build', 'dist', '__pycache__']
    files_to_clean = ['*.spec']

    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"Removed: {dir_name}")

    # Remove __pycache__ directories recursively
    for root, dirs, files in os.walk('.'):
        if '__pycache__' in dirs:
            cache_dir = os.path.join(root, '__pycache__')
            shutil.rmtree(cache_dir)
            print(f"Removed: {cache_dir}")

    print("Clean complete.")


def build_executable(onefile=False):
    """
    Build executable using PyInstaller.

    Args:
        onefile: If True, build single executable file
    """
    print("Building SGIMI TECNOGAS executable...")
    print(f"Platform: {platform.system()} {platform.architecture()[0]}")

    # Build command
    cmd = [
        sys.executable,
        '-m',
        'PyInstaller',
        '--clean',
        '--noconfirm',
    ]

    if onefile:
        cmd.append('--onefile')
        print("Building as single executable file...")
    else:
        cmd.append('--onedir')
        print("Building as directory...")

    # Add windowed mode (no console)
    cmd.append('--windowed')

    # Add name
    cmd.extend(['--name', 'SGIMI_TECNOGAS'])

    # Add data files (if needed)
    # cmd.extend(['--add-data', 'data;data'])

    # Add hidden imports
    hidden_imports = [
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'sqlalchemy',
        'dateutil',
    ]

    for imp in hidden_imports:
        cmd.extend(['--hidden-import', imp])

    # Exclude unnecessary modules
    excludes = ['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy']
    for exc in excludes:
        cmd.extend(['--exclude-module', exc])

    # Add main script
    cmd.append('main.py')

    print(f"Command: {' '.join(cmd[:10])}...")
    print("Building...")

    # Run PyInstaller
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("Build failed!")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        return False

    print("Build successful!")
    print(f"Output location: dist/SGIMI_TECNOGAS")

    return True


def create_distribution_package():
    """
    Create distribution package with executable, README, and LICENSE.
    """
    dist_dir = Path('dist/SGIMI_TECNOGAS_Distribution')
    exe_dir = Path('dist/SGIMI_TECNOGAS')

    if not exe_dir.exists():
        print("No executable found. Build first.")
        return False

    print("Creating distribution package...")

    # Create distribution directory
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    dist_dir.mkdir(parents=True)

    # Copy executable
    shutil.copytree(exe_dir, dist_dir / 'Application')

    # Create README
    readme_content = """# SGIMI TECNOGAS
## Sistema de Gestion de Inventario Multi-Sucursal

### Instalacion
1. Descomprima el archivo descargado
2. Ejecute SGIMI_TECNOGAS.exe (Windows) o SGIMI_TECNOGAS (Linux/Mac)

### Primer Uso
- Usuario por defecto: admin@tecnogas.com
- Contrasena: admin123

### Soporte
Para soporte tecnico, contacte a soporte@tecnogas.com

### Licencia
Este software es propiedad de TECNOGAS. Uso interno autorizado.
Version: 1.0.0
"""

    readme_path = dist_dir / 'README.txt'
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)

    # Create config template
    config_content = """# Archivo de configuracion de SGIMI TECNOGAS
# Copie este archivo a la misma ubicacion del ejecutable si necesita personalizar

[DATABASE]
# URL de la base de datos (SQLite por defecto)
URL = sqlite:///sgimi_tecnogas.db

[LOGGING]
# Nivel de registro: DEBUG, INFO, WARNING, ERROR
LEVEL = INFO

[INVENTORY]
# Umbral de stock bajo
LOW_STOCK_THRESHOLD = 10

# Tolerancia de discrepancia (porcentaje)
DISCREPANCY_THRESHOLD = 5
"""

    config_path = dist_dir / 'config_template.ini'
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(config_content)

    print(f"Distribution package created: {dist_dir}")
    return True


def main():
    """Main build script."""
    # Parse arguments
    args = sys.argv[1:]

    print("=" * 60)
    print("SGIMI TECNOGAS - Build Script")
    print("=" * 60)

    # Handle options
    clean = '--clean' in args
    onefile = '--onefile' in args
    create_dist = '--dist' in args

    # Remove options from args
    for opt in ['--clean', '--onefile', '--onedir', '--dist']:
        if opt in args:
            args.remove(opt)

    # Clean if requested
    if clean:
        clean_build()

    # Build executable
    if build_executable(onefile=onefile):
        # Create distribution package if requested
        if create_dist:
            create_distribution_package()

        print("\n" + "=" * 60)
        print("Build complete!")
        print("=" * 60)
        return 0

    print("\nBuild failed!")
    return 1


if __name__ == '__main__':
    sys.exit(main())
