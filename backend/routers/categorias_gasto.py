from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from database import get_pool
from dependencies import get_empresa_id

router = APIRouter()


# =====================
# MODELOS
# =====================
class CategoriaGastoBase(BaseModel):
    codigo: Optional[str] = None
    nombre: str
    activo: bool = True
    es_cif: bool = False

class CategoriaGastoCreate(CategoriaGastoBase):
    pass

class CategoriaGasto(CategoriaGastoBase):
    id: int
    empresa_id: Optional[int] = None


# =====================
# CRUD CATEGORIAS DE GASTO
# =====================
@router.get("/categorias-gasto", response_model=List[CategoriaGasto])
async def list_categorias_gasto(empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, empresa_id, codigo, nombre, activo, COALESCE(es_cif, false) as es_cif FROM finanzas2.cont_categoria_gasto WHERE empresa_id = $1 ORDER BY nombre",
            empresa_id)
        return [dict(r) for r in rows]


@router.post("/categorias-gasto", response_model=CategoriaGasto)
async def create_categoria_gasto(data: CategoriaGastoCreate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO finanzas2.cont_categoria_gasto (empresa_id, codigo, nombre, activo) VALUES ($1, $2, $3, $4) RETURNING *",
            empresa_id, data.codigo, data.nombre, data.activo)
        return dict(row)


@router.put("/categorias-gasto/{id}", response_model=CategoriaGasto)
async def update_categoria_gasto(id: int, data: CategoriaGastoCreate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE finanzas2.cont_categoria_gasto SET codigo=$1, nombre=$2, activo=$3 WHERE id=$4 AND empresa_id=$5 RETURNING *",
            data.codigo, data.nombre, data.activo, id, empresa_id)
        if not row:
            raise HTTPException(404, "Categoria de gasto no encontrada")
        return dict(row)


@router.delete("/categorias-gasto/{id}")
async def delete_categoria_gasto(id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM finanzas2.cont_categoria_gasto WHERE id=$1 AND empresa_id=$2", id, empresa_id)
        return {"message": "Eliminada"}
