"""
Router de Trabajadores (Planilla v3 — reset desde cero).

Campos principales:
- Identificación: dni, nombre, área, unidad interna, empresa
- Sueldo: sueldo_planilla + sueldo_basico → sueldo_basico_total (GENERATED)
- Configuración: horas_quincenales (editable), asignacion_familiar, porcentaje_planilla (100|50), afp_id

Endpoint extra /calculos devuelve los 6 cálculos derivados:
- hora_simple, hora_extra_25, hora_extra_35
- asignacion_familiar_monto (0.10 × sueldo_minimo si activa)
- aporte_afp, prima_seguros (sobre sueldo_planilla + asignación)
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
from decimal import Decimal
from database import get_pool
from dependencies import get_empresa_id

router = APIRouter(tags=["Trabajadores"])

AREAS_VALIDAS = {'ADMINISTRACION', 'PRODUCCION', 'VENTAS', 'MARKETING'}


class TrabajadorIn(BaseModel):
    dni: Optional[str] = None
    nombre: str
    area: str
    unidad_interna_id: Optional[int] = None
    sueldo_planilla: float = Field(ge=0, default=0)
    sueldo_basico: float = Field(ge=0, default=0)
    horas_quincenales: int = Field(ge=0, default=120)
    # Horas extras "esperadas" cada quincena → se pre-cargan al armar la planilla
    horas_extras_25_default: float = Field(ge=0, default=0)
    horas_extras_35_default: float = Field(ge=0, default=0)
    asignacion_familiar: bool = False
    porcentaje_planilla: float = Field(default=100.00)
    afp_id: Optional[int] = None
    fecha_ingreso: Optional[date] = None
    activo: Optional[bool] = True
    notas: Optional[str] = None
    # Planilla v4: destajo
    tipo_pago: Optional[str] = 'planilla'       # planilla | destajo | mixto
    prod_persona_id: Optional[str] = None        # link a prod_personas_produccion.id


TIPOS_PAGO_VALIDOS = {'planilla', 'destajo', 'mixto'}


def _validar(data: TrabajadorIn):
    if data.area.upper() not in AREAS_VALIDAS:
        raise HTTPException(400, f"Área inválida. Use: {', '.join(AREAS_VALIDAS)}")
    if data.porcentaje_planilla not in (50.00, 100.00):
        raise HTTPException(400, "porcentaje_planilla debe ser 50 o 100")
    if data.tipo_pago and data.tipo_pago not in TIPOS_PAGO_VALIDOS:
        raise HTTPException(400, f"tipo_pago inválido. Use: {', '.join(TIPOS_PAGO_VALIDOS)}")


def _calcular_derivados(row: dict, ajustes: dict, afp: Optional[dict]) -> dict:
    """Genera los 6 cálculos que se muestran debajo del form."""
    sbt = float(row.get('sueldo_basico_total') or 0)
    sueldo_planilla = float(row.get('sueldo_planilla') or 0)
    sueldo_minimo = float(ajustes.get('sueldo_minimo') or 0)
    asig_fam_pct = float(ajustes.get('asignacion_familiar_pct') or 0) / 100.0

    # Fórmula: sueldo_basico_total / (horas_quincenales × 2)
    # Ej: 1220.34 / (120 × 2) = 1220.34 / 240 = 5.085
    horas_quincenales = float(row.get('horas_quincenales') or 120)
    horas_mensuales = horas_quincenales * 2
    hora_simple = (sbt / horas_mensuales) if (sbt > 0 and horas_mensuales > 0) else 0
    hora_extra_25 = hora_simple * 1.25
    hora_extra_35 = hora_simple * 1.35
    asig_fam_monto = sueldo_minimo * asig_fam_pct if row.get('asignacion_familiar') else 0

    base_afp = sueldo_planilla + asig_fam_monto
    aporte_afp = 0.0
    prima_seguros = 0.0
    if afp:
        aporte_pct = float(afp.get('aporte_obligatorio_pct') or 0) / 100.0
        prima_pct = float(afp.get('prima_seguro_pct') or 0) / 100.0
        aporte_afp = base_afp * aporte_pct
        prima_seguros = base_afp * prima_pct

    # Cálculos SIN redondeo intermedio — el round solo se aplica al devolver
    # al cliente para visualización (2 decimales). Los valores reales tienen
    # precisión completa de float hasta este punto.
    return {
        "hora_simple":          round(hora_simple, 2),
        "hora_extra_25":        round(hora_extra_25, 2),
        "hora_extra_35":        round(hora_extra_35, 2),
        "asignacion_familiar_monto": round(asig_fam_monto, 2),
        "base_afp":             round(base_afp, 2),
        "aporte_afp":           round(aporte_afp, 2),
        "prima_seguros":        round(prima_seguros, 2),
        # metadatos para la UI
        "meta": {
            "sueldo_minimo":    sueldo_minimo,
            "asig_fam_pct":     float(ajustes.get('asignacion_familiar_pct') or 0),
            "afp_nombre":       afp.get('nombre') if afp else None,
            "afp_aporte_pct":   float(afp.get('aporte_obligatorio_pct') or 0) if afp else 0,
            "afp_prima_pct":    float(afp.get('prima_seguro_pct') or 0) if afp else 0,
        }
    }


async def _enrich(conn, row: dict, empresa_id: int) -> dict:
    """Agrega unidad_nombre, afp_nombre y el bloque 'calculos' a un trabajador."""
    d = dict(row)
    if d.get('unidad_interna_id'):
        d['unidad_interna_nombre'] = await conn.fetchval(
            "SELECT nombre FROM finanzas2.fin_unidad_interna WHERE id = $1",
            d['unidad_interna_id'])
    else:
        d['unidad_interna_nombre'] = None
    afp_row = None
    if d.get('afp_id'):
        afp_row = await conn.fetchrow(
            "SELECT * FROM finanzas2.fin_afp WHERE id = $1", d['afp_id'])
        d['afp_nombre'] = afp_row['nombre'] if afp_row else None
    else:
        d['afp_nombre'] = None
    ajustes = await conn.fetchrow(
        "SELECT * FROM finanzas2.fin_ajustes_planilla WHERE empresa_id = $1",
        empresa_id)
    ajustes_dict = dict(ajustes) if ajustes else {
        'sueldo_minimo': 1130, 'horas_quincena_default': 120, 'asignacion_familiar_pct': 10
    }
    d['calculos'] = _calcular_derivados(d, ajustes_dict, dict(afp_row) if afp_row else None)
    return d


# ───── LIST ─────

@router.get("/trabajadores")
async def list_trabajadores(
    activo: Optional[bool] = None,
    area: Optional[str] = None,
    unidad_interna_id: Optional[int] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        conds = ["t.empresa_id = $1"]
        params = [empresa_id]
        idx = 2
        if activo is not None:
            conds.append(f"t.activo = ${idx}")
            params.append(activo); idx += 1
        if area:
            conds.append(f"t.area = ${idx}")
            params.append(area.upper()); idx += 1
        if unidad_interna_id:
            conds.append(f"t.unidad_interna_id = ${idx}")
            params.append(unidad_interna_id); idx += 1

        rows = await conn.fetch(f"""
            SELECT t.*,
                   ui.nombre AS unidad_interna_nombre,
                   a.nombre  AS afp_nombre,
                   a.codigo  AS afp_codigo
              FROM finanzas2.fin_trabajador t
              LEFT JOIN finanzas2.fin_unidad_interna ui ON t.unidad_interna_id = ui.id
              LEFT JOIN finanzas2.fin_afp a              ON t.afp_id = a.id
             WHERE {' AND '.join(conds)}
             ORDER BY t.activo DESC, t.nombre
        """, *params)
        return [dict(r) for r in rows]


# ───── DETAIL (con cálculos) ─────

@router.get("/trabajadores/{trabajador_id}")
async def get_trabajador(trabajador_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM finanzas2.fin_trabajador WHERE id = $1 AND empresa_id = $2",
            trabajador_id, empresa_id)
        if not row:
            raise HTTPException(404, "Trabajador no encontrado")
        return await _enrich(conn, row, empresa_id)


# ───── PREVIEW DE CÁLCULOS (sin guardar) ─────

@router.post("/trabajadores/calculos-preview")
async def preview_calculos(data: TrabajadorIn, empresa_id: int = Depends(get_empresa_id)):
    """Calcula el cuadro de derivados para un trabajador sin guardar en DB."""
    _validar(data)
    sbt = (data.sueldo_planilla or 0) + (data.sueldo_basico or 0)
    mock_row = {
        'sueldo_basico_total': sbt,
        'sueldo_planilla':     data.sueldo_planilla,
        'asignacion_familiar': data.asignacion_familiar,
        'horas_quincenales':   data.horas_quincenales,
    }
    pool = await get_pool()
    async with pool.acquire() as conn:
        ajustes = await conn.fetchrow(
            "SELECT * FROM finanzas2.fin_ajustes_planilla WHERE empresa_id = $1",
            empresa_id)
        ajustes_dict = dict(ajustes) if ajustes else {
            'sueldo_minimo': 1130, 'horas_quincena_default': 120, 'asignacion_familiar_pct': 10
        }
        afp_row = None
        if data.afp_id:
            afp_row = await conn.fetchrow(
                "SELECT * FROM finanzas2.fin_afp WHERE id = $1 AND empresa_id = $2",
                data.afp_id, empresa_id)
    return _calcular_derivados(mock_row, ajustes_dict, dict(afp_row) if afp_row else None)


# ─── CALCULADORA INVERSA ─────────────────────────────────────────
# Dado un sueldo objetivo mensual + horas extras esperadas, calcula
# cuál debería ser el sueldo básico total para que cuadre.

class CalcInversaIn(BaseModel):
    sueldo_objetivo: float = Field(gt=0)
    horas_quincenales: int = Field(default=120, gt=0)
    horas_extras_25: float = Field(default=0, ge=0)
    horas_extras_35: float = Field(default=0, ge=0)


@router.post("/trabajadores/calc-inversa")
async def calc_inversa(data: CalcInversaIn):
    """
    Resuelve: dado el sueldo total que el trabajador debe ganar mensualmente
    y las horas extras quincenales típicas, ¿cuál es el sueldo básico total?

    Modelo:
        sueldo_total = básico + (HE25 × tarifa25 × 2) + (HE35 × tarifa35 × 2)
        tarifa25 = básico / horas_mensuales × 1.25
        tarifa35 = básico / horas_mensuales × 1.35

        Despejando:
        básico = sueldo_total / (1 + 2×1.25×HE25/horas_mensuales + 2×1.35×HE35/horas_mensuales)
    """
    horas_mensuales = data.horas_quincenales * 2
    factor = (
        1
        + (2 * 1.25 * data.horas_extras_25 / horas_mensuales)
        + (2 * 1.35 * data.horas_extras_35 / horas_mensuales)
    )
    basico = data.sueldo_objetivo / factor
    hora_simple = basico / horas_mensuales
    aporte_he25 = data.horas_extras_25 * hora_simple * 1.25 * 2
    aporte_he35 = data.horas_extras_35 * hora_simple * 1.35 * 2
    return {
        "sueldo_basico_total": round(basico, 2),
        "hora_simple": round(hora_simple, 4),
        "hora_extra_25": round(hora_simple * 1.25, 4),
        "hora_extra_35": round(hora_simple * 1.35, 4),
        "aporte_he25_mensual": round(aporte_he25, 2),
        "aporte_he35_mensual": round(aporte_he35, 2),
        "sueldo_total_calculado": round(basico + aporte_he25 + aporte_he35, 2),
        "horas_mensuales": horas_mensuales,
    }


# ───── CREATE ─────

@router.post("/trabajadores")
async def create_trabajador(data: TrabajadorIn, empresa_id: int = Depends(get_empresa_id)):
    _validar(data)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO finanzas2.fin_trabajador (
                empresa_id, dni, nombre, area, unidad_interna_id,
                sueldo_planilla, sueldo_basico, horas_quincenales,
                horas_extras_25_default, horas_extras_35_default,
                asignacion_familiar, porcentaje_planilla, afp_id,
                fecha_ingreso, activo, notas,
                tipo_pago, prod_persona_id
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
            RETURNING *
        """, empresa_id, data.dni, data.nombre, data.area.upper(),
             data.unidad_interna_id,
             data.sueldo_planilla, data.sueldo_basico, data.horas_quincenales,
             data.horas_extras_25_default, data.horas_extras_35_default,
             data.asignacion_familiar, data.porcentaje_planilla, data.afp_id,
             data.fecha_ingreso,
             data.activo if data.activo is not None else True,
             data.notas,
             data.tipo_pago or 'planilla',
             data.prod_persona_id)
        return await _enrich(conn, row, empresa_id)


