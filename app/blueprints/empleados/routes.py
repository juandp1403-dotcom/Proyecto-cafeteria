from flask import render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from ...models import (
    db, Admin, Personal, registrar_auditoria,
    crear_token_recuperacion, validar_token_recuperacion,
)
from ...extensions import limiter
from ...correo import enviar_correo
from . import empleados_bp

# Hash dummy para igualar el tiempo de respuesta cuando el email no
# existe, y evitar enumerar correos por temporizacion.
_HASH_DUMMY = generate_password_hash('valor-que-nunca-va-a-coincidir')


@empleados_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=['POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('cliente.catalogo'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        clave = request.form.get('clave', '').strip()

        admin = Admin.query.filter_by(email=email, activo=True).first()
        if admin and admin.check_password(clave):
            login_user(admin)
            session.permanent = True
            return redirect(url_for('cliente.catalogo'))

        personal = Personal.query.filter_by(email=email, activo=True).first()
        if personal and personal.check_password(clave):
            login_user(personal)
            session.permanent = True
            return redirect(url_for('cliente.catalogo'))

        if not admin and not personal:
            check_password_hash(_HASH_DUMMY, clave)

        registrar_auditoria(email or 'desconocido', 'login_fallido', detalle=f'ip={request.remote_addr}')
        flash('Correo o contraseña incorrectos.', 'danger')

    return render_template('empleados/login.html')


@empleados_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('Sesión de administrador cerrada.', 'success')
    return redirect(url_for('cliente.registro'))


@empleados_bp.route('/olvide-clave', methods=['GET', 'POST'])
@limiter.limit("3 per minute", methods=['POST'])
def olvide_clave():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        admin = Admin.query.filter_by(email=email).first()
        personal = Personal.query.filter_by(email=email).first() if not admin else None

        # Mismo mensaje exista o no la cuenta, para no revelar el correo.
        if admin:
            token = crear_token_recuperacion('admin', admin.documento)
            enlace = url_for('empleados.restablecer_clave', token=token, _external=True)
            enviar_correo(
                admin.email, 'Recuperar acceso - Cafetería SENA',
                f'Hola {admin.nombre},\n\nUsa este enlace para restablecer tu '
                f'contraseña (valido por 30 minutos, un solo uso):\n{enlace}\n\n'
                f'Si no solicitaste esto, ignora este correo.'
            )
        elif personal:
            token = crear_token_recuperacion('personal', personal.docpersonal)
            enlace = url_for('empleados.restablecer_clave', token=token, _external=True)
            enviar_correo(
                personal.email, 'Recuperar acceso - Cafetería SENA',
                f'Hola {personal.nombre},\n\nUsa este enlace para restablecer tu '
                f'contraseña (valido por 30 minutos, un solo uso):\n{enlace}\n\n'
                f'Si no solicitaste esto, ignora este correo.'
            )

        flash('Si el correo está registrado, recibirás un enlace para restablecer tu contraseña.', 'info')
        return redirect(url_for('empleados.login'))

    return render_template('empleados/olvide_clave.html')


@empleados_bp.route('/restablecer/<token>', methods=['GET', 'POST'])
def restablecer_clave(token):
    registro = validar_token_recuperacion(token)
    if registro is None:
        flash('El enlace no es válido o ya expiró. Solicita uno nuevo.', 'danger')
        return redirect(url_for('empleados.olvide_clave'))

    if request.method == 'POST':
        nueva_clave = request.form.get('clave', '').strip()
        if len(nueva_clave) < 8 or not any(c.isalpha() for c in nueva_clave) or not any(c.isdigit() for c in nueva_clave):
            flash('La contraseña debe tener al menos 8 caracteres y combinar letras y números.', 'danger')
            return render_template('empleados/restablecer_clave.html', token=token)

        if registro.tipo_cuenta == 'admin':
            cuenta = Admin.query.get(registro.identificador)
        else:
            cuenta = Personal.query.get(registro.identificador)

        if cuenta is None:
            flash('La cuenta asociada a este enlace ya no existe.', 'danger')
            return redirect(url_for('empleados.olvide_clave'))

        cuenta.set_password(nueva_clave)
        registro.usado = True
        db.session.commit()
        registrar_auditoria(cuenta.email, 'restablecer_clave', f'{registro.tipo_cuenta}:{registro.identificador}')
        flash('Contraseña actualizada. Ya puedes iniciar sesión.', 'success')
        return redirect(url_for('empleados.login'))

    return render_template('empleados/restablecer_clave.html', token=token)
