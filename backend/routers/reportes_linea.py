"""Reportes por Línea de Negocio — Control de dinero simple."""
from fastapi import APIRouter, Depends
from datetime import date
from database import get_pool
from dependencies import get_empresa_id

router = APIRouter(prefix="/reportes", tags=["Reportes Linea"])


def _default_range(fd, fh):
    return fd or date.today().replace(day=1), fh or date.today()


@router.get("/ventas-por-linea")
async def ventas_por_linea(
    empresa_id: int = Depends(get_empresa_id),
    fecha_desde: date = None, fecha_hasta: date = None,
):
    """Ventas confirmadas + crédito agrupadas por línea de negocio."""
    fd, fh = _default_range(fecha_desde, fecha_hasta)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        rows = await conn.fetch("""
            SELECT
                COALESCE(ln.id, sc.id) as linea_id,
                COALESCE(ln.nombre, 'SIN CLASIFICAR') as linea,
                COUNT(DISTINCT v.odoo_id) as tickets,
                COALESCE(SUM(l.price_subtotal_incl), 0) as ventas
            FROM cont_venta_pos_linea l
            JOIN cont_venta_pos v ON l.venta_pos_id = v.id
            LEFT JOIN cont_venta_pos_estado e
                ON e.odoo_order_id = v.odoo_id AND e.empresa_id = v.empresa_id
            LEFT JOIN cont_linea_negocio ln
                ON ln.odoo_linea_negocio_id = l.odoo_linea_negocio_id
                AND ln.empresa_id = v.empresa_id
            LEFT JOIN cont_linea_negocio sc
                ON sc.nombre = 'SIN CLASIFICAR' AND sc.empresa_id = v.empresa_id
            WHERE v.empresa_id = $1
              AND v.date_order::date BETWEEN $2 AND $3
              AND COALESCE(e.estado_local, 'pendiente') IN ('confirmada', 'credito')
            GROUP BY linea_id, linea
            ORDER BY ventas DESC
        """, empresa_id, fd, fh)

        result = []
        total_ventas = 0
        total_tickets = 0
        for r in rows:
            v = float(r['ventas'])
            t = int(r['tickets'])
            total_ventas += v
            total_tickets += t
            result.append({
                "linea_id": r['linea_id'],
                "linea": r['linea'],
                "ventas": v,
                "tickets": t,
                "ticket_promedio": round(v / t, 2) if t > 0 else 0,
            })
        return {
            "data": result,
            "totales": {
                "ventas": total_ventas,
                "tickets": total_tickets,
                "ticket_promedio": round(total_ventas / total_tickets, 2) if total_tickets > 0 else 0,
            }
        }


