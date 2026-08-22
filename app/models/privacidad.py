from ..utils import ahora_bogota
from .base import db


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
