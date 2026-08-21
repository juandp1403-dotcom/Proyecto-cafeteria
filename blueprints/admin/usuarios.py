from flask import render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from models import db, Admin, Personal, Compra, Reporte, BajaInventario, SolicitudSupresion, registrar_auditoria
from blueprints.permisos import requiere_permiso, requiere_ver_pagina
from . import admin_bp


# ── Gestión de usuarios (Admin + Personal) ───────────────────────────────────
@admin_bp.route('/usuarios')
@login_required
@requiere_ver_pagina('usuarios')
def usuarios():
    admins = Admin.query.order_by(Admin.documento).all()
    personal_list = Personal.query.order_by(Personal.docpersonal).all()
    # HU-66: solicitudes de supresion pendientes (solo visibles con ver_datos_personales)
    solicitudes = (SolicitudSupresion.query
                   .order_by(SolicitudSupresion.fecha.desc())
                   .limit(30)
                   .all())
    return render_template('admin/usuarios.html', admins=admins, personal_list=personal_list,
                           solicitudes=solicitudes)


@admin_bp.route('/usuarios/supresion/procesar/<int:idsolicitud>', methods=['POST'])
@login_required
@requiere_permiso('ver_datos_personales')
def solicitud_supresion_procesar(idsolicitud):
    """HU-66: marca una solicitud de supresion como procesada.
    El borrado/anonimizacion de los datos se realiza manualmente."""
    s = SolicitudSupresion.query.get_or_404(idsolicitud)
    s.estado = 'Procesada'
    db.session.commit()
    registrar_auditoria(current_user.email, 'procesar_solicitud_supresion', f'solicitud:{idsolicitud}')
    flash(f'Solicitud de supresión #{idsolicitud} marcada como procesada.', 'success')
    return redirect(url_for('admin_panel.usuarios'))


def _validar_password(clave):
    """HU-17: minimo 8 caracteres, combinando letras y numeros. El
    minlength del HTML es solo una ayuda visual, no protege nada por si
    solo -- un request directo a la ruta lo saltaba por completo."""
    if len(clave) < 8:
        return 'La contraseña debe tener al menos 8 caracteres.'
    if not any(c.isalpha() for c in clave) or not any(c.isdigit() for c in clave):
        return 'La contraseña debe combinar letras y números.'
    return None


@admin_bp.route('/usuarios/nuevo', methods=['POST'])
@login_required
@requiere_permiso('escribir_todo')
def usuario_nuevo():
    tipo_cuenta = request.form.get('tipo_cuenta', 'admin')
    doc    = request.form.get('documento', '').strip()
    nombre = request.form.get('nombre', '').strip()
    email  = request.form.get('email', '').strip()
    clave  = request.form.get('clave', '').strip()

    if not all([doc, nombre, email, clave]):
        flash('Todos los campos son obligatorios.', 'danger')
        return redirect(url_for('admin_panel.usuarios'))

    # HU-53: un documento no numerico ya no lanza una excepcion sin
    # capturar (500), se rechaza con un mensaje claro.
    try:
        doc_int = int(doc)
    except ValueError:
        flash('El documento debe ser un valor numerico.', 'danger')
        return redirect(url_for('admin_panel.usuarios'))

    error_clave = _validar_password(clave)
    if error_clave:
        flash(error_clave, 'danger')
        return redirect(url_for('admin_panel.usuarios'))

    if tipo_cuenta == 'personal':
        rol = request.form.get('rol_personal', 'cajero')
        if Personal.query.filter_by(email=email).first():
            flash('Ya existe un personal con ese correo.', 'danger')
            return redirect(url_for('admin_panel.usuarios'))
        if Personal.query.filter_by(docpersonal=doc_int).first():
            flash('Ya existe un personal con ese documento.', 'danger')
            return redirect(url_for('admin_panel.usuarios'))
        p = Personal(docpersonal=doc_int, nombre=nombre, email=email, clave='', rol=rol)
        p.set_password(clave)
        db.session.add(p)
        db.session.commit()
        registrar_auditoria(current_user.email, 'crear_usuario', f'personal:{doc_int}', f'rol={rol}')
        flash(f'Personal "{nombre}" creado correctamente.', 'success')
    else:
        if Admin.query.filter_by(email=email).first():
            flash('Ya existe un usuario con ese correo.', 'danger')
            return redirect(url_for('admin_panel.usuarios'))
        # HU-53: antes solo se validaba email duplicado para admin;
        # un documento repetido lanzaba IntegrityError sin capturar (500).
        if Admin.query.filter_by(documento=doc_int).first():
            flash('Ya existe un usuario con ese documento.', 'danger')
            return redirect(url_for('admin_panel.usuarios'))
        admin = Admin(documento=doc_int, nombre=nombre, email=email, clave='')
        admin.set_password(clave)
        db.session.add(admin)
        db.session.commit()
        registrar_auditoria(current_user.email, 'crear_usuario', f'admin:{doc_int}')
        flash(f'Usuario "{nombre}" creado correctamente.', 'success')

    return redirect(url_for('admin_panel.usuarios'))


