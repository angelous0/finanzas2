"""
Movimientos desde Producción — vista de lectura.
Consulta cross-schema a produccion.* para mostrar eventos productivos
que tienen impacto financiero (servicios externos, ingresos MP, entregas PT).
"""
from fastapi import APIRouter, Depends, Query
from database import get_pool
from dependencies import get_empresa_id
from typing import Optional
from datetime import date as _date, datetime as _datetime

router = APIRouter(tags=["movimientos-produccion"])


def _parse_date(s: Optional[str]) -> Optional[_date]:
    """Convierte 'YYYY-MM-DD' a date; devuelve None si está vacío o inválido."""
    if not s:
        return None
    try:
        return _datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


@router.get("/movimientos-produccion")
async def get_movimientos_produccion(
    empresa_id: int = Depends(get_empresa_id),
    fecha_desde: Optional[str] = Query(None),
    fecha_hasta: Optional[str] = Query(None),
    tipo: Optional[str] = Query(None),  # servicio|ingreso_mp|entrega_pt
):
    d_desde = _parse_date(fecha_desde)
    d_hasta = _parse_date(fecha_hasta)
    pool = await get_pool()
    async with pool.acquire() as conn:
        items = []
        resumen = {"total_servicios": 0, "total_ingresos_mp": 0, "total_entregas_pt": 0,
                   "monto_servicios": 0, "monto_ingresos_mp": 0, "monto_entregas_pt": 0}

        # 1. Servicios externos → egresos (from prod_movimientos_produccion)
        if not tipo or tipo == "servicio":
            date_filter = ""
            params = [empresa_id]
            idx = 2
            if d_desde:
                date_filter += f" AND mp.fecha_inicio >= ${idx}"
                params.append(d_desde); idx += 1
            if d_hasta:
                date_filter += f" AND mp.fecha_inicio <= ${idx}"
                params.append(d_hasta); idx += 1

            rows = await conn.fetch(f"""
                SELECT
                    mp.id,
                    mp.cantidad_enviada, mp.cantidad_recibida,
                    mp.tarifa_aplicada as tarifa_unitaria,
                    mp.costo_calculado as costo_total,
                    mp.fecha_inicio, mp.fecha_fin,
                    sv.nombre as servicio_nombre,
                    p.nombre as persona_nombre,
                    r.n_corte,
                    mp.factura_numero,
                    mp.factura_id
                FROM produccion.prod_movimientos_produccion mp
                INNER JOIN produccion.prod_registros r ON mp.registro_id = r.id
                LEFT JOIN produccion.prod_servicios_produccion sv ON mp.servicio_id = sv.id
                LEFT JOIN produccion.prod_personas_produccion p ON mp.persona_id = p.id
                WHERE r.empresa_id = $1
                  AND COALESCE(mp.costo_calculado, 0) > 0
                  {date_filter}
                ORDER BY mp.fecha_inicio DESC NULLS LAST
                LIMIT 500
            """, *params)

            for r in rows:
                costo = float(r["costo_total"] or 0)
                items.append({
                    "tipo": "servicio",
                    "tipo_label": "Servicio Externo",
                    "impacto": "egreso",
                    "fecha": str(r["fecha_inicio"]) if r["fecha_inicio"] else None,
                    "descripcion": f"Corte {r['n_corte'] or '?'} — {r['servicio_nombre'] or 'Servicio'}",
                    "detalle": r["persona_nombre"] or "",
                    "cantidad": float(r["cantidad_recibida"] or r["cantidad_enviada"] or 0),
                    "monto": costo,
                    "estado": "FACTURADO" if r["factura_numero"] else "SIN FACTURA",
                    "factura_numero": r["factura_numero"],
                    "referencia_id": str(r["id"]),
                })
                resumen["total_servicios"] += 1
                resumen["monto_servicios"] += costo

        # 2. Ingresos de MP → costo
        if not tipo or tipo == "ingreso_mp":
            date_filter = ""
            params = [empresa_id]
            idx = 2
            if d_desde:
                date_filter += f" AND i.fecha >= ${idx}"
                params.append(d_desde); idx += 1
            if d_hasta:
                date_filter += f" AND i.fecha <= ${idx}"
                params.append(d_hasta); idx += 1

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
            if d_desde:
                date_filter += f" AND r.fecha_creacion >= ${idx}"
                params.append(d_desde); idx += 1
            if d_hasta:
                date_filter += f" AND r.fecha_creacion <= ${idx}"
                params.append(d_hasta); idx += 1

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


@router.get("/movimientos-produccion-finanzas")
async def get_movimientos_produccion_finanzas(
    empresa_id: int = Depends(get_empresa_id),
    fecha_desde: Optional[str] = Query(None),
    fecha_hasta: Optional[str] = Query(None),
    persona_nombre: Optional[str] = Query(None),
):
    """
    Movimientos individuales de prod_movimientos_produccion con estado de facturación.
    Usado en Finanzas → pestaña Servicios de Movimientos de Producción.
    """
    d_desde = _parse_date(fecha_desde)
    d_hasta = _parse_date(fecha_hasta)
    pool = await get_pool()
    async with pool.acquire() as conn:
        date_filter = ""
        params = [empresa_id]
        idx = 2

        if d_desde:
            date_filter += f" AND mp.fecha_inicio >= ${idx}"
            params.append(d_desde); idx += 1
        if d_hasta:
            date_filter += f" AND mp.fecha_inicio <= ${idx}"
            params.append(d_hasta); idx += 1
        if persona_nombre:
            date_filter += f" AND p.nombre ILIKE ${idx}"
            params.append(f"%{persona_nombre}%"); idx += 1

        rows = await conn.fetch(f"""
            SELECT
                mp.id,
                mp.costo_calculado,
                mp.cantidad_recibida,
                mp.fecha_inicio,
                mp.factura_numero,
                mp.factura_id,
                s.nombre  AS servicio_nombre,
                p.nombre  AS persona_nombre,
                r.n_corte AS registro_n_corte
            FROM produccion.prod_movimientos_produccion mp
            LEFT JOIN produccion.prod_servicios_produccion s ON mp.servicio_id = s.id
            LEFT JOIN produccion.prod_personas_produccion  p ON mp.persona_id  = p.id
            INNER JOIN produccion.prod_registros           r ON mp.registro_id = r.id
            WHERE r.empresa_id = $1
              AND COALESCE(mp.costo_calculado, 0) > 0
              {date_filter}
            ORDER BY mp.fecha_inicio DESC NULLS LAST
            LIMIT 500
        """, *params)

        items = []
        for r in rows:
            d = dict(r)
            if d.get("fecha_inicio"):
                d["fecha_inicio"] = str(d["fecha_inicio"])
            d["facturado"] = bool(d.get("factura_numero"))
            d["tipo"] = "movimiento"
            d["tipo_label"] = d.get("servicio_nombre") or "Servicio"
            d["descripcion"] = f"Corte {d.get('registro_n_corte') or '?'} — {d.get('servicio_nombre') or 'Servicio'}"
            d["detalle"] = d.get("persona_nombre") or ""
            d["monto"] = float(d.get("costo_calculado") or 0)
            d["cantidad"] = float(d.get("cantidad_recibida") or 0)
            d["fecha"] = d.get("fecha_inicio")
            items.append(d)

        return {"items": items, "total": len(items)}
