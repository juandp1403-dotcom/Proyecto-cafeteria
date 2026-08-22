from ..utils import ahora_bogota
from .base import db


class Producto(db.Model):
    __tablename__ = 'producto'
    idproducto   = db.Column(db.Integer, primary_key=True)
    nombre       = db.Column(db.String(100), nullable=False)
    precio       = db.Column(db.Integer, nullable=False)
    stock        = db.Column(db.Integer, nullable=False, default=0)
    imagen       = db.Column(db.String(255), nullable=True, default=None)
    stock_minimo = db.Column(db.Integer, nullable=False, default=10)
    costo        = db.Column(db.Integer, nullable=False, default=0)
    # especial_hasta opcional: si se pone, la promocion vence esa fecha.
    es_especial     = db.Column(db.Boolean, nullable=False, default=False)
    especial_hasta  = db.Column(db.Date, nullable=True)
    created_at   = db.Column(db.DateTime, default=ahora_bogota)
    updated_at   = db.Column(db.DateTime, default=ahora_bogota, onupdate=ahora_bogota)
    # Borrado logico: los productos con historial nunca se borran fisicamente.
    activo       = db.Column(db.Boolean, nullable=False, default=True)

    detalles_venta  = db.relationship('DetalleVenta',  back_populates='producto')
    detalles_compra = db.relationship('DetalleCompra', back_populates='producto')

    @property
    def estado(self):
        """Retorna el estado del producto segun su stock y umbral personalizado."""
        if self.stock == 0:
            return 'Agotado'
        umbral_casi = max(self.stock_minimo // 2, 1)
        if self.stock < umbral_casi:
            return 'Casi agotado'
        if self.stock < self.stock_minimo:
            return 'Poco stock'
        return 'En stock'

    def to_dict(self):
        return {
            'idproducto':   self.idproducto,
            'nombre':       self.nombre,
            'precio':       self.precio,
            'stock':        self.stock,
            'imagen':       self.imagen,
            'estado':       self.estado,
            'stock_minimo': self.stock_minimo,
            'costo':        self.costo,
        }


def ajustar_stock(idproducto, delta):
    """UPDATE condicional atomico para que operaciones concurrentes no se
    pisen. Devuelve True si se aplico, False si no habia stock suficiente."""
    query = Producto.query.filter(Producto.idproducto == idproducto)
    if delta < 0:
        query = query.filter(Producto.stock >= -delta)
    afectados = query.update({'stock': Producto.stock + delta})
    return afectados > 0
