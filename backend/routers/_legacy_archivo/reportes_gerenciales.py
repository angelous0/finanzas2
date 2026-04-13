from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from typing import Optional
from datetime import date, datetime
from database import get_pool
from dependencies import get_empresa_id
import csv
import io

router = APIRouter(prefix="/reportes")


def make_csv(rows: list[dict], columns: list[tuple]) -> StreamingResponse:
    """Generate a CSV StreamingResponse from rows and column definitions [(key, header)]."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([h for _, h in columns])
    for row in rows:
        writer.writerow([row.get(k, '') for k, _ in columns])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=reporte.csv"}
    )


@router.get("/exportar/cxc")
async def exportar_cxc(
    estado: Optional[str] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        conditions = ["cxc.empresa_id = $1"]
        params = [empresa_id]
        idx = 2
        if estado:
            conditions.append(f"cxc.estado = ${idx}")
            params.append(estado)
        rows = await conn.fetch(f"""
            SELECT cxc.id, COALESCE(t.nombre, 'Sin Cliente') as cliente,
                   cxc.monto_original, cxc.saldo_pendiente, cxc.estado,
                   cxc.fecha_vencimiento, cxc.tipo_origen, cxc.documento_referencia,
                   COALESCE(m.nombre, '') as marca,
                   CASE WHEN cxc.fecha_vencimiento < CURRENT_DATE AND cxc.estado NOT IN ('cobrada','anulada')
                        THEN CURRENT_DATE - cxc.fecha_vencimiento ELSE 0 END as dias_atraso
            FROM cont_cxc cxc
            LEFT JOIN cont_tercero t ON cxc.cliente_id = t.id
            LEFT JOIN cont_marca m ON cxc.marca_id = m.id
            WHERE {' AND '.join(conditions)}
            ORDER BY cxc.fecha_vencimiento ASC NULLS LAST
        """, *params)
        data = [dict(r) for r in rows]
        for d in data:
            if d.get('fecha_vencimiento'):
                d['fecha_vencimiento'] = d['fecha_vencimiento'].isoformat()
        cols = [
            ('id', 'ID'), ('cliente', 'Cliente'), ('monto_original', 'Monto Original'),
            ('saldo_pendiente', 'Saldo Pendiente'), ('estado', 'Estado'),
            ('fecha_vencimiento', 'Vencimiento'), ('dias_atraso', 'Dias Atraso'),
            ('tipo_origen', 'Tipo Origen'), ('documento_referencia', 'Doc. Referencia'), ('marca', 'Marca')
        ]
        resp = make_csv(data, cols)
        resp.headers["Content-Disposition"] = "attachment; filename=cxc_reporte.csv"
        return resp


@router.get("/exportar/cxp")
async def exportar_cxp(
    estado: Optional[str] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        conditions = ["cxp.empresa_id = $1"]
        params = [empresa_id]
        idx = 2
        if estado:
            conditions.append(f"cxp.estado = ${idx}::finanzas2.estado_factura")
            params.append(estado)
        rows = await conn.fetch(f"""
            SELECT cxp.id, COALESCE(t.nombre, 'Sin Proveedor') as proveedor,
                   cxp.monto_original, cxp.saldo_pendiente, cxp.estado::text as estado,
                   cxp.fecha_vencimiento, cxp.tipo_origen, cxp.documento_referencia,
                   COALESCE(m.nombre, '') as marca
            FROM cont_cxp cxp
            LEFT JOIN cont_tercero t ON cxp.proveedor_id = t.id
            LEFT JOIN cont_marca m ON cxp.marca_id = m.id
            WHERE {' AND '.join(conditions)}
            ORDER BY cxp.fecha_vencimiento ASC NULLS LAST
        """, *params)
        data = [dict(r) for r in rows]
        for d in data:
            if d.get('fecha_vencimiento'):
                d['fecha_vencimiento'] = d['fecha_vencimiento'].isoformat()
        cols = [
            ('id', 'ID'), ('proveedor', 'Proveedor'), ('monto_original', 'Monto Original'),
            ('saldo_pendiente', 'Saldo Pendiente'), ('estado', 'Estado'),
            ('fecha_vencimiento', 'Vencimiento'), ('tipo_origen', 'Tipo Origen'),
            ('documento_referencia', 'Doc. Referencia'), ('marca', 'Marca')
        ]
        resp = make_csv(data, cols)
        resp.headers["Content-Disposition"] = "attachment; filename=cxp_reporte.csv"
        return resp


@router.get("/exportar/flujo-caja")
async def exportar_flujo_caja(
    fecha_desde: date = Query(...),
    fecha_hasta: date = Query(...),
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        ingresos = await conn.fetch("""
            SELECT pa.created_at::date as fecha, COALESCE(SUM(pa.monto_aplicado), 0) as ingreso_ventas
            FROM cont_pago_aplicacion pa
            WHERE pa.empresa_id=$1 AND pa.created_at::date BETWEEN $2 AND $3
            GROUP BY fecha ORDER BY fecha
        """, empresa_id, fecha_desde, fecha_hasta)

        egresos = await conn.fetch("""
            SELECT fecha, COALESCE(SUM(monto_total), 0) as egreso_gastos
            FROM cont_pago WHERE empresa_id=$1 AND tipo='egreso' AND fecha BETWEEN $2 AND $3
            GROUP BY fecha ORDER BY fecha
        """, empresa_id, fecha_desde, fecha_hasta)

        dates = {}
        for r in ingresos:
            d = r['fecha'].isoformat()
            dates.setdefault(d, {'fecha': d, 'ingresos': 0, 'egresos': 0})
            dates[d]['ingresos'] = float(r['ingreso_ventas'])
        for r in egresos:
            d = r['fecha'].isoformat()
            dates.setdefault(d, {'fecha': d, 'ingresos': 0, 'egresos': 0})
            dates[d]['egresos'] = float(r['egreso_gastos'])

        data = []
        saldo = 0
        for d in sorted(dates.keys()):
            row = dates[d]
            neto = row['ingresos'] - row['egresos']
            saldo += neto
            row['flujo_neto'] = neto
            row['saldo_acumulado'] = saldo
            data.append(row)

        cols = [
            ('fecha', 'Fecha'), ('ingresos', 'Ingresos'), ('egresos', 'Egresos'),
            ('flujo_neto', 'Flujo Neto'), ('saldo_acumulado', 'Saldo Acumulado')
        ]
        resp = make_csv(data, cols)
        resp.headers["Content-Disposition"] = f"attachment; filename=flujo_caja_{fecha_desde}_{fecha_hasta}.csv"
        return resp


@router.get("/exportar/rentabilidad")
async def exportar_rentabilidad(
    fecha_desde: date = Query(...),
    fecha_hasta: date = Query(...),
    dimension: str = Query("marca"),
    empresa_id: int = Depends(get_empresa_id),
):
    # Reuse the rentabilidad endpoint logic
    from routers.finanzas_gerencial import rentabilidad as rent_fn
    # We need to call the function directly - simplified approach using same pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        dim_config = {
            "marca": {"join_table": "cont_marca", "join_col": "marca_id", "name_col": "nombre"},
            "proyecto": {"join_table": "cont_proyecto", "join_col": "proyecto_id", "name_col": "nombre"},
            "linea_negocio": {"join_table": "cont_linea_negocio", "join_col": "linea_negocio_id", "name_col": "nombre"},
        }
        cfg = dim_config.get(dimension, dim_config["marca"])

        from services.linea_mapping import get_linea_negocio_map, resolve_linea
        ln_map = await get_linea_negocio_map(conn, empresa_id)

        if dimension == 'linea_negocio':
            raw = await conn.fetch("""
                SELECT l.odoo_linea_negocio_id as odoo_ln_id,
                       COALESCE(SUM(l.price_subtotal), 0) as ingreso
                FROM cont_venta_pos_linea l
                JOIN cont_venta_pos v ON l.venta_pos_id = v.id
                JOIN cont_venta_pos_estado e ON e.odoo_order_id = v.odoo_id AND e.empresa_id=$1
                WHERE e.estado_local='confirmada' AND v.date_order BETWEEN $2 AND $3
                GROUP BY l.odoo_linea_negocio_id
            """, empresa_id,
                datetime.combine(fecha_desde, datetime.min.time()),
                datetime.combine(fecha_hasta, datetime.max.time()))
            ingresos_rows = []
            agg = {}
            for r in raw:
                mapped = resolve_linea(ln_map, r['odoo_ln_id'])
                agg[mapped['nombre']] = agg.get(mapped['nombre'], 0) + float(r['ingreso'])
            ingresos_rows = [{"dim": k, "ingreso": v} for k, v in agg.items()]
        else:
            ingresos_rows = await conn.fetch(f"""
                SELECT COALESCE(m.{cfg['name_col']}, 'Sin Asignar') as dim,
                       COALESCE(SUM(l.price_subtotal), 0) as ingreso
                FROM cont_venta_pos_linea l
                JOIN cont_venta_pos v ON l.venta_pos_id = v.id
                JOIN cont_venta_pos_estado e ON e.odoo_order_id = v.odoo_id AND e.empresa_id=$1
                LEFT JOIN {cfg['join_table']} m ON m.nombre = l.marca
                WHERE e.estado_local='confirmada' AND v.date_order BETWEEN $2 AND $3
                GROUP BY dim
            """, empresa_id,
                datetime.combine(fecha_desde, datetime.min.time()),
                datetime.combine(fecha_hasta, datetime.max.time()))

        gastos_rows = await conn.fetch(f"""
            SELECT COALESCE(m.{cfg['name_col']}, 'Sin Asignar') as dim,
                   COALESCE(SUM(gl.importe), 0) as gasto
            FROM cont_gasto g JOIN cont_gasto_linea gl ON g.id=gl.gasto_id
            LEFT JOIN {cfg['join_table']} m ON g.{cfg['join_col']}=m.id
            WHERE g.empresa_id=$1 AND g.fecha BETWEEN $2 AND $3
            GROUP BY dim
        """, empresa_id, fecha_desde, fecha_hasta)

        merged = {}
        for r in ingresos_rows:
            merged.setdefault(r['dim'], {'dimension': r['dim'], 'ingreso': 0, 'gasto': 0})
            merged[r['dim']]['ingreso'] += float(r['ingreso'])
        for r in gastos_rows:
            merged.setdefault(r['dim'], {'dimension': r['dim'], 'ingreso': 0, 'gasto': 0})
            merged[r['dim']]['gasto'] += float(r['gasto'])

        data = []
        for v in merged.values():
            v['utilidad'] = v['ingreso'] - v['gasto']
            v['margen_pct'] = round((v['utilidad'] / v['ingreso'] * 100) if v['ingreso'] > 0 else 0, 1)
            data.append(v)

        cols = [
            ('dimension', dimension.title()), ('ingreso', 'Ingreso'), ('gasto', 'Gasto'),
            ('utilidad', 'Utilidad'), ('margen_pct', 'Margen %')
        ]
        resp = make_csv(data, cols)
        resp.headers["Content-Disposition"] = f"attachment; filename=rentabilidad_{dimension}_{fecha_desde}_{fecha_hasta}.csv"
        return resp


@router.get("/exportar/gastos")
async def exportar_gastos(
    fecha_desde: date = Query(...),
    fecha_hasta: date = Query(...),
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        rows = await conn.fetch("""
            SELECT g.id, g.fecha, g.numero_documento, COALESCE(g.notas, '') as descripcion,
                   COALESCE(t.nombre, g.beneficiario_nombre, '') as proveedor,
                   COALESCE(c.nombre, '') as categoria,
                   g.subtotal, g.igv, g.total,
                   COALESCE(m.nombre, '') as marca,
                   COALESCE(cc.nombre, '') as centro_costo
            FROM cont_gasto g
            LEFT JOIN cont_tercero t ON g.proveedor_id = t.id
            LEFT JOIN cont_gasto_linea gl ON g.id = gl.gasto_id
            LEFT JOIN cont_categoria c ON gl.categoria_id = c.id
            LEFT JOIN cont_marca m ON g.marca_id = m.id
            LEFT JOIN cont_centro_costo cc ON g.centro_costo_id = cc.id
            WHERE g.empresa_id = $1 AND g.fecha BETWEEN $2 AND $3
            GROUP BY g.id, g.fecha, g.numero_documento, g.notas, t.nombre, g.beneficiario_nombre, c.nombre, g.subtotal, g.igv, g.total, m.nombre, cc.nombre
            ORDER BY g.fecha DESC
        """, empresa_id, fecha_desde, fecha_hasta)
        data = []
        for r in rows:
            d = dict(r)
            d['fecha'] = d['fecha'].isoformat() if d.get('fecha') else ''
            data.append(d)

        cols = [
            ('id', 'ID'), ('fecha', 'Fecha'), ('numero_documento', 'Nro Doc'),
            ('descripcion', 'Descripcion'), ('proveedor', 'Proveedor'),
            ('categoria', 'Categoria'), ('subtotal', 'Subtotal'),
            ('igv', 'IGV'), ('total', 'Total'), ('marca', 'Marca'), ('centro_costo', 'Centro Costo')
        ]
        resp = make_csv(data, cols)
        resp.headers["Content-Disposition"] = f"attachment; filename=gastos_{fecha_desde}_{fecha_hasta}.csv"
        return resp


@router.get("/exportar/tesoreria")
async def exportar_tesoreria(
    fecha_desde: date = Query(...),
    fecha_hasta: date = Query(...),
    tipo: Optional[str] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    """Export treasury movements to CSV."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        conditions = ["mt.empresa_id = $1", "mt.fecha BETWEEN $2 AND $3"]
        params = [empresa_id, fecha_desde, fecha_hasta]
        if tipo:
            conditions.append("mt.tipo = $4")
            params.append(tipo)
        where = ' AND '.join(conditions)

        rows = await conn.fetch(f"""
            SELECT mt.id, mt.fecha, mt.tipo, mt.monto, mt.origen_tipo, mt.concepto,
                   mt.forma_pago, mt.referencia, mt.notas,
                   cf.nombre as cuenta, m.nombre as marca,
                   ln.nombre as linea_negocio, cc.nombre as centro_costo,
                   p.nombre as proyecto
            FROM cont_movimiento_tesoreria mt
            LEFT JOIN cont_cuenta_financiera cf ON mt.cuenta_financiera_id = cf.id
            LEFT JOIN cont_marca m ON mt.marca_id = m.id
            LEFT JOIN cont_linea_negocio ln ON mt.linea_negocio_id = ln.id
            LEFT JOIN cont_centro_costo cc ON mt.centro_costo_id = cc.id
            LEFT JOIN cont_proyecto p ON mt.proyecto_id = p.id
            WHERE {where}
            ORDER BY mt.fecha DESC
        """, *params)

        data = []
        for r in rows:
            d = dict(r)
            d['fecha'] = d['fecha'].isoformat() if d.get('fecha') else ''
            data.append(d)

        cols = [
            ('id', 'ID'), ('fecha', 'Fecha'), ('tipo', 'Tipo'), ('monto', 'Monto'),
            ('origen_tipo', 'Origen'), ('concepto', 'Concepto'), ('cuenta', 'Cuenta'),
            ('forma_pago', 'Forma Pago'), ('referencia', 'Referencia'),
            ('marca', 'Marca'), ('linea_negocio', 'Linea Negocio'),
            ('centro_costo', 'Centro Costo'), ('proyecto', 'Proyecto'), ('notas', 'Notas')
        ]
        resp = make_csv(data, cols)
        resp.headers["Content-Disposition"] = f"attachment; filename=tesoreria_{fecha_desde}_{fecha_hasta}.csv"
        return resp



