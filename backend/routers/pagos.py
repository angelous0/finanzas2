"""
pagos.py - Unified Payment & Letras Router
All payments read/write from cont_movimiento_tesoreria (single source of truth).
cont_pago is DEPRECATED and no longer written to from this router.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from datetime import date, datetime
from database import get_pool
from models import PagoCreate, Letra, GenerarLetrasRequest
from dependencies import get_empresa_id, get_next_correlativo, safe_date_param
from services.treasury_service import create_movimiento_tesoreria
from services.distribucion_service import calcular_distribucion_factura
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


async def generate_pago_number(conn, tipo: str, empresa_id: int) -> str:
    year = datetime.now().year
    prefijo = f"PAG-{tipo[0].upper()}-{year}-"
    return await get_next_correlativo(conn, empresa_id, f'pago_{tipo}', prefijo)


def _serialize_row(row):
    """Convert an asyncpg Record to a JSON-safe dict."""
    d = dict(row)
    if 'monto' in d and 'monto_total' not in d:
        d['monto_total'] = float(d.pop('monto', 0))
    elif 'monto_total' in d:
        d['monto_total'] = float(d['monto_total'])
    for k in ('fecha', 'created_at', 'updated_at'):
        if d.get(k) and hasattr(d[k], 'isoformat'):
            d[k] = d[k].isoformat()
    for k in d:
        from decimal import Decimal
        if isinstance(d[k], Decimal):
            d[k] = float(d[k])
    return d


_PAGO_SELECT = """
    SELECT mt.id, mt.empresa_id,
           COALESCE(mt.numero, UPPER(REPLACE(mt.origen_tipo,'_','-')) || '-' || mt.id::text) as numero,
           mt.tipo, mt.fecha,
           mt.monto as monto_total, mt.cuenta_financiera_id, mt.moneda_id,
           mt.referencia, mt.notas, COALESCE(mt.conciliado, false) as conciliado,
           mt.origen_tipo, mt.concepto,
           mt.centro_costo_id, mt.linea_negocio_id,
           mt.created_at, mt.updated_at,
           cf.nombre as cuenta_nombre, mon.codigo as moneda_codigo,
           cc.nombre as centro_costo_nombre, ln.nombre as linea_negocio_nombre
    FROM finanzas2.cont_movimiento_tesoreria mt
    LEFT JOIN finanzas2.cont_cuenta_financiera cf ON mt.cuenta_financiera_id = cf.id
    LEFT JOIN finanzas2.cont_moneda mon ON mt.moneda_id = mon.id
    LEFT JOIN finanzas2.cont_centro_costo cc ON mt.centro_costo_id = cc.id
    LEFT JOIN finanzas2.cont_linea_negocio ln ON mt.linea_negocio_id = ln.id
