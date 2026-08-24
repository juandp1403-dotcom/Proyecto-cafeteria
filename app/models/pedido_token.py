import secrets
from datetime import datetime

from .base import db


class TokenPedido(db.Model):
    """Token de un solo uso por cliente: evita que un doble clic (o una
    peticion reenviada por red lenta) confirme el mismo pedido dos veces."""
    __tablename__ = 'tokenpedido'
    idtoken           = db.Column(db.Integer, primary_key=True)
    token             = db.Column(db.String(64), nullable=False, unique=True)
    documento_cliente = db.Column(db.Integer, nullable=False)
    usado             = db.Column(db.Boolean, nullable=False, default=False)
    creado            = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


def crear_token_pedido(documento_cliente):
    """Genera un token de un solo uso para el proximo pedido de este
    cliente, invalidando cualquier token anterior sin usar."""
    TokenPedido.query.filter_by(
        documento_cliente=documento_cliente, usado=False
    ).update({'usado': True})
    token = secrets.token_urlsafe(16)
    db.session.add(TokenPedido(token=token, documento_cliente=documento_cliente))
    db.session.commit()
    return token


def consumir_token_pedido(token, documento_cliente):
    """UPDATE condicional atomico (mismo patron que ajustar_stock): marca
    el token como usado solo si aun no lo estaba. Devuelve True si el
    token era valido, False si ya se habia usado o no existe."""
    if not token:
        return False
    afectados = TokenPedido.query.filter_by(
        token=token, documento_cliente=documento_cliente, usado=False
    ).update({'usado': True})
    return afectados > 0
