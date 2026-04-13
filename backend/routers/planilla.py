from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel
from database import get_pool
from dependencies import get_empresa_id

router = APIRouter()


# ── Pydantic Models ──

class PlanillaDetalleIn(BaseModel):
    trabajador_id: Optional[str] = None
    trabajador_nombre: Optional[str] = None
    tipo_trabajador: Optional[str] = None
    unidad_interna_id: Optional[int] = None
    linea_negocio_id: Optional[int] = None
    salario_base: float = 0
    bonificaciones: float = 0
    adelantos: float = 0
    otros_descuentos: float = 0
    neto_pagar: float = 0
    notas: Optional[str] = None


class PlanillaCreate(BaseModel):
    periodo: str
    tipo: Optional[str] = "quincenal"
    fecha_inicio: date
    fecha_fin: date
    fecha_pago: Optional[date] = None
    notas: Optional[str] = None
    lineas: List[PlanillaDetalleIn] = []


class PlanillaUpdate(BaseModel):
    periodo: Optional[str] = None
    tipo: Optional[str] = None
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    fecha_pago: Optional[date] = None
    estado: Optional[str] = None
    notas: Optional[str] = None
    lineas: Optional[List[PlanillaDetalleIn]] = None


class AdelantoCreate(BaseModel):
    empleado_id: int
    monto: float
    fecha: date
    motivo: Optional[str] = None


class CalcularPlanillaIn(BaseModel):
    fecha_inicio: date
    fecha_fin: date
    tipo: Optional[str] = "quincenal"


# ── Helpers ──

async def _enrich_planilla(conn, planilla: dict) -> dict:
    """Load detail lines + joined names for a single planilla."""
    rows = await conn.fetch("""
        SELECT d.*,
               ui.nombre AS unidad_interna_nombre,
               ln.nombre AS linea_negocio_nombre
        FROM finanzas2.cont_planilla_detalle d
        LEFT JOIN finanzas2.fin_unidad_interna ui ON d.unidad_interna_id = ui.id
        LEFT JOIN finanzas2.cont_linea_negocio ln ON d.linea_negocio_id = ln.id
        WHERE d.planilla_id = $1
        ORDER BY d.id
    """, planilla["id"])
    planilla["lineas"] = [dict(r) for r in rows]
    return planilla


# ── PERIODOS ──

@router.get("/planillas/periodos")
async def list_periodos():
    """Return available period types."""
    return [
        {"value": "semanal", "label": "Semanal"},
        {"value": "quincenal", "label": "Quincenal"},
        {"value": "mensual", "label": "Mensual"},
        {"value": "gratificacion", "label": "Gratificacion"},
    ]


# ── CALCULAR ──

