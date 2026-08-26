from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from .base import db


class Admin(UserMixin, db.Model):
    __tablename__ = 'admin'
    documento = db.Column(db.BigInteger, primary_key=True)
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
    docpersonal = db.Column(db.BigInteger, primary_key=True)
    nombre      = db.Column(db.String(50))
    clave       = db.Column(db.String(255))
    email       = db.Column(db.String(120))
    rol         = db.Column(db.String(15))
    # HU-36: desactivacion en lugar de borrado cuando tiene historial
    activo      = db.Column(db.Boolean, nullable=False, default=True)

    def get_id(self):
        return f'personal:{self.docpersonal}'

    def set_password(self, password):
        self.clave = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.clave, password)
