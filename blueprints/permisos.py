from functools import wraps
from flask import abort, flash, redirect, url_for, current_app
from flask_login import current_user


PERMISOS = {
    'admin': {
        'ver_todo': True,
        'escribir_todo': True,
    },
    'auditor': {
        'ver_todo': True,
        'escribir_todo': False,
    },
    'cajero': {
        'ver_todo': True,
        'escribir_todo': False,
        'aceptar_rechazar_venta': True,
        'generar_reporte': True,
    },
    'despachador': {
        'ver_todo': False,
        'ver_solo': ['ventas'],
        'cambiar_estado_entrega': True,
    },
}

PAGINAS_ADMIN = ['dashboard', 'productos', 'ventas', 'compras', 'usuarios', 'reportes']


def tipo_usuario_actual():
    if not current_user.is_authenticated:
        return None
    rid = current_user.get_id()
    if rid.startswith('admin:'):
        return 'admin'
    if rid.startswith('personal:'):
        return getattr(current_user, 'rol', None)
    return None


def puede(permiso):
    rol = tipo_usuario_actual()
    if rol is None:
        return False
    permisos_rol = PERMISOS.get(rol, {})
    return permisos_rol.get(permiso, False)


def puede_ver_pagina(nombre_pagina):
    rol = tipo_usuario_actual()
    if rol is None:
        return False
    if rol in ('admin', 'auditor', 'cajero'):
        return True
    if rol == 'despachador':
        return nombre_pagina in PERMISOS['despachador'].get('ver_solo', [])
    return False


def requiere_permiso(permiso):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return current_app.login_manager.unauthorized()
            if not puede(permiso):
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def requiere_ver_pagina(nombre_pagina):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return current_app.login_manager.unauthorized()
            if not puede_ver_pagina(nombre_pagina):
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def registrar_context_processor(app):
    @app.context_processor
    def inject_permisos():
        return dict(
            puede=puede,
            puede_ver_pagina=puede_ver_pagina,
            tipo_usuario_actual=tipo_usuario_actual,
        )
