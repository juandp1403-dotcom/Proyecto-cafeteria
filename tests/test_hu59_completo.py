"""
HU-59 completo: combina lo que ya trajo el equipo (enmascarado de datos
personales por rol) con lo que le faltaba segun el criterio de aceptacion
original -- "un cajero ya no puede abrir la gestion de usuarios".
"""
import os
import tempfile

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_hu59c_")
_DB_PATH = os.path.join(_DB_DIR, "test_cafeteria.db")
os.environ['DATABASE_URL'] = f"sqlite:///{_DB_PATH}"
os.environ.pop('SSH_HOST', None)

import pytest

from app import create_app
from models import db, Personal
from werkzeug.security import generate_password_hash


@pytest.fixture()
def app():
    application = create_app('development')
    application.config['WTF_CSRF_ENABLED'] = False
    application.config['TESTING'] = True
    with application.app_context():
        db.session.add(Personal(
            docpersonal=8891111, nombre='Cajero HU59c',
            email='cajero_hu59c@cafeteria.com', clave=generate_password_hash('Xx123456'),
            rol='cajero',
        ))
        db.session.add(Personal(
            docpersonal=8892222, nombre='Auditor HU59c',
            email='auditor_hu59c@cafeteria.com', clave=generate_password_hash('Xx123456'),
            rol='auditor',
        ))
        db.session.commit()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture()
def client(app):
    return app.test_client()


def _login(client, email):
    client.post('/empleados/login', data={'email': email, 'clave': 'Xx123456'}, follow_redirects=True)


def test_cajero_no_puede_abrir_gestion_de_usuarios(client):
    _login(client, 'cajero_hu59c@cafeteria.com')
    resp = client.get('/admin/usuarios')
    assert resp.status_code == 403


def test_auditor_puede_abrir_usuarios_pero_ve_datos_enmascarados(client):
    _login(client, 'auditor_hu59c@cafeteria.com')
    resp = client.get('/admin/usuarios')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # el auditor no tiene ver_datos_personales -- debe ver iniciales, no el nombre completo
    assert 'cajero_hu59c@cafeteria.com' not in html
    assert '***@***' in html