@router.post("/planillas/calcular")
async def calcular_planilla(
    data: CalcularPlanillaIn,
    empresa_id: int = Depends(get_empresa_id),
):
    """
    Calculate payroll for a period by reading prod_movimientos_produccion.
    Returns preview data (not saved yet).
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, produccion, public")

        # Get movements from produccion for the period
        movimientos = await conn.fetch("""
            SELECT
                m.persona_id,
                pp.nombre AS persona_nombre,
                pp.tipo_persona,
                pp.unidad_interna_id,
                ui.nombre AS unidad_interna_nombre,
                SUM(m.cantidad_recibida) AS total_cantidad,
                SUM(m.costo_calculado) AS total_bruto,
                AVG(m.tarifa_aplicada) AS tarifa_promedio,
                COUNT(*) AS num_movimientos,
                MAX(m.fecha_fin) AS ultimo_movimiento
            FROM produccion.prod_movimientos_produccion m
            JOIN produccion.prod_personas_produccion pp ON m.persona_id = pp.id
            LEFT JOIN finanzas2.fin_unidad_interna ui ON pp.unidad_interna_id = ui.id
            WHERE m.fecha_fin >= $1
              AND m.fecha_fin <= $2
              AND pp.activo = true
            GROUP BY m.persona_id, pp.nombre, pp.tipo_persona, pp.unidad_interna_id, ui.nombre
            ORDER BY pp.nombre
        """, data.fecha_inicio, data.fecha_fin)

        # Get pending adelantos for each worker
        adelantos_map = {}
        adelantos_rows = await conn.fetch("""
            SELECT empleado_id, SUM(monto) AS total_adelantos
            FROM finanzas2.cont_adelanto_empleado
            WHERE descontado = false
              AND empresa_id = $1
            GROUP BY empleado_id
        """, empresa_id)
        for row in adelantos_rows:
            adelantos_map[row["empleado_id"]] = float(row["total_adelantos"] or 0)

        # Build preview lines
        lineas = []
        total_bruto = 0
        total_adelantos = 0
        total_neto = 0

        for mov in movimientos:
            bruto = float(mov["total_bruto"] or 0)
            # Try to match adelantos by checking cont_tercero linked to this persona
            adelanto = 0  # Adelantos are by empleado_id (cont_tercero), not persona_id
            neto = bruto - adelanto

            lineas.append({
                "trabajador_id": mov["persona_id"],
                "trabajador_nombre": mov["persona_nombre"],
                "tipo_trabajador": mov["tipo_persona"],
                "unidad_interna_id": mov["unidad_interna_id"],
                "unidad_interna_nombre": mov["unidad_interna_nombre"],
                "cantidad_total": int(mov["total_cantidad"] or 0),
                "tarifa_promedio": float(mov["tarifa_promedio"] or 0),
                "num_movimientos": mov["num_movimientos"],
                "ultimo_movimiento": str(mov["ultimo_movimiento"]) if mov["ultimo_movimiento"] else None,
                "salario_base": bruto,
                "bonificaciones": 0,
                "adelantos": adelanto,
                "otros_descuentos": 0,
                "neto_pagar": neto,
            })
            total_bruto += bruto
            total_adelantos += adelanto
            total_neto += neto

        periodo_str = f"{data.fecha_inicio.strftime('%Y-%m-%d')} al {data.fecha_fin.strftime('%Y-%m-%d')}"

        return {
            "periodo": periodo_str,
            "tipo": data.tipo,
            "fecha_inicio": str(data.fecha_inicio),
            "fecha_fin": str(data.fecha_fin),
            "total_bruto": total_bruto,
            "total_adelantos": total_adelantos,
            "total_neto": total_neto,
            "num_trabajadores": len(lineas),
            "lineas": lineas,
        }


# ── LIST ──

@router.get("/planillas")
async def list_planillas(
    periodo: Optional[str] = None,
    tipo: Optional[str] = None,
    estado: Optional[str] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        conds = ["p.empresa_id = $1"]
        params: list = [empresa_id]
        idx = 2
        if periodo:
            conds.append(f"p.periodo ILIKE '%' || ${idx} || '%'")
            params.append(periodo); idx += 1
        if tipo:
            conds.append(f"p.tipo = ${idx}")
            params.append(tipo); idx += 1
        if estado:
            conds.append(f"p.estado = ${idx}")
            params.append(estado); idx += 1

        query = f"""
            SELECT p.*
            FROM finanzas2.cont_planilla p
            WHERE {' AND '.join(conds)}
            ORDER BY p.fecha_inicio DESC
        """
        rows = await conn.fetch(query, *params)
        result = []
        for row in rows:
            p = dict(row)
            p = await _enrich_planilla(conn, p)
            result.append(p)
        return result


# ── GET BY ID (detail) ──

@router.get("/planillas/{planilla_id}")
async def get_planilla(planilla_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        row = await conn.fetchrow(
            "SELECT * FROM finanzas2.cont_planilla WHERE id=$1 AND empresa_id=$2",
            planilla_id, empresa_id,
        )
        if not row:
            raise HTTPException(404, "Planilla no encontrada")
        p = dict(row)
        return await _enrich_planilla(conn, p)


# ── CREATE ──

@router.post("/planillas")
async def create_planilla(data: PlanillaCreate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        total_bruto = sum(l.salario_base + l.bonificaciones for l in data.lineas)
        total_adel = sum(l.adelantos for l in data.lineas)
        total_desc = sum(l.otros_descuentos for l in data.lineas)
        total_neto = sum(l.neto_pagar for l in data.lineas)

        pid = await conn.fetchval("""
            INSERT INTO finanzas2.cont_planilla
                (empresa_id, periodo, tipo, fecha_inicio, fecha_fin, fecha_pago,
                 total_bruto, total_adelantos, total_descuentos, total_neto,
                 estado, notas, created_at, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'borrador',$11,NOW(),NOW())
            RETURNING id
        """, empresa_id, data.periodo, data.tipo,
            data.fecha_inicio, data.fecha_fin, data.fecha_pago,
            total_bruto, total_adel, total_desc, total_neto,
            data.notas)

        for l in data.lineas:
            await conn.execute("""
                INSERT INTO finanzas2.cont_planilla_detalle
                    (empresa_id, planilla_id, trabajador_id, trabajador_nombre, tipo_trabajador,
                     unidad_interna_id, linea_negocio_id, salario_base, bonificaciones,
                     adelantos, otros_descuentos, neto_pagar, notas, created_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,NOW())
            """, empresa_id, pid, l.trabajador_id, l.trabajador_nombre, l.tipo_trabajador,
                l.unidad_interna_id, l.linea_negocio_id, l.salario_base, l.bonificaciones,
                l.adelantos, l.otros_descuentos, l.neto_pagar, l.notas)

        row = await conn.fetchrow("SELECT * FROM finanzas2.cont_planilla WHERE id=$1", pid)
        return await _enrich_planilla(conn, dict(row))


# ── UPDATE ──

@router.put("/planillas/{planilla_id}")
async def update_planilla(planilla_id: int, data: PlanillaUpdate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        existing = await conn.fetchrow(
            "SELECT * FROM finanzas2.cont_planilla WHERE id=$1 AND empresa_id=$2",
            planilla_id, empresa_id,
        )
        if not existing:
            raise HTTPException(404, "Planilla no encontrada")

        sets = []
        params = []
        idx = 1
        for field in ["periodo", "tipo", "fecha_inicio", "fecha_fin", "fecha_pago", "estado", "notas"]:
            val = getattr(data, field, None)
            if val is not None:
                sets.append(f"{field} = ${idx}")
                params.append(val); idx += 1

        if data.lineas is not None:
            total_bruto = sum(l.salario_base + l.bonificaciones for l in data.lineas)
            total_adel = sum(l.adelantos for l in data.lineas)
            total_desc = sum(l.otros_descuentos for l in data.lineas)
            total_neto = sum(l.neto_pagar for l in data.lineas)

            for col, val in [("total_bruto", total_bruto), ("total_adelantos", total_adel),
                             ("total_descuentos", total_desc), ("total_neto", total_neto)]:
                sets.append(f"{col} = ${idx}")
                params.append(val); idx += 1

        sets.append(f"updated_at = NOW()")
        params.append(planilla_id); idx_id = idx

        await conn.execute(
            f"UPDATE finanzas2.cont_planilla SET {', '.join(sets)} WHERE id = ${idx_id}",
            *params,
        )

        if data.lineas is not None:
            await conn.execute("DELETE FROM finanzas2.cont_planilla_detalle WHERE planilla_id=$1", planilla_id)
            for l in data.lineas:
                await conn.execute("""
                    INSERT INTO finanzas2.cont_planilla_detalle
                        (empresa_id, planilla_id, trabajador_id, trabajador_nombre, tipo_trabajador,
                         unidad_interna_id, linea_negocio_id, salario_base, bonificaciones,
                         adelantos, otros_descuentos, neto_pagar, notas, created_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,NOW())
                """, empresa_id, planilla_id, l.trabajador_id, l.trabajador_nombre, l.tipo_trabajador,
                    l.unidad_interna_id, l.linea_negocio_id, l.salario_base, l.bonificaciones,
                    l.adelantos, l.otros_descuentos, l.neto_pagar, l.notas)

        row = await conn.fetchrow("SELECT * FROM finanzas2.cont_planilla WHERE id=$1", planilla_id)
        return await _enrich_planilla(conn, dict(row))


# ── APROBAR ──

@router.post("/planillas/{planilla_id}/aprobar")
async def aprobar_planilla(planilla_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        row = await conn.fetchrow(
            "SELECT * FROM finanzas2.cont_planilla WHERE id=$1 AND empresa_id=$2",
            planilla_id, empresa_id,
        )
        if not row:
            raise HTTPException(404, "Planilla no encontrada")
        if row["estado"] != "borrador":
            raise HTTPException(400, f"Solo se puede aprobar planillas en estado borrador (actual: {row['estado']})")

        await conn.execute("""
            UPDATE finanzas2.cont_planilla
            SET estado = 'aprobado', updated_at = NOW()
            WHERE id = $1
        """, planilla_id)

        updated = await conn.fetchrow("SELECT * FROM finanzas2.cont_planilla WHERE id=$1", planilla_id)
        return await _enrich_planilla(conn, dict(updated))


# ── PAGAR (OPCIÓN B: EGRESO en cuentas ficticias por unidad interna) ──

@router.post("/planillas/{planilla_id}/pagar")
async def pagar_planilla(planilla_id: int, empresa_id: int = Depends(get_empresa_id)):
    """
    Crear movimientos EGRESO en cuentas ficticias por unidad interna.
    NO crea cont_pago ni cont_gasto. Agrupa detalles por unidad_interna_id,
    suma neto_pagar, y crea un fin_movimiento_cuenta EGRESO por cada cuenta ficticia.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        async with conn.transaction():
            planilla = await conn.fetchrow(
                "SELECT * FROM finanzas2.cont_planilla WHERE id=$1 AND empresa_id=$2",
                planilla_id, empresa_id,
            )
            if not planilla:
                raise HTTPException(404, "Planilla no encontrada")
            if planilla["estado"] == "pagada":
                raise HTTPException(400, "La planilla ya está pagada")
            if planilla["estado"] != "aprobado":
                raise HTTPException(400, f"La planilla debe estar aprobada antes de pagar (actual: {planilla['estado']})")

            # Group detalles by unidad_interna_id and sum neto_pagar
            detalles = await conn.fetch("""
                SELECT unidad_interna_id, SUM(neto_pagar) as total
                FROM finanzas2.cont_planilla_detalle
                WHERE planilla_id = $1 AND unidad_interna_id IS NOT NULL
                GROUP BY unidad_interna_id
            """, planilla_id)

            sin_unidad = await conn.fetchval("""
                SELECT SUM(neto_pagar) FROM finanzas2.cont_planilla_detalle
                WHERE planilla_id = $1 AND unidad_interna_id IS NULL
            """, planilla_id)

            if not detalles and not sin_unidad:
                raise HTTPException(400, "No hay detalles en la planilla para pagar")

            movimientos_creados = []
            fecha_pago = datetime.now().date()

            for det in detalles:
                ui_id = det["unidad_interna_id"]
                monto = float(det["total"])
                if monto <= 0:
                    continue

                cuenta = await conn.fetchrow("""
                    SELECT id, nombre, saldo_actual
                    FROM finanzas2.cont_cuenta_financiera
                    WHERE empresa_id = $1 AND es_ficticia = true AND unidad_interna_id = $2
                """, empresa_id, ui_id)

                if not cuenta:
                    raise HTTPException(400,
                        f"No se encontró cuenta ficticia para unidad interna ID {ui_id}")

                mov = await conn.fetchrow("""
                    INSERT INTO finanzas2.fin_movimiento_cuenta
                    (cuenta_id, empresa_id, tipo, monto, descripcion, fecha, referencia_id, referencia_tipo)
                    VALUES ($1, $2, 'EGRESO', $3, $4, $5, $6, 'planilla')
                    RETURNING id
                """, cuenta["id"], empresa_id, monto,
                    f"Pago planilla {planilla['periodo']}", fecha_pago, str(planilla_id))

                await conn.execute("""
                    UPDATE finanzas2.cont_cuenta_financiera
                    SET saldo_actual = saldo_actual - $1
                    WHERE id = $2
                """, monto, cuenta["id"])

                nuevo_saldo = await conn.fetchval(
                    "SELECT saldo_actual FROM finanzas2.cont_cuenta_financiera WHERE id = $1", cuenta["id"])

                movimientos_creados.append({
                    "cuenta_id": cuenta["id"],
                    "cuenta_nombre": cuenta["nombre"],
                    "unidad_interna_id": ui_id,
                    "monto": monto,
                    "nuevo_saldo": float(nuevo_saldo),
                    "movimiento_id": mov["id"],
                })

            monto_sin_unidad = float(sin_unidad) if sin_unidad else 0

            # Mark adelantos as descontados (empleado_id in adelantos links to cont_planilla_detalle.empleado_id)
            await conn.execute("""
                UPDATE finanzas2.cont_adelanto_empleado
                SET descontado = true, planilla_id = $1
                WHERE empleado_id IN (
                    SELECT empleado_id FROM finanzas2.cont_planilla_detalle
                    WHERE planilla_id = $1 AND empleado_id IS NOT NULL
                )
                AND descontado = false
                AND empresa_id = $2
            """, planilla_id, empresa_id)

            await conn.execute("""
                UPDATE finanzas2.cont_planilla
                SET estado = 'pagada', fecha_pago = $1, updated_at = NOW()
                WHERE id = $2
            """, fecha_pago, planilla_id)

            planilla_data = await conn.fetchrow("SELECT * FROM finanzas2.cont_planilla WHERE id=$1", planilla_id)
            result = await _enrich_planilla(conn, dict(planilla_data))
            result["movimientos_creados"] = movimientos_creados
            result["monto_sin_unidad"] = monto_sin_unidad
            return result


