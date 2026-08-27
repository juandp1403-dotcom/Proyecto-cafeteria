import logging
import os
import secrets
from datetime import datetime

from flask import Flask, redirect, url_for
from flask_login import LoginManager
from flask_talisman import Talisman
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

from .blueprints.permisos import registrar_context_processor
from .extensions import limiter
from .models import Admin, Personal, cancelar_pedidos_expirados, db

login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_name='default'):
    from config.config import _abrir_tunel, _construir_db_url, config

    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(config[config_name])

    if config_name == 'production':
        secret = app.config.get('SECRET_KEY') or ''
        if secret == 'cambia-esta-clave' or len(secret) < 32:
            raise RuntimeError(
                "SECRET_KEY no esta configurada correctamente para produccion "
                "(falta, es el valor por defecto del codigo, o tiene menos de "
                "32 caracteres). Sin una clave real, las sesiones y los tokens "
                "CSRF pueden falsificarse. Genera una con: "
                "python -c \"import secrets; print(secrets.token_hex(32))\" "
                "y configurala en SECRET_KEY."
            )

    # Conexion a BD: tunel SSH (desarrollo contra la BD remota) o
    # DATABASE_URL directa. En produccion no hay fallback efimero: si no
    # hay BD configurada, mejor no arrancar.
    puerto = _abrir_tunel(config_name)
    if puerto:
        app.config['SQLALCHEMY_DATABASE_URI'] = _construir_db_url(puerto)
    elif not app.config.get('SQLALCHEMY_DATABASE_URI'):
        if config_name == 'production':
            raise RuntimeError(
                "No hay conexion real a base de datos configurada (falta SSH_HOST "
                "para el tunel, o DATABASE_URL). En produccion la app no puede "
                "arrancar con SQLite efimero: los datos se perderian en cada "
                "reinicio del contenedor."
            )
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cafeteria.db'

    # Extensiones
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # Flask-Login
    login_manager.login_view = 'empleados.login'
    login_manager.login_message = 'Inicia sesión para continuar.'
    login_manager.login_message_category = 'warning'
    login_manager.session_protection = 'strong'

    # Talisman solo en producción para no romper el desarrollo local
    if config_name == 'production':
        # Coolify termina el TLS y reenvia por HTTP interno: sin ProxyFix
        # todas las peticiones llegan con la IP del proxy y el esquema
        # http, rompiendo el rate limiting por IP y las URLs externas.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

        Talisman(
            app,
            force_https=False,          # Coolify/Traefik ya maneja HTTPS
            strict_transport_security=True,
            content_security_policy={
                'default-src': "'self'",
                'script-src': ["'self'", "'unsafe-inline'", 'https://cdn.jsdelivr.net'],
                'style-src': ["'self'", "'unsafe-inline'", 'https://cdn.jsdelivr.net'],
                'img-src': ["'self'", "'data:'"],
                'font-src': ["'self'", 'https://cdn.jsdelivr.net'],
            },
            session_cookie_secure=True,
        )

        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s %(name)s: %(message)s'
        ))
        app.logger.handlers = [handler]
        app.logger.setLevel(logging.INFO)

    # Blueprints
    from .blueprints.admin import admin_bp
    from .blueprints.cliente import cliente_bp
    from .blueprints.empleados import empleados_bp

    app.register_blueprint(cliente_bp)
    app.register_blueprint(empleados_bp)
    app.register_blueprint(admin_bp)

    # Ruta raíz
    @app.route('/')
    def index():
        return redirect(url_for('cliente.registro'))

    # Healthcheck para Coolify
    @app.route('/healthz')
    def healthz():
        return 'ok', 200

    @app.before_request
    def expirar_pedidos_pendientes():
        """Libera pedidos sin pago confirmado despues de 20 minutos."""
        try:
            cancelar_pedidos_expirados()
        except Exception:
            db.session.rollback()
            app.logger.exception('No se pudieron cancelar pedidos expirados')

    # Context processors de permisos
    registrar_context_processor(app)

    @app.context_processor
    def inject_anio_actual():
        return dict(anio_actual=datetime.utcnow().year)

    # Crear tablas si no existen
    with app.app_context():
        db.create_all()
        _migrar_esquema()
        # Los datos iniciales se cargan solo cuando se solicita
        # expresamente (SEED_INITIAL_DATA): un reinicio no crea inventario
        # ni cuentas/roles por defecto. conftest.py activa la variable
        # durante las pruebas.
        if os.environ.get('SEED_INITIAL_DATA', '').strip().lower() in ('1', 'true', 'si', 'yes'):
            _seed_datos_iniciales(config_name)
            _seed_catalogo_categorizado()

    return app


