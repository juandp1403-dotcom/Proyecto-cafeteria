from flask import current_app
from ..utils import ahora_bogota
from .base import db


class RegistroAuditoria(db.Model):
    """Quien hizo que y cuando. Usuario y entidad se guardan como texto
    (no FK) para que la fila sobreviva si esa cuenta o producto se borra."""
    __tablename__ = 'registroauditoria'
    idregistro = db.Column(db.Integer, primary_key=True)
    usuario    = db.Column(db.String(150), nullable=False)
    accion     = db.Column(db.String(50), nullable=False)
    entidad    = db.Column(db.String(150), nullable=True)
    detalle    = db.Column(db.String(500), nullable=True)
    timestamp  = db.Column(db.DateTime, default=ahora_bogota, nullable=False)


def registrar_auditoria(usuario, accion, entidad=None, detalle=None):
    """Registra un evento; nunca lanza excepcion hacia el llamador.

    Ademas de guardarlo en la tabla (para /admin/auditoria), lo imprime
    en el logger de la app -- sin esto, eventos como login_fallido solo
    eran visibles entrando al panel, nunca en los logs de Coolify."""
    try:
        db.session.add(RegistroAuditoria(
            usuario=usuario or 'desconocido',
            accion=accion,
            entidad=entidad,
            detalle=detalle,
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()

    try:
        nivel = current_app.logger.warning if accion == 'login_fallido' else current_app.logger.info
        nivel("auditoria: usuario=%s accion=%s entidad=%s detalle=%s", usuario, accion, entidad, detalle)
    except Exception:
        pass
