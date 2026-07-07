"""
Build script for creating executable packages.

Usage:
    python build_exe.py [options]

Options:
    --onefile    Build as single executable file
    --onedir     Build as directory (default)
    --clean      Clean build artifacts before building
    --dist       Create a distributable package after building

Note:
    PyInstaller builds are platform-specific. Build the Windows .exe on
    Windows, the Linux binary on Linux, and the macOS app/binary on macOS.
"""

import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path


APP_NAME = 'SGIMI_TECNOGAS'


def normalize_target(target=None):
    """Normalize a target platform name to a PyInstaller-friendly value."""
    if target is None:
        target = platform.system()

    aliases = {
        'windows': 'windows',
        'win': 'windows',
        'win32': 'windows',
        'mac': 'darwin',
        'macos': 'darwin',
        'osx': 'darwin',
        'darwin': 'darwin',
        'linux': 'linux',
        'linux2': 'linux',
    }
    return aliases.get(str(target).strip().lower(), str(target).strip().lower())


def get_host_target():
    """Return the normalized platform for the current host."""
    return normalize_target(platform.system())


def get_output_name(target=None):
    """Return the expected output name for the requested platform."""
    target = normalize_target(target)
    if target == 'windows':
        return f'{APP_NAME}.exe'
    if target == 'darwin':
        return f'{APP_NAME}.app'
    return APP_NAME


def validate_build_environment():
    """Validate that the active Python environment can build the desktop app."""
    try:
        import PyInstaller  # noqa: F401
        from PyQt6 import QtCore  # noqa: F401
        import sqlalchemy  # noqa: F401
    except Exception as exc:
        print("Build environment is not ready.")
        print("Use Python 3.11 or 3.12 with dependencies installed from requirements.txt.")
        print(f"Import error: {exc}")
        return False

    return True


def clean_build():
    """Clean build artifacts."""
    print("Cleaning build artifacts...")

    dirs_to_clean = ['build', 'dist', '__pycache__']
    ignored_dirs = {'.git', '.venv', 'venv', 'temp_pyqt_env', 'temp_pyqt_env_311', 'node_modules'}

    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"Removed: {dir_name}")

    # Remove __pycache__ directories recursively
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        if '__pycache__' in dirs:
            cache_dir = os.path.join(root, '__pycache__')
            shutil.rmtree(cache_dir)
            print(f"Removed: {cache_dir}")

    print("Clean complete.")


def build_executable(onefile=False, target=None):
    """
    Build executable using PyInstaller for the requested target platform.

    Args:
        onefile: If True, build single executable file
        target: Platform target (windows, darwin, linux)
    """
    target = normalize_target(target)
    host_target = get_host_target()
    print("Building SGIMI TECNOGAS executable...")
    print(f"Target platform: {target}")
    print(f"Host platform: {platform.system()} {platform.architecture()[0]}")

    if target != host_target:
        print(
            "Cross-platform PyInstaller builds are not supported. "
            f"Run this build on {target} to generate that platform's package."
        )
        return False

    project_root = Path(__file__).resolve().parent
    dist_dir = project_root / 'dist' / f'{APP_NAME}_Distribution_{target}'
    spec_dir = project_root / 'build' / 'spec'
    dist_dir.mkdir(parents=True, exist_ok=True)
    spec_dir.mkdir(parents=True, exist_ok=True)

    if not validate_build_environment():
        return False

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

    cmd.append('--windowed')
    cmd.extend(['--name', APP_NAME])
    cmd.extend(['--distpath', str(dist_dir)])
    cmd.extend(['--specpath', str(spec_dir)])

    # Add icon based on platform
    icon_path = project_root / 'assets'
    if target == 'windows':
        icon_file = icon_path / 'icon.ico'
        if icon_file.exists():
            cmd.extend(['--icon', str(icon_file)])
    elif target == 'darwin':
        cmd.extend(['--osx-bundle-identifier', 'com.tecnogas.sgimi'])
        icon_file = icon_path / 'icon_temp.png'
        if icon_file.exists():
            cmd.extend(['--icon', str(icon_file)])
    elif target == 'linux':
        icon_file = icon_path / 'icon.png'
        if icon_file.exists():
            cmd.extend(['--icon', str(icon_file)])

    hidden_imports = [
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'sqlalchemy',
        'dateutil',
        'modules.alerts.routes',
        'modules.history.routes',
        'modules.reports.routes',
    ]

    for imp in hidden_imports:
        cmd.extend(['--hidden-import', imp])

    excludes = ['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy']
    for exc in excludes:
        cmd.extend(['--exclude-module', exc])

    cmd.append(str(project_root / 'main.py'))

    print(f"Command: {' '.join(cmd[:10])}...")
    print("Building...")

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(project_root))

    if result.returncode != 0:
        print("Build failed!")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        return False

    output_name = get_output_name(target)
    print("Build successful!")
    print(f"Output location: {dist_dir / output_name}")

    return True


def create_distribution_package(target=None, onefile=False):
    """
    Create distribution package with README, LICENSE, and config template.
    The executable is already in the distribution directory from the build step.
    """
    target = normalize_target(target)
    project_root = Path(__file__).resolve().parent
    dist_dir = Path(f'dist/{APP_NAME}_Distribution_{target}')
    
    output_name = get_output_name(target)
    exe_path = dist_dir / output_name

    if not exe_path.exists():
        print("No executable found. Build first.")
        return False

    print("Adding distribution files...")

    # Copy LICENSE file if exists
    license_file = project_root / 'LICENSE'
    if license_file.exists():
        shutil.copy2(license_file, dist_dir / 'LICENSE.txt')
        print("LICENSE file included in distribution.")

    # Create README
    readme_content = """# SGIMI TECNOGAS
## Sistema de Gestion de Inventario Multi-Sucursal

### Instalacion
1. Descomprima el archivo descargado
2. Ejecute SGIMI_TECNOGAS.exe (Windows) o SGIMI_TECNOGAS (Linux/macOS)

### Primer Uso
Al abrir la aplicacion por primera vez, cree el usuario inicial con datos reales.

### Datos de la Aplicacion
La base de datos y los logs se guardan en la carpeta de datos del usuario del sistema operativo.
Esto permite ejecutar la aplicacion desde ubicaciones protegidas sin permisos de escritura.

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
# URL de la base de datos. Si se omite, la aplicacion usa la carpeta de datos del usuario.
URL =

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
    args = sys.argv[1:]

    print("=" * 60)
    print("SGIMI TECNOGAS - Build Script")
    print("=" * 60)

    clean = False
    onefile = False
    create_dist = False
    target = None
    parsed_args = []

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == '--clean':
            clean = True
        elif arg == '--onefile':
            onefile = True
        elif arg == '--onedir':
            onefile = False
        elif arg == '--dist':
            create_dist = True
        elif arg == '--target':
            if i + 1 >= len(args):
                raise SystemExit('Missing value for --target')
            target = args[i + 1]
            i += 1
        elif arg.startswith('--target='):
            target = arg.split('=', 1)[1]
        else:
            parsed_args.append(arg)
        i += 1

    if clean:
        clean_build()

    if build_executable(onefile=onefile, target=target):
        if create_dist:
            create_distribution_package(target=target, onefile=onefile)

        print("\n" + "=" * 60)
        print("Build complete!")
        print("=" * 60)
        return 0

    print("\nBuild failed!")
    return 1


if __name__ == '__main__':
    sys.exit(main())
