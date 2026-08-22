"""
Regresion HU-25: recuperacion de contrasena para admin/personal via
enlace de un solo uso con expiracion, enviado al correo registrado.
"""
import os
import tempfile
from datetime import datetime, timedelta

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_hu25_")
_DB_PATH = os.path.join(_DB_DIR, "test_cafeteria.db")
os.environ['DATABASE_URL'] = f"sqlite:///{_DB_PATH}"
os.environ.pop('SSH_HOST', None)
os.environ.pop('SMTP_HOST', None)  # sin SMTP configurado: solo se loguea

import pytest

from app import create_app
from app.models import db, Admin, crear_token_recuperacion, validar_token_recuperacion, TokenRecuperacion
from werkzeug.security import generate_password_hash


@pytest.fixture()
def app():
    application = create_app('development')
    application.config['WTF_CSRF_ENABLED'] = False
    application.config['TESTING'] = True
    with application.app_context():
        db.session.add(Admin(
            documento=9025001, nombre='Admin recuperacion',
            email='recuperacion_hu25@cafeteria.com', clave=generate_password_hash('ClaveVieja1'),
            rol='admin',
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


def test_solicitar_recuperacion_no_revela_si_el_correo_existe(client):
    resp_existe = client.post('/empleados/olvide-clave', data={'email': 'recuperacion_hu25@cafeteria.com'},
                               follow_redirects=True)
    resp_no_existe = client.post('/empleados/olvide-clave', data={'email': 'no-existe@cafeteria.com'},
                                  follow_redirects=True)
    assert 'Si el correo está registrado' in resp_existe.get_data(as_text=True)
    assert 'Si el correo está registrado' in resp_no_existe.get_data(as_text=True)


def test_token_permite_cambiar_clave_y_hacer_login_con_la_nueva(app, client):
    with app.app_context():
        token = crear_token_recuperacion('admin', 9025001)

    resp = client.post(f'/empleados/restablecer/{token}', data={'clave': 'ClaveNueva2'},
                        follow_redirects=True)
    assert 'Contraseña actualizada' in resp.get_data(as_text=True)

    resp_login = client.post('/empleados/login', data={
        'email': 'recuperacion_hu25@cafeteria.com', 'clave': 'ClaveNueva2',
    }, follow_redirects=True)
    assert resp_login.status_code == 200
    assert 'Correo o contraseña incorrectos' not in resp_login.get_data(as_text=True)


def test_token_es_de_un_solo_uso(app, client):
    with app.app_context():
        token = crear_token_recuperacion('admin', 9025001)

    client.post(f'/empleados/restablecer/{token}', data={'clave': 'ClaveNueva2'})
    resp_segunda_vez = client.post(f'/empleados/restablecer/{token}', data={'clave': 'OtraClave3'},
                                    follow_redirects=True)
    assert 'no es válido o ya expiró' in resp_segunda_vez.get_data(as_text=True)


def test_token_expirado_es_rechazado(app, client):
    with app.app_context():
        token = crear_token_recuperacion('admin', 9025001, minutos_validez=30)
        registro = TokenRecuperacion.query.first()
        registro.expira = datetime.utcnow() - timedelta(minutes=1)
        db.session.commit()

    resp = client.get(f'/empleados/restablecer/{token}', follow_redirects=True)
    assert 'no es válido o ya expiró' in resp.get_data(as_text=True)


def test_solicitar_nuevo_token_invalida_el_anterior(app, client):
    with app.app_context():
        token_viejo = crear_token_recuperacion('admin', 9025001)
        token_nuevo = crear_token_recuperacion('admin', 9025001)
        assert validar_token_recuperacion(token_viejo) is None
        assert validar_token_recuperacion(token_nuevo) is not None
