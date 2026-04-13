from fastapi import APIRouter, Depends
from datetime import datetime, timedelta
from database import get_pool
from models import DashboardKPIs
from dependencies import get_empresa_id

router = APIRouter()


@router.get("/dashboard/kpis", response_model=DashboardKPIs)
async def get_dashboard_kpis(empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        total_cxp = await conn.fetchval("""
            SELECT COALESCE(SUM(saldo_pendiente), 0)
            FROM finanzas2.cont_cxp WHERE estado NOT IN ('pagado', 'anulada') AND empresa_id = $1
        """, empresa_id) or 0

        total_cxc = await conn.fetchval("""
            SELECT COALESCE(SUM(saldo_pendiente), 0)
            FROM finanzas2.cont_cxc WHERE estado NOT IN ('pagado', 'anulada') AND empresa_id = $1
        """, empresa_id) or 0

        total_letras = await conn.fetchval("""
            SELECT COALESCE(SUM(saldo_pendiente), 0)
            FROM finanzas2.cont_letra WHERE estado IN ('pendiente', 'parcial') AND empresa_id = $1
        """, empresa_id) or 0

        saldo_bancos = await conn.fetchval("""
            SELECT COALESCE(SUM(saldo_actual), 0)
            FROM finanzas2.cont_cuenta_financiera WHERE activo = TRUE AND empresa_id = $1
        """, empresa_id) or 0

        inicio_mes = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        ventas_mes = await conn.fetchval("""
            SELECT COALESCE(SUM(amount_total), 0)
            FROM finanzas2.cont_venta_pos
            WHERE date_order >= $1 AND estado_local = 'confirmada' AND empresa_id = $2
        """, inicio_mes, empresa_id) or 0

        gastos_mes = await conn.fetchval("""
            SELECT COALESCE(SUM(total), 0)
            FROM finanzas2.cont_gasto WHERE fecha >= $1 AND empresa_id = $2
        """, inicio_mes.date(), empresa_id) or 0

        facturas_pendientes = await conn.fetchval("""
            SELECT COUNT(*) FROM finanzas2.cont_factura_proveedor
            WHERE estado IN ('pendiente', 'parcial') AND empresa_id = $1
        """, empresa_id) or 0

        fecha_limite = datetime.now().date() + timedelta(days=7)
        letras_por_vencer = await conn.fetchval("""
            SELECT COUNT(*) FROM finanzas2.cont_letra
            WHERE estado IN ('pendiente', 'parcial') AND fecha_vencimiento <= $1 AND empresa_id = $2
        """, fecha_limite, empresa_id) or 0

        return DashboardKPIs(
            total_cxp=float(total_cxp),
            total_cxc=float(total_cxc),
            total_letras_pendientes=float(total_letras),
            saldo_bancos=float(saldo_bancos),
            ventas_mes=float(ventas_mes),
            gastos_mes=float(gastos_mes),
            facturas_pendientes=facturas_pendientes,
            letras_por_vencer=letras_por_vencer
        )


@router.get("/dashboard/resumen-ejecutivo")
async def get_resumen_ejecutivo(empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        inicio_mes = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # 1. Ventas POS pendientes
        ventas_pend = await conn.fetchrow("""
            SELECT COUNT(*) as cantidad, COALESCE(SUM(amount_total), 0) as monto
            FROM cont_venta_pos
            WHERE COALESCE(estado_local, 'pendiente') = 'pendiente' AND empresa_id = $1
        """, empresa_id)

        # 2. Gastos comunes pendientes de prorrateo
        gastos_pend = await conn.fetchrow("""
            SELECT COUNT(*) as cantidad, COALESCE(SUM(g.total), 0) as monto
            FROM cont_gasto g
            WHERE g.empresa_id = $1
              AND (g.tipo_asignacion = 'comun' OR (g.tipo_asignacion = 'no_asignado' AND g.linea_negocio_id IS NULL))
              AND NOT EXISTS (SELECT 1 FROM cont_prorrateo_gasto p WHERE p.gasto_id = g.id)
        """, empresa_id)

        # 3. Cobranza pendiente total
        cobranza_total = await conn.fetchval("""
            SELECT COALESCE(SUM(saldo_pendiente), 0)
            FROM cont_cxc WHERE estado NOT IN ('pagado', 'anulada') AND empresa_id = $1
        """, empresa_id) or 0

        # 4. Cobranza pendiente por línea
        cobranza_linea = await conn.fetch("""
            SELECT ln.id as linea_id, ln.nombre as linea_nombre,
                   COALESCE(SUM(c.saldo_pendiente), 0) as saldo_pendiente
            FROM cont_cxc c
            LEFT JOIN cont_linea_negocio ln ON c.linea_negocio_id = ln.id
            WHERE c.estado NOT IN ('pagado', 'anulada') AND c.empresa_id = $1
            GROUP BY ln.id, ln.nombre
            ORDER BY saldo_pendiente DESC
        """, empresa_id)

        # 5. Ingresos cobrados del mes (solo dinero real recibido)
        ingresos_mes = await conn.fetchval("""
            SELECT COALESCE(SUM(d.monto), 0)
            FROM cont_distribucion_analitica d
            WHERE d.empresa_id = $1 AND d.fecha >= $2
              AND d.origen_tipo = 'cobranza_cxc'
        """, empresa_id, inicio_mes.date()) or 0

        # 6. Gastos del mes
        gastos_mes = await conn.fetchval("""
            SELECT COALESCE(SUM(total), 0) FROM cont_gasto WHERE fecha >= $1 AND empresa_id = $2
        """, inicio_mes.date(), empresa_id) or 0

        # 7. Ingresos por línea (solo cobros reales - movimientos de dinero)
        ingresos_linea = await conn.fetch("""
            SELECT ln.id as linea_id, ln.nombre as linea_nombre,
                   COALESCE(SUM(d.monto), 0) as ingresos
            FROM cont_distribucion_analitica d
            JOIN cont_linea_negocio ln ON d.linea_negocio_id = ln.id
            WHERE d.empresa_id = $1 AND d.fecha >= $2
              AND d.origen_tipo = 'cobranza_cxc'
            GROUP BY ln.id, ln.nombre
        """, empresa_id, inicio_mes.date())

        # 8. Gastos directos por línea (mes actual)
        gastos_directos_linea = await conn.fetch("""
            SELECT ln.id as linea_id, COALESCE(SUM(g.total), 0) as gastos
            FROM cont_gasto g
            JOIN cont_linea_negocio ln ON g.linea_negocio_id = ln.id
            WHERE g.empresa_id = $1 AND g.fecha >= $2 AND g.tipo_asignacion = 'directo'
            GROUP BY ln.id
        """, empresa_id, inicio_mes.date())

        # 9. Gastos prorrateados por línea (mes actual)
        gastos_prorrateados_linea = await conn.fetch("""
            SELECT p.linea_negocio_id as linea_id, COALESCE(SUM(p.monto), 0) as gastos_prorrateo
            FROM cont_prorrateo_gasto p
            JOIN cont_gasto g ON p.gasto_id = g.id
            WHERE g.empresa_id = $1 AND g.fecha >= $2
            GROUP BY p.linea_negocio_id
        """, empresa_id, inicio_mes.date())

        # 10. Egresos proveedores por línea (pagos facturas + letras desde distribución analítica)
        egresos_prov_linea = await conn.fetch("""
            SELECT d.linea_negocio_id as linea_id, COALESCE(SUM(d.monto), 0) as egresos
            FROM cont_distribucion_analitica d
            WHERE d.empresa_id = $1 AND d.fecha >= $2
              AND d.origen_tipo IN ('pago_egreso', 'pago_letra')
            GROUP BY d.linea_negocio_id
        """, empresa_id, inicio_mes.date())

        # 11. Egresos proveedores total mes
        egresos_prov_mes = await conn.fetchval("""
            SELECT COALESCE(SUM(d.monto), 0)
            FROM cont_distribucion_analitica d
            WHERE d.empresa_id = $1 AND d.fecha >= $2
              AND d.origen_tipo IN ('pago_egreso', 'pago_letra')
        """, empresa_id, inicio_mes.date()) or 0

        # Build utilidad por linea
        todas_lineas = await conn.fetch("SELECT id, nombre FROM cont_linea_negocio WHERE empresa_id = $1 AND activo = TRUE", empresa_id)
        ing_map = {r['linea_id']: float(r['ingresos']) for r in ingresos_linea}
        gd_map = {r['linea_id']: float(r['gastos']) for r in gastos_directos_linea}
        gp_map = {r['linea_id']: float(r['gastos_prorrateo']) for r in gastos_prorrateados_linea}
        ep_map = {r['linea_id']: float(r['egresos']) for r in egresos_prov_linea}

        utilidad_linea = []
        for ln in todas_lineas:
            lid = ln['id']
            ing = ing_map.get(lid, 0)
            gd = gd_map.get(lid, 0)
            gp = gp_map.get(lid, 0)
            ep = ep_map.get(lid, 0)
            utilidad_linea.append({
                "linea_id": lid,
                "linea_nombre": ln['nombre'],
                "ingresos": ing,
                "egresos_proveedores": ep,
                "gastos_directos": gd,
                "gastos_prorrateados": gp,
                "utilidad_antes_prorrateo": ing - gd - ep,
                "utilidad_despues_prorrateo": ing - gd - gp - ep,
            })
        utilidad_linea.sort(key=lambda x: x['ingresos'], reverse=True)

        return {
            "ventas_pendientes_cantidad": ventas_pend['cantidad'],
            "ventas_pendientes_monto": float(ventas_pend['monto']),
            "gastos_prorrateo_cantidad": gastos_pend['cantidad'],
            "gastos_prorrateo_monto": float(gastos_pend['monto']),
            "cobranza_pendiente_total": float(cobranza_total),
            "cobranza_pendiente_linea": [dict(r) for r in cobranza_linea],
            "ingresos_mes": float(ingresos_mes),
            "gastos_mes": float(gastos_mes),
            "egresos_proveedores_mes": float(egresos_prov_mes),
            "resultado_neto": float(ingresos_mes) - float(gastos_mes) - float(egresos_prov_mes),
            "utilidad_linea": utilidad_linea,
        }
