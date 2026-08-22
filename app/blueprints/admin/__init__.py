from flask import Blueprint

admin_bp = Blueprint('admin_panel', __name__, url_prefix='/admin')

from . import routes     # noqa: F401, E402
from . import productos  # noqa: F401, E402
from . import ventas     # noqa: F401, E402
from . import compras    # noqa: F401, E402
from . import usuarios   # noqa: F401, E402
from . import reportes   # noqa: F401, E402
from . import auditoria  # noqa: F401, E402
