from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Producto(db.Model):
    __tablename__ = 'producto'
    idproducto = db.Column(db.Integer, primary_key=True)
    nombre     = db.Column(db.String(100), nullable=False)
    precio     = db.Column(db.Integer, nullable=False)
    stock      = db.Column(db.Integer, nullable=False, default=0)
    imagen     = db.Column(db.String(255), nullable=True, default=None)

    detalles_venta  = db.relationship('DetalleVenta',  back_populates='producto')
    detalles_compra = db.relationship('DetalleCompra', back_populates='producto')

    @property
    def estado(self):
        """Retorna el estado del producto según su stock."""
        if self.stock == 0:
            return 'Agotado'
        elif self.stock < 5:
            return 'Casi agotado'
        elif self.stock < 10:
            return 'Poco stock'
        else:
            return 'En stock'

    def to_dict(self):
        return {
            'idproducto': self.idproducto,
            'nombre':     self.nombre,
            'precio':     self.precio,
            'stock':      self.stock,
            'imagen':     self.imagen,
            'estado':     self.estado,
        }

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
    fechaventa = db.Column(db.Date, default=datetime.utcnow)
    estado     = db.Column(db.String(30), nullable=False, default='Pendiente de Pago')

    cliente_rel = db.relationship('Cliente',      back_populates='ventas')
    detalles    = db.relationship('DetalleVenta', back_populates='venta', cascade='all, delete-orphan')

    @property
    def numero_pedido_diario(self):
        """Número secuencial de pedido dentro del mismo día."""
        from sqlalchemy import func
        fecha = self.fechaventa or datetime.utcnow().date()
        if self.idventa:
            num = (db.session.query(func.count(Venta.idventa))
                   .filter(Venta.fechaventa == fecha, Venta.idventa <= self.idventa)
                   .scalar())
        else:
            num = 0
        return num

    def to_dict(self):
        return {
            'idventa':            self.idventa,
            'numero_pedido_diario': self.numero_pedido_diario,
            'precio':             self.precio,
            'cliente':            self.cliente,
            'nombre_cliente':     self.cliente_rel.nombre if self.cliente_rel else '',
            'ficha_cliente':      self.cliente_rel.ficha  if self.cliente_rel else '',
            'fechaventa':         self.fechaventa.strftime('%d/%m/%Y') if self.fechaventa else '',
            'estado':             self.estado,
            'detalles':           [d.to_dict() for d in self.detalles]
        }

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

class Admin(UserMixin, db.Model):
    __tablename__ = 'admin'
    documento = db.Column(db.Integer, primary_key=True)
    nombre    = db.Column(db.String(100), nullable=False)
    clave     = db.Column(db.String(256), nullable=False)
    email     = db.Column(db.String(120), unique=True, nullable=False)

    compras = db.relationship('Compra', back_populates='admin_rel')

    def get_id(self):
        return str(self.documento)

    def set_password(self, password):
        self.clave = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.clave, password)

class Compra(db.Model):
    __tablename__ = 'compra'
    idcompra       = db.Column(db.Integer, primary_key=True)
    nombrevendedor = db.Column(db.String(100), nullable=False)
    precio         = db.Column(db.Integer, nullable=False)
    fechacompra    = db.Column(db.Date, default=datetime.utcnow)
    documentoadmin = db.Column(db.Integer, db.ForeignKey('admin.documento'), nullable=False)

    admin_rel = db.relationship('Admin',         back_populates='compras')
    detalles  = db.relationship('DetalleCompra', back_populates='compra_rel', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'idcompra':       self.idcompra,
            'nombrevendedor': self.nombrevendedor,
            'precio':         self.precio,
            'fechacompra':    self.fechacompra.strftime('%d/%m/%Y') if self.fechacompra else '',
            'documentoadmin': self.documentoadmin,
            'detalles':       [d.to_dict() for d in self.detalles],
        }

class DetalleCompra(db.Model):
    __tablename__ = 'detallecompra'
    iddetallecompra = db.Column(db.Integer, primary_key=True)
    idcompra        = db.Column(db.Integer, db.ForeignKey('compra.idcompra'),     nullable=False)
    idproducto      = db.Column(db.Integer, db.ForeignKey('producto.idproducto'), nullable=False)
    cantidad        = db.Column(db.Integer, nullable=False)

    compra_rel = db.relationship('Compra',   back_populates='detalles',        foreign_keys=[idcompra])
    producto   = db.relationship('Producto', back_populates='detalles_compra', foreign_keys=[idproducto])

    def to_dict(self):
        return {
            'iddetallecompra': self.iddetallecompra,
            'idproducto':      self.idproducto,
            'nombre_producto': self.producto.nombre if self.producto else '',
            'cantidad':        self.cantidad,
        }

class Reporte(db.Model):
    __tablename__ = 'reporte'
    idreporte  = db.Column(db.Integer, primary_key=True)
    idadmin    = db.Column(db.Integer, db.ForeignKey('admin.documento'), nullable=False)
    descripcion = db.Column(db.String(255), nullable=True)
    fecha      = db.Column(db.Date, nullable=True, default=datetime.utcnow)
    producto   = db.Column(db.Integer, db.ForeignKey('producto.idproducto'), nullable=False)

    admin_rel  = db.relationship('Admin',    backref='reportes')
    prod_rel   = db.relationship('Producto', backref='reportes')

    def to_dict(self):
        return {
            'idreporte':   self.idreporte,
            'idadmin':     self.idadmin,
            'nombre_admin': self.admin_rel.nombre if self.admin_rel else '',
            'descripcion': self.descripcion or '',
            'fecha':       self.fecha.strftime('%d/%m/%Y') if self.fecha else '',
            'idproducto':  self.producto,
            'nombre_producto': self.prod_rel.nombre if self.prod_rel else '',
        }
class BajaInventario(db.Model):
    __tablename__ = 'bajainventario'
    idbaja     = db.Column(db.Integer, primary_key=True)
    idproducto = db.Column(db.Integer, db.ForeignKey('producto.idproducto'), nullable=False)
    cantidad   = db.Column(db.Integer, nullable=False)
    motivo     = db.Column(db.String(255), nullable=False)
    fecha      = db.Column(db.Date, default=datetime.utcnow)

    producto = db.relationship('Producto', backref='bajas')


class Reporte(db.Model):
    __tablename__ = 'reporte'
    idreporte   = db.Column(db.Integer, primary_key=True)
    idadmin     = db.Column(db.Integer, db.ForeignKey('admin.documento'), nullable=False)
    descripcion = db.Column(db.String(255), nullable=True)
    fecha       = db.Column(db.Date, nullable=True, default=datetime.utcnow)
    producto    = db.Column(db.Integer, db.ForeignKey('producto.idproducto'), nullable=False)

    admin_rel = db.relationship('Admin',    backref='reportes')
    prod_rel  = db.relationship('Producto', backref='reportes')

    def to_dict(self):
        return {
            'idreporte':       self.idreporte,
            'idadmin':         self.idadmin,
            'nombre_admin':    self.admin_rel.nombre if self.admin_rel else '',
            'descripcion':     self.descripcion or '',
            'fecha':           self.fecha.strftime('%d/%m/%Y') if self.fecha else '',
            'idproducto':      self.producto,
            'nombre_producto': self.prod_rel.nombre if self.prod_rel else '',
        }
