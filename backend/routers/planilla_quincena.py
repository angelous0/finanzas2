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
import io
from database import get_pool
from dependencies import get_empresa_id
from services.treasury_service import create_movimiento_tesoreria, delete_movimientos_by_origen


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


class PagoTrabajadorIn(BaseModel):
    detalle_id: int
    medios: List[PagoIn]


class PagarDetalleIn(BaseModel):
    """Body para pagar un trabajador individual desde la tabla."""
    medios: List[PagoIn]
    fecha_pago: Optional[date] = None


class PagarIn(BaseModel):
    # Acepta dos formas:
    # - pagos_por_trabajador: lista de {detalle_id, medios[]} — nueva forma detallada
    # - pagos: lista plana [PagoIn] — legacy (sin detalle_id, pago consolidado)
    pagos_por_trabajador: Optional[List[PagoTrabajadorIn]] = None
    pagos: Optional[List[PagoIn]] = None
    fecha_pago: Optional[date] = None


# ───────── HELPERS ─────────

def calcular_periodo(anio: int, mes: int, quincena: int) -> tuple[date, date]:
    """Dado año/mes/quincena (1 o 2) retorna (fecha_inicio, fecha_fin)."""
    if quincena == 1:
        return date(anio, mes, 1), date(anio, mes, 15)
    last = monthrange(anio, mes)[1]
    return date(anio, mes, 16), date(anio, mes, last)


