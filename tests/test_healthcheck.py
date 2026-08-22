"""
Regresion HU-03: /healthz responde 200 sin autenticacion y sin exponer
datos sensibles.
"""
import os
import tempfile

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_health_")
_DB_PATH = os.path.join(_DB_DIR, "test_cafeteria.db")
os.environ['DATABASE_URL'] = f"sqlite:///{_DB_PATH}"
os.environ.pop('SSH_HOST', None)

import pytest

from app import create_app
from app.models import db


@pytest.fixture()
def app():
    application = create_app('development')
    application.config['TESTING'] = True
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


def test_healthz_responde_200_sin_login(app):
    client = app.test_client()
    resp = client.get('/healthz')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == {'status': 'ok'}
    # Nada de contraseñas, tokens ni info de conexion en la respuesta.
    body = resp.get_data(as_text=True).lower()
    for palabra in ('password', 'clave', 'secret', 'token', 'postgresql://'):
        assert palabra not in body
