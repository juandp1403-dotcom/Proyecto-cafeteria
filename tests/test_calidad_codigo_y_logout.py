"""
HU-22: Reporte.to_dict() ya no revienta con AttributeError (admin_rel
ahora existe de verdad); Venta.to_dict() muerto se elimino.

HU-46: un DDL de migracion que falla queda logueado, no silencioso.

HU-52: logout exige POST (antes GET permitia CSRF de bajo impacto via
<img src="/empleados/logout">).

HU-11: seleccionar una imagen de biblioteca que no existe en la lista
real (path traversal) se ignora en vez de copiarse.
"""
import os
import io
import logging
import tempfile

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_calidad_")
_DB_PATH = os.path.join(_DB_DIR, "test_cafeteria.db")
os.environ['DATABASE_URL'] = f"sqlite:///{_DB_PATH}"
os.environ.pop('SSH_HOST', None)

import pytest

from app import create_app, _ejecutar_migracion
from models import db, Producto, Admin, Reporte


@pytest.fixture()
def app():
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


def _login_admin(client):
    return client.post('/empleados/login', data={
        'email': 'admin@cafeteria.com', 'clave': 'Admin123',
    }, follow_redirects=True)


# ── HU-22 ──────────────────────────────────────────────────────────

def test_reporte_to_dict_no_lanza_attributeerror(app):
    with app.app_context():
        prod = Producto.query.first()
        admin = Admin.query.first()
        r = Reporte(idadmin=admin.documento, descripcion='test', producto=prod.idproducto)
        db.session.add(r)
        db.session.commit()
        data = r.to_dict()  # no debe lanzar AttributeError
        assert data['nombre_admin'] == admin.nombre


def test_venta_ya_no_tiene_to_dict_muerto():
    from models import Venta
    assert not hasattr(Venta, 'to_dict')


# ── HU-46 ──────────────────────────────────────────────────────────

def test_migracion_fallida_queda_logueada(app, caplog):
    with app.app_context():
        with caplog.at_level(logging.WARNING):
            _ejecutar_migracion("ESTO NO ES SQL VALIDO NUNCA")
        assert any('Migracion de esquema fallo' in r.message for r in caplog.records)


# ── HU-52 ──────────────────────────────────────────────────────────

def test_logout_por_get_ya_no_funciona(app, client):
    _login_admin(client)
    resp = client.get('/empleados/logout')
    assert resp.status_code == 405  # Method Not Allowed


def test_logout_por_post_si_funciona(app, client):
    _login_admin(client)
    resp = client.post('/empleados/logout', follow_redirects=True)
    assert resp.status_code == 200


# ── HU-11 ──────────────────────────────────────────────────────────

def test_seleccionar_imagen_de_biblioteca_inexistente_no_la_copia(app, client):
    _login_admin(client)
    resp = client.post('/admin/productos/nuevo', data={
        'nombre': 'Producto con imagen falsa',
        'precio': '1000', 'stock': '5', 'costo': '100',
        'imagen_biblioteca': '../../../../etc/passwd',
    }, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        prod = Producto.query.filter_by(nombre='Producto con imagen falsa').first()
        assert prod is not None
        assert prod.imagen is None  # no se copio nada
