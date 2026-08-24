import os
import logging
import secrets
from datetime import datetime
from flask import Flask, redirect, url_for
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman
from werkzeug.middleware.proxy_fix import ProxyFix
from config.config import config, _abrir_tunel, _construir_db_url
from .models import db, Admin, Personal
from .extensions import limiter

login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'productos')

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

    puerto = _abrir_tunel(config_name)
    if puerto:
        app.config['SQLALCHEMY_DATABASE_URI'] = _construir_db_url(puerto)
    elif not app.config.get('SQLALCHEMY_DATABASE_URI'):
        if config_name == 'production':
            raise RuntimeError(
                "No hay conexion real a base de datos configurada (falta SSH_HOST "
                "para el tunel, o DATABASE_URL). En produccion la app no puede "
                "arrancar con SQLite efimero: los datos se perderian en cada "
                "reinicio del contenedor. Configura las variables de entorno "
                "necesarias antes de desplegar (ver .env.example)."
            )
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cafeteria.db'

    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'empleados.login'
    login_manager.login_message = 'Inicia sesión para continuar.'
    login_manager.login_message_category = 'warning'
    login_manager.session_protection = 'strong'

    if config_name == 'production':
        # Coolify termina el TLS y reenvia por HTTP interno.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

        Talisman(
            app,
            force_https=False,  # el proxy reverso ya termina el TLS
            strict_transport_security=True,
            content_security_policy={
                'default-src': "'self'",
                'script-src': ["'self'", "'unsafe-inline'", 'https://cdn.jsdelivr.net'],
                'style-src': ["'self'", "'unsafe-inline'", 'https://cdn.jsdelivr.net'],
                'img-src': ["'self'", 'data:'],
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

    from .blueprints.cliente   import cliente_bp
    from .blueprints.empleados import empleados_bp
    from .blueprints.admin     import admin_bp
    from .blueprints.permisos  import registrar_context_processor

    app.register_blueprint(cliente_bp)
    app.register_blueprint(empleados_bp)
    app.register_blueprint(admin_bp)

    registrar_context_processor(app)

    @app.context_processor
    def inject_anio_actual():
        return dict(anio_actual=datetime.utcnow().year)

    @app.route('/')
    def index():
        return redirect(url_for('cliente.registro'))

    @app.route('/healthz')
    def healthz():
        return {'status': 'ok'}, 200

    with app.app_context():
        db.create_all()
        _migrar_esquema()
        # Los datos iniciales se cargan solo cuando se solicita expresamente.
        # Asi un reinicio no crea inventario ni cuentas/roles por defecto.
        if os.environ.get('SEED_INITIAL_DATA', '').strip().lower() in ('1', 'true', 'si', 'yes'):
            _seed_datos_iniciales(config_name)
            _seed_catalogo_categorizado()

    return app


@login_manager.user_loader
def load_user(user_id):
    if ':' in user_id:
        tipo, doc = user_id.split(':', 1)
        if tipo == 'admin':
            user = Admin.query.get(int(doc))
        elif tipo == 'personal':
            user = Personal.query.get(int(doc))
        else:
            return None
        if user is not None and not getattr(user, 'activo', True):
            return None
        return user
    return None


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
        # Bajas de inventario y compras pasaron de DATE a TIMESTAMP (fecha
        # y hora); en SQLite no hace falta DDL (tipado dinamico) y las
        # filas legacy quedan con hora 00:00.
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
        # 'preciou' es una columna huerfana en la BD real (no existe en el
        # modelo ni en el historial de git); bloqueaba cualquier insert nuevo.
        # Se verifica que exista antes de intentar el ALTER, para no
        # registrar un warning en cada arranque en las bases que nunca
        # tuvieron esa columna.
        if columna_existe('detalleventa', 'preciou'):
            _ejecutar_migracion("ALTER TABLE detalleventa ALTER COLUMN preciou DROP NOT NULL")
        # Race condition entre workers de gunicorn al sembrar el catalogo
        # (ver _seed_catalogo_categorizado) dejo productos duplicados por
        # nombre en la BD real. Se borra el duplicado mas reciente de
        # cada par antes de poner el indice unico que evita que vuelva a pasar.
        _ejecutar_migracion("""
            DELETE FROM producto p1
            USING producto p2
            WHERE p1.idproducto > p2.idproducto AND p1.nombre = p2.nombre
        """)

    # Indice unico (sintaxis portable Postgres/SQLite) para que la
    # restriccion la aplique la BD, no una lectura-y-escritura en Python
    # que puede pisarse entre workers concurrentes.
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
        # Backfill del consecutivo diario; en SQLite no hay datos legacy que rellenar.
        _ejecutar_migracion("""
            UPDATE venta SET numero_pedido_diario = sub.n
            FROM (
                SELECT idventa, ROW_NUMBER() OVER (PARTITION BY fechaventa::date ORDER BY idventa) AS n
                FROM venta
            ) AS sub
            WHERE venta.idventa = sub.idventa AND venta.numero_pedido_diario IS NULL
        """)

    agregar_columna(
        'detalleventa', 'precio_unitario',
        "ALTER TABLE detalleventa ADD COLUMN IF NOT EXISTS precio_unitario INT NOT NULL DEFAULT 0",
        "ALTER TABLE detalleventa ADD COLUMN precio_unitario INT NOT NULL DEFAULT 0",
    )
    agregar_columna(
        'detallecompra', 'subtotal',
        "ALTER TABLE detallecompra ADD COLUMN IF NOT EXISTS subtotal INT NOT NULL DEFAULT 0",
        "ALTER TABLE detallecompra ADD COLUMN subtotal INT NOT NULL DEFAULT 0",
    )
    # Backfill de filas legacy con el precio actual del producto.
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
    from .models import Admin, Producto
    from werkzeug.security import generate_password_hash

    documentos_existentes = {a.documento for a in Admin.query.with_entities(Admin.documento).all()}
    correos_existentes = {a.email for a in Admin.query.with_entities(Admin.email).all()}

    def _agregar_admin_seed(documento, nombre, email, clave_plana, rol):
        # HU-70: antes solo se validaba el documento -- si el correo ya
        # existia en OTRA cuenta (email tiene UNIQUE), el INSERT fallaba
        # con IntegrityError durante el autoflush del Producto.query.first()
        # de mas abajo, tumbando el arranque completo del worker (el
        # try/except de mas abajo nunca llegaba a proteger este INSERT).
        if documento in documentos_existentes:
            return
        if email in correos_existentes:
            print(f"[seed] ADVERTENCIA: no se creo la cuenta '{nombre}' "
                  f"(documento={documento}) porque el correo '{email}' ya "
                  f"esta en uso por otra cuenta. Ajusta la variable de "
                  f"entorno correspondiente o revisa la cuenta existente.")
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

    # Commit aparte (no combinado con el seed de productos de abajo): asi
    # el autoflush de la consulta Producto.query.first() nunca encuentra
    # estos INSERT todavia pendientes, y si de verdad fallaran, quedan
    # protegidos por su propio try/except en vez de tumbar el arranque.
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

    from sqlalchemy.exc import IntegrityError
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()


# Los productos legacy (Almuerzo Completo, Sanduche de Pollo, etc.) se
# dejan sin categoria a proposito: la vista "Ordenar" solo debe mostrar
# los 2 productos por categoria definidos en CATALOGO_SEED.


def _seed_catalogo_categorizado():
    """Inserta el catalogo de 2 productos por categoria si aun no
    existen. Commit individual por item (no uno solo al final): con
    varios workers de gunicorn arrancando a la vez, la unica fuente de
    verdad real es la restriccion UNIQUE de producto.nombre en la BD
    -- el chequeo previo por nombre es solo para evitar una consulta
    redundante, no para prevenir la condicion de carrera."""
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


if __name__ == '__main__':
    app = create_app('development')
    app.run(debug=True, host='0.0.0.0', port=5545)
