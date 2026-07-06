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
- Python 3.8 o superior
- SQLite 3.x
- 4GB RAM minimo
- 50MB espacio en disco

### Instalacion

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

#### Desde Ejecutable
1. Descargar el ejecutable para su plataforma
2. Descomprimir el archivo
3. Ejecutar `SGIMI_TECNOGAS.exe` (Windows) o `SGIMI_TECNOGAS` (Linux/Mac)

### Primer Uso
Al abrir la aplicacion por primera vez, el sistema solicita crear el usuario inicial. No se instalan datos de prueba ni credenciales por defecto.

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

```bash
# Compilar como directorio
python build_exe.py

# Compilar como archivo unico
python build_exe.py --onefile

# Limpiar y compilar
python build_exe.py --clean --onefile
```

### Soporte
Para soporte tecnico, contacte: soporte@tecnogas.com

### Licencia
Software propietario para uso interno autorizado de TECNOGAS.

Version: 1.0.0
