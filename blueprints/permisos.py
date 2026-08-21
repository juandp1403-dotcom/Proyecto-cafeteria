from functools import wraps
from flask import abort, flash, redirect, url_for, current_app
from flask_login import current_user


PAGINAS_ADMIN = ['dashboard', 'productos', 'ventas', 'compras', 'usuarios', 'reportes', 'auditoria']

# HU-59: 'usuarios' expone datos personales (documento, nombre, correo)
# de todo el personal -- solo admin y auditor lo necesitan para su rol.
# 'exportar_datos_personales' separa el permiso de solo-ver-la-pagina
# del permiso de exportar el detalle completo (ej. Excel de ventas con
# documento/ficha de cliente); un despachador puede ver la pagina de
# ventas pero no exportar ese detalle.
PERMISOS = {
    'admin': {
        'ver_todo': True,
        'escribir_todo': True,
        'exportar_datos_personales': True,
        'paginas': PAGINAS_ADMIN,
    },
    'auditor': {
        'ver_todo': True,
        'escribir_todo': False,
        'exportar_datos_personales': True,
        'paginas': PAGINAS_ADMIN,
    },
    'cajero': {
        'ver_todo': True,
        'escribir_todo': False,
        'aceptar_rechazar_venta': True,
        'generar_reporte': True,
        'exportar_datos_personales': True,
        'paginas': ['dashboard', 'productos', 'ventas', 'compras', 'reportes'],
    },
    'despachador': {
        'ver_todo': False,
        'ver_solo': ['ventas'],
        'cambiar_estado_entrega': True,
        'exportar_datos_personales': False,
        'paginas': ['ventas'],
    },
}


def tipo_usuario_actual():
    if not current_user.is_authenticated:
        return None
    rid = current_user.get_id()
    if rid.startswith('admin:'):
        return getattr(current_user, 'rol', None) or 'admin'
    if rid.startswith('personal:'):
        return getattr(current_user, 'rol', None)
    return None


def puede(permiso):
    rol = tipo_usuario_actual()
    if rol is None:
        return False
    if rol == 'admin':
        return True
    permisos_rol = PERMISOS.get(rol, {})
    return permisos_rol.get(permiso, False)


def puede_ver_pagina(nombre_pagina):
    rol = tipo_usuario_actual()
    if rol is None:
        return False
    return nombre_pagina in PERMISOS.get(rol, {}).get('paginas', [])


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
