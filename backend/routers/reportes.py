"""
Reportes Financieros Gerenciales (Mejorado)
- Balance General
- Estado de Ganancias y Perdidas (EGyP)
- Cash Flow / Flujo de Caja
- Inventario Valorizado
"""
from fastapi import APIRouter, Depends, Query
from datetime import date, datetime
from typing import Optional
from database import get_pool
from dependencies import get_empresa_id

router = APIRouter()


def _serialize(row):
    d = {}
    for k, v in dict(row).items():
        if isinstance(v, (date, datetime)):
            d[k] = v.isoformat()
        elif hasattr(v, 'as_tuple'):
            d[k] = float(v)
        else:
            d[k] = v
    return d


# =====================
# BALANCE GENERAL
# =====================
@router.get("/reportes/balance-general")
async def reporte_balance_general(
    empresa_id: int = Depends(get_empresa_id),
    fecha_corte: Optional[str] = Query(None),
    linea_negocio_id: Optional[int] = Query(None)
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        # Si no hay fecha_corte, usar hoy
        corte = date.fromisoformat(fecha_corte) if fecha_corte else date.today()

        # ── ACTIVOS ──

        # Caja y Bancos: saldo inicial + movimientos hasta fecha_corte
        cuentas_raw = await conn.fetch(
            "SELECT id, nombre, tipo, saldo_inicial FROM finanzas2.cont_cuenta_financiera WHERE empresa_id = $1 AND activo = TRUE",
            empresa_id)
        cuentas = []
        for c in cuentas_raw:
            saldo_inicial = float(c['saldo_inicial'] or 0)
            ingresos = float(await conn.fetchval("""
                SELECT COALESCE(SUM(monto), 0) FROM finanzas2.cont_movimiento_tesoreria
                WHERE cuenta_financiera_id = $1 AND tipo = 'ingreso' AND fecha <= $2::date
            """, c['id'], corte) or 0)
            egresos = float(await conn.fetchval("""
                SELECT COALESCE(SUM(monto), 0) FROM finanzas2.cont_movimiento_tesoreria
                WHERE cuenta_financiera_id = $1 AND tipo = 'egreso' AND fecha <= $2::date
            """, c['id'], corte) or 0)
            saldo = saldo_inicial + ingresos - egresos
            cuentas.append({"id": c['id'], "nombre": c['nombre'], "tipo": c['tipo'], "saldo_actual": saldo})
        caja_total = sum(c['saldo_actual'] for c in cuentas)

        # CxC: creadas hasta fecha_corte menos las pagadas hasta fecha_corte
        cxc = float(await conn.fetchval("""
            SELECT COALESCE(SUM(monto_original), 0) FROM finanzas2.cont_cxc
            WHERE empresa_id = $1 AND estado != 'anulada' AND created_at::date <= $2::date
        """, empresa_id, corte) or 0)
        cxc_cobrado = float(await conn.fetchval("""
            SELECT COALESCE(SUM(pa.monto_aplicado), 0)
            FROM finanzas2.cont_pago_aplicacion pa
            JOIN finanzas2.cont_movimiento_tesoreria mt ON pa.pago_id = mt.id
            WHERE pa.tipo_documento = 'cxc' AND mt.empresa_id = $1 AND pa.created_at::date <= $2::date
        """, empresa_id, corte) or 0)
        cxc_neto = cxc - cxc_cobrado

        # Inventario MP: ingresos hasta fecha - salidas hasta fecha
        inv_mp_detail = await conn.fetch("""
            SELECT inv.categoria,
                   COALESCE(SUM(i.cantidad), 0) - COALESCE(
                       (SELECT SUM(s.cantidad) FROM produccion.prod_inventario_salidas s
                        WHERE s.item_id = inv.id AND s.empresa_id = $1 AND s.fecha <= $2::date), 0
                   ) as cantidad,
                   COALESCE(SUM(i.cantidad * i.costo_unitario), 0) - COALESCE(
                       (SELECT SUM(s.costo_total) FROM produccion.prod_inventario_salidas s
                        WHERE s.item_id = inv.id AND s.empresa_id = $1 AND s.fecha <= $2::date), 0
                   ) as valor
            FROM produccion.prod_inventario_ingresos i
            JOIN produccion.prod_inventario inv ON i.item_id = inv.id
            WHERE i.empresa_id = $1 AND inv.categoria != 'PT' AND i.fecha <= $2::date
            GROUP BY inv.categoria, inv.id
            HAVING COALESCE(SUM(i.cantidad), 0) - COALESCE(
                (SELECT SUM(s.cantidad) FROM produccion.prod_inventario_salidas s
                 WHERE s.item_id = inv.id AND s.empresa_id = $1 AND s.fecha <= $2::date), 0) > 0
        """, empresa_id, corte)
        # Reagrupar por categoria
        cat_totals = {}
        for r in inv_mp_detail:
            cat = r['categoria'] or 'Sin categoria'
            if cat not in cat_totals:
                cat_totals[cat] = {"categoria": cat, "cantidad": 0, "valor": 0}
            cat_totals[cat]["cantidad"] += float(r['cantidad'] or 0)
            cat_totals[cat]["valor"] += float(r['valor'] or 0)
        inv_mp_grouped = sorted(cat_totals.values(), key=lambda x: x['categoria'])
        inv_mp = sum(c['valor'] for c in inv_mp_grouped)

        # Inventario PT
        inv_pt_detail = await conn.fetch("""
            SELECT inv.id,
                   COALESCE(SUM(i.cantidad), 0) - COALESCE(
                       (SELECT SUM(s.cantidad) FROM produccion.prod_inventario_salidas s
                        WHERE s.item_id = inv.id AND s.empresa_id = $1 AND s.fecha <= $2::date), 0
                   ) as cantidad,
                   COALESCE(SUM(i.cantidad * i.costo_unitario), 0) - COALESCE(
                       (SELECT SUM(s.costo_total) FROM produccion.prod_inventario_salidas s
                        WHERE s.item_id = inv.id AND s.empresa_id = $1 AND s.fecha <= $2::date), 0
                   ) as valor
            FROM produccion.prod_inventario_ingresos i
            JOIN produccion.prod_inventario inv ON i.item_id = inv.id
            WHERE i.empresa_id = $1 AND inv.categoria = 'PT' AND i.fecha <= $2::date
            GROUP BY inv.id
            HAVING COALESCE(SUM(i.cantidad), 0) - COALESCE(
                (SELECT SUM(s.cantidad) FROM produccion.prod_inventario_salidas s
                 WHERE s.item_id = inv.id AND s.empresa_id = $1 AND s.fecha <= $2::date), 0) > 0
        """, empresa_id, corte)
        inv_pt = sum(float(r['valor'] or 0) for r in inv_pt_detail)

        # WIP: salidas hasta fecha en registros NO terminados a esa fecha
        wip_mp = float(await conn.fetchval("""
            SELECT COALESCE(SUM(s.costo_total), 0)
            FROM produccion.prod_inventario_salidas s
            JOIN produccion.prod_registros r ON s.registro_id = r.id
            WHERE s.empresa_id = $1 AND s.fecha <= $2::date AND r.estado != 'Producto Terminado'
        """, empresa_id, corte) or 0)
        wip_srv = float(await conn.fetchval("""
            SELECT COALESCE(SUM(fl.importe), 0)
            FROM finanzas2.cont_factura_proveedor_linea fl
            JOIN finanzas2.cont_factura_proveedor f ON fl.factura_id = f.id
            JOIN produccion.prod_registros r ON fl.modelo_corte_id::text = r.id::text
            WHERE f.empresa_id = $1 AND fl.tipo_linea = 'servicio'
            AND r.estado != 'Producto Terminado' AND f.estado != 'anulada'
            AND f.fecha_factura <= $2::date
        """, empresa_id, corte) or 0)
        wip_total = wip_mp + wip_srv

        total_activos = caja_total + cxc_neto + inv_mp + inv_pt + wip_total

        # ── PASIVOS ──

        # CxP: facturas creadas hasta fecha_corte menos pagos hasta fecha_corte
        cxp_total_facturas = float(await conn.fetchval("""
            SELECT COALESCE(SUM(monto_original), 0) FROM finanzas2.cont_cxp
            WHERE empresa_id = $1 AND estado != 'anulada' AND created_at::date <= $2::date
            AND factura_id NOT IN (
                SELECT DISTINCT factura_id FROM finanzas2.cont_letra
                WHERE empresa_id = $1 AND created_at::date <= $2::date
            )
        """, empresa_id, corte) or 0)
        cxp_pagos = float(await conn.fetchval("""
            SELECT COALESCE(SUM(pa.monto_aplicado), 0)
            FROM finanzas2.cont_pago_aplicacion pa
            JOIN finanzas2.cont_movimiento_tesoreria mt ON pa.pago_id = mt.id
            WHERE pa.tipo_documento = 'factura' AND mt.empresa_id = $1 AND pa.created_at::date <= $2::date
            AND pa.documento_id NOT IN (
                SELECT DISTINCT factura_id FROM finanzas2.cont_letra
                WHERE empresa_id = $1 AND created_at::date <= $2::date
            )
        """, empresa_id, corte) or 0)
        cxp = cxp_total_facturas - cxp_pagos

        # Letras: emitidas hasta fecha - pagos de letras hasta fecha
        letras_total = float(await conn.fetchval("""
            SELECT COALESCE(SUM(monto), 0) FROM finanzas2.cont_letra
            WHERE empresa_id = $1 AND estado != 'anulada' AND created_at::date <= $2::date
        """, empresa_id, corte) or 0)
        letras_pagos = float(await conn.fetchval("""
            SELECT COALESCE(SUM(pa.monto_aplicado), 0)
            FROM finanzas2.cont_pago_aplicacion pa
            JOIN finanzas2.cont_movimiento_tesoreria mt ON pa.pago_id = mt.id
            WHERE pa.tipo_documento = 'letra' AND mt.empresa_id = $1 AND pa.created_at::date <= $2::date
        """, empresa_id, corte) or 0)
        letras = letras_total - letras_pagos

        total_pasivos = cxp + letras
        patrimonio = total_activos - total_pasivos

        return {
            "fecha_corte": corte,
            "activos": {
                "caja_bancos": {"cuentas": cuentas, "total": caja_total},
                "cuentas_por_cobrar": cxc_neto,
                "inventario_mp": {"detalle": inv_mp_grouped, "total": inv_mp},
                "inventario_pt": inv_pt,
                "wip": {"mp_consumida": wip_mp, "servicios": wip_srv, "total": wip_total},
                "total": total_activos
            },
            "pasivos": {
                "cuentas_por_pagar": cxp,
                "letras_por_pagar": letras,
                "total": total_pasivos
            },
            "patrimonio": patrimonio,
            "total_activos": total_activos,
            "total_pasivos": total_pasivos
        }


# =====================
# ESTADO DE RESULTADOS
# =====================
@router.get("/reportes/estado-resultados")
async def reporte_estado_resultados(
    empresa_id: int = Depends(get_empresa_id),
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    linea_negocio_id: Optional[int] = Query(None)
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        f_desde = fecha_desde or date(2020, 1, 1)
        f_hasta = fecha_hasta or date.today()

        # VENTAS (solo confirmadas + credito)
        ventas = float(await conn.fetchval("""
            SELECT COALESCE(SUM(v.amount_total), 0)
            FROM finanzas2.cont_venta_pos v
            LEFT JOIN finanzas2.cont_venta_pos_estado e ON e.odoo_order_id = v.odoo_id AND e.empresa_id = v.empresa_id
            WHERE v.empresa_id = $1 AND v.date_order >= $2::timestamp AND v.date_order <= ($3::date + 1)::timestamp
            AND COALESCE(e.estado_local, 'pendiente') IN ('confirmada', 'credito')
        """, empresa_id, f_desde, f_hasta) or 0)

        # Ventas por linea (solo confirmadas + credito)
        ventas_linea = await conn.fetch("""
            SELECT ln.nombre as linea, COALESCE(SUM(v.amount_total), 0) as total
            FROM finanzas2.cont_venta_pos v
            LEFT JOIN finanzas2.cont_venta_pos_estado e ON e.odoo_order_id = v.odoo_id AND e.empresa_id = v.empresa_id
            LEFT JOIN finanzas2.cont_linea_negocio ln ON v.tienda_id::text = ln.id::text
            WHERE v.empresa_id = $1 AND v.date_order >= $2::timestamp AND v.date_order <= ($3::date + 1)::timestamp
            AND COALESCE(e.estado_local, 'pendiente') IN ('confirmada', 'credito')
            GROUP BY ln.nombre ORDER BY total DESC
        """, empresa_id, f_desde, f_hasta)

        # COSTO DE VENTA
        costo_mp = float(await conn.fetchval("""
            SELECT COALESCE(SUM(costo_total), 0)
            FROM produccion.prod_inventario_salidas
            WHERE empresa_id = $1 AND fecha >= $2::timestamp AND fecha <= ($3::date + 1)::timestamp
        """, empresa_id, f_desde, f_hasta) or 0)
        costo_srv = float(await conn.fetchval("""
            SELECT COALESCE(SUM(fl.importe), 0)
            FROM finanzas2.cont_factura_proveedor_linea fl
            JOIN finanzas2.cont_factura_proveedor f ON fl.factura_id = f.id
            WHERE f.empresa_id = $1 AND fl.tipo_linea = 'servicio'
            AND f.fecha_factura >= $2 AND f.fecha_factura <= $3
            AND f.estado != 'anulada'
        """, empresa_id, f_desde, f_hasta) or 0)
        costo_venta_total = costo_mp + costo_srv
        margen_bruto = ventas - costo_venta_total

        # GASTOS OPERATIVOS
        gastos_total = float(await conn.fetchval("""
            SELECT COALESCE(SUM(total), 0) FROM finanzas2.cont_gasto
            WHERE empresa_id = $1 AND fecha >= $2 AND fecha <= $3
        """, empresa_id, f_desde, f_hasta) or 0)

        gastos_cat = await conn.fetch("""
            SELECT COALESCE(c.nombre, 'Sin Categoria') as categoria, SUM(gd.importe) as monto
            FROM finanzas2.cont_gasto_linea gd
            JOIN finanzas2.cont_gasto g ON gd.gasto_id = g.id
            LEFT JOIN finanzas2.cont_categoria c ON gd.categoria_id = c.id
            WHERE g.empresa_id = $1 AND g.fecha >= $2 AND g.fecha <= $3
            GROUP BY c.nombre ORDER BY monto DESC
        """, empresa_id, f_desde, f_hasta)

        utilidad_operativa = margen_bruto - gastos_total

        return {
            "periodo": {"desde": f_desde.isoformat(), "hasta": f_hasta.isoformat()},
            "ventas": {"total": ventas, "por_linea": [_serialize(r) for r in ventas_linea]},
            "costo_venta": {"mp_consumida": costo_mp, "servicios": costo_srv, "total": costo_venta_total},
            "margen_bruto": margen_bruto,
            "gastos_operativos": {"total": gastos_total, "por_categoria": [_serialize(r) for r in gastos_cat]},
            "utilidad_operativa": utilidad_operativa,
            "utilidad_neta": utilidad_operativa
        }


# =====================
# CASH FLOW
# =====================
@router.get("/reportes/flujo-caja")
async def reporte_flujo_caja(
    empresa_id: int = Depends(get_empresa_id),
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
    linea_negocio_id: Optional[int] = Query(None)
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        f_desde = fecha_desde or date(2020, 1, 1)
        f_hasta = fecha_hasta or date.today()

        # INGRESOS REALES
        cobros_ventas = float(await conn.fetchval("""
            SELECT COALESCE(SUM(monto), 0) FROM finanzas2.cont_venta_pos_pago
            WHERE empresa_id = $1 AND fecha_pago >= $2 AND fecha_pago <= $3
        """, empresa_id, f_desde, f_hasta) or 0)

        ing_tesoreria = float(await conn.fetchval("""
            SELECT COALESCE(SUM(monto), 0) FROM finanzas2.cont_movimiento_tesoreria
            WHERE empresa_id = $1 AND tipo = 'ingreso' AND fecha >= $2 AND fecha <= $3
        """, empresa_id, f_desde, f_hasta) or 0)

        pagos_ingreso = float(await conn.fetchval("""
            SELECT COALESCE(SUM(monto_total), 0) FROM finanzas2.cont_pago
            WHERE empresa_id = $1 AND tipo = 'ingreso' AND fecha >= $2 AND fecha <= $3
        """, empresa_id, f_desde, f_hasta) or 0)

        total_ingresos = cobros_ventas + ing_tesoreria + pagos_ingreso

        # Detalle ingresos
        ing_detalle = await conn.fetch("""
            SELECT concepto, SUM(monto) as total FROM finanzas2.cont_movimiento_tesoreria
            WHERE empresa_id = $1 AND tipo = 'ingreso' AND fecha >= $2 AND fecha <= $3
            GROUP BY concepto ORDER BY total DESC
        """, empresa_id, f_desde, f_hasta)

        # EGRESOS REALES
        eg_tesoreria = float(await conn.fetchval("""
            SELECT COALESCE(SUM(monto), 0) FROM finanzas2.cont_movimiento_tesoreria
            WHERE empresa_id = $1 AND tipo = 'egreso' AND fecha >= $2 AND fecha <= $3
        """, empresa_id, f_desde, f_hasta) or 0)

        pagos_egreso = float(await conn.fetchval("""
            SELECT COALESCE(SUM(monto_total), 0) FROM finanzas2.cont_pago
            WHERE empresa_id = $1 AND tipo = 'egreso' AND fecha >= $2 AND fecha <= $3
        """, empresa_id, f_desde, f_hasta) or 0)

        total_egresos = eg_tesoreria + pagos_egreso

        # Detalle egresos
        eg_detalle = await conn.fetch("""
            SELECT concepto, SUM(monto) as total FROM finanzas2.cont_movimiento_tesoreria
            WHERE empresa_id = $1 AND tipo = 'egreso' AND fecha >= $2 AND fecha <= $3
            GROUP BY concepto ORDER BY total DESC
        """, empresa_id, f_desde, f_hasta)

        # Saldos actuales
        saldos = await conn.fetch(
            "SELECT nombre, tipo, saldo_actual FROM finanzas2.cont_cuenta_financiera WHERE empresa_id = $1 AND activo = TRUE ORDER BY nombre",
            empresa_id)

        return {
            "periodo": {"desde": f_desde.isoformat(), "hasta": f_hasta.isoformat()},
            "ingresos": {
                "cobros_ventas": cobros_ventas,
                "tesoreria": ing_tesoreria,
                "pagos_recibidos": pagos_ingreso,
                "total": total_ingresos,
                "detalle": [_serialize(r) for r in ing_detalle]
            },
            "egresos": {
                "tesoreria": eg_tesoreria,
                "pagos_proveedores": pagos_egreso,
                "total": total_egresos,
                "detalle": [_serialize(r) for r in eg_detalle]
            },
            "flujo_neto": total_ingresos - total_egresos,
            "saldos_cuentas": [_serialize(r) for r in saldos]
        }


# =====================
# INVENTARIO VALORIZADO
# =====================
@router.get("/reportes/inventario-valorizado")
async def reporte_inventario_valorizado(
    empresa_id: int = Depends(get_empresa_id),
    linea_negocio_id: Optional[int] = Query(None)
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        # MP detail
        mp_items = await conn.fetch("""
            SELECT inv.nombre, inv.codigo, inv.categoria, inv.unidad_medida,
                   SUM(i.cantidad_disponible) as stock,
                   CASE WHEN SUM(i.cantidad_disponible) > 0
                        THEN SUM(i.cantidad_disponible * i.costo_unitario) / SUM(i.cantidad_disponible)
                        ELSE 0 END as costo_promedio,
                   SUM(i.cantidad_disponible * i.costo_unitario) as valor_total
            FROM produccion.prod_inventario_ingresos i
            JOIN produccion.prod_inventario inv ON i.item_id = inv.id
            WHERE i.empresa_id = $1 AND inv.categoria != 'PT' AND i.cantidad_disponible > 0
            GROUP BY inv.nombre, inv.codigo, inv.categoria, inv.unidad_medida
            ORDER BY inv.categoria, inv.nombre
        """, empresa_id)

        # PT detail
        pt_items = await conn.fetch("""
            SELECT inv.nombre, inv.codigo, inv.unidad_medida,
                   SUM(i.cantidad_disponible) as stock,
                   CASE WHEN SUM(i.cantidad_disponible) > 0
                        THEN SUM(i.cantidad_disponible * i.costo_unitario) / SUM(i.cantidad_disponible)
                        ELSE 0 END as costo_promedio,
                   SUM(i.cantidad_disponible * i.costo_unitario) as valor_total
            FROM produccion.prod_inventario_ingresos i
            JOIN produccion.prod_inventario inv ON i.item_id = inv.id
            WHERE i.empresa_id = $1 AND inv.categoria = 'PT' AND i.cantidad_disponible > 0
            GROUP BY inv.nombre, inv.codigo, inv.unidad_medida
            ORDER BY inv.nombre
        """, empresa_id)

        # WIP MP
        wip_mp = await conn.fetch("""
            SELECT r.inventario_nombre, r.tipo_componente,
                   SUM(r.cantidad_consumida) as consumido,
                   SUM(r.cantidad_consumida * COALESCE(i.costo_unitario, 0)) as valor
            FROM produccion.prod_registro_requerimiento_mp r
            LEFT JOIN produccion.prod_inventario_ingresos i ON r.item_id = i.item_id AND i.empresa_id = $1
            WHERE r.empresa_id = $1 AND r.cantidad_consumida > 0
            GROUP BY r.inventario_nombre, r.tipo_componente
        """, empresa_id)

        # WIP Services
        wip_srv = await conn.fetch("""
            SELECT descripcion, SUM(monto) as monto
            FROM produccion.prod_registro_costos_servicio WHERE empresa_id = $1
            GROUP BY descripcion
        """, empresa_id)

        mp_total = sum(float(r['valor_total'] or 0) for r in mp_items)
        pt_total = sum(float(r['valor_total'] or 0) for r in pt_items)
        wip_mp_total = sum(float(r['valor'] or 0) for r in wip_mp)
        wip_srv_total = sum(float(r['monto'] or 0) for r in wip_srv)

        return {
            "materia_prima": {"items": [_serialize(r) for r in mp_items], "total": mp_total},
            "producto_terminado": {"items": [_serialize(r) for r in pt_items], "total": pt_total},
            "wip": {
                "mp_consumida": [_serialize(r) for r in wip_mp], "total_mp": wip_mp_total,
                "servicios": [_serialize(r) for r in wip_srv], "total_srv": wip_srv_total,
                "total": wip_mp_total + wip_srv_total
            },
            "gran_total": mp_total + pt_total + wip_mp_total + wip_srv_total
        }


# =====================
# RENTABILIDAD POR LINEA DE NEGOCIO
# =====================
@router.get("/reportes/rentabilidad-linea")
async def reporte_rentabilidad_linea(
    empresa_id: int = Depends(get_empresa_id),
    fecha_desde: Optional[date] = Query(None),
    fecha_hasta: Optional[date] = Query(None),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        f_desde = fecha_desde or date(2020, 1, 1)
        f_hasta = fecha_hasta or date.today()

        # Get all lineas de negocio
        lineas = await conn.fetch("SELECT id, nombre, codigo FROM finanzas2.cont_linea_negocio ORDER BY nombre")

        resultado = []
        total_ventas = 0
        total_costo = 0
        total_gastos = 0

        for ln in lineas:
            ln_id = ln['id']

            # Ventas por linea (tienda_id maps to linea_negocio)
            ventas = float(await conn.fetchval("""
                SELECT COALESCE(SUM(v.amount_total), 0)
                FROM finanzas2.cont_venta_pos v
                LEFT JOIN finanzas2.cont_venta_pos_estado e ON e.odoo_order_id = v.odoo_id AND e.empresa_id = v.empresa_id
                WHERE v.empresa_id = $1 AND v.date_order >= $2::timestamp AND v.date_order <= ($3::date + 1)::timestamp
                AND COALESCE(e.estado_local, 'pendiente') IN ('confirmada', 'credito')
                AND v.tienda_id::text = $4::text
            """, empresa_id, f_desde, f_hasta, str(ln_id)) or 0)

            # Costo MP: salidas de inventario por linea
            costo_mp = float(await conn.fetchval("""
                SELECT COALESCE(SUM(s.costo_total), 0)
                FROM produccion.prod_inventario_salidas s
                JOIN produccion.prod_inventario inv ON s.item_id = inv.id
                WHERE s.empresa_id = $1 AND s.fecha >= $2::timestamp AND s.fecha <= ($3::date + 1)::timestamp
                AND inv.linea_negocio_id = $4
            """, empresa_id, f_desde, f_hasta, ln_id) or 0)

            # Costo servicios: facturas proveedor lineas con linea_negocio_id
            costo_srv = float(await conn.fetchval("""
                SELECT COALESCE(SUM(fl.importe), 0)
                FROM finanzas2.cont_factura_proveedor_linea fl
                JOIN finanzas2.cont_factura_proveedor f ON fl.factura_id = f.id
                WHERE f.empresa_id = $1 AND fl.tipo_linea = 'servicio'
                AND f.fecha_factura >= $2 AND f.fecha_factura <= $3
                AND f.estado != 'anulada' AND fl.linea_negocio_id = $4
            """, empresa_id, f_desde, f_hasta, ln_id) or 0)

            costo_total = costo_mp + costo_srv

            # Gastos asignados a esta linea
            gastos = float(await conn.fetchval("""
                SELECT COALESCE(SUM(gl.importe), 0)
                FROM finanzas2.cont_gasto_linea gl
                JOIN finanzas2.cont_gasto g ON gl.gasto_id = g.id
                WHERE g.empresa_id = $1 AND g.fecha >= $2 AND g.fecha <= $3
                AND gl.linea_negocio_id = $4
            """, empresa_id, f_desde, f_hasta, ln_id) or 0)

            margen_bruto = ventas - costo_total
            utilidad = margen_bruto - gastos
            pct_margen = (margen_bruto / ventas * 100) if ventas > 0 else 0

            resultado.append({
                "linea_id": ln_id,
                "linea_nombre": ln['nombre'],
                "linea_codigo": ln['codigo'],
                "ventas": ventas,
                "costo_mp": costo_mp,
                "costo_servicios": costo_srv,
                "costo_total": costo_total,
                "margen_bruto": margen_bruto,
                "pct_margen": round(pct_margen, 1),
                "gastos": gastos,
                "utilidad": utilidad
            })

            total_ventas += ventas
            total_costo += costo_total
            total_gastos += gastos

        return {
            "periodo": {"desde": f_desde.isoformat(), "hasta": f_hasta.isoformat()},
            "lineas": resultado,
            "totales": {
                "ventas": total_ventas,
                "costo_total": total_costo,
                "margen_bruto": total_ventas - total_costo,
                "pct_margen": round((total_ventas - total_costo) / total_ventas * 100, 1) if total_ventas > 0 else 0,
                "gastos": total_gastos,
                "utilidad": total_ventas - total_costo - total_gastos
            }
        }


# =====================
# CXP POR ANTIGUEDAD (AGING)
# =====================
@router.get("/reportes/cxp-aging")
async def reporte_cxp_aging(
    empresa_id: int = Depends(get_empresa_id),
    fecha_corte: Optional[str] = Query(None),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        corte = date.fromisoformat(fecha_corte) if fecha_corte else date.today()

        rows = await conn.fetch("""
            SELECT cp.id, cp.monto_original, cp.saldo_pendiente, cp.fecha_vencimiento,
                   cp.estado, cp.documento_referencia, cp.created_at,
                   t.nombre as proveedor,
                   ln.nombre as linea_negocio
            FROM finanzas2.cont_cxp cp
            LEFT JOIN finanzas2.cont_tercero t ON cp.proveedor_id = t.id
            LEFT JOIN finanzas2.cont_linea_negocio ln ON cp.linea_negocio_id = ln.id
            WHERE cp.empresa_id = $1 AND cp.estado NOT IN ('anulada', 'pagado')
              AND cp.saldo_pendiente > 0
            ORDER BY cp.fecha_vencimiento
        """, empresa_id)

        # Aging buckets
        buckets = {"vigente": 0, "1_30": 0, "31_60": 0, "61_90": 0, "90_plus": 0}
        detalle = []

        for r in rows:
            venc = r['fecha_vencimiento']
            dias = (corte - venc).days if venc else 0
            saldo = float(r['saldo_pendiente'] or 0)

            if dias <= 0:
                bucket = "vigente"
            elif dias <= 30:
                bucket = "1_30"
            elif dias <= 60:
                bucket = "31_60"
            elif dias <= 90:
                bucket = "61_90"
            else:
                bucket = "90_plus"

            buckets[bucket] += saldo

            detalle.append({
                "id": r['id'],
                "proveedor": r['proveedor'] or 'Sin proveedor',
                "documento": r['documento_referencia'] or f"CXP-{r['id']}",
                "monto_original": float(r['monto_original'] or 0),
                "saldo": saldo,
                "fecha_vencimiento": venc.isoformat() if venc else None,
                "dias_vencido": max(dias, 0),
                "bucket": bucket,
                "linea_negocio": r['linea_negocio']
            })

        total = sum(buckets.values())

        return {
            "fecha_corte": corte.isoformat(),
            "buckets": buckets,
            "total": total,
            "detalle": detalle,
            "resumen_proveedor": _agrupar_por(detalle, "proveedor", corte)
        }


# =====================
# CXC POR ANTIGUEDAD (AGING)
# =====================
@router.get("/reportes/cxc-aging")
async def reporte_cxc_aging(
    empresa_id: int = Depends(get_empresa_id),
    fecha_corte: Optional[str] = Query(None),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        corte = date.fromisoformat(fecha_corte) if fecha_corte else date.today()

        rows = await conn.fetch("""
            SELECT cc.id, cc.monto_original, cc.saldo_pendiente, cc.fecha_vencimiento,
                   cc.estado, cc.documento_referencia, cc.created_at,
                   ln.nombre as linea_negocio
            FROM finanzas2.cont_cxc cc
            LEFT JOIN finanzas2.cont_linea_negocio ln ON cc.linea_negocio_id = ln.id
            WHERE cc.empresa_id = $1 AND cc.estado NOT IN ('anulada', 'pagado', 'cobrado')
              AND cc.saldo_pendiente > 0
            ORDER BY cc.fecha_vencimiento
        """, empresa_id)

        buckets = {"vigente": 0, "1_30": 0, "31_60": 0, "61_90": 0, "90_plus": 0}
        detalle = []

        for r in rows:
            venc = r['fecha_vencimiento']
            dias = (corte - venc).days if venc else 0
            saldo = float(r['saldo_pendiente'] or 0)

            if dias <= 0:
                bucket = "vigente"
            elif dias <= 30:
                bucket = "1_30"
            elif dias <= 60:
                bucket = "31_60"
            elif dias <= 90:
                bucket = "61_90"
            else:
                bucket = "90_plus"

            buckets[bucket] += saldo
            detalle.append({
                "id": r['id'],
                "cliente": r['documento_referencia'] or f"CXC-{r['id']}",
                "monto_original": float(r['monto_original'] or 0),
                "saldo": saldo,
                "fecha_vencimiento": venc.isoformat() if venc else None,
                "dias_vencido": max(dias, 0),
                "bucket": bucket,
                "linea_negocio": r['linea_negocio']
            })

        total = sum(buckets.values())

        return {
            "fecha_corte": corte.isoformat(),
            "buckets": buckets,
            "total": total,
            "detalle": detalle,
        }


def _agrupar_por(detalle, campo, corte):
    """Group aging detail by a field, with bucket subtotals."""
    grupos = {}
    for d in detalle:
        key = d.get(campo) or 'Sin asignar'
        if key not in grupos:
            grupos[key] = {"nombre": key, "total": 0, "vigente": 0, "1_30": 0, "31_60": 0, "61_90": 0, "90_plus": 0}
        grupos[key]["total"] += d['saldo']
        grupos[key][d['bucket']] += d['saldo']
    return sorted(grupos.values(), key=lambda x: -x['total'])
