from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, cast, Date

db = SQLAlchemy()


def expr_fecha(col):
    """Extrae la fecha (sin hora) de una columna DateTime, compatible con
    SQLite (func.date) y PostgreSQL (CAST ... AS DATE). HU-56."""
    try:
        es_sqlite = db.engine.url.drivername.startswith('sqlite')
    except Exception:
        es_sqlite = False
    if es_sqlite:
        return func.date(col)
    return cast(col, Date)
