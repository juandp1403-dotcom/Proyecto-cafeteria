from flask import render_template, request, redirect, url_for, session, jsonify
from datetime import datetime, date
from models import db, Producto, Cliente, Venta, DetalleVenta
from . import cliente_bp


def _numero_pedido_hoy():
    """Cuenta cuántos pedidos se han hecho hoy y devuelve el siguiente número."""
    hoy = date.today()
    count = Venta.query.filter(
        db.func.date(Venta.fechaventa) == hoy
    ).count()
    return count + 1


# ── Registro / Identificación del cliente ──────────────────────────────────
@cliente_bp.route('/', methods=['GET', 'POST'])
@cliente_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        doc   = request.form.get('documento', '').strip()
        nombre = request.form.get('nombre', '').strip()
        ficha  = request.form.get('ficha', '').strip()

        if not doc or not nombre or not ficha:
            return render_template('cliente/registro.html', error='Completa todos los campos.')

        try:
            doc   = int(doc)
            ficha = int(ficha)
        except ValueError:
            return render_template('cliente/registro.html', error='Documento y ficha deben ser numéricos.')

        cliente = Cliente.query.get(doc)
        if not cliente:
            cliente = Cliente(documento=doc, nombre=nombre, ficha=ficha)
            db.session.add(cliente)
            db.session.commit()
        else:
            # Actualiza nombre/ficha si regresa
            cliente.nombre = nombre
            cliente.ficha  = ficha
            db.session.commit()

        session['cliente_doc']    = doc
        session['cliente_nombre'] = nombre
        return redirect(url_for('cliente.catalogo'))

    return render_template('cliente/registro.html')


# ── Catálogo de productos ───────────────────────────────────────────────────
@cliente_bp.route('/catalogo')
def catalogo():
    if 'cliente_doc' not in session:
        return redirect(url_for('cliente.registro'))
    productos = Producto.query.filter_by(activo=True).all()
    return render_template('cliente/catalogo.html', productos=productos)


# ── Confirmar pedido (POST JSON desde carrito JS) ──────────────────────────
@cliente_bp.route('/confirmar', methods=['POST'])
def confirmar():
    if 'cliente_doc' not in session:
        return jsonify({'error': 'Sesión expirada'}), 403

    data = request.get_json()
    items = data.get('items', [])
    if not items:
        return jsonify({'error': 'Carrito vacío'}), 400

    total = 0
    detalles_a_guardar = []

    for item in items:
        prod = Producto.query.get(item['idproducto'])
        if not prod or not prod.activo:
            return jsonify({'error': f'Producto {item["idproducto"]} no disponible'}), 400
        if prod.stock < item['cantidad']:
            return jsonify({'error': f'Stock insuficiente para {prod.nombre}'}), 400
        subtotal = prod.precio * item['cantidad']
        total += subtotal
        detalles_a_guardar.append((prod, item['cantidad']))

    num_pedido = _numero_pedido_hoy()
    venta = Venta(
        precio               = total,
        cliente              = session['cliente_doc'],
        fechaventa           = datetime.utcnow(),
        numero_pedido_diario = num_pedido,
        estado               = 'Pendiente de Pago'
    )
    db.session.add(venta)
    db.session.flush()  # obtiene idventa antes del commit

    for prod, cant in detalles_a_guardar:
        detalle = DetalleVenta(idventa=venta.idventa, idproducto=prod.idproducto, cantidad=cant)
        db.session.add(detalle)
        prod.stock -= cant  # descuenta stock

    db.session.commit()
    session['ultimo_pedido'] = venta.idventa
    return jsonify({'idventa': venta.idventa, 'numero_pedido': num_pedido})


# ── Factura virtual ─────────────────────────────────────────────────────────
@cliente_bp.route('/factura/<int:idventa>')
def factura(idventa):
    venta = Venta.query.get_or_404(idventa)
    return render_template('cliente/factura.html', venta=venta)


# ── Estado del pedido (polling SSE-like via JSON) ──────────────────────────
@cliente_bp.route('/estado/<int:idventa>')
def estado_pedido(idventa):
    venta = Venta.query.get_or_404(idventa)
    return render_template('cliente/estado_pedido.html', venta=venta)


@cliente_bp.route('/api/estado/<int:idventa>')
def api_estado(idventa):
    venta = Venta.query.get_or_404(idventa)
    return jsonify({'estado': venta.estado, 'numero_pedido': venta.numero_pedido_diario})


# ── Cerrar sesión cliente ───────────────────────────────────────────────────
@cliente_bp.route('/salir')
def salir():
    session.pop('cliente_doc', None)
    session.pop('cliente_nombre', None)
    session.pop('ultimo_pedido', None)
    return redirect(url_for('cliente.registro'))
