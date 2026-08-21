from flask import render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from models import db, Producto, Compra, DetalleCompra, ajustar_stock
from blueprints.permisos import requiere_permiso, requiere_ver_pagina
from utils import hoy_bogota
from . import admin_bp


# ── Compras / Abastecimiento ──────────────────────────────────────────────────
@admin_bp.route('/compras')
@login_required
@requiere_ver_pagina('compras')
def compras():
    page    = request.args.get('page', 1, type=int)
    compras = (Compra.query
               .order_by(Compra.fechacompra.desc())
               .paginate(page=page, per_page=20, error_out=False))
    productos = Producto.query.filter(Producto.activo.is_(True)).order_by(Producto.nombre).all()
    return render_template('admin/compras.html', compras=compras, productos=productos)


@admin_bp.route('/compras/nueva', methods=['POST'])
@login_required
@requiere_permiso('escribir_todo')
def compra_nueva():
    vendedor = request.form.get('nombrevendedor', '').strip()
    items    = request.form.getlist('idproducto[]')
    cantidades = request.form.getlist('cantidad[]')

    if not vendedor or not items:
        flash('Completa todos los campos de la compra.', 'danger')
        return redirect(url_for('admin_panel.compras'))

    total = 0
    detalles = []
    for pid, cant in zip(items, cantidades):
        try:
            pid_int = int(pid)
            cant_int = int(cant)
        except (ValueError, TypeError):
            continue
        prod = Producto.query.get(pid_int)
        if prod and cant_int > 0:
            # HU-37: la compra se registra al COSTO real del producto,
            # no al precio de venta.
            total += prod.costo * cant_int
            detalles.append((prod, cant_int))

    compra = Compra(
        nombrevendedor = vendedor,
        precio         = total,
        fechacompra    = hoy_bogota(),
        documentoadmin = current_user.documento
    )
    db.session.add(compra)
    db.session.flush()

    for prod, cant in detalles:
        dc = DetalleCompra(idcompra=compra.idcompra, idproducto=prod.idproducto, cantidad=cant)
        db.session.add(dc)
        ajustar_stock(prod.idproducto, cant)  # HU-47: UPDATE atomico

    db.session.commit()
    flash('Compra registrada y stock actualizado.', 'success')
    return redirect(url_for('admin_panel.compras'))
