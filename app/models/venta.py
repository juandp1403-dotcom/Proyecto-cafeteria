from ..utils import ahora_bogota
from .base import db


class Cliente(db.Model):
    __tablename__ = 'cliente'
    documento = db.Column(db.Integer, primary_key=True)
    nombre    = db.Column(db.String(100), nullable=False)
    ficha     = db.Column(db.Integer, nullable=False)

    ventas = db.relationship('Venta', back_populates='cliente_rel')


class Venta(db.Model):
    __tablename__ = 'venta'
    idventa    = db.Column(db.Integer, primary_key=True)
    precio     = db.Column(db.Integer, nullable=False)
    cliente    = db.Column(db.Integer, db.ForeignKey('cliente.documento'), nullable=False)
    # HU-56: fecha Y hora reales en zona America/Bogota
    fechaventa = db.Column(db.DateTime, default=ahora_bogota)
    estado     = db.Column(db.String(30), nullable=False, default='Pendiente de Pago')
    # HU-76: como se pago la venta -- necesario para el cierre de caja
    # (HU-75, pendiente) y para que los reportes reflejen la realidad
    # de como entra el dinero, no solo el total.
    metodo_pago = db.Column(db.String(20), nullable=True)
    # HU-57: numero de pedido consecutivo DENTRO DEL DIA, persistido al
    # crear la venta (antes existian tres numeraciones distintas que no
    # coincidian entre si: el id global en la factura del cliente, un
    # indice de paginacion en la lista del cajero, y esta misma logica
    # pero calculada de nuevo en cada lectura via COUNT -- ahora es una
    # sola fuente, escrita una vez). NO reintroducir como @property: ya
    # se probo ese enfoque y hacia una consulta N+1 por venta.
    numero_pedido_diario = db.Column(db.Integer, nullable=True)
    # HU-62: auditoria
    created_at = db.Column(db.DateTime, default=ahora_bogota)
    updated_at = db.Column(db.DateTime, default=ahora_bogota, onupdate=ahora_bogota)

    cliente_rel = db.relationship('Cliente',      back_populates='ventas')
    detalles    = db.relationship('DetalleVenta', back_populates='venta', cascade='all, delete-orphan')

    # HU-22: to_dict() nunca se usa en ningun lado del codigo (verificado
    # por grep) y dependia de numero_pedido_diario, que hace una consulta
    # N+1 por venta -- se elimina en vez de dejarlo como codigo muerto
    # con una trampa de rendimiento.


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
