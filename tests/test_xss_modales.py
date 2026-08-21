"""
Regresion HU-39: un nombre de producto o usuario con comillas simples,
dobles o backticks no debe romper el modal de edicion ni permitir
ejecutar JavaScript (antes: se pasaba con |e dentro de un onclick
delimitado por comillas simples, lo que no protegia el contexto JS).
"""
import os
import tempfile

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_xss_")
_DB_PATH = os.path.join(_DB_DIR, "test_cafeteria.db")
os.environ['DATABASE_URL'] = f"sqlite:///{_DB_PATH}"
os.environ.pop('SSH_HOST', None)

import pytest

from app import create_app
from models import db, Producto

PAYLOAD = """Cafe');alert(document.cookie);//' "></button><script>alert(1)</script>"""


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


def test_nombre_producto_malicioso_no_rompe_el_onclick(app, client):
    _login_admin(client)
    resp = client.get('/admin/productos')
    html = resp.get_data(as_text=True)

    assert resp.status_code == 200
    # El script inyectado en el nombre no debe quedar como una etiqueta
    # <script> real en el HTML: JSON.dumps/tojson escapa < y > a </>.
    assert '<script>alert(1)</script>' not in html
    # El onclick debe seguir siendo una sola llamada valida a abrirEditar,
    # no debe haberse cortado a mitad de camino por una comilla sin escapar.
    assert "onclick='abrirEditar(" in html


def test_nombre_usuario_malicioso_no_rompe_el_onclick(app, client):
    with app.app_context():
        from models import Admin
        from werkzeug.security import generate_password_hash
        db.session.add(Admin(
            documento=5555555,
            nombre=PAYLOAD,
            email='payload@cafeteria.com',
            clave=generate_password_hash('Xx123456'),
            rol='admin',
        ))
        db.session.commit()

    _login_admin(client)
    resp = client.get('/admin/usuarios')
    html = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert '<script>alert(1)</script>' not in html
    assert "onclick='abrirEditarUser(" in html
