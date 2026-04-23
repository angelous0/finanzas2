"""
unidades_internas.py - Unidades Internas de Producción (Gerencial)
Control gerencial para medir rentabilidad de servicios internos vs externos.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
from datetime import date
from database import get_pool
from dependencies import get_empresa_id
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

TIPOS_GASTO = [
    'PLANILLA_JORNAL', 'DESTAJO', 'GASTO_CORTE', 'ALQUILER',
    'LUZ', 'MANTENIMIENTO', 'OTRO'
]


# ════════════════════════════════════════
# UNIDADES INTERNAS - CRUD
# ════════════════════════════════════════

@router.get("/unidades-internas")
async def list_unidades_internas(empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        rows = await conn.fetch("""
            SELECT * FROM finanzas2.fin_unidad_interna
            WHERE empresa_id = $1 ORDER BY nombre
        """, empresa_id)
        return [dict(r) for r in rows]


@router.post("/unidades-internas")
async def create_unidad_interna(data: dict, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        row = await conn.fetchrow("""
            INSERT INTO finanzas2.fin_unidad_interna (nombre, tipo, activo, empresa_id)
            VALUES ($1, $2, $3, $4) RETURNING *
        """, data['nombre'], data.get('tipo', ''), True, empresa_id)
        return dict(row)


@router.put("/unidades-internas/{id}")
async def update_unidad_interna(id: int, data: dict, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        await conn.execute("""
            UPDATE finanzas2.fin_unidad_interna
            SET nombre=$1, tipo=$2, activo=$3, updated_at=NOW()
            WHERE id=$4 AND empresa_id=$5
        """, data['nombre'], data.get('tipo', ''), data.get('activo', True), id, empresa_id)
        row = await conn.fetchrow("SELECT * FROM finanzas2.fin_unidad_interna WHERE id=$1", id)
        return dict(row)


@router.delete("/unidades-internas/{id}")
async def delete_unidad_interna(id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        # Check if has cargos or gastos
        cargos = await conn.fetchval(
            "SELECT count(*) FROM finanzas2.fin_cargo_interno WHERE unidad_interna_id=$1", id)
        gastos = await conn.fetchval(
            "SELECT count(*) FROM finanzas2.fin_gasto_unidad_interna WHERE unidad_interna_id=$1", id)
        if cargos > 0 or gastos > 0:
            raise HTTPException(400, f"No se puede eliminar: tiene {cargos} cargos y {gastos} gastos asociados")
        await conn.execute("DELETE FROM finanzas2.fin_unidad_interna WHERE id=$1 AND empresa_id=$2", id, empresa_id)
        return {"message": "Eliminado"}


# ════════════════════════════════════════
# PERSONAS PRODUCCIÓN - tipo interno/externo
# ════════════════════════════════════════

@router.get("/personas-produccion")
async def list_personas_produccion(empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT p.id, p.nombre, p.tipo, p.telefono, p.activo,
                   COALESCE(p.tipo_persona, 'EXTERNO') as tipo_persona,
                   p.unidad_interna_id,
                   u.nombre as unidad_interna_nombre
            FROM produccion.prod_personas_produccion p
            LEFT JOIN finanzas2.fin_unidad_interna u ON p.unidad_interna_id = u.id
            WHERE p.activo = true
            ORDER BY p.nombre
        """)
        return [dict(r) for r in rows]


