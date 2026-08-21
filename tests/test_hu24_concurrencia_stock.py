"""
Regresion HU-24: condicion de carrera real de stock -- dos hilos
intentando descontar stock del MISMO producto al mismo tiempo, mas
unidades de las que hay disponibles en total. El UPDATE condicional
(WHERE stock >= cantidad) debe evitar vender de mas: como maximo el
stock inicial se vende, nunca queda negativo.
"""
import os
import tempfile
import threading

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_hu24_")
_DB_PATH = os.path.join(_DB_DIR, "test_cafeteria.db")
os.environ['DATABASE_URL'] = f"sqlite:///{_DB_PATH}"
os.environ.pop('SSH_HOST', None)

import pytest

from app import create_app
from models import db, Producto, ajustar_stock


@pytest.fixture()
def app():
    application = create_app('development')
    application.config['TESTING'] = True
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


def test_dos_compras_simultaneas_no_venden_mas_stock_del_disponible(app):
    with app.app_context():
        prod = Producto(nombre='Producto concurrencia', precio=1000, stock=5, costo=500)
        db.session.add(prod)
        db.session.commit()
        idproducto = prod.idproducto

    resultados = []
    CANTIDAD_POR_HILO = 4  # 2 hilos x 4 = 8 unidades pedidas, solo hay 5

    def intentar_comprar():
        with app.app_context():
            ok = ajustar_stock(idproducto, -CANTIDAD_POR_HILO)
            db.session.commit()
            resultados.append(ok)

    hilo_a = threading.Thread(target=intentar_comprar)
    hilo_b = threading.Thread(target=intentar_comprar)
    hilo_a.start()
    hilo_b.start()
    hilo_a.join()
    hilo_b.join()

    with app.app_context():
        stock_final = Producto.query.filter_by(idproducto=idproducto).first().stock

    # Como mucho uno de los dos hilos pudo completar la compra (4 <= 5,
    # pero 4+4=8 > 5) -- nunca deben poder completar ambos, y el stock
    # nunca queda negativo.
    assert stock_final >= 0
    assert resultados.count(True) <= 1
    if resultados.count(True) == 1:
        assert stock_final == 1  # 5 - 4
    else:
        assert stock_final == 5  # ninguna compra se aplico


def test_dos_compras_simultaneas_dentro_del_stock_disponible_ambas_completan(app):
    with app.app_context():
        prod = Producto(nombre='Producto concurrencia 2', precio=1000, stock=10, costo=500)
        db.session.add(prod)
        db.session.commit()
        idproducto = prod.idproducto

    resultados = []

    def intentar_comprar():
        with app.app_context():
            ok = ajustar_stock(idproducto, -3)
            db.session.commit()
            resultados.append(ok)

    hilos = [threading.Thread(target=intentar_comprar) for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    with app.app_context():
        stock_final = Producto.query.filter_by(idproducto=idproducto).first().stock

    assert all(resultados)
    assert stock_final == 4  # 10 - 3 - 3
