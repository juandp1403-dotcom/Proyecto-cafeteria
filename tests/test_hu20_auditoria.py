"""
Regresion HU-20: acciones sensibles (login fallido, crear/editar/eliminar
usuarios y productos, baja de inventario) quedan registradas en
RegistroAuditoria con usuario, accion, entidad y timestamp. Un admin
puede consultar el log desde /admin/auditoria; un cajero no.
"""
import os
import tempfile

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_hu20_")
_DB_PATH = os.path.join(_DB_DIR, "test_cafeteria.db")
os.environ['DATABASE_URL'] = f"sqlite:///{_DB_PATH}"
os.environ.pop('SSH_HOST', None)

import pytest

from app import create_app
from app.models import db, Admin, Personal, Producto, RegistroAuditoria
from werkzeug.security import generate_password_hash


@pytest.fixture()
def app():
    application = create_app('development')
    application.config['WTF_CSRF_ENABLED'] = False
    application.config['TESTING'] = True
    with application.app_context():
        db.session.add(Admin(
            documento=9020001, nombre='Admin auditoria',
            email='admin_hu20@cafeteria.com', clave=generate_password_hash('Xx123456'),
            rol='admin',
        ))
        db.session.add(Personal(
            docpersonal=9020002, nombre='Cajero auditoria',
            email='cajero_hu20@cafeteria.com', clave=generate_password_hash('Xx123456'),
            rol='cajero',
        ))
        db.session.add(Producto(nombre='Producto HU20', precio=1000, stock=10, costo=500))
        db.session.commit()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture()
def client(app):
    return app.test_client()


def _login(client, email, clave='Xx123456'):
    return client.post('/empleados/login', data={'email': email, 'clave': clave},
                        follow_redirects=True)


def test_login_fallido_queda_registrado(app, client):
    _login(client, 'admin_hu20@cafeteria.com', clave='clave-incorrecta')
    with app.app_context():
        evento = RegistroAuditoria.query.filter_by(accion='login_fallido').first()
        assert evento is not None
        assert evento.usuario == 'admin_hu20@cafeteria.com'
        assert evento.timestamp is not None


def test_crear_producto_queda_registrado(app, client):
    _login(client, 'admin_hu20@cafeteria.com')
    client.post('/admin/productos/nuevo', data={
        'nombre': 'Nuevo producto auditado', 'precio': '2000', 'stock': '5', 'costo': '1000',
    })
    with app.app_context():
        evento = RegistroAuditoria.query.filter_by(accion='crear_producto').first()
        assert evento is not None
        assert evento.usuario == 'admin_hu20@cafeteria.com'


def test_cambio_de_precio_queda_registrado_con_detalle(app, client):
    _login(client, 'admin_hu20@cafeteria.com')
    with app.app_context():
        prod = Producto.query.filter_by(nombre='Producto HU20').first()
        idproducto = prod.idproducto
    client.post(f'/admin/productos/editar/{idproducto}', data={
        'nombre': 'Producto HU20', 'precio': '9999', 'stock': '10', 'costo': '500',
    })
    with app.app_context():
        evento = RegistroAuditoria.query.filter_by(accion='editar_producto').first()
        assert evento is not None
        assert '9999' in (evento.detalle or '')


def test_admin_puede_ver_auditoria_cajero_no(client):
    _login(client, 'admin_hu20@cafeteria.com')
    resp = client.get('/admin/auditoria')
    assert resp.status_code == 200

    client.post('/empleados/logout')
    _login(client, 'cajero_hu20@cafeteria.com')
    resp = client.get('/admin/auditoria')
    assert resp.status_code == 403
