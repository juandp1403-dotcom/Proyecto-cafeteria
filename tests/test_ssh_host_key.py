"""
Regresion HU-43: sin SSH_HOST_KEY configurada, SSHTunnelForwarder acepta
cualquier clave de host del servidor remoto (riesgo de MITM). En
produccion esto ahora debe fallar explicito; en desarrollo solo advierte.
"""
import os
import pytest

os.environ.pop('SSH_HOST_KEY', None)

import config.config as config


def test_sin_ssh_host_key_falla_explicito_en_produccion(monkeypatch):
    monkeypatch.setenv('SSH_HOST', 'db.ejemplo.com')
    monkeypatch.delenv('SSH_HOST_KEY', raising=False)
    config._tunnel = None

    with pytest.raises(RuntimeError, match='SSH_HOST_KEY'):
        config._abrir_tunel(config_name='production')


def test_sin_ssh_host_key_solo_advierte_en_desarrollo(monkeypatch, capsys):
    monkeypatch.setenv('SSH_HOST', 'db.ejemplo.com')
    monkeypatch.delenv('SSH_HOST_KEY', raising=False)
    config._tunnel = None

    # En desarrollo no debe lanzar RuntimeError por la falta de la clave
    # (fallara mas adelante al intentar conectar de verdad, pero no por
    # la validacion de SSH_HOST_KEY en si).
    try:
        config._abrir_tunel(config_name='development')
    except RuntimeError as e:
        assert 'SSH_HOST_KEY' not in str(e)
    except Exception:
        pass  # falla de conexion real esperada (no hay servidor SSH de verdad)

    salida = capsys.readouterr().out
    assert 'SSH_HOST_KEY' in salida


def test_formato_invalido_de_ssh_host_key_lanza_error_claro(monkeypatch):
    monkeypatch.setenv('SSH_HOST_KEY', 'esto-no-es-una-clave-valida')
    with pytest.raises(RuntimeError, match='formato invalido'):
        config._cargar_ssh_host_key('db.ejemplo.com')


def test_ssh_host_key_valida_se_carga_correctamente(monkeypatch):
    # Clave ed25519 de ejemplo, formato real de known_hosts.
    clave = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJBM0FKMZ2wkoLcNyqBHoxUYAxvKna4cJ5EiF8XeeVvB"
    monkeypatch.setenv('SSH_HOST_KEY', clave)
    key = config._cargar_ssh_host_key('db.ejemplo.com')
    assert key is not None