# ── ANULAR PAGO ──

@router.post("/planillas/{planilla_id}/anular-pago")
async def anular_pago_planilla(planilla_id: int, empresa_id: int = Depends(get_empresa_id)):
    """
    Reversa el pago: crea movimientos INGRESO por cada EGRESO original,
    restaura saldos de cuentas ficticias, y vuelve estado a 'aprobado'.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        async with conn.transaction():
            planilla = await conn.fetchrow(
                "SELECT * FROM finanzas2.cont_planilla WHERE id=$1 AND empresa_id=$2",
                planilla_id, empresa_id,
            )
            if not planilla:
                raise HTTPException(404, "Planilla no encontrada")
            if planilla["estado"] != "pagada":
                raise HTTPException(400, "Solo se puede anular el pago de una planilla pagada")

            movimientos = await conn.fetch("""
                SELECT id, cuenta_id, monto
                FROM finanzas2.fin_movimiento_cuenta
                WHERE empresa_id = $1 AND referencia_tipo = 'planilla'
                  AND referencia_id = $2 AND tipo = 'EGRESO'
            """, empresa_id, str(planilla_id))

            reversas = []
            fecha_anulacion = datetime.now().date()

            for mov in movimientos:
                monto = float(mov["monto"])

                await conn.execute("""
                    INSERT INTO finanzas2.fin_movimiento_cuenta
                    (cuenta_id, empresa_id, tipo, monto, descripcion, fecha, referencia_id, referencia_tipo)
                    VALUES ($1, $2, 'INGRESO', $3, $4, $5, $6, 'planilla_anulacion')
                """, mov["cuenta_id"], empresa_id, monto,
                    f"Anulación pago planilla {planilla['periodo']}", fecha_anulacion, str(planilla_id))

                await conn.execute("""
                    UPDATE finanzas2.cont_cuenta_financiera
                    SET saldo_actual = saldo_actual + $1
                    WHERE id = $2
                """, monto, mov["cuenta_id"])

                cuenta = await conn.fetchrow(
                    "SELECT nombre, saldo_actual FROM finanzas2.cont_cuenta_financiera WHERE id = $1",
                    mov["cuenta_id"])

                reversas.append({
                    "cuenta_id": mov["cuenta_id"],
                    "cuenta_nombre": cuenta["nombre"],
                    "monto_revertido": monto,
                    "nuevo_saldo": float(cuenta["saldo_actual"]),
                })

            # Revert adelantos
            await conn.execute("""
                UPDATE finanzas2.cont_adelanto_empleado
                SET descontado = false, planilla_id = NULL
                WHERE planilla_id = $1
            """, planilla_id)

            await conn.execute("""
                UPDATE finanzas2.cont_planilla
                SET estado = 'aprobado', fecha_pago = NULL, pago_id = NULL, updated_at = NOW()
                WHERE id = $1
            """, planilla_id)

            planilla_data = await conn.fetchrow("SELECT * FROM finanzas2.cont_planilla WHERE id=$1", planilla_id)
            result = await _enrich_planilla(conn, dict(planilla_data))
            result["reversas"] = reversas
            return result


# ── DELETE ──

@router.delete("/planillas/{planilla_id}")
async def delete_planilla(planilla_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        existing = await conn.fetchrow(
            "SELECT id, estado FROM finanzas2.cont_planilla WHERE id=$1 AND empresa_id=$2",
            planilla_id, empresa_id,
        )
        if not existing:
            raise HTTPException(404, "Planilla no encontrada")
        if existing["estado"] in ("pagado", "pagada"):
            raise HTTPException(400, "No se puede eliminar una planilla pagada")
        await conn.execute("DELETE FROM finanzas2.cont_planilla_detalle WHERE planilla_id=$1", planilla_id)
        await conn.execute("DELETE FROM finanzas2.cont_planilla WHERE id=$1", planilla_id)
        return {"ok": True}


# ── TRABAJADORES (from produccion.prod_personas_produccion) ──

@router.get("/planillas/trabajadores/list")
async def list_trabajadores(empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT pp.id, pp.nombre, pp.tipo_persona, pp.unidad_interna_id,
                   ui.nombre AS unidad_interna_nombre
            FROM produccion.prod_personas_produccion pp
            LEFT JOIN finanzas2.fin_unidad_interna ui ON pp.unidad_interna_id = ui.id
            WHERE pp.activo = true
            ORDER BY pp.nombre
        """)
        return [dict(r) for r in rows]


