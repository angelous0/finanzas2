from fastapi import APIRouter, Depends
from datetime import date, datetime
from database import get_pool
from dependencies import get_empresa_id

router = APIRouter(prefix="/reportes", tags=["Reportes"])


@router.get("/ventas-pendientes")
async def reporte_ventas_pendientes(empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        rows = await conn.fetch("""
            SELECT COUNT(*) as cantidad, COALESCE(SUM(v.amount_total), 0) as monto
            FROM cont_venta_pos v
            LEFT JOIN cont_venta_pos_estado e ON e.odoo_order_id = v.odoo_id AND e.empresa_id = v.empresa_id
            WHERE v.empresa_id = $1 AND COALESCE(e.estado_local, 'pendiente') = 'pendiente'
        """, empresa_id)
        return dict(rows[0])


@router.get("/ingresos-por-linea")
async def reporte_ingresos_por_linea(
    empresa_id: int = Depends(get_empresa_id),
    fecha_desde: date = None, fecha_hasta: date = None
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        fd = fecha_desde or date.today().replace(day=1)
        fh = fecha_hasta or date.today()
        rows = await conn.fetch("""
            SELECT ln.id, ln.nombre as linea, COALESCE(SUM(d.monto), 0) as ingresos
            FROM cont_distribucion_analitica d
            JOIN cont_linea_negocio ln ON d.linea_negocio_id = ln.id
            WHERE d.empresa_id = $1 AND d.fecha BETWEEN $2 AND $3
              AND d.origen_tipo = 'venta_pos_ingreso'
            GROUP BY ln.id, ln.nombre
            ORDER BY ingresos DESC
        """, empresa_id, fd, fh)
        return [dict(r) for r in rows]


@router.get("/ingresos-por-marca")
async def reporte_ingresos_por_marca(
    empresa_id: int = Depends(get_empresa_id),
    fecha_desde: date = None, fecha_hasta: date = None
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        fd = fecha_desde or date.today().replace(day=1)
        fh = fecha_hasta or date.today()
        rows = await conn.fetch("""
            SELECT COALESCE(l.marca, 'Sin Marca') as marca,
                   COALESCE(SUM(l.price_subtotal_incl), 0) as ingresos
            FROM cont_venta_pos_linea l
            JOIN cont_venta_pos v ON l.venta_pos_id = v.id
            LEFT JOIN cont_venta_pos_estado e ON e.odoo_order_id = v.odoo_id AND e.empresa_id = v.empresa_id
            WHERE v.empresa_id = $1 AND v.date_order::date BETWEEN $2 AND $3
              AND COALESCE(e.estado_local, 'pendiente') IN ('confirmada', 'credito')
            GROUP BY marca
            ORDER BY ingresos DESC
        """, empresa_id, fd, fh)
        return [dict(r) for r in rows]


@router.get("/cobranzas-por-linea")
async def reporte_cobranzas_por_linea(
    empresa_id: int = Depends(get_empresa_id),
    fecha_desde: date = None, fecha_hasta: date = None
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        fd = fecha_desde or date.today().replace(day=1)
        fh = fecha_hasta or date.today()
        rows = await conn.fetch("""
            SELECT ln.id, ln.nombre as linea, COALESCE(SUM(d.monto), 0) as cobrado
            FROM cont_distribucion_analitica d
            JOIN cont_linea_negocio ln ON d.linea_negocio_id = ln.id
            WHERE d.empresa_id = $1 AND d.fecha BETWEEN $2 AND $3
              AND d.origen_tipo = 'cobranza_cxc'
            GROUP BY ln.id, ln.nombre
            ORDER BY cobrado DESC
        """, empresa_id, fd, fh)
        return [dict(r) for r in rows]


@router.get("/pendiente-cobrar-por-linea")
async def reporte_pendiente_cobrar(empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        rows = await conn.fetch("""
            SELECT ln.nombre as linea, COALESCE(SUM(c.saldo_pendiente), 0) as pendiente
            FROM cont_cxc c
            LEFT JOIN cont_linea_negocio ln ON c.linea_negocio_id = ln.id
            WHERE c.empresa_id = $1 AND c.estado NOT IN ('pagado', 'anulada')
            GROUP BY ln.nombre
            ORDER BY pendiente DESC
        """, empresa_id)
        return [dict(r) for r in rows]


@router.get("/gastos-por-categoria")
async def reporte_gastos_por_categoria(
    empresa_id: int = Depends(get_empresa_id),
    fecha_desde: date = None, fecha_hasta: date = None
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        fd = fecha_desde or date.today().replace(day=1)
        fh = fecha_hasta or date.today()
        rows = await conn.fetch("""
            SELECT COALESCE(cg.nombre, 'Sin Categoría') as categoria,
                   COUNT(*) as cantidad, COALESCE(SUM(g.total), 0) as monto
            FROM cont_gasto g
            LEFT JOIN cont_categoria_gasto cg ON g.categoria_gasto_id = cg.id
            WHERE g.empresa_id = $1 AND g.fecha BETWEEN $2 AND $3
            GROUP BY cg.nombre
            ORDER BY monto DESC
        """, empresa_id, fd, fh)
        return [dict(r) for r in rows]


@router.get("/gastos-por-centro-costo")
async def reporte_gastos_por_centro(
    empresa_id: int = Depends(get_empresa_id),
    fecha_desde: date = None, fecha_hasta: date = None
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        fd = fecha_desde or date.today().replace(day=1)
        fh = fecha_hasta or date.today()
        rows = await conn.fetch("""
            SELECT COALESCE(cc.nombre, 'Sin Centro') as centro_costo,
                   COUNT(*) as cantidad, COALESCE(SUM(g.total), 0) as monto
            FROM cont_gasto g
            LEFT JOIN cont_centro_costo cc ON g.centro_costo_id = cc.id
            WHERE g.empresa_id = $1 AND g.fecha BETWEEN $2 AND $3
            GROUP BY cc.nombre
            ORDER BY monto DESC
        """, empresa_id, fd, fh)
        return [dict(r) for r in rows]


@router.get("/utilidad-por-linea")
async def reporte_utilidad_por_linea(
    empresa_id: int = Depends(get_empresa_id),
    fecha_desde: date = None, fecha_hasta: date = None
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        fd = fecha_desde or date.today().replace(day=1)
        fh = fecha_hasta or date.today()

        todas_lineas = await conn.fetch(
            "SELECT id, nombre FROM cont_linea_negocio WHERE empresa_id = $1 AND activo = TRUE", empresa_id)

        ingresos = await conn.fetch("""
            SELECT d.linea_negocio_id, COALESCE(SUM(d.monto), 0) as ingresos
            FROM cont_distribucion_analitica d
            WHERE d.empresa_id = $1 AND d.fecha BETWEEN $2 AND $3
              AND d.origen_tipo = 'cobranza_cxc'
            GROUP BY d.linea_negocio_id
        """, empresa_id, fd, fh)

        gastos_directos = await conn.fetch("""
            SELECT g.linea_negocio_id, COALESCE(SUM(g.total), 0) as gastos
            FROM cont_gasto g
            WHERE g.empresa_id = $1 AND g.fecha BETWEEN $2 AND $3
              AND g.tipo_asignacion = 'directo' AND g.linea_negocio_id IS NOT NULL
            GROUP BY g.linea_negocio_id
        """, empresa_id, fd, fh)

        gastos_prorrateados = await conn.fetch("""
            SELECT p.linea_negocio_id, COALESCE(SUM(p.monto), 0) as gastos_prorrateo
            FROM cont_prorrateo_gasto p
            JOIN cont_gasto g ON p.gasto_id = g.id
            WHERE g.empresa_id = $1 AND g.fecha BETWEEN $2 AND $3
            GROUP BY p.linea_negocio_id
        """, empresa_id, fd, fh)

        egresos_proveedores = await conn.fetch("""
            SELECT d.linea_negocio_id, COALESCE(SUM(d.monto), 0) as egresos
            FROM cont_distribucion_analitica d
            WHERE d.empresa_id = $1 AND d.fecha BETWEEN $2 AND $3
              AND d.origen_tipo IN ('pago_egreso', 'pago_letra')
            GROUP BY d.linea_negocio_id
        """, empresa_id, fd, fh)

        ing_map = {r['linea_negocio_id']: float(r['ingresos']) for r in ingresos}
        gd_map = {r['linea_negocio_id']: float(r['gastos']) for r in gastos_directos}
        gp_map = {r['linea_negocio_id']: float(r['gastos_prorrateo']) for r in gastos_prorrateados}
        ep_map = {r['linea_negocio_id']: float(r['egresos']) for r in egresos_proveedores}

        result = []
        for ln in todas_lineas:
            lid = ln['id']
            ing = ing_map.get(lid, 0)
            gd = gd_map.get(lid, 0)
            gp = gp_map.get(lid, 0)
            ep = ep_map.get(lid, 0)
            result.append({
                "linea": ln['nombre'],
                "ingresos": ing,
                "egresos_proveedores": ep,
                "gastos_directos": gd,
                "gastos_prorrateados": gp,
                "utilidad_antes": ing - gd - ep,
                "utilidad_despues": ing - gd - gp - ep,
            })
        result.sort(key=lambda x: x['ingresos'], reverse=True)
        return result
