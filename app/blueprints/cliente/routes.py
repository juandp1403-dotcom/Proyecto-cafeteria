from flask import render_template, request, redirect, url_for, session, jsonify, flash, current_app
from flask_login import current_user
from sqlalchemy import func
from ...models import (
    db, expr_fecha, Producto, Cliente, Venta, DetalleVenta, SolicitudSupresion,
    crear_token_pedido, consumir_token_pedido,
)
from ...models.producto import CATEGORIAS
from ...extensions import limiter
from ...utils import ahora_bogota, hoy_bogota
from . import cliente_bp


CATEGORIA_IMAGEN = {
    'Bebidas':       'categoria_bebidas.jpg',
    'Paquetes':      'categoria_paquetes.jpg',
    'Galletas':      'categoria_galletas.png',
    'Comida Rápida': 'categoria_comida_rapida.jpg',
    'Dulces':        'categoria_dulces.jpg',
    'Combos':        'categoria_combos.jpg',
    'Postres':       'categoria_postres.webp',
}

ORDEN_SUBCATEGORIA = {
    'Bebidas':       ['Gaseosas', 'Jugos', 'Tés', 'Aguas', 'Café'],
    'Paquetes':      ['Papas', 'Nachos', 'Plátano', 'Maní', 'Snacks'],
    'Galletas':      ['Saladas', 'Dulces'],
    'Comida Rápida': ['Hamburguesas', 'Perros calientes', 'Empanadas', 'Arepas', 'Pizza', 'Papas'],
    'Dulces':        ['Dulces', 'Chocolates', 'Gomitas', 'Chicles'],
    'Combos':        ['Combos'],
    'Postres':       ['Tortas', 'Flanes', 'Frutas', 'Gelatinas', 'Helados', 'Otros'],
}


@cliente_bp.route('/', methods=['GET', 'POST'])
@cliente_bp.route('/registro', methods=['GET', 'POST'])
@limiter.limit("10 per minute", methods=['POST'])
def registro():
    if request.method == 'POST':
        doc    = request.form.get('documento', '').strip()
        nombre = request.form.get('nombre', '').strip()
        ficha  = request.form.get('ficha', '').strip()

        if not doc or not nombre or not ficha:
            return render_template('cliente/registro.html', error='Completa todos los campos.')

        if not request.form.get('autorizo_datos'):
            return render_template(
                'cliente/registro.html',
                error='Debes autorizar el tratamiento de tus datos personales conforme a la Ley 1581 de 2012 para continuar.')

        # Las columnas son db.Integer (32 bits); un numero fuera de rango
        # rompia el driver de BD sin manejar (500).
        try:
            doc   = int(doc)
            ficha = int(ficha)
            if not (0 < doc <= 9_999_999_999) or not (0 < ficha <= 2_147_483_647):
                raise ValueError
        except ValueError:
            return render_template('cliente/registro.html', error='Documento y ficha deben ser numéricos válidos.')

        # Si el documento ya existe, exige que nombre y ficha coincidan
        # para reutilizar esa identidad (evita suplantar a otro cliente).
        cliente = Cliente.query.get(doc)
        if not cliente:
            cliente = Cliente(documento=doc, nombre=nombre, ficha=ficha)
            db.session.add(cliente)
        elif cliente.nombre.strip().lower() != nombre.strip().lower() or cliente.ficha != ficha:
            current_app.logger.warning(
                'Intento de registro con documento existente sin coincidencia: documento=%s', doc
            )
            return render_template('cliente/registro.html', error=(
                'Ese documento ya está registrado con otro nombre o ficha. '
                'Verifica que los escribiste exactamente igual a tu primer registro, '
                'o pide ayuda a un cajero.'
            ))
        db.session.commit()

        session['cliente_doc']    = doc
        session['cliente_nombre'] = nombre
        return redirect(url_for('cliente.ordenar'))

    return render_template('cliente/registro.html')


