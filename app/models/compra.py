from ..utils import ahora_bogota
from .base import db


class Compra(db.Model):
    __tablename__ = 'compra'
    idcompra       = db.Column(db.Integer, primary_key=True)
    nombrevendedor = db.Column(db.String(100), nullable=False)
    precio         = db.Column(db.Integer, nullable=False)
    # Timestamp completo: permite mostrar fecha y hora por separado.
    # Filas legacy (tipo DATE) quedan con hora 00:00; ver _migrar_esquema.
    fechacompra    = db.Column(db.DateTime, default=ahora_bogota)
    documentoadmin = db.Column(db.Integer, db.ForeignKey('admin.documento'), nullable=False)

    admin_rel = db.relationship('Admin',         back_populates='compras')
    detalles  = db.relationship('DetalleCompra', back_populates='compra_rel', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'idcompra':       self.idcompra,
            'nombrevendedor': self.nombrevendedor,
            'precio':         self.precio,
            'fechacompra':    self.fechacompra.strftime('%d/%m/%Y %H:%M') if self.fechacompra else '',
            'documentoadmin': self.documentoadmin,
            'detalles':       [d.to_dict() for d in self.detalles],
        }


class DetalleCompra(db.Model):
    __tablename__ = 'detallecompra'
    iddetallecompra = db.Column(db.Integer, primary_key=True)
    idcompra        = db.Column(db.Integer, db.ForeignKey('compra.idcompra'),     nullable=False)
    idproducto      = db.Column(db.Integer, db.ForeignKey('producto.idproducto'), nullable=False)
    cantidad        = db.Column(db.Integer, nullable=False)
    # Precio total pagado por la linea al momento de la compra (historico).
    subtotal        = db.Column(db.Integer, nullable=False, default=0)

    compra_rel = db.relationship('Compra',   back_populates='detalles',        foreign_keys=[idcompra])
    producto   = db.relationship('Producto', back_populates='detalles_compra', foreign_keys=[idproducto])

    def to_dict(self):
        return {
            'iddetallecompra': self.iddetallecompra,
            'idproducto':      self.idproducto,
            'nombre_producto': self.producto.nombre if self.producto else '',
            'cantidad':        self.cantidad,
            'subtotal':        self.subtotal or 0,
        }