# ───── UPDATE ─────

@router.put("/trabajadores/{trabajador_id}")
async def update_trabajador(
    trabajador_id: int,
    data: TrabajadorIn,
    empresa_id: int = Depends(get_empresa_id),
):
    _validar(data)
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            UPDATE finanzas2.fin_trabajador SET
                dni = $1, nombre = $2, area = $3,
                unidad_interna_id = $4,
                sueldo_planilla = $5, sueldo_basico = $6,
                horas_quincenales = $7,
                horas_extras_25_default = $8, horas_extras_35_default = $9,
                asignacion_familiar = $10,
                porcentaje_planilla = $11, afp_id = $12,
                fecha_ingreso = $13, activo = $14, notas = $15,
                tipo_pago = $16, prod_persona_id = $17,
                updated_at = NOW()
            WHERE id = $18 AND empresa_id = $19
            RETURNING *
        """, data.dni, data.nombre, data.area.upper(),
             data.unidad_interna_id,
             data.sueldo_planilla, data.sueldo_basico, data.horas_quincenales,
             data.horas_extras_25_default, data.horas_extras_35_default,
             data.asignacion_familiar, data.porcentaje_planilla, data.afp_id,
             data.fecha_ingreso,
             data.activo if data.activo is not None else True,
             data.notas,
             data.tipo_pago or 'planilla',
             data.prod_persona_id,
             trabajador_id, empresa_id)
        if not row:
            raise HTTPException(404, "Trabajador no encontrado")
        return await _enrich(conn, row, empresa_id)


# ───── DELETE ─────

# ───── MEDIOS DE PAGO POR DEFECTO ─────

class MedioPagoDefaultIn(BaseModel):
    cuenta_id: int
    porcentaje: float = Field(gt=0, le=100)
    orden: Optional[int] = 0
    notas: Optional[str] = None


@router.get("/trabajadores/{trabajador_id}/medios-pago")
async def list_medios_pago(trabajador_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT m.*, c.nombre AS cuenta_nombre, c.tipo AS cuenta_tipo
              FROM finanzas2.fin_trabajador_medio_pago_default m
              JOIN finanzas2.cont_cuenta_financiera c ON m.cuenta_id = c.id
             WHERE m.trabajador_id = $1 AND m.empresa_id = $2
             ORDER BY m.orden, m.id
        """, trabajador_id, empresa_id)
        return [dict(r) for r in rows]


