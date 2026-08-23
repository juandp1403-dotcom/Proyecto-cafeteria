"""
Flujo de compra principal en /ordenar y cierre del hueco de categorias:
registro/supresion llevan a Ordenar, link al catalogo plano desde Ordenar,
el importador masivo asigna Categoria/Subcategoria y el panel avisa los
productos sin categoria.
"""
import io
import os
import tempfile

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_ordenar_")
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


# ── Entrada principal hacia "Ordenar" ───────────────────────────────

def test_registro_exitoso_redirige_a_ordenar(app, client):
    resp = client.post('/cliente/registro', data={
        'documento': '1020304050',
        'nombre': 'Cliente Ordenar',
        'ficha': '3141592',
        'autorizo_datos': 'on',
    }, follow_redirects=False)
    assert resp.status_code == 302
    assert '/cliente/ordenar' in resp.headers['Location']


def test_supresion_registrada_redirige_a_ordenar(app, client):
    # El prompt lo llamaba "confirmar()", pero confirmar() responde JSON;
    # la redireccion post-accion del lado servidor era la de supresion.
    client.post('/cliente/registro', data={
        'documento': '607080900',   # dentro del rango int32 que valida la ruta
        'nombre': 'Cliente Supresion',
        'ficha': '2718281',
        'autorizo_datos': 'on',
    })
    resp = client.post('/cliente/supresion', data={'motivo': 'no quiero datos'},
                       follow_redirects=False)
    assert resp.status_code == 302
    assert '/cliente/ordenar' in resp.headers['Location']


def test_ordenar_muestra_link_al_catalogo_completo(app, client):
    client.post('/cliente/registro', data={
        'documento': '506070800',   # dentro del rango int32 que valida la ruta
        'nombre': 'Cliente Link',
        'ficha': '1618033',
        'autorizo_datos': 'on',
    })
    html = client.get('/cliente/ordenar').get_data(as_text=True)
    assert 'Ver catálogo completo' in html
    assert 'href="/cliente/catalogo"' in html


# ── Importador masivo: categoria y subcategoria ─────────────────────

def test_importador_asigna_categoria_valida_con_tilde_en_header(app, client):
    _login_admin(client)
    archivo = _excel_bytes(
        ['nombre', 'precio', 'Categoría', 'Subcategoría'],
        [['Limonada de Coco', 8000, 'Bebidas', 'Jugos']],
    )
    resp = client.post('/admin/productos/importar', data={
        'archivo': (archivo, 'productos.xlsx'),
    }, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        p = Producto.query.filter_by(nombre='Limonada de Coco').one()
        assert p.categoria == 'Bebidas'
        assert p.subcategoria == 'Jugos'


def test_importador_con_categoria_invalida_no_rompe_y_avisa(app, client):
    _login_admin(client)
    with app.app_context():
        previo = Producto(nombre='Ya Existente', precio=1000, stock=5,
                          costo=500, categoria='Bebidas')
        db.session.add(previo)
        db.session.commit()

    archivo = _excel_bytes(
        ['nombre', 'precio', 'Categoría'],
        [
            ['Otro Validó', 2000, 'Comida Rápida'],   # valido -> se crea
            ['Ya Existente', 1500, 'Postres Raros'],  # invalido -> no se toca
        ],
    )
    resp = client.post('/admin/productos/importar', data={
        'archivo': (archivo, 'productos.xlsx'),
    }, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    # El aviso dice bien claro la fila y el producto afectado (las comillas
    # llegan escapadas como &#34; en el HTML).
    assert 'Fila 3' in html and 'Ya Existente' in html
    assert 'Postres Raros' in html

    with app.app_context():
        # El resto de la fila SI se proceso (precio actualizado), pero la
        # categoria invalida no piso la que ya tenia.
        previo = Producto.query.filter_by(nombre='Ya Existente').one()
        assert previo.precio == 1500
        assert previo.categoria == 'Bebidas'
        # Y el producto valido de la misma carga si quedo categorizado.
        nuevo = Producto.query.filter_by(nombre='Otro Validó').one()
        assert nuevo.categoria == 'Comida Rápida'


def test_importador_sin_columnas_de_categoria_no_toca_las_existentes(app, client):
    _login_admin(client)
    with app.app_context():
        previo = Producto(nombre='Con Categoria', precio=1000, stock=5,
                          costo=500, categoria='Galletas',
                          subcategoria='Dulces')
        db.session.add(previo)
        db.session.commit()

    archivo = _excel_bytes(
        ['nombre', 'precio'],
        [['Con Categoria', 1200]],
    )
    resp = client.post('/admin/productos/importar', data={
        'archivo': (archivo, 'productos.xlsx'),
    }, content_type='multipart/form-data', follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        p = Producto.query.filter_by(nombre='Con Categoria').one()
        assert p.precio == 1200
        assert p.categoria == 'Galletas'
        assert p.subcategoria == 'Dulces'


# ── Aviso de productos sin categoria en el panel admin ──────────────

def test_panel_admin_cuenta_productos_sin_categoria(app, client):
    _login_admin(client)
    with app.app_context():
        base_sin = Producto.query.filter(
            Producto.activo.is_(True), Producto.categoria.is_(None)
        ).count()
        db.session.add(Producto(nombre='Con Cat A', precio=1000, stock=5,
                                costo=500, categoria='Bebidas'))
        db.session.add(Producto(nombre='Con Cat B', precio=1000, stock=5,
                                costo=500, categoria='Paquetes'))
        db.session.add(Producto(nombre='Sin Cat C', precio=1000, stock=5,
                                costo=500))
        db.session.commit()

    html = client.get('/admin/productos').get_data(as_text=True)
    assert f'{base_sin + 1} producto(s) sin categoría asignada' in html