def calcular_tarifas(sueldo_basico_total: float) -> dict:
    """Dado el sueldo mensual, devuelve hora_simple, extra_25, extra_35.
    IMPORTANTE: NO redondeamos aquí. El redondeo solo se hace al FINAL (neto).
    El redondeo a 2 decimales es solo visual (helper fmt en UI).
    Para DB guardamos con 4 decimales de precisión.
    """
    hs = (sueldo_basico_total / 30 / 8) if sueldo_basico_total > 0 else 0
    return {
        "hora_simple": hs,
        "hora_extra_25": hs * 1.25,
        "hora_extra_35": hs * 1.35,
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
    # Cálculo sin redondeo intermedio — usamos la precisión completa de floats
    monto_hn_raw = hn * t['hora_simple']
    monto_h25_raw = h25 * t['hora_extra_25']
    monto_h35_raw = h35 * t['hora_extra_35']
    subtotal_horas_raw = monto_hn_raw + monto_h25_raw + monto_h35_raw

    sueldo_min = float(ajustes.get('sueldo_minimo') or 0)
    asig_pct = float(ajustes.get('asignacion_familiar_pct') or 0) / 100
    # Asignación familiar MENSUAL (sin redondeo), dividida por quincena
    asig_monto_mensual_raw = (sueldo_min * asig_pct) if asig_familiar else 0.0
    asig_monto_raw = asig_monto_mensual_raw * FACTOR_QUINCENA

    # AFP: se calcula sobre la remuneración MENSUAL y luego se divide para quincena.
    # Solo si tiene sueldo_planilla > 0 y afp asignada.
    afp_aporte_raw = 0.0
    afp_prima_raw = 0.0
    if sueldo_planilla > 0 and afp:
        base_mensual = sueldo_planilla + asig_monto_mensual_raw
        afp_aporte_raw = base_mensual * float(afp['aporte_obligatorio_pct']) / 100 * FACTOR_QUINCENA
        afp_prima_raw = base_mensual * float(afp['prima_seguro_pct']) / 100 * FACTOR_QUINCENA
    afp_total_raw = afp_aporte_raw + afp_prima_raw

    # Neto SIN redondeo intermedio — solo al final, 2 decimales
    neto_raw = subtotal_horas_raw + asig_monto_raw - afp_total_raw - tardanzas - adelantos

    # Retornamos TODO redondeado a 2 decimales para mostrar/persistir subtotales,
    # PERO el neto se calculó desde los valores raw (precisión completa).
    # Las tarifas se guardan con 4 decimales para mantener precisión en DB.
    return {
        "hora_simple":            round(t['hora_simple'], 4),
        "hora_extra_25":          round(t['hora_extra_25'], 4),
        "hora_extra_35":          round(t['hora_extra_35'], 4),
        "monto_horas_normales":   round(monto_hn_raw, 2),
        "monto_horas_25":         round(monto_h25_raw, 2),
        "monto_horas_35":         round(monto_h35_raw, 2),
        "subtotal_horas":         round(subtotal_horas_raw, 2),
        "asig_familiar_monto":    round(asig_monto_raw, 2),
        "afp_aporte":             round(afp_aporte_raw, 2),
        "afp_prima":              round(afp_prima_raw, 2),
        "afp_total":              round(afp_total_raw, 2),
        "neto":                   round(neto_raw, 2),
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

        # Precargar medios por defecto de todos los trabajadores
        medios_default_rows = await conn.fetch("""
            SELECT m.trabajador_id, m.cuenta_id, m.porcentaje, m.orden,
                   c.nombre AS cuenta_nombre
              FROM finanzas2.fin_trabajador_medio_pago_default m
              JOIN finanzas2.cont_cuenta_financiera c ON m.cuenta_id = c.id
             WHERE m.empresa_id = $1
             ORDER BY m.orden
        """, empresa_id)
        medios_por_trabajador = {}
        for r in medios_default_rows:
            medios_por_trabajador.setdefault(r['trabajador_id'], []).append({
                "cuenta_id": r['cuenta_id'],
                "cuenta_nombre": r['cuenta_nombre'],
                "porcentaje": float(r['porcentaje']),
            })

        # Precargar adelantos PENDIENTES (no descontados) de todos los trabajadores
        # — se autoseleccionan en el preview; el usuario puede desmarcar para postergar.
        adelantos_rows = await conn.fetch("""
            SELECT id, trabajador_id, fecha, monto, motivo, observaciones
              FROM finanzas2.fin_adelanto_trabajador
             WHERE empresa_id = $1 AND descontado = FALSE
             ORDER BY fecha ASC, id ASC
        """, empresa_id)
        adelantos_por_trabajador = {}
        for r in adelantos_rows:
            adelantos_por_trabajador.setdefault(r['trabajador_id'], []).append({
                "id": r['id'],
                "trabajador_id": r['trabajador_id'],
                "fecha": str(r['fecha']) if r['fecha'] else None,
                "monto": float(r['monto'] or 0),
                "motivo": r['motivo'],
                "observaciones": r['observaciones'],
            })

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
            # Adelantos pendientes del trabajador (auto-seleccionados)
            adel_pend = adelantos_por_trabajador.get(td['id'], [])
            monto_adel_auto = sum(a['monto'] for a in adel_pend)
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
                "monto_adelantos": float(monto_adel_auto),
                # Auto-selección de adelantos pendientes (el usuario puede desmarcar)
                "adelantos_ids": [a['id'] for a in adel_pend],
                "adelantos_pendientes": adel_pend,
            }
            calc = calcular_linea(det, ajustes_d, afp)
            det.update(calc)
            # Agregar medios de pago default
            det["medios_pago_default"] = medios_por_trabajador.get(td['id'], [])
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
    # Medios de pago por defecto de cada trabajador — para auto-poblar el modal de pago
    trabajador_ids = list({d['trabajador_id'] for d in dets})
    medios_por_trabajador = {}
    if trabajador_ids:
        medios_rows = await conn.fetch("""
            SELECT m.trabajador_id, m.cuenta_id, m.porcentaje, m.orden, c.nombre AS cuenta_nombre
              FROM finanzas2.fin_trabajador_medio_pago_default m
              LEFT JOIN finanzas2.cont_cuenta_financiera c ON m.cuenta_id = c.id
             WHERE m.trabajador_id = ANY($1::int[])
             ORDER BY m.trabajador_id, m.orden
        """, trabajador_ids)
        for row in medios_rows:
            tid = row['trabajador_id']
            medios_por_trabajador.setdefault(tid, []).append({
                "cuenta_id": row['cuenta_id'],
                "cuenta_nombre": row['cuenta_nombre'],
                "porcentaje": float(row['porcentaje']),
                "orden": row['orden'],
            })
    detalles_out = []
    for d in dets:
        dd = dict(d)
        dd['medios_pago_default'] = medios_por_trabajador.get(d['trabajador_id'], [])
        detalles_out.append(dd)
    return {
        **dict(cab),
        "detalles": detalles_out,
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
            fecha_pago = data.fecha_pago or date.today()
            periodo_str = f"{pl['anio']}-{pl['mes']:02d}-Q{pl['quincena']}"

            # Modo NUEVO: pagos por trabajador (recomendado)
            if data.pagos_por_trabajador:
                # Cargar detalles para validar
                dets = await conn.fetch("""
                    SELECT id, nombre, neto FROM finanzas2.fin_planilla_quincena_detalle
                     WHERE planilla_id = $1
                """, planilla_id)
                det_map = {d['id']: d for d in dets}

                # Validar cada trabajador: suma de medios = su neto
                suma_total = 0.0
                for pt in data.pagos_por_trabajador:
                    det = det_map.get(pt.detalle_id)
                    if not det:
                        raise HTTPException(400, f"Detalle {pt.detalle_id} no pertenece a la planilla")
                    suma_trab = sum(float(m.monto) for m in pt.medios)
                    neto_trab = float(det['neto'])
                    if abs(suma_trab - neto_trab) > 0.01:
                        raise HTTPException(400,
                            f"Trabajador {det['nombre']}: suma de medios ({suma_trab:.2f}) "
                            f"no coincide con su neto ({neto_trab:.2f})")
                    suma_total += suma_trab

                # Validar total
                if abs(suma_total - total_neto) > 0.01:
                    raise HTTPException(400, f"Total de pagos no coincide con el neto de la planilla")

                # Crear egresos y pagos — agrupados pero cada uno asociado al detalle
                for pt in data.pagos_por_trabajador:
                    det = det_map[pt.detalle_id]
                    for p in pt.medios:
                        cta = await conn.fetchrow(
                            "SELECT id, nombre FROM finanzas2.cont_cuenta_financiera WHERE id = $1 AND empresa_id = $2",
                            p.cuenta_id, empresa_id)
                        if not cta:
                            raise HTTPException(404, f"Cuenta {p.cuenta_id} no encontrada")

                        # Primero insertar el registro de pago para obtener el id (origen_id del movimiento)
                        pago_row = await conn.fetchrow("""
                            INSERT INTO finanzas2.fin_planilla_quincena_pago
                                (planilla_id, empresa_id, cuenta_id, detalle_id, monto, referencia, notas, movimiento_cuenta_id)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, NULL)
                            RETURNING id
                        """, planilla_id, empresa_id, p.cuenta_id, pt.detalle_id, p.monto, p.referencia, p.notas)

                        mov_id = await create_movimiento_tesoreria(
                            conn, empresa_id, fecha_pago, 'egreso', float(p.monto),
                            cuenta_financiera_id=p.cuenta_id,
                            referencia=p.referencia,
                            concepto=f"Planilla {periodo_str} · {det['nombre']}",
                            origen_tipo='planilla_quincena_pago',
                            origen_id=pago_row['id'],
                            notas=p.notas,
                        )
                        await conn.execute(
                            "UPDATE finanzas2.fin_planilla_quincena_pago SET movimiento_cuenta_id = $1 WHERE id = $2",
                            mov_id, pago_row['id'])

                        await conn.execute("""
                            UPDATE finanzas2.cont_cuenta_financiera
                               SET saldo_actual = COALESCE(saldo_actual, 0) - $1, updated_at = NOW()
                             WHERE id = $2
                        """, p.monto, p.cuenta_id)

            # Modo LEGACY: pagos consolidados (sin asociar a detalle)
            elif data.pagos:
                suma_pagos = sum(float(p.monto) for p in data.pagos)
                if abs(suma_pagos - total_neto) > 0.01:
                    raise HTTPException(400,
                        f"La suma de medios de pago ({suma_pagos:.2f}) no coincide con el total neto ({total_neto:.2f})")

                for p in data.pagos:
                    cta = await conn.fetchrow(
                        "SELECT id, nombre FROM finanzas2.cont_cuenta_financiera WHERE id = $1 AND empresa_id = $2",
                        p.cuenta_id, empresa_id)
                    if not cta:
                        raise HTTPException(404, f"Cuenta {p.cuenta_id} no encontrada")

                    pago_row = await conn.fetchrow("""
                        INSERT INTO finanzas2.fin_planilla_quincena_pago
                            (planilla_id, empresa_id, cuenta_id, monto, referencia, notas, movimiento_cuenta_id)
                        VALUES ($1, $2, $3, $4, $5, $6, NULL)
                        RETURNING id
                    """, planilla_id, empresa_id, p.cuenta_id, p.monto, p.referencia, p.notas)

                    mov_id = await create_movimiento_tesoreria(
                        conn, empresa_id, fecha_pago, 'egreso', float(p.monto),
                        cuenta_financiera_id=p.cuenta_id,
                        referencia=p.referencia,
                        concepto=f"Planilla {periodo_str}",
                        origen_tipo='planilla_quincena_pago',
                        origen_id=pago_row['id'],
                        notas=p.notas,
                    )
                    await conn.execute(
                        "UPDATE finanzas2.fin_planilla_quincena_pago SET movimiento_cuenta_id = $1 WHERE id = $2",
                        mov_id, pago_row['id'])

                    await conn.execute("""
                        UPDATE finanzas2.cont_cuenta_financiera
                           SET saldo_actual = COALESCE(saldo_actual, 0) - $1, updated_at = NOW()
                         WHERE id = $2
                    """, p.monto, p.cuenta_id)
            else:
                raise HTTPException(400, "Debe enviar 'pagos_por_trabajador' o 'pagos'")

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


# ───────── PAGAR TRABAJADOR INDIVIDUAL ─────────

@router.post("/planillas-quincena/{planilla_id}/detalles/{detalle_id}/pagar")
async def pagar_detalle(
    planilla_id: int,
    detalle_id: int,
    data: PagarDetalleIn,
    empresa_id: int = Depends(get_empresa_id),
    user=Depends(get_current_user),
):
    """Paga UN solo trabajador de la planilla.
    Si todos los detalles quedan pagados, cambia estado planilla → 'pagada'."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            pl = await conn.fetchrow(
                "SELECT * FROM finanzas2.fin_planilla_quincena WHERE id = $1 AND empresa_id = $2",
                planilla_id, empresa_id)
            if not pl:
                raise HTTPException(404, "Planilla no encontrada")
            if pl['estado'] not in ('aprobada', 'pagada'):
                raise HTTPException(400, f"Planilla debe estar aprobada (estado actual: {pl['estado']})")

            det = await conn.fetchrow("""
                SELECT * FROM finanzas2.fin_planilla_quincena_detalle
                 WHERE id = $1 AND planilla_id = $2 AND empresa_id = $3
            """, detalle_id, planilla_id, empresa_id)
            if not det:
                raise HTTPException(404, "Detalle no encontrado")
            if det['pagado_at'] is not None:
                raise HTTPException(400, f"{det['nombre']} ya está pagado. Anular pago primero si necesita corregir.")

            neto = float(det['neto'])
            suma = sum(float(m.monto) for m in data.medios)
            if abs(suma - neto) > 0.01:
                raise HTTPException(400,
                    f"Suma de medios ({suma:.2f}) no coincide con neto del trabajador ({neto:.2f})")

            fecha_pago = data.fecha_pago or date.today()
            periodo_str = f"{pl['anio']}-{pl['mes']:02d}-Q{pl['quincena']}"

            # Crear egresos por cada medio — se escribe en cont_movimiento_tesoreria
            # (fuente única para Tesorería, Pagos y Flujo de Caja)
            for m in data.medios:
                cta = await conn.fetchrow(
                    "SELECT id, nombre FROM finanzas2.cont_cuenta_financiera WHERE id = $1 AND empresa_id = $2",
                    m.cuenta_id, empresa_id)
                if not cta:
                    raise HTTPException(404, f"Cuenta {m.cuenta_id} no encontrada")

                # 1) Crear el registro de pago primero (para obtener id como origen del movimiento)
                pago_row = await conn.fetchrow("""
                    INSERT INTO finanzas2.fin_planilla_quincena_pago
                        (planilla_id, empresa_id, cuenta_id, detalle_id, monto, referencia, notas, movimiento_cuenta_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, NULL)
                    RETURNING id
                """, planilla_id, empresa_id, m.cuenta_id, detalle_id, m.monto, m.referencia, m.notas)

                # 2) Insertar el movimiento en la tabla única de tesorería
                mov_id = await create_movimiento_tesoreria(
                    conn, empresa_id, fecha_pago, 'egreso', float(m.monto),
                    cuenta_financiera_id=m.cuenta_id,
                    referencia=m.referencia,
                    concepto=f"Planilla {periodo_str} · {det['nombre']}",
                    origen_tipo='planilla_quincena_pago',
                    origen_id=pago_row['id'],
                    notas=m.notas,
                )

                # 3) Amarrar el mov_id al registro de pago
                await conn.execute(
                    "UPDATE finanzas2.fin_planilla_quincena_pago SET movimiento_cuenta_id = $1 WHERE id = $2",
                    mov_id, pago_row['id'])

                # 4) Descontar el saldo de la cuenta
                await conn.execute("""
                    UPDATE finanzas2.cont_cuenta_financiera
                       SET saldo_actual = COALESCE(saldo_actual, 0) - $1, updated_at = NOW()
                     WHERE id = $2
                """, m.monto, m.cuenta_id)

            # Marcar adelantos del trabajador como descontados
            await conn.execute("""
                UPDATE finanzas2.fin_adelanto_trabajador
                   SET descontado = TRUE, updated_at = NOW()
                 WHERE detalle_id = $1 AND empresa_id = $2
            """, detalle_id, empresa_id)

            # Marcar detalle como pagado
            await conn.execute("""
                UPDATE finanzas2.fin_planilla_quincena_detalle
                   SET pagado_at = NOW(), pagado_por = $1, updated_at = NOW()
                 WHERE id = $2
            """, user.get('username') if user else None, detalle_id)

            # Si TODOS los detalles están pagados, marcar planilla como pagada
            pendientes = await conn.fetchval("""
                SELECT COUNT(*) FROM finanzas2.fin_planilla_quincena_detalle
                 WHERE planilla_id = $1 AND pagado_at IS NULL
            """, planilla_id)
            if pendientes == 0 and pl['estado'] != 'pagada':
                await conn.execute("""
                    UPDATE finanzas2.fin_planilla_quincena
                       SET estado = 'pagada', fecha_pago = $1,
                           pagado_at = NOW(), pagado_por = $2, updated_at = NOW()
                     WHERE id = $3
                """, fecha_pago, user.get('username') if user else None, planilla_id)

            return await _get_planilla_full(conn, planilla_id, empresa_id)


# ───────── ANULAR PAGO INDIVIDUAL ─────────

@router.post("/planillas-quincena/{planilla_id}/detalles/{detalle_id}/anular-pago")
async def anular_pago_detalle(
    planilla_id: int,
    detalle_id: int,
    empresa_id: int = Depends(get_empresa_id),
    user=Depends(get_current_user),
):
    """Anula el pago de UN solo trabajador (revierte sus egresos)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            pl = await conn.fetchrow(
                "SELECT * FROM finanzas2.fin_planilla_quincena WHERE id = $1 AND empresa_id = $2",
                planilla_id, empresa_id)
            if not pl:
                raise HTTPException(404, "Planilla no encontrada")

            det = await conn.fetchrow("""
                SELECT * FROM finanzas2.fin_planilla_quincena_detalle
                 WHERE id = $1 AND planilla_id = $2
            """, detalle_id, planilla_id)
            if not det:
                raise HTTPException(404, "Detalle no encontrado")
            if det['pagado_at'] is None:
                raise HTTPException(400, f"{det['nombre']} no está pagado")

            # Revertir pagos del detalle: eliminar movimiento en tesorería + restaurar saldo
            pagos = await conn.fetch("""
                SELECT * FROM finanzas2.fin_planilla_quincena_pago
                 WHERE detalle_id = $1
            """, detalle_id)
            for p in pagos:
                # Eliminar el movimiento de tesorería vinculado
                await delete_movimientos_by_origen(
                    conn, empresa_id, 'planilla_quincena_pago', p['id'])
                # Restaurar saldo de la cuenta
                await conn.execute("""
                    UPDATE finanzas2.cont_cuenta_financiera
                       SET saldo_actual = COALESCE(saldo_actual, 0) + $1, updated_at = NOW()
                     WHERE id = $2
                """, p['monto'], p['cuenta_id'])

            # Borrar los pagos del detalle
            await conn.execute(
                "DELETE FROM finanzas2.fin_planilla_quincena_pago WHERE detalle_id = $1",
                detalle_id)

            # Desmarcar adelantos del detalle
            await conn.execute("""
                UPDATE finanzas2.fin_adelanto_trabajador
                   SET descontado = FALSE, updated_at = NOW()
                 WHERE detalle_id = $1 AND empresa_id = $2
            """, detalle_id, empresa_id)

            # Desmarcar detalle
            await conn.execute("""
                UPDATE finanzas2.fin_planilla_quincena_detalle
                   SET pagado_at = NULL, pagado_por = NULL, updated_at = NOW()
                 WHERE id = $1
            """, detalle_id)

            # Si la planilla estaba pagada, volver a aprobada
            if pl['estado'] == 'pagada':
                await conn.execute("""
                    UPDATE finanzas2.fin_planilla_quincena
                       SET estado = 'aprobada', fecha_pago = NULL,
                           anulado_at = NOW(), anulado_por = $1,
                           updated_at = NOW()
                     WHERE id = $2
                """, user.get('username') if user else None, planilla_id)

            return await _get_planilla_full(conn, planilla_id, empresa_id)


# ───────── ANULAR PAGO (TODA LA PLANILLA) ─────────

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

            # Revertir movimientos: eliminar de cont_movimiento_tesoreria + restaurar saldos
            pagos = await conn.fetch(
                "SELECT * FROM finanzas2.fin_planilla_quincena_pago WHERE planilla_id = $1",
                planilla_id)
            for p in pagos:
                await delete_movimientos_by_origen(
                    conn, empresa_id, 'planilla_quincena_pago', p['id'])
                await conn.execute("""
                    UPDATE finanzas2.cont_cuenta_financiera
                       SET saldo_actual = COALESCE(saldo_actual, 0) + $1, updated_at = NOW()
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
    """
    Elimina una planilla en CUALQUIER estado.
    Si está 'pagada', primero revierte los egresos (genera INGRESOS de reversión
    y restaura saldos) antes de eliminar.
    Siempre libera los adelantos vinculados.

    TODO (cuando exista sistema de roles): restringir solo a admin.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            pl = await conn.fetchrow(
                "SELECT * FROM finanzas2.fin_planilla_quincena WHERE id = $1 AND empresa_id = $2",
                planilla_id, empresa_id)
            if not pl:
                raise HTTPException(404, "Planilla no encontrada")

            periodo_str = f"{pl['anio']}-{pl['mes']:02d}-Q{pl['quincena']}"

            # Revertir egresos de CUALQUIER pago registrado (aunque la planilla no esté en 'pagada':
            # puede haber detalles pagados con planilla en 'aprobada' con pagos parciales).
            pagos = await conn.fetch(
                "SELECT * FROM finanzas2.fin_planilla_quincena_pago WHERE planilla_id = $1",
                planilla_id)
            for p in pagos:
                await delete_movimientos_by_origen(
                    conn, empresa_id, 'planilla_quincena_pago', p['id'])
                await conn.execute("""
                    UPDATE finanzas2.cont_cuenta_financiera
                       SET saldo_actual = COALESCE(saldo_actual, 0) + $1, updated_at = NOW()
                     WHERE id = $2
                """, p['monto'], p['cuenta_id'])

            # Liberar adelantos vinculados (volver a pendientes)
            await conn.execute("""
                UPDATE finanzas2.fin_adelanto_trabajador
                   SET planilla_id = NULL, detalle_id = NULL, descontado = FALSE, updated_at = NOW()
                 WHERE planilla_id = $1
            """, planilla_id)

            # Eliminar planilla (CASCADE borra detalles y pagos)
            await conn.execute(
                "DELETE FROM finanzas2.fin_planilla_quincena WHERE id = $1",
                planilla_id)

            return {
                "message": "Planilla eliminada",
                "estado_previo": pl['estado'],
                "se_revirtieron_egresos": len(pagos) > 0,
                "pagos_revertidos": len(pagos),
            }


# ═══════════════════════════════════════════════════════════════════════
#  PDF — Planilla consolidada imprimible
# ═══════════════════════════════════════════════════════════════════════

MESES_ES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
            'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']


def _monto_a_letras(monto: float) -> str:
    """Convierte S/ 1,250.76 → 'Mil doscientos cincuenta con 76/100 soles'."""
    try:
        from num2words import num2words
    except ImportError:
        return ""
    entero = int(monto)
    centavos = int(round((monto - entero) * 100))
    texto = num2words(entero, lang='es').capitalize()
    return f"{texto} con {centavos:02d}/100 soles"


@router.get("/planillas-quincena/{planilla_id}/pdf")
async def descargar_planilla_pdf(
    planilla_id: int,
    empresa_id: int = Depends(get_empresa_id),
):
    """Genera un PDF consolidado (apaisado) con todos los trabajadores,
    totales, resumen por cuenta de pago y líneas para firmas.
    Disponible en estado 'aprobada' y 'pagada'."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether,
    )
    from fastapi.responses import StreamingResponse

    pool = await get_pool()
    async with pool.acquire() as conn:
        data = await _get_planilla_full(conn, planilla_id, empresa_id)
        emp = await conn.fetchrow(
            "SELECT id, nombre, ruc, direccion, telefono, email FROM finanzas2.cont_empresa WHERE id = $1",
            empresa_id)

    if data['estado'] not in ('aprobada', 'pagada'):
        raise HTTPException(400,
            f"El PDF solo está disponible cuando la planilla está aprobada o pagada (estado actual: {data['estado']})")

    detalles = sorted(data['detalles'], key=lambda d: (d.get('nombre') or '').upper())
    pagos = data['pagos']
    mes = data['mes']
    anio = data['anio']
    quincena = data['quincena']
    periodo_label = f"Quincena {quincena} · {MESES_ES[mes-1]} {anio}"
    fechas_label = f"Del {data['fecha_inicio'].strftime('%d/%m/%Y')} al {data['fecha_fin'].strftime('%d/%m/%Y')}"

    # Totales
    def _f(v): return float(v or 0)
    total_bruto = sum(_f(d.get('subtotal_horas')) for d in detalles)
    total_asig = sum(_f(d.get('asig_familiar_monto')) for d in detalles)
    total_afp = sum(_f(d.get('afp_total')) for d in detalles)
    total_tardanzas = sum(_f(d.get('descuento_tardanzas')) for d in detalles)
    total_adelantos = sum(_f(d.get('monto_adelantos')) for d in detalles)
    total_neto = sum(_f(d.get('neto')) for d in detalles)

    # Resumen por cuenta
    cuentas_resumen: dict = {}
    for p in pagos:
        k = p.get('cuenta_nombre') or f"Cuenta #{p.get('cuenta_id')}"
        cuentas_resumen[k] = cuentas_resumen.get(k, 0) + _f(p.get('monto'))

    # Qué trabajadores ya están pagados vs pendientes (para mostrar en la tabla)
    pagos_por_det: dict = {}
    for p in pagos:
        det_id = p.get('detalle_id')
        if det_id:
            pagos_por_det.setdefault(det_id, []).append(p)

    # ─────────── Construir el PDF ───────────
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=12*mm, rightMargin=12*mm,
        topMargin=12*mm, bottomMargin=12*mm,
        title=f"Planilla {periodo_label}",
    )
    story = []
    styles = getSampleStyleSheet()
    H1 = ParagraphStyle('H1', parent=styles['Title'], fontSize=14,
                        textColor=colors.HexColor('#111827'), alignment=1, spaceAfter=2)
    Hsub = ParagraphStyle('Hsub', parent=styles['Normal'], fontSize=10,
                          textColor=colors.HexColor('#6b7280'), alignment=1, spaceAfter=6)
    EmpStyle = ParagraphStyle('Emp', parent=styles['Normal'], fontSize=10,
                              textColor=colors.HexColor('#111827'), alignment=0, leading=12)
    SmallGray = ParagraphStyle('SmG', parent=styles['Normal'], fontSize=8,
                               textColor=colors.HexColor('#6b7280'), leading=10)
    SectionTitle = ParagraphStyle('ST', parent=styles['Normal'], fontSize=10,
                                  textColor=colors.HexColor('#111827'),
                                  fontName='Helvetica-Bold', spaceBefore=6, spaceAfter=3)

    # Encabezado
    emp_nombre = (emp and emp['nombre']) or ""
    emp_ruc = (emp and emp['ruc']) or ""
    emp_dir = (emp and emp['direccion']) or ""
    emp_tel = (emp and emp['telefono']) or ""

    header_data = [
        [
            Paragraph(
                f"<b>{emp_nombre}</b><br/>"
                f"RUC: {emp_ruc}"
                + (f"<br/>{emp_dir}" if emp_dir else "")
                + (f"<br/>Tel: {emp_tel}" if emp_tel else ""),
                EmpStyle
            ),
            Paragraph("<b>PLANILLA DE REMUNERACIONES</b>", H1),
            Paragraph(
                f"<para align='right'><b>Estado:</b> {data['estado'].upper()}<br/>"
                f"Emitido: {date.today().strftime('%d/%m/%Y')}</para>",
                EmpStyle,
            ),
        ]
    ]
    header_tbl = Table(header_data, colWidths=[80*mm, 110*mm, 80*mm])
    header_tbl.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LINEBELOW', (0,0), (-1,-1), 0.8, colors.HexColor('#d1d5db')),
    ]))
    story.append(header_tbl)
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<para align='center'><b>{periodo_label}</b> · {fechas_label}</para>", Hsub))
    story.append(Spacer(1, 4))

    # Tabla principal
    def mfmt(v): return f"S/ {_f(v):,.2f}"
    def nfmt(v): return f"{_f(v):g}"

    # ─── Cuentas únicas usadas en pagos (para columnas dinámicas) ───
    # Preserva el orden de aparición de la primera vez que se ve cada cuenta.
    cuentas_orden: list = []
    cuentas_seen: set = set()
    for p in pagos:
        cn = p.get('cuenta_nombre') or '—'
        if cn not in cuentas_seen:
            cuentas_seen.add(cn)
            cuentas_orden.append(cn)

    # Header dinámico: #, Trabajador, Sueldo, Bruto, AFP, Tard, Adel, Neto, [cuentas...], Estado
    header_row = [
        "N°", "TRABAJADOR", "SUELDO MES", "BRUTO", "AFP",
        "TARD.", "ADEL.", "NETO",
    ] + [c.upper() for c in cuentas_orden] + ["ESTADO"]

    # Totales por cuenta (a calcular conforme se construyen las filas)
    totales_por_cuenta: dict = {c: 0.0 for c in cuentas_orden}

    rows_data = [header_row]
    for i, d in enumerate(detalles, start=1):
        pago_det = pagos_por_det.get(d['id'], [])
        # Sumar lo pagado por cuenta para este trabajador
        montos_por_cuenta = {c: 0.0 for c in cuentas_orden}
        for p in pago_det:
            cn = p.get('cuenta_nombre') or '—'
            if cn in montos_por_cuenta:
                montos_por_cuenta[cn] += _f(p.get('monto'))
        for c, m in montos_por_cuenta.items():
            totales_por_cuenta[c] += m

        estado_celda = "PAGADO" if d.get('pagado_at') else "PENDIENTE"
        cuenta_cells = [
            (mfmt(montos_por_cuenta[c]) if montos_por_cuenta[c] > 0 else "—")
            for c in cuentas_orden
        ]
        rows_data.append([
            str(i),
            (d.get('nombre') or '').upper(),
            mfmt(d.get('sueldo_basico_total')),
            mfmt(d.get('subtotal_horas')),
            mfmt(d.get('afp_total')),
            mfmt(d.get('descuento_tardanzas')),
            mfmt(d.get('monto_adelantos')),
            mfmt(d.get('neto')),
        ] + cuenta_cells + [estado_celda])

    # Fila de totales
    cuenta_totals_cells = [mfmt(totales_por_cuenta[c]) for c in cuentas_orden]
    rows_data.append([
        "", "TOTALES", "", mfmt(total_bruto),
        mfmt(total_afp), mfmt(total_tardanzas), mfmt(total_adelantos),
        mfmt(total_neto),
    ] + cuenta_totals_cells + [""])

    # ─── Anchos de columnas ───
    # A4 landscape, márgenes 12mm c/lado → ancho útil = 273mm
    # Fijos: 8+50+22+24+22+16+16+24+18 = 200mm
    # Restante = 73mm, dividido entre cuentas
    n_cuentas = max(1, len(cuentas_orden))
    ancho_cuentas = 73 / n_cuentas if n_cuentas > 0 else 0
    col_widths = [
        8*mm, 50*mm, 22*mm,     # # Trabajador Sueldo
        24*mm, 22*mm,           # Bruto AFP
        16*mm, 16*mm, 24*mm,    # Tard Adel Neto
    ] + [ancho_cuentas*mm] * n_cuentas + [
        18*mm,                  # Estado
    ]

    # Índices de columnas (estructura final):
    # 0:#  1:Trab  2:Sueldo  3:Bruto  4:AFP  5:Tard  6:Adel  7:Neto
    # 8..(8+n_cuentas-1): cuentas dinámicas
    # 8+n_cuentas: Estado
    idx_estado = 8 + n_cuentas

    tbl = Table(rows_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1f2937')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 7.5),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,0), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,0), 5),
        ('TOPPADDING', (0,0), (-1,0), 5),
        # Cuerpo
        ('FONTSIZE', (0,1), (-1,-2), 7.5),
        ('VALIGN', (0,1), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,1), (0,-1), 'CENTER'),                      # #
        ('ALIGN', (2,1), (idx_estado-1,-1), 'RIGHT'),            # montos a la derecha
        ('ALIGN', (idx_estado,1), (idx_estado,-1), 'CENTER'),    # Estado
        ('FONTNAME', (3,1), (3,-2), 'Helvetica-Bold'),           # Bruto negrita
        ('FONTNAME', (7,1), (7,-2), 'Helvetica-Bold'),           # Neto negrita
        ('TEXTCOLOR', (3,1), (3,-2), colors.HexColor('#065f46')),    # Bruto verde
        ('TEXTCOLOR', (4,1), (6,-2), colors.HexColor('#b91c1c')),    # AFP/Tard/Adel rojo
        ('TEXTCOLOR', (7,1), (7,-2), colors.HexColor('#065f46')),    # Neto verde
        # Cuentas: en azul como referencia visual
        ('TEXTCOLOR', (8,1), (idx_estado-1,-2), colors.HexColor('#1d4ed8')),
        ('FONTNAME', (8,1), (idx_estado-1,-2), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#d1d5db')),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, colors.HexColor('#f9fafb')]),
        # Totales
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#e5e7eb')),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,-1), (-1,-1), 8),
        ('TEXTCOLOR', (3,-1), (3,-1), colors.HexColor('#065f46')),   # Bruto total verde
        ('TEXTCOLOR', (7,-1), (7,-1), colors.HexColor('#065f46')),   # Neto total verde
        ('TEXTCOLOR', (4,-1), (6,-1), colors.HexColor('#b91c1c')),   # AFP/Tard/Adel total rojo
        ('TEXTCOLOR', (8,-1), (idx_estado-1,-1), colors.HexColor('#1d4ed8')),  # cuentas total azul
    ]))
    story.append(tbl)
    story.append(Spacer(1, 8))

    # Resumen pagado por cuenta + total en letras
    resumen_items = []
    resumen_items.append(Paragraph("<b>Resumen de pagos por cuenta</b>", SectionTitle))
    if cuentas_resumen:
        res_rows = [["Cuenta", "Monto"]]
        total_pagado = 0.0
        for nombre, monto in cuentas_resumen.items():
            res_rows.append([nombre, mfmt(monto)])
            total_pagado += monto
        res_rows.append(["TOTAL PAGADO", mfmt(total_pagado)])
        res_tbl = Table(res_rows, colWidths=[80*mm, 40*mm])
        res_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1f2937')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('ALIGN', (1,0), (1,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#d1d5db')),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#e5e7eb')),
            ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (1,-1), (1,-1), colors.HexColor('#065f46')),
        ]))
        resumen_items.append(res_tbl)
        resumen_items.append(Spacer(1, 4))
        if total_pagado > 0:
            resumen_items.append(Paragraph(
                f"<i>Son: {_monto_a_letras(total_pagado)}</i>",
                SmallGray))
    else:
        resumen_items.append(Paragraph(
            "<i>Sin pagos registrados aún. La planilla está aprobada pero no pagada.</i>",
            SmallGray))

    # Bloque firmas (a la derecha del resumen)
    firma_cell = Paragraph(
        "<para align='center'>"
        "_________________________<br/><b>Elaborado por</b><br/><font size=7 color='#6b7280'>Nombre · DNI · Firma</font>"
        "</para>",
        EmpStyle
    )
    firma_cell2 = Paragraph(
        "<para align='center'>"
        "_________________________<br/><b>Revisado por</b><br/><font size=7 color='#6b7280'>Nombre · DNI · Firma</font>"
        "</para>",
        EmpStyle
    )
    firma_cell3 = Paragraph(
        "<para align='center'>"
        "_________________________<br/><b>Aprobado Gerencia</b><br/><font size=7 color='#6b7280'>Nombre · DNI · Firma</font>"
        "</para>",
        EmpStyle
    )
    firmas_tbl = Table([[firma_cell, firma_cell2, firma_cell3]],
                      colWidths=[50*mm, 50*mm, 50*mm], rowHeights=[22*mm])
    firmas_tbl.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
    ]))

    bottom_tbl = Table(
        [[resumen_items, firmas_tbl]],
        colWidths=[130*mm, 150*mm],
    )
    bottom_tbl.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(KeepTogether(bottom_tbl))

    doc.build(story)
    buf.seek(0)
    filename = f"planilla_{anio}-{mes:02d}-Q{quincena}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"'
        },
    )
