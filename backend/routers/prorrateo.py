from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel
from database import get_pool
from dependencies import get_empresa_id
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class ProrrateoLinea(BaseModel):
    linea_negocio_id: int
    porcentaje: float
    monto: float


class ProrrateoRequest(BaseModel):
    gasto_id: int
    metodo: str  # 'ventas_mes', 'ventas_rango', 'manual'
    periodo_desde: Optional[date] = None
    periodo_hasta: Optional[date] = None
    lineas: Optional[List[ProrrateoLinea]] = None  # solo para metodo='manual'


# =====================
# GASTOS PENDIENTES DE PRORRATEO
# =====================
@router.get("/prorrateo/pendientes")
async def get_gastos_pendientes_prorrateo(
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        conditions = ["g.empresa_id = $1"]
        conditions.append("(g.tipo_asignacion = 'comun' OR (g.tipo_asignacion = 'no_asignado' AND g.linea_negocio_id IS NULL))")
        conditions.append("NOT EXISTS (SELECT 1 FROM cont_prorrateo_gasto p WHERE p.gasto_id = g.id)")
        params = [empresa_id]
        idx = 2
        if fecha_desde:
            conditions.append(f"g.fecha >= ${idx}")
            params.append(fecha_desde)
            idx += 1
        if fecha_hasta:
            conditions.append(f"g.fecha <= ${idx}")
            params.append(fecha_hasta)
            idx += 1

        rows = await conn.fetch(f"""
            SELECT g.id, g.numero, g.fecha, g.total, g.beneficiario_nombre,
                   g.tipo_asignacion, g.notas, g.centro_costo_id, g.marca_id,
                   cg.nombre as categoria_gasto_nombre,
                   cc.nombre as centro_costo_nombre,
                   ma.nombre as marca_nombre
            FROM cont_gasto g
            LEFT JOIN cont_categoria_gasto cg ON g.categoria_gasto_id = cg.id
            LEFT JOIN cont_centro_costo cc ON g.centro_costo_id = cc.id
            LEFT JOIN cont_marca ma ON g.marca_id = ma.id
            WHERE {' AND '.join(conditions)}
            ORDER BY g.fecha DESC
        """, *params)
        return [dict(r) for r in rows]


# =====================
# PREVIEW PRORRATEO (calcular sin guardar)
# =====================
@router.post("/prorrateo/preview")
async def preview_prorrateo(data: ProrrateoRequest, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        gasto = await conn.fetchrow(
            "SELECT id, fecha, total FROM cont_gasto WHERE id=$1 AND empresa_id=$2", data.gasto_id, empresa_id)
        if not gasto:
            raise HTTPException(404, "Gasto no encontrado")

        if data.metodo == 'manual' and data.lineas:
            return {"lineas": [l.dict() for l in data.lineas], "metodo": "manual"}

        # Calcular rango de fechas
        if data.metodo == 'ventas_rango' and data.periodo_desde and data.periodo_hasta:
            fd = data.periodo_desde
            fh = data.periodo_hasta
        else:
            # ventas_mes: mismo mes del gasto
            gasto_fecha = gasto['fecha']
            fd = gasto_fecha.replace(day=1)
            if gasto_fecha.month == 12:
                fh = gasto_fecha.replace(year=gasto_fecha.year + 1, month=1, day=1)
            else:
                fh = gasto_fecha.replace(month=gasto_fecha.month + 1, day=1)

        # Ingresos confirmados por linea de negocio
        rows = await conn.fetch("""
            SELECT da.linea_negocio_id, ln.nombre as linea_negocio_nombre, SUM(da.monto) as ingreso
            FROM cont_distribucion_analitica da
            JOIN cont_linea_negocio ln ON ln.id = da.linea_negocio_id
            WHERE da.empresa_id = $1 AND da.origen_tipo = 'venta_pos_ingreso'
              AND da.fecha >= $2 AND da.fecha < $3
            GROUP BY da.linea_negocio_id, ln.nombre
            HAVING SUM(da.monto) > 0
        """, empresa_id, fd, fh)

        if not rows:
            return {"lineas": [], "metodo": data.metodo, "mensaje": "No hay ingresos confirmados en el periodo"}

        total_ingresos = sum(float(r['ingreso']) for r in rows)
        monto_gasto = float(gasto['total'])
        lineas = []
        restante = monto_gasto
        for i, r in enumerate(rows):
            pct = float(r['ingreso']) / total_ingresos * 100
            if i == len(rows) - 1:
                monto_linea = round(restante, 2)
            else:
                monto_linea = round(monto_gasto * pct / 100, 2)
                restante -= monto_linea
            lineas.append({
                "linea_negocio_id": r['linea_negocio_id'],
                "linea_negocio_nombre": r['linea_negocio_nombre'],
                "porcentaje": round(pct, 2),
                "monto": monto_linea,
                "ingreso_base": float(r['ingreso'])
            })
        return {"lineas": lineas, "metodo": data.metodo, "periodo_desde": str(fd), "periodo_hasta": str(fh), "total_ingresos": total_ingresos}


# =====================
# EJECUTAR PRORRATEO
# =====================
@router.post("/prorrateo/ejecutar")
async def ejecutar_prorrateo(data: ProrrateoRequest, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        gasto = await conn.fetchrow(
            "SELECT id, fecha, total, tipo_asignacion FROM cont_gasto WHERE id=$1 AND empresa_id=$2",
            data.gasto_id, empresa_id)
        if not gasto:
            raise HTTPException(404, "Gasto no encontrado")

        # Check not already prorated
        existing = await conn.fetchval(
            "SELECT COUNT(*) FROM cont_prorrateo_gasto WHERE gasto_id = $1", data.gasto_id)
        if existing > 0:
            raise HTTPException(400, "Este gasto ya fue prorrateado")

        # Get distribution lines
        if data.metodo == 'manual' and data.lineas:
            lineas = data.lineas
            fd = data.periodo_desde
            fh = data.periodo_hasta
        else:
            preview = await preview_prorrateo(data, empresa_id)
            if not preview.get('lineas'):
                raise HTTPException(400, "No hay ingresos para calcular prorrateo")
            lineas = [ProrrateoLinea(**{k: v for k, v in l.items() if k in ('linea_negocio_id', 'porcentaje', 'monto')}) for l in preview['lineas']]
            fd_raw = preview.get('periodo_desde')
            fh_raw = preview.get('periodo_hasta')
            fd = date.fromisoformat(fd_raw) if isinstance(fd_raw, str) else fd_raw
            fh = date.fromisoformat(fh_raw) if isinstance(fh_raw, str) else fh_raw

        async with conn.transaction():
            for linea in lineas:
                await conn.execute("""
                    INSERT INTO cont_prorrateo_gasto
                        (empresa_id, gasto_id, linea_negocio_id, monto, porcentaje, metodo, periodo_desde, periodo_hasta)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """, empresa_id, data.gasto_id, linea.linea_negocio_id, linea.monto, linea.porcentaje,
                    data.metodo, fd, fh)

            # Mark gasto as prorated
            await conn.execute(
                "UPDATE cont_gasto SET tipo_asignacion = 'comun' WHERE id = $1", data.gasto_id)

        return {"message": "Prorrateo ejecutado", "lineas_creadas": len(lineas)}


# =====================
# HISTORIAL DE PRORRATEOS
# =====================
@router.get("/prorrateo/historial")
async def get_historial_prorrateo(
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        conditions = ["p.empresa_id = $1"]
        params = [empresa_id]
        idx = 2
        if fecha_desde:
            conditions.append(f"g.fecha >= ${idx}")
            params.append(fecha_desde)
            idx += 1
        if fecha_hasta:
            conditions.append(f"g.fecha <= ${idx}")
            params.append(fecha_hasta)
            idx += 1

        rows = await conn.fetch(f"""
            SELECT g.id as gasto_id, g.numero, g.fecha, g.total as gasto_total,
                   g.beneficiario_nombre, cg.nombre as categoria_gasto_nombre,
                   p.id as prorrateo_id, p.linea_negocio_id, ln.nombre as linea_negocio_nombre,
                   p.monto, p.porcentaje, p.metodo, p.periodo_desde, p.periodo_hasta,
                   p.created_at as prorrateo_fecha
            FROM cont_prorrateo_gasto p
            JOIN cont_gasto g ON g.id = p.gasto_id
            JOIN cont_linea_negocio ln ON ln.id = p.linea_negocio_id
            LEFT JOIN cont_categoria_gasto cg ON g.categoria_gasto_id = cg.id
            WHERE {' AND '.join(conditions)}
            ORDER BY g.fecha DESC, g.id, ln.nombre
        """, *params)
        return [dict(r) for r in rows]


# =====================
# ELIMINAR PRORRATEO (revertir)
# =====================
@router.delete("/prorrateo/{gasto_id}")
async def eliminar_prorrateo(gasto_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        deleted = await conn.execute(
            "DELETE FROM cont_prorrateo_gasto WHERE gasto_id = $1 AND empresa_id = $2",
            gasto_id, empresa_id)
        return {"message": "Prorrateo eliminado"}
