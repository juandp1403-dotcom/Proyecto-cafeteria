---
name: project-cafeteria-sena
description: App web cafetería SENA CGAO Flask+SQLAlchemy+Bootstrap5 en C:\Users\ASUS\Documents\Proyecto-cafeteria
metadata:
  type: project
---

App web cafetería institucional SENA CGAO — generada 2026-06-22.

**Why:** Gestión digital de pedidos para la cafetería del SENA CGAO con 4 roles: Cliente, Cajero, Entregador, Administrador.

## Arquitectura del Proyecto

### Estructura de archivos
```
Proyecto-cafeteria/
├── app.py              ← PUNTO DE ENTRADA (python app.py)
├── config.py           ← Config Flask (SECRET_KEY, DATABASE_URL)
├── models.py           ← Modelos SQLAlchemy (todas las tablas)
├── requirements.txt    ← Dependencias pip
├── .env                ← Variables de entorno (NO compartir en git)
├── blueprints/         ← Lógica de negocio por módulo
│   ├── cliente/        ← Registro clientes + catálogo + pedidos + factura
│   │   ├── __init__.py ← Blueprint 'cliente' con url_prefix='/cliente'
│   │   └── routes.py   ← /registro, /catalogo, /confirmar, /factura, /estado
│   ├── empleados/      ← Login admin + cajero + entregador
│   │   ├── __init__.py ← Blueprint 'empleados' con url_prefix='/empleados'
│   │   └── routes.py   ← /login, /logout, /cajero, /entregador + APIs JSON
│   └── admin/          ← Panel administrativo completo
│       ├── __init__.py ← Blueprint 'admin_panel' con url_prefix='/admin'
│       └── routes.py   ← Dashboard, CRUD productos/usuarios, ventas, compras
├── templates/          ← Templates Jinja2
│   ├── base.html       ← Plantilla base (navbar, Bootstrap 5, dark mode)
│   ├── cliente/        ← registro.html, catalogo.html, factura.html, estado_pedido.html
│   ├── empleados/      ← login.html, cajero.html, entregador.html, _tabla_cajero.html
│   └── admin/          ← dashboard.html, productos.html, usuarios.html, ventas.html, compras.html, base_admin.html
├── cafeteria.db        ← Base de datos SQLite (se crea sola al primer arranque)
└── .venv/              ← Virtual environment Python 3.12
```

### Base de datos (PostgreSQL en Coolify)
Conecta via SSH tunnel a PostgreSQL remoto. El `.env` configura:
- SSH: `root@144.91.74.225:22` con key `~/.ssh/id_cafeteria` (sin passphrase)
- PostgreSQL: `juan@127.0.0.1:5438/cafeteria` (via tunnel)
- `config.py` abre el túnel automáticamente al iniciar `python app.py`
- El archivo `.db` de SQLite NO se usa — ignóralo si existe.

Tablas:
- `producto` — idproducto, nombre, precio, stock
- `cliente` — documento (PK), nombre, ficha
- `venta` — idventa, precio, cliente (FK), fechaventa, **estado** (Pendiente de Pago / Pagado/Preparando / Entregado)
- `detalleventa` — iddetalle, idventa (FK), idproducto (FK), cantidad
- `admin` — documento (PK), nombre, clave (hash), email
- `compra` — idcompra, nombrevendedor, precio, fechacompra, documentoadmin (FK)
- `detallecompra` — iddetallecompra, idcompra (FK), idproducto (FK), cantidad

### Flujo de pedidos (estado en Venta)
1. Cliente crea pedido → estado = 'Pendiente de Pago'
2. Cajero marca pagado → estado = 'Pagado/Preparando'
3. Entregador confirma entrega → estado = 'Entregado'

### Seed automático
Al arrancar `python app.py` se crea:
- 1 Admin: documento=1000000, email=admin@gmail.com, password=Admin123.ñ
- 8 Productos: Almuerzo, Sanduche, Jugo, Café, Empanada, Agua, Ensalada, Chocolate

### Cómo correr
```bash
cd C:\Users\ASUS\Documents\Proyecto-cafeteria
.venv\Scripts\activate          # Activar venv
python app.py                   # Inicia en http://localhost:5545
```

### Cómo cambiar cosas sin romper la app

**REGLAS DE ORO:**
1. **Nunca renombrar** un Blueprint ('cliente', 'empleados', 'admin_panel') — rompe todos los `url_for()`.
2. **Nunca renombrar** un modelo (Producto, Cliente, Venta, etc.) — rompe FKs y templates.
3. **Nunca renombrar** una columna PK — rompe relaciones.
4. **Si agregas una columna**, agregarla en `models.py` Y en el `to_dict()` correspondiente.
5. **Si agregas un modelo**, importarlo en `app.py` (en `_seed_datos_iniciales` si necesita seed).
6. **Si agregas un blueprint**, registrarlo en `create_app()` en `app.py`.
7. **Si agregas una ruta**, usar `url_for('blueprint.ruta')` en templates.
8. **ventas.html** usa `v.numero_pedido_diario` (property) y `v.estado` (columna) — si cambias el modelo Venta, verifica estas referencias.
9. **El flujo de estado** es: Pendiente de Pago → Pagado/Preparando → Entregado. Los endpoints de cajero y entregador actualizan esto automáticamente.

**Para agregar una nueva funcionalidad:**
1. Crear modelo en `models.py` si es necesario
2. Crear blueprint en `blueprints/nuevo/` con `__init__.py` y `routes.py`
3. Registrar blueprint en `app.py` → `create_app()`
4. Crear templates en `templates/nuevo/`
5. Heredar de `templates/base.html` con `{% extends 'base.html' %}`

### Puerto
- Puerto: **5545**
- URL: http://localhost:5545