"""


async def _load_detalles_aplicaciones(conn, mov_id: int, pago_dict: dict):
    """Load detalles and aplicaciones for a payment/movement."""
    detalles = await conn.fetch("""
        SELECT pd.*, cf.nombre as cuenta_nombre
        FROM finanzas2.cont_pago_detalle pd
        LEFT JOIN finanzas2.cont_cuenta_financiera cf ON pd.cuenta_financiera_id = cf.id
        WHERE pd.movimiento_tesoreria_id = $1
    """, mov_id)
    pago_dict['detalles'] = [_serialize_row(d) for d in detalles]

    aplicaciones = await conn.fetch(
        "SELECT * FROM finanzas2.cont_pago_aplicacion WHERE movimiento_tesoreria_id = $1", mov_id)
    pago_dict['aplicaciones'] = [_serialize_row(a) for a in aplicaciones]


# =====================
# PAGOS CRUD
# =====================

@router.get("/pagos")
async def list_pagos(
    tipo: Optional[str] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    cuenta_financiera_id: Optional[int] = None,
    conciliado: Optional[bool] = None,
    centro_costo_id: Optional[int] = None,
    linea_negocio_id: Optional[int] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        conditions = ["mt.empresa_id = $1"]
        params = [empresa_id]
        idx = 2

        if tipo:
            conditions.append(f"mt.tipo = ${idx}"); params.append(tipo); idx += 1
        if fecha_desde:
            conditions.append(f"mt.fecha >= ${idx}"); params.append(fecha_desde); idx += 1
        if fecha_hasta:
            conditions.append(f"mt.fecha <= ${idx}"); params.append(fecha_hasta); idx += 1
        if cuenta_financiera_id:
            conditions.append(f"mt.cuenta_financiera_id = ${idx}"); params.append(cuenta_financiera_id); idx += 1
        if conciliado is not None:
            conditions.append(f"COALESCE(mt.conciliado, false) = ${idx}"); params.append(conciliado); idx += 1
        if centro_costo_id:
            conditions.append(f"mt.centro_costo_id = ${idx}"); params.append(centro_costo_id); idx += 1
        if linea_negocio_id:
            conditions.append(f"mt.linea_negocio_id = ${idx}"); params.append(linea_negocio_id); idx += 1

        query = f"""{_PAGO_SELECT}
            WHERE {' AND '.join(conditions)}
            ORDER BY mt.fecha DESC, mt.id DESC
        """
        rows = await conn.fetch(query, *params)
        result = []
        for row in rows:
            pago_dict = _serialize_row(row)
            await _load_detalles_aplicaciones(conn, row['id'], pago_dict)
            result.append(pago_dict)
        return result


@router.post("/pagos")
async def create_pago(data: PagoCreate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        async with conn.transaction():
            # ── Validate applications ──
            for aplicacion in data.aplicaciones:
                if aplicacion.tipo_documento == 'factura':
                    doc = await conn.fetchrow(
                        "SELECT saldo_pendiente, total, estado FROM finanzas2.cont_factura_proveedor WHERE id = $1",
                        aplicacion.documento_id)
                    if not doc:
                        raise HTTPException(404, f"Factura {aplicacion.documento_id} not found")
                    if doc['estado'] == 'canjeado':
                        raise HTTPException(400, "No se puede pagar una factura canjeada. Debe pagar las letras.")
                    if aplicacion.monto_aplicado > float(doc['saldo_pendiente']):
                        raise HTTPException(400,
                            f"El monto ({aplicacion.monto_aplicado:.2f}) excede el saldo pendiente ({doc['saldo_pendiente']:.2f})")
                elif aplicacion.tipo_documento == 'letra':
                    doc = await conn.fetchrow(
                        "SELECT saldo_pendiente, monto, estado FROM finanzas2.cont_letra WHERE id = $1",
                        aplicacion.documento_id)
                    if not doc:
                        raise HTTPException(404, f"Letra {aplicacion.documento_id} not found")
                    if doc['estado'] == 'pagada':
                        raise HTTPException(400, "La letra ya esta pagada")
                    saldo = float(doc['saldo_pendiente'])
                    if abs(aplicacion.monto_aplicado - saldo) > 0.01:
                        raise HTTPException(400,
                            f"El pago de una letra debe ser por el monto exacto ({saldo:.2f}). No se permiten pagos parciales.")

            # ── Generate payment number ──
            numero = await generate_pago_number(conn, data.tipo, empresa_id)

            # ── Create the MAIN treasury movement (replaces cont_pago) ──
            primary_cuenta = data.detalles[0].cuenta_financiera_id if data.detalles else data.cuenta_financiera_id
            primary_forma = data.detalles[0].medio_pago if data.detalles else None

            mov_id = await create_movimiento_tesoreria(
                conn, empresa_id,
                fecha=data.fecha,
                tipo=data.tipo,
                monto=data.monto_total,
                cuenta_financiera_id=primary_cuenta,
                forma_pago=primary_forma,
                referencia=data.referencia,
                concepto=data.notas or data.referencia or f"Pago {numero}",
                origen_tipo=f'pago_{data.tipo}',
                numero=numero,
                moneda_id=data.moneda_id,
                notas=data.notas,
            )

            # ── Insert payment details and update account balances ──
            for detalle in data.detalles:
                await conn.execute("""
                    INSERT INTO finanzas2.cont_pago_detalle
                    (empresa_id, movimiento_tesoreria_id, cuenta_financiera_id, medio_pago, monto, referencia)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, empresa_id, mov_id, detalle.cuenta_financiera_id, detalle.medio_pago,
                    detalle.monto, detalle.referencia)

                if data.tipo == 'egreso':
                    await conn.execute(
                        "UPDATE finanzas2.cont_cuenta_financiera SET saldo_actual = saldo_actual - $1 WHERE id = $2",
                        detalle.monto, detalle.cuenta_financiera_id)
                else:
                    await conn.execute(
                        "UPDATE finanzas2.cont_cuenta_financiera SET saldo_actual = saldo_actual + $1 WHERE id = $2",
                        detalle.monto, detalle.cuenta_financiera_id)

                # If fictitious account, register movement in fin_movimiento_cuenta
                is_ficticia = await conn.fetchval(
                    "SELECT es_ficticia FROM finanzas2.cont_cuenta_financiera WHERE id=$1",
                    detalle.cuenta_financiera_id)
                if is_ficticia:
                    mov_tipo = 'EGRESO' if data.tipo == 'egreso' else 'INGRESO'
                    await conn.execute("""
                        INSERT INTO finanzas2.fin_movimiento_cuenta
                        (cuenta_id, empresa_id, tipo, monto, descripcion, fecha, referencia_id, referencia_tipo)
                        VALUES ($1, $2, $3, $4, $5, TO_DATE($6, 'YYYY-MM-DD'), $7, 'PAGO')
                    """, detalle.cuenta_financiera_id, empresa_id, mov_tipo, detalle.monto,
                        data.notas or data.referencia or f"Pago {numero}",
                        data.fecha, str(mov_id))

            # ── Insert applications and update document states ──
            for aplicacion in data.aplicaciones:
                await conn.execute("""
                    INSERT INTO finanzas2.cont_pago_aplicacion
                    (empresa_id, movimiento_tesoreria_id, tipo_documento, documento_id, monto_aplicado)
                    VALUES ($1, $2, $3, $4, $5)
                """, empresa_id, mov_id, aplicacion.tipo_documento,
                    aplicacion.documento_id, aplicacion.monto_aplicado)

                if aplicacion.tipo_documento == 'factura':
                    await conn.execute(
                        "UPDATE finanzas2.cont_factura_proveedor SET saldo_pendiente = saldo_pendiente - $1 WHERE id = $2",
                        aplicacion.monto_aplicado, aplicacion.documento_id)
                    fp = await conn.fetchrow(
                        "SELECT total, saldo_pendiente FROM finanzas2.cont_factura_proveedor WHERE id = $1",
                        aplicacion.documento_id)
                    if fp['saldo_pendiente'] <= 0:
                        await conn.execute(
                            "UPDATE finanzas2.cont_factura_proveedor SET estado = 'pagado' WHERE id = $1",
                            aplicacion.documento_id)
                        await conn.execute(
                            "UPDATE finanzas2.cont_cxp SET estado = 'pagado', saldo_pendiente = 0 WHERE factura_id = $1",
                            aplicacion.documento_id)
                    else:
                        await conn.execute(
                            "UPDATE finanzas2.cont_factura_proveedor SET estado = 'parcial' WHERE id = $1",
                            aplicacion.documento_id)
                        await conn.execute(
                            "UPDATE finanzas2.cont_cxp SET estado = 'parcial', saldo_pendiente = $2 WHERE factura_id = $1",
                            aplicacion.documento_id, fp['saldo_pendiente'])

                    # Distribución analítica proporcional a líneas de factura
                    await calcular_distribucion_factura(
                        conn, empresa_id, aplicacion.documento_id,
                        mov_id, aplicacion.monto_aplicado,
                        data.fecha, f'pago_{data.tipo}'
                    )

                elif aplicacion.tipo_documento == 'letra':
                    await conn.execute(
                        "UPDATE finanzas2.cont_letra SET saldo_pendiente = saldo_pendiente - $1 WHERE id = $2",
                        aplicacion.monto_aplicado, aplicacion.documento_id)
                    letra = await conn.fetchrow(
                        "SELECT monto, saldo_pendiente, factura_id FROM finanzas2.cont_letra WHERE id = $1",
                        aplicacion.documento_id)
                    if letra['saldo_pendiente'] <= 0:
                        await conn.execute(
                            "UPDATE finanzas2.cont_letra SET estado = 'pagada' WHERE id = $1",
                            aplicacion.documento_id)
                    else:
                        await conn.execute(
                            "UPDATE finanzas2.cont_letra SET estado = 'parcial' WHERE id = $1",
                            aplicacion.documento_id)

                    if letra['factura_id']:
                        total_letras_pendiente = await conn.fetchval(
                            "SELECT COALESCE(SUM(saldo_pendiente), 0) FROM finanzas2.cont_letra WHERE factura_id = $1",
                            letra['factura_id'])
                        nuevo_saldo = float(total_letras_pendiente)
                        nuevo_estado = 'pagado' if nuevo_saldo <= 0 else 'parcial'
                        await conn.execute(
                            "UPDATE finanzas2.cont_cxp SET saldo_pendiente = $2, estado = $3 WHERE factura_id = $1",
                            letra['factura_id'], nuevo_saldo, nuevo_estado)
                        await conn.execute(
                            "UPDATE finanzas2.cont_factura_proveedor SET saldo_pendiente = $2 WHERE id = $1",
                            letra['factura_id'], nuevo_saldo)
                        # Distribución analítica proporcional a líneas de factura madre
                        await calcular_distribucion_factura(
                            conn, empresa_id, letra['factura_id'],
                            mov_id, aplicacion.monto_aplicado,
                            data.fecha, 'pago_letra'
                        )

            # ── Return the created payment ──
            row = await conn.fetchrow(f"""{_PAGO_SELECT}
                WHERE mt.id = $1
            """, mov_id)
            if not row:
                raise HTTPException(404, "Pago not found after creation")
            pago_dict = _serialize_row(row)
            await _load_detalles_aplicaciones(conn, mov_id, pago_dict)
            return pago_dict


