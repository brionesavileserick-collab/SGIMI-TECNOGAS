# Instrucciones de Construcción Multiplataforma

## Windows ✅ (Completado)
El ejecutable de Windows ya ha sido construido y está disponible en:
- `dist/SGIMI_TECNOGAS_Distribution_windows/SGIMI_TECNOGAS/SGIMI_TECNOGAS.exe`
- Archivo ZIP: `dist/SGIMI_TECNOGAS_Windows.zip`

## Linux (Pendiente)
Para construir el ejecutable de Linux, debe ejecutarse en una máquina Linux:

1. Clone el repositorio en una máquina Linux
2. Instale las dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. Ejecute el script de build:
   ```bash
   python build_exe.py --clean --dist
   ```
4. El ejecutable se generará en: `dist/SGIMI_TECNOGAS_Distribution_linux/SGIMI_TECNOGAS/SGIMI_TECNOGAS`
5. Cree el archivo ZIP:
   ```bash
   cd dist
   zip -r SGIMI_TECNOGAS_Linux.zip SGIMI_TECNOGAS_Distribution_linux
   ```

## macOS (Pendiente)
Para construir el ejecutable de macOS, debe ejecutarse en una máquina Mac:

1. Clone el repositorio en una máquina Mac
2. Instale las dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. Ejecute el script de build:
   ```bash
   python build_exe.py --clean --dist
   ```
4. La aplicación se generará en: `dist/SGIMI_TECNOGAS_Distribution_darwin/SGIMI_TECNOGAS.app`
5. Cree el archivo ZIP:
   ```bash
   cd dist
   zip -r SGIMI_TECNOGAS_Mac.zip SGIMI_TECNOGAS_Distribution_darwin
   ```

## Notas Importantes
- PyInstaller no puede construir ejecutables multiplataforma desde una sola máquina
- Cada plataforma debe construirse en su respectivo sistema operativo
- La base de datos se inicializa vacía (sin datos de prueba)
- Al ejecutar la aplicación por primera vez, se mostrará un diálogo para crear el usuario inicial