@cliente_bp.route('/catalogo')
def catalogo():
    if 'cliente_doc' not in session and not current_user.is_authenticated:
        return redirect(url_for('cliente.registro'))

    from sqlalchemy import func, case

    estados_pagados = ('Pagado/Preparando', 'Preparado', 'Entregado')

    # Cantidad vendida por producto, contando solo ventas con estado
    # valido, para que todos los productos aparezcan (con 0 si no aplica).
    total_vendido_expr = func.coalesce(
        func.sum(case((Venta.estado.in_(estados_pagados), DetalleVenta.cantidad), else_=0)),
        0
    )
    rows = (db.session.query(Producto.idproducto, total_vendido_expr.label('total_vendido'))
            .select_from(Producto)
            .outerjoin(DetalleVenta, DetalleVenta.idproducto == Producto.idproducto)
            .outerjoin(Venta, Venta.idventa == DetalleVenta.idventa)
            .filter(Producto.activo == True)  # noqa: E712
            .group_by(Producto.idproducto)
            .order_by(total_vendido_expr.desc())
            .all())

    mapa_ventas = {r.idproducto: int(r.total_vendido) for r in rows}
    ids_por_venta = [r.idproducto for r in rows]

    top_10_ids = ids_por_venta[:10]
    resto_ids  = ids_por_venta[10:]

    top_10 = Producto.query.filter(Producto.idproducto.in_(top_10_ids)).all()
    top_10.sort(key=lambda p: top_10_ids.index(p.idproducto) if p.idproducto in top_10_ids else 999)

    resto = Producto.query.filter(Producto.idproducto.in_(resto_ids)).order_by(Producto.nombre).all()

    productos_ordenados = top_10 + resto

    for p in productos_ordenados:
        p.is_top = p.idproducto in top_10_ids and mapa_ventas.get(p.idproducto, 0) > 0

    return render_template('cliente/catalogo.html', productos=productos_ordenados)


@cliente_bp.route('/ordenar')
def ordenar():
    """Landing de compra: cuadrícula de categorías (estilo KFC/Papa
    John's) en vez del listado plano de productos."""
    if 'cliente_doc' not in session and not current_user.is_authenticated:
        return redirect(url_for('cliente.registro'))

    categorias = [
        {'nombre': cat, 'imagen': CATEGORIA_IMAGEN.get(cat)}
        for cat in CATEGORIAS
    ]
    return render_template('cliente/ordenar.html', categorias=categorias)


@cliente_bp.route('/categoria/<categoria>')
def categoria(categoria):
    if 'cliente_doc' not in session and not current_user.is_authenticated:
        return redirect(url_for('cliente.registro'))

    if categoria not in CATEGORIAS:
        flash('Categoría no encontrada.', 'warning')
        return redirect(url_for('cliente.ordenar'))

    productos = (Producto.query
                 .filter(Producto.activo.is_(True), Producto.categoria == categoria)
                 .all())

    orden = ORDEN_SUBCATEGORIA.get(categoria, [])

    def clave_orden(p):
        sub = p.subcategoria or ''
        idx = orden.index(sub) if sub in orden else len(orden)
        return (idx, p.nombre)

    productos.sort(key=clave_orden)

    # Agrupado en Python (no con el filtro |groupby de Jinja, que
    # reordena alfabeticamente y rompe si hay subcategoria=None mezclada
    # con texto) para conservar el orden de ORDEN_SUBCATEGORIA.
    grupos = []
    for p in productos:
        sub = p.subcategoria or ''
        if grupos and grupos[-1][0] == sub:
            grupos[-1][1].append(p)
        else:
            grupos.append((sub, [p]))

    es_cliente = 'cliente_doc' in session
    # HU-49: token de un solo uso para que un doble clic (o una peticion
    # reenviada por red lenta) en "Confirmar pedido" no cree la misma
    # venta dos veces -- ver consumir_token_pedido() en /confirmar.
    pedido_token = crear_token_pedido(session['cliente_doc']) if es_cliente else None

    return render_template('cliente/categoria.html', grupos=grupos,
                           categoria=categoria, categorias=CATEGORIAS,
                           es_cliente=es_cliente, pedido_token=pedido_token)


