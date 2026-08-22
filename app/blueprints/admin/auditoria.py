from flask import render_template, request
from flask_login import login_required
from ...models import RegistroAuditoria
from ..permisos import requiere_ver_pagina
from . import admin_bp


# Consulta de solo lectura del log de auditoria, restringida a admin/auditor.
@admin_bp.route('/auditoria')
@login_required
@requiere_ver_pagina('auditoria')
def auditoria():
    page = request.args.get('page', 1, type=int)
    registros = (RegistroAuditoria.query
                 .order_by(RegistroAuditoria.timestamp.desc())
                 .paginate(page=page, per_page=30, error_out=False))
    return render_template('admin/auditoria.html', registros=registros)
