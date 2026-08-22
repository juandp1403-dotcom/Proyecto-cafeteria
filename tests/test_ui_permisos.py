"""
Regresion HU-58: un rol sin permiso de escritura (auditor) no debe ver
los botones de crear/editar/eliminar usuarios, solo "Solo lectura".
El admin (con escribir_todo) si debe seguir viendolos.
"""
import os
import tempfile

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_ui_")
_DB_PATH = os.path.join(_DB_DIR, "test_cafeteria.db")
os.environ['DATABASE_URL'] = f"sqlite:///{_DB_PATH}"
os.environ.pop('SSH_HOST', None)

import pytest

from app import create_app
from app.models import db, Personal
from werkzeug.security import generate_password_hash


@pytest.fixture()
def app():
    application = create_app('development')
    application.config['WTF_CSRF_ENABLED'] = False
    application.config['TESTING'] = True
    with application.app_context():
        db.session.add(Personal(
            docpersonal=7777777,
            nombre='Auditor de prueba',
            email='auditor@cafeteria.com',
            clave=generate_password_hash('Xx123456'),
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


def test_auditor_no_ve_botones_de_escritura_en_usuarios(client):
    client.post('/empleados/login', data={
        'email': 'auditor@cafeteria.com', 'clave': 'Xx123456',
    }, follow_redirects=True)

    resp = client.get('/admin/usuarios')
    html = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'Nuevo Usuario' not in html
    assert 'Solo lectura' in html
    # Los modales en si no deben existir en el DOM (el id="..." del div,
    # no el string suelto que igual aparece dentro de la funcion JS
    # abrirEditarUser(), que queda inerte sin boton que la invoque).
    assert 'id="modalNuevoUser"' not in html
    assert 'id="modalEditarUser"' not in html


def test_admin_si_ve_botones_de_escritura_en_usuarios(client):
    client.post('/empleados/login', data={
        'email': 'admin@cafeteria.com', 'clave': 'Admin123',
    }, follow_redirects=True)

    resp = client.get('/admin/usuarios')
    html = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'Nuevo Usuario' in html
    assert 'id="modalNuevoUser"' in html
    assert 'Solo lectura' not in html
