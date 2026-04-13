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
        rows = await conn.fetch(f"""
            SELECT c.*, u.nombre as unidad_nombre
            FROM finanzas2.fin_cargo_interno c
            LEFT JOIN finanzas2.fin_unidad_interna u ON c.unidad_interna_id = u.id
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
            result.append(d)
        return result


@router.post("/cargos-internos/generar")
async def generar_cargos_internos(empresa_id: int = Depends(get_empresa_id)):
    """
    Scan production movements where persona is INTERNO and generate
    fin_cargo_interno records (skipping duplicates via movimiento_id UNIQUE).
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        # Find all movements by internal personas that don't have a cargo yet
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
                    # Register INGRESO in the unit's fictitious account
                    cuenta_id = await conn.fetchval("""
                        SELECT id FROM finanzas2.cont_cuenta_financiera
                        WHERE empresa_id=$1 AND unidad_interna_id=$2 AND es_ficticia=true
                    """, empresa_id, mov['unidad_interna_id'])
                    if cuenta_id:
                        await conn.execute("""
                            INSERT INTO finanzas2.fin_movimiento_cuenta
                            (cuenta_id, empresa_id, tipo, monto, descripcion, fecha, referencia_id, referencia_tipo)
                            VALUES ($1, $2, 'INGRESO', $3, $4, $5, $6, 'CARGO_INTERNO')
                        """, cuenta_id, empresa_id, importe,
                            f"Cobro {cantidad} prendas - {mov['servicio_nombre'] or 'Servicio'}",
                            mov['fecha'], str(cargo_id))
                        await conn.execute("""
                            UPDATE finanzas2.cont_cuenta_financiera
                            SET saldo_actual = COALESCE(saldo_actual, 0) + $1
                            WHERE id = $2
                        """, importe, cuenta_id)
            except Exception as e:
                logger.warning(f"Error generating cargo for mov {mov['movimiento_id']}: {e}")

        return {"message": f"{generados} cargos internos generados", "generados": generados}


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
            gastos_total = gastos_ui + gastos_cont
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
