"""
Catálogo de AFPs (Habitat, Integra, Prima, Profuturo).
Las tasas (aporte obligatorio, prima seguros, comisiones) se mantienen aquí
y se actualizan mensualmente según publicación de la SBS.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
from database import get_pool
from dependencies import get_empresa_id

router = APIRouter(tags=["AFP"])


class AfpIn(BaseModel):
    codigo: str
    nombre: str
    aporte_obligatorio_pct: float = Field(ge=0)
    prima_seguro_pct: float = Field(ge=0)
    comision_flujo_pct: Optional[float] = None
    comision_saldo_pct: Optional[float] = None
    remuneracion_maxima_asegurable: Optional[float] = None
    vigente_desde: Optional[date] = None
    activo: Optional[bool] = True
    notas: Optional[str] = None


@router.get("/afp")
async def list_afp(
    activo: Optional[bool] = True,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        q = "SELECT * FROM finanzas2.fin_afp WHERE empresa_id = $1"
        params = [empresa_id]
        if activo is not None:
            q += " AND activo = $2"
            params.append(activo)
        q += " ORDER BY nombre"
        rows = await conn.fetch(q, *params)
        return [dict(r) for r in rows]


@router.get("/afp/{afp_id}")
async def get_afp(afp_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM finanzas2.fin_afp WHERE id = $1 AND empresa_id = $2",
            afp_id, empresa_id,
        )
        if not row:
            raise HTTPException(404, "AFP no encontrada")
        return dict(row)


@router.put("/afp/{afp_id}")
async def update_afp(
    afp_id: int,
    data: AfpIn,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            UPDATE finanzas2.fin_afp SET
                codigo = $1, nombre = $2,
                aporte_obligatorio_pct = $3,
                prima_seguro_pct = $4,
                comision_flujo_pct = $5,
                comision_saldo_pct = $6,
                remuneracion_maxima_asegurable = $7,
                vigente_desde = $8,
                activo = $9,
                notas = $10,
                updated_at = NOW()
            WHERE id = $11 AND empresa_id = $12
            RETURNING *
        """, data.codigo, data.nombre,
             data.aporte_obligatorio_pct, data.prima_seguro_pct,
             data.comision_flujo_pct, data.comision_saldo_pct,
             data.remuneracion_maxima_asegurable, data.vigente_desde,
             data.activo if data.activo is not None else True,
             data.notas,
             afp_id, empresa_id)
        if not row:
            raise HTTPException(404, "AFP no encontrada")
        return dict(row)
