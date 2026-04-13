"""POS CRUD: Listado de ventas y detalle de líneas."""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from datetime import date, datetime
from database import get_pool
from dependencies import get_empresa_id
from routers.pos_common import get_company_key
import logging
import math

logger = logging.getLogger(__name__)
router = APIRouter()


# =====================
# VENTAS POS — LIST
# =====================
@router.get("/ventas-pos")
async def list_ventas_pos(
    estado: Optional[str] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    search: Optional[str] = None,
    include_cancelled: bool = False,
    page: int = 1,
    page_size: int = 50,
    empresa_id: int = Depends(get_empresa_id),
):
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 200:
        page_size = 50

    pool = await get_pool()
    async with pool.acquire() as conn:
        company_key = await get_company_key(conn, empresa_id)

        if company_key:
            return await _list_from_odoo(conn, empresa_id, company_key,
                                         estado, fecha_desde, fecha_hasta,
                                         search, include_cancelled, page, page_size)
        else:
            return {
                "error_code": "MISSING_ODOO_COMPANY_KEY",
                "message": "No hay mapeo empresa - company_key configurado. Configure el mapeo para poder ver ventas POS desde Odoo.",
                "data": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "total_pages": 0
            }


async def _list_from_odoo(conn, empresa_id, company_key,
                           estado, fecha_desde, fecha_hasta, search, include_cancelled,
                           page, page_size):
    """Read orders from LOCAL cont_venta_pos + estado (desacoplado de Odoo)."""

    # Lazy sync removed - use explicit refresh/sync instead
    conditions = [f"v.empresa_id = {empresa_id}"]

    params = []
    idx = 1

    if not include_cancelled:
        conditions.append("v.is_cancel = FALSE")

    if fecha_desde:
        conditions.append(f"v.date_order >= ${idx}")
        params.append(datetime.combine(fecha_desde, datetime.min.time()))
        idx += 1
    if fecha_hasta:
        conditions.append(f"v.date_order <= ${idx}")
        params.append(datetime.combine(fecha_hasta, datetime.max.time()))
        idx += 1
    if search:
        conditions.append(f"(v.partner_name ILIKE ${idx} OR v.vendedor_name ILIKE ${idx} OR v.tienda_name ILIKE ${idx} OR CAST(v.odoo_id AS TEXT) LIKE ${idx})")
        params.append(f"%{search}%")
        idx += 1

    estado_filter = ""
    if estado:
        if estado == 'pendiente':
            estado_filter = " AND COALESCE(e.estado_local, 'pendiente') = 'pendiente'"
        else:
            estado_filter = f" AND e.estado_local = ${idx}"
            params.append(estado)
            idx += 1

    from_clause = f"""
        FROM finanzas2.cont_venta_pos v
        LEFT JOIN finanzas2.cont_venta_pos_estado e
            ON e.odoo_order_id = v.odoo_id AND e.empresa_id = {empresa_id}
        WHERE {' AND '.join(conditions)}
        {estado_filter}
    """

    count_query = f"SELECT COUNT(*), MAX(v.date_order) {from_clause}"
    row_agg = await conn.fetchrow(count_query, *params)
    total = row_agg[0]
    max_date_order = row_agg[1]

    offset = (page - 1) * page_size

    query = f"""
        SELECT
            v.odoo_id AS odoo_order_id,
            v.date_order,
            v.amount_total,
            v.state,
            v.is_cancel AS is_cancelled,
            v.reserva,
            v.partner_name,
            v.vendedor_id,
            v.vendedor_name,
            v.tienda_name,
            v.quantity_total,
            v.x_pagos,
            v.tipo_comp,
            v.num_comp,
            v.company_name,
            COALESCE(e.estado_local, 'pendiente') AS estado_local,
            e.notas AS estado_notas,
            e.cxc_id,
            COALESCE(
                (SELECT SUM(vp.monto) FROM finanzas2.cont_venta_pos_pago vp
                 WHERE vp.odoo_order_id = v.odoo_id AND vp.empresa_id = {empresa_id}), 0
            ) AS pagos_asignados,
            COALESCE(
                (SELECT COUNT(*) FROM finanzas2.cont_venta_pos_pago vp
                 WHERE vp.odoo_order_id = v.odoo_id AND vp.empresa_id = {empresa_id}), 0
            ) AS num_pagos,
            COALESCE(
                (SELECT SUM(pa.monto_aplicado) FROM finanzas2.cont_pago_aplicacion pa
                 WHERE pa.tipo_documento = 'venta_pos_odoo' AND pa.documento_id = v.odoo_id
                   AND pa.empresa_id = {empresa_id}), 0
            ) AS pagos_oficiales,
            COALESCE(
                (SELECT COUNT(*) FROM finanzas2.cont_pago_aplicacion pa
                 WHERE pa.tipo_documento = 'venta_pos_odoo' AND pa.documento_id = v.odoo_id
                   AND pa.empresa_id = {empresa_id}), 0
            ) AS num_pagos_oficiales,
            COALESCE(
                (SELECT SUM(ab.monto) FROM finanzas2.cont_cxc_abono ab
                 JOIN finanzas2.cont_cxc cxc ON cxc.id = ab.cxc_id
                 WHERE cxc.odoo_order_id = v.odoo_id AND cxc.empresa_id = {empresa_id}), 0
            ) AS pagos_cxc,
            COALESCE(
                (SELECT COUNT(*) FROM finanzas2.cont_cxc_abono ab
                 JOIN finanzas2.cont_cxc cxc ON cxc.id = ab.cxc_id
                 WHERE cxc.odoo_order_id = v.odoo_id AND cxc.empresa_id = {empresa_id}), 0
            ) AS num_pagos_cxc
        {from_clause}
        ORDER BY v.date_order DESC
        LIMIT {page_size} OFFSET {offset}
    """
    rows = await conn.fetch(query, *params)
    result = []
    for r in rows:
        result.append({
            "id": r['odoo_order_id'],
            "odoo_order_id": r['odoo_order_id'],
            "date_order": r['date_order'].isoformat() if r['date_order'] else None,
            "amount_total": float(r['amount_total'] or 0),
            "state": r['state'],
            "is_cancelled": r['is_cancelled'],
            "reserva": r['reserva'],
            "partner_name": r['partner_name'] or '-',
            "vendedor_id": r['vendedor_id'],
            "vendedor_name": r['vendedor_name'] or '-',
            "tienda_name": r['tienda_name'],
            "quantity_total": float(r['quantity_total'] or 0),
            "x_pagos": r['x_pagos'],
            "tipo_comp": r['tipo_comp'],
            "num_comp": r['num_comp'],
            "company_name": r['company_name'],
            "estado_local": r['estado_local'],
            "pagos_asignados": float(r['pagos_asignados']),
            "num_pagos": r['num_pagos'],
            "pagos_oficiales": float(r['pagos_oficiales']),
            "num_pagos_oficiales": r['num_pagos_oficiales'],
            "pagos_cxc": float(r['pagos_cxc']),
            "num_pagos_cxc": r['num_pagos_cxc'],
            "cxc_id": r['cxc_id'],
            "name": f"POS-{r['odoo_order_id']}",
            "source": "odoo",
        })
    return {
        "data": result,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if page_size > 0 else 0,
        "max_date_order": max_date_order.isoformat() if max_date_order else None
    }


