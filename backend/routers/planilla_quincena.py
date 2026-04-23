"""
Planilla Quincenal — Wizard completo.

Flujo:
1. POST /planillas-quincena/calcular — genera preview (no guarda)
2. POST /planillas-quincena — crea en borrador con detalles
3. PUT /planillas-quincena/{id} — actualiza detalles (borrador)
4. POST /planillas-quincena/{id}/aprobar — pasa a aprobada
5. POST /planillas-quincena/{id}/pagar — con body [{cuenta_id, monto, referencia}]
   → genera EGRESOS en cuentas indicadas
   → marca adelantos como descontados
   → estado = pagada
6. POST /planillas-quincena/{id}/anular-pago
   → revierte EGRESOS con INGRESOS
   → adelantos vuelven a pendientes
   → estado = aprobada

Fórmula del neto por trabajador:
  subtotal_horas = horas_normales × hora_simple
                 + horas_extra_25 × hora_extra_25
                 + horas_extra_35 × hora_extra_35
  neto = subtotal_horas + asig_familiar_monto - afp_total - tardanzas - adelantos
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from calendar import monthrange
from database import get_pool
from dependencies import get_empresa_id


# Placeholder para usuario actual (sin auth en este proyecto)
async def get_current_user():
    return {"username": "sistema"}

router = APIRouter(tags=["Planilla Quincena"])

# Los montos legales (AFP, asig familiar) son MENSUALES.
# En planilla quincenal se descuenta la mitad en cada quincena.
FACTOR_QUINCENA = 0.5


# ───────── MODELS ─────────

class CalcularInput(BaseModel):
    anio: int
    mes: int = Field(ge=1, le=12)
    quincena: int = Field(ge=1, le=2)


class DetalleIn(BaseModel):
    trabajador_id: int
    horas_normales: float = 0
    horas_extra_25: float = 0
    horas_extra_35: float = 0
    descuento_tardanzas: float = 0
    adelantos_ids: List[int] = []
    notas: Optional[str] = None


class PlanillaCreateIn(BaseModel):
    anio: int
    mes: int
    quincena: int
    fecha_inicio: date
    fecha_fin: date
    detalles: List[DetalleIn]
    notas: Optional[str] = None


class PlanillaUpdateIn(BaseModel):
    detalles: List[DetalleIn]
    notas: Optional[str] = None


class PagoIn(BaseModel):
    cuenta_id: int
    monto: float = Field(gt=0)
    referencia: Optional[str] = None
    notas: Optional[str] = None


class PagarIn(BaseModel):
    pagos: List[PagoIn]
    fecha_pago: Optional[date] = None


# ───────── HELPERS ─────────

def calcular_periodo(anio: int, mes: int, quincena: int) -> tuple[date, date]:
    """Dado año/mes/quincena (1 o 2) retorna (fecha_inicio, fecha_fin)."""
    if quincena == 1:
        return date(anio, mes, 1), date(anio, mes, 15)
    last = monthrange(anio, mes)[1]
    return date(anio, mes, 16), date(anio, mes, last)


def calcular_tarifas(sueldo_basico_total: float) -> dict:
    """Dado el sueldo mensual, devuelve hora_simple, extra_25, extra_35 (2 decimales)."""
    hs = round(sueldo_basico_total / 30 / 8, 2) if sueldo_basico_total > 0 else 0
    return {
        "hora_simple": hs,
        "hora_extra_25": round(hs * 1.25, 2),
        "hora_extra_35": round(hs * 1.35, 2),
    }


def calcular_linea(det: dict, ajustes: dict, afp: Optional[dict]) -> dict:
    """Calcula todos los subtotales de una línea de planilla."""
    sbt = float(det.get('sueldo_basico_total') or 0)
    sueldo_planilla = float(det.get('sueldo_planilla') or 0)
    asig_familiar = det.get('asignacion_familiar', False)
    hn = float(det.get('horas_normales') or 0)
    h25 = float(det.get('horas_extra_25') or 0)
    h35 = float(det.get('horas_extra_35') or 0)
    tardanzas = float(det.get('descuento_tardanzas') or 0)
    adelantos = float(det.get('monto_adelantos') or 0)

    t = calcular_tarifas(sbt)
    monto_hn = round(hn * t['hora_simple'], 2)
    monto_h25 = round(h25 * t['hora_extra_25'], 2)
    monto_h35 = round(h35 * t['hora_extra_35'], 2)
    subtotal_horas = round(monto_hn + monto_h25 + monto_h35, 2)

    sueldo_min = float(ajustes.get('sueldo_minimo') or 0)
    asig_pct = float(ajustes.get('asignacion_familiar_pct') or 0) / 100
    # Asignación familiar MENSUAL, dividida por quincena
    asig_monto_mensual = round(sueldo_min * asig_pct, 2) if asig_familiar else 0
    asig_monto = round(asig_monto_mensual * FACTOR_QUINCENA, 2)

    # AFP: se calcula sobre la remuneración MENSUAL y luego se divide para quincena.
    # Solo si tiene sueldo_planilla > 0 y afp asignada.
    afp_aporte = 0.0
    afp_prima = 0.0
    if sueldo_planilla > 0 and afp:
        base_mensual = sueldo_planilla + asig_monto_mensual
        afp_aporte_mensual = round(base_mensual * float(afp['aporte_obligatorio_pct']) / 100, 2)
        afp_prima_mensual = round(base_mensual * float(afp['prima_seguro_pct']) / 100, 2)
        afp_aporte = round(afp_aporte_mensual * FACTOR_QUINCENA, 2)
        afp_prima = round(afp_prima_mensual * FACTOR_QUINCENA, 2)
    afp_total = round(afp_aporte + afp_prima, 2)

    neto = round(subtotal_horas + asig_monto - afp_total - tardanzas - adelantos, 2)

    return {
        **t,
        "monto_horas_normales": monto_hn,
        "monto_horas_25": monto_h25,
        "monto_horas_35": monto_h35,
        "subtotal_horas": subtotal_horas,
        "asig_familiar_monto": asig_monto,
        "afp_aporte": afp_aporte,
        "afp_prima": afp_prima,
        "afp_total": afp_total,
        "neto": neto,
    }


async def _cargar_trabajador(conn, trabajador_id: int, empresa_id: int):
    return await conn.fetchrow("""
        SELECT t.*, ui.nombre AS unidad_interna_nombre, a.nombre AS afp_nombre,
               a.aporte_obligatorio_pct, a.prima_seguro_pct
          FROM finanzas2.fin_trabajador t
          LEFT JOIN finanzas2.fin_unidad_interna ui ON t.unidad_interna_id = ui.id
          LEFT JOIN finanzas2.fin_afp a              ON t.afp_id = a.id
         WHERE t.id = $1 AND t.empresa_id = $2
    """, trabajador_id, empresa_id)


# ───────── CALCULAR PREVIEW ─────────

@router.post("/planillas-quincena/calcular")
async def calcular_preview(data: CalcularInput, empresa_id: int = Depends(get_empresa_id)):
    """Genera el preview inicial: carga trabajadores activos con horas default = horas_quincenales del trabajador."""
    fi, ff = calcular_periodo(data.anio, data.mes, data.quincena)
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Ajustes
        ajustes = await conn.fetchrow(
            "SELECT * FROM finanzas2.fin_ajustes_planilla WHERE empresa_id = $1", empresa_id)
        if not ajustes:
            raise HTTPException(500, "Empresa sin ajustes de planilla configurados")
        ajustes_d = dict(ajustes)

        # Verificar si ya existe planilla en este periodo
        existe = await conn.fetchval("""
            SELECT id FROM finanzas2.fin_planilla_quincena
             WHERE empresa_id = $1 AND anio = $2 AND mes = $3 AND quincena = $4
        """, empresa_id, data.anio, data.mes, data.quincena)

        # Trabajadores activos
        trabs = await conn.fetch("""
            SELECT t.*, ui.nombre AS unidad_interna_nombre,
                   a.nombre AS afp_nombre, a.aporte_obligatorio_pct, a.prima_seguro_pct
              FROM finanzas2.fin_trabajador t
              LEFT JOIN finanzas2.fin_unidad_interna ui ON t.unidad_interna_id = ui.id
              LEFT JOIN finanzas2.fin_afp a              ON t.afp_id = a.id
             WHERE t.empresa_id = $1 AND t.activo = TRUE
             ORDER BY t.nombre
        """, empresa_id)

        lineas = []
        warnings = []
        for t in trabs:
            td = dict(t)
            afp = None
            if td.get('afp_id'):
                afp = {
                    'aporte_obligatorio_pct': td['aporte_obligatorio_pct'],
                    'prima_seguro_pct': td['prima_seguro_pct'],
                }
            # Warning: tiene sueldo_planilla > 0 pero no AFP asignada
            if (td.get('sueldo_planilla') or 0) > 0 and not td.get('afp_id'):
                warnings.append({
                    "trabajador_id": td['id'],
                    "trabajador_nombre": td['nombre'],
                    "tipo": "sin_afp_con_sueldo_planilla",
                    "mensaje": "Tiene sueldo de planilla pero no tiene AFP asignada",
                })
            # Horas default = horas_quincenales del trabajador
            horas_default = td.get('horas_quincenales') or ajustes_d.get('horas_quincena_default') or 120
            det = {
                "trabajador_id": td['id'],
                "nombre": td['nombre'],
                "dni": td.get('dni'),
                "area": td.get('area'),
                "unidad_interna_id": td.get('unidad_interna_id'),
                "unidad_interna_nombre": td.get('unidad_interna_nombre'),
                "sueldo_planilla": float(td.get('sueldo_planilla') or 0),
                "sueldo_basico": float(td.get('sueldo_basico') or 0),
                "sueldo_basico_total": float(td.get('sueldo_basico_total') or 0),
                "afp_id": td.get('afp_id'),
                "afp_nombre": td.get('afp_nombre'),
                "asignacion_familiar": td.get('asignacion_familiar', False),
                "horas_normales": float(horas_default),
                "horas_extra_25": 0.0,
                "horas_extra_35": 0.0,
                "descuento_tardanzas": 0.0,
                "monto_adelantos": 0.0,
            }
            calc = calcular_linea(det, ajustes_d, afp)
            det.update(calc)
            lineas.append(det)

        return {
            "anio": data.anio,
            "mes": data.mes,
            "quincena": data.quincena,
            "fecha_inicio": str(fi),
            "fecha_fin": str(ff),
            "planilla_existente_id": existe,
            "trabajadores": lineas,
            "warnings": warnings,
            "ajustes": dict(ajustes_d),
        }


# ───────── CREATE (borrador) ─────────

@router.post("/planillas-quincena")
async def create_planilla(
    data: PlanillaCreateIn,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            ajustes = await conn.fetchrow(
                "SELECT * FROM finanzas2.fin_ajustes_planilla WHERE empresa_id = $1", empresa_id)
            ajustes_d = dict(ajustes) if ajustes else {}

            # Verificar que no exista otra planilla en este periodo
            existe = await conn.fetchval("""
                SELECT id FROM finanzas2.fin_planilla_quincena
                 WHERE empresa_id = $1 AND anio = $2 AND mes = $3 AND quincena = $4
            """, empresa_id, data.anio, data.mes, data.quincena)
            if existe:
                raise HTTPException(400, f"Ya existe una planilla para {data.anio}-{data.mes:02d}-Q{data.quincena}")

            # Crear cabecera
            pl = await conn.fetchrow("""
                INSERT INTO finanzas2.fin_planilla_quincena
                    (empresa_id, anio, mes, quincena, fecha_inicio, fecha_fin, estado, notas)
                VALUES ($1, $2, $3, $4, $5, $6, 'borrador', $7)
                RETURNING *
            """, empresa_id, data.anio, data.mes, data.quincena,
                 data.fecha_inicio, data.fecha_fin, data.notas)

            planilla_id = pl['id']
            totales = {'bruto': 0.0, 'asig_fam': 0.0, 'afp': 0.0,
                       'tardanzas': 0.0, 'adelantos': 0.0, 'neto': 0.0}

            for det_in in data.detalles:
                trab = await _cargar_trabajador(conn, det_in.trabajador_id, empresa_id)
                if not trab:
                    continue
                td = dict(trab)
                afp = {'aporte_obligatorio_pct': td['aporte_obligatorio_pct'],
                       'prima_seguro_pct': td['prima_seguro_pct']} if td.get('afp_id') else None

                # Sumar adelantos vinculados
                monto_adelantos = 0.0
                if det_in.adelantos_ids:
                    total_adel = await conn.fetchval("""
                        SELECT COALESCE(SUM(monto), 0)
                          FROM finanzas2.fin_adelanto_trabajador
                         WHERE id = ANY($1::int[])
                           AND trabajador_id = $2
                           AND empresa_id = $3
                           AND descontado = FALSE
                    """, det_in.adelantos_ids, det_in.trabajador_id, empresa_id)
                    monto_adelantos = float(total_adel or 0)

                det_dict = {
                    **td,
                    'sueldo_basico_total': float(td.get('sueldo_basico_total') or 0),
                    'horas_normales': det_in.horas_normales,
                    'horas_extra_25': det_in.horas_extra_25,
                    'horas_extra_35': det_in.horas_extra_35,
                    'descuento_tardanzas': det_in.descuento_tardanzas,
                    'monto_adelantos': monto_adelantos,
                }
                calc = calcular_linea(det_dict, ajustes_d, afp)

                # Insert detalle
                det_row = await conn.fetchrow("""
                    INSERT INTO finanzas2.fin_planilla_quincena_detalle
                        (planilla_id, empresa_id, trabajador_id, nombre, dni, area,
                         unidad_interna_id, unidad_interna_nombre,
                         sueldo_planilla, sueldo_basico, sueldo_basico_total,
                         afp_id, afp_nombre, asignacion_familiar,
                         hora_simple, hora_extra_25, hora_extra_35,
                         horas_normales, horas_extra_25, horas_extra_35,
                         monto_horas_normales, monto_horas_25, monto_horas_35, subtotal_horas,
                         asig_familiar_monto, afp_aporte, afp_prima, afp_total,
                         descuento_tardanzas, monto_adelantos, neto, notas)
                    VALUES ($1, $2, $3, $4, $5, $6,
                            $7, $8,
                            $9, $10, $11,
                            $12, $13, $14,
                            $15, $16, $17,
                            $18, $19, $20,
                            $21, $22, $23, $24,
                            $25, $26, $27, $28,
                            $29, $30, $31, $32)
                    RETURNING id
                """, planilla_id, empresa_id, td['id'], td['nombre'], td.get('dni'), td.get('area'),
                     td.get('unidad_interna_id'), td.get('unidad_interna_nombre'),
                     float(td.get('sueldo_planilla') or 0), float(td.get('sueldo_basico') or 0),
                     float(td.get('sueldo_basico_total') or 0),
                     td.get('afp_id'), td.get('afp_nombre'), td.get('asignacion_familiar', False),
                     calc['hora_simple'], calc['hora_extra_25'], calc['hora_extra_35'],
                     det_in.horas_normales, det_in.horas_extra_25, det_in.horas_extra_35,
                     calc['monto_horas_normales'], calc['monto_horas_25'], calc['monto_horas_35'], calc['subtotal_horas'],
                     calc['asig_familiar_monto'], calc['afp_aporte'], calc['afp_prima'], calc['afp_total'],
                     det_in.descuento_tardanzas, monto_adelantos, calc['neto'], det_in.notas)

                # Vincular adelantos al detalle (PERO no marcar como descontados aún — eso se hace al pagar)
                if det_in.adelantos_ids:
                    await conn.execute("""
                        UPDATE finanzas2.fin_adelanto_trabajador
                           SET planilla_id = $1, detalle_id = $2, updated_at = NOW()
                         WHERE id = ANY($3::int[])
                           AND empresa_id = $4
                    """, planilla_id, det_row['id'], det_in.adelantos_ids, empresa_id)

                totales['bruto'] += calc['subtotal_horas']
                totales['asig_fam'] += calc['asig_familiar_monto']
                totales['afp'] += calc['afp_total']
                totales['tardanzas'] += det_in.descuento_tardanzas
                totales['adelantos'] += monto_adelantos
                totales['neto'] += calc['neto']

            # Actualizar totales en cabecera
            await conn.execute("""
                UPDATE finanzas2.fin_planilla_quincena SET
                    total_bruto = $1, total_asig_familiar = $2, total_afp = $3,
                    total_tardanzas = $4, total_adelantos = $5, total_neto = $6,
                    updated_at = NOW()
                WHERE id = $7
            """, totales['bruto'], totales['asig_fam'], totales['afp'],
                 totales['tardanzas'], totales['adelantos'], totales['neto'], planilla_id)

            return await _get_planilla_full(conn, planilla_id, empresa_id)


# ───────── LIST ─────────

@router.get("/planillas-quincena")
async def list_planillas(
    estado: Optional[str] = None,
    anio: Optional[int] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        conds = ["empresa_id = $1"]
        params = [empresa_id]
        idx = 2
        if estado:
            conds.append(f"estado = ${idx}"); params.append(estado); idx += 1
        if anio:
            conds.append(f"anio = ${idx}"); params.append(anio); idx += 1

        rows = await conn.fetch(f"""
            SELECT p.*,
                   (SELECT COUNT(*) FROM finanzas2.fin_planilla_quincena_detalle WHERE planilla_id = p.id) AS num_trabajadores
              FROM finanzas2.fin_planilla_quincena p
             WHERE {' AND '.join(conds)}
             ORDER BY p.anio DESC, p.mes DESC, p.quincena DESC
        """, *params)
        return [dict(r) for r in rows]


# ───────── DETAIL ─────────

async def _get_planilla_full(conn, planilla_id: int, empresa_id: int) -> dict:
    cab = await conn.fetchrow(
        "SELECT * FROM finanzas2.fin_planilla_quincena WHERE id = $1 AND empresa_id = $2",
        planilla_id, empresa_id)
    if not cab:
        raise HTTPException(404, "Planilla no encontrada")
    dets = await conn.fetch("""
        SELECT * FROM finanzas2.fin_planilla_quincena_detalle
         WHERE planilla_id = $1
         ORDER BY nombre
    """, planilla_id)
    pagos = await conn.fetch("""
        SELECT pg.*, c.nombre AS cuenta_nombre
          FROM finanzas2.fin_planilla_quincena_pago pg
          LEFT JOIN finanzas2.cont_cuenta_financiera c ON pg.cuenta_id = c.id
         WHERE pg.planilla_id = $1
         ORDER BY pg.id
    """, planilla_id)
    # Adelantos vinculados a cada detalle
    adelantos = await conn.fetch("""
        SELECT * FROM finanzas2.fin_adelanto_trabajador
         WHERE planilla_id = $1
    """, planilla_id)
    return {
        **dict(cab),
        "detalles": [dict(d) for d in dets],
        "pagos": [dict(p) for p in pagos],
        "adelantos_vinculados": [dict(a) for a in adelantos],
    }


@router.get("/planillas-quincena/{planilla_id}")
async def get_planilla(planilla_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await _get_planilla_full(conn, planilla_id, empresa_id)


# ───────── UPDATE (solo borrador) ─────────

@router.put("/planillas-quincena/{planilla_id}")
async def update_planilla(
    planilla_id: int,
    data: PlanillaUpdateIn,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            pl = await conn.fetchrow(
                "SELECT * FROM finanzas2.fin_planilla_quincena WHERE id = $1 AND empresa_id = $2",
                planilla_id, empresa_id)
            if not pl:
                raise HTTPException(404, "Planilla no encontrada")
            if pl['estado'] != 'borrador':
                raise HTTPException(400, "Solo se puede editar planilla en borrador")

            ajustes = await conn.fetchrow(
                "SELECT * FROM finanzas2.fin_ajustes_planilla WHERE empresa_id = $1", empresa_id)
            ajustes_d = dict(ajustes) if ajustes else {}

            # Desvincular adelantos viejos
            await conn.execute("""
                UPDATE finanzas2.fin_adelanto_trabajador
                   SET planilla_id = NULL, detalle_id = NULL, updated_at = NOW()
                 WHERE planilla_id = $1
            """, planilla_id)
            # Borrar detalles existentes
            await conn.execute(
                "DELETE FROM finanzas2.fin_planilla_quincena_detalle WHERE planilla_id = $1",
                planilla_id)

            totales = {'bruto': 0.0, 'asig_fam': 0.0, 'afp': 0.0,
                       'tardanzas': 0.0, 'adelantos': 0.0, 'neto': 0.0}
            for det_in in data.detalles:
                trab = await _cargar_trabajador(conn, det_in.trabajador_id, empresa_id)
                if not trab: continue
                td = dict(trab)
                afp = {'aporte_obligatorio_pct': td['aporte_obligatorio_pct'],
                       'prima_seguro_pct': td['prima_seguro_pct']} if td.get('afp_id') else None

                monto_adelantos = 0.0
                if det_in.adelantos_ids:
                    total_adel = await conn.fetchval("""
                        SELECT COALESCE(SUM(monto), 0)
                          FROM finanzas2.fin_adelanto_trabajador
                         WHERE id = ANY($1::int[])
                           AND trabajador_id = $2
                           AND empresa_id = $3
                           AND descontado = FALSE
                    """, det_in.adelantos_ids, det_in.trabajador_id, empresa_id)
                    monto_adelantos = float(total_adel or 0)

                det_dict = {**td, 'sueldo_basico_total': float(td.get('sueldo_basico_total') or 0),
                            'horas_normales': det_in.horas_normales,
                            'horas_extra_25': det_in.horas_extra_25,
                            'horas_extra_35': det_in.horas_extra_35,
                            'descuento_tardanzas': det_in.descuento_tardanzas,
                            'monto_adelantos': monto_adelantos}
                calc = calcular_linea(det_dict, ajustes_d, afp)

                det_row = await conn.fetchrow("""
                    INSERT INTO finanzas2.fin_planilla_quincena_detalle
                        (planilla_id, empresa_id, trabajador_id, nombre, dni, area,
                         unidad_interna_id, unidad_interna_nombre,
                         sueldo_planilla, sueldo_basico, sueldo_basico_total,
                         afp_id, afp_nombre, asignacion_familiar,
                         hora_simple, hora_extra_25, hora_extra_35,
                         horas_normales, horas_extra_25, horas_extra_35,
                         monto_horas_normales, monto_horas_25, monto_horas_35, subtotal_horas,
                         asig_familiar_monto, afp_aporte, afp_prima, afp_total,
                         descuento_tardanzas, monto_adelantos, neto, notas)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14,
                            $15, $16, $17, $18, $19, $20, $21, $22, $23, $24,
                            $25, $26, $27, $28, $29, $30, $31, $32)
                    RETURNING id
                """, planilla_id, empresa_id, td['id'], td['nombre'], td.get('dni'), td.get('area'),
                     td.get('unidad_interna_id'), td.get('unidad_interna_nombre'),
                     float(td.get('sueldo_planilla') or 0), float(td.get('sueldo_basico') or 0),
                     float(td.get('sueldo_basico_total') or 0),
                     td.get('afp_id'), td.get('afp_nombre'), td.get('asignacion_familiar', False),
                     calc['hora_simple'], calc['hora_extra_25'], calc['hora_extra_35'],
                     det_in.horas_normales, det_in.horas_extra_25, det_in.horas_extra_35,
                     calc['monto_horas_normales'], calc['monto_horas_25'], calc['monto_horas_35'], calc['subtotal_horas'],
                     calc['asig_familiar_monto'], calc['afp_aporte'], calc['afp_prima'], calc['afp_total'],
                     det_in.descuento_tardanzas, monto_adelantos, calc['neto'], det_in.notas)

                if det_in.adelantos_ids:
                    await conn.execute("""
                        UPDATE finanzas2.fin_adelanto_trabajador
                           SET planilla_id = $1, detalle_id = $2, updated_at = NOW()
                         WHERE id = ANY($3::int[]) AND empresa_id = $4
                    """, planilla_id, det_row['id'], det_in.adelantos_ids, empresa_id)

                totales['bruto'] += calc['subtotal_horas']
                totales['asig_fam'] += calc['asig_familiar_monto']
                totales['afp'] += calc['afp_total']
                totales['tardanzas'] += det_in.descuento_tardanzas
                totales['adelantos'] += monto_adelantos
                totales['neto'] += calc['neto']

            await conn.execute("""
                UPDATE finanzas2.fin_planilla_quincena SET
                    total_bruto = $1, total_asig_familiar = $2, total_afp = $3,
                    total_tardanzas = $4, total_adelantos = $5, total_neto = $6,
                    notas = $7, updated_at = NOW()
                WHERE id = $8
            """, totales['bruto'], totales['asig_fam'], totales['afp'],
                 totales['tardanzas'], totales['adelantos'], totales['neto'],
                 data.notas, planilla_id)

            return await _get_planilla_full(conn, planilla_id, empresa_id)


# ───────── APROBAR ─────────

@router.post("/planillas-quincena/{planilla_id}/aprobar")
async def aprobar_planilla(
    planilla_id: int,
    empresa_id: int = Depends(get_empresa_id),
    user=Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        pl = await conn.fetchrow(
            "SELECT * FROM finanzas2.fin_planilla_quincena WHERE id = $1 AND empresa_id = $2",
            planilla_id, empresa_id)
        if not pl:
            raise HTTPException(404, "Planilla no encontrada")
        if pl['estado'] != 'borrador':
            raise HTTPException(400, f"Solo se puede aprobar planilla en borrador (estado actual: {pl['estado']})")

        await conn.execute("""
            UPDATE finanzas2.fin_planilla_quincena
               SET estado = 'aprobada', aprobado_at = NOW(), aprobado_por = $1, updated_at = NOW()
             WHERE id = $2
        """, user.get('username') if user else None, planilla_id)
        return await _get_planilla_full(conn, planilla_id, empresa_id)


# ───────── PAGAR (con medios) ─────────

@router.post("/planillas-quincena/{planilla_id}/pagar")
async def pagar_planilla(
    planilla_id: int,
    data: PagarIn,
    empresa_id: int = Depends(get_empresa_id),
    user=Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            pl = await conn.fetchrow(
                "SELECT * FROM finanzas2.fin_planilla_quincena WHERE id = $1 AND empresa_id = $2",
                planilla_id, empresa_id)
            if not pl:
                raise HTTPException(404, "Planilla no encontrada")
            if pl['estado'] != 'aprobada':
                raise HTTPException(400, f"Planilla debe estar aprobada (estado actual: {pl['estado']})")

            total_neto = float(pl['total_neto'])
            suma_pagos = sum(float(p.monto) for p in data.pagos)
            if abs(suma_pagos - total_neto) > 0.01:
                raise HTTPException(400,
                    f"La suma de medios de pago ({suma_pagos:.2f}) no coincide con el total neto ({total_neto:.2f})")

            fecha_pago = data.fecha_pago or date.today()
            periodo_str = f"{pl['anio']}-{pl['mes']:02d}-Q{pl['quincena']}"

            # Crear EGRESOS y pagos
            for p in data.pagos:
                cta = await conn.fetchrow(
                    "SELECT id, nombre FROM finanzas2.cont_cuenta_financiera WHERE id = $1 AND empresa_id = $2",
                    p.cuenta_id, empresa_id)
                if not cta:
                    raise HTTPException(404, f"Cuenta {p.cuenta_id} no encontrada")

                mov = await conn.fetchrow("""
                    INSERT INTO finanzas2.fin_movimiento_cuenta
                        (cuenta_id, empresa_id, tipo, monto, descripcion, fecha, referencia_id, referencia_tipo)
                    VALUES ($1, $2, 'EGRESO', $3, $4, $5, $6, 'planilla_quincena')
                    RETURNING id
                """, p.cuenta_id, empresa_id, p.monto,
                     f"Pago planilla {periodo_str}" + (f" — {p.referencia}" if p.referencia else ""),
                     fecha_pago, str(planilla_id))

                await conn.execute("""
                    UPDATE finanzas2.cont_cuenta_financiera
                       SET saldo_actual = saldo_actual - $1, updated_at = NOW()
                     WHERE id = $2
                """, p.monto, p.cuenta_id)

                await conn.execute("""
                    INSERT INTO finanzas2.fin_planilla_quincena_pago
                        (planilla_id, empresa_id, cuenta_id, monto, referencia, notas, movimiento_cuenta_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, planilla_id, empresa_id, p.cuenta_id, p.monto, p.referencia, p.notas, mov['id'])

            # Marcar adelantos como descontados
            await conn.execute("""
                UPDATE finanzas2.fin_adelanto_trabajador
                   SET descontado = TRUE, updated_at = NOW()
                 WHERE planilla_id = $1 AND empresa_id = $2
            """, planilla_id, empresa_id)

            # Cambiar estado
            await conn.execute("""
                UPDATE finanzas2.fin_planilla_quincena
                   SET estado = 'pagada', fecha_pago = $1,
                       pagado_at = NOW(), pagado_por = $2, updated_at = NOW()
                 WHERE id = $3
            """, fecha_pago, user.get('username') if user else None, planilla_id)

            return await _get_planilla_full(conn, planilla_id, empresa_id)


