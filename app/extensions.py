"""Extensiones compartidas, separadas para evitar imports circulares."""
import os
import logging

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

logger = logging.getLogger(__name__)


def _storage_uri_resiliente():
    """Verifica RATELIMIT_STORAGE_URI antes de usarla: si el Redis de esa
    URI no responde (caido, credenciales invalidas, URI mal formada), cae
    a memoria en vez de dejar que Flask-Limiter reviente con un 500 en
    cada request limitado -- eso fue justo lo que tumbo el login antes
    (AuthenticationError contra un Redis con auth mal configurada).

    Con memoria, cada worker de Gunicorn lleva su propio conteo (el
    limite efectivo se multiplica por el numero de workers); es el
    peor caso aceptable, nunca un 500 para el usuario."""
    uri = os.environ.get('RATELIMIT_STORAGE_URI')
    if not uri:
        return 'memory://'
    try:
        import redis
        redis.from_url(uri, socket_connect_timeout=2).ping()
        return uri
    except Exception as e:
        logger.warning(
            "RATELIMIT_STORAGE_URI no responde (%s), usando memoria como "
            "respaldo para el rate limiting: %s", uri, e
        )
        return 'memory://'


limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_storage_uri_resiliente(),
)
