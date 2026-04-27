"""
Planilla Destajo — paga a trabajadores destajistas por prendas trabajadas.

Flujo (espejo de planilla quincenal):
1. POST /planillas-destajo/calcular
     → dado un rango fecha_desde/fecha_hasta, busca movimientos de producción
       asociados a trabajadores tipo_pago IN ('destajo','mixto') y calcula el
       bruto usando la tarifa destajo configurada por (trabajador, servicio).
     → excluye movimientos que ya estén en otra planilla_destajo.
2. POST /planillas-destajo         → crea en borrador
3. PUT  /planillas-destajo/{id}    → edita (solo borrador)
4. POST /planillas-destajo/{id}/aprobar
5. POST /planillas-destajo/{id}/detalles/{detalle_id}/pagar
6. POST /planillas-destajo/{id}/detalles/{detalle_id}/anular-pago
7. DELETE /planillas-destajo/{id}  (revierte pagos si los hay)

Reglas:
- Los destajistas NO tienen AFP ni asignación familiar (se ignoran).
- La tarifa destajo es la del trabajador × servicio; si el movimiento no
  tiene tarifa configurada, aparece como "sin_tarifa" y NO se incluye en
  el bruto.
- Los adelantos pendientes del trabajador se sugieren pero se pueden
  vincular/desvincular por detalle (igual que la quincenal).
- Un movimiento solo puede estar en UNA planilla destajo (UNIQUE DB).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date
import io
from database import get_pool
from dependencies import get_empresa_id
from services.treasury_service import create_movimiento_tesoreria, delete_movimientos_by_origen


# Placeholder hasta que exista auth
async def get_current_user():
    return {"username": "sistema"}


router = APIRouter(tags=["Planilla Destajo"])


# ─────────────────────────────────────────────────────────────────
#  MODELOS
# ─────────────────────────────────────────────────────────────────

class CalcularDestajoIn(BaseModel):
    fecha_desde: date
    fecha_hasta: date


class DetalleDestajoIn(BaseModel):
    trabajador_id: int
    movimiento_ids: List[str] = Field(default_factory=list)   # ids que se incluyen
    # Override de tarifa destajo por movimiento. Si el movimiento_id aparece aquí,
    # se usa esta tarifa en vez de la configurada en la ficha del trabajador.
    # Útil cuando hay modelos especiales que pagan diferente.
    tarifa_overrides: dict[str, float] = Field(default_factory=dict)
    adelantos_ids: List[int] = Field(default_factory=list)
    notas: Optional[str] = None


class PlanillaDestajoCreateIn(BaseModel):
    fecha_desde: date
    fecha_hasta: date
    detalles: List[DetalleDestajoIn]
    notas: Optional[str] = None


class PlanillaDestajoUpdateIn(BaseModel):
    detalles: List[DetalleDestajoIn]
    notas: Optional[str] = None


class MedioPagoIn(BaseModel):
    cuenta_id: int
    monto: float = Field(gt=0)
    referencia: Optional[str] = None
    notas: Optional[str] = None


class PagarDetalleDestajoIn(BaseModel):
    medios: List[MedioPagoIn]
    fecha_pago: Optional[date] = None


# ─────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────

async def _movimientos_candidatos(conn, empresa_id: int, fecha_desde: date, fecha_hasta: date,
                                  trabajadores: list[dict]) -> list[dict]:
    """
    Trae los movimientos de producción para los trabajadores dados que aún
    estén pendientes de pago (no vinculados a otra planilla destajo).

    Filtros:
      - fecha_inicio <= fecha_hasta (solo cota superior)
      - persona_id en los prod_persona_id de los destajistas

    NO filtra por fecha_desde: incluye también movimientos de períodos
    anteriores que quedaron sin pagar. Cada movimiento viene con flag
    `dentro_rango` = (fecha_desde <= fecha_inicio <= fecha_hasta) para
    que el frontend pre-seleccione solo los del período actual.
    """
    persona_ids = [t['prod_persona_id'] for t in trabajadores if t.get('prod_persona_id')]
    if not persona_ids:
        return []

    rows = await conn.fetch("""
        SELECT mp.id                     AS movimiento_id,
               mp.fecha_inicio           AS fecha,
               mp.cantidad_recibida,
               mp.cantidad_enviada,
               mp.tarifa_aplicada        AS tarifa_mercado,
               mp.costo_calculado        AS costo_mercado,
               p.id                      AS prod_persona_id,
               p.nombre                  AS persona_nombre,
               s.nombre                  AS servicio_nombre,
               r.id                      AS registro_id,
               r.n_corte,
               COALESCE(m.nombre, r.modelo_manual->>'nombre_modelo') AS modelo_nombre,
               (SELECT pld.id FROM finanzas2.fin_planilla_destajo_movimiento pld
                 WHERE pld.movimiento_id = mp.id LIMIT 1) AS ya_vinculado_id
          FROM produccion.prod_movimientos_produccion mp
          INNER JOIN produccion.prod_registros r ON r.id = mp.registro_id
          LEFT JOIN produccion.prod_personas_produccion p ON mp.persona_id = p.id
          LEFT JOIN produccion.prod_servicios_produccion s ON mp.servicio_id = s.id
          LEFT JOIN produccion.prod_modelos m ON r.modelo_id = m.id
         WHERE r.empresa_id = $1
           AND p.id = ANY($2::text[])
           AND mp.fecha_inicio <= $3
         ORDER BY mp.fecha_inicio DESC NULLS LAST, mp.id DESC
    """, empresa_id, persona_ids, fecha_hasta)

    # Tarifas destajo por trabajador
    trab_ids = [t['id'] for t in trabajadores]
    tarifas_rows = await conn.fetch("""
        SELECT trabajador_id, servicio_nombre, tarifa
          FROM finanzas2.fin_trabajador_tarifa_destajo
         WHERE trabajador_id = ANY($1::int[])
    """, trab_ids)
    # Map (trabajador_id, servicio_nombre_lower) → tarifa
    tarifa_map: dict = {}
    for r in tarifas_rows:
        tarifa_map[(r['trabajador_id'], (r['servicio_nombre'] or '').strip().lower())] = float(r['tarifa'])

    # Map prod_persona_id → trabajador
    prod_to_trab: dict = {t['prod_persona_id']: t for t in trabajadores if t.get('prod_persona_id')}

    items = []
    for r in rows:
        persona_id = r['prod_persona_id']
        trab = prod_to_trab.get(persona_id)
        if not trab:
            continue
        cantidad = int(r['cantidad_recibida'] or r['cantidad_enviada'] or 0)
        servicio = (r['servicio_nombre'] or '').strip()
        tarifa_destajo = tarifa_map.get((trab['id'], servicio.lower()))
        importe = round(cantidad * tarifa_destajo, 2) if tarifa_destajo is not None else None
        fecha_mov = r['fecha']
        dentro_rango = bool(fecha_mov) and (fecha_desde <= fecha_mov <= fecha_hasta)
        items.append({
            "movimiento_id": str(r['movimiento_id']),
            "trabajador_id": trab['id'],
            "trabajador_nombre": trab['nombre'],
            "fecha": fecha_mov.isoformat() if fecha_mov else None,
            "registro_id": str(r['registro_id']) if r['registro_id'] else None,
            "n_corte": r['n_corte'],
            "modelo_nombre": r['modelo_nombre'],
            "servicio_nombre": servicio,
            "persona_nombre": r['persona_nombre'],
            "cantidad": cantidad,
            "tarifa_destajo": tarifa_destajo,
            "tarifa_mercado": float(r['tarifa_mercado'] or 0),
            "importe": importe,
            "ya_vinculado": r['ya_vinculado_id'] is not None,
            "sin_tarifa": tarifa_destajo is None,
            "dentro_rango": dentro_rango,
        })
    return items


async def _cargar_trabajadores_destajo(conn, empresa_id: int, solo_con_prod_persona: bool = True) -> list[dict]:
    where = "t.empresa_id = $1 AND t.activo = TRUE AND t.tipo_pago IN ('destajo','mixto')"
    if solo_con_prod_persona:
        where += " AND t.prod_persona_id IS NOT NULL"
    rows = await conn.fetch(f"""
        SELECT t.id, t.nombre, t.dni, t.area, t.unidad_interna_id,
               t.prod_persona_id, t.tipo_pago,
               ui.nombre AS unidad_interna_nombre
          FROM finanzas2.fin_trabajador t
          LEFT JOIN finanzas2.fin_unidad_interna ui ON ui.id = t.unidad_interna_id
         WHERE {where}
    """, empresa_id)
    return [dict(r) for r in rows]


async def _adelantos_pendientes(conn, empresa_id: int, trabajador_id: int) -> list[dict]:
    rows = await conn.fetch("""
        SELECT a.id, a.fecha, a.monto, a.motivo, a.cuenta_pago_id,
               c.nombre AS cuenta_nombre
          FROM finanzas2.fin_adelanto_trabajador a
          LEFT JOIN finanzas2.cont_cuenta_financiera c ON c.id = a.cuenta_pago_id
         WHERE a.empresa_id = $1
           AND a.trabajador_id = $2
           AND a.descontado = FALSE
           AND a.planilla_id IS NULL
           AND a.planilla_destajo_id IS NULL
         ORDER BY a.fecha ASC
    """, empresa_id, trabajador_id)
    return [dict(r) for r in rows]


async def _get_planilla_full(conn, planilla_id: int, empresa_id: int) -> dict:
    cab = await conn.fetchrow(
        "SELECT * FROM finanzas2.fin_planilla_destajo WHERE id = $1 AND empresa_id = $2",
        planilla_id, empresa_id)
    if not cab:
        raise HTTPException(404, "Planilla destajo no encontrada")

    dets = await conn.fetch("""
        SELECT * FROM finanzas2.fin_planilla_destajo_detalle
         WHERE planilla_id = $1 ORDER BY nombre
    """, planilla_id)

    movs = await conn.fetch("""
        SELECT * FROM finanzas2.fin_planilla_destajo_movimiento
         WHERE planilla_id = $1 ORDER BY fecha_inicio ASC NULLS LAST, id ASC
    """, planilla_id) if False else await conn.fetch("""
        SELECT m.*
          FROM finanzas2.fin_planilla_destajo_movimiento m
         WHERE m.planilla_id = $1
         ORDER BY m.id ASC
    """, planilla_id)

    pagos = await conn.fetch("""
        SELECT p.id, p.planilla_destajo_id, p.detalle_id, p.cuenta_id, p.monto,
               p.referencia, p.notas, p.movimiento_cuenta_id,
               c.nombre AS cuenta_nombre
          FROM finanzas2.fin_planilla_destajo_pago p
          LEFT JOIN finanzas2.cont_cuenta_financiera c ON p.cuenta_id = c.id
         WHERE p.planilla_destajo_id = $1
         ORDER BY p.id ASC
    """, planilla_id) if await _table_exists(conn, 'fin_planilla_destajo_pago') else []

    adelantos = await conn.fetch("""
        SELECT * FROM finanzas2.fin_adelanto_trabajador
         WHERE planilla_destajo_id = $1
    """, planilla_id)

    # Medios de pago default de cada trabajador (para auto-poblar modal)
    trab_ids = list({d['trabajador_id'] for d in dets})
    medios_por_trab: dict = {}
    if trab_ids:
        mrows = await conn.fetch("""
            SELECT m.trabajador_id, m.cuenta_id, m.porcentaje, m.orden,
                   c.nombre AS cuenta_nombre
              FROM finanzas2.fin_trabajador_medio_pago_default m
              LEFT JOIN finanzas2.cont_cuenta_financiera c ON m.cuenta_id = c.id
             WHERE m.trabajador_id = ANY($1::int[])
             ORDER BY m.trabajador_id, m.orden
        """, trab_ids)
        for row in mrows:
            medios_por_trab.setdefault(row['trabajador_id'], []).append({
                "cuenta_id": row['cuenta_id'],
                "cuenta_nombre": row['cuenta_nombre'],
                "porcentaje": float(row['porcentaje']),
                "orden": row['orden'],
            })

    detalles_out = []
    movs_por_det: dict = {}
    for m in movs:
        movs_por_det.setdefault(m['detalle_id'], []).append(dict(m))
    for d in dets:
        dd = dict(d)
        dd['medios_pago_default'] = medios_por_trab.get(d['trabajador_id'], [])
        dd['movimientos'] = movs_por_det.get(d['id'], [])
        detalles_out.append(dd)

    return {
        **dict(cab),
        "detalles": detalles_out,
        "pagos": [dict(p) for p in pagos],
        "adelantos_vinculados": [dict(a) for a in adelantos],
    }


async def _table_exists(conn, name: str) -> bool:
    return await conn.fetchval("""
        SELECT EXISTS (SELECT 1 FROM information_schema.tables
                        WHERE table_schema='finanzas2' AND table_name=$1)
    """, name)


# ─────────────────────────────────────────────────────────────────
#  CALCULAR PREVIEW
# ─────────────────────────────────────────────────────────────────

@router.post("/planillas-destajo/calcular")
async def calcular_preview(
    data: CalcularDestajoIn,
    empresa_id: int = Depends(get_empresa_id),
):
    """Preview: agrupa movimientos por trabajador destajista en el rango."""
    if data.fecha_desde > data.fecha_hasta:
        raise HTTPException(400, "fecha_desde no puede ser mayor a fecha_hasta")

    pool = await get_pool()
    async with pool.acquire() as conn:
        # 1) Trabajadores destajistas con prod_persona vinculada
        trabajadores = await _cargar_trabajadores_destajo(conn, empresa_id, solo_con_prod_persona=True)
        if not trabajadores:
            return {
                "fecha_desde": str(data.fecha_desde),
                "fecha_hasta": str(data.fecha_hasta),
                "trabajadores": [],
                "warnings": ["No hay trabajadores destajistas con persona de producción vinculada. "
                             "Configura tipo_pago='destajo' y vincula a una persona de Producción en la ficha."]
            }

        # 2) Movimientos candidatos
        items = await _movimientos_candidatos(
            conn, empresa_id, data.fecha_desde, data.fecha_hasta, trabajadores)

        # 3) Agrupar por trabajador + calcular totales iniciales.
        # Los totales mostrados al usuario solo cuentan los movs DENTRO del rango
        # (los anteriores entran como "pendientes" no pre-seleccionados).
        trab_map: dict = {}
        warnings_out: list[dict] = []
        for t in trabajadores:
            trab_map[t['id']] = {
                "trabajador_id": t['id'],
                "nombre": t['nombre'],
                "dni": t.get('dni'),
                "area": t.get('area'),
                "unidad_interna_id": t.get('unidad_interna_id'),
                "unidad_interna_nombre": t.get('unidad_interna_nombre'),
                "prod_persona_id": t['prod_persona_id'],
                "tipo_pago": t['tipo_pago'],
                "num_movimientos": 0,          # del rango actual
                "num_pendientes_anteriores": 0, # de períodos previos aún sin pagar
                "prendas": 0,
                "monto_bruto": 0.0,
                "movimientos": [],              # incluye dentro + fuera de rango (todos pendientes)
                "movimientos_excluidos": [],    # ya_vinculado o sin_tarifa (no se muestran como seleccionables)
            }
        for it in items:
            bucket = trab_map.get(it['trabajador_id'])
            if not bucket: continue
            if it['ya_vinculado']:
                bucket['movimientos_excluidos'].append({**it, "motivo_excluido": "ya_vinculado"})
                continue
            if it['sin_tarifa']:
                bucket['movimientos_excluidos'].append({**it, "motivo_excluido": "sin_tarifa"})
                warnings_out.append({
                    "trabajador_id": it['trabajador_id'],
                    "trabajador_nombre": it['trabajador_nombre'],
                    "tipo": "sin_tarifa",
                    "mensaje": f"Sin tarifa destajo para el servicio '{it['servicio_nombre']}'. "
                               f"Configurala en la ficha del trabajador.",
                })
                continue
            bucket['movimientos'].append(it)
            if it['dentro_rango']:
                bucket['num_movimientos'] += 1
                bucket['prendas'] += it['cantidad']
                bucket['monto_bruto'] += it['importe'] or 0
            else:
                bucket['num_pendientes_anteriores'] += 1

        # 4) Adelantos pendientes por trabajador
        for t in trabajadores:
            pendientes = await _adelantos_pendientes(conn, empresa_id, t['id'])
            trab_map[t['id']]['adelantos_pendientes'] = [
                {
                    "id": a['id'],
                    "fecha": a['fecha'].isoformat() if a['fecha'] else None,
                    "monto": float(a['monto']),
                    "motivo": a.get('motivo'),
                    "cuenta_nombre": a.get('cuenta_nombre'),
                } for a in pendientes
            ]

        # 5) Incluir trabajadores que tengan AL MENOS un movimiento
        # (sea del rango actual o de períodos previos no pagados)
        result_list = [
            {**v, "monto_bruto": round(v['monto_bruto'], 2)}
            for v in trab_map.values()
            if (v['num_movimientos'] + v['num_pendientes_anteriores']) > 0
        ]
        # Deduplicar warnings
        seen = set()
        unique_warns = []
        for w in warnings_out:
            key = (w['trabajador_id'], w['mensaje'])
            if key not in seen:
                seen.add(key)
                unique_warns.append(w)

        return {
            "fecha_desde": str(data.fecha_desde),
            "fecha_hasta": str(data.fecha_hasta),
            "trabajadores": result_list,
            "warnings": unique_warns,
        }


# ─────────────────────────────────────────────────────────────────
#  CREATE (borrador)
# ─────────────────────────────────────────────────────────────────

async def _persistir_detalles(conn, planilla_id: int, empresa_id: int,
                              detalles_in: list[DetalleDestajoIn],
                              fecha_desde: date, fecha_hasta: date):
    """Inserta detalles + movimientos vinculados. Requiere planilla existente (borrador)."""
    trabajadores = await _cargar_trabajadores_destajo(conn, empresa_id, solo_con_prod_persona=True)
    trab_map = {t['id']: t for t in trabajadores}
    items = await _movimientos_candidatos(conn, empresa_id, fecha_desde, fecha_hasta, trabajadores)
    # Map movimiento_id → item (más rápido)
    mov_map = {it['movimiento_id']: it for it in items}

    total_bruto = 0.0
    total_adelantos = 0.0
    total_prendas = 0
    total_movs = 0
    num_trab = 0

    for d_in in detalles_in:
        t = trab_map.get(d_in.trabajador_id)
        if not t: continue
        # Filtrar movimientos pedidos. Un movimiento es válido si:
        #  - existe en los candidatos,
        #  - no está ya vinculado a otra planilla,
        #  - pertenece a este trabajador,
        #  - TIENE tarifa (ya sea del default de ficha O un override explícito del usuario)
        movs_validos = []
        for mid in d_in.movimiento_ids:
            mv = mov_map.get(mid)
            if not mv: continue
            if mv['ya_vinculado']: continue
            if mv['trabajador_id'] != d_in.trabajador_id: continue
            override = d_in.tarifa_overrides.get(mid)
            if override is None and mv['sin_tarifa']:
                continue
            # Componer una copia con la tarifa final + importe recalculado
            tarifa_final = float(override) if override is not None else mv['tarifa_destajo']
            importe_final = round((mv['cantidad'] or 0) * tarifa_final, 2)
            movs_validos.append({
                **mv,
                'tarifa_destajo': tarifa_final,
                'importe': importe_final,
                'tarifa_overrideada': override is not None,
            })
        if not movs_validos: continue

        bruto = sum(m['importe'] or 0 for m in movs_validos)
        prendas = sum(m['cantidad'] for m in movs_validos)

        # Adelantos válidos del trabajador
        monto_adel = 0.0
        if d_in.adelantos_ids:
            ad_rows = await conn.fetch("""
                SELECT id, monto FROM finanzas2.fin_adelanto_trabajador
                 WHERE id = ANY($1::int[])
                   AND trabajador_id = $2 AND empresa_id = $3
                   AND descontado = FALSE
                   AND planilla_id IS NULL
                   AND planilla_destajo_id IS NULL
            """, d_in.adelantos_ids, d_in.trabajador_id, empresa_id)
            monto_adel = float(sum(float(r['monto']) for r in ad_rows))

        det_row = await conn.fetchrow("""
            INSERT INTO finanzas2.fin_planilla_destajo_detalle
                (planilla_id, empresa_id, trabajador_id, nombre, dni,
                 unidad_interna_id, unidad_interna_nombre,
                 num_movimientos, prendas,
                 monto_bruto, monto_adelantos, notas)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            RETURNING id
        """, planilla_id, empresa_id, t['id'], t['nombre'], t.get('dni'),
             t.get('unidad_interna_id'), t.get('unidad_interna_nombre'),
             len(movs_validos), prendas,
             round(bruto, 2), round(monto_adel, 2), d_in.notas)
        detalle_id = det_row['id']

        # Insertar movimientos
        for mv in movs_validos:
            await conn.execute("""
                INSERT INTO finanzas2.fin_planilla_destajo_movimiento
                    (planilla_id, detalle_id, movimiento_id, servicio_nombre,
                     registro_id, registro_n_corte, modelo_nombre,
                     cantidad, tarifa_destajo, importe)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            """, planilla_id, detalle_id, mv['movimiento_id'], mv['servicio_nombre'],
                 mv['registro_id'], mv['n_corte'], mv['modelo_nombre'],
                 mv['cantidad'], mv['tarifa_destajo'], mv['importe'])

        # Vincular adelantos
        if d_in.adelantos_ids:
            await conn.execute("""
                UPDATE finanzas2.fin_adelanto_trabajador
                   SET planilla_destajo_id = $1,
                       detalle_destajo_id = $2,
                       updated_at = NOW()
                 WHERE id = ANY($3::int[])
                   AND trabajador_id = $4
                   AND descontado = FALSE
                   AND planilla_id IS NULL
                   AND planilla_destajo_id IS NULL
            """, planilla_id, detalle_id, d_in.adelantos_ids, d_in.trabajador_id)

        total_bruto += bruto
        total_adelantos += monto_adel
        total_movs += len(movs_validos)
        total_prendas += prendas
        num_trab += 1

    # Actualizar totales de la planilla
    await conn.execute("""
        UPDATE finanzas2.fin_planilla_destajo
           SET total_bruto = $1::numeric,
               total_adelantos = $2::numeric,
               total_neto = ($1::numeric - $2::numeric),
               num_trabajadores = $3::integer,
               num_movimientos = $4::integer,
               prendas = $5::integer,
               updated_at = NOW()
         WHERE id = $6::integer
    """, round(total_bruto, 2), round(total_adelantos, 2),
         num_trab, total_movs, total_prendas, planilla_id)


@router.post("/planillas-destajo")
async def create_planilla_destajo(
    data: PlanillaDestajoCreateIn,
    empresa_id: int = Depends(get_empresa_id),
):
    if data.fecha_desde > data.fecha_hasta:
        raise HTTPException(400, "fecha_desde > fecha_hasta")
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("""
                INSERT INTO finanzas2.fin_planilla_destajo
                    (empresa_id, fecha_desde, fecha_hasta, estado, notas)
                VALUES ($1, $2, $3, 'borrador', $4)
                RETURNING id
            """, empresa_id, data.fecha_desde, data.fecha_hasta, data.notas)
            pid = row['id']
            await _persistir_detalles(conn, pid, empresa_id,
                                      data.detalles, data.fecha_desde, data.fecha_hasta)
            return await _get_planilla_full(conn, pid, empresa_id)


# ─────────────────────────────────────────────────────────────────
#  LIST + DETAIL
# ─────────────────────────────────────────────────────────────────

@router.get("/planillas-destajo")
async def list_planillas(
    estado: Optional[str] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        conds = ["empresa_id = $1"]
        params: list = [empresa_id]
        if estado:
            conds.append(f"estado = ${len(params)+1}")
            params.append(estado)
        rows = await conn.fetch(f"""
            SELECT p.*
              FROM finanzas2.fin_planilla_destajo p
             WHERE {' AND '.join(conds)}
             ORDER BY p.fecha_desde DESC, p.id DESC
        """, *params)
        return [dict(r) for r in rows]


@router.get("/planillas-destajo/{planilla_id}")
async def get_planilla(planilla_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await _get_planilla_full(conn, planilla_id, empresa_id)


# ─────────────────────────────────────────────────────────────────
#  UPDATE (solo borrador)
# ─────────────────────────────────────────────────────────────────

@router.put("/planillas-destajo/{planilla_id}")
async def update_planilla(
    planilla_id: int,
    data: PlanillaDestajoUpdateIn,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            pl = await conn.fetchrow(
                "SELECT * FROM finanzas2.fin_planilla_destajo WHERE id = $1 AND empresa_id = $2",
                planilla_id, empresa_id)
            if not pl:
                raise HTTPException(404, "Planilla destajo no encontrada")
            if pl['estado'] != 'borrador':
                raise HTTPException(400, "Solo se puede editar planilla en borrador")

            # Desvincular adelantos viejos
            await conn.execute("""
                UPDATE finanzas2.fin_adelanto_trabajador
                   SET planilla_destajo_id = NULL, detalle_destajo_id = NULL, updated_at = NOW()
                 WHERE planilla_destajo_id = $1
            """, planilla_id)
            # Borrar movimientos + detalles
            await conn.execute(
                "DELETE FROM finanzas2.fin_planilla_destajo_movimiento WHERE planilla_id = $1",
                planilla_id)
            await conn.execute(
                "DELETE FROM finanzas2.fin_planilla_destajo_detalle WHERE planilla_id = $1",
                planilla_id)
            # Actualizar notas
            await conn.execute(
                "UPDATE finanzas2.fin_planilla_destajo SET notas = $1, updated_at = NOW() WHERE id = $2",
                data.notas, planilla_id)
            # Re-persistir
            await _persistir_detalles(conn, planilla_id, empresa_id,
                                      data.detalles, pl['fecha_desde'], pl['fecha_hasta'])
            return await _get_planilla_full(conn, planilla_id, empresa_id)


# ─────────────────────────────────────────────────────────────────
#  APROBAR
# ─────────────────────────────────────────────────────────────────

@router.post("/planillas-destajo/{planilla_id}/aprobar")
async def aprobar_planilla(
    planilla_id: int,
    empresa_id: int = Depends(get_empresa_id),
    user=Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            pl = await conn.fetchrow(
                "SELECT * FROM finanzas2.fin_planilla_destajo WHERE id = $1 AND empresa_id = $2",
                planilla_id, empresa_id)
            if not pl:
                raise HTTPException(404, "Planilla no encontrada")
            if pl['estado'] != 'borrador':
                raise HTTPException(400, f"Solo se aprueba desde borrador (estado actual: {pl['estado']})")
            if (pl['num_trabajadores'] or 0) == 0:
                raise HTTPException(400, "La planilla no tiene trabajadores")
            await conn.execute("""
                UPDATE finanzas2.fin_planilla_destajo
                   SET estado = 'aprobada',
                       aprobado_at = NOW(),
                       aprobado_por = $1,
                       updated_at = NOW()
                 WHERE id = $2
            """, user.get('username') if user else None, planilla_id)
            return await _get_planilla_full(conn, planilla_id, empresa_id)


# ─────────────────────────────────────────────────────────────────
#  PAGAR TRABAJADOR INDIVIDUAL
# ─────────────────────────────────────────────────────────────────

@router.post("/planillas-destajo/{planilla_id}/detalles/{detalle_id}/pagar")
async def pagar_detalle(
    planilla_id: int,
    detalle_id: int,
    data: PagarDetalleDestajoIn,
    empresa_id: int = Depends(get_empresa_id),
    user=Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            pl = await conn.fetchrow(
                "SELECT * FROM finanzas2.fin_planilla_destajo WHERE id = $1 AND empresa_id = $2",
                planilla_id, empresa_id)
            if not pl:
                raise HTTPException(404, "Planilla no encontrada")
            if pl['estado'] not in ('aprobada', 'pagada'):
                raise HTTPException(400, f"Planilla debe estar aprobada (estado actual: {pl['estado']})")

            det = await conn.fetchrow("""
                SELECT * FROM finanzas2.fin_planilla_destajo_detalle
                 WHERE id = $1 AND planilla_id = $2 AND empresa_id = $3
            """, detalle_id, planilla_id, empresa_id)
            if not det:
                raise HTTPException(404, "Detalle no encontrado")
            if det['pagado_at'] is not None:
                raise HTTPException(400,
                    f"{det['nombre']} ya está pagado. Anular pago primero si necesita corregir.")

            neto = float(det['neto'])
            suma = sum(float(m.monto) for m in data.medios)
            if abs(suma - neto) > 0.01:
                raise HTTPException(400,
                    f"Suma de medios ({suma:.2f}) no coincide con neto del trabajador ({neto:.2f})")

            fecha_pago = data.fecha_pago or date.today()
            periodo_str = f"{pl['fecha_desde']} al {pl['fecha_hasta']}"

            # Asegurarnos de que existe la tabla de pagos
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS finanzas2.fin_planilla_destajo_pago (
                    id                     SERIAL PRIMARY KEY,
                    planilla_destajo_id    INTEGER NOT NULL
                        REFERENCES finanzas2.fin_planilla_destajo(id) ON DELETE CASCADE,
                    empresa_id             INTEGER NOT NULL,
                    cuenta_id              INTEGER NOT NULL,
                    detalle_id             INTEGER NOT NULL
                        REFERENCES finanzas2.fin_planilla_destajo_detalle(id) ON DELETE CASCADE,
                    monto                  NUMERIC(12,2) NOT NULL,
                    referencia             VARCHAR(200),
                    notas                  TEXT,
                    movimiento_cuenta_id   INTEGER,
                    created_at             TIMESTAMP DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_pld_pago_det
                       ON finanzas2.fin_planilla_destajo_pago(detalle_id);
            """)

            for m in data.medios:
                cta = await conn.fetchrow(
                    "SELECT id FROM finanzas2.cont_cuenta_financiera WHERE id = $1 AND empresa_id = $2",
                    m.cuenta_id, empresa_id)
                if not cta:
                    raise HTTPException(404, f"Cuenta {m.cuenta_id} no encontrada")

                # 1. Crear registro de pago
                pago_row = await conn.fetchrow("""
                    INSERT INTO finanzas2.fin_planilla_destajo_pago
                        (planilla_destajo_id, empresa_id, cuenta_id, detalle_id, monto, referencia, notas, movimiento_cuenta_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, NULL)
                    RETURNING id
                """, planilla_id, empresa_id, m.cuenta_id, detalle_id, m.monto, m.referencia, m.notas)

                # 2. Egreso en tesorería
                mov_id = await create_movimiento_tesoreria(
                    conn, empresa_id, fecha_pago, 'egreso', float(m.monto),
                    cuenta_financiera_id=m.cuenta_id,
                    referencia=m.referencia,
                    concepto=f"Destajo {periodo_str} · {det['nombre']}",
                    origen_tipo='planilla_destajo_pago',
                    origen_id=pago_row['id'],
                    notas=m.notas,
                )
                await conn.execute(
                    "UPDATE finanzas2.fin_planilla_destajo_pago SET movimiento_cuenta_id = $1 WHERE id = $2",
                    mov_id, pago_row['id'])

                # 3. Restar saldo cuenta
                await conn.execute("""
                    UPDATE finanzas2.cont_cuenta_financiera
                       SET saldo_actual = COALESCE(saldo_actual, 0) - $1, updated_at = NOW()
                     WHERE id = $2
                """, m.monto, m.cuenta_id)

            # 4. Marcar adelantos del detalle como descontados
            await conn.execute("""
                UPDATE finanzas2.fin_adelanto_trabajador
                   SET descontado = TRUE, updated_at = NOW()
                 WHERE detalle_destajo_id = $1 AND empresa_id = $2
            """, detalle_id, empresa_id)

            # 5. Marcar detalle como pagado
            await conn.execute("""
                UPDATE finanzas2.fin_planilla_destajo_detalle
                   SET pagado_at = NOW(), pagado_por = $1, updated_at = NOW()
                 WHERE id = $2
            """, user.get('username') if user else None, detalle_id)

            # 6. Si todos los detalles están pagados → planilla a 'pagada'
            pendientes = await conn.fetchval("""
                SELECT COUNT(*) FROM finanzas2.fin_planilla_destajo_detalle
                 WHERE planilla_id = $1 AND pagado_at IS NULL
            """, planilla_id)
            if pendientes == 0 and pl['estado'] != 'pagada':
                await conn.execute("""
                    UPDATE finanzas2.fin_planilla_destajo
                       SET estado = 'pagada', fecha_pago = $1,
                           pagado_at = NOW(), pagado_por = $2, updated_at = NOW()
                     WHERE id = $3
                """, fecha_pago, user.get('username') if user else None, planilla_id)

            return await _get_planilla_full(conn, planilla_id, empresa_id)


