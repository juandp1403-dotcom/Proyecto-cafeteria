import os
from datetime import timedelta
from dotenv import load_dotenv
from sshtunnel import SSHTunnelForwarder

load_dotenv()

_tunnel = None


def _abrir_tunel():
    """Abre un tunel SSH al servidor remoto y retorna el puerto local."""
    global _tunnel
    if _tunnel is not None:
        return _tunnel.local_bind_port

    ssh_host = os.environ.get('SSH_HOST')
    if not ssh_host:
        return None

    _tunnel = SSHTunnelForwarder(
        (ssh_host, int(os.environ.get('SSH_PORT', '22'))),
        ssh_username=os.environ.get('SSH_USER', 'root'),
        ssh_pkey=os.environ.get('SSH_KEY'),
        remote_bind_address=(
            os.environ.get('DB_HOST', '127.0.0.1'),
            int(os.environ.get('DB_PORT', '5432'))
        ),
    )
    _tunnel.start()
    print(f"[tunel SSH] Conectado a {ssh_host} -> puerto local {_tunnel.local_bind_port}")
    return _tunnel.local_bind_port


def _cerrar_tunel():
    global _tunnel
    if _tunnel:
        _tunnel.stop()
        _tunnel = None


def _construir_db_url(puerto_local):
    user = os.environ.get('DB_USER', 'juan')
    password = os.environ.get('DB_PASS', '')
    name = os.environ.get('DB_NAME', 'cafeteria')
    if password:
        return f"postgresql://{user}:{password}@127.0.0.1:{puerto_local}/{name}"
    return f"postgresql://{user}@127.0.0.1:{puerto_local}/{name}"


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'cambia-esta-clave')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TIMEZONE = 'America/Bogota'


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)


config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig
}