@cliente_bp.route('/confirmar', methods=['POST'])
def confirmar():
    if 'cliente_doc' not in session:
        return jsonify({'error': 'Sesion expirada'}), 403

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'error': 'Cuerpo de petición inválido'}), 400

    # HU-49: token de un solo uso, consumido con UPDATE condicional
    # atomico (mismo patron que ajustar_stock) -- si dos peticiones
    # llegan casi al mismo tiempo con el mismo token (doble clic, red
    # lenta reenviando el POST), solo la primera lo consume.
    if not consumir_token_pedido(data.get('token'), session['cliente_doc']):
        return jsonify({'error': 'Este pedido ya fue procesado, o la página está desactualizada. Recarga e intenta de nuevo.'}), 409

    items = data.get('items', [])
    if not items:
        return jsonify({'error': 'Carrito vacio'}), 400

    if len(items) > 50:
        return jsonify({'error': 'El pedido tiene demasiados items distintos (maximo 50)'}), 400

    # Consolida cantidades repetidas del mismo producto antes de validar
    # el tope, para que no se pueda evadir repitiendo filas.
    cantidades_por_producto = {}
    for item in items:
        try:
            idproducto = int(item['idproducto'])
            cantidad = int(item['cantidad'])
        except (ValueError, TypeError, KeyError):
            return jsonify({'error': 'Datos de producto invalidos'}), 400
        if cantidad <= 0:
            return jsonify({'error': f'Cantidad invalida para el producto {idproducto}'}), 400
        cantidades_por_producto[idproducto] = cantidades_por_producto.get(idproducto, 0) + cantidad

    total = 0
    detalles_a_guardar = []

    for idproducto, cantidad in cantidades_por_producto.items():
        if cantidad > 100:
            return jsonify({'error': f'Cantidad invalida para el producto {idproducto} (debe ser entre 1 y 100)'}), 400

        prod = Producto.query.get(idproducto)
        if not prod:
            return jsonify({'error': f'Producto {idproducto} no disponible'}), 400

        detalles_a_guardar.append((prod, cantidad))
        total += prod.precio * cantidad

    # Descuento atomico de stock con UPDATE condicional.
    for prod, cant in detalles_a_guardar:
        affected = Producto.query.filter(
            Producto.idproducto == prod.idproducto,
            Producto.stock >= cant
        ).update({'stock': Producto.stock - cant})
        if affected == 0:
            db.session.rollback()
            return jsonify({'error': f'Stock insuficiente para {prod.nombre}'}), 400

    metodos_validos = {'Efectivo', 'Tarjeta', 'Transferencia'}
    metodo_pago = data.get('metodo_pago')
    if metodo_pago not in metodos_validos:
        metodo_pago = 'Efectivo'

    # Numero de pedido consecutivo del dia, calculado una sola vez al crear la venta.
    hoy = hoy_bogota()
    ultimo_numero = (db.session.query(func.coalesce(func.max(Venta.numero_pedido_diario), 0))
                      .filter(expr_fecha(Venta.fechaventa) == hoy)
                      .scalar())

    venta = Venta(
        precio      = total,
        cliente     = session['cliente_doc'],
        fechaventa  = ahora_bogota(),
        metodo_pago = metodo_pago,
        numero_pedido_diario = ultimo_numero + 1,
    )
    db.session.add(venta)
    db.session.flush()

    for prod, cant in detalles_a_guardar:
        detalle = DetalleVenta(idventa=venta.idventa, idproducto=prod.idproducto,
                               cantidad=cant, precio_unitario=prod.precio)
        db.session.add(detalle)

    db.session.commit()
    session['ultimo_pedido'] = venta.idventa
    return jsonify({'idventa': venta.idventa})


