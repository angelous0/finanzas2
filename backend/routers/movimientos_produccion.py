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
    pool = await get_pool()
    async with pool.acquire() as conn:
        items = []
        resumen = {"total_servicios": 0, "total_ingresos_mp": 0, "total_entregas_pt": 0,
                   "monto_servicios": 0, "monto_ingresos_mp": 0, "monto_entregas_pt": 0}

        # 1. Servicios externos → egresos
        if not tipo or tipo == "servicio":
            date_filter = ""
            params = [empresa_id]
            idx = 2
            if fecha_desde:
                date_filter += f" AND s.fecha_inicio >= ${idx}::date"
                params.append(fecha_desde); idx += 1
            if fecha_hasta:
                date_filter += f" AND s.fecha_inicio <= ${idx}::date"
                params.append(fecha_hasta); idx += 1

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
                  AND COALESCE(s.costo_total, 0) > 0
                  {date_filter}
                ORDER BY s.fecha_inicio DESC NULLS LAST
                LIMIT 500
            """, *params)

            for r in rows:
                items.append({
                    "tipo": "servicio",
                    "tipo_label": "Servicio Externo",
                    "impacto": "egreso",
                    "fecha": str(r["fecha_inicio"]) if r["fecha_inicio"] else None,
                    "descripcion": f"Corte {r['n_corte'] or '?'} — {r['servicio_nombre'] or r['descripcion'] or 'Servicio'}",
                    "detalle": r["proveedor_texto"] or r["persona_nombre"] or "",
                    "cantidad": float(r["cantidad_enviada"] or 0),
                    "monto": float(r["costo_total"] or 0),
                    "estado": r["estado"],
                    "referencia_id": str(r["id"]),
                })
                resumen["total_servicios"] += 1
                resumen["monto_servicios"] += float(r["costo_total"] or 0)

        # 2. Ingresos de MP → costo
        if not tipo or tipo == "ingreso_mp":
            date_filter = ""
            params = [empresa_id]
            idx = 2
            if fecha_desde:
                date_filter += f" AND i.fecha >= ${idx}::date"
                params.append(fecha_desde); idx += 1
            if fecha_hasta:
                date_filter += f" AND i.fecha <= ${idx}::date"
                params.append(fecha_hasta); idx += 1

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
                  {date_filter}
                ORDER BY i.fecha DESC NULLS LAST
                LIMIT 500
            """, *params)

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
                    "referencia_id": str(r["id"]),
                })
                resumen["total_ingresos_mp"] += 1
                resumen["monto_ingresos_mp"] += float(r["costo_total"] or 0)

        # 3. Entregas de PT (registros con estado_op CERRADO) → ingreso potencial
        if not tipo or tipo == "entrega_pt":
            date_filter = ""
            params = [empresa_id]
            idx = 2
            if fecha_desde:
                date_filter += f" AND r.fecha_creacion >= ${idx}::date"
                params.append(fecha_desde); idx += 1
            if fecha_hasta:
                date_filter += f" AND r.fecha_creacion <= ${idx}::date"
                params.append(fecha_hasta); idx += 1

            rows = await conn.fetch(f"""
                SELECT
                    r.id, r.n_corte, r.estado, r.estado_op,
                    r.fecha_creacion,
                    m.nombre as modelo_nombre,
                    (SELECT COALESCE(SUM((elem->>'cantidad')::int), 0)
                     FROM jsonb_array_elements(COALESCE(r.tallas, '[]'::jsonb)) elem
                     WHERE elem->>'cantidad' IS NOT NULL) as total_prendas,
                    (SELECT COALESCE(SUM(so.costo_total), 0)
                     FROM produccion.prod_servicio_orden so
                     WHERE so.orden_id = r.id) as costo_servicios
                FROM produccion.prod_registros r
                LEFT JOIN produccion.prod_modelos m ON r.modelo_id = m.id
                WHERE r.empresa_id = $1
                  AND r.estado_op IN ('CERRADO', 'ENTREGADO')
                  {date_filter}
                ORDER BY r.fecha_creacion DESC NULLS LAST
                LIMIT 500
            """, *params)

            for r in rows:
                costo_prod = float(r["costo_servicios"] or 0)
                items.append({
                    "tipo": "entrega_pt",
                    "tipo_label": "Entrega PT",
                    "impacto": "ingreso",
                    "fecha": str(r["fecha_creacion"]) if r["fecha_creacion"] else None,
                    "descripcion": f"Corte {r['n_corte'] or '?'} — {r['modelo_nombre'] or ''}".strip(),
                    "detalle": f"{r['total_prendas'] or 0} prendas",
                    "cantidad": int(r["total_prendas"] or 0),
                    "monto": round(costo_prod, 2),
                    "estado": r["estado_op"] or r["estado"],
                    "referencia_id": str(r["id"]),
                })
                resumen["total_entregas_pt"] += 1
                resumen["monto_entregas_pt"] += costo_prod

        # Sort all items by date desc
        items.sort(key=lambda x: x.get("fecha") or "", reverse=True)

        resumen["monto_servicios"] = round(resumen["monto_servicios"], 2)
        resumen["monto_ingresos_mp"] = round(resumen["monto_ingresos_mp"], 2)
        resumen["monto_entregas_pt"] = round(resumen["monto_entregas_pt"], 2)

        return {"items": items, "resumen": resumen, "total": len(items)}
