from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# ─────────────────────────────────────────
# PRODUCTO
# ─────────────────────────────────────────
class Producto(db.Model):
    __tablename__ = 'producto'
    idproducto = db.Column(db.Integer, primary_key=True)
    nombre     = db.Column(db.String(100), nullable=False)
    precio     = db.Column(db.Integer, nullable=False)
    stock      = db.Column(db.Integer, nullable=False, default=0)
    imagen_url = db.Column(db.String(200), nullable=True)
    activo     = db.Column(db.Boolean, default=True)

    detalles_venta  = db.relationship('DetalleVenta',  back_populates='producto')
    detalles_compra = db.relationship('DetalleCompra', back_populates='producto')

    def to_dict(self):
        return {
            'idproducto': self.idproducto,
            'nombre':     self.nombre,
            'precio':     self.precio,
            'stock':      self.stock,
            'imagen_url': self.imagen_url or '',
            'activo':     self.activo
        }

# ─────────────────────────────────────────
# CLIENTE
# ─────────────────────────────────────────
class Cliente(db.Model):
    __tablename__ = 'cliente'
    documento = db.Column(db.Integer, primary_key=True)
    nombre    = db.Column(db.String(100), nullable=False)
    ficha     = db.Column(db.Integer, nullable=False)

    ventas = db.relationship('Venta', back_populates='cliente_rel')

# ─────────────────────────────────────────
# VENTA
# ─────────────────────────────────────────
class Venta(db.Model):
    __tablename__ = 'venta'
    idventa              = db.Column(db.Integer, primary_key=True)
    precio               = db.Column(db.Integer, nullable=False)
    cliente              = db.Column(db.Integer, db.ForeignKey('cliente.documento'), nullable=False)
    fechaventa           = db.Column(db.DateTime, default=datetime.utcnow)
    numero_pedido_diario = db.Column(db.Integer, nullable=False, default=1)
    estado               = db.Column(db.String(30), nullable=False, default='Pendiente de Pago')

    cliente_rel = db.relationship('Cliente',      back_populates='ventas')
    detalles    = db.relationship('DetalleVenta', back_populates='venta', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'idventa':              self.idventa,
            'precio':               self.precio,
            'cliente':              self.cliente,
            'nombre_cliente':       self.cliente_rel.nombre if self.cliente_rel else '',
            'ficha_cliente':        self.cliente_rel.ficha  if self.cliente_rel else '',
            'fechaventa':           self.fechaventa.strftime('%d/%m/%Y %H:%M'),
            'numero_pedido_diario': self.numero_pedido_diario,
            'estado':               self.estado,
            'detalles':             [d.to_dict() for d in self.detalles]
        }

# ─────────────────────────────────────────
# DETALLE VENTA
# ─────────────────────────────────────────
class DetalleVenta(db.Model):
    __tablename__ = 'detalleventa'
    iddetalle  = db.Column(db.Integer, primary_key=True)
    idventa    = db.Column(db.Integer, db.ForeignKey('venta.idventa'),       nullable=False)
    idproducto = db.Column(db.Integer, db.ForeignKey('producto.idproducto'), nullable=False)
    cantidad   = db.Column(db.Integer, nullable=False)

    venta    = db.relationship('Venta',    back_populates='detalles')
    producto = db.relationship('Producto', back_populates='detalles_venta')

    def to_dict(self):
        return {
            'iddetalle':       self.iddetalle,
            'idproducto':      self.idproducto,
            'nombre_producto': self.producto.nombre if self.producto else '',
            'precio_unitario': self.producto.precio if self.producto else 0,
            'cantidad':        self.cantidad,
            'subtotal':        (self.producto.precio * self.cantidad) if self.producto else 0
        }

# ─────────────────────────────────────────
# ADMIN (con Flask-Login)
# ─────────────────────────────────────────
class Admin(UserMixin, db.Model):
    __tablename__ = 'admin'
    documento = db.Column(db.Integer, primary_key=True)
    nombre    = db.Column(db.String(100), nullable=False)
    clave     = db.Column(db.String(256), nullable=False)
    email     = db.Column(db.String(120), unique=True, nullable=False)
    rol       = db.Column(db.String(20),  nullable=False, default='Cajero')

    compras = db.relationship('Compra', back_populates='admin_rel')

    def get_id(self):
        return str(self.documento)

    def set_password(self, password):
        self.clave = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.clave, password)

# ─────────────────────────────────────────
# COMPRA (abastecimiento)
# ─────────────────────────────────────────
class Compra(db.Model):
    __tablename__ = 'compra'
    idcompra       = db.Column(db.Integer, primary_key=True)
    nombrevendedor = db.Column(db.String(100), nullable=False)
    precio         = db.Column(db.Integer, nullable=False)
    fechacompra    = db.Column(db.DateTime, default=datetime.utcnow)
    documentoadmin = db.Column(db.Integer, db.ForeignKey('admin.documento'), nullable=False)

    admin_rel = db.relationship('Admin',         back_populates='compras')
    detalles  = db.relationship('DetalleCompra', back_populates='compra_rel', cascade='all, delete-orphan')

# ─────────────────────────────────────────
# DETALLE COMPRA
# ─────────────────────────────────────────
class DetalleCompra(db.Model):
    __tablename__ = 'detallecompra'
    iddetallecompra = db.Column(db.Integer, primary_key=True)
    idcompra        = db.Column(db.Integer, db.ForeignKey('compra.idcompra'),    nullable=False)
    idproducto      = db.Column(db.Integer, db.ForeignKey('producto.idproducto'), nullable=False)
    cantidad        = db.Column(db.Integer, nullable=False)

    compra_rel = db.relationship('Compra',   back_populates='detalles',       foreign_keys=[idcompra])
    producto   = db.relationship('Producto', back_populates='detalles_compra', foreign_keys=[idproducto])
