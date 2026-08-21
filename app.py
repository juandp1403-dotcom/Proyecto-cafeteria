import os
from datetime import datetime
from flask import Flask, redirect, url_for
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman
from werkzeug.middleware.proxy_fix import ProxyFix
from config import config, _abrir_tunel, _cerrar_tunel, _construir_db_url
from models import db, Admin, Personal
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max
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

    # ── Tunel SSH → DB ──
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
    login_manager.init_app(app)
    login_manager.login_view = 'empleados.login'
    login_manager.login_message = 'Inicia sesión para continuar.'
    login_manager.login_message_category = 'warning'
    login_manager.session_protection = 'strong'

    if config_name == 'production':
        # El proxy reverso (Coolify) termina el TLS y reenvia por HTTP
        # interno; sin esto Flask ve toda peticion como no-segura y
        # Talisman nunca emite Strict-Transport-Security.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

        # HU-19: cabeceras de seguridad HTTP. force_https=False porque el
        # TLS ya lo termina el proxy reverso (Coolify) delante del
        # contenedor -- forzarlo aqui podria causar un loop de redirects.
        Talisman(
            app,
            force_https=False,
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

    from blueprints.cliente   import cliente_bp
    from blueprints.empleados import empleados_bp
    from blueprints.admin     import admin_bp
    from blueprints.permisos  import registrar_context_processor

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

    with app.app_context():
        db.create_all()
        _migrar_esquema()
        _seed_datos_iniciales()

    _iniciar_scheduler(app)

    return app


@login_manager.user_loader
def load_user(user_id):
    if ':' in user_id:
        tipo, doc = user_id.split(':', 1)
        if tipo == 'admin':
            return Admin.query.get(int(doc))
        elif tipo == 'personal':
            return Personal.query.get(int(doc))
    return None


def _migrar_esquema():
    """Ajusta el esquema de la BD segun el motor (solo PostgreSQL)."""
    uri = db.engine.url
    if uri.drivername not in ('postgresql', 'postgresql+psycopg', 'postgresql+psycopg2'):
        return
    from sqlalchemy import text
    try:
        db.session.execute(text(
            "ALTER TABLE admin ALTER COLUMN clave TYPE VARCHAR(256)"
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
    # Agregar columna imagen si no existe
    try:
        db.session.execute(text(
            "ALTER TABLE producto ADD COLUMN IF NOT EXISTS imagen VARCHAR(255)"
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
    # Agregar columna estado a venta si no existe
    try:
        db.session.execute(text(
            "ALTER TABLE venta ADD COLUMN IF NOT EXISTS estado VARCHAR(30) DEFAULT 'Pendiente de Pago'"
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
    # Agregar columna rol a admin si no existe
    try:
        db.session.execute(text(
            "ALTER TABLE admin ADD COLUMN IF NOT EXISTS rol VARCHAR(20) DEFAULT 'admin'"
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
    # Agregar columna stock_minimo a producto si no existe
    try:
        db.session.execute(text(
            "ALTER TABLE producto ADD COLUMN IF NOT EXISTS stock_minimo INT NOT NULL DEFAULT 10"
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
    # Unificar el rol de entrega: 'entregador' no existe en PERMISOS, el valor
    # canonico es 'despachador' (ver HU-33)
    try:
        db.session.execute(text(
            "UPDATE admin SET rol = 'despachador' WHERE rol = 'entregador'"
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()


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
            rol='despachador',
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


def _iniciar_scheduler(app):
    # TODO: implementar reset diario de contadores si se necesita
    pass


if __name__ == '__main__':
    app = create_app('development')
    app.run(debug=True, host='0.0.0.0', port=5545)
