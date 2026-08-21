"""
Regresion HU-51: en produccion, la cookie de sesion debe tener Secure y
SameSite, y la sesion debe ser permanente con una caducidad de 8 horas.
"""
import os
import tempfile
from datetime import timedelta

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_cookies_")
_DB_PATH = os.path.join(_DB_DIR, "test_cafeteria.db")
os.environ['DATABASE_URL'] = f"sqlite:///{_DB_PATH}"
os.environ.pop('SSH_HOST', None)

import pytest

from app import create_app
from models import db


@pytest.fixture()
def app_production():
    application = create_app('production')
    application.config['WTF_CSRF_ENABLED'] = False
    application.config['TESTING'] = True
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


def test_configuracion_de_cookie_en_produccion(app_production):
    assert app_production.config['SESSION_COOKIE_SECURE'] is True
    assert app_production.config['SESSION_COOKIE_SAMESITE'] == 'Lax'
    assert app_production.config['PERMANENT_SESSION_LIFETIME'] == timedelta(hours=8)
    assert app_production.login_manager.session_protection == 'strong'


def test_login_marca_la_sesion_como_permanente(app_production):
    client = app_production.test_client()
    with client.session_transaction() as sess:
        assert not sess.permanent

    client.post('/empleados/login', data={
        'email': 'admin@cafeteria.com',
        'clave': 'Admin123',
    }, follow_redirects=True)

    with client.session_transaction() as sess:
        assert sess.permanent is True
