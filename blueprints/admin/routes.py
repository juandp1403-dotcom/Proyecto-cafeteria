from flask import render_template
from flask_login import login_required
from datetime import timedelta
from models import db, expr_fecha, Producto, Venta, DetalleVenta
from blueprints.permisos import requiere_ver_pagina
from utils import hoy_bogota
from . import admin_bp


def _ultimos_12_meses(hoy):
    """HU-55: los ultimos 12 meses de calendario terminando en `hoy`,
    con aritmetica real (year*12+month) en vez de aproximar un mes a 30
    dias -- esa aproximacion acumula deriva y llega a saltarse meses
    como febrero. Devuelve [(clave 'YYYY-MM', etiqueta 'Mon YYYY'), ...]."""
    mes_absoluto_actual = hoy.year * 12 + (hoy.month - 1)
    resultado = []
    for i in range(12, 0, -1):
        mes_absoluto = mes_absoluto_actual - (i - 1)
        anio_mes, mes_mes = divmod(mes_absoluto, 12)
        fecha_mes = hoy.replace(year=anio_mes, month=mes_mes + 1, day=1)
        resultado.append((fecha_mes.strftime('%Y-%m'), fecha_mes.strftime('%b %Y')))
    return resultado


# ── Dashboard ────────────────────────────────────────────────────────────────
@admin_bp.route('/')
@login_required
@requiere_ver_pagina('dashboard')
def dashboard():
    from sqlalchemy import func, desc

    hoy = hoy_bogota()
    estados_pagados = ('Pagado/Preparando', 'Preparado', 'Entregado')

    # KPIs — solo pedidos pagados / entregados
    total_ventas = int(db.session.query(func.coalesce(func.sum(Venta.precio), 0)).filter(
        expr_fecha(Venta.fechaventa) == hoy,
        Venta.estado.in_(estados_pagados)
    ).scalar())
    ventas_hoy = int(db.session.query(func.count(Venta.idventa)).filter(
        expr_fecha(Venta.fechaventa) == hoy,
        Venta.estado.in_(estados_pagados)
    ).scalar())

    productos_bajo = Producto.query.filter(Producto.activo == True, Producto.stock < Producto.stock_minimo, Producto.stock > 0).order_by(Producto.stock.asc()).all()  # noqa: E712
    productos_agotados = Producto.query.filter(Producto.activo == True, Producto.stock == 0).all()  # noqa: E712

    # ── Ventas diarias (últimos 7 días) — solo pagados/entregados ──
    desde_dias = hoy - timedelta(days=6)
    rows_diarios = db.session.query(
        expr_fecha(Venta.fechaventa).label('dia'),
        func.coalesce(func.sum(Venta.precio), 0).label('total')
    ).filter(
        expr_fecha(Venta.fechaventa) >= desde_dias,
        Venta.estado.in_(estados_pagados)
    ).group_by('dia').order_by('dia').all()
    mapa_dias = {str(r.dia): int(r.total) for r in rows_diarios}
    ventas_diarias = []
    etiquetas_dias = []
    for i in range(7):
        fecha = desde_dias + timedelta(days=i)
        ventas_diarias.append(mapa_dias.get(str(fecha), 0))
        etiquetas_dias.append(fecha.strftime('%d/%m'))

    # ── Ventas mensuales (últimos 12 meses) — solo pagados/entregados ──
    desde_meses = hoy - timedelta(days=365)
    is_sqlite = db.engine.url.drivername.startswith('sqlite')
    if is_sqlite:
        mes_col = func.strftime('%Y-%m', Venta.fechaventa)
    else:
        mes_col = func.date_trunc('month', Venta.fechaventa)
    rows_mensuales = db.session.query(
        mes_col.label('mes'),
        func.coalesce(func.sum(Venta.precio), 0).label('total')
    ).filter(
        expr_fecha(Venta.fechaventa) >= desde_meses,
        Venta.estado.in_(estados_pagados)
    ).group_by('mes').order_by('mes').all()
    mapa_meses = {}
    for r in rows_mensuales:
        clave = r.mes if isinstance(r.mes, str) else (r.mes.strftime('%Y-%m') if r.mes else '')
        mapa_meses[clave] = int(r.total)
    ventas_mensuales = []
    etiquetas_meses = []
    for clave, etiqueta in _ultimos_12_meses(hoy):
        ventas_mensuales.append(mapa_meses.get(clave, 0))
        etiquetas_meses.append(etiqueta)

    # ── Top 15 productos más vendidos — solo pagados/entregados ──
    rows_top = (
        db.session.query(
            Producto.nombre,
            func.coalesce(func.sum(DetalleVenta.cantidad), 0).label('total_vendido')
        )
        .join(DetalleVenta, DetalleVenta.idproducto == Producto.idproducto)
        .join(Venta, Venta.idventa == DetalleVenta.idventa)
        .filter(
            expr_fecha(Venta.fechaventa) >= hoy - timedelta(days=30),
            Venta.estado.in_(estados_pagados)
        )
        .group_by(Producto.nombre)
        .order_by(desc('total_vendido'))
        .limit(15)
        .all()
    )
    top_15 = [(r.nombre, int(r.total_vendido)) for r in rows_top]

    return render_template('admin/dashboard.html',
                           total_ventas=total_ventas,
                           ventas_hoy=ventas_hoy,
                           productos_bajo=productos_bajo,
                           productos_agotados=productos_agotados,
                           ventas_diarias=ventas_diarias,
                           etiquetas_dias=etiquetas_dias,
                           ventas_mensuales=ventas_mensuales,
                           etiquetas_meses=etiquetas_meses,
                           top_15=top_15)

