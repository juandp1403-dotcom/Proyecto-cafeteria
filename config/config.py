import os
import paramiko
from datetime import timedelta
from dotenv import load_dotenv
from sshtunnel import SSHTunnelForwarder

load_dotenv()

_tunnel = None


def _cargar_ssh_host_key(ssh_host):
    """Carga la clave de host esperada desde SSH_HOST_KEY (formato
    known_hosts). Sin ella, el tunel aceptaria cualquier clave de host
    del servidor remoto (riesgo de MITM)."""
    linea = os.environ.get('SSH_HOST_KEY')
    if not linea:
        return None
    entry = paramiko.hostkeys.HostKeyEntry.from_line(f"{ssh_host} {linea.strip()}")
    if entry is None:
        raise RuntimeError(
            "SSH_HOST_KEY tiene un formato invalido. Se espera 'tipo base64key', "
            "ej: 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA...'"
        )
    return entry.key


def _abrir_tunel(config_name='development'):
    """Abre un tunel SSH al servidor remoto y retorna el puerto local."""
    global _tunnel
    if _tunnel is not None:
        return _tunnel.local_bind_port

    ssh_host = os.environ.get('SSH_HOST')
    if not ssh_host:
        return None

    host_key = _cargar_ssh_host_key(ssh_host)
    if host_key is None:
        mensaje = (
            f"SSH_HOST_KEY no esta configurada. Sin ella el tunel acepta "
            f"cualquier clave de host de '{ssh_host}' (riesgo de MITM). "
            f"Obtenla con: ssh-keyscan -t ed25519 {ssh_host}  y configura "
            f"SSH_HOST_KEY='ssh-ed25519 AAAA...' en el entorno."
        )
        if config_name == 'production':
            raise RuntimeError(mensaje)
        print(f"[tunel SSH] ADVERTENCIA: {mensaje}")

    _tunnel = SSHTunnelForwarder(
        (ssh_host, int(os.environ.get('SSH_PORT', '22'))),
        ssh_username=os.environ.get('SSH_USER', 'root'),
        ssh_pkey=os.environ.get('SSH_KEY'),
        ssh_host_key=host_key,
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
    user = os.environ.get('DB_USER', 'postgres')
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
    # Evita reutilizar conexiones muertas tras un timeout del tunel SSH.
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 1800,
    }


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