@cliente_bp.route('/factura/<int:idventa>')
def factura(idventa):
    venta = Venta.query.get_or_404(idventa)
    es_propietario = 'cliente_doc' in session and session['cliente_doc'] == venta.cliente
    es_admin = current_user.is_authenticated
    if not es_propietario and not es_admin:
        flash('No tienes acceso a este pedido.', 'danger')
        return redirect(url_for('cliente.registro'))
    return render_template('cliente/factura.html', venta=venta)


@cliente_bp.route('/estado/<int:idventa>')
def estado_pedido(idventa):
    venta = Venta.query.get_or_404(idventa)
    es_propietario = 'cliente_doc' in session and session['cliente_doc'] == venta.cliente
    es_admin = current_user.is_authenticated
    if not es_propietario and not es_admin:
        flash('No tienes acceso a este pedido.', 'danger')
        return redirect(url_for('cliente.registro'))
    return render_template('cliente/estado_pedido.html', venta=venta)


@cliente_bp.route('/estado/<int:idventa>/json')
@limiter.limit("20 per minute")
def estado_pedido_json(idventa):
    """Endpoint liviano para el polling de la pantalla de estado."""
    venta = Venta.query.get_or_404(idventa)
    es_propietario = 'cliente_doc' in session and session['cliente_doc'] == venta.cliente
    es_admin = current_user.is_authenticated
    if not es_propietario and not es_admin:
        return jsonify({'error': 'sin acceso'}), 403
    return jsonify({'estado': venta.estado})


@cliente_bp.route('/cancelar/<int:idventa>', methods=['POST'])
def cancelar_pedido(idventa):
    """El cliente puede cancelar su propio pedido mientras siga 'Pendiente
    de Pago', devolviendo el stock igual que cuando lo rechaza un cajero."""
    venta = Venta.query.get_or_404(idventa)
    if 'cliente_doc' not in session or session['cliente_doc'] != venta.cliente:
        flash('No tienes acceso a este pedido.', 'danger')
        return redirect(url_for('cliente.registro'))

    detalles = list(venta.detalles)
    # UPDATE condicionado al estado actual para que un doble clic no
    # devuelva el stock dos veces.
    afectados = Venta.query.filter(
        Venta.idventa == idventa, Venta.estado == 'Pendiente de Pago'
    ).update({'estado': 'Cancelado'}, synchronize_session=False)
    db.session.commit()

    if afectados:
        from ...models import ajustar_stock
        for det in detalles:
            ajustar_stock(det.idproducto, det.cantidad)
        db.session.commit()
        flash('Tu pedido fue cancelado.', 'success')
    else:
        flash('Este pedido ya no se puede cancelar (ya fue procesado).', 'warning')

    return redirect(url_for('cliente.estado_pedido', idventa=idventa))


@cliente_bp.route('/salir')
def salir():
    session.pop('cliente_doc', None)
    session.pop('cliente_nombre', None)
    session.pop('ultimo_pedido', None)
    return redirect(url_for('cliente.registro'))


@cliente_bp.route('/privacidad')
def privacidad():
    return render_template('cliente/privacidad.html')


@cliente_bp.route('/supresion', methods=['GET', 'POST'])
def supresion():
    doc = session.get('cliente_doc')
    if not doc:
        flash('Primero identifícate para poder solicitar la supresión de tus datos.', 'warning')
        return redirect(url_for('cliente.registro'))

    if request.method == 'POST':
        motivo = request.form.get('motivo', '').strip()
        solicitud = SolicitudSupresion(
            documento_cliente=doc,
            nombre_cliente=session.get('cliente_nombre'),
            motivo=motivo or None,
        )
        db.session.add(solicitud)
        db.session.commit()
        flash('Tu solicitud de supresión fue registrada. El administrador la procesará y te contactará si es necesario.', 'success')
        return redirect(url_for('cliente.ordenar'))

    return render_template('cliente/supresion.html')
