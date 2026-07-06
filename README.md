# SGIMI TECNOGAS
## Sistema de Gestion de Inventario Multi-Sucursal

### Descripcion
Sistema completo de gestion de inventario basado en arquitectura orientada a eventos (Event-Driven Architecture). Disegnado para controlar inventario en multiples sucursales con trazabilidad completa.

### Caracteristicas Principales
- **Arquitectura basada en eventos**: Comunicacion desacoplada entre modulos mediante Event Bus
- **Gestion multi-sucursal**: Control centralizado con visibilidad por sucursal
- **Movimientos de inventario**: Entradas, salidas, ajustes y transferencias
- **Validacion de movimientos**: Flujo de aprobacion para control de operaciones
- **Historial completo**: Trazabilidad de todas las operaciones
- **Alertas automaticas**: Deteccion de discrepancias y stock bajo
- **Dashboard con KPIs**: Metricas en tiempo real (ERI, ERU)
- **Reportes**: Informes de inventario, movimientos y discrepancias

### Requisitos del Sistema
- Python 3.11 o 3.12 recomendado para compilar ejecutables
- SQLite 3.x
- 4GB RAM minimo
- 50MB espacio en disco

### Instalacion

#### Desde Ejecutable
1. Descarga el archivo para tu sistema operativo.
2. Descomprime la carpeta si es necesario.
3. Haz doble clic en el archivo ejecutable:
   - Windows: `SGIMI_TECNOGAS.exe`
   - macOS: `SGIMI_TECNOGAS.app`
   - Linux: `SGIMI_TECNOGAS`
4. Si aparece una advertencia de seguridad, confirma que deseas abrirlo.

#### Desde Codigo Fuente
```bash
# Clonar repositorio
git clone <url-del-repo>
cd SGIMI_TECNOGAS

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\\Scripts\\activate   # Windows

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar aplicacion
python main.py
```

### Primer Uso
Al abrir la aplicacion por primera vez, el sistema te pedira crear el usuario inicial.
Solo debes completar:
- Nombre
- Correo
- Contraseña
- Confirmar contraseña

Luego presiona Crear usuario.

### Como Iniciar Sesion
1. Escribe tu correo
2. Escribe tu contraseña
3. Presiona Iniciar Sesion

### Estructura del Proyecto
```
SGIMI TECNOGAS/
├── main.py                 # Punto de entrada
├── config.py                # Configuracion de logging
├── requirements.txt         # Dependencias
├── core/                    # Componentes centrales
│   ├── event_bus.py         # Bus de eventos
│   ├── database.py          # Configuracion DB
│   └── settings.py          # Variables de entorno
├── models/                  # Modelos de datos
│   ├── product.py
│   ├── branch.py
│   ├── inventory.py
│   ├── movement.py
│   └── user.py
├── modules/                 # Modulos de negocio
│   ├── products/
│   ├── branches/
│   ├── inventory/
│   ├── movements/
│   ├── dashboard/
│   ├── alerts/
│   ├── history/
│   └── reports/
├── database/                # Scripts de DB
│   └── seed.py
├── utils/                    # Utilidades
│   ├── validators.py
│   └── helpers.py
└── tests/                    # Pruebas unitarias
```

### Arquitectura de Eventos

#### Eventos del Sistema
- `product.created/updated/deleted`: Cambios en productos
- `movement.created/validated/rejected`: Flujo de movimientos
- `inventory.updated/counted`: Cambios en inventario
- `transfer.sent/received`: Transferencias entre sucursales
- `alert.generated`: Generacion de alertas

#### Flujo de Movimientos
1. Usuario crea movimiento -> `movement.created`
2. Validador aprueba/rechaza -> `movement.validated` / `movement.rejected`
3. Inventario reacciona -> actualiza stock -> `inventory.updated`
4. Alertas detectan problemas -> `alert.generated`
5. Historial registra todo -> trazabilidad completa

### Compilar Ejecutable

PyInstaller genera binarios para el sistema operativo donde se ejecuta la compilacion. Para obtener una build compatible con Windows, macOS y Linux, ejecuta el script en cada sistema operativo con el destino correspondiente:

Para empaquetar, usa preferentemente Python 3.11 o 3.12 con un entorno virtual limpio e instala `requirements.txt`.

```bash
# Windows
python build_exe.py --target windows --onefile

# macOS
python build_exe.py --target darwin --onefile

# Linux
python build_exe.py --target linux --onefile

# Crear paquete distribuible
python build_exe.py --target windows --onefile --dist

# Limpiar y compilar
python build_exe.py --clean --target windows --onefile
```

Nota: el parametro `--target` valida y organiza la salida, pero no realiza compilacion cruzada. El `.exe` debe generarse en Windows, el paquete macOS en macOS y el binario Linux en Linux.

La base de datos y los logs se guardan en la carpeta de datos del usuario del sistema operativo, por lo que la aplicacion puede ejecutarse como sistema de escritorio instalado sin escribir dentro de la carpeta del programa.

### Soporte
Para soporte tecnico, contacte: soporte@tecnogas.com

### Licencia
Software propietario para uso interno autorizado de TECNOGAS.

Version: 1.0.0