@router.get("/resumen-ejecutivo")
async def resumen_ejecutivo(empresa_id: int = Depends(get_empresa_id)):
    """CFO Executive Summary - all key KPIs in one call."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        # Treasury
        treasury = await conn.fetchrow("""
            SELECT
                COALESCE(SUM(CASE WHEN tipo='caja' THEN saldo_actual ELSE 0 END), 0) as caja,
                COALESCE(SUM(CASE WHEN tipo='banco' THEN saldo_actual ELSE 0 END), 0) as banco,
                COALESCE(SUM(saldo_actual), 0) as total
            FROM cont_cuenta_financiera WHERE empresa_id=$1 AND activo=TRUE
        """, empresa_id)

        # CxC/CxP totals
        cxc = await conn.fetchrow("""
            SELECT COUNT(*) as cnt,
                   COALESCE(SUM(saldo_pendiente), 0) as total,
                   COALESCE(SUM(saldo_pendiente) FILTER(WHERE fecha_vencimiento < CURRENT_DATE), 0) as vencido
            FROM cont_cxc WHERE empresa_id=$1 AND estado NOT IN ('cobrada','anulada')
        """, empresa_id)

        cxp = await conn.fetchrow("""
            SELECT COUNT(*) as cnt,
                   COALESCE(SUM(saldo_pendiente), 0) as total,
                   COALESCE(SUM(saldo_pendiente) FILTER(WHERE fecha_vencimiento < CURRENT_DATE), 0) as vencido
            FROM cont_cxp WHERE empresa_id=$1 AND estado NOT IN ('pagado','anulada')
        """, empresa_id)

        # Month-to-date sales (desde tablas locales)
        today = date.today()
        first_of_month = today.replace(day=1)
        ventas_mtd = await conn.fetchrow("""
            SELECT COUNT(*) as cnt,
                   COALESCE(SUM(v.amount_total), 0) as total
            FROM cont_venta_pos v
            JOIN cont_venta_pos_estado e ON e.odoo_order_id = v.odoo_id AND e.empresa_id=$1
            WHERE e.estado_local = 'confirmada'
              AND v.date_order >= $2
        """, empresa_id, datetime.combine(first_of_month, datetime.min.time()))

        # Month-to-date gastos
        gastos_mtd = await conn.fetchrow("""
            SELECT COALESCE(SUM(total), 0) as total
            FROM cont_gasto WHERE empresa_id=$1 AND fecha >= $2
        """, empresa_id, first_of_month)

        # Pending POS sales
        pendientes = await conn.fetchrow("""
            SELECT COUNT(*) as cnt
            FROM cont_venta_pos_estado
            WHERE empresa_id=$1 AND COALESCE(estado_local, 'pendiente') = 'pendiente'
        """, empresa_id)

        # Treasury movements MTD (real cash flow)
        tesoreria_mtd = await conn.fetchrow("""
            SELECT
                COALESCE(SUM(monto) FILTER (WHERE tipo = 'ingreso'), 0) as ingresos,
                COALESCE(SUM(monto) FILTER (WHERE tipo = 'egreso'), 0) as egresos
            FROM cont_movimiento_tesoreria
            WHERE empresa_id = $1 AND fecha >= $2
        """, empresa_id, first_of_month)

        return {
            "fecha": today.isoformat(),
            "tesoreria": {
                "caja": float(treasury['caja']),
                "banco": float(treasury['banco']),
                "total": float(treasury['total']),
            },
            "flujo_caja_mtd": {
                "ingresos_reales": float(tesoreria_mtd['ingresos']),
                "egresos_reales": float(tesoreria_mtd['egresos']),
                "flujo_neto": float(tesoreria_mtd['ingresos']) - float(tesoreria_mtd['egresos']),
            },
            "cxc": {
                "documentos": int(cxc['cnt']),
                "total": float(cxc['total']),
                "vencido": float(cxc['vencido']),
            },
            "cxp": {
                "documentos": int(cxp['cnt']),
                "total": float(cxp['total']),
                "vencido": float(cxp['vencido']),
            },
            "ventas_mtd": {
                "cantidad": int(ventas_mtd['cnt']),
                "total": float(ventas_mtd['total']),
            },
            "gastos_mtd": float(gastos_mtd['total']),
            "utilidad_mtd": float(ventas_mtd['total']) - float(gastos_mtd['total']),
            "pendientes_confirmar": int(pendientes['cnt']),
            "liquidez_neta": float(treasury['total']) + float(cxc['total']) - float(cxp['total']),
        }
