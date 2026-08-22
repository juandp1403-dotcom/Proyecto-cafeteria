"""
Regresion HU-26: el cliente puede ver la actualizacion de estado de su
pedido en tiempo real via polling, sin recargar la pagina.

- /cliente/estado/<id>/json expone solo el estado, con el mismo control
  de acceso que la vista HTML (dueño del pedido o personal autenticado).
- La plantilla incluye el script de polling.
"""
import os
import tempfile

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_hu26_")
_DB_PATH = os.path.join(_DB_DIR, "test_cafeteria.db")
os.environ['DATABASE_URL'] = f"sqlite:///{_DB_PATH}"
os.environ.pop('SSH_HOST', None)

import pytest

from app import create_app
from app.models import db, Producto, Cliente, Venta, DetalleVenta


@pytest.fixture()
def app():
    application = create_app('development')
    application.config['WTF_CSRF_ENABLED'] = False
    application.config['TESTING'] = True
    with application.app_context():
        prod = Producto(nombre='Producto HU26', precio=1000, stock=10, costo=500)
        db.session.add(prod)
        cli = Cliente(documento=9026001, nombre='Cliente HU26', ficha=111)
        db.session.add(cli)
        db.session.commit()
        venta = Venta(precio=1000, cliente=cli.documento, estado='Pagado/Preparando', numero_pedido_diario=1)
        db.session.add(venta)
        db.session.commit()
        db.session.add(DetalleVenta(idventa=venta.idventa, idproducto=prod.idproducto, cantidad=1))
        db.session.commit()
        app_state = {'idventa': venta.idventa, 'doc': cli.documento}
    application.config['_hu26_state'] = app_state
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture()
def client(app):
    return app.test_client()


def test_dueno_del_pedido_puede_consultar_su_estado(app, client):
    state = app.config['_hu26_state']
    with client.session_transaction() as sess:
        sess['cliente_doc'] = state['doc']

    resp = client.get(f"/cliente/estado/{state['idventa']}/json")
    assert resp.status_code == 200
    assert resp.get_json()['estado'] == 'Pagado/Preparando'


def test_otro_visitante_no_puede_consultar_el_estado(app, client):
    state = app.config['_hu26_state']
    resp = client.get(f"/cliente/estado/{state['idventa']}/json")
    assert resp.status_code == 403


def test_pagina_de_estado_incluye_el_script_de_polling(app, client):
    state = app.config['_hu26_state']
    with client.session_transaction() as sess:
        sess['cliente_doc'] = state['doc']

    resp = client.get(f"/cliente/estado/{state['idventa']}")
    html = resp.get_data(as_text=True)
    assert '/json' in html
    assert 'setInterval' in html