@router.get("/cobranza-por-linea")
async def cobranza_por_linea(
    empresa_id: int = Depends(get_empresa_id),
    fecha_desde: date = None, fecha_hasta: date = None,
):
    """Vendido vs cobrado vs pendiente por línea de negocio."""
    fd, fh = _default_range(fecha_desde, fecha_hasta)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        # Vendido por línea (from POS lines)
        vendido = await conn.fetch("""
            SELECT
                COALESCE(ln.id, sc.id) as linea_id,
                COALESCE(ln.nombre, 'SIN CLASIFICAR') as linea,
                COALESCE(SUM(l.price_subtotal_incl), 0) as vendido
            FROM cont_venta_pos_linea l
            JOIN cont_venta_pos v ON l.venta_pos_id = v.id
            LEFT JOIN cont_venta_pos_estado e
                ON e.odoo_order_id = v.odoo_id AND e.empresa_id = v.empresa_id
            LEFT JOIN cont_linea_negocio ln
                ON ln.odoo_linea_negocio_id = l.odoo_linea_negocio_id
                AND ln.empresa_id = v.empresa_id
            LEFT JOIN cont_linea_negocio sc
                ON sc.nombre = 'SIN CLASIFICAR' AND sc.empresa_id = v.empresa_id
            WHERE v.empresa_id = $1
              AND v.date_order::date BETWEEN $2 AND $3
              AND COALESCE(e.estado_local, 'pendiente') IN ('confirmada', 'credito')
            GROUP BY linea_id, linea
        """, empresa_id, fd, fh)

        # Cobrado por línea (from analytical distributions - cash collected)
        cobrado = await conn.fetch("""
            SELECT d.linea_negocio_id as linea_id,
                   COALESCE(SUM(d.monto), 0) as cobrado
            FROM cont_distribucion_analitica d
            WHERE d.empresa_id = $1 AND d.fecha BETWEEN $2 AND $3
              AND d.origen_tipo = 'cobranza_cxc'
              AND d.linea_negocio_id IS NOT NULL
            GROUP BY d.linea_negocio_id
        """, empresa_id, fd, fh)

        # Also direct confirm cobros
        cobrado_confirm = await conn.fetch("""
            SELECT d.linea_negocio_id as linea_id,
                   COALESCE(SUM(d.monto), 0) as cobrado
            FROM cont_distribucion_analitica d
            WHERE d.empresa_id = $1 AND d.fecha BETWEEN $2 AND $3
              AND d.origen_tipo = 'venta_pos_confirmada'
              AND d.linea_negocio_id IS NOT NULL
            GROUP BY d.linea_negocio_id
        """, empresa_id, fd, fh)

        cobrado_map = {}
        for r in cobrado:
            cobrado_map[r['linea_id']] = float(r['cobrado'])
        for r in cobrado_confirm:
            lid = r['linea_id']
            cobrado_map[lid] = cobrado_map.get(lid, 0) + float(r['cobrado'])

        result = []
        totales = {"vendido": 0, "cobrado": 0, "pendiente": 0}
        for r in vendido:
            v = float(r['vendido'])
            lid = r['linea_id']
            c = cobrado_map.get(lid, 0)
            p = max(v - c, 0)
            pct = round((c / v) * 100, 1) if v > 0 else 0
            totales["vendido"] += v
            totales["cobrado"] += c
            totales["pendiente"] += p
            result.append({
                "linea_id": lid,
                "linea": r['linea'],
                "vendido": v,
                "cobrado": c,
                "pendiente": p,
                "pct_cobrado": pct,
            })
        result.sort(key=lambda x: x['vendido'], reverse=True)
        totales["pct_cobrado"] = round((totales["cobrado"] / totales["vendido"]) * 100, 1) if totales["vendido"] > 0 else 0
        return {"data": result, "totales": totales}


@router.get("/cruce-linea-marca")
async def cruce_linea_marca(
    empresa_id: int = Depends(get_empresa_id),
    fecha_desde: date = None, fecha_hasta: date = None,
):
    """Desglose de ventas por línea de negocio y marca."""
    fd, fh = _default_range(fecha_desde, fecha_hasta)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        rows = await conn.fetch("""
            SELECT
                COALESCE(ln.nombre, 'SIN CLASIFICAR') as linea,
                COALESCE(l.marca, 'Sin Marca') as marca,
                COUNT(DISTINCT v.odoo_id) as tickets,
                COALESCE(SUM(l.price_subtotal_incl), 0) as ventas
            FROM cont_venta_pos_linea l
            JOIN cont_venta_pos v ON l.venta_pos_id = v.id
            LEFT JOIN cont_venta_pos_estado e
                ON e.odoo_order_id = v.odoo_id AND e.empresa_id = v.empresa_id
            LEFT JOIN cont_linea_negocio ln
                ON ln.odoo_linea_negocio_id = l.odoo_linea_negocio_id
                AND ln.empresa_id = v.empresa_id
            WHERE v.empresa_id = $1
              AND v.date_order::date BETWEEN $2 AND $3
              AND COALESCE(e.estado_local, 'pendiente') IN ('confirmada', 'credito')
            GROUP BY linea, marca
            ORDER BY linea, ventas DESC
        """, empresa_id, fd, fh)

        # Group by linea for structured output
        lineas = {}
        for r in rows:
            ln = r['linea']
            if ln not in lineas:
                lineas[ln] = {"linea": ln, "total_ventas": 0, "marcas": []}
            v = float(r['ventas'])
            lineas[ln]["total_ventas"] += v
            lineas[ln]["marcas"].append({
                "marca": r['marca'],
                "ventas": v,
                "tickets": int(r['tickets']),
            })

        result = sorted(lineas.values(), key=lambda x: x['total_ventas'], reverse=True)
        # Add percentage
        for ln in result:
            for m in ln["marcas"]:
                m["pct"] = round((m["ventas"] / ln["total_ventas"]) * 100, 1) if ln["total_ventas"] > 0 else 0
        return result


