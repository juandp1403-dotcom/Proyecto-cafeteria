"""
Regresion HU-14: el login de empleados responde 429 tras 5 intentos por
minuto desde la misma IP.

Regresion HU-9: /cliente/registro responde 429 tras 10 intentos por
minuto desde la misma IP.
"""
import os
import tempfile

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_ratelimit_")
_DB_PATH = os.path.join(_DB_DIR, "test_cafeteria.db")
os.environ['DATABASE_URL'] = f"sqlite:///{_DB_PATH}"
os.environ.pop('SSH_HOST', None)

import pytest

from app import create_app
from app.models import db


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


def test_login_responde_429_tras_5_intentos_por_minuto(client):
    for _ in range(5):
        resp = client.post('/empleados/login', data={'email': 'x@x.com', 'clave': 'mal'})
        assert resp.status_code != 429

    resp = client.post('/empleados/login', data={'email': 'x@x.com', 'clave': 'mal'})
    assert resp.status_code == 429


def test_registro_responde_429_tras_10_intentos_por_minuto(client):
    for i in range(10):
        resp = client.post('/cliente/registro', data={
            'documento': str(1000 + i), 'nombre': 'Test', 'ficha': '1',
        })
        assert resp.status_code != 429

    resp = client.post('/cliente/registro', data={
        'documento': '9999', 'nombre': 'Test', 'ficha': '1',
    })
    assert resp.status_code == 429
