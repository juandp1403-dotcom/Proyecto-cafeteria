from datetime import datetime

from .base import db


class RegistroAuditoria(db.Model):
    """HU-20: quien hizo que y cuando, para acciones sensibles (login
    fallido, creacion/edicion/borrado de usuarios y productos, cambios
    de precio, bajas de inventario). Se guarda usuario+entidad como
    texto (no FK) a proposito: la fila de auditoria debe sobrevivir
    aunque la cuenta o el producto involucrado se borren despues."""
    __tablename__ = 'registroauditoria'
    idregistro = db.Column(db.Integer, primary_key=True)
    usuario    = db.Column(db.String(150), nullable=False)
    accion     = db.Column(db.String(50), nullable=False)
    entidad    = db.Column(db.String(150), nullable=True)
    detalle    = db.Column(db.String(500), nullable=True)
    timestamp  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


def registrar_auditoria(usuario, accion, entidad=None, detalle=None):
    """Registra un evento de auditoria. Nunca lanza una excepcion hacia
    el llamador: un fallo al escribir el log de auditoria no debe
    tumbar la operacion real (crear un usuario, aceptar una venta)."""
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
