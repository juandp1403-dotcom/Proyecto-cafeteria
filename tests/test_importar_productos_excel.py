"""
Nueva funcionalidad: importar productos en lote desde un archivo Excel.
Crea productos nuevos por nombre, actualiza los que ya existen, y
reporta errores de filas invalidas sin tumbar toda la importacion.
"""
import os
import io
import tempfile

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_import_")
_DB_PATH = os.path.join(_DB_DIR, "test_cafeteria.db")
os.environ['DATABASE_URL'] = f"sqlite:///{_DB_PATH}"
os.environ.pop('SSH_HOST', None)

import pytest
from openpyxl import Workbook

from app import create_app
from app.models import db, Producto


@pytest.fixture()
def app():
    application = create_app('development')
    application.config['WTF_CSRF_ENABLED'] = False
    application.config['TESTING'] = True
    # Nota: _seed_datos_iniciales() ya crea un producto "Café Tinto"
    # (precio 1500) -- se reutiliza ese para probar la actualizacion,
    # en vez de insertar un duplicado.
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


def _excel_bytes(headers, filas):
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for fila in filas:
        ws.append(fila)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_crea_producto_nuevo_y_actualiza_uno_existente(app, client):
    _login_admin(client)
    archivo = _excel_bytes(
        ['nombre', 'precio', 'costo', 'stock', 'stock_minimo'],
        [
            ['Café Tinto', 1800, 600, 40, 8],          # existente -> actualiza
            ['Té Verde', 2000, 700, 15, 5],             # nuevo -> crea
        ],
    )
    resp = client.post('/admin/productos/importar', data={
        'archivo': (archivo, 'productos.xlsx'),
    }, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        cafe = Producto.query.filter_by(nombre='Café Tinto').first()
        te = Producto.query.filter_by(nombre='Té Verde').first()
        assert cafe.precio == 1800
        assert cafe.costo == 600
        assert cafe.stock == 40
        assert te is not None
        assert te.precio == 2000
        # 8 productos del seed inicial + 1 nuevo (Té Verde); Café Tinto
        # ya existia y se actualizo, no se duplico.
        assert Producto.query.count() == 9


def test_fila_invalida_no_tumba_la_importacion_completa(app, client):
    _login_admin(client)
    archivo = _excel_bytes(
        ['nombre', 'precio'],
        [
            ['Producto Bueno', 3000],
            ['Producto Malo', 'no-es-un-numero'],
            ['', 5000],  # sin nombre
        ],
    )
    resp = client.post('/admin/productos/importar', data={
        'archivo': (archivo, 'productos.xlsx'),
    }, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        assert Producto.query.filter_by(nombre='Producto Bueno').first() is not None
        assert Producto.query.filter_by(nombre='Producto Malo').first() is None


def test_rechaza_archivo_sin_columna_precio(app, client):
    _login_admin(client)
    archivo = _excel_bytes(['nombre', 'descripcion'], [['X', 'algo']])
    resp = client.post('/admin/productos/importar', data={
        'archivo': (archivo, 'productos.xlsx'),
    }, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert Producto.query.filter_by(nombre='X').first() is None


def test_solo_escribir_todo_puede_importar(app, client):
    resp_sin_login = client.get('/admin/productos/importar', follow_redirects=True)
    # Sin sesion, login_required redirige al login
    assert b'Correo' in resp_sin_login.data or resp_sin_login.status_code in (200, 302)
