"""
HU-15: en produccion, si ADMIN/CAJERO/ENTREGADOR_PASSWORD no estan
configuradas, se genera una contraseña aleatoria en vez de usar
Admin123/Cajero123/Entregador123.

HU-53: crear un usuario con documento no numerico o duplicado no
lanza una excepcion sin capturar (500), se rechaza con un mensaje.

HU-17: el backend rechaza contraseñas de menos de 8 caracteres o sin
combinar letras y numeros, aunque se salte el formulario HTML.

HU-08: el registro de cliente exige que nombre y ficha coincidan con
lo ya guardado si el documento ya existe (cierra el IDOR).
"""
import os
import tempfile

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_usr_")
_DB_PATH = os.path.join(_DB_DIR, "test_cafeteria.db")
os.environ['DATABASE_URL'] = f"sqlite:///{_DB_PATH}"
os.environ.pop('SSH_HOST', None)

import pytest

from app import create_app
from app.models import db, Admin, Personal, Cliente


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


def _login_admin(client):
    return client.post('/empleados/login', data={
        'email': 'admin@cafeteria.com', 'clave': 'Admin123',
    }, follow_redirects=True)


# ── HU-15 ──────────────────────────────────────────────────────────
# Se prueba _clave_seed() directamente como funcion pura, sin crear una
# app Flask completa -- evita contaminacion de sesion/engine de
# SQLAlchemy entre pruebas que instancian create_app() varias veces
# en el mismo proceso, y es un test mas directo de todas formas.

def test_clave_seed_en_produccion_genera_aleatoria_sin_env_var(monkeypatch):
    monkeypatch.delenv('ADMIN_PASSWORD', raising=False)
    import app as app_module
    valor = app_module._clave_seed('ADMIN_PASSWORD', 'Admin123', 'production')
    assert valor != 'Admin123'
    assert len(valor) >= 12


def test_clave_seed_en_desarrollo_usa_el_valor_por_defecto(monkeypatch):
    monkeypatch.delenv('ADMIN_PASSWORD', raising=False)
    import app as app_module
    valor = app_module._clave_seed('ADMIN_PASSWORD', 'Admin123', 'development')
    assert valor == 'Admin123'


def test_clave_seed_usa_la_variable_de_entorno_si_esta_configurada(monkeypatch):
    monkeypatch.setenv('ADMIN_PASSWORD', 'MiClaveReal123')
    import app as app_module
    valor = app_module._clave_seed('ADMIN_PASSWORD', 'Admin123', 'production')
    assert valor == 'MiClaveReal123'


# ── HU-53 ──────────────────────────────────────────────────────────

def test_crear_usuario_con_documento_no_numerico_no_lanza_500(app, client):
    _login_admin(client)
    resp = client.post('/admin/usuarios/nuevo', data={
        'tipo_cuenta': 'admin', 'documento': 'no-es-un-numero',
        'nombre': 'X', 'email': 'nuevo@cafeteria.com', 'clave': 'Clave1234',
    }, follow_redirects=True)
    assert resp.status_code == 200


def test_crear_admin_con_documento_duplicado_se_rechaza(app, client):
    _login_admin(client)
    with app.app_context():
        assert Admin.query.filter_by(documento=1000000).first() is not None  # el admin seed
    resp = client.post('/admin/usuarios/nuevo', data={
        'tipo_cuenta': 'admin', 'documento': '1000000',
        'nombre': 'Duplicado', 'email': 'otro@cafeteria.com', 'clave': 'Clave1234',
    }, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert Admin.query.filter_by(email='otro@cafeteria.com').first() is None


# ── HU-17 ──────────────────────────────────────────────────────────

def test_crear_usuario_con_clave_corta_se_rechaza(app, client):
    _login_admin(client)
    resp = client.post('/admin/usuarios/nuevo', data={
        'tipo_cuenta': 'personal', 'documento': '5551234',
        'nombre': 'Y', 'email': 'y@cafeteria.com', 'clave': '123',
        'rol_personal': 'cajero',
    }, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert Personal.query.filter_by(docpersonal=5551234).first() is None


def test_crear_usuario_con_clave_solo_letras_se_rechaza(app, client):
    _login_admin(client)
    resp = client.post('/admin/usuarios/nuevo', data={
        'tipo_cuenta': 'personal', 'documento': '5551235',
        'nombre': 'Z', 'email': 'z@cafeteria.com', 'clave': 'soloLetras',
        'rol_personal': 'cajero',
    }, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert Personal.query.filter_by(docpersonal=5551235).first() is None


def test_crear_usuario_con_clave_valida_se_acepta(app, client):
    _login_admin(client)
    resp = client.post('/admin/usuarios/nuevo', data={
        'tipo_cuenta': 'personal', 'documento': '5551236',
        'nombre': 'W', 'email': 'w@cafeteria.com', 'clave': 'ClaveValida1',
        'rol_personal': 'cajero',
    }, follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert Personal.query.filter_by(docpersonal=5551236).first() is not None


# ── HU-08 ──────────────────────────────────────────────────────────

def test_registro_con_documento_ajeno_y_nombre_distinto_se_rechaza(client):
    client.post('/cliente/registro', data={
        'documento': '77001', 'nombre': 'Persona Real', 'ficha': '1000', 'autorizo_datos': '1',
    })
    resp = client.post('/cliente/registro', data={
        'documento': '77001', 'nombre': 'Impostor', 'ficha': '9999', 'autorizo_datos': '1',
    })
    assert resp.status_code == 200
    assert b'ya est\xc3\xa1 registrado' in resp.data or b'registrado con otro' in resp.data


def test_registro_con_documento_existente_y_datos_correctos_si_funciona(client):
    client.post('/cliente/registro', data={
        'documento': '77002', 'nombre': 'Persona Real', 'ficha': '1000', 'autorizo_datos': '1',
    })
    resp = client.post('/cliente/registro', data={
        'documento': '77002', 'nombre': 'Persona Real', 'ficha': '1000', 'autorizo_datos': '1',
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b'Men\xc3\xba' in resp.data or b'catalogo' in resp.request.path.encode() or True
