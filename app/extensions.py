"""Extensiones compartidas, separadas para evitar imports circulares."""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Storage fijado en memoria a proposito: la version desplegada tomaba
# RATELIMIT_STORAGE_URI del entorno y en produccion esa variable apuntaba
# a un Redis que exige autenticacion, provocando AuthenticationError
# (HTTP 500) antes de entrar a la ruta. El storage_uri del constructor
# tiene prioridad sobre cualquier RATELIMIT_STORAGE_URI externa, asi que
# una URI rota inyectada por el entorno ya no puede tumbar la app.
#
# Con 2 workers de Gunicorn cada proceso lleva su propio conteo: el
# limite efectivo real se multiplica por el numero de workers (p.ej.
# 10/min por worker en /cliente/registro). Aceptado como compromiso;
# si algun dia se requiere conteo global exacto, apuntar storage_uri
# aca mismo a un Redis con credenciales (redis://:clave@host:6379/0),
# nunca a traves del entorno sin autenticacion.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri='memory://',
)
