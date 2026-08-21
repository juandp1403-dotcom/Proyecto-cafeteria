"""
Regresion HU-59: separar el permiso de solo-ver-la-pagina del permiso
de exportar/ver el detalle con datos personales.

- Un cajero ya no puede abrir /admin/usuarios (gestion de personal).
- Un despachador puede ver /admin/ventas pero no descargar el Excel
  (documento/nombre/ficha de cliente).
"""
import os
import tempfile

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_hu59_")
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
            docpersonal=8881111,
            nombre='Cajero de prueba',
            email='cajero_hu59@cafeteria.com',
            clave=generate_password_hash('Xx123456'),
            rol='cajero',
        ))
        db.session.add(Personal(
            docpersonal=8882222,
            nombre='Despachador de prueba',
            email='despachador_hu59@cafeteria.com',
            clave=generate_password_hash('Xx123456'),
            rol='despachador',
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
    client.post('/empleados/login', data={'email': email, 'clave': 'Xx123456'},
                follow_redirects=True)


def test_cajero_no_puede_abrir_gestion_de_usuarios(client):
    _login(client, 'cajero_hu59@cafeteria.com')
    resp = client.get('/admin/usuarios')
    assert resp.status_code == 403


def test_cajero_no_ve_enlace_a_usuarios_en_el_menu(client):
    _login(client, 'cajero_hu59@cafeteria.com')
    resp = client.get('/admin/ventas')
    html = resp.get_data(as_text=True)
    assert '/admin/usuarios' not in html


def test_despachador_ve_ventas_pero_no_puede_exportar_excel(client):
    _login(client, 'despachador_hu59@cafeteria.com')

    resp_pagina = client.get('/admin/ventas')
    assert resp_pagina.status_code == 200

    resp_excel = client.get('/admin/ventas/excel')
    assert resp_excel.status_code == 403


def test_despachador_no_ve_boton_de_excel(client):
    _login(client, 'despachador_hu59@cafeteria.com')
    resp = client.get('/admin/ventas')
    html = resp.get_data(as_text=True)
    assert 'Descargar Excel del Día' not in html
