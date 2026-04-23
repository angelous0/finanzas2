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
    horas_quincenales: int = Field(gt=0, default=120)
    asignacion_familiar: bool = False
    porcentaje_planilla: float = Field(default=100.00)
    afp_id: Optional[int] = None
    fecha_ingreso: Optional[date] = None
    activo: Optional[bool] = True
    notas: Optional[str] = None


def _validar(data: TrabajadorIn):
    if data.area.upper() not in AREAS_VALIDAS:
        raise HTTPException(400, f"Área inválida. Use: {', '.join(AREAS_VALIDAS)}")
    if data.porcentaje_planilla not in (50.00, 100.00):
        raise HTTPException(400, "porcentaje_planilla debe ser 50 o 100")


def _calcular_derivados(row: dict, ajustes: dict, afp: Optional[dict]) -> dict:
    """Genera los 6 cálculos que se muestran debajo del form."""
    sbt = float(row.get('sueldo_basico_total') or 0)
    sueldo_planilla = float(row.get('sueldo_planilla') or 0)
    sueldo_minimo = float(ajustes.get('sueldo_minimo') or 0)
    asig_fam_pct = float(ajustes.get('asignacion_familiar_pct') or 0) / 100.0

    hora_simple = sbt / 30 / 8 if sbt > 0 else 0
    hora_extra_25 = hora_simple * 1.25
    hora_extra_35 = hora_simple * 1.35
    asig_fam_monto = sueldo_minimo * asig_fam_pct if row.get('asignacion_familiar') else 0

    base_afp = sueldo_planilla + asig_fam_monto
    aporte_afp = 0.0
    prima_seguros = 0.0
    comision_flujo = 0.0
    if afp:
        aporte_pct = float(afp.get('aporte_obligatorio_pct') or 0) / 100.0
        prima_pct = float(afp.get('prima_seguro_pct') or 0) / 100.0
        flujo_pct = float(afp.get('comision_flujo_pct') or 0) / 100.0
        aporte_afp = base_afp * aporte_pct
        prima_seguros = base_afp * prima_pct
        comision_flujo = base_afp * flujo_pct

    return {
        "hora_simple":          round(hora_simple, 4),
        "hora_extra_25":        round(hora_extra_25, 4),
        "hora_extra_35":        round(hora_extra_35, 4),
        "asignacion_familiar_monto": round(asig_fam_monto, 2),
        "base_afp":             round(base_afp, 2),
        "aporte_afp":           round(aporte_afp, 2),
        "prima_seguros":        round(prima_seguros, 2),
        "comision_flujo":       round(comision_flujo, 2),
        # metadatos para la UI
        "meta": {
            "sueldo_minimo":    sueldo_minimo,
            "asig_fam_pct":     float(ajustes.get('asignacion_familiar_pct') or 0),
            "afp_nombre":       afp.get('nombre') if afp else None,
            "afp_aporte_pct":   float(afp.get('aporte_obligatorio_pct') or 0) if afp else 0,
            "afp_prima_pct":    float(afp.get('prima_seguro_pct') or 0) if afp else 0,
            "afp_flujo_pct":    float(afp.get('comision_flujo_pct') or 0) if afp else 0,
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
    """Calcula el cuadro de derivados para un trabajador sin guardar en DB.
    Útil para mostrar el cuadro en tiempo real mientras el usuario llena el form."""
    _validar(data)
    sbt = (data.sueldo_planilla or 0) + (data.sueldo_basico or 0)
    mock_row = {
        'sueldo_basico_total': sbt,
        'sueldo_planilla':     data.sueldo_planilla,
        'asignacion_familiar': data.asignacion_familiar,
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
                asignacion_familiar, porcentaje_planilla, afp_id,
                fecha_ingreso, activo, notas
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            RETURNING *
        """, empresa_id, data.dni, data.nombre, data.area.upper(),
             data.unidad_interna_id,
             data.sueldo_planilla, data.sueldo_basico, data.horas_quincenales,
             data.asignacion_familiar, data.porcentaje_planilla, data.afp_id,
             data.fecha_ingreso,
             data.activo if data.activo is not None else True,
             data.notas)
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
                horas_quincenales = $7, asignacion_familiar = $8,
                porcentaje_planilla = $9, afp_id = $10,
                fecha_ingreso = $11, activo = $12, notas = $13,
                updated_at = NOW()
            WHERE id = $14 AND empresa_id = $15
            RETURNING *
        """, data.dni, data.nombre, data.area.upper(),
             data.unidad_interna_id,
             data.sueldo_planilla, data.sueldo_basico, data.horas_quincenales,
             data.asignacion_familiar, data.porcentaje_planilla, data.afp_id,
             data.fecha_ingreso,
             data.activo if data.activo is not None else True,
             data.notas,
             trabajador_id, empresa_id)
        if not row:
            raise HTTPException(404, "Trabajador no encontrado")
        return await _enrich(conn, row, empresa_id)


# ───── DELETE ─────

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
