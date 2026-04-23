"""
Adelantos a trabajadores (Opción B del diseño):
- Al crear: genera EGRESO real en la cuenta_pago_id (saldo baja)
- Al eliminar: genera INGRESO reverso (saldo vuelve) — solo si no está descontado
- Al descontar en planilla: marca descontado=true + planilla_id
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
from database import get_pool
from dependencies import get_empresa_id

router = APIRouter(tags=["Adelantos Trabajador"])


class AdelantoIn(BaseModel):
    trabajador_id: int
    fecha: date
    monto: float = Field(gt=0)
    motivo: Optional[str] = None
    cuenta_pago_id: int


# ───── LIST ─────
@router.get("/adelantos-trabajador")
async def list_adelantos(
    trabajador_id: Optional[int] = None,
    pendientes: Optional[bool] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        conds = ["a.empresa_id = $1"]
        params = [empresa_id]
        idx = 2
        if trabajador_id:
            conds.append(f"a.trabajador_id = ${idx}"); params.append(trabajador_id); idx += 1
        if pendientes is not None:
            conds.append(f"a.descontado = ${idx}"); params.append(not pendientes); idx += 1

        rows = await conn.fetch(f"""
            SELECT a.*,
                   t.nombre AS trabajador_nombre,
                   t.dni    AS trabajador_dni,
                   c.nombre AS cuenta_nombre,
                   c.tipo   AS cuenta_tipo
              FROM finanzas2.fin_adelanto_trabajador a
              LEFT JOIN finanzas2.fin_trabajador t ON a.trabajador_id = t.id
              LEFT JOIN finanzas2.cont_cuenta_financiera c ON a.cuenta_pago_id = c.id
             WHERE {' AND '.join(conds)}
             ORDER BY a.fecha DESC, a.id DESC
        """, *params)
        return [dict(r) for r in rows]


# ───── POR TRABAJADOR (pendientes) — usado por el popup del wizard ─────
@router.get("/adelantos-trabajador/trabajador/{trabajador_id}/pendientes")
async def adelantos_pendientes(
    trabajador_id: int,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT a.*, c.nombre AS cuenta_nombre
              FROM finanzas2.fin_adelanto_trabajador a
              LEFT JOIN finanzas2.cont_cuenta_financiera c ON a.cuenta_pago_id = c.id
             WHERE a.empresa_id = $1
               AND a.trabajador_id = $2
               AND a.descontado = FALSE
             ORDER BY a.fecha ASC
        """, empresa_id, trabajador_id)
        return [dict(r) for r in rows]


# ───── CREATE (con EGRESO automático) ─────
@router.post("/adelantos-trabajador")
async def create_adelanto(data: AdelantoIn, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            trab = await conn.fetchrow(
                "SELECT id, nombre FROM finanzas2.fin_trabajador WHERE id = $1 AND empresa_id = $2",
                data.trabajador_id, empresa_id)
            if not trab:
                raise HTTPException(404, "Trabajador no encontrado")
            cta = await conn.fetchrow(
                "SELECT id, nombre, saldo_actual FROM finanzas2.cont_cuenta_financiera WHERE id = $1 AND empresa_id = $2",
                data.cuenta_pago_id, empresa_id)
            if not cta:
                raise HTTPException(404, "Cuenta no encontrada")

            adel = await conn.fetchrow("""
                INSERT INTO finanzas2.fin_adelanto_trabajador
                    (empresa_id, trabajador_id, fecha, monto, motivo, cuenta_pago_id)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
            """, empresa_id, data.trabajador_id, data.fecha, data.monto, data.motivo, data.cuenta_pago_id)

            # Generar EGRESO
            desc = f"Adelanto a {trab['nombre']}" + (f" — {data.motivo}" if data.motivo else "")
            mov = await conn.fetchrow("""
                INSERT INTO finanzas2.fin_movimiento_cuenta
                    (cuenta_id, empresa_id, tipo, monto, descripcion, fecha, referencia_id, referencia_tipo)
                VALUES ($1, $2, 'EGRESO', $3, $4, $5, $6, 'adelanto')
                RETURNING id
            """, data.cuenta_pago_id, empresa_id, data.monto, desc, data.fecha, str(adel['id']))

            await conn.execute("""
                UPDATE finanzas2.cont_cuenta_financiera
                   SET saldo_actual = saldo_actual - $1, updated_at = NOW()
                 WHERE id = $2
            """, data.monto, data.cuenta_pago_id)

            await conn.execute(
                "UPDATE finanzas2.fin_adelanto_trabajador SET movimiento_cuenta_id = $1 WHERE id = $2",
                mov['id'], adel['id'])

            # Devolver con datos enriquecidos
            full = await conn.fetchrow("""
                SELECT a.*, t.nombre AS trabajador_nombre, c.nombre AS cuenta_nombre
                  FROM finanzas2.fin_adelanto_trabajador a
                  LEFT JOIN finanzas2.fin_trabajador t ON a.trabajador_id = t.id
                  LEFT JOIN finanzas2.cont_cuenta_financiera c ON a.cuenta_pago_id = c.id
                 WHERE a.id = $1
            """, adel['id'])
            return dict(full)


# ───── DELETE (revierte EGRESO) ─────
@router.delete("/adelantos-trabajador/{adelanto_id}")
async def delete_adelanto(adelanto_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            adel = await conn.fetchrow(
                "SELECT * FROM finanzas2.fin_adelanto_trabajador WHERE id = $1 AND empresa_id = $2",
                adelanto_id, empresa_id)
            if not adel:
                raise HTTPException(404, "Adelanto no encontrado")
            if adel['descontado']:
                raise HTTPException(400, "No se puede eliminar: el adelanto ya fue descontado en una planilla")

            if adel['movimiento_cuenta_id']:
                await conn.execute("""
                    INSERT INTO finanzas2.fin_movimiento_cuenta
                        (cuenta_id, empresa_id, tipo, monto, descripcion, fecha, referencia_id, referencia_tipo)
                    VALUES ($1, $2, 'INGRESO', $3, $4, CURRENT_DATE, $5, 'adelanto_reverso')
                """, adel['cuenta_pago_id'], empresa_id, adel['monto'],
                     f"Reversión adelanto #{adel['id']}", str(adel['id']))

                await conn.execute("""
                    UPDATE finanzas2.cont_cuenta_financiera
                       SET saldo_actual = saldo_actual + $1, updated_at = NOW()
                     WHERE id = $2
                """, adel['monto'], adel['cuenta_pago_id'])

            await conn.execute("DELETE FROM finanzas2.fin_adelanto_trabajador WHERE id = $1", adelanto_id)
            return {"message": "Adelanto eliminado y egreso revertido"}
