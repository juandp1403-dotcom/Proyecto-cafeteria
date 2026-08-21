from flask import render_template, request, redirect, url_for, session, jsonify, flash
from flask_login import current_user
from models import db, Producto, Cliente, Venta, DetalleVenta, SolicitudSupresion
from utils import ahora_bogota
from . import cliente_bp


@cliente_bp.route('/', methods=['GET', 'POST'])
@cliente_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        doc    = request.form.get('documento', '').strip()
        nombre = request.form.get('nombre', '').strip()
        ficha  = request.form.get('ficha', '').strip()

        if not doc or not nombre or not ficha:
            return render_template('cliente/registro.html', error='Completa todos los campos.')

        # HU-65: el consentimiento es obligatorio (validacion en backend,
        # no solo en el HTML) conforme a la Ley 1581 de 2012.
        if not request.form.get('autorizo_datos'):
            return render_template(
                'cliente/registro.html',
                error='Debes autorizar el tratamiento de tus datos personales conforme a la Ley 1581 de 2012 para continuar.')

        try:
            doc   = int(doc)
            ficha = int(ficha)
        except ValueError:
            return render_template('cliente/registro.html', error='Documento y ficha deben ser numéricos.')

        cliente = Cliente.query.get(doc)
        if not cliente:
            cliente = Cliente(documento=doc, nombre=nombre, ficha=ficha)
            db.session.add(cliente)
        else:
            cliente.nombre = nombre
            cliente.ficha  = ficha
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
    # HU-36: solo productos activos en el catalogo de cliente
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

    total = 0
    detalles_a_guardar = []

    for item in items:
        try:
            idproducto = int(item['idproducto'])
            cantidad = int(item['cantidad'])
        except (ValueError, TypeError, KeyError):
            return jsonify({'error': 'Datos de producto invalidos'}), 400

        if cantidad <= 0 or cantidad > 100:
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

    venta = Venta(
        precio     = total,
        cliente    = session['cliente_doc'],
        fechaventa = ahora_bogota(),
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


@cliente_bp.route('/salir')
def salir():
    session.pop('cliente_doc', None)
    session.pop('cliente_nombre', None)
    session.pop('ultimo_pedido', None)
    return redirect(url_for('cliente.registro'))


# ── HU-65/66: privacidad y derecho de supresion (Ley 1581 de 2012) ──
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
        return redirect(url_for('cliente.catalogo'))

    return render_template('cliente/supresion.html')
