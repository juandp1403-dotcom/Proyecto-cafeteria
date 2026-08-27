from datetime import timedelta

from ..utils import ahora_bogota
from .base import db
from .producto import ajustar_stock


class Cliente(db.Model):
    __tablename__ = 'cliente'
    documento = db.Column(db.BigInteger, primary_key=True)
    nombre    = db.Column(db.String(100), nullable=False)
    ficha     = db.Column(db.Integer, nullable=False)

    ventas = db.relationship('Venta', back_populates='cliente_rel')


class Venta(db.Model):
    __tablename__ = 'venta'
    idventa    = db.Column(db.Integer, primary_key=True)
    precio     = db.Column(db.Integer, nullable=False)
    cliente    = db.Column(db.BigInteger, db.ForeignKey('cliente.documento'), nullable=False)
    fechaventa = db.Column(db.DateTime, default=ahora_bogota)
    estado     = db.Column(db.String(30), nullable=False, default='Pendiente de Pago')
    metodo_pago = db.Column(db.String(20), nullable=True)
    # Consecutivo dentro del dia, escrito una sola vez al crear la venta.
    # No reintroducir como @property: hacia una consulta N+1 por venta.
    numero_pedido_diario = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=ahora_bogota)
    updated_at = db.Column(db.DateTime, default=ahora_bogota, onupdate=ahora_bogota)

    cliente_rel = db.relationship('Cliente',      back_populates='ventas')
    detalles    = db.relationship('DetalleVenta', back_populates='venta', cascade='all, delete-orphan')


class DetalleVenta(db.Model):
    __tablename__ = 'detalleventa'
    iddetalle  = db.Column(db.Integer, primary_key=True)
    idventa    = db.Column(db.Integer, db.ForeignKey('venta.idventa'),       nullable=False)
    idproducto = db.Column(db.Integer, db.ForeignKey('producto.idproducto'), nullable=False)
    cantidad   = db.Column(db.Integer, nullable=False)
    # Precio del producto AL MOMENTO de la venta (historico, inmutable).
    precio_unitario = db.Column(db.Integer, nullable=False, default=0)

    venta    = db.relationship('Venta',    back_populates='detalles')
    producto = db.relationship('Producto', back_populates='detalles_venta')

    @property
    def precio_historico(self):
        """Precio unitario efectivo; fallback al precio actual solo para
        filas legacy que no pudieron ser rellenadas."""
        if self.precio_unitario is not None:
            return self.precio_unitario
        return self.producto.precio if self.producto else 0

    def to_dict(self):
        return {
            'iddetalle':       self.iddetalle,
            'idproducto':      self.idproducto,
            'nombre_producto': self.producto.nombre if self.producto else '',
            'precio_unitario': self.precio_historico,
            'cantidad':        self.cantidad,
            'subtotal':        self.precio_historico * self.cantidad
        }


def cancelar_pedidos_expirados(minutos=20):
    """Cancela pedidos pendientes vencidos y devuelve su stock."""
    limite = ahora_bogota() - timedelta(minutes=minutos)
    pendientes = Venta.query.filter(
        Venta.estado == 'Pendiente de Pago',
        Venta.fechaventa <= limite,
    ).all()
    cancelados = 0

    for venta in pendientes:
        detalles = list(venta.detalles)
        afectadas = Venta.query.filter(
            Venta.idventa == venta.idventa,
            Venta.estado == 'Pendiente de Pago',
        ).update({'estado': 'Cancelado'}, synchronize_session=False)
        if not afectadas:
            continue
        for detalle in detalles:
            ajustar_stock(detalle.idproducto, detalle.cantidad)
        cancelados += 1

    if cancelados:
        db.session.commit()
    return cancelados
