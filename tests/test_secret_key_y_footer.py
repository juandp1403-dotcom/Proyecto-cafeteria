"""
Regresion HU-16: en produccion, SECRET_KEY debe existir, no ser el valor
por defecto del codigo, y tener al menos 32 caracteres.

Regresion HU-64: el año del footer se calcula, no queda hardcodeado.
"""
import os
import tempfile
from datetime import datetime

import pytest

os.environ.pop('SSH_HOST', None)


def _tmp_db_url():
    d = tempfile.mkdtemp(prefix="cafeteria_test_secret_")
    return f"sqlite:///{d}/test.db"


def test_secret_key_por_defecto_falla_en_produccion(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', _tmp_db_url())
    monkeypatch.delenv('SECRET_KEY', raising=False)
    import importlib
    import config
    importlib.reload(config)  # SECRET_KEY se lee a nivel de clase
    import app as app_module
    importlib.reload(app_module)

    with pytest.raises(RuntimeError, match='SECRET_KEY'):
        app_module.create_app('production')


def test_secret_key_corta_falla_en_produccion(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', _tmp_db_url())
    monkeypatch.setenv('SECRET_KEY', 'corta123')
    import importlib
    import config
    importlib.reload(config)
    import app as app_module
    importlib.reload(app_module)

    with pytest.raises(RuntimeError, match='SECRET_KEY'):
        app_module.create_app('production')


def test_secret_key_valida_permite_arrancar(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', _tmp_db_url())
    monkeypatch.setenv('SECRET_KEY', 'a' * 40)
    import importlib
    import config
    importlib.reload(config)
    import app as app_module
    importlib.reload(app_module)

    application = app_module.create_app('production')
    assert application is not None


def test_footer_muestra_el_anio_actual(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', _tmp_db_url())
    monkeypatch.setenv('SECRET_KEY', 'a' * 40)
    import importlib
    import config
    importlib.reload(config)
    import app as app_module
    importlib.reload(app_module)

    application = app_module.create_app('development')
    client = application.test_client()
    html = client.get('/cliente/registro').get_data(as_text=True)
    assert f'{datetime.utcnow().year}' in html
    assert '{{ 2026 }}' not in html
