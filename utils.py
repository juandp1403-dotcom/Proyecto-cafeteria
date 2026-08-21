# -*- coding: utf-8 -*-
"""Utilidades centralizadas de fecha/hora para todo el proyecto.

HU-56: TODA la aplicacion (dashboard, reportes, Excel, creacion de ventas,
compras y bajas) debe usar la hora real de Colombia (America/Bogota),
no la hora UTC del servidor.

Las funciones devuelven datetime NAIVE (sin tzinfo) con la hora de pared
de Bogota. Esto es a proposito: las columnas de la BD son TIMESTAMP sin
zona horaria y asi se evita mezclar datetimes aware/naive al comparar.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

TZ_BOGOTA = ZoneInfo('America/Bogota')


def ahora_bogota():
    """Datetime actual en hora de Bogota (naive, hora de pared local)."""
    return datetime.now(TZ_BOGOTA).replace(tzinfo=None)


def hoy_bogota():
    """Fecha actual segun la hora de Bogota."""
    return ahora_bogota().date()
