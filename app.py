from flask import Flask, redirect, url_for
from flask_login import LoginManager
from config import config
from models import db, Admin
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import date
import atexit

login_manager = LoginManager()


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Extensiones
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view    = 'empleados.login'
    login_manager.login_message = 'Inicia sesión para continuar.'
    login_manager.login_message_category = 'warning'

    # Blueprints
    from blueprints.cliente   import cliente_bp
    from blueprints.empleados import empleados_bp
    from blueprints.admin     import admin_bp

    app.register_blueprint(cliente_bp)
    app.register_blueprint(empleados_bp)
    app.register_blueprint(admin_bp)

    # Ruta raíz → portal cliente
    @app.route('/')
    def index():
        return redirect(url_for('cliente.registro'))

    # Crear tablas y datos iniciales
    with app.app_context():
        db.create_all()
        _seed_datos_iniciales()

    # Scheduler: resetear contador de pedidos a medianoche
    _iniciar_scheduler(app)

    return app


@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))


def _seed_datos_iniciales():
    """Crea un admin por defecto y productos de ejemplo si la BD está vacía."""
    from models import Admin, Producto
    from werkzeug.security import generate_password_hash

    if not Admin.query.first():
        admin = Admin(
            documento = 1000000,
            nombre    = 'Administrador SENA',
            email     = 'admin@sena.edu.co',
            clave     = generate_password_hash('Admin2026*'),
            rol       = 'Administrador'
        )
        cajero = Admin(
            documento = 2000000,
            nombre    = 'Cajero Principal',
            email     = 'cajero@sena.edu.co',
            clave     = generate_password_hash('Cajero2026*'),
            rol       = 'Cajero'
        )
        entregador = Admin(
            documento = 3000000,
            nombre    = 'Entregador Principal',
            email     = 'entregador@sena.edu.co',
            clave     = generate_password_hash('Entrega2026*'),
            rol       = 'Entregador'
        )
        db.session.add_all([admin, cajero, entregador])

    if not Producto.query.first():
        productos = [
            Producto(nombre='Almuerzo Completo',    precio=8000,  stock=50, imagen_url='🍛'),
            Producto(nombre='Sanduche de Pollo',    precio=5000,  stock=30, imagen_url='🥪'),
            Producto(nombre='Jugo Natural',         precio=3000,  stock=40, imagen_url='🥤'),
            Producto(nombre='Café Tinto',           precio=1500,  stock=60, imagen_url='☕'),
            Producto(nombre='Empanada',             precio=2500,  stock=35, imagen_url='🥟'),
            Producto(nombre='Agua Botella 600ml',   precio=2000,  stock=50, imagen_url='💧'),
            Producto(nombre='Ensalada de Frutas',   precio=4000,  stock=20, imagen_url='🍓'),
            Producto(nombre='Chocolate Caliente',   precio=2500,  stock=25, imagen_url='🍫'),
        ]
        db.session.add_all(productos)

    db.session.commit()


def _iniciar_scheduler(app):
    """Programa el reset del contador de pedidos diarios a las 00:00."""
    scheduler = BackgroundScheduler()

    def resetear_contadores():
        with app.app_context():
            # El contador se calcula dinámicamente por fecha en routes.py,
            # no hay columna que resetear manualmente — esta tarea es
            # un placeholder para limpiezas futuras (ej. archivar ventas).
            pass

    scheduler.add_job(resetear_contadores, 'cron', hour=0, minute=0)
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())


if __name__ == '__main__':
    app = create_app('development')
    app.run(debug=True, host='0.0.0.0', port=5000)
