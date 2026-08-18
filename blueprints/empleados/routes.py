from flask import render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from datetime import date
from models import db, Admin, Venta
from . import empleados_bp


@empleados_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Si ya está autenticado, enviarlo al catálogo en modo admin
    if current_user.is_authenticated:
        return redirect(url_for('cliente.catalogo'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        clave = request.form.get('clave', '').strip()
        admin = Admin.query.filter_by(email=email).first()

        if admin and admin.check_password(clave):
            login_user(admin)
            # Siempre va al catálogo para que opere como cliente + admin
            return redirect(url_for('cliente.catalogo'))

        flash('Correo o contraseña incorrectos.', 'danger')

    return render_template('empleados/login.html')


@empleados_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión de administrador cerrada.', 'success')
    return redirect(url_for('cliente.registro'))


@empleados_bp.route('/cajero')
@login_required
def cajero():
    hoy = date.today()
    pedidos = (Venta.query
               .filter(db.func.date(Venta.fechaventa) == hoy,
                       Venta.estado == 'Pendiente de Pago')
               .order_by(Venta.idventa.asc())
               .all())
    return render_template('empleados/cajero.html', pedidos=pedidos)


@empleados_bp.route('/api/cajero/pedidos')
@login_required
def api_cajero_pedidos():
    hoy = date.today()
    pedidos = (Venta.query
               .filter(db.func.date(Venta.fechaventa) == hoy,
                       Venta.estado == 'Pendiente de Pago')
               .order_by(Venta.idventa.asc())
               .all())
    return jsonify([p.to_dict() for p in pedidos])


@empleados_bp.route('/api/cajero/pagar/<int:idventa>', methods=['POST'])
@login_required
def api_pagar(idventa):
    venta = Venta.query.get_or_404(idventa)
    venta.estado = 'Pagado/Preparando'
    db.session.commit()
    return jsonify({'ok': True})


@empleados_bp.route('/entregador')
@login_required
def entregador():
    hoy = date.today()
    pedidos = (Venta.query
               .filter(db.func.date(Venta.fechaventa) == hoy,
                       Venta.estado == 'Preparado')
               .order_by(Venta.idventa.asc())
               .all())
    return render_template('empleados/entregador.html', pedidos=pedidos)


@empleados_bp.route('/api/entregador/pedidos')
@login_required
def api_entregador_pedidos():
    hoy = date.today()
    pedidos = (Venta.query
               .filter(db.func.date(Venta.fechaventa) == hoy,
                       Venta.estado == 'Preparado')
               .order_by(Venta.idventa.asc())
               .all())
    return jsonify([p.to_dict() for p in pedidos])


@empleados_bp.route('/api/entregador/entregar/<int:idventa>', methods=['POST'])
@login_required
def api_entregar(idventa):
    venta = Venta.query.get_or_404(idventa)
    venta.estado = 'Entregado'
    db.session.commit()
    return jsonify({'ok': True})
