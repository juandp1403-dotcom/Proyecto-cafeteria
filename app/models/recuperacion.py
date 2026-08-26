import hashlib
import secrets
from datetime import datetime, timedelta

from .base import db


class TokenRecuperacion(db.Model):
    """Enlace de un solo uso para restablecer contraseña; se guarda solo
    el hash del token, nunca el valor en claro."""
    __tablename__ = 'tokenrecuperacion'
    idtoken     = db.Column(db.Integer, primary_key=True)
    tipo_cuenta = db.Column(db.String(10), nullable=False)   # 'admin' o 'personal'
    identificador = db.Column(db.BigInteger, nullable=False)    # documento / docpersonal
    token_hash  = db.Column(db.String(64), nullable=False, unique=True)
    creado      = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expira      = db.Column(db.DateTime, nullable=False)
    usado       = db.Column(db.Boolean, nullable=False, default=False)


def crear_token_recuperacion(tipo_cuenta, identificador, minutos_validez=30):
    """Genera un token de un solo uso e invalida cualquier token anterior
    sin usar de esa cuenta."""
    TokenRecuperacion.query.filter_by(
        tipo_cuenta=tipo_cuenta, identificador=identificador, usado=False
    ).update({'usado': True})

    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    db.session.add(TokenRecuperacion(
        tipo_cuenta=tipo_cuenta,
        identificador=identificador,
        token_hash=token_hash,
        expira=datetime.utcnow() + timedelta(minutes=minutos_validez),
    ))
    db.session.commit()
    return token


def validar_token_recuperacion(token):
    """Retorna el registro valido (no usado, no expirado) para ese
    token, o None. No lo marca como usado."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    registro = TokenRecuperacion.query.filter_by(token_hash=token_hash, usado=False).first()
    if registro is None:
        return None
    if registro.expira < datetime.utcnow():
        return None
    return registro
