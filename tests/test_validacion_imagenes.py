"""
Regresion HU-12: un archivo con extension de imagen pero contenido
invalido (no es realmente una imagen) debe ser rechazado.

Regresion HU-13: una imagen valida pero con dimensiones excesivas debe
ser rechazada (evita decompression bombs).
"""
import os
import io
import tempfile

_DB_DIR = tempfile.mkdtemp(prefix="cafeteria_test_img_")
_DB_PATH = os.path.join(_DB_DIR, "test_cafeteria.db")
os.environ['DATABASE_URL'] = f"sqlite:///{_DB_PATH}"
os.environ.pop('SSH_HOST', None)

from PIL import Image
from werkzeug.datastructures import FileStorage

from blueprints.admin.routes import _es_imagen_valida, MAX_IMAGE_DIMENSION


def _png_bytes(width, height):
    buf = io.BytesIO()
    Image.new('RGB', (width, height), color='red').save(buf, format='PNG')
    buf.seek(0)
    return buf


def test_archivo_con_extension_png_pero_contenido_invalido_es_rechazado():
    fake = FileStorage(stream=io.BytesIO(b'esto no es una imagen, es texto plano'),
                        filename='falso.png', content_type='image/png')
    assert _es_imagen_valida(fake) is False


def test_imagen_real_y_de_tamano_normal_es_aceptada():
    fs = FileStorage(stream=_png_bytes(200, 200), filename='ok.png', content_type='image/png')
    assert _es_imagen_valida(fs) is True


def test_imagen_con_dimensiones_excesivas_es_rechazada():
    fs = FileStorage(stream=_png_bytes(MAX_IMAGE_DIMENSION + 500, 100),
                      filename='enorme.png', content_type='image/png')
    assert _es_imagen_valida(fs) is False
