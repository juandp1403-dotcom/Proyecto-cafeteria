"""
HU-71: la baja de inventario guarda una categoria estructurada
(Vencido/Dañado/Otro), no solo texto libre.

HU-68: un producto se puede marcar como especial y aparece con badge
distinto en el catalogo.

HU-76: la venta guarda el metodo de pago (Efectivo por defecto si no
se envia uno valido).
"""
import os
import tempfile

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_cat_")
_DB_PATH = os.path.join(_DB_DIR, "test_cafeteria.db")
os.environ['DATABASE_URL'] = f"sqlite:///{_DB_PATH}"
os.environ.pop('SSH_HOST', None)

import pytest

from app import create_app
from models import db, Producto, BajaInventario, Venta


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


# ── HU-71 ──────────────────────────────────────────────────────────

def test_baja_de_inventario_guarda_categoria_vencido(app, client):
    _login_admin(client)
    with app.app_context():
        idproducto = Producto.query.first().idproducto
    client.post(f'/admin/productos/baja/{idproducto}', data={
        'cantidad': '2', 'motivo': 'Vencido',
    }, follow_redirects=True)
    with app.app_context():
        baja = BajaInventario.query.filter_by(idproducto=idproducto).first()
        assert baja.categoria == 'Vencido'


def test_baja_con_motivo_libre_cae_en_categoria_otro(app, client):
    _login_admin(client)
    with app.app_context():
        idproducto = Producto.query.first().idproducto
    client.post(f'/admin/productos/baja/{idproducto}', data={
        'cantidad': '1', 'motivo': 'Se cayo de la mesa',
    }, follow_redirects=True)
    with app.app_context():
        baja = BajaInventario.query.filter_by(idproducto=idproducto).first()
        assert baja.categoria == 'Otro'


# ── HU-68 ──────────────────────────────────────────────────────────

def test_crear_producto_especial_se_marca_correctamente(app, client):
    _login_admin(client)
    client.post('/admin/productos/nuevo', data={
        'nombre': 'Combo Especial', 'precio': '5000', 'stock': '10',
        'costo': '2000', 'es_especial': '1',
    }, follow_redirects=True)
    with app.app_context():
        prod = Producto.query.filter_by(nombre='Combo Especial').first()
        assert prod.es_especial is True


def test_catalogo_muestra_badge_especial(app, client):
    with app.app_context():
        prod = Producto.query.filter_by(nombre='Café Tinto').first()
        prod.es_especial = True
        db.session.commit()
    client.post('/cliente/registro', data={'documento': '95001', 'nombre': 'QA', 'ficha': '1'})
    resp = client.get('/cliente/catalogo')
    assert 'Especial'.encode() in resp.data


# ── HU-76 ──────────────────────────────────────────────────────────

def test_venta_guarda_metodo_pago_enviado(app, client):
    client.post('/cliente/registro', data={'documento': '95002', 'nombre': 'QA', 'ficha': '1'})
    resp = client.post('/cliente/confirmar', json={
        'items': [{'idproducto': 1, 'cantidad': 1}], 'metodo_pago': 'Tarjeta',
    })
    idventa = resp.get_json()['idventa']
    with app.app_context():
        assert Venta.query.get(idventa).metodo_pago == 'Tarjeta'


def test_venta_sin_metodo_pago_usa_efectivo_por_defecto(app, client):
    client.post('/cliente/registro', data={'documento': '95003', 'nombre': 'QA', 'ficha': '1'})
    resp = client.post('/cliente/confirmar', json={
        'items': [{'idproducto': 1, 'cantidad': 1}],
    })
    idventa = resp.get_json()['idventa']
    with app.app_context():
        assert Venta.query.get(idventa).metodo_pago == 'Efectivo'
