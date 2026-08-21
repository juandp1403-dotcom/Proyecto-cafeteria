import secrets
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Producto(db.Model):
    __tablename__ = 'producto'
    idproducto   = db.Column(db.Integer, primary_key=True)
    nombre       = db.Column(db.String(100), nullable=False)
    precio       = db.Column(db.Integer, nullable=False)
    stock        = db.Column(db.Integer, nullable=False, default=0)
    imagen       = db.Column(db.String(255), nullable=True, default=None)
    stock_minimo = db.Column(db.Integer, nullable=False, default=10)
    costo        = db.Column(db.Integer, nullable=False, default=0)
    # HU-68: destacar un producto como especial/promocion del dia en el
    # catalogo. especial_hasta es opcional -- si se pone, la promocion
    # se considera vencida despues de esa fecha (logica en el codigo).
    es_especial     = db.Column(db.Boolean, nullable=False, default=False)
    especial_hasta  = db.Column(db.Date, nullable=True)

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
    """Ajusta el stock de un producto con un UPDATE condicional atomico,
    para que dos operaciones concurrentes (venta, baja, rechazo, compra)
    no se pisen entre si. Si delta es negativo, exige que el stock
    resultante no quede negativo. Devuelve True si se aplico el ajuste,
    False si no habia stock suficiente (delta negativo)."""
    query = Producto.query.filter(Producto.idproducto == idproducto)
    if delta < 0:
        query = query.filter(Producto.stock >= -delta)
    afectados = query.update({'stock': Producto.stock + delta})
    return afectados > 0

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
    # HU-76: como se pago la venta -- necesario para el cierre de caja
    # (HU-75, pendiente) y para que los reportes reflejen la realidad
    # de como entra el dinero, no solo el total.
    metodo_pago = db.Column(db.String(20), nullable=True)
    # HU-57: numero de pedido consecutivo DENTRO DEL DIA, persistido al
    # crear la venta (antes existian tres numeraciones distintas que no
    # coincidian entre si: el id global en la factura del cliente, un
    # indice de paginacion en la lista del cajero, y esta misma logica
    # pero calculada de nuevo en cada lectura via COUNT -- ahora es una
    # sola fuente, escrita una vez).
    numero_pedido_diario = db.Column(db.Integer, nullable=True)

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
    rol       = db.Column(db.String(20), nullable=False, default='admin')

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
    email       = db.Column(db.String(120))
    rol         = db.Column(db.String(15))

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

class BajaInventario(db.Model):
    __tablename__ = 'bajainventario'
    idbaja     = db.Column(db.Integer, primary_key=True)
    idproducto = db.Column(db.Integer, db.ForeignKey('producto.idproducto'), nullable=False)
    cantidad   = db.Column(db.Integer, nullable=False)
    motivo     = db.Column(db.String(255), nullable=False)
    # HU-71: categoria estructurada, separada del texto libre de motivo,
    # para poder agrupar cuanto se pierde por vencimiento vs. dano vs. otro.
    categoria  = db.Column(db.String(20), nullable=False, default='Otro')
    fecha      = db.Column(db.Date, default=datetime.utcnow)

    producto = db.relationship('Producto', backref='bajas')


class Reporte(db.Model):
    __tablename__ = 'reporte'
    idreporte   = db.Column(db.Integer, primary_key=True)
    idadmin     = db.Column(db.Integer, db.ForeignKey('admin.documento'), nullable=False)
    descripcion = db.Column(db.String(255), nullable=True)
    fecha       = db.Column(db.Date, nullable=True, default=datetime.utcnow)
    producto    = db.Column(db.Integer, db.ForeignKey('producto.idproducto'), nullable=False)

    prod_rel  = db.relationship('Producto', backref='reportes')
    # HU-22: to_dict() referenciaba self.admin_rel sin que existiera la
    # relacion (AttributeError garantizado si alguna vez se llamaba).
    admin_rel = db.relationship('Admin', backref='reportes_creados')

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


class TokenRecuperacion(db.Model):
    """HU-25: enlace de un solo uso para restablecer contraseña de
    admin/personal. Se guarda un hash del token (nunca el token en
    claro) para que una lectura de la base de datos no permita
    reutilizar un enlace ya enviado por correo."""
    __tablename__ = 'tokenrecuperacion'
    idtoken     = db.Column(db.Integer, primary_key=True)
    tipo_cuenta = db.Column(db.String(10), nullable=False)   # 'admin' o 'personal'
    identificador = db.Column(db.Integer, nullable=False)    # documento / docpersonal
    token_hash  = db.Column(db.String(64), nullable=False, unique=True)
    creado      = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expira      = db.Column(db.DateTime, nullable=False)
    usado       = db.Column(db.Boolean, nullable=False, default=False)


def crear_token_recuperacion(tipo_cuenta, identificador, minutos_validez=30):
    """Genera un token de un solo uso (valor en claro se retorna una
    unica vez para el enlace por correo; solo su hash SHA-256 se
    guarda). Invalida cualquier token anterior sin usar de esa cuenta."""
    import hashlib
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
    """Retorna el registro TokenRecuperacion valido (no usado, no
    expirado) para ese token, o None. No lo marca como usado -- eso
    ocurre solo al completar el cambio de contraseña."""
    import hashlib
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    registro = TokenRecuperacion.query.filter_by(token_hash=token_hash, usado=False).first()
    if registro is None:
        return None
    if registro.expira < datetime.utcnow():
        return None
    return registro