@login_manager.user_loader
def load_user(user_id):
    if not user_id:
        return None
    if user_id.startswith('admin:'):
        doc = int(user_id.split(':')[1])
        user = Admin.query.get(doc)
    elif user_id.startswith('personal:'):
        doc = int(user_id.split(':')[1])
        user = Personal.query.get(doc)
    else:
        return None
    # HU-36: una cuenta desactivada no conserva sesion activa.
    if user is not None and not getattr(user, 'activo', True):
        return None
    return user


def _ejecutar_migracion(ddl):
    """Ejecuta un DDL de migracion; si falla, lo loguea en vez de silenciarlo."""
    from sqlalchemy import text
    try:
        db.session.execute(text(ddl))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logging.getLogger(__name__).warning(
            "Migracion de esquema fallo (puede ser esperado si ya se aplico "
            "antes, o requiere intervencion manual): %s -- %s", ddl, e
        )


def _migrar_esquema():
    """Ajusta el esquema de la BD segun el motor (PostgreSQL y SQLite)."""
    uri = db.engine.url
    es_pg = uri.drivername in ('postgresql', 'postgresql+psycopg', 'postgresql+psycopg2')
    from sqlalchemy import inspect
    insp = inspect(db.engine)

    def columna_existe(tabla, columna):
        try:
            return columna in [c['name'] for c in insp.get_columns(tabla)]
        except Exception:
            return False

    def agregar_columna(tabla, columna, ddl_pg, ddl_sqlite):
        ddl = ddl_pg if es_pg else ddl_sqlite
        if not es_pg and columna_existe(tabla, columna):
            return
        _ejecutar_migracion(ddl)

    def constraint_unico_existe(tabla, nombre):
        try:
            return nombre in [c['name'] for c in insp.get_unique_constraints(tabla)]
        except Exception:
            return False

    if es_pg:
        _ejecutar_migracion("ALTER TABLE admin ALTER COLUMN clave TYPE VARCHAR(256)")
        _ejecutar_migracion("ALTER TABLE venta ALTER COLUMN fechaventa TYPE TIMESTAMP USING fechaventa::timestamp")
        _ejecutar_migracion("ALTER TABLE bajainventario ALTER COLUMN fecha TYPE TIMESTAMP USING fecha::timestamp")
        _ejecutar_migracion("ALTER TABLE compra ALTER COLUMN fechacompra TYPE TIMESTAMP USING fechacompra::timestamp")
        _ejecutar_migracion("UPDATE admin SET rol = 'despachador' WHERE rol = 'entregador'")
        _ejecutar_migracion("ALTER TABLE producto ALTER COLUMN nombre TYPE VARCHAR(100)")
        _ejecutar_migracion("ALTER TABLE cliente ALTER COLUMN nombre TYPE VARCHAR(100)")
        _ejecutar_migracion("ALTER TABLE admin ALTER COLUMN email TYPE VARCHAR(120)")
        if not constraint_unico_existe('admin', 'admin_email_key'):
            _ejecutar_migracion("ALTER TABLE admin ADD CONSTRAINT admin_email_key UNIQUE (email)")
        _ejecutar_migracion("ALTER TABLE reporte DROP CONSTRAINT IF EXISTS reporte_idadmin_key")
        _ejecutar_migracion("ALTER TABLE reporte DROP CONSTRAINT IF EXISTS reporte_producto_key")
        _ejecutar_migracion("ALTER TABLE personal ALTER COLUMN email TYPE VARCHAR(120)")
        _ejecutar_migracion("CREATE INDEX IF NOT EXISTS idx_venta_fechaventa ON venta (fechaventa)")
        _ejecutar_migracion("CREATE INDEX IF NOT EXISTS idx_venta_estado ON venta (estado)")
        _ejecutar_migracion("CREATE INDEX IF NOT EXISTS idx_venta_cliente ON venta (cliente)")
        _ejecutar_migracion("CREATE INDEX IF NOT EXISTS idx_detalleventa_idventa ON detalleventa (idventa)")
        _ejecutar_migracion("CREATE INDEX IF NOT EXISTS idx_detalleventa_idproducto ON detalleventa (idproducto)")
        _ejecutar_migracion("CREATE INDEX IF NOT EXISTS idx_detallecompra_idcompra ON detallecompra (idcompra)")
        # 'preciou' es una columna huerfana historica: solo soltar el NOT
        # NULL si existe, para no registrar warning en bases que nunca la
        # tuvieron.
        if columna_existe('detalleventa', 'preciou'):
            _ejecutar_migracion("ALTER TABLE detalleventa ALTER COLUMN preciou DROP NOT NULL")
        # Race condition entre workers al sembrar catalogo: borrar el
        # duplicado mas reciente antes del indice unico.
        _ejecutar_migracion("""
            DELETE FROM producto p1
            USING producto p2
            WHERE p1.idproducto > p2.idproducto AND p1.nombre = p2.nombre
        """)

    _ejecutar_migracion("CREATE UNIQUE INDEX IF NOT EXISTS idx_producto_nombre_unico ON producto (nombre)")

    agregar_columna('producto', 'imagen',
                    "ALTER TABLE producto ADD COLUMN IF NOT EXISTS imagen VARCHAR(255)",
                    "ALTER TABLE producto ADD COLUMN imagen VARCHAR(255)")
    agregar_columna('venta', 'estado',
                    "ALTER TABLE venta ADD COLUMN IF NOT EXISTS estado VARCHAR(30) DEFAULT 'Pendiente de Pago'",
                    "ALTER TABLE venta ADD COLUMN estado VARCHAR(30) DEFAULT 'Pendiente de Pago'")
    agregar_columna('admin', 'rol',
                    "ALTER TABLE admin ADD COLUMN IF NOT EXISTS rol VARCHAR(20) DEFAULT 'admin'",
                    "ALTER TABLE admin ADD COLUMN rol VARCHAR(20) DEFAULT 'admin'")
    agregar_columna('producto', 'stock_minimo',
                    "ALTER TABLE producto ADD COLUMN IF NOT EXISTS stock_minimo INT NOT NULL DEFAULT 10",
                    "ALTER TABLE producto ADD COLUMN stock_minimo INT NOT NULL DEFAULT 10")
    agregar_columna('producto', 'costo',
                    "ALTER TABLE producto ADD COLUMN IF NOT EXISTS costo INT NOT NULL DEFAULT 0",
                    "ALTER TABLE producto ADD COLUMN costo INT NOT NULL DEFAULT 0")
    agregar_columna('bajainventario', 'categoria',
                    "ALTER TABLE bajainventario ADD COLUMN IF NOT EXISTS categoria VARCHAR(20) NOT NULL DEFAULT 'Otro'",
                    "ALTER TABLE bajainventario ADD COLUMN categoria VARCHAR(20) NOT NULL DEFAULT 'Otro'")
    agregar_columna('producto', 'es_especial',
                    "ALTER TABLE producto ADD COLUMN IF NOT EXISTS es_especial BOOLEAN NOT NULL DEFAULT FALSE",
                    "ALTER TABLE producto ADD COLUMN es_especial BOOLEAN NOT NULL DEFAULT 0")
    agregar_columna('producto', 'especial_hasta',
                    "ALTER TABLE producto ADD COLUMN IF NOT EXISTS especial_hasta DATE",
                    "ALTER TABLE producto ADD COLUMN especial_hasta DATE")
    agregar_columna('venta', 'metodo_pago',
                    "ALTER TABLE venta ADD COLUMN IF NOT EXISTS metodo_pago VARCHAR(20)",
                    "ALTER TABLE venta ADD COLUMN metodo_pago VARCHAR(20)")
    agregar_columna('venta', 'numero_pedido_diario',
                    "ALTER TABLE venta ADD COLUMN IF NOT EXISTS numero_pedido_diario INTEGER",
                    "ALTER TABLE venta ADD COLUMN numero_pedido_diario INTEGER")
    if es_pg:
        _ejecutar_migracion("""
            UPDATE venta SET numero_pedido_diario = sub.n
            FROM (
                SELECT idventa, ROW_NUMBER() OVER (PARTITION BY fechaventa::date ORDER BY idventa) AS n
                FROM venta
            ) AS sub
            WHERE venta.idventa = sub.idventa AND venta.numero_pedido_diario IS NULL
        """)

    agregar_columna('detalleventa', 'precio_unitario',
                    "ALTER TABLE detalleventa ADD COLUMN IF NOT EXISTS precio_unitario INT NOT NULL DEFAULT 0",
                    "ALTER TABLE detalleventa ADD COLUMN precio_unitario INT NOT NULL DEFAULT 0")
    agregar_columna('detallecompra', 'subtotal',
                    "ALTER TABLE detallecompra ADD COLUMN IF NOT EXISTS subtotal INT NOT NULL DEFAULT 0",
                    "ALTER TABLE detallecompra ADD COLUMN subtotal INT NOT NULL DEFAULT 0")
    _ejecutar_migracion(
        "UPDATE detalleventa SET precio_unitario = "
        "COALESCE((SELECT p.precio FROM producto p WHERE p.idproducto = detalleventa.idproducto), 0) "
        "WHERE precio_unitario IS NULL OR precio_unitario = 0"
    )

    agregar_columna('producto', 'created_at',
                    "ALTER TABLE producto ADD COLUMN IF NOT EXISTS created_at TIMESTAMP",
                    "ALTER TABLE producto ADD COLUMN created_at TIMESTAMP")
    agregar_columna('producto', 'updated_at',
                    "ALTER TABLE producto ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP",
                    "ALTER TABLE producto ADD COLUMN updated_at TIMESTAMP")
    agregar_columna('venta', 'created_at',
                    "ALTER TABLE venta ADD COLUMN IF NOT EXISTS created_at TIMESTAMP",
                    "ALTER TABLE venta ADD COLUMN created_at TIMESTAMP")
    agregar_columna('venta', 'updated_at',
                    "ALTER TABLE venta ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP",
                    "ALTER TABLE venta ADD COLUMN updated_at TIMESTAMP")
    agregar_columna('bajainventario', 'usuario_documento',
                    "ALTER TABLE bajainventario ADD COLUMN IF NOT EXISTS usuario_documento INT",
                    "ALTER TABLE bajainventario ADD COLUMN usuario_documento INT")
    agregar_columna('bajainventario', 'usuario_tipo',
                    "ALTER TABLE bajainventario ADD COLUMN IF NOT EXISTS usuario_tipo VARCHAR(20)",
                    "ALTER TABLE bajainventario ADD COLUMN usuario_tipo VARCHAR(20)")

    agregar_columna('producto', 'activo',
                    "ALTER TABLE producto ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE",
                    "ALTER TABLE producto ADD COLUMN activo BOOLEAN NOT NULL DEFAULT 1")
    agregar_columna('admin', 'activo',
                    "ALTER TABLE admin ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE",
                    "ALTER TABLE admin ADD COLUMN activo BOOLEAN NOT NULL DEFAULT 1")
    agregar_columna('personal', 'activo',
                    "ALTER TABLE personal ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE",
                    "ALTER TABLE personal ADD COLUMN activo BOOLEAN NOT NULL DEFAULT 1")

    agregar_columna('producto', 'categoria',
                    "ALTER TABLE producto ADD COLUMN IF NOT EXISTS categoria VARCHAR(30)",
                    "ALTER TABLE producto ADD COLUMN categoria VARCHAR(30)")
    agregar_columna('producto', 'subcategoria',
                    "ALTER TABLE producto ADD COLUMN IF NOT EXISTS subcategoria VARCHAR(30)",
                    "ALTER TABLE producto ADD COLUMN subcategoria VARCHAR(30)")
    agregar_columna('producto', 'descripcion',
                    "ALTER TABLE producto ADD COLUMN IF NOT EXISTS descripcion VARCHAR(300)",
                    "ALTER TABLE producto ADD COLUMN descripcion VARCHAR(300)")


