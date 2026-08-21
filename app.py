import os
from flask import Flask, redirect, url_for
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import config, _abrir_tunel, _construir_db_url
from models import db, Admin, Personal

login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'productos')

    # ── Tunel SSH → DB ──
    puerto = _abrir_tunel()
    if puerto:
        app.config['SQLALCHEMY_DATABASE_URI'] = _construir_db_url(puerto)
    elif not app.config.get('SQLALCHEMY_DATABASE_URI'):
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cafeteria.db'

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'empleados.login'
    login_manager.login_message = 'Inicia sesión para continuar.'
    login_manager.login_message_category = 'warning'

    from blueprints.cliente   import cliente_bp
    from blueprints.empleados import empleados_bp
    from blueprints.admin     import admin_bp
    from blueprints.permisos  import registrar_context_processor

    app.register_blueprint(cliente_bp)
    app.register_blueprint(empleados_bp)
    app.register_blueprint(admin_bp)

    registrar_context_processor(app)

    @app.route('/')
    def index():
        return redirect(url_for('cliente.registro'))

    with app.app_context():
        db.create_all()
        _migrar_esquema()
        _seed_datos_iniciales()

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
        # HU-36: usuarios desactivados no pueden iniciar sesion
        if user is not None and not getattr(user, 'activo', True):
            return None
        return user
    return None


def _migrar_esquema():
    """Ajusta el esquema de la BD segun el motor (solo PostgreSQL)."""
    uri = db.engine.url
    es_pg = uri.drivername in ('postgresql', 'postgresql+psycopg', 'postgresql+psycopg2')
    from sqlalchemy import text, inspect
    insp = inspect(db.engine)

    def columna_existe(tabla, columna):
        try:
            return columna in [c['name'] for c in insp.get_columns(tabla)]
        except Exception:
            return False

    def agregar_columna(tabla, columna, ddl_pg, ddl_sqlite):
        """Agrega una columna de forma segura en ambos motores."""
        if es_pg:
            try:
                db.session.execute(text(ddl_pg))
                db.session.commit()
            except Exception:
                db.session.rollback()
        else:
            if not columna_existe(tabla, columna):
                try:
                    db.session.execute(text(ddl_sqlite))
                    db.session.commit()
                except Exception:
                    db.session.rollback()

    if es_pg:
        try:
            db.session.execute(text(
                "ALTER TABLE admin ALTER COLUMN clave TYPE VARCHAR(256)"
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
        # HU-56: venta.fechaventa pasa de DATE a TIMESTAMP para conservar la hora real
        try:
            db.session.execute(text(
                "ALTER TABLE venta ALTER COLUMN fechaventa TYPE TIMESTAMP USING fechaventa::timestamp"
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()

    # ── Columnas agregadas en cambios anteriores (ambos motores) ──
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

    # ── HU-35: precio historico por detalle de venta ──
    agregar_columna(
        'detalleventa', 'precio_unitario',
        "ALTER TABLE detalleventa ADD COLUMN IF NOT EXISTS precio_unitario INT NOT NULL DEFAULT 0",
        "ALTER TABLE detalleventa ADD COLUMN precio_unitario INT NOT NULL DEFAULT 0",
    )
    # Backfill: filas legacy se rellenan con el precio ACTUAL del producto
    # (mejor aproximacion posible; las ventas nuevas ya guardan su precio real).
    try:
        db.session.execute(text(
            "UPDATE detalleventa SET precio_unitario = "
            "COALESCE((SELECT p.precio FROM producto p WHERE p.idproducto = detalleventa.idproducto), 0) "
            "WHERE precio_unitario IS NULL OR precio_unitario = 0"
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()

    # ── HU-62: auditoria (quien y cuando) ──
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

    # ── HU-36: borrado logico ──
    agregar_columna('producto', 'activo',
                    "ALTER TABLE producto ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE",
                    "ALTER TABLE producto ADD COLUMN activo BOOLEAN NOT NULL DEFAULT 1")
    agregar_columna('admin', 'activo',
                    "ALTER TABLE admin ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE",
                    "ALTER TABLE admin ADD COLUMN activo BOOLEAN NOT NULL DEFAULT 1")
    agregar_columna('personal', 'activo',
                    "ALTER TABLE personal ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE",
                    "ALTER TABLE personal ADD COLUMN activo BOOLEAN NOT NULL DEFAULT 1")


def _seed_datos_iniciales():
    from models import Admin, Producto
    from werkzeug.security import generate_password_hash

    documentos_existentes = {a.documento for a in Admin.query.with_entities(Admin.documento).all()}

    doc_admin = int(os.environ.get('ADMIN_DOCUMENTO', '1000000'))
    doc_cajero = int(os.environ.get('CAJERO_DOCUMENTO', '2000000'))
    doc_entregador = int(os.environ.get('ENTREGADOR_DOCUMENTO', '3000000'))

    if doc_admin not in documentos_existentes:
        db.session.add(Admin(
            documento=doc_admin,
            nombre=os.environ.get('ADMIN_NOMBRE', 'Administrador SENA'),
            email=os.environ.get('ADMIN_EMAIL', 'admin@cafeteria.com'),
            clave=generate_password_hash(os.environ.get('ADMIN_PASSWORD', 'Admin123')),
            rol='admin',
        ))

    if doc_cajero not in documentos_existentes:
        db.session.add(Admin(
            documento=doc_cajero,
            nombre=os.environ.get('CAJERO_NOMBRE', 'Cajero Principal'),
            email=os.environ.get('CAJERO_EMAIL', 'cajero@cafeteria.com'),
            clave=generate_password_hash(os.environ.get('CAJERO_PASSWORD', 'Cajero123')),
            rol='cajero',
        ))

    if doc_entregador not in documentos_existentes:
        db.session.add(Admin(
            documento=doc_entregador,
            nombre=os.environ.get('ENTREGADOR_NOMBRE', 'Entregador Principal'),
            email=os.environ.get('ENTREGADOR_EMAIL', 'entregador@cafeteria.com'),
            clave=generate_password_hash(os.environ.get('ENTREGADOR_PASSWORD', 'Entregador123')),
            rol='entregador',
        ))

    if not Producto.query.first():
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

    db.session.commit()


if __name__ == '__main__':
    app = create_app('development')
    app.run(debug=True, host='0.0.0.0', port=5545)
