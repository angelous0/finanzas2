from fastapi import APIRouter, HTTPException, Depends
from database import get_pool
from dependencies import get_empresa_id
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/proyectos")
async def list_proyectos(empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        rows = await conn.fetch("""
            SELECT p.*, m.nombre as marca_nombre, l.nombre as linea_nombre, c.nombre as cc_nombre
            FROM cont_proyecto p
            LEFT JOIN cont_marca m ON m.id = p.marca_id
            LEFT JOIN cont_linea_negocio l ON l.id = p.linea_negocio_id
            LEFT JOIN cont_centro_costo c ON c.id = p.centro_costo_id
            WHERE p.empresa_id = $1 ORDER BY p.nombre
        """, empresa_id)
        return [dict(r) for r in rows]


@router.post("/proyectos")
async def create_proyecto(data: dict, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        int_or_none = lambda v: int(v) if v else None
        str_or_none = lambda v: v if v else None
        row = await conn.fetchrow("""
            INSERT INTO cont_proyecto (empresa_id, nombre, codigo, marca_id, linea_negocio_id,
                centro_costo_id, fecha_inicio, fecha_fin, presupuesto, estado, notas)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) RETURNING *
        """, empresa_id, data['nombre'], str_or_none(data.get('codigo')),
            int_or_none(data.get('marca_id')), int_or_none(data.get('linea_negocio_id')),
            int_or_none(data.get('centro_costo_id')),
            str_or_none(data.get('fecha_inicio')), str_or_none(data.get('fecha_fin')),
            float(data.get('presupuesto') or 0), data.get('estado', 'activo'),
            str_or_none(data.get('notas')))
        return dict(row)


@router.put("/proyectos/{proyecto_id}")
async def update_proyecto(proyecto_id: int, data: dict, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        int_or_none = lambda v: int(v) if v else None
        str_or_none = lambda v: v if v else None
        row = await conn.fetchrow("""
            UPDATE cont_proyecto SET nombre=$1, codigo=$2, marca_id=$3, linea_negocio_id=$4,
                centro_costo_id=$5, fecha_inicio=$6, fecha_fin=$7, presupuesto=$8, estado=$9, notas=$10
            WHERE id=$11 AND empresa_id=$12 RETURNING *
        """, data['nombre'], str_or_none(data.get('codigo')),
            int_or_none(data.get('marca_id')), int_or_none(data.get('linea_negocio_id')),
            int_or_none(data.get('centro_costo_id')),
            str_or_none(data.get('fecha_inicio')), str_or_none(data.get('fecha_fin')),
            float(data.get('presupuesto') or 0), data.get('estado', 'activo'),
            str_or_none(data.get('notas')),
            proyecto_id, empresa_id)
        if not row:
            raise HTTPException(404, "Proyecto no encontrado")
        return dict(row)


@router.delete("/proyectos/{proyecto_id}")
async def delete_proyecto(proyecto_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        r = await conn.execute("DELETE FROM cont_proyecto WHERE id=$1 AND empresa_id=$2", proyecto_id, empresa_id)
        if r == "DELETE 0":
            raise HTTPException(404, "Proyecto no encontrado")
        return {"message": "Proyecto eliminado"}
