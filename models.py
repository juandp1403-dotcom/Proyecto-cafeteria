from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func, cast, Date
from utils import ahora_bogota, hoy_bogota

db = SQLAlchemy()


def expr_fecha(col):
    """Extrae la fecha (sin hora) de una columna DateTime, compatible con
    SQLite (func.date) y PostgreSQL (CAST ... AS DATE). HU-56."""
    try:
        es_sqlite = db.engine.url.drivername.startswith('sqlite')
    except Exception:
        es_sqlite = False
    if es_sqlite:
        return func.date(col)
    return cast(col, Date)

class Producto(db.Model):
    __tablename__ = 'producto'
    idproducto   = db.Column(db.Integer, primary_key=True)
    nombre       = db.Column(db.String(100), nullable=False)
    precio       = db.Column(db.Integer, nullable=False)
    stock        = db.Column(db.Integer, nullable=False, default=0)
    imagen       = db.Column(db.String(255), nullable=True, default=None)
    stock_minimo = db.Column(db.Integer, nullable=False, default=10)
    costo        = db.Column(db.Integer, nullable=False, default=0)
    # HU-62: auditoria (quien/cuando se creo y modifico por ultima vez)
    created_at   = db.Column(db.DateTime, default=ahora_bogota)
    updated_at   = db.Column(db.DateTime, default=ahora_bogota, onupdate=ahora_bogota)
    # HU-36: borrado logico; los productos con historial nunca se borran fisicamente
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
    # HU-62: auditoria
    created_at = db.Column(db.DateTime, default=ahora_bogota)
    updated_at = db.Column(db.DateTime, default=ahora_bogota, onupdate=ahora_bogota)

    cliente_rel = db.relationship('Cliente',      back_populates='ventas')
    detalles    = db.relationship('DetalleVenta', back_populates='venta', cascade='all, delete-orphan')

    @property
    def numero_pedido_diario(self):
        """Número secuencial de pedido dentro del mismo día."""
        fecha = (self.fechaventa.date() if self.fechaventa else hoy_bogota())
        if self.idventa:
            num = (db.session.query(func.count(Venta.idventa))
                   .filter(expr_fecha(Venta.fechaventa) == fecha, Venta.idventa <= self.idventa)
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

class Admin(UserMixin, db.Model):
    __tablename__ = 'admin'
    documento = db.Column(db.Integer, primary_key=True)
    nombre    = db.Column(db.String(100), nullable=False)
    clave     = db.Column(db.String(256), nullable=False)
    email     = db.Column(db.String(120), unique=True, nullable=False)
    rol       = db.Column(db.String(20), nullable=False, default='admin')
    # HU-36: desactivacion en lugar de borrado cuando tiene historial
    activo    = db.Column(db.Boolean, nullable=False, default=True)

    compras = db.relationship('Compra', back_populates='admin_rel')

    def get_id(self):
        return f'admin:{self.documento}'

    def set_password(self, password):
        self.clave = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.clave, password)


class Personal(UserMixin, db.Model):
    __tablename__ = 'personal'
    docpersonal = db.Column(db.Integer, primary_key=True)
    nombre      = db.Column(db.String(50))
    clave       = db.Column(db.String(255))
    email       = db.Column(db.String(30))
    rol         = db.Column(db.String(15))
    # HU-36: desactivacion en lugar de borrado cuando tiene historial
    activo      = db.Column(db.Boolean, nullable=False, default=True)

    def get_id(self):
        return f'personal:{self.docpersonal}'

    def set_password(self, password):
        self.clave = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.clave, password)

class Compra(db.Model):
    __tablename__ = 'compra'
    idcompra       = db.Column(db.Integer, primary_key=True)
    nombrevendedor = db.Column(db.String(100), nullable=False)
    precio         = db.Column(db.Integer, nullable=False)
    fechacompra    = db.Column(db.Date, default=hoy_bogota)
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

class BajaInventario(db.Model):
    __tablename__ = 'bajainventario'
    idbaja     = db.Column(db.Integer, primary_key=True)
    idproducto = db.Column(db.Integer, db.ForeignKey('producto.idproducto'), nullable=False)
    cantidad   = db.Column(db.Integer, nullable=False)
    motivo     = db.Column(db.String(255), nullable=False)
    fecha      = db.Column(db.Date, default=hoy_bogota)
    # HU-62: quien ejecuto la baja (Admin o Personal; sin FK por ser tablas distintas)
    usuario_documento = db.Column(db.Integer, nullable=True)
    usuario_tipo      = db.Column(db.String(20), nullable=True)  # 'admin' | 'personal'

    producto = db.relationship('Producto', backref='bajas')

    @property
    def usuario_nombre(self):
        """Nombre del usuario que registro la baja (para auditoria)."""
        if self.usuario_documento is None:
            return None
        if self.usuario_tipo == 'personal':
            p = db.session.get(Personal, self.usuario_documento)
            return p.nombre if p else None
        a = db.session.get(Admin, self.usuario_documento)
        return a.nombre if a else None


class SolicitudSupresion(db.Model):
    """HU-65/66: registro trazable de solicitudes de supresion de datos
    personales (Ley 1581 de 2012). Un admin las procesa manualmente."""
    __tablename__ = 'solicitudsupresion'
    idsolicitud       = db.Column(db.Integer, primary_key=True)
    documento_cliente = db.Column(db.Integer, nullable=False)
    nombre_cliente    = db.Column(db.String(100), nullable=True)
    motivo            = db.Column(db.String(500), nullable=True)
    fecha             = db.Column(db.DateTime, default=ahora_bogota)
    estado            = db.Column(db.String(20), nullable=False, default='Pendiente')  # Pendiente | Procesada

    def to_dict(self):
        return {
            'idsolicitud':       self.idsolicitud,
            'documento_cliente': self.documento_cliente,
            'nombre_cliente':    self.nombre_cliente or '',
            'motivo':            self.motivo or '',
            'fecha':             self.fecha.strftime('%d/%m/%Y %H:%M') if self.fecha else '',
            'estado':            self.estado,
        }


class Reporte(db.Model):
    __tablename__ = 'reporte'
    idreporte   = db.Column(db.Integer, primary_key=True)
    idadmin     = db.Column(db.Integer, nullable=False)
    descripcion = db.Column(db.String(255), nullable=True)
    fecha       = db.Column(db.Date, nullable=True, default=hoy_bogota)
    producto    = db.Column(db.Integer, db.ForeignKey('producto.idproducto'), nullable=False)

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
