"""
Movimientos desde Producción — vista de lectura.
Consulta cross-schema a produccion.* para mostrar eventos productivos
que tienen impacto financiero (servicios externos, ingresos MP, entregas PT).
"""
from fastapi import APIRouter, Depends, Query
from database import get_pool
from dependencies import get_empresa_id
from typing import Optional

router = APIRouter(tags=["movimientos-produccion"])


@router.get("/movimientos-produccion")
async def get_movimientos_produccion(
    empresa_id: int = Depends(get_empresa_id),
    fecha_desde: Optional[str] = Query(None),
    fecha_hasta: Optional[str] = Query(None),
    tipo: Optional[str] = Query(None),  # servicio|ingreso_mp|entrega_pt
):
    """
    Retorna eventos de producción con impacto financiero:
    1. Servicios externos (prod_servicio_orden) → egreso
    2. Ingresos de MP (prod_inventario_ingresos) → costo
    3. Entregas de PT (registros cerrados) → ingreso potencial
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        items = []
        resumen = {"total_servicios": 0, "total_ingresos_mp": 0, "total_entregas_pt": 0,
                   "monto_servicios": 0, "monto_ingresos_mp": 0, "monto_entregas_pt": 0}

        date_filter_s = ""
        date_filter_i = ""
        date_filter_r = ""
        params_s = [empresa_id]
        params_i = [empresa_id]
        params_r = [empresa_id]
        idx_s = 2
        idx_i = 2
        idx_r = 2

        if fecha_desde:
            date_filter_s += f" AND s.fecha_inicio >= ${idx_s}::date"
            params_s.append(fecha_desde)
            idx_s += 1
            date_filter_i += f" AND i.fecha >= ${idx_i}::date"
            params_i.append(fecha_desde)
            idx_i += 1
            date_filter_r += f" AND r.fecha_cierre >= ${idx_r}::date"
            params_r.append(fecha_desde)
            idx_r += 1

        if fecha_hasta:
            date_filter_s += f" AND s.fecha_inicio <= ${idx_s}::date"
            params_s.append(fecha_hasta)
            idx_s += 1
            date_filter_i += f" AND i.fecha <= ${idx_i}::date"
            params_i.append(fecha_hasta)
            idx_i += 1
            date_filter_r += f" AND r.fecha_cierre <= ${idx_r}::date"
            params_r.append(fecha_hasta)
            idx_r += 1

        # 1. Servicios externos → egresos
        if not tipo or tipo == "servicio":
            rows = await conn.fetch(f"""
                SELECT
                    s.id, s.orden_id, s.proveedor_texto,
                    s.descripcion, s.cantidad_enviada, s.cantidad_recibida,
                    s.tarifa_unitaria, s.costo_total, s.estado,
                    s.fecha_inicio, s.fecha_fin,
                    sv.nombre as servicio_nombre,
                    p.nombre as persona_nombre,
                    r.n_corte
                FROM produccion.prod_servicio_orden s
                LEFT JOIN produccion.prod_servicios_produccion sv ON s.servicio_id = sv.id
                LEFT JOIN produccion.prod_personas_produccion p ON s.persona_id = p.id
                LEFT JOIN produccion.prod_registros r ON s.orden_id = r.id
                WHERE s.empresa_id = $1
                  AND s.costo_total > 0
                  {date_filter_s}
                ORDER BY s.fecha_inicio DESC NULLS LAST
                LIMIT 500
            """, *params_s)

            for r in rows:
                items.append({
                    "tipo": "servicio",
                    "tipo_label": "Servicio Externo",
                    "impacto": "egreso",
                    "fecha": str(r["fecha_inicio"]) if r["fecha_inicio"] else None,
                    "descripcion": f"Corte {r['n_corte'] or '?'} — {r['servicio_nombre'] or r['descripcion'] or 'Servicio'}",
                    "detalle": r["proveedor_texto"] or r["persona_nombre"] or "",
                    "cantidad": r["cantidad_enviada"] or 0,
                    "monto": float(r["costo_total"] or 0),
                    "estado": r["estado"],
                    "referencia_id": r["id"],
                    "orden_id": r["orden_id"],
                })
                resumen["total_servicios"] += 1
                resumen["monto_servicios"] += float(r["costo_total"] or 0)

        # 2. Ingresos de MP → costo
        if not tipo or tipo == "ingreso_mp":
            rows = await conn.fetch(f"""
                SELECT
                    i.id, i.item_id, i.cantidad, i.costo_unitario,
                    (COALESCE(i.cantidad,0) * COALESCE(i.costo_unitario,0)) as costo_total,
                    i.proveedor, i.numero_documento, i.fecha, i.observaciones,
                    inv.codigo as articulo_codigo, inv.nombre as articulo_nombre
                FROM produccion.prod_inventario_ingresos i
                LEFT JOIN produccion.prod_inventario inv ON i.item_id = inv.id
                WHERE i.empresa_id = $1
                  AND COALESCE(i.costo_unitario, 0) > 0
                  {date_filter_i}
                ORDER BY i.fecha DESC NULLS LAST
                LIMIT 500
            """, *params_i)

            for r in rows:
                items.append({
                    "tipo": "ingreso_mp",
                    "tipo_label": "Ingreso MP",
                    "impacto": "costo",
                    "fecha": str(r["fecha"]) if r["fecha"] else None,
                    "descripcion": f"{r['articulo_codigo'] or ''} {r['articulo_nombre'] or 'Material'}".strip(),
                    "detalle": r["proveedor"] or "",
                    "cantidad": float(r["cantidad"] or 0),
                    "monto": float(r["costo_total"] or 0),
                    "estado": "REGISTRADO",
                    "referencia_id": r["id"],
                    "documento": r["numero_documento"],
                })
                resumen["total_ingresos_mp"] += 1
                resumen["monto_ingresos_mp"] += float(r["costo_total"] or 0)

        # 3. Entregas de PT (registros cerrados) → ingreso potencial
        if not tipo or tipo == "entrega_pt":
            rows = await conn.fetch(f"""
                SELECT
                    r.id, r.n_corte, r.modelo, r.marca,
                    r.cantidad_total, r.cantidad_entregada,
                    r.estado, r.fecha_cierre,
                    COALESCE(r.costo_total_servicios, 0) + COALESCE(r.costo_total_materiales, 0) as costo_produccion
                FROM produccion.prod_registros r
                WHERE r.empresa_id = $1
                  AND r.estado IN ('CERRADO', 'ENTREGADO')
                  AND r.fecha_cierre IS NOT NULL
                  {date_filter_r}
                ORDER BY r.fecha_cierre DESC NULLS LAST
                LIMIT 500
            """, *params_r)

            for r in rows:
                items.append({
                    "tipo": "entrega_pt",
                    "tipo_label": "Entrega PT",
                    "impacto": "ingreso",
                    "fecha": str(r["fecha_cierre"]) if r["fecha_cierre"] else None,
                    "descripcion": f"Corte {r['n_corte'] or '?'} — {r['modelo'] or ''} {r['marca'] or ''}".strip(),
                    "detalle": f"{r['cantidad_entregada'] or r['cantidad_total'] or 0} prendas",
                    "cantidad": int(r["cantidad_entregada"] or r["cantidad_total"] or 0),
                    "monto": float(r["costo_produccion"] or 0),
                    "estado": r["estado"],
                    "referencia_id": r["id"],
                })
                resumen["total_entregas_pt"] += 1
                resumen["monto_entregas_pt"] += float(r["costo_produccion"] or 0)

        # Sort all items by date desc
        items.sort(key=lambda x: x.get("fecha") or "", reverse=True)

        resumen["monto_servicios"] = round(resumen["monto_servicios"], 2)
        resumen["monto_ingresos_mp"] = round(resumen["monto_ingresos_mp"], 2)
        resumen["monto_entregas_pt"] = round(resumen["monto_entregas_pt"], 2)

        return {"items": items, "resumen": resumen, "total": len(items)}
