# -*- coding: utf-8 -*-
"""Catalogo inicial: 2 productos por categoria, con imagenes reales
descargadas de Wikimedia Commons (licencia libre) guardadas en
app/static/productos/."""

CATALOGO_SEED = [
    # ── Bebidas ──
    dict(
        nombre='Coca-Cola en Lata 350ml', categoria='Bebidas', subcategoria='Gaseosas',
        precio=3000, costo=1800, stock=60,
        descripcion='Bebida cola clásica, lata de 350ml bien fría.', imagen='cat_coca_cola_en_lata_350ml.jpg',
    ),
    dict(
        nombre='Jugo de Naranja Natural 300ml', categoria='Bebidas', subcategoria='Jugos',
        precio=3000, costo=1700, stock=40,
        descripcion='Jugo de naranja recién exprimido, 300ml.', imagen='cat_jugo_de_naranja_natural_300ml.jpg',
    ),

    # ── Paquetes ──
    dict(
        nombre='Papas Fritas Sabor Pollo 25g', categoria='Paquetes', subcategoria='Papas',
        precio=2000, costo=1100, stock=50,
        descripcion='Papas fritas crocantes sabor a pollo, paquete individual.', imagen='cat_papas_fritas_sabor_pollo_25g.jpg',
    ),
    dict(
        nombre='Platanitos Verdes 25g', categoria='Paquetes', subcategoria='Plátano',
        precio=2000, costo=1100, stock=40,
        descripcion='Chips de plátano verde fritos y salados.', imagen='cat_platanitos_verdes_25g.jpg',
    ),

    # ── Galletas ──
    dict(
        nombre='Galletas de Chocolate', categoria='Galletas', subcategoria='Dulces',
        precio=2500, costo=1400, stock=40,
        descripcion='Galletas cubiertas de chocolate, paquete individual.', imagen='cat_galletas_de_chocolate.jpg',
    ),
    dict(
        nombre='Galletas de Avena y Pasas', categoria='Galletas', subcategoria='Dulces',
        precio=2200, costo=1200, stock=30,
        descripcion='Galletas de avena con pasas, textura crocante.', imagen='cat_galletas_de_avena_y_pasas.jpg',
    ),

    # ── Comida Rápida ──
    dict(
        nombre='Hamburguesa Sencilla', categoria='Comida Rápida', subcategoria='Hamburguesas',
        precio=8000, costo=4500, stock=30,
        descripcion='Carne de res, queso, lechuga y tomate en pan brioche.', imagen='cat_hamburguesa_sencilla.jpg',
    ),
    dict(
        nombre='Empanada de Carne', categoria='Comida Rápida', subcategoria='Empanadas',
        precio=2500, costo=1200, stock=50,
        descripcion='Masa de maíz frita rellena de carne de res guisada.', imagen='cat_empanada_de_carne.jpg',
    ),

    # ── Dulces ──
    dict(
        nombre='Chocolatina de Leche', categoria='Dulces', subcategoria='Chocolates',
        precio=1500, costo=800, stock=60,
        descripcion='Barra de chocolate con leche, tamaño individual.', imagen='cat_chocolatina_de_leche.jpg',
    ),
    dict(
        nombre='Gomitas de Frutas', categoria='Dulces', subcategoria='Gomitas',
        precio=2000, costo=1000, stock=45,
        descripcion='Bolsa de gomitas surtidas sabor a frutas.', imagen='cat_gomitas_de_frutas.jpg',
    ),

    # ── Combos ──
    dict(
        nombre='Combo Hamburguesa', categoria='Combos', subcategoria='Combos',
        precio=12000, costo=6500, stock=25,
        descripcion='Hamburguesa sencilla, papas fritas y gaseosa.', imagen='cat_combo_hamburguesa.jpg',
    ),
    dict(
        nombre='Combo Pizza + Gaseosa', categoria='Combos', subcategoria='Combos',
        precio=8000, costo=4200, stock=25,
        descripcion='Porción de pizza con gaseosa incluida.', imagen='cat_combo_pizza_gaseosa.jpg',
    ),

    # ── Postres ──
    dict(
        nombre='Torta de Chocolate', categoria='Postres', subcategoria='Tortas',
        precio=5000, costo=2500, stock=25,
        descripcion='Porción de torta húmeda de chocolate.', imagen='cat_torta_de_chocolate.jpg',
    ),
    dict(
        nombre='Cheesecake de Fresa', categoria='Postres', subcategoria='Tortas',
        precio=6500, costo=3300, stock=20,
        descripcion='Porción de cheesecake con salsa de fresa.', imagen='cat_cheesecake_de_fresa.jpg',
    ),
]
