"""
HU-07: suite de pruebas de la matriz de permisos por rol.

Recorre cada rol (admin, auditor, cajero, despachador) contra cada
pagina protegida de /admin/* y confirma que el resultado coincide
exactamente con blueprints/permisos.py::PERMISOS -- si alguien cambia
la matriz de permisos sin querer, esta prueba debe romperse.
"""
import os
import tempfile

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_matriz_")
_DB_PATH = os.path.join(_DB_DIR, "test_cafeteria.db")
os.environ['DATABASE_URL'] = f"sqlite:///{_DB_PATH}"
os.environ.pop('SSH_HOST', None)

import pytest

from app import create_app
from app.models import db, Admin, Personal
from app.blueprints.permisos import PERMISOS
from werkzeug.security import generate_password_hash

CREDENCIALES = {
    'admin': 'admin_matriz@cafeteria.com',
    'auditor': 'auditor_matriz@cafeteria.com',
    'cajero': 'cajero_matriz@cafeteria.com',
    'despachador': 'despachador_matriz@cafeteria.com',
}

RUTA_POR_PAGINA = {
    'dashboard': '/admin/',
    'productos': '/admin/productos',
    'ventas': '/admin/ventas',
    'compras': '/admin/compras',
    'usuarios': '/admin/usuarios',
    'reportes': '/admin/reportes',
}


@pytest.fixture()
def app():
    application = create_app('development')
    application.config['WTF_CSRF_ENABLED'] = False
    application.config['TESTING'] = True
    with application.app_context():
        db.session.add(Admin(
            documento=9010001, nombre='Admin matriz',
            email=CREDENCIALES['admin'], clave=generate_password_hash('Xx123456'),
            rol='admin',
        ))
        db.session.add(Personal(
            docpersonal=9010002, nombre='Auditor matriz',
            email=CREDENCIALES['auditor'], clave=generate_password_hash('Xx123456'),
            rol='auditor',
        ))
        db.session.add(Personal(
            docpersonal=9010003, nombre='Cajero matriz',
            email=CREDENCIALES['cajero'], clave=generate_password_hash('Xx123456'),
            rol='cajero',
        ))
        db.session.add(Personal(
            docpersonal=9010004, nombre='Despachador matriz',
            email=CREDENCIALES['despachador'], clave=generate_password_hash('Xx123456'),
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


def _login(client, rol):
    client.post('/empleados/login', data={
        'email': CREDENCIALES[rol], 'clave': 'Xx123456',
    }, follow_redirects=True)


def _casos_matriz():
    """Genera (rol, pagina, deberia_poder) para cada combinacion, a
    partir de la propia PERMISOS['<rol>']['paginas'] -- la fuente de
    verdad es el codigo de produccion, no una copia hardcodeada aqui."""
    casos = []
    for rol in CREDENCIALES:
        paginas_permitidas = set(PERMISOS[rol]['paginas'])
        for pagina in RUTA_POR_PAGINA:
            casos.append((rol, pagina, pagina in paginas_permitidas))
    return casos


@pytest.mark.parametrize('rol,pagina,deberia_poder', _casos_matriz())
def test_matriz_permisos_por_rol(client, rol, pagina, deberia_poder):
    _login(client, rol)
    resp = client.get(RUTA_POR_PAGINA[pagina])
    if deberia_poder:
        assert resp.status_code == 200, (
            f"{rol} deberia poder ver '{pagina}' pero recibio {resp.status_code}"
        )
    else:
        assert resp.status_code == 403, (
            f"{rol} NO deberia poder ver '{pagina}' pero recibio {resp.status_code}"
        )


def test_sin_sesion_toda_pagina_admin_redirige_a_login(client):
    for ruta in RUTA_POR_PAGINA.values():
        resp = client.get(ruta, follow_redirects=False)
        assert resp.status_code in (301, 302), f"{ruta} deberia exigir login"
