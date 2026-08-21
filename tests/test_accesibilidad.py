"""
Regresion HU-60: los formularios principales tienen label/for asociados,
y las cards de producto del catalogo son accesibles por teclado.
"""
import os
import tempfile
import re

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_a11y_")
_DB_PATH = os.path.join(_DB_DIR, "test_cafeteria.db")
os.environ['DATABASE_URL'] = f"sqlite:///{_DB_PATH}"
os.environ.pop('SSH_HOST', None)

import pytest

from app import create_app
from models import db


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


def _for_ids(html):
    return set(re.findall(r'for="([^"]+)"', html))


def _element_ids(html):
    return set(re.findall(r'id="([^"]+)"', html))


def test_registro_cliente_tiene_labels_asociados(client):
    html = client.get('/cliente/registro').get_data(as_text=True)
    fors = _for_ids(html)
    ids = _element_ids(html)
    assert {'registro-documento', 'registro-nombre', 'registro-ficha'} <= fors
    assert {'registro-documento', 'registro-nombre', 'registro-ficha'} <= ids


def test_login_empleados_tiene_labels_asociados(client):
    html = client.get('/empleados/login').get_data(as_text=True)
    fors = _for_ids(html)
    ids = _element_ids(html)
    assert {'login-email', 'campoPass'} <= fors
    assert {'login-email', 'campoPass'} <= ids


def test_catalogo_cards_accesibles_por_teclado(client):
    html = client.get('/cliente/registro').get_data(as_text=True)
    # el catalogo requiere sesion de cliente; probamos el buscador y,
    # si hay productos sembrados, que las cards tengan role/tabindex.
    with client.session_transaction() as sess:
        sess['cliente_doc'] = 1
        sess['cliente_nombre'] = 'Test'
        sess['cliente_ficha'] = 1
    html = client.get('/cliente/catalogo').get_data(as_text=True)
    assert 'for="buscador-productos"' in html
    if 'producto-card' in html and 'opacity-50' not in html.split('producto-card')[1][:50]:
        assert 'role="button"' in html
        assert 'tabindex="0"' in html
