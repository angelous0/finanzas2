from fastapi import APIRouter, Depends
from typing import List, Optional
from database import get_pool
from models import ArticuloRef, ArticuloRefCreate
from dependencies import get_empresa_id
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/articulos", response_model=List[ArticuloRef])
async def list_articulos(search: Optional[str] = None, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        try:
            inv_rows = await conn.fetch("""
                SELECT id, id as prod_inventario_id,
                       COALESCE(codigo, '') as codigo,
                       COALESCE(nombre, descripcion, 'Sin nombre') as nombre,
                       descripcion, COALESCE(precio_ref, 0) as precio_referencia,
                       TRUE as activo, NOW() as created_at
                FROM produccion.prod_inventario
                WHERE ($1::text IS NULL OR nombre ILIKE $1 OR codigo ILIKE $1)
                LIMIT 100
            """, f"%{search}%" if search else None)
            if inv_rows:
                return [dict(r) for r in inv_rows]
        except Exception as e:
            logger.warning(f"Could not fetch from prod_inventario: {e}")
        query = "SELECT * FROM finanzas2.cont_articulo_ref WHERE activo = TRUE"
        if search:
            query += " AND (nombre ILIKE $1 OR codigo ILIKE $1)"
            rows = await conn.fetch(query + " ORDER BY nombre LIMIT 100", f"%{search}%")
        else:
            rows = await conn.fetch(query + " ORDER BY nombre LIMIT 100")
        return [dict(r) for r in rows]


@router.get("/inventario")
async def list_inventario(search: Optional[str] = None, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            search_param = f"%{search}%" if search else None
            rows = await conn.fetch("""
                SELECT id, codigo, nombre, descripcion, categoria, unidad_medida,
                       COALESCE(stock_actual, 0) as stock_actual,
                       COALESCE(stock_minimo, 0) as stock_minimo,
                       COALESCE(precio_ref, 0) as precio_ref,
                       COALESCE(costo_compra, 0) as costo_compra,
                       modelo, marca, activo
                FROM produccion.prod_inventario
                WHERE ($1::text IS NULL OR nombre ILIKE $1 OR codigo ILIKE $1 OR descripcion ILIKE $1)
                ORDER BY nombre LIMIT 200
            """, search_param)
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Error fetching inventario: {e}")
            return []


@router.get("/modelos-cortes")
async def list_modelos_cortes(search: Optional[str] = None, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            search_param = f"%{search}%" if search else None
            rows = await conn.fetch("""
                SELECT r.id, r.n_corte, r.modelo_id, r.estado,
                       m.nombre as modelo_nombre,
                       CONCAT(m.nombre, ' - Corte ', r.n_corte) as display_name
                FROM produccion.prod_registros r
                LEFT JOIN produccion.prod_modelos m ON r.modelo_id = m.id
                WHERE ($1::text IS NULL OR m.nombre ILIKE $1 OR r.n_corte ILIKE $1)
                ORDER BY r.fecha_creacion DESC LIMIT 200
            """, search_param)
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Error fetching modelos/cortes: {e}")
            return []


@router.get("/modelos")
async def list_modelos(search: Optional[str] = None, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            search_param = f"%{search}%" if search else None
            rows = await conn.fetch("""
                SELECT id, nombre FROM produccion.prod_modelos
                WHERE ($1::text IS NULL OR nombre ILIKE $1)
                ORDER BY nombre LIMIT 100
            """, search_param)
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Error fetching modelos: {e}")
            return []


@router.post("/articulos", response_model=ArticuloRef)
async def create_articulo(data: ArticuloRefCreate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        row = await conn.fetchrow("""
            INSERT INTO finanzas2.cont_articulo_ref
            (prod_inventario_id, codigo, nombre, descripcion, precio_referencia, activo, empresa_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
        """, data.prod_inventario_id, data.codigo, data.nombre, data.descripcion,
            data.precio_referencia, data.activo, empresa_id)
        return dict(row)