@router.get("/gastos-directos-por-linea")
async def gastos_directos_por_linea(
    empresa_id: int = Depends(get_empresa_id),
    fecha_desde: date = None, fecha_hasta: date = None,
):
    """Gastos directos + facturas proveedor agrupados por línea."""
    fd, fh = _default_range(fecha_desde, fecha_hasta)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        # Gastos directos por línea (from gasto header)
        gastos = await conn.fetch("""
            SELECT COALESCE(ln.nombre, 'No Asignado') as linea,
                   ln.id as linea_id,
                   COALESCE(SUM(g.total), 0) as total_gastos,
                   COUNT(*) as cantidad
            FROM cont_gasto g
            LEFT JOIN cont_linea_negocio ln ON g.linea_negocio_id = ln.id
            WHERE g.empresa_id = $1 AND g.fecha BETWEEN $2 AND $3
            GROUP BY ln.id, ln.nombre
            ORDER BY total_gastos DESC
        """, empresa_id, fd, fh)

        # Facturas proveedor por línea (from detalle lines)
        facturas = await conn.fetch("""
            SELECT COALESCE(ln.nombre, 'No Asignado') as linea,
                   ln.id as linea_id,
                   COALESCE(SUM(fpl.importe), 0) as total_facturas
            FROM cont_factura_proveedor_linea fpl
            JOIN cont_factura_proveedor fp ON fpl.factura_id = fp.id
            LEFT JOIN cont_linea_negocio ln ON fpl.linea_negocio_id = ln.id
            WHERE fp.empresa_id = $1 AND fp.fecha_factura BETWEEN $2 AND $3
            GROUP BY ln.id, ln.nombre
        """, empresa_id, fd, fh)

        # Merge
        linea_map = {}
        for r in gastos:
            key = r['linea']
            linea_map[key] = {
                "linea": key,
                "linea_id": r['linea_id'],
                "total_gastos": float(r['total_gastos']),
                "cantidad_gastos": int(r['cantidad']),
                "total_facturas": 0,
            }
        for r in facturas:
            key = r['linea']
            if key not in linea_map:
                linea_map[key] = {
                    "linea": key,
                    "linea_id": r['linea_id'],
                    "total_gastos": 0,
                    "cantidad_gastos": 0,
                    "total_facturas": 0,
                }
            linea_map[key]["total_facturas"] = float(r['total_facturas'])

        result = []
        totales = {"total_gastos": 0, "total_facturas": 0, "total_egresos": 0}
        for item in linea_map.values():
            item["total_egresos"] = item["total_gastos"] + item["total_facturas"]
            totales["total_gastos"] += item["total_gastos"]
            totales["total_facturas"] += item["total_facturas"]
            totales["total_egresos"] += item["total_egresos"]
            result.append(item)
        result.sort(key=lambda x: x['total_egresos'], reverse=True)
        return {"data": result, "totales": totales}