# ─────────────────────────────────────────────────────────────────
#  ANULAR PAGO INDIVIDUAL
# ─────────────────────────────────────────────────────────────────

@router.post("/planillas-destajo/{planilla_id}/detalles/{detalle_id}/anular-pago")
async def anular_pago_detalle(
    planilla_id: int,
    detalle_id: int,
    empresa_id: int = Depends(get_empresa_id),
    user=Depends(get_current_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            pl = await conn.fetchrow(
                "SELECT * FROM finanzas2.fin_planilla_destajo WHERE id = $1 AND empresa_id = $2",
                planilla_id, empresa_id)
            if not pl:
                raise HTTPException(404, "Planilla no encontrada")

            det = await conn.fetchrow("""
                SELECT * FROM finanzas2.fin_planilla_destajo_detalle
                 WHERE id = $1 AND planilla_id = $2
            """, detalle_id, planilla_id)
            if not det:
                raise HTTPException(404, "Detalle no encontrado")
            if det['pagado_at'] is None:
                raise HTTPException(400, f"{det['nombre']} no está pagado")

            # Revertir pagos
            if await _table_exists(conn, 'fin_planilla_destajo_pago'):
                pagos = await conn.fetch("""
                    SELECT * FROM finanzas2.fin_planilla_destajo_pago WHERE detalle_id = $1
                """, detalle_id)
                for p in pagos:
                    await delete_movimientos_by_origen(
                        conn, empresa_id, 'planilla_destajo_pago', p['id'])
                    await conn.execute("""
                        UPDATE finanzas2.cont_cuenta_financiera
                           SET saldo_actual = COALESCE(saldo_actual, 0) + $1, updated_at = NOW()
                         WHERE id = $2
                    """, p['monto'], p['cuenta_id'])
                await conn.execute(
                    "DELETE FROM finanzas2.fin_planilla_destajo_pago WHERE detalle_id = $1",
                    detalle_id)

            # Desmarcar adelantos del detalle
            await conn.execute("""
                UPDATE finanzas2.fin_adelanto_trabajador
                   SET descontado = FALSE, updated_at = NOW()
                 WHERE detalle_destajo_id = $1 AND empresa_id = $2
            """, detalle_id, empresa_id)

            # Desmarcar detalle
            await conn.execute("""
                UPDATE finanzas2.fin_planilla_destajo_detalle
                   SET pagado_at = NULL, pagado_por = NULL, updated_at = NOW()
                 WHERE id = $1
            """, detalle_id)

            # Si la planilla estaba pagada, volver a aprobada
            if pl['estado'] == 'pagada':
                await conn.execute("""
                    UPDATE finanzas2.fin_planilla_destajo
                       SET estado = 'aprobada', fecha_pago = NULL,
                           anulado_at = NOW(), anulado_por = $1,
                           pagado_at = NULL, pagado_por = NULL,
                           updated_at = NOW()
                     WHERE id = $2
                """, user.get('username') if user else None, planilla_id)

            return await _get_planilla_full(conn, planilla_id, empresa_id)


# ─────────────────────────────────────────────────────────────────
#  DELETE (con reverso automático)
# ─────────────────────────────────────────────────────────────────

@router.delete("/planillas-destajo/{planilla_id}")
async def delete_planilla(
    planilla_id: int,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            pl = await conn.fetchrow(
                "SELECT * FROM finanzas2.fin_planilla_destajo WHERE id = $1 AND empresa_id = $2",
                planilla_id, empresa_id)
            if not pl:
                raise HTTPException(404, "Planilla no encontrada")

            # Revertir TODOS los pagos (cualquier estado)
            revertidos = 0
            if await _table_exists(conn, 'fin_planilla_destajo_pago'):
                pagos = await conn.fetch("""
                    SELECT * FROM finanzas2.fin_planilla_destajo_pago WHERE planilla_destajo_id = $1
                """, planilla_id)
                for p in pagos:
                    await delete_movimientos_by_origen(
                        conn, empresa_id, 'planilla_destajo_pago', p['id'])
                    await conn.execute("""
                        UPDATE finanzas2.cont_cuenta_financiera
                           SET saldo_actual = COALESCE(saldo_actual, 0) + $1, updated_at = NOW()
                         WHERE id = $2
                    """, p['monto'], p['cuenta_id'])
                    revertidos += 1

            # Liberar adelantos vinculados
            await conn.execute("""
                UPDATE finanzas2.fin_adelanto_trabajador
                   SET planilla_destajo_id = NULL, detalle_destajo_id = NULL,
                       descontado = FALSE, updated_at = NOW()
                 WHERE planilla_destajo_id = $1
            """, planilla_id)

            # Borrar planilla (CASCADE elimina detalles + movimientos + pagos)
            await conn.execute(
                "DELETE FROM finanzas2.fin_planilla_destajo WHERE id = $1",
                planilla_id)

            return {
                "message": "Planilla destajo eliminada",
                "estado_previo": pl['estado'],
                "pagos_revertidos": revertidos,
            }
