from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
from datetime import date
from pydantic import BaseModel
from database import get_pool
from dependencies import get_empresa_id
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class CapitalMovCreate(BaseModel):
    linea_negocio_id: int
    marca_id: Optional[int] = None
    proyecto_id: Optional[int] = None
    fecha: date
    tipo_movimiento: str  # capital_inicial, aporte, retiro
    monto: float
    observacion: Optional[str] = None


class CapitalMovUpdate(BaseModel):
    fecha: Optional[date] = None
    tipo_movimiento: Optional[str] = None
    monto: Optional[float] = None
    observacion: Optional[str] = None


# ── CRUD ──

@router.get("/capital-linea-negocio")
async def list_capital_movimientos(
    linea_negocio_id: Optional[int] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        conds = ["c.empresa_id = $1"]
        params = [empresa_id]
        idx = 2
        if linea_negocio_id:
            conds.append(f"c.linea_negocio_id = ${idx}")
            params.append(linea_negocio_id)
            idx += 1
        where = " AND ".join(conds)
        rows = await conn.fetch(f"""
            SELECT c.*, ln.nombre as linea_negocio_nombre,
                   m.nombre as marca_nombre, p.nombre as proyecto_nombre
            FROM cont_capital_linea_negocio c
            LEFT JOIN cont_linea_negocio ln ON c.linea_negocio_id = ln.id
            LEFT JOIN cont_marca m ON c.marca_id = m.id
            LEFT JOIN cont_proyecto p ON c.proyecto_id = p.id
            WHERE {where}
            ORDER BY c.fecha DESC, c.id DESC
        """, *params)
        data = []
        for r in rows:
            d = dict(r)
            for k in ('fecha', 'created_at', 'updated_at'):
                if d.get(k) and hasattr(d[k], 'isoformat'):
                    d[k] = d[k].isoformat()
            data.append(d)
        return {"data": data, "total": len(data)}


@router.post("/capital-linea-negocio")
async def create_capital_movimiento(data: CapitalMovCreate, empresa_id: int = Depends(get_empresa_id)):
    if data.tipo_movimiento not in ('capital_inicial', 'aporte', 'retiro'):
        raise HTTPException(400, "tipo_movimiento invalido")
    if data.monto <= 0:
        raise HTTPException(400, "monto debe ser positivo")
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        row = await conn.fetchrow("""
            INSERT INTO cont_capital_linea_negocio
            (empresa_id, linea_negocio_id, marca_id, proyecto_id, fecha, tipo_movimiento, monto, observacion)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
        """, empresa_id, data.linea_negocio_id, data.marca_id, data.proyecto_id,
            data.fecha, data.tipo_movimiento, data.monto, data.observacion)
        return {"id": row['id'], "message": "Movimiento de capital registrado"}


@router.put("/capital-linea-negocio/{mov_id}")
async def update_capital_movimiento(mov_id: int, data: CapitalMovUpdate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        existing = await conn.fetchrow(
            "SELECT id FROM cont_capital_linea_negocio WHERE id=$1 AND empresa_id=$2", mov_id, empresa_id)
        if not existing:
            raise HTTPException(404, "Movimiento no encontrado")
        updates = []
        values = []
        idx = 1
        for field, value in data.model_dump(exclude_unset=True).items():
            updates.append(f"{field} = ${idx}")
            values.append(value)
            idx += 1
        if not updates:
            raise HTTPException(400, "No fields to update")
        values.append(mov_id)
        await conn.execute(
            f"UPDATE cont_capital_linea_negocio SET {', '.join(updates)}, updated_at=NOW() WHERE id=${idx}",
            *values)
        return {"message": "Movimiento actualizado"}


@router.delete("/capital-linea-negocio/{mov_id}")
async def delete_capital_movimiento(mov_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        result = await conn.execute(
            "DELETE FROM cont_capital_linea_negocio WHERE id=$1 AND empresa_id=$2", mov_id, empresa_id)
        if result == "DELETE 0":
            raise HTTPException(404, "Movimiento no encontrado")
        return {"message": "Movimiento eliminado"}


# ── RENTABILIDAD Y RECUPERACION POR LINEA ──

@router.get("/rentabilidad-linea-negocio")
async def rentabilidad_por_linea(
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    """
    Calculate per business line:
    - Vista 1: Rendimiento Economico (ingresos, costos, gastos, utilidad, ROI)
    - Vista 2: Recuperacion de Caja (capital invertido, cobrado, pagado, saldo)
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        today = date.today()
        if not fecha_desde:
            fecha_desde = date(today.year, 1, 1)
        if not fecha_hasta:
            fecha_hasta = today

        # Get all lineas de negocio
        lineas = await conn.fetch(
            "SELECT id, nombre FROM cont_linea_negocio WHERE empresa_id=$1 ORDER BY nombre", empresa_id)

        results = []
        totals = {
            "capital_total": 0, "ingresos": 0, "costos": 0, "gastos": 0,
            "utilidad": 0, "cobrado_real": 0, "pagado_real": 0
        }

        for ln in lineas:
            ln_id = ln['id']

            # Capital movements (all time)
            capital = await conn.fetchrow("""
                SELECT
                    COALESCE(SUM(monto) FILTER (WHERE tipo_movimiento IN ('capital_inicial', 'aporte')), 0) as invertido,
                    COALESCE(SUM(monto) FILTER (WHERE tipo_movimiento = 'retiro'), 0) as retirado
                FROM cont_capital_linea_negocio
                WHERE empresa_id = $1 AND linea_negocio_id = $2
            """, empresa_id, ln_id)
            capital_invertido = float(capital['invertido'])
            capital_retirado = float(capital['retirado'])
            capital_neto = capital_invertido - capital_retirado

            # ── VISTA 1: RENDIMIENTO ECONOMICO (devengado) ──

            # Ingresos confirmados (ventas POS con linea_negocio assigned via detail)
            # For now, use factura_proveedor_linea as proxy for costs
            ingresos_row = await conn.fetchrow("""
                SELECT COALESCE(SUM(pa.monto_aplicado), 0) as total
                FROM cont_pago_aplicacion pa
                JOIN cont_venta_pos_estado e ON pa.documento_id = e.odoo_order_id AND pa.empresa_id = e.empresa_id
                WHERE pa.empresa_id = $1
                  AND pa.tipo_documento = 'venta_pos_odoo'
                  AND pa.created_at::date BETWEEN $2 AND $3
            """, empresa_id, fecha_desde, fecha_hasta)
            # Since we don't have linea_negocio on sales yet, use treasury
            ingresos_tes = await conn.fetchrow("""
                SELECT COALESCE(SUM(monto), 0) as total
                FROM cont_movimiento_tesoreria
                WHERE empresa_id = $1 AND tipo = 'ingreso'
                  AND linea_negocio_id = $2
                  AND fecha BETWEEN $3 AND $4
            """, empresa_id, ln_id, fecha_desde, fecha_hasta)
            ingresos = float(ingresos_tes['total'])

            # Costos: facturas proveedor lines assigned to this linea
            costos_row = await conn.fetchrow("""
                SELECT COALESCE(SUM(fpl.importe), 0) as total
                FROM cont_factura_proveedor_linea fpl
                JOIN cont_factura_proveedor fp ON fpl.factura_id = fp.id
                WHERE fpl.empresa_id = $1
                  AND fpl.linea_negocio_id = $2
                  AND fp.fecha_factura BETWEEN $3 AND $4
            """, empresa_id, ln_id, fecha_desde, fecha_hasta)
            costos = float(costos_row['total'])

            # Gastos assigned to this linea
            gastos_row = await conn.fetchrow("""
                SELECT COALESCE(SUM(gl.importe), 0) as total
                FROM cont_gasto_linea gl
                JOIN cont_gasto g ON gl.gasto_id = g.id
                WHERE g.empresa_id = $1
                  AND gl.linea_negocio_id = $2
                  AND g.fecha BETWEEN $3 AND $4
            """, empresa_id, ln_id, fecha_desde, fecha_hasta)
            gastos = float(gastos_row['total'])

            utilidad = ingresos - costos - gastos
            roi = (utilidad / capital_neto * 100) if capital_neto > 0 else 0

            # ── VISTA 2: RECUPERACION DE CAJA (real cash) ──
            cobrado_real = await conn.fetchrow("""
                SELECT COALESCE(SUM(monto), 0) as total
                FROM cont_movimiento_tesoreria
                WHERE empresa_id = $1 AND tipo = 'ingreso'
                  AND linea_negocio_id = $2
                  AND fecha BETWEEN $3 AND $4
            """, empresa_id, ln_id, fecha_desde, fecha_hasta)

            pagado_real = await conn.fetchrow("""
                SELECT COALESCE(SUM(monto), 0) as total
                FROM cont_movimiento_tesoreria
                WHERE empresa_id = $1 AND tipo = 'egreso'
                  AND linea_negocio_id = $2
                  AND fecha BETWEEN $3 AND $4
            """, empresa_id, ln_id, fecha_desde, fecha_hasta)

            cobrado = float(cobrado_real['total'])
            pagado = float(pagado_real['total'])
            flujo_neto_caja = cobrado - pagado
            saldo_por_recuperar = capital_neto - flujo_neto_caja
            # Payback: estimate months to recover based on avg monthly net flow
            dias_periodo = max((fecha_hasta - fecha_desde).days, 1)
            flujo_mensual = flujo_neto_caja / (dias_periodo / 30) if dias_periodo > 0 else 0
            payback_meses = (saldo_por_recuperar / flujo_mensual) if flujo_mensual > 0 else None

            line_data = {
                "linea_negocio_id": ln_id,
                "linea_negocio": ln['nombre'],
                # Capital
                "capital_invertido": capital_invertido,
                "capital_retirado": capital_retirado,
                "capital_neto": capital_neto,
                # Rendimiento economico
                "ingresos": ingresos,
                "costos": costos,
                "gastos": gastos,
                "utilidad": utilidad,
                "roi_pct": round(roi, 2),
                # Recuperacion caja
                "cobrado_real": cobrado,
                "pagado_real": pagado,
                "flujo_neto_caja": flujo_neto_caja,
                "saldo_por_recuperar": saldo_por_recuperar,
                "payback_meses": round(payback_meses, 1) if payback_meses is not None else None,
                "flujo_mensual_promedio": round(flujo_mensual, 2),
            }
            results.append(line_data)

            totals["capital_total"] += capital_neto
            totals["ingresos"] += ingresos
            totals["costos"] += costos
            totals["gastos"] += gastos
            totals["utilidad"] += utilidad
            totals["cobrado_real"] += cobrado
            totals["pagado_real"] += pagado

        totals["roi_pct"] = round(totals["utilidad"] / totals["capital_total"] * 100, 2) if totals["capital_total"] > 0 else 0
        totals["flujo_neto_caja"] = totals["cobrado_real"] - totals["pagado_real"]
        totals["saldo_por_recuperar"] = totals["capital_total"] - totals["flujo_neto_caja"]

        return {
            "lineas": results,
            "totales": totals,
            "fecha_desde": fecha_desde.isoformat(),
            "fecha_hasta": fecha_hasta.isoformat(),
        }
