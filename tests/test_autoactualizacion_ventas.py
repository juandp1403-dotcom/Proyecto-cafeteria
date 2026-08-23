"""
Auto-actualizacion de la vista de Ventas (HU-26, mismo patron de polling
liviano que cliente/estado_pedido.html): endpoint minimo /ventas/ultimo/json
protegido por requiere_ver_pagina('ventas') y deteccion de pedidos nuevos.
"""
import os
import tempfile

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_autovtas_")
_DB_PATH = os.path.join(_DB_DIR, "test_cafeteria.db")
os.environ['DATABASE_URL'] = f"sqlite:///{_DB_PATH}"
os.environ.pop('SSH_HOST', None)

import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.models import db, Cliente, Personal, Venta
from app.utils import ahora_bogota


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


def _crear_venta(precio=5000):
    """Crea una venta directa en BD y retorna su id."""
    doc = f'9000{Venta.query.count() + 1}'
    cli = Cliente(documento=doc, nombre=f'Cliente {doc}', ficha='12345')
    db.session.add(cli)
    db.session.flush()
    venta = Venta(cliente=doc, precio=precio, estado='Entregado',
                  fechaventa=ahora_bogota())
    db.session.add(venta)
    db.session.commit()
    return venta.idventa


def test_endpoint_devuelve_ultimo_id_y_suben_con_ventas_nuevas(app, client):
    _login_admin(client)

    resp = client.get('/admin/ventas/ultimo/json')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'ultimo_id' in data
    assert data['ultimo_id'] == 0  # sin ventas todavia

    id1 = None
    with app.app_context():
        id1 = _crear_venta()
    assert client.get('/admin/ventas/ultimo/json').get_json()['ultimo_id'] == id1

    with app.app_context():
        id2 = _crear_venta()
    assert id2 > id1
    assert client.get('/admin/ventas/ultimo/json').get_json()['ultimo_id'] == id2


def test_sin_sesion_redirige_al_login(app, client):
    resp = client.get('/admin/ventas/ultimo/json')
    assert resp.status_code == 302


def test_personal_sin_pagina_ventas_recibe_403(app, client):
    # 'mesero' no existe en PERMISOS -> sin paginas asignadas -> 403,
    # igual que reciberia al abrir /admin/ventas.
    with app.app_context():
        db.session.add(Personal(
            docpersonal=4321, nombre='Mesero Prueba',
            clave=generate_password_hash('Mesero123.'),
            email='mesero@test.com', rol='mesero', activo=True,
        ))
        db.session.commit()

    login = client.post('/empleados/login', data={
        'email': 'mesero@test.com', 'clave': 'Mesero123.',
    }, follow_redirects=True)
    assert login.status_code == 200

    resp_json = client.get('/admin/ventas/ultimo/json')
    assert resp_json.status_code == 403
    # La vista normal se comporta igual para ese rol.
    assert client.get('/admin/ventas').status_code == 403


def test_vista_ventas_expone_el_ultimo_id_de_la_pagina(app, client):
    _login_admin(client)
    with app.app_context():
        id1 = _crear_venta(4000)
    html = client.get('/admin/ventas?periodo=todos').get_data(as_text=True)
    # El script de polling arranca con el id mas alto de la pagina actual.
    assert f'let ultimoIdConocido = {id1};' in html