@router.get("/dinero-por-linea")
async def dinero_por_linea(
    empresa_id: int = Depends(get_empresa_id),
    fecha_desde: date = None, fecha_hasta: date = None,
):
    """Reporte consolidado: ventas - cobranzas - CxC - gastos - saldo neto."""
    fd, fh = _default_range(fecha_desde, fecha_hasta)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        # All active lineas
        all_lineas = await conn.fetch(
            "SELECT id, nombre FROM cont_linea_negocio WHERE empresa_id = $1 AND activo = TRUE",
            empresa_id)

        # Ventas confirmadas por línea
        ventas = await conn.fetch("""
            SELECT
                COALESCE(ln.id, sc.id) as linea_id,
                COALESCE(SUM(l.price_subtotal_incl), 0) as ventas
            FROM cont_venta_pos_linea l
            JOIN cont_venta_pos v ON l.venta_pos_id = v.id
            LEFT JOIN cont_venta_pos_estado e
                ON e.odoo_order_id = v.odoo_id AND e.empresa_id = v.empresa_id
            LEFT JOIN cont_linea_negocio ln
                ON ln.odoo_linea_negocio_id = l.odoo_linea_negocio_id
                AND ln.empresa_id = v.empresa_id
            LEFT JOIN cont_linea_negocio sc
                ON sc.nombre = 'SIN CLASIFICAR' AND sc.empresa_id = v.empresa_id
            WHERE v.empresa_id = $1
              AND v.date_order::date BETWEEN $2 AND $3
              AND COALESCE(e.estado_local, 'pendiente') IN ('confirmada', 'credito')
            GROUP BY linea_id
        """, empresa_id, fd, fh)

        # Cobranzas reales
        cobranzas = await conn.fetch("""
            SELECT d.linea_negocio_id as linea_id,
                   COALESCE(SUM(d.monto), 0) as cobrado
            FROM cont_distribucion_analitica d
            WHERE d.empresa_id = $1 AND d.fecha BETWEEN $2 AND $3
              AND d.origen_tipo IN ('cobranza_cxc', 'venta_pos_confirmada')
              AND d.linea_negocio_id IS NOT NULL
            GROUP BY d.linea_negocio_id
        """, empresa_id, fd, fh)

        # CxC pendientes por línea
        cxc_pend = await conn.fetch("""
            SELECT ln.id as linea_id,
                   COALESCE(SUM(c.saldo_pendiente), 0) as pendiente
            FROM cont_cxc c
            LEFT JOIN cont_linea_negocio ln ON c.linea_negocio_id = ln.id
            WHERE c.empresa_id = $1 AND c.estado NOT IN ('cobrada', 'anulada')
            GROUP BY ln.id
        """, empresa_id)

        # Gastos directos
        gastos = await conn.fetch("""
            SELECT g.linea_negocio_id as linea_id,
                   COALESCE(SUM(g.total), 0) as gastos
            FROM cont_gasto g
            WHERE g.empresa_id = $1 AND g.fecha BETWEEN $2 AND $3
              AND g.linea_negocio_id IS NOT NULL
            GROUP BY g.linea_negocio_id
        """, empresa_id, fd, fh)

        # Facturas proveedor por línea
        fact_prov = await conn.fetch("""
            SELECT fpl.linea_negocio_id as linea_id,
                   COALESCE(SUM(fpl.importe), 0) as facturas
            FROM cont_factura_proveedor_linea fpl
            JOIN cont_factura_proveedor fp ON fpl.factura_id = fp.id
            WHERE fp.empresa_id = $1 AND fp.fecha_factura BETWEEN $2 AND $3
              AND fpl.linea_negocio_id IS NOT NULL
            GROUP BY fpl.linea_negocio_id
        """, empresa_id, fd, fh)

        # Build maps
        v_map = {r['linea_id']: float(r['ventas']) for r in ventas}
        c_map = {r['linea_id']: float(r['cobrado']) for r in cobranzas}
        p_map = {r['linea_id']: float(r['pendiente']) for r in cxc_pend}
        g_map = {r['linea_id']: float(r['gastos']) for r in gastos}
        f_map = {r['linea_id']: float(r['facturas']) for r in fact_prov}

        result = []
        totales = {"ventas": 0, "cobranzas": 0, "cxc_pendiente": 0, "gastos": 0, "saldo_neto": 0}
        for ln in all_lineas:
            lid = ln['id']
            ven = v_map.get(lid, 0)
            cob = c_map.get(lid, 0)
            pend = p_map.get(lid, 0)
            gas = g_map.get(lid, 0) + f_map.get(lid, 0)
            saldo = cob - gas
            totales["ventas"] += ven
            totales["cobranzas"] += cob
            totales["cxc_pendiente"] += pend
            totales["gastos"] += gas
            totales["saldo_neto"] += saldo
            result.append({
                "linea": ln['nombre'],
                "ventas": ven,
                "cobranzas": cob,
                "cxc_pendiente": pend,
                "gastos": gas,
                "saldo_neto": saldo,
            })
        result.sort(key=lambda x: x['ventas'], reverse=True)
        return {"data": result, "totales": totales}
