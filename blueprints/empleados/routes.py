from flask import render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from models import Admin, Personal
from extensions import limiter
from . import empleados_bp

# HU-52: hash dummy fijo para igualar el tiempo de respuesta cuando el
# email no existe en ninguna tabla -- sin esto, la ausencia de un
# check_password_hash real hacia la respuesta medible mas rapida,
# permitiendo enumerar correos del personal por temporizacion.
_HASH_DUMMY = generate_password_hash('valor-que-nunca-va-a-coincidir')


@empleados_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=['POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('cliente.catalogo'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        clave = request.form.get('clave', '').strip()

        admin = Admin.query.filter_by(email=email).first()
        if admin and admin.check_password(clave):
            login_user(admin)
            session.permanent = True
            return redirect(url_for('cliente.catalogo'))

        personal = Personal.query.filter_by(email=email).first()
        if personal and personal.check_password(clave):
            login_user(personal)
            session.permanent = True
            return redirect(url_for('cliente.catalogo'))

        if not admin and not personal:
            check_password_hash(_HASH_DUMMY, clave)

        flash('Correo o contraseña incorrectos.', 'danger')

    return render_template('empleados/login.html')


@empleados_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('Sesión de administrador cerrada.', 'success')
    return redirect(url_for('cliente.registro'))
