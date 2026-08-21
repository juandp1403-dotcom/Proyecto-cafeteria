from flask import render_template, request, redirect, url_for, session, jsonify, flash, current_app
from datetime import datetime
from flask_login import current_user
from sqlalchemy import func
from models import db, Producto, Cliente, Venta, DetalleVenta
from extensions import limiter
from . import cliente_bp


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

        try:
            doc   = int(doc)
            ficha = int(ficha)
        except ValueError:
            return render_template('cliente/registro.html', error='Documento y ficha deben ser numéricos.')

        # HU-08: si el documento ya existe, exigir que nombre y ficha
        # coincidan exactamente con lo guardado antes de reutilizar esa
        # identidad -- antes cualquiera que conociera un documento ajeno
        # podia sobrescribir el nombre y ver el historial de esa persona.
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
        return redirect(url_for('cliente.catalogo'))

    return render_template('cliente/registro.html')


@cliente_bp.route('/catalogo')
def catalogo():
    # Permite acceso si hay sesión de cliente O si el usuario es admin autenticado
    if 'cliente_doc' not in session and not current_user.is_authenticated:
        return redirect(url_for('cliente.registro'))
        
    from sqlalchemy import func, case
    
    estados_pagados = ('Pagado/Preparando', 'Preparado', 'Entregado')
    
    # Obtener cantidad vendida por producto.
    # Se usa CASE dentro de SUM para contar solo ventas con estado válido,
    # de modo que TODOS los productos aparecen siempre (con 0 si no tienen
    # ventas calificadas). Así se evita que un producto con solo ventas
    # 'Pendiente de Pago' o 'Cancelado' desaparezca del catálogo.
    rows = db.session.query(
        Producto.idproducto,
        func.coalesce(
            func.sum(case((Venta.estado.in_(estados_pagados), DetalleVenta.cantidad), else_=0)),
            0
        ).label('total_vendido')
    ).select_from(Producto) \
     .outerjoin(DetalleVenta, DetalleVenta.idproducto == Producto.idproducto) \
     .outerjoin(Venta, Venta.idventa == DetalleVenta.idventa) \
     .group_by(Producto.idproducto) \
     .order_by(func.coalesce(
         func.sum(case((Venta.estado.in_(estados_pagados), DetalleVenta.cantidad), else_=0)),
         0
     ).desc()).all()
    
    # Separar: top 10 más vendidos y el resto
    mapa_ventas = {r.idproducto: int(r.total_vendido) for r in rows}
    ids_por_venta = [r.idproducto for r in rows]
    
    top_10_ids = ids_por_venta[:10]
    resto_ids  = ids_por_venta[10:]
    
    # Obtener objetos Producto
    top_10 = Producto.query.filter(Producto.idproducto.in_(top_10_ids)).all()
    # Mantener orden por cantidad vendida
    top_10.sort(key=lambda p: top_10_ids.index(p.idproducto) if p.idproducto in top_10_ids else 999)
    
    resto = Producto.query.filter(Producto.idproducto.in_(resto_ids)).order_by(Producto.nombre).all()
    
    # Combinar: primero top 10, luego resto alfabético
    productos_ordenados = top_10 + resto
    
    # Marcar los top 10 que tengan ventas
    for p in productos_ordenados:
        p.is_top = p.idproducto in top_10_ids and mapa_ventas.get(p.idproducto, 0) > 0
        
    return render_template('cliente/catalogo.html', productos=productos_ordenados)


@cliente_bp.route('/confirmar', methods=['POST'])
def confirmar():
    if 'cliente_doc' not in session:
        return jsonify({'error': 'Sesion expirada'}), 403

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({'error': 'Cuerpo de petición inválido'}), 400
    items = data.get('items', [])
    if not items:
        return jsonify({'error': 'Carrito vacio'}), 400

    # HU-49: limitar cuantos items distintos puede traer un pedido, y
    # consolidar cantidades repetidas del mismo producto ANTES de
    # validar el tope de 100 -- antes se podia evadir ese tope
    # repitiendo el mismo producto en varias filas del carrito.
    if len(items) > 50:
        return jsonify({'error': 'El pedido tiene demasiados items distintos (maximo 50)'}), 400

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

    # Descuento atomico de stock con UPDATE condicional
    for prod, cant in detalles_a_guardar:
        affected = Producto.query.filter(
            Producto.idproducto == prod.idproducto,
            Producto.stock >= cant
        ).update({'stock': Producto.stock - cant})
        if affected == 0:
            db.session.rollback()
            return jsonify({'error': f'Stock insuficiente para {prod.nombre}'}), 400

    # HU-76: metodo de pago opcional, necesario para el futuro cierre
    # de caja (HU-75) y para que los reportes reflejen como entra el
    # dinero real, no solo el total.
    metodos_validos = {'Efectivo', 'Tarjeta', 'Transferencia'}
    metodo_pago = data.get('metodo_pago')
    if metodo_pago not in metodos_validos:
        metodo_pago = 'Efectivo'

    # HU-57: numero de pedido consecutivo del dia, calculado y guardado
    # una sola vez al crear la venta (no como propiedad recalculada en
    # cada lectura). No es perfectamente a prueba de condiciones de
    # carrera bajo concurrencia muy alta, pero es la misma fuente para
    # cliente y cajero -- ya no hay tres numeraciones que no coinciden.
    hoy = datetime.utcnow().date()
    ultimo_numero = (db.session.query(func.coalesce(func.max(Venta.numero_pedido_diario), 0))
                      .filter(Venta.fechaventa == hoy)
                      .scalar())

    venta = Venta(
        precio      = total,
        cliente     = session['cliente_doc'],
        fechaventa  = datetime.utcnow(),
        metodo_pago = metodo_pago,
        numero_pedido_diario = ultimo_numero + 1,
    )
    db.session.add(venta)
    db.session.flush()

    for prod, cant in detalles_a_guardar:
        detalle = DetalleVenta(idventa=venta.idventa, idproducto=prod.idproducto, cantidad=cant)
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


@cliente_bp.route('/cancelar/<int:idventa>', methods=['POST'])
def cancelar_pedido(idventa):
    """HU-29: el cliente puede cancelar su propio pedido mientras siga
    en 'Pendiente de Pago', devolviendo el stock igual que cuando lo
    rechaza un cajero."""
    venta = Venta.query.get_or_404(idventa)
    if 'cliente_doc' not in session or session['cliente_doc'] != venta.cliente:
        flash('No tienes acceso a este pedido.', 'danger')
        return redirect(url_for('cliente.registro'))

    detalles = list(venta.detalles)
    # UPDATE condicionado al estado actual (mismo patron que HU-48 en
    # admin/ventas.py), para que un doble clic no devuelva el stock dos veces.
    afectados = Venta.query.filter(
        Venta.idventa == idventa, Venta.estado == 'Pendiente de Pago'
    ).update({'estado': 'Cancelado'}, synchronize_session=False)
    db.session.commit()

    if afectados:
        from models import ajustar_stock
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
