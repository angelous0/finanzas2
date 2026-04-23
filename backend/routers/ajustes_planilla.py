"""
Ajustes globales de Planilla (1 fila por empresa).
Configura: sueldo mínimo, horas quincena default, % asignación familiar.
Estos valores se usan en cálculos automáticos al crear/ver trabajadores.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from database import get_pool
from dependencies import get_empresa_id

router = APIRouter(tags=["Ajustes Planilla"])


class AjustesPlanillaIn(BaseModel):
    sueldo_minimo: float = Field(gt=0)
    horas_quincena_default: int = Field(gt=0)
    asignacion_familiar_pct: float = Field(ge=0)


@router.get("/ajustes-planilla")
async def get_ajustes(empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM finanzas2.fin_ajustes_planilla WHERE empresa_id = $1",
            empresa_id,
        )
        if not row:
            # si alguien crea una empresa nueva, inicializar con defaults
            await conn.execute("""
                INSERT INTO finanzas2.fin_ajustes_planilla
                    (empresa_id, sueldo_minimo, horas_quincena_default, asignacion_familiar_pct)
                VALUES ($1, 1130.00, 120, 10.00)
            """, empresa_id)
            row = await conn.fetchrow(
                "SELECT * FROM finanzas2.fin_ajustes_planilla WHERE empresa_id = $1",
                empresa_id,
            )
        return dict(row)


@router.put("/ajustes-planilla")
async def update_ajustes(
    data: AjustesPlanillaIn,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Upsert por si no existe todavía
        row = await conn.fetchrow("""
            INSERT INTO finanzas2.fin_ajustes_planilla
                (empresa_id, sueldo_minimo, horas_quincena_default, asignacion_familiar_pct, updated_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (empresa_id) DO UPDATE SET
                sueldo_minimo = EXCLUDED.sueldo_minimo,
                horas_quincena_default = EXCLUDED.horas_quincena_default,
                asignacion_familiar_pct = EXCLUDED.asignacion_familiar_pct,
                updated_at = NOW()
            RETURNING *
        """, empresa_id, data.sueldo_minimo, data.horas_quincena_default, data.asignacion_familiar_pct)
        return dict(row)
