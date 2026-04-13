from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from database import get_pool
from models import Presupuesto, PresupuestoCreate
from dependencies import get_empresa_id, safe_date_param

router = APIRouter()


async def get_presupuesto(id: int, emp_id: int = None) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        if emp_id:
            row = await conn.fetchrow("SELECT * FROM finanzas2.cont_presupuesto WHERE id = $1 AND empresa_id = $2", id, emp_id)
        else:
            row = await conn.fetchrow("SELECT * FROM finanzas2.cont_presupuesto WHERE id = $1", id)
        if not row:
            raise HTTPException(404, "Presupuesto not found")
        pres_dict = dict(row)
        lineas = await conn.fetch("""
            SELECT pl.*, c.nombre as categoria_nombre
            FROM finanzas2.cont_presupuesto_linea pl
            LEFT JOIN finanzas2.cont_categoria c ON pl.categoria_id = c.id
            WHERE pl.presupuesto_id = $1
        """, id)
        pres_dict['lineas'] = [dict(l) for l in lineas]
        return pres_dict


@router.get("/presupuestos", response_model=List[Presupuesto])
async def list_presupuestos(anio: Optional[int] = None, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        if anio:
            rows = await conn.fetch("SELECT * FROM finanzas2.cont_presupuesto WHERE anio = $1 ORDER BY version DESC", anio)
        else:
            rows = await conn.fetch("SELECT * FROM finanzas2.cont_presupuesto ORDER BY anio DESC, version DESC")
        result = []
        for row in rows:
            pres_dict = dict(row)
            lineas = await conn.fetch("""
                SELECT pl.*, c.nombre as categoria_nombre
                FROM finanzas2.cont_presupuesto_linea pl
                LEFT JOIN finanzas2.cont_categoria c ON pl.categoria_id = c.id
                WHERE pl.presupuesto_id = $1
            """, row['id'])
            pres_dict['lineas'] = [dict(l) for l in lineas]
            result.append(pres_dict)
        return result


@router.post("/presupuestos", response_model=Presupuesto)
async def create_presupuesto(data: PresupuestoCreate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        async with conn.transaction():
            version = await conn.fetchval(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM finanzas2.cont_presupuesto WHERE anio = $1", data.anio) or 1
            row = await conn.fetchrow("""
                INSERT INTO finanzas2.cont_presupuesto
                (nombre, anio, version, estado, notas, empresa_id)
                VALUES ($1, $2, $3, 'borrador', $4, $5)
                RETURNING *
            """, data.nombre, data.anio, version, data.notas, empresa_id)
            presupuesto_id = row['id']
            for linea in data.lineas:
                await conn.execute("""
                    INSERT INTO finanzas2.cont_presupuesto_linea
                    (presupuesto_id, categoria_id, centro_costo_id, linea_negocio_id, mes, monto_presupuestado, empresa_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, presupuesto_id, linea.categoria_id, linea.centro_costo_id,
                    linea.linea_negocio_id, linea.mes, linea.monto_presupuestado, empresa_id)
        return await get_presupuesto(presupuesto_id, empresa_id)


@router.get("/presupuestos/{id}", response_model=Presupuesto)
async def get_presupuesto_endpoint(id: int, empresa_id: int = Depends(get_empresa_id)):
    return await get_presupuesto(id, empresa_id)


@router.delete("/presupuestos/{id}")
async def delete_presupuesto(id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM finanzas2.cont_presupuesto WHERE id = $1 AND empresa_id = $2", id, empresa_id)
        if result == "DELETE 0":
            raise HTTPException(404, "Presupuesto no encontrado")
        return {"ok": True}


@router.put("/presupuestos/{id}")
async def update_presupuesto(id: int, data: PresupuestoCreate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("""
                UPDATE finanzas2.cont_presupuesto SET nombre=$1, notas=$2, updated_at=NOW()
                WHERE id=$3 AND empresa_id=$4
            """, data.nombre, data.notas, id, empresa_id)
            await conn.execute("DELETE FROM finanzas2.cont_presupuesto_linea WHERE presupuesto_id=$1", id)
            for linea in data.lineas:
                await conn.execute("""
                    INSERT INTO finanzas2.cont_presupuesto_linea
                    (presupuesto_id, categoria_id, centro_costo_id, linea_negocio_id, mes, monto_presupuestado, empresa_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, id, linea.categoria_id, linea.centro_costo_id,
                    linea.linea_negocio_id, linea.mes, linea.monto_presupuestado, empresa_id)
        return await get_presupuesto(id, empresa_id)