# ───────── ANULAR PAGO ─────────

@router.post("/planillas-quincena/{planilla_id}/anular-pago")
async def anular_pago(
    planilla_id: int,
    empresa_id: int = Depends(get_empresa_id),
    user=Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            pl = await conn.fetchrow(
                "SELECT * FROM finanzas2.fin_planilla_quincena WHERE id = $1 AND empresa_id = $2",
                planilla_id, empresa_id)
            if not pl:
                raise HTTPException(404, "Planilla no encontrada")
            if pl['estado'] != 'pagada':
                raise HTTPException(400, "Solo se puede anular una planilla pagada")

            # Revertir movimientos
            pagos = await conn.fetch(
                "SELECT * FROM finanzas2.fin_planilla_quincena_pago WHERE planilla_id = $1",
                planilla_id)
            periodo_str = f"{pl['anio']}-{pl['mes']:02d}-Q{pl['quincena']}"
            for p in pagos:
                await conn.execute("""
                    INSERT INTO finanzas2.fin_movimiento_cuenta
                        (cuenta_id, empresa_id, tipo, monto, descripcion, fecha, referencia_id, referencia_tipo)
                    VALUES ($1, $2, 'INGRESO', $3, $4, CURRENT_DATE, $5, 'planilla_quincena_reverso')
                """, p['cuenta_id'], empresa_id, p['monto'],
                     f"Reversión pago planilla {periodo_str}", str(planilla_id))

                await conn.execute("""
                    UPDATE finanzas2.cont_cuenta_financiera
                       SET saldo_actual = saldo_actual + $1, updated_at = NOW()
                     WHERE id = $2
                """, p['monto'], p['cuenta_id'])

            # Borrar pagos
            await conn.execute(
                "DELETE FROM finanzas2.fin_planilla_quincena_pago WHERE planilla_id = $1",
                planilla_id)

            # Desmarcar adelantos
            await conn.execute("""
                UPDATE finanzas2.fin_adelanto_trabajador
                   SET descontado = FALSE, updated_at = NOW()
                 WHERE planilla_id = $1 AND empresa_id = $2
            """, planilla_id, empresa_id)

            # Volver a aprobada
            await conn.execute("""
                UPDATE finanzas2.fin_planilla_quincena
                   SET estado = 'aprobada', fecha_pago = NULL,
                       anulado_at = NOW(), anulado_por = $1,
                       pagado_at = NULL, pagado_por = NULL,
                       updated_at = NOW()
                 WHERE id = $2
            """, user.get('username') if user else None, planilla_id)

            return await _get_planilla_full(conn, planilla_id, empresa_id)


# ───────── DELETE ─────────

@router.delete("/planillas-quincena/{planilla_id}")
async def delete_planilla(
    planilla_id: int,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            pl = await conn.fetchrow(
                "SELECT * FROM finanzas2.fin_planilla_quincena WHERE id = $1 AND empresa_id = $2",
                planilla_id, empresa_id)
            if not pl:
                raise HTTPException(404, "Planilla no encontrada")
            if pl['estado'] not in ('borrador', 'anulada'):
                raise HTTPException(400, "Solo se puede eliminar borrador o anulada")

            # Liberar adelantos vinculados
            await conn.execute("""
                UPDATE finanzas2.fin_adelanto_trabajador
                   SET planilla_id = NULL, detalle_id = NULL, descontado = FALSE, updated_at = NOW()
                 WHERE planilla_id = $1
            """, planilla_id)

            await conn.execute(
                "DELETE FROM finanzas2.fin_planilla_quincena WHERE id = $1",
                planilla_id)
            return {"message": "Planilla eliminada"}
