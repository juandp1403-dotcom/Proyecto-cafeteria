"""
Regresion: un documento o ficha con un valor numerico fuera del rango
de una columna db.Integer (ej. escrito accidentalmente dos veces, o de
forma maliciosa) debe rechazarse con un mensaje claro, no crashear con
un OverflowError sin manejar al llegar al driver de la base de datos.
"""
import os
import tempfile

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_overflow_")
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


def test_documento_demasiado_grande_se_rechaza_sin_crashear(client):
    resp = client.post('/cliente/registro', data={
        'documento': '10505060601050506060',  # 20 digitos, fuera de rango int32
        'nombre': 'QA', 'ficha': '1', 'autorizo_datos': '1',
    })
    assert resp.status_code == 200
    assert b'v\xc3\xa1lidos' in resp.data or b'numericos' in resp.data.lower()


def test_ficha_demasiado_grande_se_rechaza_sin_crashear(client):
    resp = client.post('/cliente/registro', data={
        'documento': '1050506060', 'nombre': 'QA',
        'ficha': '99999999999999999999', 'autorizo_datos': '1',
    })
    assert resp.status_code == 200


def test_documento_cero_o_negativo_se_rechaza(client):
    resp = client.post('/cliente/registro', data={
        'documento': '-5', 'nombre': 'QA', 'ficha': '1', 'autorizo_datos': '1',
    })
    assert resp.status_code == 200
