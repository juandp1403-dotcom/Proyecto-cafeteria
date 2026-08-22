"""Extensiones de Flask compartidas entre app.py y los blueprints, para
evitar imports circulares (los blueprints necesitan @limiter.limit(...)
en sus rutas, y app.py necesita registrar los blueprints)."""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
