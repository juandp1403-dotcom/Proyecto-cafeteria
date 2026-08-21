from flask import render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import Admin, Personal
from . import empleados_bp


@empleados_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('cliente.catalogo'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        clave = request.form.get('clave', '').strip()

        admin = Admin.query.filter_by(email=email, activo=True).first()
        if admin and admin.check_password(clave):
            login_user(admin)
            return redirect(url_for('cliente.catalogo'))

        personal = Personal.query.filter_by(email=email, activo=True).first()
        if personal and personal.check_password(clave):
            login_user(personal)
            return redirect(url_for('cliente.catalogo'))

        flash('Correo o contraseña incorrectos.', 'danger')

    return render_template('empleados/login.html')


@empleados_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión de administrador cerrada.', 'success')
    return redirect(url_for('cliente.registro'))
