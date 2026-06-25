from flask import render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from datetime import date
from models import db, Admin, Venta
from . import empleados_bp


@empleados_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_panel.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        clave = request.form.get('clave', '').strip()
        admin = Admin.query.filter_by(email=email).first()

        if admin and admin.check_password(clave):
            login_user(admin)
            return redirect(url_for('admin_panel.dashboard'))

        flash('Correo o contraseña incorrectos.', 'danger')

    return render_template('empleados/login.html')


@empleados_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada correctamente.', 'success')
    return redirect(url_for('empleados.login'))


@empleados_bp.route('/cajero')
@login_required
def cajero():
    hoy = date.today()
    pedidos = (Venta.query
               .filter(db.func.date(Venta.fechaventa) == hoy)
               .order_by(Venta.idventa.asc())
               .all())
    return render_template('empleados/cajero.html', pedidos=pedidos)


@empleados_bp.route('/api/cajero/pedidos')
@login_required
def api_cajero_pedidos():
    hoy = date.today()
    pedidos = (Venta.query
               .filter(db.func.date(Venta.fechaventa) == hoy)
               .order_by(Venta.idventa.asc())
               .all())
    return jsonify([p.to_dict() for p in pedidos])


@empleados_bp.route('/api/cajero/pagar/<int:idventa>', methods=['POST'])
@login_required
def api_pagar(idventa):
    Venta.query.get_or_404(idventa)
    return jsonify({'ok': True})


@empleados_bp.route('/entregador')
@login_required
def entregador():
    hoy = date.today()
    pedidos = (Venta.query
               .filter(db.func.date(Venta.fechaventa) == hoy)
               .order_by(Venta.idventa.asc())
               .all())
    return render_template('empleados/entregador.html', pedidos=pedidos)


@empleados_bp.route('/api/entregador/pedidos')
@login_required
def api_entregador_pedidos():
    hoy = date.today()
    pedidos = (Venta.query
               .filter(db.func.date(Venta.fechaventa) == hoy)
               .order_by(Venta.idventa.asc())
               .all())
    return jsonify([p.to_dict() for p in pedidos])


@empleados_bp.route('/api/entregador/entregar/<int:idventa>', methods=['POST'])
@login_required
def api_entregar(idventa):
    Venta.query.get_or_404(idventa)
    return jsonify({'ok': True})
