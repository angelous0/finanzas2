from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from datetime import datetime
from database import get_pool
from models import Planilla, PlanillaCreate
from dependencies import get_empresa_id, safe_date_param

router = APIRouter()


async def get_planilla(id: int, empresa_id: int = None) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        if empresa_id:
            row = await conn.fetchrow("SELECT * FROM finanzas2.cont_planilla WHERE id = $1 AND empresa_id = $2", id, empresa_id)
        else:
            row = await conn.fetchrow("SELECT * FROM finanzas2.cont_planilla WHERE id = $1", id)
        if not row:
            raise HTTPException(404, "Planilla not found")
        planilla_dict = dict(row)
        detalles = await conn.fetch("""
            SELECT pd.*, t.nombre as empleado_nombre
            FROM finanzas2.cont_planilla_detalle pd
            LEFT JOIN finanzas2.cont_tercero t ON pd.empleado_id = t.id
            WHERE pd.planilla_id = $1
        """, id)
        planilla_dict['detalles'] = [dict(d) for d in detalles]
        return planilla_dict


@router.get("/planillas", response_model=List[Planilla])
async def list_planillas(empresa_id: Optional[int] = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        if empresa_id is not None:
            rows = await conn.fetch("""
                SELECT DISTINCT p.* FROM finanzas2.cont_planilla p
                JOIN finanzas2.cont_planilla_detalle pd ON pd.planilla_id = p.id
                JOIN finanzas2.cont_tercero t ON pd.empleado_id = t.id
                WHERE t.empresa_id = $1
                ORDER BY p.periodo DESC
            """, empresa_id)
        else:
            rows = await conn.fetch("SELECT * FROM finanzas2.cont_planilla ORDER BY periodo DESC")
        result = []
        for row in rows:
            planilla_dict = dict(row)
            detalles = await conn.fetch("""
                SELECT pd.*, t.nombre as empleado_nombre
                FROM finanzas2.cont_planilla_detalle pd
                LEFT JOIN finanzas2.cont_tercero t ON pd.empleado_id = t.id
                WHERE pd.planilla_id = $1
            """, row['id'])
            planilla_dict['detalles'] = [dict(d) for d in detalles]
            result.append(planilla_dict)
        return result


@router.post("/planillas", response_model=Planilla)
async def create_planilla(data: PlanillaCreate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        async with conn.transaction():
            total_bruto = sum(d.salario_base + d.bonificaciones for d in data.detalles)
            total_adelantos = sum(d.adelantos for d in data.detalles)
            total_descuentos = sum(d.otros_descuentos for d in data.detalles)
            total_neto = total_bruto - total_adelantos - total_descuentos
            row = await conn.fetchrow("""
                INSERT INTO finanzas2.cont_planilla
                (periodo, fecha_inicio, fecha_fin, total_bruto, total_adelantos,
                 total_descuentos, total_neto, estado, empresa_id)
                VALUES ($1, TO_DATE($2, 'YYYY-MM-DD'), TO_DATE($3, 'YYYY-MM-DD'), $4, $5, $6, $7, 'borrador', $8)
                RETURNING *
            """, data.periodo, safe_date_param(data.fecha_inicio), safe_date_param(data.fecha_fin), total_bruto,
                total_adelantos, total_descuentos, total_neto, empresa_id)
            planilla_id = row['id']
            planilla_dict = dict(row)
            detalles_list = []
            for detalle in data.detalles:
                neto_pagar = detalle.salario_base + detalle.bonificaciones - detalle.adelantos - detalle.otros_descuentos
                detalle_row = await conn.fetchrow("""
                    INSERT INTO finanzas2.cont_planilla_detalle
                    (planilla_id, empleado_id, salario_base, bonificaciones, adelantos,
                     otros_descuentos, neto_pagar, empresa_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING *
                """, planilla_id, detalle.empleado_id, detalle.salario_base, detalle.bonificaciones,
                    detalle.adelantos, detalle.otros_descuentos, neto_pagar, empresa_id)
                emp = await conn.fetchrow("SELECT nombre FROM finanzas2.cont_tercero WHERE id = $1 AND empresa_id = $2", detalle.empleado_id, empresa_id)
                detalle_dict = dict(detalle_row)
                detalle_dict['empleado_nombre'] = emp['nombre'] if emp else None
                detalles_list.append(detalle_dict)
            planilla_dict['detalles'] = detalles_list
            return planilla_dict


@router.get("/planillas/{id}", response_model=Planilla)
async def get_planilla_endpoint(id: int, empresa_id: int = Depends(get_empresa_id)):
    return await get_planilla(id, empresa_id)


@router.post("/planillas/{id}/pagar")
async def pagar_planilla(id: int, empresa_id: int = Depends(get_empresa_id)):
    """
    OPCIÓN B: Crear movimientos EGRESO en cuentas ficticias por unidad interna.
    NO crea cont_pago ni cont_gasto. Agrupa detalles por unidad_interna_id,
    suma neto_pagar, y crea un fin_movimiento_cuenta EGRESO por cada cuenta ficticia.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        async with conn.transaction():
            planilla = await conn.fetchrow(
                "SELECT * FROM finanzas2.cont_planilla WHERE id = $1 AND empresa_id = $2", id, empresa_id)
            if not planilla:
                raise HTTPException(404, "Planilla no encontrada")
            if planilla['estado'] == 'pagada':
                raise HTTPException(400, "La planilla ya está pagada")
            if planilla['estado'] == 'borrador':
                raise HTTPException(400, "La planilla debe estar aprobada antes de pagar")

            # Group detalles by unidad_interna_id and sum neto_pagar
            detalles = await conn.fetch("""
                SELECT unidad_interna_id, SUM(neto_pagar) as total
                FROM finanzas2.cont_planilla_detalle
                WHERE planilla_id = $1 AND unidad_interna_id IS NOT NULL
                GROUP BY unidad_interna_id
            """, id)

            # Also get workers without unidad_interna
            sin_unidad = await conn.fetchval("""
                SELECT SUM(neto_pagar) FROM finanzas2.cont_planilla_detalle
                WHERE planilla_id = $1 AND unidad_interna_id IS NULL
            """, id)

            if not detalles and not sin_unidad:
                raise HTTPException(400, "No hay detalles en la planilla para pagar")

            movimientos_creados = []
            fecha_pago = datetime.now().date()

            for det in detalles:
                ui_id = det['unidad_interna_id']
                monto = float(det['total'])
                if monto <= 0:
                    continue

                # Find the fictitious account for this unidad_interna
                cuenta = await conn.fetchrow("""
                    SELECT id, nombre, saldo_actual
                    FROM finanzas2.cont_cuenta_financiera
                    WHERE empresa_id = $1 AND es_ficticia = true AND unidad_interna_id = $2
                """, empresa_id, ui_id)

                if not cuenta:
                    raise HTTPException(400,
                        f"No se encontró cuenta ficticia para unidad interna ID {ui_id}")

                # Create EGRESO movement
                mov = await conn.fetchrow("""
                    INSERT INTO finanzas2.fin_movimiento_cuenta
                    (cuenta_id, empresa_id, tipo, monto, descripcion, fecha, referencia_id, referencia_tipo)
                    VALUES ($1, $2, 'EGRESO', $3, $4, $5, $6, 'planilla')
                    RETURNING id
                """, cuenta['id'], empresa_id, monto,
                    f"Pago planilla {planilla['periodo']}", fecha_pago, str(id))

                # Update account balance (EGRESO = subtract)
                await conn.execute("""
                    UPDATE finanzas2.cont_cuenta_financiera
                    SET saldo_actual = saldo_actual - $1
                    WHERE id = $2
                """, monto, cuenta['id'])

                nuevo_saldo = await conn.fetchval(
                    "SELECT saldo_actual FROM finanzas2.cont_cuenta_financiera WHERE id = $1", cuenta['id'])

                movimientos_creados.append({
                    "cuenta_id": cuenta['id'],
                    "cuenta_nombre": cuenta['nombre'],
                    "unidad_interna_id": ui_id,
                    "monto": monto,
                    "nuevo_saldo": float(nuevo_saldo),
                    "movimiento_id": mov['id'],
                })

            # Handle workers without unidad_interna (if any) — warn but don't block
            monto_sin_unidad = float(sin_unidad) if sin_unidad else 0

            # Mark adelantos as descontados
            await conn.execute("""
                UPDATE finanzas2.cont_adelanto_empleado
                SET descontado = TRUE, planilla_id = $1
                WHERE empleado_id IN (SELECT empleado_id FROM finanzas2.cont_planilla_detalle WHERE planilla_id = $1)
                AND pagado = TRUE AND descontado = FALSE
            """, id)

            # Update planilla state
            await conn.execute("""
                UPDATE finanzas2.cont_planilla
                SET estado = 'pagada', fecha_pago = $1
                WHERE id = $2
            """, fecha_pago, id)

            planilla_data = await get_planilla(id, empresa_id)
            return {
                **planilla_data,
                "movimientos_creados": movimientos_creados,
                "monto_sin_unidad": monto_sin_unidad,
            }


@router.post("/planillas/{id}/anular-pago")
async def anular_pago_planilla(id: int, empresa_id: int = Depends(get_empresa_id)):
    """
    Reversa el pago de una planilla: crea movimientos INGRESO para cada EGRESO
    que se creó al pagar, restaura saldos de cuentas ficticias, y vuelve estado a 'aprobado'.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        async with conn.transaction():
            planilla = await conn.fetchrow(
                "SELECT * FROM finanzas2.cont_planilla WHERE id = $1 AND empresa_id = $2", id, empresa_id)
            if not planilla:
                raise HTTPException(404, "Planilla no encontrada")
            if planilla['estado'] != 'pagada':
                raise HTTPException(400, "Solo se puede anular el pago de una planilla pagada")

            # Find all EGRESO movements for this planilla
            movimientos = await conn.fetch("""
                SELECT id, cuenta_id, monto
                FROM finanzas2.fin_movimiento_cuenta
                WHERE empresa_id = $1 AND referencia_tipo = 'planilla' AND referencia_id = $2 AND tipo = 'EGRESO'
            """, empresa_id, str(id))

            reversas = []
            fecha_anulacion = datetime.now().date()

            for mov in movimientos:
                monto = float(mov['monto'])

                # Create INGRESO reversal
                await conn.execute("""
                    INSERT INTO finanzas2.fin_movimiento_cuenta
                    (cuenta_id, empresa_id, tipo, monto, descripcion, fecha, referencia_id, referencia_tipo)
                    VALUES ($1, $2, 'INGRESO', $3, $4, $5, $6, 'planilla_anulacion')
                """, mov['cuenta_id'], empresa_id, monto,
                    f"Anulación pago planilla {planilla['periodo']}", fecha_anulacion, str(id))

                # Restore account balance
                await conn.execute("""
                    UPDATE finanzas2.cont_cuenta_financiera
                    SET saldo_actual = saldo_actual + $1
                    WHERE id = $2
                """, monto, mov['cuenta_id'])

                cuenta = await conn.fetchrow(
                    "SELECT nombre, saldo_actual FROM finanzas2.cont_cuenta_financiera WHERE id = $1",
                    mov['cuenta_id'])

                reversas.append({
                    "cuenta_id": mov['cuenta_id'],
                    "cuenta_nombre": cuenta['nombre'],
                    "monto_revertido": monto,
                    "nuevo_saldo": float(cuenta['saldo_actual']),
                })

            # Revert adelantos
            await conn.execute("""
                UPDATE finanzas2.cont_adelanto_empleado
                SET descontado = FALSE, planilla_id = NULL
                WHERE planilla_id = $1
            """, id)

            # Reset planilla state
            await conn.execute("""
                UPDATE finanzas2.cont_planilla
                SET estado = 'aprobado', fecha_pago = NULL, pago_id = NULL
                WHERE id = $1
            """, id)

            planilla_data = await get_planilla(id, empresa_id)
            return {
                **planilla_data,
                "reversas": reversas,
            }


@router.delete("/planillas/{id}")
async def delete_planilla(id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        existing = await conn.fetchrow("SELECT * FROM finanzas2.cont_planilla WHERE id = $1 AND empresa_id = $2", id, empresa_id)
        if not existing:
            raise HTTPException(404, "Planilla no encontrada")
        if existing['estado'] == 'pagada':
            raise HTTPException(400, "No se puede eliminar una planilla pagada")
        await conn.execute("DELETE FROM finanzas2.cont_planilla_detalle WHERE planilla_id = $1", id)
        await conn.execute("DELETE FROM finanzas2.cont_planilla WHERE id = $1 AND empresa_id = $2", id, empresa_id)
        return {"message": "Planilla eliminada"}