@admin_bp.route('/usuarios/editar/<int:documento>', methods=['POST'])
@login_required
@requiere_permiso('escribir_todo')
def usuario_editar(documento):
    tipo_cuenta = request.form.get('tipo_cuenta', 'admin')

    if tipo_cuenta == 'personal':
        p = Personal.query.get_or_404(documento)
        p.nombre = request.form.get('nombre', p.nombre).strip()
        p.email  = request.form.get('email', p.email).strip()
        nuevo_rol = request.form.get('rol_personal', '').strip()
        if nuevo_rol:
            p.rol = nuevo_rol
        nueva_clave = request.form.get('clave', '').strip()
        if nueva_clave:
            error_clave = _validar_password(nueva_clave)
            if error_clave:
                flash(error_clave, 'danger')
                return redirect(url_for('admin_panel.usuarios'))
            p.set_password(nueva_clave)
        db.session.commit()
        registrar_auditoria(current_user.email, 'editar_usuario', f'personal:{documento}')
        flash('Personal actualizado correctamente.', 'success')
    else:
        admin = Admin.query.get_or_404(documento)
        admin.nombre = request.form.get('nombre', admin.nombre).strip()
        admin.email  = request.form.get('email', admin.email).strip()
        nueva_clave  = request.form.get('clave', '').strip()
        if nueva_clave:
            error_clave = _validar_password(nueva_clave)
            if error_clave:
                flash(error_clave, 'danger')
                return redirect(url_for('admin_panel.usuarios'))
            admin.set_password(nueva_clave)
        db.session.commit()
        registrar_auditoria(current_user.email, 'editar_usuario', f'admin:{documento}')
        flash('Usuario actualizado correctamente.', 'success')

    return redirect(url_for('admin_panel.usuarios'))


def _admin_tiene_historial(documento):
    """HU-36: un admin/cajero/auditor tiene historial si registro compras,
    reportes o bajas de inventario."""
    return (
        db.session.query(Compra.idcompra).filter_by(documentoadmin=documento).first() is not None or
        db.session.query(Reporte.idreporte).filter_by(idadmin=documento).first() is not None or
        db.session.query(BajaInventario.idbaja)
            .filter_by(usuario_documento=documento, usuario_tipo='admin').first() is not None
    )


def _personal_tiene_historial(docpersonal):
    """HU-36: personal tiene historial si registro bajas de inventario."""
    return db.session.query(BajaInventario.idbaja).filter_by(
        usuario_documento=docpersonal, usuario_tipo='personal').first() is not None


@admin_bp.route('/usuarios/eliminar/<int:documento>', methods=['POST'])
@login_required
@requiere_permiso('escribir_todo')
def usuario_eliminar(documento):
    from sqlalchemy.exc import IntegrityError
    tipo_cuenta = request.form.get('tipo_cuenta', 'admin')

    if tipo_cuenta == 'personal':
        p = Personal.query.get_or_404(documento)
        # HU-36: no se borra fisicamente si tiene historial asociado.
        if _personal_tiene_historial(documento):
            p.activo = False
            db.session.commit()
            registrar_auditoria(current_user.email, 'desactivar_usuario', f'personal:{documento}')
            flash('Este usuario tiene historial asociado y no puede eliminarse; fue desactivado.', 'danger')
            return redirect(url_for('admin_panel.usuarios'))
        try:
            db.session.delete(p)
            db.session.commit()
            registrar_auditoria(current_user.email, 'eliminar_usuario', f'personal:{documento}')
            flash('Personal eliminado.', 'warning')
        except IntegrityError:
            db.session.rollback()
            p.activo = False
            db.session.commit()
            registrar_auditoria(current_user.email, 'desactivar_usuario', f'personal:{documento}')
            flash('Este usuario tiene historial asociado y no puede eliminarse; fue desactivado.', 'danger')
    else:
        if documento == current_user.documento:
            flash('No puedes eliminar tu propio usuario.', 'danger')
            return redirect(url_for('admin_panel.usuarios'))
        admin = Admin.query.get_or_404(documento)
        # HU-36: no se borra fisicamente si tiene historial asociado.
        if _admin_tiene_historial(documento):
            admin.activo = False
            db.session.commit()
            registrar_auditoria(current_user.email, 'desactivar_usuario', f'admin:{documento}')
            flash('Este usuario tiene historial asociado y no puede eliminarse; fue desactivado.', 'danger')
            return redirect(url_for('admin_panel.usuarios'))
        try:
            db.session.delete(admin)
            db.session.commit()
            registrar_auditoria(current_user.email, 'eliminar_usuario', f'admin:{documento}')
            flash('Usuario eliminado.', 'warning')
        except IntegrityError:
            db.session.rollback()
            admin.activo = False
            db.session.commit()
            registrar_auditoria(current_user.email, 'desactivar_usuario', f'admin:{documento}')
            flash('Este usuario tiene historial asociado y no puede eliminarse; fue desactivado.', 'danger')

    return redirect(url_for('admin_panel.usuarios'))


@admin_bp.route('/usuarios/reactivar/<int:documento>', methods=['POST'])
@login_required
@requiere_permiso('escribir_todo')
def usuario_reactivar(documento):
    tipo_cuenta = request.form.get('tipo_cuenta', 'admin')
    if tipo_cuenta == 'personal':
        p = Personal.query.get_or_404(documento)
        p.activo = True
        registrar_auditoria(current_user.email, 'reactivar_usuario', f'personal:{documento}')
        flash(f'Personal "{p.nombre}" reactivado.', 'success')
    else:
        a = Admin.query.get_or_404(documento)
        a.activo = True
        registrar_auditoria(current_user.email, 'reactivar_usuario', f'admin:{documento}')
        flash(f'Usuario "{a.nombre}" reactivado.', 'success')
    db.session.commit()
    return redirect(url_for('admin_panel.usuarios'))