def _clave_seed(env_var, default_dev, config_name):
    """En produccion, si falta la contraseña por variable de entorno, se
    genera una aleatoria y se imprime una sola vez en el log de arranque."""
    valor = os.environ.get(env_var)
    if valor:
        return valor
    if config_name == 'production':
        generada = secrets.token_urlsafe(12)
        print(f"[seed] ADVERTENCIA: {env_var} no esta configurada. Se genero "
              f"una contraseña aleatoria para esta cuenta -- anotala ahora, "
              f"no se volvera a mostrar: {generada}")
        return generada
    return default_dev


def _seed_datos_iniciales(config_name='development'):
    from werkzeug.security import generate_password_hash

    from .models import Admin, Producto

    documentos_existentes = {a.documento for a in Admin.query.with_entities(Admin.documento).all()}
    correos_existentes = {a.email for a in Admin.query.with_entities(Admin.email).all()}

    def _agregar_admin_seed(documento, nombre, email, clave_plana, rol):
        # HU-70: validar tambien el correo -- si ya existe en OTRA cuenta
        # (email UNIQUE), el INSERT fallaba con IntegrityError durante un
        # autoflush posterior y tumbaba el arranque del worker.
        if documento in documentos_existentes:
            return
        if email in correos_existentes:
            print(f"[seed] ADVERTENCIA: no se creo la cuenta '{nombre}' "
                  f"(documento={documento}) porque el correo '{email}' ya "
                  f"esta en uso por otra cuenta.")
            return
        db.session.add(Admin(
            documento=documento, nombre=nombre, email=email,
            clave=generate_password_hash(clave_plana), rol=rol,
        ))
        correos_existentes.add(email)

    _agregar_admin_seed(
        int(os.environ.get('ADMIN_DOCUMENTO', '1000000')),
        os.environ.get('ADMIN_NOMBRE', 'Administrador SENA'),
        os.environ.get('ADMIN_EMAIL', 'admin@cafeteria.com'),
        _clave_seed('ADMIN_PASSWORD', 'Admin123', config_name),
        'admin',
    )
    _agregar_admin_seed(
        int(os.environ.get('CAJERO_DOCUMENTO', '2000000')),
        os.environ.get('CAJERO_NOMBRE', 'Cajero Principal'),
        os.environ.get('CAJERO_EMAIL', 'cajero@cafeteria.com'),
        _clave_seed('CAJERO_PASSWORD', 'Cajero123', config_name),
        'cajero',
    )
    _agregar_admin_seed(
        int(os.environ.get('ENTREGADOR_DOCUMENTO', '3000000')),
        os.environ.get('ENTREGADOR_NOMBRE', 'Entregador Principal'),
        os.environ.get('ENTREGADOR_EMAIL', 'entregador@cafeteria.com'),
        _clave_seed('ENTREGADOR_PASSWORD', 'Entregador123', config_name),
        'despachador',
    )

    from sqlalchemy.exc import IntegrityError
    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        print(f"[seed] ADVERTENCIA: fallo al crear las cuentas semilla: {e}")

    if not Producto.query.first():
        # Sin categoria a proposito: la vista "Ordenar" solo muestra los
        # 2 productos por categoria definidos en CATALOGO_SEED.
        productos = [
            Producto(nombre='Almuerzo Completo',  precio=8000, stock=50),
            Producto(nombre='Sanduche de Pollo',  precio=5000, stock=30),
            Producto(nombre='Jugo Natural',        precio=3000, stock=40),
            Producto(nombre='Café Tinto',          precio=1500, stock=60),
            Producto(nombre='Empanada',            precio=2500, stock=35),
            Producto(nombre='Agua Botella 600ml',  precio=2000, stock=50),
            Producto(nombre='Ensalada de Frutas',  precio=4000, stock=20),
            Producto(nombre='Chocolate Caliente',  precio=2500, stock=25),
        ]
        db.session.add_all(productos)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()


def _seed_catalogo_categorizado():
    """Inserta el catalogo base si aun no existen. Commit individual por
    item: con varios workers arrancando a la vez, la fuente de verdad es
    la restriccion UNIQUE de producto.nombre en la BD."""
    from sqlalchemy.exc import IntegrityError

    from .catalogo_seed import CATALOGO_SEED
    from .models import Producto

    nombres_existentes = {n for (n,) in db.session.query(Producto.nombre).all()}
    for item in CATALOGO_SEED:
        if item['nombre'] in nombres_existentes:
            continue
        db.session.add(Producto(
            nombre=item['nombre'], categoria=item['categoria'], subcategoria=item['subcategoria'],
            precio=item['precio'], costo=item['costo'], stock=item['stock'],
            descripcion=item['descripcion'], imagen=item['imagen'],
        ))
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
