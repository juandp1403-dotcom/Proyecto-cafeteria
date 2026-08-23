"""Extensiones compartidas, separadas para evitar imports circulares."""
import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# HU-1 (auditoria 2026-08-23): sin storage_uri, Flask-Limiter usa memoria
# por proceso -- con Gunicorn corriendo mas de un worker, cada uno lleva
# su propio conteo de intentos, duplicando de facto los limites de login
# y recuperacion de clave. RATELIMIT_STORAGE_URI apunta a un backend
# compartido (Redis) en produccion; sin definirla, se mantiene el
# comportamiento anterior (memoria) para no romper el desarrollo local.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.environ.get('RATELIMIT_STORAGE_URI', 'memory://'),
)
