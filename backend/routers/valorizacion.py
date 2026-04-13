from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from database import get_pool
from dependencies import get_empresa_id
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/valorizacion-inventario")
async def valorizacion_inventario(
    categoria: Optional[str] = None,
    search: Optional[str] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    """FIFO inventory valuation report - optimized batch query."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        conditions = ["i.empresa_id = $1"]
        params = [empresa_id]
        idx = 2

        if categoria:
            conditions.append(f"i.categoria = ${idx}")
            params.append(categoria)
            idx += 1
        if search:
            conditions.append(f"(i.nombre ILIKE ${idx} OR i.codigo ILIKE ${idx})")
            params.append(f"%{search}%")
            idx += 1

        where = " AND ".join(conditions)

        # Single query: items + aggregated FIFO data via subquery
        items = await conn.fetch(f"""
            SELECT i.id, i.codigo, i.nombre, i.categoria, i.unidad_medida,
                   COALESCE(i.stock_actual, 0) as stock_actual,
                   COALESCE(i.costo_compra, 0) as costo_compra,
                   COALESCE(i.costo_promedio, 0) as costo_promedio,
                   i.tipo_articulo, i.marca, i.modelo,
                   COALESCE(fifo.stock_fifo, 0) as stock_fifo,
                   COALESCE(fifo.valor_fifo, 0) as valor_fifo
            FROM produccion.prod_inventario i
            LEFT JOIN LATERAL (
                SELECT SUM(ing.cantidad_disponible) as stock_fifo,
                       SUM(ing.cantidad_disponible * ing.costo_unitario) as valor_fifo
                FROM produccion.prod_inventario_ingresos ing
                WHERE ing.item_id = i.id AND ing.cantidad_disponible > 0
            ) fifo ON true
            WHERE {where}
            ORDER BY i.categoria, i.nombre
        """, *params)

        # Batch: get all FIFO lots for items with stock
        item_ids = [item['id'] for item in items if float(item['stock_fifo'] or 0) > 0]
        lotes_map = {}
        if item_ids:
            lotes = await conn.fetch("""
                SELECT item_id, id, cantidad_disponible, costo_unitario, fecha, numero_documento
                FROM produccion.prod_inventario_ingresos
                WHERE item_id = ANY($1) AND cantidad_disponible > 0
                ORDER BY item_id, fecha ASC
            """, item_ids)
            for l in lotes:
                iid = l['item_id']
                if iid not in lotes_map:
                    lotes_map[iid] = []
                lotes_map[iid].append({
                    "id": l['id'],
                    "cantidad_disponible": float(l['cantidad_disponible']),
                    "costo_unitario": float(l['costo_unitario']),
                    "fecha": l['fecha'].isoformat() if l['fecha'] else None,
                    "documento": l['numero_documento'],
                })

        result = []
        total_valor_fifo = 0
        total_valor_promedio = 0

        for item in items:
            stock = float(item['stock_actual'] or 0)
            costo_prom = float(item['costo_promedio'] or 0)
            valor_fifo = float(item['valor_fifo'] or 0)
            stock_fifo = float(item['stock_fifo'] or 0)
            costo_fifo_unitario = valor_fifo / stock_fifo if stock_fifo > 0 else 0
            valor_promedio = stock * costo_prom

            total_valor_fifo += valor_fifo
            total_valor_promedio += valor_promedio

            result.append({
                "id": item['id'],
                "codigo": item['codigo'],
                "nombre": item['nombre'],
                "categoria": item['categoria'],
                "unidad": item['unidad_medida'],
                "stock_actual": stock,
                "stock_fifo": stock_fifo,
                "costo_compra": float(item['costo_compra'] or 0),
                "costo_promedio": costo_prom,
                "costo_fifo_unitario": round(costo_fifo_unitario, 4),
                "valor_fifo": round(valor_fifo, 2),
                "valor_promedio": round(valor_promedio, 2),
                "tipo_articulo": item['tipo_articulo'],
                "marca": item['marca'],
                "lotes_fifo": lotes_map.get(item['id'], []),
            })

        categorias = await conn.fetch("""
            SELECT DISTINCT categoria FROM produccion.prod_inventario
            WHERE empresa_id = $1 AND categoria IS NOT NULL
            ORDER BY categoria
        """, empresa_id)

        return {
            "data": result,
            "total_articulos": len(result),
            "total_valor_fifo": round(total_valor_fifo, 2),
            "total_valor_promedio": round(total_valor_promedio, 2),
            "categorias": [c['categoria'] for c in categorias],
        }


@router.get("/valorizacion-inventario/{item_id}")
async def valorizacion_articulo_detalle(
    item_id: str,
    empresa_id: int = Depends(get_empresa_id),
):
    """Detail FIFO valuation for a single article with full lot history."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        item = await conn.fetchrow("""
            SELECT id, codigo, nombre, categoria, unidad_medida,
                   COALESCE(stock_actual, 0) as stock_actual,
                   COALESCE(costo_compra, 0) as costo_compra,
                   COALESCE(costo_promedio, 0) as costo_promedio
            FROM produccion.prod_inventario
            WHERE id = $1 AND empresa_id = $2
        """, item_id, empresa_id)
        if not item:
            raise HTTPException(404, "Articulo no encontrado")

        ingresos = await conn.fetch("""
            SELECT id, cantidad, cantidad_disponible, costo_unitario, fecha,
                   numero_documento, proveedor
            FROM produccion.prod_inventario_ingresos
            WHERE item_id = $1
            ORDER BY fecha ASC
        """, item_id)

        salidas = await conn.fetch("""
            SELECT id, cantidad, costo_total, detalle_fifo, fecha
            FROM produccion.prod_inventario_salidas
            WHERE item_id = $1
            ORDER BY fecha DESC LIMIT 20
        """, item_id)

        lotes_disponibles = [l for l in ingresos if float(l['cantidad_disponible'] or 0) > 0]
        valor_fifo = sum(float(l['cantidad_disponible']) * float(l['costo_unitario']) for l in lotes_disponibles)
        stock_fifo = sum(float(l['cantidad_disponible']) for l in lotes_disponibles)

        return {
            "articulo": {
                "id": item['id'],
                "codigo": item['codigo'],
                "nombre": item['nombre'],
                "categoria": item['categoria'],
                "unidad": item['unidad_medida'],
                "stock_actual": float(item['stock_actual']),
                "costo_compra": float(item['costo_compra']),
                "costo_promedio": float(item['costo_promedio']),
                "costo_fifo": round(valor_fifo / stock_fifo, 4) if stock_fifo > 0 else 0,
                "valor_fifo": round(valor_fifo, 2),
                "stock_fifo": stock_fifo,
            },
            "ingresos": [{
                "id": l['id'],
                "cantidad": float(l['cantidad']),
                "disponible": float(l['cantidad_disponible']),
                "costo_unitario": float(l['costo_unitario']),
                "fecha": l['fecha'].isoformat() if l['fecha'] else None,
                "documento": l['numero_documento'],
                "proveedor": l['proveedor'],
                "consumido": float(l['cantidad']) - float(l['cantidad_disponible']),
            } for l in ingresos],
            "salidas": [{
                "id": s['id'],
                "cantidad": float(s['cantidad']),
                "costo_total": float(s['costo_total'] or 0),
                "detalle_fifo": s['detalle_fifo'],
                "fecha": s['fecha'].isoformat() if s['fecha'] else None,
            } for s in salidas],
        }
