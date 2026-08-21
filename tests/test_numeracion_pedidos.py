"""
HU-57: el numero de pedido consecutivo diario se calcula y guarda una
sola vez al crear la venta, y es el MISMO numero que ve el cliente en
su factura y el que ve el cajero en su lista (antes eran tres fuentes
distintas que no coincidian).
"""
import os
import tempfile

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_numpedido_")
_DB_PATH = os.path.join(_DB_DIR, "test_cafeteria.db")
os.environ['DATABASE_URL'] = f"sqlite:///{_DB_PATH}"
os.environ.pop('SSH_HOST', None)

import pytest

from app import create_app
from models import db, Venta


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


def _pedido(client, doc):
    client.post('/cliente/registro', data={'documento': doc, 'nombre': 'QA', 'ficha': '1'})
    resp = client.post('/cliente/confirmar', json={'items': [{'idproducto': 1, 'cantidad': 1}]})
    return resp.get_json()['idventa']


def test_numeracion_diaria_es_consecutiva_desde_1(app, client):
    id1 = _pedido(client, '96001')
    id2 = _pedido(client, '96002')
    id3 = _pedido(client, '96003')
    with app.app_context():
        assert Venta.query.get(id1).numero_pedido_diario == 1
        assert Venta.query.get(id2).numero_pedido_diario == 2
        assert Venta.query.get(id3).numero_pedido_diario == 3


def test_factura_y_lista_del_cajero_muestran_el_mismo_numero(app, client):
    idventa = _pedido(client, '96004')
    with app.app_context():
        numero_real = Venta.query.get(idventa).numero_pedido_diario

    factura_html = client.get(f'/cliente/factura/{idventa}').get_data(as_text=True)
    assert f'#{numero_real}' in factura_html

    _login_admin(client)
    lista_html = client.get('/admin/ventas').get_data(as_text=True)
    assert f'#{numero_real}' in lista_html
