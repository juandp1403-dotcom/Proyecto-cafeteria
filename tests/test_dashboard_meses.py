"""
Regresion HU-55: la grafica mensual del dashboard debe mostrar 12 meses
de calendario consecutivos, sin saltos ni duplicados (el bug original
aproximaba un mes a 30 dias, lo que en ciertas fechas se saltaba febrero).
"""
import os
import re
import json
import tempfile
from datetime import datetime

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_dash_")
_DB_PATH = os.path.join(_DB_DIR, "test_cafeteria.db")
os.environ['DATABASE_URL'] = f"sqlite:///{_DB_PATH}"
os.environ.pop('SSH_HOST', None)

import pytest

from app import create_app
from app.models import db
from app.blueprints.admin.routes import _ultimos_12_meses
from datetime import date


def test_ultimos_12_meses_no_se_salta_febrero():
    # Bug original: partiendo de marzo, restar dias en bloques de 30
    # aproximaba mal y en algunos casos febrero desaparecia del eje.
    meses = _ultimos_12_meses(date(2026, 3, 15))
    claves = [c for c, _ in meses]
    assert '2026-02' in claves
    assert len(claves) == 12
    assert len(set(claves)) == 12
    assert claves[0] == '2025-04'
    assert claves[-1] == '2026-03'


def test_ultimos_12_meses_cruza_el_cambio_de_anio_correctamente():
    meses = _ultimos_12_meses(date(2026, 1, 10))
    claves = [c for c, _ in meses]
    assert claves == [
        '2025-02', '2025-03', '2025-04', '2025-05', '2025-06', '2025-07',
        '2025-08', '2025-09', '2025-10', '2025-11', '2025-12', '2026-01',
    ]


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


def test_grafica_mensual_tiene_12_meses_consecutivos_sin_saltos(client):
    _login_admin(client)
    html = client.get('/admin/').get_data(as_text=True)

    m = re.search(r"getElementById\('chartMensual'\).*?labels:\s*(\[[^\]]*\])", html, re.DOTALL)
    assert m is not None, "No se encontro el arreglo de etiquetas de meses en el dashboard"
    etiquetas = json.loads(m.group(1))

    assert len(etiquetas) == 12
    assert len(set(etiquetas)) == 12  # sin duplicados

    fechas = [datetime.strptime(e, '%b %Y') for e in etiquetas]
    for anterior, siguiente in zip(fechas, fechas[1:]):
        mes_esperado = anterior.month % 12 + 1
        anio_esperado = anterior.year + (1 if anterior.month == 12 else 0)
        assert siguiente.month == mes_esperado
        assert siguiente.year == anio_esperado
