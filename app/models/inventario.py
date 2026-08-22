from ..utils import hoy_bogota
from .base import db
from .usuario import Admin, Personal


class BajaInventario(db.Model):
    __tablename__ = 'bajainventario'
    idbaja     = db.Column(db.Integer, primary_key=True)
    idproducto = db.Column(db.Integer, db.ForeignKey('producto.idproducto'), nullable=False)
    cantidad   = db.Column(db.Integer, nullable=False)
    motivo     = db.Column(db.String(255), nullable=False)
    # HU-71: categoria estructurada, separada del texto libre de motivo,
    # para poder agrupar cuanto se pierde por vencimiento vs. dano vs. otro.
    categoria  = db.Column(db.String(20), nullable=False, default='Otro')
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
