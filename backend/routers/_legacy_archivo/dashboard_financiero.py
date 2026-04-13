from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from datetime import date, datetime, timedelta
from database import get_pool
from dependencies import get_empresa_id
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/dashboard-financiero")
async def dashboard_financiero(
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    marca_id: Optional[int] = None,
    linea_negocio_id: Optional[int] = None,
    centro_costo_id: Optional[int] = None,
    proyecto_id: Optional[int] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        today = date.today()
        if not fecha_desde:
            fecha_desde = today.replace(day=1)
        if not fecha_hasta:
            fecha_hasta = today

        fd = datetime.combine(fecha_desde, datetime.min.time())
        fh = datetime.combine(fecha_hasta, datetime.max.time())

        # ── 1. TESORERIA: saldos reales ──
        cuentas = await conn.fetch(
            "SELECT tipo, SUM(saldo_actual) as total FROM cont_cuenta_financiera WHERE empresa_id=$1 AND activo=TRUE GROUP BY tipo",
            empresa_id)
        saldo_caja = 0
        saldo_banco = 0
        for c in cuentas:
            if c['tipo'] == 'caja':
                saldo_caja = float(c['total'] or 0)
            else:
                saldo_banco = float(c['total'] or 0)

        # ── 2. VENTAS POS por estado (desde tablas locales, desacoplado de Odoo) ──
        ventas_stats = {"pendiente": 0, "confirmada": 0, "credito": 0, "descartada": 0,
                        "monto_pendiente": 0, "monto_confirmada": 0, "monto_credito": 0}

        rows = await conn.fetch("""
            SELECT COALESCE(e.estado_local, 'pendiente') as estado,
                   COUNT(*) as cnt,
                   COALESCE(SUM(v.amount_total), 0) as monto
            FROM cont_venta_pos v
            LEFT JOIN cont_venta_pos_estado e
                ON e.odoo_order_id = v.odoo_id AND e.empresa_id = $1
            WHERE v.empresa_id = $1
              AND v.date_order >= $2 AND v.date_order <= $3
            GROUP BY COALESCE(e.estado_local, 'pendiente')
        """, empresa_id, fd, fh)
        for r in rows:
            est = r['estado']
            if est in ventas_stats:
                ventas_stats[est] = int(r['cnt'])
                ventas_stats[f"monto_{est}"] = float(r['monto'])

        # ── 3. INGRESOS CONFIRMADOS por linea de negocio (desde tablas locales) ──
        ingresos_por_marca = []
        total_ingresos_confirmados = 0

        from services.linea_mapping import get_linea_negocio_map, resolve_linea
        ln_map = await get_linea_negocio_map(conn, empresa_id)

        ln_rows = await conn.fetch("""
            SELECT l.odoo_linea_negocio_id as odoo_ln_id,
                   l.odoo_linea_negocio_nombre as odoo_ln_nombre,
                   l.marca,
                   SUM(l.price_subtotal) AS ingreso,
                   SUM(l.qty) AS unidades,
                   COUNT(DISTINCT v.odoo_id) AS num_ventas
            FROM cont_venta_pos_estado e
            JOIN cont_venta_pos v
                ON v.odoo_id = e.odoo_order_id AND v.empresa_id = $1
            JOIN cont_venta_pos_linea l
                ON l.venta_pos_id = v.id
            WHERE e.empresa_id = $1
              AND e.estado_local = 'confirmada'
              AND v.date_order >= $2 AND v.date_order <= $3
            GROUP BY l.odoo_linea_negocio_id, l.odoo_linea_negocio_nombre, l.marca
            ORDER BY ingreso DESC
        """, empresa_id, fd, fh)
        for r in ln_rows:
            ingreso = float(r['ingreso'] or 0)
            total_ingresos_confirmados += ingreso
            mapped = resolve_linea(ln_map, r['odoo_ln_id'])
            ingresos_por_marca.append({
                "marca": r['marca'] or 'Sin Marca',
                "linea_negocio": mapped['nombre'],
                "linea_negocio_id": mapped['id'],
                "ingreso": ingreso,
                "unidades": int(r['unidades'] or 0),
                "num_ventas": int(r['num_ventas'] or 0)
            })

        # ── 4. COBRANZAS REALES (from treasury movements - single source of truth) ──
        cobranzas = await conn.fetchrow("""
            SELECT COALESCE(SUM(monto), 0) as total, COUNT(*) as cnt
            FROM cont_movimiento_tesoreria
            WHERE empresa_id = $1 AND tipo = 'ingreso'
              AND fecha >= $2 AND fecha <= $3
        """, empresa_id, fecha_desde, fecha_hasta)
        total_cobranzas = float(cobranzas['total'] or 0)

        # ── 5. EGRESOS REALES (from treasury movements - single source of truth) ──
        egresos = await conn.fetchrow("""
            SELECT COALESCE(SUM(monto), 0) as total, COUNT(*) as cnt
            FROM cont_movimiento_tesoreria
            WHERE empresa_id = $1 AND tipo = 'egreso'
              AND fecha >= $2 AND fecha <= $3
        """, empresa_id, fecha_desde, fecha_hasta)
        total_egresos = float(egresos['total'] or 0)

        # ── 6. GASTOS del periodo ──
        gastos = await conn.fetchrow("""
            SELECT COALESCE(SUM(total), 0) as total, COUNT(*) as cnt
            FROM cont_gasto
            WHERE empresa_id = $1
              AND fecha >= $2 AND fecha <= $3
        """, empresa_id, fecha_desde, fecha_hasta)
        total_gastos = float(gastos['total'] or 0)

        # ── 7. CXC pendientes ──
        cxc = await conn.fetchrow("""
            SELECT COALESCE(SUM(saldo_pendiente), 0) as total, COUNT(*) as cnt
            FROM cont_cxc
            WHERE empresa_id = $1 AND estado NOT IN ('cobrada', 'anulada')
        """, empresa_id)
        total_cxc = float(cxc['total'] or 0)
        cnt_cxc = int(cxc['cnt'] or 0)

        # ── 8. CXP pendientes ──
        cxp = await conn.fetchrow("""
            SELECT COALESCE(SUM(saldo_pendiente), 0) as total, COUNT(*) as cnt
            FROM cont_cxp
            WHERE empresa_id = $1 AND estado NOT IN ('pagado', 'anulada')
        """, empresa_id)
        total_cxp = float(cxp['total'] or 0)
        cnt_cxp = int(cxp['cnt'] or 0)

        # ── 9. CXC aging ──
        cxc_aging = {"0_30": 0, "31_60": 0, "61_90": 0, "90_plus": 0}
        aging_rows = await conn.fetch("""
            SELECT
                CASE
                    WHEN CURRENT_DATE - fecha_vencimiento <= 30 THEN '0_30'
                    WHEN CURRENT_DATE - fecha_vencimiento <= 60 THEN '31_60'
                    WHEN CURRENT_DATE - fecha_vencimiento <= 90 THEN '61_90'
                    ELSE '90_plus'
                END as bucket,
                COALESCE(SUM(saldo_pendiente), 0) as total
            FROM cont_cxc
            WHERE empresa_id = $1 AND estado NOT IN ('cobrada', 'anulada')
              AND fecha_vencimiento IS NOT NULL
            GROUP BY bucket
        """, empresa_id)
        for r in aging_rows:
            cxc_aging[r['bucket']] = float(r['total'])

        # ── 10. Top CxC vencidas ──
        top_cxc = await conn.fetch("""
            SELECT c.id, COALESCE(t.nombre, 'Sin Cliente') as tercero_nombre,
                   c.monto_original as monto, c.saldo_pendiente, c.fecha_vencimiento,
                   CURRENT_DATE - c.fecha_vencimiento as dias_atraso, c.tipo_origen
            FROM cont_cxc c
            LEFT JOIN cont_tercero t ON t.id = c.cliente_id
            WHERE c.empresa_id = $1 AND c.estado NOT IN ('cobrada', 'anulada')
              AND c.fecha_vencimiento < CURRENT_DATE
            ORDER BY c.saldo_pendiente DESC LIMIT 5
        """, empresa_id)

        # ── 11. Top CxP por vencer ──
        top_cxp = await conn.fetch("""
            SELECT c.id, COALESCE(t.nombre, 'Sin Proveedor') as tercero_nombre,
                   c.monto_original as monto, c.saldo_pendiente, c.fecha_vencimiento,
                   c.fecha_vencimiento - CURRENT_DATE as dias_por_vencer, c.tipo_origen
            FROM cont_cxp c
            LEFT JOIN cont_tercero t ON t.id = c.proveedor_id
            WHERE c.empresa_id = $1 AND c.estado NOT IN ('pagado', 'anulada')
            ORDER BY c.fecha_vencimiento ASC LIMIT 5
        """, empresa_id)

        # ── CALCULOS ──
        flujo_neto = total_cobranzas - total_egresos - total_gastos
        utilidad_estimada = total_ingresos_confirmados - total_gastos

        return {
            # Tesoreria
            "saldo_caja": saldo_caja,
            "saldo_banco": saldo_banco,
            "saldo_total": saldo_caja + saldo_banco,
            # Devengado (ingresos reconocidos)
            "ingresos_confirmados": total_ingresos_confirmados,
            "gastos_periodo": total_gastos,
            "utilidad_estimada": utilidad_estimada,
            # Flujo de caja real
            "cobranzas_reales": total_cobranzas,
            "egresos_reales": total_egresos + total_gastos,
            "flujo_neto": flujo_neto,
            # Ventas POS por estado
            "ventas": ventas_stats,
            # CxC / CxP
            "cxc_total": total_cxc,
            "cxc_count": cnt_cxc,
            "cxp_total": total_cxp,
            "cxp_count": cnt_cxp,
            "cxc_aging": cxc_aging,
            # Desglose por marca
            "ingresos_por_marca": ingresos_por_marca,
            # Top listas
            "top_cxc_vencidas": [dict(r) for r in top_cxc],
            "top_cxp_por_vencer": [dict(r) for r in top_cxp],
            # Periodo
            "fecha_desde": fecha_desde.isoformat(),
            "fecha_hasta": fecha_hasta.isoformat(),
        }