# =====================
# VENTAS POS — LINEAS (on-demand)
# =====================
@router.get("/ventas-pos/{order_id}/lineas")
async def get_lineas_venta_pos(order_id: int, empresa_id: int = Depends(get_empresa_id)):
    """Detalle de líneas POS desde tablas locales con mapeo de línea de negocio."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        rows = await conn.fetch("""
            SELECT l.id, l.product_id, l.product_name, l.product_code,
                   l.qty, l.price_unit, l.discount, l.price_subtotal, l.price_subtotal_incl,
                   l.marca, l.tipo,
                   l.odoo_linea_negocio_id, l.odoo_linea_negocio_nombre
            FROM finanzas2.cont_venta_pos_linea l
            JOIN finanzas2.cont_venta_pos v ON l.venta_pos_id = v.id
            WHERE v.odoo_id = $1 AND v.empresa_id = $2
            ORDER BY l.id ASC
        """, order_id, empresa_id)

        if not rows:
            return []

        from services.linea_mapping import get_linea_negocio_map, resolve_linea
        ln_map = await get_linea_negocio_map(conn, empresa_id)

        result = []
        for r in rows:
            mapped = resolve_linea(ln_map, r['odoo_linea_negocio_id'])
            result.append({
                "id": r['id'],
                "product_id": r['product_id'],
                "product_name": r['product_name'] or r['product_code'] or '-',
                "product_code": r['product_code'] or '-',
                "qty": float(r['qty'] or 0),
                "price_unit": float(r['price_unit'] or 0),
                "discount": float(r['discount'] or 0),
                "price_subtotal": float(r['price_subtotal'] or 0),
                "price_subtotal_incl": float(r['price_subtotal_incl'] or 0),
                "marca": r['marca'],
                "tipo": r['tipo'],
                "linea_negocio_id": mapped['id'],
                "linea_negocio_nombre": mapped['nombre'],
                "odoo_linea_negocio_id": r['odoo_linea_negocio_id'],
            })
        return result


# =====================
# VENTAS POS — PAGOS CREDITO (CxC Abonos)
# =====================
@router.get("/ventas-pos/{order_id}/pagos-credito")
async def get_pagos_credito(order_id: int, empresa_id: int = Depends(get_empresa_id)):
    """Returns CxC abonos linked to a credit sale's receivable."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        cxc_info = await conn.fetchrow("""
            SELECT id, monto_original, saldo_pendiente, estado, fecha_vencimiento
            FROM cont_cxc
            WHERE odoo_order_id = $1 AND empresa_id = $2
            LIMIT 1
        """, order_id, empresa_id)

        if not cxc_info:
            return {"abonos": [], "cxc": None}

        rows = await conn.fetch("""
            SELECT ab.id, ab.fecha, ab.monto, ab.forma_pago, ab.referencia, ab.notas,
                   cf.nombre as cuenta_nombre
            FROM cont_cxc_abono ab
            LEFT JOIN cont_cuenta_financiera cf ON cf.id = ab.cuenta_financiera_id
            WHERE ab.cxc_id = $1 AND ab.empresa_id = $2
            ORDER BY ab.fecha DESC, ab.id DESC
        """, cxc_info['id'], empresa_id)

        return {
            "abonos": [{
                "id": r['id'],
                "fecha": r['fecha'].isoformat() if r['fecha'] else None,
                "monto": float(r['monto']),
                "forma_pago": r['forma_pago'],
                "referencia": r['referencia'],
                "notas": r['notas'],
                "cuenta_nombre": r['cuenta_nombre'],
            } for r in rows],
            "cxc": {
                "id": cxc_info['id'],
                "monto_original": float(cxc_info['monto_original']),
                "saldo_pendiente": float(cxc_info['saldo_pendiente']),
                "estado": cxc_info['estado'],
                "fecha_vencimiento": cxc_info['fecha_vencimiento'].isoformat() if cxc_info['fecha_vencimiento'] else None,
            }
        }