# ── RESUMEN (summary for reporting) ──

@router.get("/planillas/resumen/totales")
async def resumen_planillas(
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        conds = ["p.empresa_id = $1"]
        params: list = [empresa_id]
        idx = 2
        if fecha_desde:
            conds.append(f"p.fecha_inicio >= ${idx}")
            params.append(fecha_desde); idx += 1
        if fecha_hasta:
            conds.append(f"p.fecha_fin <= ${idx}")
            params.append(fecha_hasta); idx += 1

        por_empleado = await conn.fetch(f"""
            SELECT d.empleado_id, t.nombre AS empleado_nombre,
                   SUM(d.salario_base) AS total_bruto,
                   SUM(d.adelantos) AS total_adelantos,
                   SUM(d.otros_descuentos) AS total_descuentos,
                   SUM(d.neto_pagar) AS total_neto
            FROM finanzas2.cont_planilla_detalle d
            JOIN finanzas2.cont_planilla p ON d.planilla_id = p.id
            LEFT JOIN finanzas2.cont_tercero t ON d.empleado_id = t.id
            WHERE {' AND '.join(conds)}
            GROUP BY d.empleado_id, t.nombre
            ORDER BY total_neto DESC
        """, *params)

        totals = await conn.fetchrow(f"""
            SELECT COUNT(*) AS num_planillas,
                   COALESCE(SUM(p.total_bruto), 0) AS total_bruto,
                   COALESCE(SUM(p.total_neto), 0) AS total_neto,
                   COALESCE(SUM(p.total_adelantos), 0) AS total_adelantos,
                   COALESCE(SUM(p.total_descuentos), 0) AS total_descuentos
            FROM finanzas2.cont_planilla p
            WHERE {' AND '.join(conds)}
        """, *params)

        return {
            "totales": dict(totals) if totals else {},
            "por_empleado": [dict(r) for r in por_empleado],
        }


# ── ADELANTOS ──

@router.get("/planillas/adelantos")
async def list_adelantos(
    empleado_id: Optional[int] = None,
    pendientes: Optional[bool] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        conds = ["a.empresa_id = $1"]
        params: list = [empresa_id]
        idx = 2
        if empleado_id:
            conds.append(f"a.empleado_id = ${idx}")
            params.append(empleado_id); idx += 1
        if pendientes:
            conds.append("a.descontado = false")

        rows = await conn.fetch(f"""
            SELECT a.*, t.nombre AS empleado_nombre
            FROM finanzas2.cont_adelanto_empleado a
            LEFT JOIN finanzas2.cont_tercero t ON a.empleado_id = t.id
            WHERE {' AND '.join(conds)}
            ORDER BY a.fecha DESC
        """, *params)
        return [dict(r) for r in rows]


@router.post("/planillas/adelantos")
async def create_adelanto(data: AdelantoCreate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO finanzas2.cont_adelanto_empleado
                (empresa_id, empleado_id, monto, fecha, motivo, created_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            RETURNING *
        """, empresa_id, data.empleado_id, data.monto, data.fecha, data.motivo)
        return dict(row)
