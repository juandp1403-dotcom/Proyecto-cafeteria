"""
Regresion HU-32 / HU-04 (auditoria): antes de este fix, tipo_usuario_actual()
devolvia el string fijo 'admin' para CUALQUIER fila de la tabla `admin`,
sin mirar la columna `rol`. Eso hacia que las cuentas sembradas como
'cajero' o 'entregador' terminaran con permisos de administrador total
(podian crear/editar/eliminar productos y usuarios), y a la vez que
puede('aceptar_rechazar_venta') fuera False incluso para el admin real
(porque PERMISOS['admin'] no tenia ese permiso listado).

Este test cubre exactamente ese caso para que no vuelva a romperse.
"""
import os
import tempfile

# Config.SQLALCHEMY_DATABASE_URI se congela al importar config.py (lectura de
# os.environ.get('DATABASE_URL') a nivel de clase), asi que hay que fijar la
# variable de entorno ANTES de cualquier import del proyecto, en un unico
# archivo para todo el modulo de test (no por-test, no serviria de nada).
_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_")
_DB_PATH = os.path.join(_DB_DIR, "test_cafeteria.db")
os.environ['DATABASE_URL'] = f"sqlite:///{_DB_PATH}"
os.environ.pop('SSH_HOST', None)

import pytest

from app import create_app
from app.models import db, Cliente, Venta


@pytest.fixture()
def app():
    # En Windows el archivo sqlite queda con el handle abierto entre tests;
    # en vez de borrar el archivo, se resetean las tablas dentro de el.
    application = create_app('development')
    application.config['WTF_CSRF_ENABLED'] = False
    application.config['TESTING'] = True
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture()
def client(app):
    return app.test_client()


def _crear_venta_pendiente(app):
    with app.app_context():
        cliente = Cliente(documento=999999, nombre='Cliente de prueba', ficha=1234)
        db.session.add(cliente)
        db.session.commit()
        venta = Venta(cliente=cliente.documento, precio=5000, estado='Pendiente de Pago')
        db.session.add(venta)
        db.session.commit()
        return venta.idventa


def test_cajero_no_tiene_permisos_de_admin_pero_si_puede_operar_ventas(app, client):
    idventa = _crear_venta_pendiente(app)

    login = client.post('/empleados/login', data={
        'email': 'cajero@cafeteria.com',
        'clave': 'Cajero123',
    }, follow_redirects=True)
    assert login.status_code == 200

    # Permiso propio de cajero: SI debe poder aceptar una venta.
    resp_venta = client.post(f'/admin/ventas/aceptar/{idventa}', follow_redirects=True)
    assert resp_venta.status_code != 403, (
        "El cajero deberia poder aceptar ventas (bug original: PERMISOS['admin'] "
        "no tenia 'aceptar_rechazar_venta', y el cajero era tratado como 'admin' fijo)."
    )

    # Permiso exclusivo de escribir_todo/admin: NO debe poder crear productos.
    resp_producto = client.post('/admin/productos/nuevo', data={
        'nombre': 'Producto de prueba',
        'precio': '1000',
        'costo': '500',
        'stock': '10',
    })
    assert resp_producto.status_code == 403, (
        "El cajero NO deberia poder crear productos (bug original: cualquier "
        "cuenta admin: era tratada como rol 'admin' completo, con escribir_todo=True)."
    )


def test_admin_real_conserva_todos_los_permisos(app, client):
    login = client.post('/empleados/login', data={
        'email': 'admin@cafeteria.com',
        'clave': 'Admin123',
    }, follow_redirects=True)
    assert login.status_code == 200

    resp = client.get('/admin/productos')
    assert resp.status_code == 200


def test_seed_usa_rol_despachador_no_entregador(app):
    """HU-33: el rol 'entregador' no existe en PERMISOS (queda sin permisos
    reales). El seed debe usar el valor canonico 'despachador'."""
    with app.app_context():
        from app.models import Admin
        cuenta = Admin.query.filter_by(email='entregador@cafeteria.com').first()
        assert cuenta is not None
        assert cuenta.rol == 'despachador'
