from flask import render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
from models import db, Producto, Admin, Venta, Compra, DetalleCompra
from . import admin_bp


def solo_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.rol != 'Administrador':
            flash('Acceso restringido al Administrador.', 'danger')
            return redirect(url_for('empleados.login'))
        return f(*args, **kwargs)
    return wrapper


# ── Dashboard ────────────────────────────────────────────────────────────────
@admin_bp.route('/')
@login_required
@solo_admin
def dashboard():
    total_ventas    = db.session.query(db.func.sum(Venta.precio)).scalar() or 0
    ventas_hoy      = Venta.query.filter(
        db.func.date(Venta.fechaventa) == datetime.utcnow().date()
    ).count()
    productos_bajo  = Producto.query.filter(Producto.stock < 5, Producto.activo == True).all()
    return render_template('admin/dashboard.html',
                           total_ventas=total_ventas,
                           ventas_hoy=ventas_hoy,
                           productos_bajo=productos_bajo)


# ── CRUD Productos ────────────────────────────────────────────────────────────
@admin_bp.route('/productos')
@login_required
@solo_admin
def productos():
    prods = Producto.query.order_by(Producto.idproducto).all()
    return render_template('admin/productos.html', productos=prods)


@admin_bp.route('/productos/nuevo', methods=['POST'])
@login_required
@solo_admin
def producto_nuevo():
    nombre = request.form.get('nombre', '').strip()
    precio = request.form.get('precio', 0)
    stock  = request.form.get('stock', 0)
    imagen = request.form.get('imagen_url', '').strip()
    if not nombre:
        flash('El nombre es obligatorio.', 'danger')
        return redirect(url_for('admin_panel.productos'))
    prod = Producto(nombre=nombre, precio=int(precio), stock=int(stock), imagen_url=imagen or None)
    db.session.add(prod)
    db.session.commit()
    flash(f'Producto "{nombre}" creado correctamente.', 'success')
    return redirect(url_for('admin_panel.productos'))


@admin_bp.route('/productos/editar/<int:idproducto>', methods=['POST'])
@login_required
@solo_admin
def producto_editar(idproducto):
    prod = Producto.query.get_or_404(idproducto)
    prod.nombre     = request.form.get('nombre', prod.nombre).strip()
    prod.precio     = int(request.form.get('precio', prod.precio))
    prod.stock      = int(request.form.get('stock', prod.stock))
    prod.imagen_url = request.form.get('imagen_url', prod.imagen_url or '').strip() or None
    prod.activo     = request.form.get('activo') == 'on'
    db.session.commit()
    flash(f'Producto "{prod.nombre}" actualizado.', 'success')
    return redirect(url_for('admin_panel.productos'))


@admin_bp.route('/productos/eliminar/<int:idproducto>', methods=['POST'])
@login_required
@solo_admin
def producto_eliminar(idproducto):
    prod = Producto.query.get_or_404(idproducto)
    prod.activo = False  # baja lógica para preservar historial
    db.session.commit()
    flash(f'Producto "{prod.nombre}" desactivado.', 'warning')
    return redirect(url_for('admin_panel.productos'))


# ── Gestión de usuarios (Admin) ───────────────────────────────────────────────
@admin_bp.route('/usuarios')
@login_required
@solo_admin
def usuarios():
    admins = Admin.query.order_by(Admin.documento).all()
    return render_template('admin/usuarios.html', admins=admins)


@admin_bp.route('/usuarios/nuevo', methods=['POST'])
@login_required
@solo_admin
def usuario_nuevo():
    doc    = request.form.get('documento', '').strip()
    nombre = request.form.get('nombre', '').strip()
    email  = request.form.get('email', '').strip()
    clave  = request.form.get('clave', '').strip()
    rol    = request.form.get('rol', 'Cajero')

    if not all([doc, nombre, email, clave]):
        flash('Todos los campos son obligatorios.', 'danger')
        return redirect(url_for('admin_panel.usuarios'))

    if Admin.query.filter_by(email=email).first():
        flash('Ya existe un usuario con ese correo.', 'danger')
        return redirect(url_for('admin_panel.usuarios'))

    admin = Admin(documento=int(doc), nombre=nombre, email=email, rol=rol, clave='')
    admin.set_password(clave)
    db.session.add(admin)
    db.session.commit()
    flash(f'Usuario "{nombre}" creado como {rol}.', 'success')
    return redirect(url_for('admin_panel.usuarios'))


@admin_bp.route('/usuarios/editar/<int:documento>', methods=['POST'])
@login_required
@solo_admin
def usuario_editar(documento):
    admin  = Admin.query.get_or_404(documento)
    admin.nombre = request.form.get('nombre', admin.nombre).strip()
    admin.email  = request.form.get('email', admin.email).strip()
    admin.rol    = request.form.get('rol', admin.rol)
    nueva_clave  = request.form.get('clave', '').strip()
    if nueva_clave:
        admin.set_password(nueva_clave)
    db.session.commit()
    flash('Usuario actualizado correctamente.', 'success')
    return redirect(url_for('admin_panel.usuarios'))


@admin_bp.route('/usuarios/eliminar/<int:documento>', methods=['POST'])
@login_required
@solo_admin
def usuario_eliminar(documento):
    if documento == current_user.documento:
        flash('No puedes eliminar tu propio usuario.', 'danger')
        return redirect(url_for('admin_panel.usuarios'))
    admin = Admin.query.get_or_404(documento)
    db.session.delete(admin)
    db.session.commit()
    flash('Usuario eliminado.', 'warning')
    return redirect(url_for('admin_panel.usuarios'))


# ── Histórico de ventas ───────────────────────────────────────────────────────
@admin_bp.route('/ventas')
@login_required
@solo_admin
def ventas():
    page   = request.args.get('page', 1, type=int)
    ventas = (Venta.query
              .order_by(Venta.fechaventa.desc())
              .paginate(page=page, per_page=20))
    return render_template('admin/ventas.html', ventas=ventas)


# ── Compras / Abastecimiento ──────────────────────────────────────────────────
@admin_bp.route('/compras')
@login_required
@solo_admin
def compras():
    page    = request.args.get('page', 1, type=int)
    compras = (Compra.query
               .order_by(Compra.fechacompra.desc())
               .paginate(page=page, per_page=20))
    productos = Producto.query.filter_by(activo=True).all()
    return render_template('admin/compras.html', compras=compras, productos=productos)


@admin_bp.route('/compras/nueva', methods=['POST'])
@login_required
@solo_admin
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
        prod = Producto.query.get(int(pid))
        if prod and int(cant) > 0:
            total += prod.precio * int(cant)
            detalles.append((prod, int(cant)))

    compra = Compra(
        nombrevendedor = vendedor,
        precio         = total,
        fechacompra    = datetime.utcnow(),
        documentoadmin = current_user.documento
    )
    db.session.add(compra)
    db.session.flush()

    for prod, cant in detalles:
        dc = DetalleCompra(idcompra=compra.idcompra, idproducto=prod.idproducto, cantidad=cant)
        db.session.add(dc)
        prod.stock += cant  # suma al inventario

    db.session.commit()
    flash('Compra registrada y stock actualizado.', 'success')
    return redirect(url_for('admin_panel.compras'))
