"""
Regresion HU-19: en produccion, las respuestas deben incluir cabeceras
de seguridad HTTP (X-Content-Type-Options, X-Frame-Options, CSP,
Strict-Transport-Security). En desarrollo no deben forzarse (para no
romper el flujo local).
"""
import os
import tempfile

import pytest

os.environ.pop('SSH_HOST', None)


def _tmp_db_url():
    d = tempfile.mkdtemp(prefix="cafeteria_test_headers_")
    return f"sqlite:///{d}/test.db"


@pytest.fixture()
def app_production(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', _tmp_db_url())
    monkeypatch.setenv('SECRET_KEY', 'a' * 40)
    import importlib
    import config as config_module
    importlib.reload(config_module)
    import app as app_module
    importlib.reload(app_module)
    application = app_module.create_app('production')
    application.config['TESTING'] = True
    yield application


def test_cabeceras_de_seguridad_presentes_en_produccion(app_production):
    client = app_production.test_client()
    # Simula al proxy reverso (Coolify) indicando que la conexion
    # original del usuario si fue HTTPS, aunque internamente sea HTTP.
    resp = client.get('/cliente/registro', headers={'X-Forwarded-Proto': 'https'})

    assert resp.headers.get('X-Content-Type-Options') == 'nosniff'
    assert resp.headers.get('X-Frame-Options') is not None
    assert resp.headers.get('Content-Security-Policy') is not None
    assert resp.headers.get('Strict-Transport-Security') is not None


def test_respuesta_sigue_siendo_200_sin_redirect_forzado(app_production):
    # force_https=False: no debe redirigir a https en la respuesta de test
    # (el TLS ya lo maneja el proxy reverso delante del contenedor).
    client = app_production.test_client()
    resp = client.get('/cliente/registro')
    assert resp.status_code == 200