@router.put("/personas-produccion/{id}/tipo")
async def update_persona_tipo(id: str, data: dict, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        tipo_persona = data.get('tipo_persona', 'EXTERNO')
        unidad_id = data.get('unidad_interna_id')
        await conn.execute("""
            UPDATE produccion.prod_personas_produccion
            SET tipo_persona=$1, unidad_interna_id=$2
            WHERE id=$3
        """, tipo_persona, unidad_id if tipo_persona == 'INTERNO' else None, id)
        return {"message": "Actualizado"}


# ════════════════════════════════════════
# CARGOS INTERNOS
# ════════════════════════════════════════

@router.get("/cargos-internos")
async def list_cargos_internos(
    unidad_interna_id: Optional[int] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    con_nota: Optional[str] = None,  # "si" | "no" | None para todos
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        conditions = ["c.empresa_id = $1"]
        params = [empresa_id]
        idx = 2
        if unidad_interna_id:
            conditions.append(f"c.unidad_interna_id = ${idx}")
            params.append(unidad_interna_id); idx += 1
        if fecha_desde:
            conditions.append(f"c.fecha >= ${idx}")
            params.append(fecha_desde); idx += 1
        if fecha_hasta:
            conditions.append(f"c.fecha <= ${idx}")
            params.append(fecha_hasta); idx += 1
        if con_nota == "si":
            conditions.append("mp.factura_numero LIKE 'NI-%'")
        elif con_nota == "no":
            conditions.append("(mp.factura_numero IS NULL OR mp.factura_numero NOT LIKE 'NI-%')")
        rows = await conn.fetch(f"""
            SELECT
                c.*,
                u.nombre as unidad_nombre,
                r.n_corte as n_corte,
                COALESCE(m.nombre, r.modelo_manual->>'nombre_modelo') AS modelo_nombre,
                mp.factura_numero,
                CASE WHEN mp.factura_numero LIKE 'NI-%' THEN mp.factura_id ELSE NULL END AS nota_interna_id
            FROM finanzas2.fin_cargo_interno c
            LEFT JOIN finanzas2.fin_unidad_interna u ON c.unidad_interna_id = u.id
            LEFT JOIN produccion.prod_movimientos_produccion mp ON mp.id::text = c.movimiento_id
            LEFT JOIN produccion.prod_registros r ON r.id = c.registro_id
            LEFT JOIN produccion.prod_modelos m ON m.id = r.modelo_id
            WHERE {' AND '.join(conditions)}
            ORDER BY c.fecha DESC, c.id DESC
        """, *params)
        result = []
        for r in rows:
            d = dict(r)
            for k in d:
                if hasattr(d[k], 'isoformat'):
                    d[k] = d[k].isoformat()
                from decimal import Decimal
                if isinstance(d[k], Decimal):
                    d[k] = float(d[k])
            # Etiqueta visual
            d['tiene_nota_interna'] = bool(d.get('factura_numero') and str(d.get('factura_numero')).startswith('NI-'))
            result.append(d)
        return result


@router.post("/cargos-internos/generar")
async def generar_cargos_internos(empresa_id: int = Depends(get_empresa_id)):
    """
    Escanea movimientos de personas INTERNO sin cargo y los crea como CxC virtual.

    ⚠️ NUEVO FLUJO (post-migración): estos cargos se crean en estado 'generado'
    SIN tocar el saldo de la cuenta ficticia. Son CxC virtuales pendientes.

    Para que cuenten como ingreso efectivo, hay que:
    1. Generar una Nota Interna (NI) desde el reporte de Producción que los agrupe, O
    2. Procesar la NI asociada (si ya existe).

    Este endpoint sirve como utilidad para "detectar" movimientos internos no
    valorizados, pero el camino recomendado es crear las NIs desde Producción.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        movimientos = await conn.fetch("""
            SELECT m.id as movimiento_id, m.registro_id, m.servicio_id,
                   m.persona_id, m.cantidad_recibida, m.cantidad_enviada,
                   m.tarifa_aplicada, m.costo_calculado,
                   COALESCE(m.fecha_fin, m.fecha_inicio, m.created_at::date) as fecha,
                   p.nombre as persona_nombre, p.unidad_interna_id,
                   s.nombre as servicio_nombre,
                   r.n_corte, r.empresa_id
            FROM produccion.prod_movimientos_produccion m
            JOIN produccion.prod_personas_produccion p ON m.persona_id = p.id
            LEFT JOIN produccion.prod_servicios_produccion s ON m.servicio_id = s.id
            LEFT JOIN produccion.prod_registros r ON m.registro_id = r.id
            WHERE COALESCE(p.tipo_persona, 'EXTERNO') = 'INTERNO'
              AND p.unidad_interna_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM finanzas2.fin_cargo_interno ci
                  WHERE ci.movimiento_id = m.id
              )
        """)

        generados = 0
        total_importe = 0.0
        for mov in movimientos:
            cantidad = mov['cantidad_recibida'] or mov['cantidad_enviada'] or 0
            tarifa = float(mov['tarifa_aplicada'] or 0)
            importe = float(mov['costo_calculado'] or 0)
            if importe == 0 and tarifa > 0:
                importe = cantidad * tarifa
            if importe == 0:
                continue

            try:
                cargo_id = await conn.fetchval("""
                    INSERT INTO finanzas2.fin_cargo_interno
                    (fecha, registro_id, movimiento_id, unidad_interna_id,
                     servicio_nombre, persona_nombre, cantidad, tarifa, importe, estado, empresa_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'generado', $10)
                    ON CONFLICT (movimiento_id) DO NOTHING
                    RETURNING id
                """, mov['fecha'], mov['registro_id'], mov['movimiento_id'],
                    mov['unidad_interna_id'], mov['servicio_nombre'] or '',
                    mov['persona_nombre'] or '', cantidad, tarifa, importe,
                    empresa_id)
                if cargo_id is not None:
                    generados += 1
                    total_importe += importe
                # ⚠️ NO se crea fin_movimiento_cuenta ni se toca el saldo de la cuenta ficticia.
                #    El cargo queda como CxC virtual. Para materializar el ingreso, hay que
                #    generar y procesar una Nota Interna desde el reporte de Producción.
            except Exception as e:
                logger.warning(f"Error generating cargo for mov {mov['movimiento_id']}: {e}")

        return {
            "message": (
                f"{generados} cargo(s) creado(s) como CxC virtual por S/ {total_importe:.2f}. "
                "Para materializar el ingreso, generá Notas Internas desde Producción."
            ),
            "generados": generados,
            "total_importe": round(total_importe, 2),
            "nota": "Estos cargos NO tocan el saldo de la cuenta ficticia. Son CxC virtuales.",
        }


# ════════════════════════════════════════
# GASTOS UNIDAD INTERNA
# ════════════════════════════════════════

@router.get("/gastos-unidad-interna")
async def list_gastos_unidad_interna(
    unidad_interna_id: Optional[int] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        conditions = ["g.empresa_id = $1"]
        params = [empresa_id]
        idx = 2
        if unidad_interna_id:
            conditions.append(f"g.unidad_interna_id = ${idx}")
            params.append(unidad_interna_id); idx += 1
        if fecha_desde:
            conditions.append(f"g.fecha >= ${idx}")
            params.append(fecha_desde); idx += 1
        if fecha_hasta:
            conditions.append(f"g.fecha <= ${idx}")
            params.append(fecha_hasta); idx += 1
        rows = await conn.fetch(f"""
            SELECT g.*, u.nombre as unidad_nombre
            FROM finanzas2.fin_gasto_unidad_interna g
            LEFT JOIN finanzas2.fin_unidad_interna u ON g.unidad_interna_id = u.id
            WHERE {' AND '.join(conditions)}
            ORDER BY g.fecha DESC, g.id DESC
        """, *params)
        result = []
        for r in rows:
            d = dict(r)
            for k in d:
                if hasattr(d[k], 'isoformat'):
                    d[k] = d[k].isoformat()
                from decimal import Decimal
                if isinstance(d[k], Decimal):
                    d[k] = float(d[k])
            result.append(d)
        return result


@router.post("/gastos-unidad-interna")
async def create_gasto_unidad_interna(data: dict, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        from datetime import date as date_cls
        fecha_val = data['fecha']
        if isinstance(fecha_val, str):
            fecha_val = date_cls.fromisoformat(fecha_val)
        row = await conn.fetchrow("""
            INSERT INTO finanzas2.fin_gasto_unidad_interna
            (fecha, unidad_interna_id, tipo_gasto, descripcion, monto, registro_id, movimiento_id, empresa_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING *
        """, fecha_val, data['unidad_interna_id'], data['tipo_gasto'],
            data.get('descripcion', ''), data['monto'],
            data.get('registro_id'), data.get('movimiento_id'), empresa_id)
        d = dict(row)
        for k in d:
            if hasattr(d[k], 'isoformat'):
                d[k] = d[k].isoformat()
            from decimal import Decimal
            if isinstance(d[k], Decimal):
                d[k] = float(d[k])
        return d


@router.put("/gastos-unidad-interna/{id}")
async def update_gasto_unidad_interna(id: int, data: dict, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        from datetime import date as date_cls
        fecha_val = data['fecha']
        if isinstance(fecha_val, str):
            fecha_val = date_cls.fromisoformat(fecha_val)
        await conn.execute("""
            UPDATE finanzas2.fin_gasto_unidad_interna
            SET fecha=$1, unidad_interna_id=$2, tipo_gasto=$3, descripcion=$4,
                monto=$5, registro_id=$6, movimiento_id=$7, updated_at=NOW()
            WHERE id=$8 AND empresa_id=$9
        """, fecha_val, data['unidad_interna_id'], data['tipo_gasto'],
            data.get('descripcion', ''), data['monto'],
            data.get('registro_id'), data.get('movimiento_id'), id, empresa_id)
        return {"message": "Actualizado"}


@router.delete("/gastos-unidad-interna/{id}")
async def delete_gasto_unidad_interna(id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        await conn.execute(
            "DELETE FROM finanzas2.fin_gasto_unidad_interna WHERE id=$1 AND empresa_id=$2", id, empresa_id)
        return {"message": "Eliminado"}


@router.get("/tipos-gasto-unidad")
async def get_tipos_gasto():
    return TIPOS_GASTO


# ════════════════════════════════════════
# REPORTE GERENCIAL POR UNIDAD INTERNA
# ════════════════════════════════════════

@router.get("/reporte-unidades-internas")
async def reporte_unidades_internas(
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        date_cond_cargo = ""
        date_cond_gasto = ""
        params = [empresa_id]
        idx = 2
        if fecha_desde:
            date_cond_cargo += f" AND c.fecha >= ${idx}"
            date_cond_gasto += f" AND g.fecha >= ${idx}"
            params.append(fecha_desde); idx += 1
        if fecha_hasta:
            date_cond_cargo += f" AND c.fecha <= ${idx}"
            date_cond_gasto += f" AND g.fecha <= ${idx}"
            params.append(fecha_hasta); idx += 1

        # Get all active units
        unidades = await conn.fetch("""
            SELECT * FROM finanzas2.fin_unidad_interna
            WHERE empresa_id = $1 AND activo = true ORDER BY nombre
        """, empresa_id)

        # Cargos internos (ingresos) per unit
        cargos_agg = await conn.fetch(f"""
            SELECT c.unidad_interna_id,
                   COALESCE(SUM(c.importe), 0) as total_ingresos,
                   COALESCE(SUM(c.cantidad), 0) as total_cantidad,
                   COUNT(*) as num_cargos
            FROM finanzas2.fin_cargo_interno c
            WHERE c.empresa_id = $1 {date_cond_cargo}
            GROUP BY c.unidad_interna_id
        """, *params)
        cargos_map = {r['unidad_interna_id']: dict(r) for r in cargos_agg}

        # Gastos reales per unit (from fin_gasto_unidad_interna)
        gastos_agg = await conn.fetch(f"""
            SELECT g.unidad_interna_id,
                   COALESCE(SUM(g.monto), 0) as total_gastos,
                   COUNT(*) as num_gastos
            FROM finanzas2.fin_gasto_unidad_interna g
            WHERE g.empresa_id = $1 {date_cond_gasto}
            GROUP BY g.unidad_interna_id
        """, *params)
        gastos_map = {r['unidad_interna_id']: dict(r) for r in gastos_agg}

        # Also include gastos from cont_gasto assigned to unidad_interna
        gastos_cont_agg = await conn.fetch(f"""
            SELECT g.unidad_interna_id,
                   COALESCE(SUM(g.total), 0) as total_gastos_cont
            FROM finanzas2.cont_gasto g
            WHERE g.empresa_id = $1 AND g.unidad_interna_id IS NOT NULL
              {date_cond_gasto.replace('g.fecha', 'g.fecha')}
            GROUP BY g.unidad_interna_id
        """, *params)
        gastos_cont_map = {r['unidad_interna_id']: float(r['total_gastos_cont']) for r in gastos_cont_agg}

        # Fuente canónica de "gastos": EGRESOS en la cuenta ficticia (fin_movimiento_cuenta)
        # Esta es la misma fuente que usa el Dashboard de Cuentas Internas, garantiza consistencia.
        date_cond_mov = ""
        params_mov = [empresa_id]
        idx_mov = 2
        if fecha_desde:
            date_cond_mov += f" AND mc.fecha >= ${idx_mov}"
            params_mov.append(fecha_desde); idx_mov += 1
        if fecha_hasta:
            date_cond_mov += f" AND mc.fecha <= ${idx_mov}"
            params_mov.append(fecha_hasta); idx_mov += 1

        egresos_cuenta_agg = await conn.fetch(f"""
            SELECT cf.unidad_interna_id,
                   COALESCE(SUM(mc.monto), 0) as total_egresos
            FROM finanzas2.fin_movimiento_cuenta mc
            JOIN finanzas2.cont_cuenta_financiera cf ON mc.cuenta_id = cf.id
            WHERE mc.empresa_id = $1
              AND mc.tipo = 'EGRESO'
              AND cf.es_ficticia = true
              AND cf.unidad_interna_id IS NOT NULL
              {date_cond_mov}
            GROUP BY cf.unidad_interna_id
        """, *params_mov)
        egresos_cuenta_map = {r['unidad_interna_id']: float(r['total_egresos']) for r in egresos_cuenta_agg}

        # Gastos desglosados por tipo per unit
        gastos_detalle = await conn.fetch(f"""
            SELECT g.unidad_interna_id, g.tipo_gasto,
                   COALESCE(SUM(g.monto), 0) as total
            FROM finanzas2.fin_gasto_unidad_interna g
            WHERE g.empresa_id = $1 {date_cond_gasto}
            GROUP BY g.unidad_interna_id, g.tipo_gasto
            ORDER BY g.unidad_interna_id, g.tipo_gasto
        """, *params)
        gastos_detalle_map = {}
        for r in gastos_detalle:
            uid = r['unidad_interna_id']
            if uid not in gastos_detalle_map:
                gastos_detalle_map[uid] = []
            gastos_detalle_map[uid].append({
                'tipo': r['tipo_gasto'], 'total': float(r['total'])
            })

        # Tarifa actual promedio per unit (from production movements)
        tarifas_agg = await conn.fetch("""
            SELECT p.unidad_interna_id,
                   AVG(m.tarifa_aplicada) as tarifa_promedio
            FROM produccion.prod_movimientos_produccion m
            JOIN produccion.prod_personas_produccion p ON m.persona_id = p.id
            WHERE p.tipo_persona = 'INTERNO' AND p.unidad_interna_id IS NOT NULL
              AND m.tarifa_aplicada > 0
            GROUP BY p.unidad_interna_id
        """)
        tarifa_map = {r['unidad_interna_id']: float(r['tarifa_promedio']) for r in tarifas_agg}

        # Build report
        vista_empresa = []  # consolidated costs for the company
        vista_unidades = []  # detailed P&L per unit

        for u in unidades:
            uid = u['id']
            cargo_data = cargos_map.get(uid, {})
            gasto_data = gastos_map.get(uid, {})

            ingresos = float(cargo_data.get('total_ingresos', 0))
            gastos_ui = float(gasto_data.get('total_gastos', 0))
            gastos_cont = gastos_cont_map.get(uid, 0)
            # Usar fin_movimiento_cuenta (fuente canónica) si tiene egresos registrados,
            # sino fallback a la suma de fin_gasto_unidad_interna + cont_gasto.
            # Esto garantiza consistencia con el Dashboard de Cuentas Internas.
            egresos_cuenta = egresos_cuenta_map.get(uid, 0)
            gastos_total = egresos_cuenta if egresos_cuenta > 0 else (gastos_ui + gastos_cont)
            cantidad = int(cargo_data.get('total_cantidad', 0))
            resultado = ingresos - gastos_total
            costo_promedio = gastos_total / cantidad if cantidad > 0 else 0

            # Tarifa mínima sugerida = gastos_reales / cantidad_trabajada
            tarifa_minima = round(gastos_total / cantidad, 4) if cantidad > 0 else 0
            tarifa_actual = round(tarifa_map.get(uid, 0), 4)
            cobertura_pct = round(tarifa_actual / tarifa_minima * 100, 1) if tarifa_minima > 0 else 0
            tarifa_sostenible = tarifa_actual >= tarifa_minima if tarifa_minima > 0 else True

            vista_empresa.append({
                'unidad_id': uid,
                'unidad_nombre': u['nombre'],
                'costo_consolidado': ingresos,  # for the company, internal charge = cost
            })

            vista_unidades.append({
                'unidad_id': uid,
                'unidad_nombre': u['nombre'],
                'tipo': u['tipo'] or '',
                'ingresos_internos': ingresos,
                'gastos_reales': gastos_total,
                'gastos_detalle': gastos_detalle_map.get(uid, []),
                'resultado': resultado,
                'cantidad_trabajada': cantidad,
                'costo_promedio': round(costo_promedio, 4),
                'tarifa_actual': tarifa_actual,
                'tarifa_minima': tarifa_minima,
                'cobertura_pct': cobertura_pct,
                'tarifa_sostenible': tarifa_sostenible,
                'num_cargos': int(cargo_data.get('num_cargos', 0)),
                'num_gastos': int(gasto_data.get('num_gastos', 0)),
            })

        total_costo_empresa = sum(v['costo_consolidado'] for v in vista_empresa)
        total_ingresos = sum(v['ingresos_internos'] for v in vista_unidades)
        total_gastos = sum(v['gastos_reales'] for v in vista_unidades)

        return {
            'vista_empresa': vista_empresa,
            'vista_unidades': vista_unidades,
            'resumen': {
                'total_costo_empresa': total_costo_empresa,
                'total_ingresos_internos': total_ingresos,
                'total_gastos_reales': total_gastos,
                'resultado_global': total_ingresos - total_gastos,
                'num_unidades': len(unidades),
            }
        }


# ════════════════════════════════════════
# P&L DETALLADO POR UNIDAD INTERNA
# ════════════════════════════════════════

@router.get("/reporte-pnl-unidad/{unidad_id}")
async def reporte_pnl_unidad(
    unidad_id: int,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    """
    Estado de Resultados (P&L) detallado de una unidad interna en un período.

    Estructura:
    - INGRESOS: cargos pagados (NI procesadas) con detalle de corte/modelo/persona
    - CxC VIRTUAL: cargos pendientes de procesar (no contabilizados)
    - GASTOS: gastos reales de la unidad (planilla + directos + facturas imputadas)
    - UTILIDAD: ingresos - gastos
    - KPIs: margen %, prendas, costo unitario efectivo, tarifa mercado vs real
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        unidad = await conn.fetchrow(
            "SELECT * FROM finanzas2.fin_unidad_interna WHERE id = $1 AND empresa_id = $2",
            unidad_id, empresa_id,
        )
        if not unidad:
            raise HTTPException(404, "Unidad no encontrada")

        # Cuenta ficticia asociada
        cuenta = await conn.fetchrow(
            """
            SELECT id, nombre, saldo_actual, saldo_inicial
            FROM finanzas2.cont_cuenta_financiera
            WHERE unidad_interna_id = $1 AND es_ficticia = TRUE AND empresa_id = $2
            LIMIT 1
            """,
            unidad_id, empresa_id,
        )

        # Construir filtros de fecha
        cond_fecha_cargo = ""
        cond_fecha_gasto = ""
        params = [unidad_id, empresa_id]
        idx = 3
        if fecha_desde:
            cond_fecha_cargo += f" AND ci.fecha >= ${idx}"
            cond_fecha_gasto += f" AND g.fecha >= ${idx}"
            params.append(fecha_desde); idx += 1
        if fecha_hasta:
            cond_fecha_cargo += f" AND ci.fecha <= ${idx}"
            cond_fecha_gasto += f" AND g.fecha <= ${idx}"
            params.append(fecha_hasta); idx += 1

        # ── INGRESOS: cargos pagados con detalle de corte/modelo ──────────
        ingresos_rows = await conn.fetch(
            f"""
            SELECT ci.id, ci.fecha, ci.cantidad, ci.tarifa, ci.importe,
                   ci.persona_nombre, ci.servicio_nombre,
                   r.n_corte,
                   COALESCE(m.nombre, r.modelo_manual->>'nombre_modelo') AS modelo_nombre,
                   mp.factura_numero
            FROM finanzas2.fin_cargo_interno ci
            LEFT JOIN produccion.prod_movimientos_produccion mp ON mp.id::text = ci.movimiento_id
            LEFT JOIN produccion.prod_registros r ON r.id = ci.registro_id
            LEFT JOIN produccion.prod_modelos m ON m.id = r.modelo_id
            WHERE ci.unidad_interna_id = $1 AND ci.empresa_id = $2
              AND ci.estado = 'pagado'
              {cond_fecha_cargo}
            ORDER BY ci.fecha DESC, ci.id DESC
            """,
            *params,
        )
        ingresos_items = []
        total_ingresos = 0.0
        total_prendas_ing = 0
        for r in ingresos_rows:
            item = {
                "cargo_id": r["id"],
                "fecha": r["fecha"].isoformat() if r["fecha"] else None,
                "n_corte": r["n_corte"],
                "modelo": r["modelo_nombre"] or "—",
                "persona": r["persona_nombre"] or "",
                "servicio": r["servicio_nombre"] or "",
                "cantidad": int(r["cantidad"] or 0),
                "tarifa": float(r["tarifa"] or 0),
                "importe": float(r["importe"] or 0),
                "factura_numero": r["factura_numero"],
            }
            ingresos_items.append(item)
            total_ingresos += item["importe"]
            total_prendas_ing += item["cantidad"]

        # ── CxC VIRTUAL: cargos pendientes (no contabilizados) ───────────
        cxc_rows = await conn.fetch(
            f"""
            SELECT ci.id, ci.fecha, ci.cantidad, ci.tarifa, ci.importe,
                   ci.persona_nombre, ci.servicio_nombre,
                   r.n_corte,
                   COALESCE(m.nombre, r.modelo_manual->>'nombre_modelo') AS modelo_nombre,
                   mp.factura_numero
            FROM finanzas2.fin_cargo_interno ci
            LEFT JOIN produccion.prod_movimientos_produccion mp ON mp.id::text = ci.movimiento_id
            LEFT JOIN produccion.prod_registros r ON r.id = ci.registro_id
            LEFT JOIN produccion.prod_modelos m ON m.id = r.modelo_id
            WHERE ci.unidad_interna_id = $1 AND ci.empresa_id = $2
              AND ci.estado = 'generado'
              {cond_fecha_cargo}
            ORDER BY ci.fecha DESC, ci.id DESC
            """,
            *params,
        )
        cxc_items = []
        total_cxc = 0.0
        total_prendas_cxc = 0
        for r in cxc_rows:
            item = {
                "cargo_id": r["id"],
                "fecha": r["fecha"].isoformat() if r["fecha"] else None,
                "n_corte": r["n_corte"],
                "modelo": r["modelo_nombre"] or "—",
                "persona": r["persona_nombre"] or "",
                "servicio": r["servicio_nombre"] or "",
                "cantidad": int(r["cantidad"] or 0),
                "tarifa": float(r["tarifa"] or 0),
                "importe": float(r["importe"] or 0),
                "factura_numero": r["factura_numero"],
            }
            cxc_items.append(item)
            total_cxc += item["importe"]
            total_prendas_cxc += item["cantidad"]

        # ── GASTOS: directos de la unidad (fin_gasto_unidad_interna) ──────
        gastos_dir = await conn.fetch(
            f"""
            SELECT g.id, g.fecha, g.tipo_gasto, g.descripcion, g.monto
            FROM finanzas2.fin_gasto_unidad_interna g
            WHERE g.unidad_interna_id = $1 AND g.empresa_id = $2
              {cond_fecha_gasto}
            ORDER BY g.fecha DESC, g.id DESC
            """,
            *params,
        )
        gastos_items = []
        for g in gastos_dir:
            gastos_items.append({
                "gasto_id": g["id"],
                "fecha": g["fecha"].isoformat() if g["fecha"] else None,
                "categoria": g["tipo_gasto"] or "Otros",
                "concepto": g["descripcion"] or "",
                "monto": float(g["monto"] or 0),
                "origen": "directo",
            })

        # Líneas de factura de proveedor con unidad_interna_id
        gastos_facturas = await conn.fetch(
            f"""
            SELECT fpl.id, fp.fecha_factura AS fecha, fp.numero AS factura_numero,
                   c.nombre AS categoria_nombre,
                   fpl.descripcion, fpl.importe
            FROM finanzas2.cont_factura_proveedor_linea fpl
            JOIN finanzas2.cont_factura_proveedor fp ON fp.id = fpl.factura_id
            LEFT JOIN finanzas2.cont_categoria c ON c.id = fpl.categoria_id
            WHERE fpl.unidad_interna_id = $1 AND fpl.empresa_id = $2
              AND fp.tipo_documento != 'nota_interna'
              {cond_fecha_gasto.replace('g.fecha', 'fp.fecha_factura')}
            ORDER BY fp.fecha_factura DESC
            """,
            *params,
        )
        for g in gastos_facturas:
            gastos_items.append({
                "gasto_id": f"fact-{g['id']}",
                "fecha": g["fecha"].isoformat() if g["fecha"] else None,
                "categoria": g["categoria_nombre"] or "Factura",
                "concepto": f"{g['factura_numero']} — {g['descripcion'] or ''}",
                "monto": float(g["importe"] or 0),
                "origen": "factura",
            })

        gastos_items.sort(key=lambda x: x["fecha"] or "", reverse=True)
        total_gastos = sum(g["monto"] for g in gastos_items)

        # Agrupación de gastos por categoría
        gastos_por_cat = {}
        for g in gastos_items:
            cat = g["categoria"]
            gastos_por_cat[cat] = gastos_por_cat.get(cat, 0) + g["monto"]
        gastos_agrupado = [
            {"categoria": k, "monto": round(v, 2)}
            for k, v in sorted(gastos_por_cat.items(), key=lambda x: -x[1])
        ]

        # ── KPIs ────────────────────────────────────────────────────────
        utilidad = total_ingresos - total_gastos
        margen_pct = (utilidad / total_ingresos * 100) if total_ingresos > 0 else 0
        costo_real_por_prenda = (total_gastos / total_prendas_ing) if total_prendas_ing > 0 else 0
        tarifa_mercado_prom = (total_ingresos / total_prendas_ing) if total_prendas_ing > 0 else 0

        return {
            "unidad": {
                "id": unidad["id"],
                "nombre": unidad["nombre"],
                "tipo": unidad["tipo"],
            },
            "cuenta_ficticia": {
                "id": cuenta["id"] if cuenta else None,
                "saldo_actual": float(cuenta["saldo_actual"]) if cuenta else 0.0,
            } if cuenta else None,
            "periodo": {
                "desde": fecha_desde.isoformat() if fecha_desde else None,
                "hasta": fecha_hasta.isoformat() if fecha_hasta else None,
            },
            "ingresos": {
                "items": ingresos_items,
                "total": round(total_ingresos, 2),
                "prendas": total_prendas_ing,
                "count": len(ingresos_items),
            },
            "cxc_virtual": {
                "items": cxc_items,
                "total": round(total_cxc, 2),
                "prendas": total_prendas_cxc,
                "count": len(cxc_items),
            },
            "gastos": {
                "items": gastos_items,
                "agrupado_categoria": gastos_agrupado,
                "total": round(total_gastos, 2),
                "count": len(gastos_items),
            },
            "utilidad": {
                "total": round(utilidad, 2),
                "margen_pct": round(margen_pct, 2),
                "es_rentable": utilidad >= 0,
            },
            "kpis": {
                "prendas_total": total_prendas_ing,
                "costo_real_por_prenda": round(costo_real_por_prenda, 4),
                "tarifa_mercado_promedio": round(tarifa_mercado_prom, 4),
                "potencial_total": round(total_ingresos + total_cxc, 2),
                "utilidad_potencial": round((total_ingresos + total_cxc) - total_gastos, 2),
            },
        }
