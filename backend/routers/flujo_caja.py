"""
CORE endpoint extraído de finanzas_gerencial.py (Fase 3 cleanup).
Contiene: /flujo-caja-gerencial
Usado por: FlujoCaja.jsx
Los endpoints /rentabilidad, /presupuesto-vs-real, /roi-proyectos quedan en finanzas_gerencial.py → legacy.
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional
from datetime import date
from database import get_pool
from dependencies import get_empresa_id

router = APIRouter()


@router.get("/flujo-caja-gerencial")
async def flujo_caja_gerencial(
    fecha_desde: date = Query(...),
    fecha_hasta: date = Query(...),
    agrupacion: str = Query("diario", regex="^(diario|semanal|mensual)$"),
    marca_id: Optional[int] = None,
    proyecto_id: Optional[int] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    """Cash flow report from TREASURY MOVEMENTS (single source of truth)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        date_trunc = {"diario": "day", "semanal": "week", "mensual": "month"}[agrupacion]

        extra_conds = ""
        params = [empresa_id, fecha_desde, fecha_hasta]
        idx = 4
        if marca_id:
            extra_conds += f" AND marca_id = ${idx}"
            params.append(marca_id)
            idx += 1
        if proyecto_id:
            extra_conds += f" AND proyecto_id = ${idx}"
            params.append(proyecto_id)
            idx += 1

        rows = await conn.fetch(f"""
            SELECT DATE_TRUNC('{date_trunc}', fecha)::date as periodo,
                   tipo,
                   origen_tipo,
                   COALESCE(SUM(monto), 0) as total
            FROM cont_movimiento_tesoreria
            WHERE empresa_id = $1
              AND fecha BETWEEN $2 AND $3
              {extra_conds}
            GROUP BY periodo, tipo, origen_tipo
            ORDER BY periodo
        """, *params)

        periods = {}
        for r in rows:
            p = r['periodo'].isoformat()
            periods.setdefault(p, {
                "ingresos_ventas": 0, "cobranzas_cxc": 0, "otros_ingresos": 0,
                "pagos_cxp": 0, "pagos_gastos": 0, "otros_egresos": 0
            })
            t = float(r['total'])
            ot = r['origen_tipo']
            if r['tipo'] == 'ingreso':
                if ot == 'venta_pos_confirmada':
                    periods[p]["ingresos_ventas"] += t
                elif ot == 'cobranza_cxc':
                    periods[p]["cobranzas_cxc"] += t
                else:
                    periods[p]["otros_ingresos"] += t
            else:
                if ot == 'pago_cxp':
                    periods[p]["pagos_cxp"] += t
                elif ot in ('gasto_directo', 'pago_gasto'):
                    periods[p]["pagos_gastos"] += t
                else:
                    periods[p]["otros_egresos"] += t

        timeline = []
        saldo = 0
        for p in sorted(periods.keys()):
            d = periods[p]
            total_in = d["ingresos_ventas"] + d["cobranzas_cxc"] + d["otros_ingresos"]
            total_out = d["pagos_cxp"] + d["pagos_gastos"] + d["otros_egresos"]
            saldo += total_in - total_out
            timeline.append({
                "periodo": p,
                "ingresos_ventas": d["ingresos_ventas"],
                "cobranzas_cxc": d["cobranzas_cxc"],
                "otros_ingresos": d["otros_ingresos"],
                "total_ingresos": total_in,
                "pagos_cxp": d["pagos_cxp"],
                "pagos_gastos": d["pagos_gastos"],
                "otros_egresos": d["otros_egresos"],
                "total_egresos": total_out,
                "flujo_neto": total_in - total_out,
                "saldo_acumulado": saldo,
            })

        total_ingresos = sum(t["total_ingresos"] for t in timeline)
        total_egresos = sum(t["total_egresos"] for t in timeline)

        return {
            "timeline": timeline,
            "totales": {
                "ingresos": total_ingresos,
                "egresos": total_egresos,
                "flujo_neto": total_ingresos - total_egresos,
            },
            "agrupacion": agrupacion,
            "fecha_desde": fecha_desde.isoformat(),
            "fecha_hasta": fecha_hasta.isoformat(),
            "source": "tesoreria",
        }