@router.put("/trabajadores/{trabajador_id}/medios-pago")
async def set_medios_pago(
    trabajador_id: int,
    medios: list[MedioPagoDefaultIn],
    empresa_id: int = Depends(get_empresa_id),
):
    """Reemplaza completamente la lista de medios del trabajador.
    Valida que la suma de porcentajes sea 100 (o 0 si se limpia todo)."""
    total_pct = sum(m.porcentaje for m in medios)
    if medios and abs(total_pct - 100) > 0.01:
        raise HTTPException(400, f"La suma de porcentajes debe ser 100% (actual: {total_pct}%)")

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Validar trabajador
            t = await conn.fetchval(
                "SELECT id FROM finanzas2.fin_trabajador WHERE id = $1 AND empresa_id = $2",
                trabajador_id, empresa_id)
            if not t:
                raise HTTPException(404, "Trabajador no encontrado")
            # Reemplazar
            await conn.execute(
                "DELETE FROM finanzas2.fin_trabajador_medio_pago_default WHERE trabajador_id = $1",
                trabajador_id)
            for idx, m in enumerate(medios):
                await conn.execute("""
                    INSERT INTO finanzas2.fin_trabajador_medio_pago_default
                        (empresa_id, trabajador_id, cuenta_id, porcentaje, orden, notas)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, empresa_id, trabajador_id, m.cuenta_id, m.porcentaje, idx, m.notas)
        # Re-leer
        rows = await conn.fetch("""
            SELECT m.*, c.nombre AS cuenta_nombre
              FROM finanzas2.fin_trabajador_medio_pago_default m
              JOIN finanzas2.cont_cuenta_financiera c ON m.cuenta_id = c.id
             WHERE m.trabajador_id = $1
             ORDER BY m.orden
        """, trabajador_id)
        return [dict(r) for r in rows]


# ───── DELETE TRABAJADOR ─────

@router.delete("/trabajadores/{trabajador_id}")
async def delete_trabajador(trabajador_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        res = await conn.execute(
            "DELETE FROM finanzas2.fin_trabajador WHERE id = $1 AND empresa_id = $2",
            trabajador_id, empresa_id)
        if res.endswith(" 0"):
            # soft delete (nunca llega aquí porque DELETE devuelve "DELETE 0" si no encuentra)
            raise HTTPException(404, "Trabajador no encontrado")
        return {"message": "Trabajador eliminado"}


# ═══════════════════════════════════════════════════════════════════
#  TARIFAS DESTAJO (por trabajador × servicio)
# ═══════════════════════════════════════════════════════════════════

class TarifaDestajoIn(BaseModel):
    servicio_nombre: str
    tarifa: float = Field(ge=0)


@router.get("/trabajadores/{trabajador_id}/tarifas-destajo")
async def list_tarifas_destajo(trabajador_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Validar trabajador
        t = await conn.fetchval(
            "SELECT id FROM finanzas2.fin_trabajador WHERE id = $1 AND empresa_id = $2",
            trabajador_id, empresa_id)
        if not t:
            raise HTTPException(404, "Trabajador no encontrado")
        rows = await conn.fetch("""
            SELECT id, trabajador_id, servicio_nombre, tarifa
              FROM finanzas2.fin_trabajador_tarifa_destajo
             WHERE trabajador_id = $1
             ORDER BY servicio_nombre
        """, trabajador_id)
        return [dict(r) for r in rows]


@router.put("/trabajadores/{trabajador_id}/tarifas-destajo")
async def set_tarifas_destajo(
    trabajador_id: int,
    tarifas: list[TarifaDestajoIn],
    empresa_id: int = Depends(get_empresa_id),
):
    """Reemplaza completamente la lista de tarifas destajo del trabajador."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            t = await conn.fetchval(
                "SELECT id FROM finanzas2.fin_trabajador WHERE id = $1 AND empresa_id = $2",
                trabajador_id, empresa_id)
            if not t:
                raise HTTPException(404, "Trabajador no encontrado")
            # Normalizar — quitar vacíos y deduplicar por servicio_nombre (última gana)
            limpio = {}
            for x in tarifas:
                nombre = (x.servicio_nombre or '').strip()
                if not nombre:
                    continue
                limpio[nombre] = float(x.tarifa)
            await conn.execute(
                "DELETE FROM finanzas2.fin_trabajador_tarifa_destajo WHERE trabajador_id = $1",
                trabajador_id)
            for servicio_nombre, tarifa in limpio.items():
                await conn.execute("""
                    INSERT INTO finanzas2.fin_trabajador_tarifa_destajo
                        (trabajador_id, servicio_nombre, tarifa)
                    VALUES ($1, $2, $3)
                """, trabajador_id, servicio_nombre, tarifa)
        rows = await conn.fetch("""
            SELECT id, trabajador_id, servicio_nombre, tarifa
              FROM finanzas2.fin_trabajador_tarifa_destajo
             WHERE trabajador_id = $1
             ORDER BY servicio_nombre
        """, trabajador_id)
        return [dict(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════
#  HELPERS para linkear con Producción (catálogos)
# ═══════════════════════════════════════════════════════════════════

@router.get("/personas-produccion-disponibles")
async def list_personas_produccion_disponibles(
    solo_sin_trabajador: bool = False,
    tipo_persona: Optional[str] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    """Lista personas de Producción para linkear con un trabajador.
    Si solo_sin_trabajador=True, filtra las que aún no están asociadas."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # $1 = empresa_id (siempre), $2 = tipo_persona (si se filtra)
        params: list = [empresa_id]
        where_extra = ""
        if tipo_persona:
            params.append(tipo_persona)
            where_extra = f" WHERE p.tipo_persona = ${len(params)}"
        personas = await conn.fetch(f"""
            SELECT p.id, p.nombre, p.tipo_persona, p.unidad_interna_id,
                   ui.nombre AS unidad_interna_nombre,
                   (SELECT t.id FROM finanzas2.fin_trabajador t
                     WHERE t.prod_persona_id = p.id AND t.empresa_id = $1 LIMIT 1) AS trabajador_id,
                   (SELECT t.nombre FROM finanzas2.fin_trabajador t
                     WHERE t.prod_persona_id = p.id AND t.empresa_id = $1 LIMIT 1) AS trabajador_nombre
              FROM produccion.prod_personas_produccion p
              LEFT JOIN finanzas2.fin_unidad_interna ui ON p.unidad_interna_id = ui.id
              {where_extra}
             ORDER BY p.nombre
        """, *params)
        items = [dict(r) for r in personas]
        if solo_sin_trabajador:
            items = [p for p in items if not p.get('trabajador_id')]
        return items
