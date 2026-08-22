"""
HU-29: el cliente puede cancelar su propio pedido pendiente, y el
stock se devuelve. No puede cancelar el pedido de otro cliente, ni
uno que ya fue procesado.

HU-27: /admin/ventas/excel y /admin/reportes/excel aceptan un rango de
fechas opcional (?desde=&hasta=).
"""
import os
import tempfile
from datetime import datetime

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_cancel_")
_DB_PATH = os.path.join(_DB_DIR, "test_cafeteria.db")
os.environ['DATABASE_URL'] = f"sqlite:///{_DB_PATH}"
os.environ.pop('SSH_HOST', None)

import pytest

from app import create_app
from app.models import db, Producto, Venta


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


def _crear_pedido(client, doc='90001'):
    client.post('/cliente/registro', data={'documento': doc, 'nombre': 'QA', 'ficha': '1', 'autorizo_datos': '1'})
    with client.session_transaction():
        pass
    resp = client.post('/cliente/confirmar', json={
        'items': [{'idproducto': 1, 'cantidad': 2}]
    })
    return resp.get_json()['idventa']


# ── HU-29 ──────────────────────────────────────────────────────────

def test_cliente_cancela_su_propio_pedido_y_recupera_stock(app, client):
    with app.app_context():
        stock_antes = Producto.query.get(1).stock

    idventa = _crear_pedido(client)
    with app.app_context():
        assert Producto.query.get(1).stock == stock_antes - 2

    resp = client.post(f'/cliente/cancelar/{idventa}', follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        venta = Venta.query.get(idventa)
        assert venta.estado == 'Cancelado'
        assert Producto.query.get(1).stock == stock_antes


def test_no_puede_cancelar_pedido_de_otro_cliente(app, client):
    idventa = _crear_pedido(client, doc='90002')
    # Se identifica como OTRO cliente distinto
    client.get('/cliente/salir')
    client.post('/cliente/registro', data={'documento': '90003', 'nombre': 'Otro', 'ficha': '2', 'autorizo_datos': '1'})

    resp = client.post(f'/cliente/cancelar/{idventa}', follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        assert Venta.query.get(idventa).estado == 'Pendiente de Pago'


def test_no_puede_cancelar_pedido_ya_aceptado(app, client):
    idventa = _crear_pedido(client, doc='90004')
    _login_admin(client)
    client.post(f'/admin/ventas/aceptar/{idventa}')

    client.get('/cliente/salir')
    client.post('/cliente/registro', data={'documento': '90004', 'nombre': 'QA', 'ficha': '1', 'autorizo_datos': '1'})
    resp = client.post(f'/cliente/cancelar/{idventa}', follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        assert Venta.query.get(idventa).estado == 'Pagado/Preparando'


# ── HU-27 ──────────────────────────────────────────────────────────

def test_ventas_excel_acepta_rango_de_fechas(app, client):
    _login_admin(client)
    resp = client.get('/admin/ventas/excel?desde=2020-01-01&hasta=2020-12-31')
    assert resp.status_code == 200
    assert resp.mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def test_reportes_excel_acepta_rango_de_fechas(app, client):
    _login_admin(client)
    resp = client.get('/admin/reportes/excel?desde=2020-01-01&hasta=2020-12-31')
    assert resp.status_code == 200


def test_ventas_excel_con_rango_invalido_no_truena(app, client):
    _login_admin(client)
    resp = client.get('/admin/ventas/excel?desde=fecha-invalida')
    assert resp.status_code == 200
