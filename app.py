import os
from flask import Flask, redirect, url_for
from flask_login import LoginManager
from config import config
from models import db, Admin
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

login_manager = LoginManager()


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'empleados.login'
    login_manager.login_message = 'Inicia sesión para continuar.'
    login_manager.login_message_category = 'warning'

    from blueprints.cliente   import cliente_bp
    from blueprints.empleados import empleados_bp
    from blueprints.admin     import admin_bp

    app.register_blueprint(cliente_bp)
    app.register_blueprint(empleados_bp)
    app.register_blueprint(admin_bp)

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
    return Admin.query.get(int(user_id))


def _migrar_esquema():
    from sqlalchemy import text
    try:
        db.session.execute(text(
            "ALTER TABLE admin ALTER COLUMN clave TYPE VARCHAR(256)"
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()


def _seed_datos_iniciales():
    from models import Admin, Producto
    from werkzeug.security import generate_password_hash

    if not Admin.query.first():
        admin = Admin(
            documento = int(os.environ.get('ADMIN_DOCUMENTO')),
            nombre    = os.environ.get('ADMIN_NOMBRE'),
            email     = os.environ.get('ADMIN_EMAIL'),
            clave     = generate_password_hash(os.environ.get('ADMIN_PASSWORD')),
        )
        db.session.add(admin)

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
    scheduler = BackgroundScheduler()

    def resetear_contadores():
        with app.app_context():
            pass

    scheduler.add_job(resetear_contadores, 'cron', hour=0, minute=0)
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())


if __name__ == '__main__':
    app = create_app('development')
    app.run(debug=True, host='0.0.0.0', port=5545)
