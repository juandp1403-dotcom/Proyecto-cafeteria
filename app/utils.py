# -*- coding: utf-8 -*-
"""Fecha/hora de Colombia (America/Bogota) para toda la app. Devuelve
datetime naive a proposito, porque las columnas de la BD son TIMESTAMP
sin zona horaria."""
from datetime import datetime
from zoneinfo import ZoneInfo

TZ_BOGOTA = ZoneInfo('America/Bogota')


def ahora_bogota():
    """Datetime actual en hora de Bogota (naive, hora de pared local)."""
    return datetime.now(TZ_BOGOTA).replace(tzinfo=None)


def hoy_bogota():
    """Fecha actual segun la hora de Bogota."""
    return ahora_bogota().date()
