from ..utils import hoy_bogota
from .base import db


class Reporte(db.Model):
    __tablename__ = 'reporte'
    idreporte   = db.Column(db.Integer, primary_key=True)
    idadmin     = db.Column(db.Integer, db.ForeignKey('admin.documento'), nullable=False)
    descripcion = db.Column(db.String(255), nullable=True)
    fecha       = db.Column(db.Date, nullable=True, default=hoy_bogota)
    producto    = db.Column(db.Integer, db.ForeignKey('producto.idproducto'), nullable=False)

    prod_rel  = db.relationship('Producto', backref='reportes')
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
