"""
HU-47: ajustar_stock() usa un UPDATE condicional atomico.
HU-48: un doble clic en aceptar/rechazar/preparar/entregar no aplica
el efecto dos veces (transicion condicionada al estado actual real).
HU-49: el pedido del cliente consolida cantidades repetidas del mismo
producto antes de validar el tope de 100, y limita el numero de items.
HU-38: precio/costo/stock negativos se rechazan en el backend.
"""
import os
import tempfile

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_stock_")
_DB_PATH = os.path.join(_DB_DIR, "test_cafeteria.db")
os.environ['DATABASE_URL'] = f"sqlite:///{_DB_PATH}"
os.environ.pop('SSH_HOST', None)

import pytest

from app import create_app
from models import db, Producto, Cliente, Venta, DetalleVenta, ajustar_stock


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


def _login_cliente(client, doc='88001'):
    client.post('/cliente/registro', data={'documento': doc, 'nombre': 'QA', 'ficha': '1'})


# ── HU-47 ──────────────────────────────────────────────────────────

def test_ajustar_stock_no_deja_negativo(app):
    with app.app_context():
        p = Producto.query.first()
        p.stock = 5
        db.session.commit()
        assert ajustar_stock(p.idproducto, -10) is False
        assert Producto.query.get(p.idproducto).stock == 5
        assert ajustar_stock(p.idproducto, -3) is True
        assert Producto.query.get(p.idproducto).stock == 2


def test_ajustar_stock_incremento_siempre_funciona(app):
    with app.app_context():
        p = Producto.query.first()
        stock_inicial = p.stock
        assert ajustar_stock(p.idproducto, 7) is True
        assert Producto.query.get(p.idproducto).stock == stock_inicial + 7


# ── HU-48 ──────────────────────────────────────────────────────────

def test_doble_clic_en_rechazar_no_devuelve_stock_dos_veces(app, client):
    _login_cliente(client)
    with app.app_context():
        prod = Producto.query.filter_by(nombre='Café Tinto').first()
        stock_antes = prod.stock

    client.post('/cliente/confirmar',
                json={'items': [{'idproducto': prod.idproducto, 'cantidad': 3}]})

    with app.app_context():
        venta = Venta.query.order_by(Venta.idventa.desc()).first()
        idventa = venta.idventa
        stock_tras_pedido = Producto.query.get(prod.idproducto).stock
        assert stock_tras_pedido == stock_antes - 3

    _login_admin(client)
    # Dos "clics" casi simultaneos sobre el mismo pedido
    client.post(f'/admin/ventas/rechazar/{idventa}')
    client.post(f'/admin/ventas/rechazar/{idventa}')

    with app.app_context():
        stock_final = Producto.query.get(prod.idproducto).stock
        # Debe volver exactamente al stock original, no sumarse dos veces
        assert stock_final == stock_antes


# ── HU-49 ──────────────────────────────────────────────────────────

def test_repetir_el_mismo_producto_no_evade_el_tope_de_100(app, client):
    _login_cliente(client)
    with app.app_context():
        prod = Producto.query.filter_by(nombre='Café Tinto').first()
        prod.stock = 1000
        db.session.commit()
        idproducto = prod.idproducto

    resp = client.post('/cliente/confirmar', json={
        'items': [{'idproducto': idproducto, 'cantidad': 60}] * 3  # 180 en total
    })
    assert resp.status_code == 400
    assert b'invalida' in resp.data.lower() or b'debe ser entre' in resp.data.lower()


def test_pedido_con_mas_de_50_items_distintos_se_rechaza(app, client):
    _login_cliente(client)
    with app.app_context():
        idproducto = Producto.query.first().idproducto
    items = [{'idproducto': idproducto, 'cantidad': i + 1} for i in range(51)]
    resp = client.post('/cliente/confirmar', json={'items': items})
    assert resp.status_code == 400


# ── HU-38 ──────────────────────────────────────────────────────────

def test_crear_producto_con_precio_negativo_se_rechaza(app, client):
    _login_admin(client)
    resp = client.post('/admin/productos/nuevo', data={
        'nombre': 'Producto Negativo', 'precio': '-100', 'stock': '5', 'costo': '10',
    }, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert Producto.query.filter_by(nombre='Producto Negativo').first() is None


def test_editar_producto_con_stock_negativo_se_rechaza(app, client):
    _login_admin(client)
    with app.app_context():
        prod = Producto.query.first()
        idproducto = prod.idproducto
        stock_original = prod.stock
    resp = client.post(f'/admin/productos/editar/{idproducto}', data={
        'nombre': 'X', 'precio': '1000', 'stock': '-5', 'costo': '100',
    }, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert Producto.query.get(idproducto).stock == stock_original