@router.get("/pagos/{id}")
async def get_pago_endpoint(id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        row = await conn.fetchrow(f"""{_PAGO_SELECT}
            WHERE mt.id = $1 AND mt.empresa_id = $2
        """, id, empresa_id)
        if not row:
            raise HTTPException(404, "Pago not found")
        pago_dict = _serialize_row(row)
        await _load_detalles_aplicaciones(conn, id, pago_dict)
        return pago_dict


@router.put("/pagos/{id}")
async def update_pago(id: int, data: dict, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        mov = await conn.fetchrow(
            "SELECT * FROM finanzas2.cont_movimiento_tesoreria WHERE id = $1 AND empresa_id = $2",
            id, empresa_id)
        if not mov:
            raise HTTPException(404, "Pago no encontrado")

        if mov['conciliado']:
            if 'referencia' in data:
                await conn.execute(
                    "UPDATE finanzas2.cont_movimiento_tesoreria SET referencia = $1, updated_at = NOW() WHERE id = $2",
                    data.get('referencia'), id)
            return {"message": "Referencia actualizada (pago conciliado)"}

        update_fields = []
        values = []
        param_count = 1
        if 'fecha' in data:
            update_fields.append(f"fecha = TO_DATE(${param_count}, 'YYYY-MM-DD')")
            values.append(safe_date_param(data['fecha'])); param_count += 1
        if 'referencia' in data:
            update_fields.append(f"referencia = ${param_count}")
            values.append(data['referencia']); param_count += 1
        if 'notas' in data:
            update_fields.append(f"notas = ${param_count}")
            values.append(data['notas']); param_count += 1
        update_fields.append("updated_at = NOW()")
        if update_fields:
            values.append(id)
            query = f"UPDATE finanzas2.cont_movimiento_tesoreria SET {', '.join(update_fields)} WHERE id = ${param_count}"
            await conn.execute(query, *values)
        return {"message": "Pago actualizado exitosamente"}


@router.delete("/pagos/{id}")
async def delete_pago(id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        async with conn.transaction():
            mov = await conn.fetchrow(
                "SELECT * FROM finanzas2.cont_movimiento_tesoreria WHERE id = $1 AND empresa_id = $2",
                id, empresa_id)
            if not mov:
                raise HTTPException(404, "Pago not found")
            if mov.get('conciliado'):
                raise HTTPException(400, "No se puede eliminar un pago conciliado")

            # Reverse account balances from detalles (new-style via movimiento_tesoreria_id)
            detalles = await conn.fetch(
                "SELECT * FROM finanzas2.cont_pago_detalle WHERE movimiento_tesoreria_id = $1", id)
            # Fallback: if no new-style detalles, check old-style via pago_id = origen_id
            if not detalles and mov['origen_id']:
                detalles = await conn.fetch(
                    "SELECT * FROM finanzas2.cont_pago_detalle WHERE pago_id = $1", mov['origen_id'])

            for detalle in detalles:
                if mov['tipo'] == 'egreso':
                    await conn.execute(
                        "UPDATE finanzas2.cont_cuenta_financiera SET saldo_actual = saldo_actual + $1 WHERE id = $2",
                        detalle['monto'], detalle['cuenta_financiera_id'])
                else:
                    await conn.execute(
                        "UPDATE finanzas2.cont_cuenta_financiera SET saldo_actual = saldo_actual - $1 WHERE id = $2",
                        detalle['monto'], detalle['cuenta_financiera_id'])

            # If no detalles at all, reverse using the movement's own data
            if not detalles and mov['cuenta_financiera_id']:
                if mov['tipo'] == 'egreso':
                    await conn.execute(
                        "UPDATE finanzas2.cont_cuenta_financiera SET saldo_actual = saldo_actual + $1 WHERE id = $2",
                        mov['monto'], mov['cuenta_financiera_id'])
                else:
                    await conn.execute(
                        "UPDATE finanzas2.cont_cuenta_financiera SET saldo_actual = saldo_actual - $1 WHERE id = $2",
                        mov['monto'], mov['cuenta_financiera_id'])

            # Reverse document state changes from aplicaciones (new-style)
            aplicaciones = await conn.fetch(
                "SELECT * FROM finanzas2.cont_pago_aplicacion WHERE movimiento_tesoreria_id = $1", id)
            # Fallback: old-style via pago_id = origen_id
            if not aplicaciones and mov['origen_id']:
                aplicaciones = await conn.fetch(
                    "SELECT * FROM finanzas2.cont_pago_aplicacion WHERE pago_id = $1", mov['origen_id'])

            for aplicacion in aplicaciones:
                if aplicacion['tipo_documento'] == 'factura':
                    await conn.execute(
                        "UPDATE finanzas2.cont_factura_proveedor SET saldo_pendiente = saldo_pendiente + $1, estado = 'pendiente' WHERE id = $2",
                        aplicacion['monto_aplicado'], aplicacion['documento_id'])
                    await conn.execute(
                        "UPDATE finanzas2.cont_cxp SET saldo_pendiente = saldo_pendiente + $1, estado = 'pendiente' WHERE factura_id = $2",
                        aplicacion['monto_aplicado'], aplicacion['documento_id'])
                elif aplicacion['tipo_documento'] == 'letra':
                    await conn.execute(
                        "UPDATE finanzas2.cont_letra SET saldo_pendiente = saldo_pendiente + $1, estado = 'pendiente' WHERE id = $2",
                        aplicacion['monto_aplicado'], aplicacion['documento_id'])

            # Clean up linked records (both old and new style)
            await conn.execute("DELETE FROM finanzas2.cont_pago_detalle WHERE movimiento_tesoreria_id = $1", id)
            await conn.execute("DELETE FROM finanzas2.cont_pago_aplicacion WHERE movimiento_tesoreria_id = $1", id)
            if mov['origen_id']:
                await conn.execute("DELETE FROM finanzas2.cont_pago_detalle WHERE pago_id = $1", mov['origen_id'])
                await conn.execute("DELETE FROM finanzas2.cont_pago_aplicacion WHERE pago_id = $1", mov['origen_id'])
                # Also clean up the old cont_pago record if it exists
                await conn.execute("DELETE FROM finanzas2.cont_pago WHERE id = $1", mov['origen_id'])
            await conn.execute(
                "DELETE FROM finanzas2.cont_distribucion_analitica WHERE origen_tipo = 'pago_letra' AND origen_id = $1", id)
            await conn.execute(
                "DELETE FROM finanzas2.cont_movimiento_tesoreria WHERE id = $1 AND empresa_id = $2", id, empresa_id)
            return {"message": "Pago deleted and reversed"}


# =====================
# LETRAS
# =====================

@router.get("/letras", response_model=List[Letra])
async def list_letras(
    estado: Optional[str] = None,
    proveedor_id: Optional[int] = None,
    factura_id: Optional[int] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    q: Optional[str] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        conditions = ["l.empresa_id = $1"]
        params = [empresa_id]
        idx = 2
        if estado:
            conditions.append(f"l.estado = ${idx}"); params.append(estado); idx += 1
        if proveedor_id:
            conditions.append(f"l.proveedor_id = ${idx}"); params.append(proveedor_id); idx += 1
        if factura_id:
            conditions.append(f"l.factura_id = ${idx}"); params.append(factura_id); idx += 1
        if fecha_desde:
            conditions.append(f"l.fecha_vencimiento >= ${idx}"); params.append(fecha_desde); idx += 1
        if fecha_hasta:
            conditions.append(f"l.fecha_vencimiento <= ${idx}"); params.append(fecha_hasta); idx += 1
        if q:
            conditions.append(f"(l.numero ILIKE ${idx} OR l.numero_unico ILIKE ${idx} OR t.nombre ILIKE ${idx} OR fp.numero ILIKE ${idx})")
            params.append(f"%{q}%"); idx += 1
        query = f"""
            SELECT l.*, t.nombre as proveedor_nombre, fp.numero as factura_numero
            FROM finanzas2.cont_letra l
            LEFT JOIN finanzas2.cont_tercero t ON l.proveedor_id = t.id
            LEFT JOIN finanzas2.cont_factura_proveedor fp ON l.factura_id = fp.id
            WHERE {' AND '.join(conditions)}
            ORDER BY l.fecha_vencimiento ASC
        """
        rows = await conn.fetch(query, *params)
        return [dict(r) for r in rows]


@router.put("/letras/{id}/numero-unico")
async def update_letra_numero_unico(id: int, data: dict, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        letra = await conn.fetchrow(
            "SELECT id FROM finanzas2.cont_letra WHERE id = $1 AND empresa_id = $2", id, empresa_id)
        if not letra:
            raise HTTPException(404, "Letra no encontrada")
        await conn.execute(
            "UPDATE finanzas2.cont_letra SET numero_unico = $1, updated_at = NOW() WHERE id = $2",
            data.get('numero_unico', ''), id)
        return {"message": "Numero unico actualizado"}


@router.post("/letras/generar", response_model=List[Letra])
async def generar_letras(data: GenerarLetrasRequest, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        async with conn.transaction():
            factura = await conn.fetchrow("SELECT * FROM finanzas2.cont_factura_proveedor WHERE id = $1", data.factura_id)
            if not factura:
                raise HTTPException(404, "Factura not found")
            if factura['estado'] in ('pagado', 'anulada', 'canjeado'):
                raise HTTPException(400, "Cannot generate letras for this factura")
            existing = await conn.fetchval("SELECT COUNT(*) FROM finanzas2.cont_letra WHERE factura_id = $1", data.factura_id)
            if existing > 0:
                raise HTTPException(400, "Factura already has letras")
            letras = []
            if data.letras_personalizadas and len(data.letras_personalizadas) > 0:
                total_letras = sum(l.monto for l in data.letras_personalizadas)
                if abs(total_letras - float(factura['total'])) > 0.01:
                    raise HTTPException(400, f"El total de las letras ({total_letras:.2f}) debe ser igual al total de la factura ({factura['total']:.2f})")
                for i, letra_data in enumerate(data.letras_personalizadas):
                    numero = f"L-{factura['numero']}-{i+1:02d}"
                    from datetime import timedelta
                    letra = await conn.fetchrow("""
                        INSERT INTO finanzas2.cont_letra
                        (empresa_id, numero, factura_id, proveedor_id, monto, fecha_emision, fecha_vencimiento, estado, saldo_pendiente)
                        VALUES ($1, $2, $3, $4, $5, TO_DATE($6, 'YYYY-MM-DD'), TO_DATE($7, 'YYYY-MM-DD'), 'pendiente', $5)
                        RETURNING *
                    """, empresa_id, numero, data.factura_id, factura['proveedor_id'], letra_data.monto,
                        safe_date_param(datetime.now().date()), safe_date_param(letra_data.fecha_vencimiento))
                    letras.append(dict(letra))
            else:
                from datetime import timedelta
                monto_por_letra = data.monto_por_letra or (factura['total'] / data.cantidad_letras)
                fecha_base = factura['fecha_vencimiento'] or datetime.now().date()
                for i in range(data.cantidad_letras):
                    fecha_vencimiento = fecha_base + timedelta(days=data.dias_entre_letras * i)
                    numero = f"L-{factura['numero']}-{i+1:02d}"
                    letra = await conn.fetchrow("""
                        INSERT INTO finanzas2.cont_letra
                        (empresa_id, numero, factura_id, proveedor_id, monto, fecha_emision, fecha_vencimiento, estado, saldo_pendiente)
                        VALUES ($1, $2, $3, $4, $5, TO_DATE($6, 'YYYY-MM-DD'), TO_DATE($7, 'YYYY-MM-DD'), 'pendiente', $5)
                        RETURNING *
                    """, empresa_id, numero, data.factura_id, factura['proveedor_id'], monto_por_letra,
                        safe_date_param(datetime.now().date()), safe_date_param(fecha_vencimiento))
                    letras.append(dict(letra))
            await conn.execute("UPDATE finanzas2.cont_factura_proveedor SET estado = 'canjeado' WHERE id = $1", data.factura_id)
            await conn.execute("UPDATE finanzas2.cont_cxp SET estado = 'canjeado' WHERE factura_id = $1", data.factura_id)
            return letras


@router.delete("/letras/{id}")
async def delete_letra(id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        async with conn.transaction():
            letra = await conn.fetchrow("SELECT * FROM finanzas2.cont_letra WHERE id = $1 AND empresa_id = $2", id, empresa_id)
            if not letra:
                raise HTTPException(404, "Letra not found")
            # Check for payments via both old (pago_id) and new (movimiento_tesoreria_id) columns
            pagos = await conn.fetchval("""
                SELECT COUNT(*) FROM finanzas2.cont_pago_aplicacion
                WHERE tipo_documento = 'letra' AND documento_id = $1
            """, id)
            if pagos > 0:
                raise HTTPException(400, "Cannot delete letra with payments. Reverse payments first.")
            factura_id = letra['factura_id']
            await conn.execute("DELETE FROM finanzas2.cont_letra WHERE id = $1 AND empresa_id = $2", id, empresa_id)
            remaining = await conn.fetchval("SELECT COUNT(*) FROM finanzas2.cont_letra WHERE factura_id = $1", factura_id)
            if remaining == 0:
                await conn.execute("UPDATE finanzas2.cont_factura_proveedor SET estado = 'pendiente' WHERE id = $1", factura_id)
                await conn.execute("UPDATE finanzas2.cont_cxp SET estado = 'pendiente' WHERE factura_id = $1", factura_id)
            return {"message": "Letra deleted"}
