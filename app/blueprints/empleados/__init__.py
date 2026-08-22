from flask import Blueprint

empleados_bp = Blueprint('empleados', __name__, url_prefix='/empleados')

from . import routes  # noqa: F401, E402
