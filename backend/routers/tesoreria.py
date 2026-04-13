from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from datetime import date, datetime
from database import get_pool
from dependencies import get_empresa_id
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class MovimientoTesoreriaCreate(BaseModel):
    fecha: date
    tipo: str  # 'ingreso' or 'egreso'
    monto: float
    cuenta_financiera_id: Optional[int] = None
    forma_pago: Optional[str] = None
    referencia: Optional[str] = None
    concepto: Optional[str] = None
    origen_tipo: str = 'manual'
    origen_id: Optional[int] = None
    marca_id: Optional[int] = None
    linea_negocio_id: Optional[int] = None
    centro_costo_id: Optional[int] = None
    proyecto_id: Optional[int] = None
    notas: Optional[str] = None


@router.get("/tesoreria")
async def list_movimientos_tesoreria(
    tipo: Optional[str] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    origen_tipo: Optional[str] = None,
    cuenta_financiera_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 50,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        conditions = ["mt.empresa_id = $1"]
        params = [empresa_id]
        idx = 2

        if tipo:
            conditions.append(f"mt.tipo = ${idx}")
            params.append(tipo)
            idx += 1
        if fecha_desde:
            conditions.append(f"mt.fecha >= ${idx}")
            params.append(fecha_desde)
            idx += 1
        if fecha_hasta:
            conditions.append(f"mt.fecha <= ${idx}")
            params.append(fecha_hasta)
            idx += 1
        if origen_tipo:
            conditions.append(f"mt.origen_tipo = ${idx}")
            params.append(origen_tipo)
            idx += 1
        if cuenta_financiera_id:
            conditions.append(f"mt.cuenta_financiera_id = ${idx}")
            params.append(cuenta_financiera_id)
            idx += 1

        where = ' AND '.join(conditions)
        count = await conn.fetchval(f"SELECT COUNT(*) FROM cont_movimiento_tesoreria mt WHERE {where}", *params)
        offset = (page - 1) * page_size

        rows = await conn.fetch(f"""
            SELECT mt.*,
                   cf.nombre as cuenta_nombre,
                   m.nombre as marca_nombre,
                   ln.nombre as linea_negocio_nombre,
                   cc.nombre as centro_costo_nombre,
                   p.nombre as proyecto_nombre
            FROM cont_movimiento_tesoreria mt
            LEFT JOIN cont_cuenta_financiera cf ON mt.cuenta_financiera_id = cf.id
            LEFT JOIN cont_marca m ON mt.marca_id = m.id
            LEFT JOIN cont_linea_negocio ln ON mt.linea_negocio_id = ln.id
            LEFT JOIN cont_centro_costo cc ON mt.centro_costo_id = cc.id
            LEFT JOIN cont_proyecto p ON mt.proyecto_id = p.id
            WHERE {where}
            ORDER BY mt.fecha DESC, mt.id DESC
            LIMIT {page_size} OFFSET {offset}
        """, *params)

        data = [dict(r) for r in rows]
        for d in data:
            for k in ('fecha', 'created_at', 'updated_at'):
                if d.get(k) and hasattr(d[k], 'isoformat'):
                    d[k] = d[k].isoformat()

        return {
            "data": data,
            "total": count,
            "page": page,
            "page_size": page_size,
        }


@router.get("/tesoreria/resumen")
async def resumen_tesoreria(
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    """KPIs de tesoreria real: ingresos, egresos, flujo neto, por tipo de origen."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        today = date.today()
        if not fecha_desde:
            fecha_desde = today.replace(day=1)
        if not fecha_hasta:
            fecha_hasta = today

        totals = await conn.fetchrow("""
            SELECT
                COALESCE(SUM(monto) FILTER (WHERE tipo = 'ingreso'), 0) as total_ingresos,
                COALESCE(SUM(monto) FILTER (WHERE tipo = 'egreso'), 0) as total_egresos,
                COUNT(*) FILTER (WHERE tipo = 'ingreso') as count_ingresos,
                COUNT(*) FILTER (WHERE tipo = 'egreso') as count_egresos
            FROM cont_movimiento_tesoreria
            WHERE empresa_id = $1 AND fecha BETWEEN $2 AND $3
        """, empresa_id, fecha_desde, fecha_hasta)

        by_origen = await conn.fetch("""
            SELECT origen_tipo, tipo,
                   COUNT(*) as cnt,
                   COALESCE(SUM(monto), 0) as total
            FROM cont_movimiento_tesoreria
            WHERE empresa_id = $1 AND fecha BETWEEN $2 AND $3
            GROUP BY origen_tipo, tipo
            ORDER BY total DESC
        """, empresa_id, fecha_desde, fecha_hasta)

        # Saldos de cuentas financieras
        cuentas = await conn.fetch("""
            SELECT id, nombre, tipo, saldo_actual
            FROM cont_cuenta_financiera
            WHERE empresa_id = $1 AND activo = TRUE
            ORDER BY tipo, nombre
        """, empresa_id)

        saldo_caja = sum(float(c['saldo_actual'] or 0) for c in cuentas if c['tipo'] == 'caja')
        saldo_banco = sum(float(c['saldo_actual'] or 0) for c in cuentas if c['tipo'] != 'caja')

        total_in = float(totals['total_ingresos'])
        total_out = float(totals['total_egresos'])

        return {
            "total_ingresos": total_in,
            "total_egresos": total_out,
            "flujo_neto": total_in - total_out,
            "count_ingresos": int(totals['count_ingresos']),
            "count_egresos": int(totals['count_egresos']),
            "saldo_caja": saldo_caja,
            "saldo_banco": saldo_banco,
            "saldo_total": saldo_caja + saldo_banco,
            "por_origen": [{"origen_tipo": r['origen_tipo'], "tipo": r['tipo'],
                           "count": int(r['cnt']), "total": float(r['total'])} for r in by_origen],
            "cuentas": [{"id": c['id'], "nombre": c['nombre'], "tipo": c['tipo'],
                        "saldo": float(c['saldo_actual'] or 0)} for c in cuentas],
            "fecha_desde": fecha_desde.isoformat(),
            "fecha_hasta": fecha_hasta.isoformat(),
        }


@router.post("/tesoreria")
async def create_movimiento_manual(
    data: MovimientoTesoreriaCreate,
    empresa_id: int = Depends(get_empresa_id),
):
    """Create a manual treasury movement (transfers, adjustments, etc.)."""
    if data.tipo not in ('ingreso', 'egreso'):
        raise HTTPException(400, "tipo debe ser 'ingreso' o 'egreso'")
    if data.monto <= 0:
        raise HTTPException(400, "monto debe ser positivo")

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        from services.treasury_service import create_movimiento_tesoreria
        mov_id = await create_movimiento_tesoreria(
            conn, empresa_id, data.fecha, data.tipo, data.monto,
            cuenta_financiera_id=data.cuenta_financiera_id,
            forma_pago=data.forma_pago,
            referencia=data.referencia,
            concepto=data.concepto,
            origen_tipo=data.origen_tipo,
            origen_id=data.origen_id,
            marca_id=data.marca_id,
            linea_negocio_id=data.linea_negocio_id,
            centro_costo_id=data.centro_costo_id,
            proyecto_id=data.proyecto_id,
            notas=data.notas,
        )
        return {"id": mov_id, "message": "Movimiento de tesoreria creado"}
