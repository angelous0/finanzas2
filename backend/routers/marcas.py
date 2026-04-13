from fastapi import APIRouter, HTTPException, Depends
from database import get_pool
from dependencies import get_empresa_id
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/marcas")
async def list_marcas(empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        rows = await conn.fetch(
            "SELECT * FROM cont_marca WHERE empresa_id = $1 ORDER BY nombre", empresa_id
        )
        return [dict(r) for r in rows]


@router.post("/marcas")
async def create_marca(data: dict, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        row = await conn.fetchrow("""
            INSERT INTO cont_marca (empresa_id, nombre, codigo, odoo_marca_key, activo)
            VALUES ($1, $2, $3, $4, $5) RETURNING *
        """, empresa_id, data['nombre'], data.get('codigo'), data.get('odoo_marca_key'), data.get('activo', True))
        return dict(row)


@router.put("/marcas/{marca_id}")
async def update_marca(marca_id: int, data: dict, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        row = await conn.fetchrow("""
            UPDATE cont_marca SET nombre=$1, codigo=$2, odoo_marca_key=$3, activo=$4
            WHERE id=$5 AND empresa_id=$6 RETURNING *
        """, data['nombre'], data.get('codigo'), data.get('odoo_marca_key'), data.get('activo', True), marca_id, empresa_id)
        if not row:
            raise HTTPException(404, "Marca no encontrada")
        return dict(row)


@router.delete("/marcas/{marca_id}")
async def delete_marca(marca_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        r = await conn.execute("DELETE FROM cont_marca WHERE id=$1 AND empresa_id=$2", marca_id, empresa_id)
        if r == "DELETE 0":
            raise HTTPException(404, "Marca no encontrada")
        return {"message": "Marca eliminada"}
