"""Guardia de seguridad para TODA la suite de pruebas. NO ELIMINAR.

Incidente 2026-08: los modulos de prueba hacen os.environ.pop('SSH_HOST')
al importarse, pero config/config.py llama load_dotenv() al importarse
tambien y el .env local trae SSH_HOST -> _abrir_tunel() abria el tunel a
la BD remota y los fixtures con db.drop_all() vaciaron la base de
produccion. Aqui se neutraliza load_dotenv() durante pytest (en CI es
no-op porque no hay .env ni SSH_HOST) y se congela la configuracion
antes de que cualquier test importe la app.
"""
import os

os.environ.pop('SSH_HOST', None)

import dotenv

dotenv.load_dotenv = lambda *a, **k: False

import config.config  # noqa: E402  (debe importar con load_dotenv ya neutralizado)
