"""POS Estados: Confirmar, Crédito, Descartar, Desconfirmar + Distribución Analítica."""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from datetime import date, datetime, timedelta
from database import get_pool
from dependencies import get_empresa_id
from routers.pos_common import get_company_key
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# =====================
# VENTAS POS — CONFIRMAR / DESCARTAR / CREDITO
# =====================
@router.post("/ventas-pos/{order_id}/confirmar")
async def confirmar_venta_pos(order_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        company_key = await get_company_key(conn, empresa_id)

        if company_key:
            # Leer desde tablas locales (desacoplado de Odoo)
            order = await conn.fetchrow(
                "SELECT id, amount_total FROM finanzas2.cont_venta_pos WHERE odoo_id=$1 AND empresa_id=$2",
                order_id, empresa_id)
            if not order:
                raise HTTPException(404, "Orden no encontrada en tablas locales")
            venta_pos_internal_id = order['id']
            estado = await conn.fetchrow(
                "SELECT estado_local FROM finanzas2.cont_venta_pos_estado WHERE odoo_order_id=$1 AND empresa_id=$2",
                order_id, empresa_id)
            if estado and estado['estado_local'] in ('confirmada', 'credito', 'descartada'):
                raise HTTPException(400, f"Venta ya tiene estado: {estado['estado_local']}")

            async with conn.transaction():
                await conn.execute("""
                    INSERT INTO finanzas2.cont_venta_pos_estado (empresa_id, odoo_order_id, estado_local, updated_at)
                    VALUES ($1, $2, 'confirmada', NOW())
                    ON CONFLICT (empresa_id, odoo_order_id)
                    DO UPDATE SET estado_local = 'confirmada', updated_at = NOW()
                """, empresa_id, order_id)

                # CAPA TESORERIA: 1 movimiento REAL por cobro total (no N ficticios)
                amount = float(order['amount_total'] or 0)
                if amount > 0:
                    pagos = await conn.fetch(
                        "SELECT forma_pago, monto, cuenta_financiera_id, referencia, fecha_pago, observaciones FROM finanzas2.cont_venta_pos_pago WHERE odoo_order_id=$1 AND empresa_id=$2",
                        order_id, empresa_id)
                    from services.treasury_service import create_movimiento_tesoreria
                    if pagos:
                        for pago in pagos:
                            await create_movimiento_tesoreria(
                                conn, empresa_id, date.today(), 'ingreso', float(pago['monto']),
                                cuenta_financiera_id=pago['cuenta_financiera_id'],
                                forma_pago=pago['forma_pago'],
                                concepto=f"Venta POS #{order_id} confirmada",
                                origen_tipo='venta_pos_confirmada',
                                origen_id=order_id,
                            )
                    else:
                        await create_movimiento_tesoreria(
                            conn, empresa_id, date.today(), 'ingreso', amount,
                            concepto=f"Venta POS #{order_id} confirmada",
                            origen_tipo='venta_pos_confirmada',
                            origen_id=order_id,
                        )

                    # CAPA PAGOS: Crear cont_pago para cada pago registrado
                    moneda_id = await conn.fetchval(
                        "SELECT id FROM finanzas2.cont_moneda WHERE codigo='PEN'")
                    if not moneda_id:
                        moneda_id = await conn.fetchval(
                            "SELECT id FROM finanzas2.cont_moneda ORDER BY id LIMIT 1")

                    if pagos:
                        for pago_item in pagos:
                            last_pago = await conn.fetchval(
                                "SELECT numero FROM finanzas2.cont_pago WHERE tipo='ingreso' AND empresa_id=$1 ORDER BY id DESC LIMIT 1",
                                empresa_id)
                            if last_pago and '-' in last_pago:
                                parts = last_pago.split('-')
                                num = int(parts[-1]) + 1 if len(parts) >= 3 else 1
                            else:
                                num = 1
                            numero_pago = f"PAG-I-{datetime.now().year}-{num:05d}"
                            pago_result = await conn.fetchrow("""
                                INSERT INTO finanzas2.cont_pago
                                (numero, tipo, fecha, cuenta_financiera_id, moneda_id, monto_total,
                                 referencia, notas, empresa_id)
                                VALUES ($1, 'ingreso', $2::date, $3, $4, $5, $6, $7, $8)
                                RETURNING id
                            """, numero_pago, pago_item['fecha_pago'] or date.today(),
                                pago_item['cuenta_financiera_id'],
                                moneda_id, pago_item['monto'], pago_item['referencia'],
                                f"Venta POS #{order_id} confirmada - {pago_item['observaciones'] or ''}",
                                empresa_id)
                            pago_id = pago_result['id']
                            await conn.execute("""
                                INSERT INTO finanzas2.cont_pago_detalle
                                (pago_id, cuenta_financiera_id, medio_pago, monto, referencia, empresa_id)
                                VALUES ($1, $2, $3, $4, $5, $6)
                            """, pago_id, pago_item['cuenta_financiera_id'], pago_item['forma_pago'],
                                pago_item['monto'], pago_item['referencia'], empresa_id)
                            await conn.execute("""
                                INSERT INTO finanzas2.cont_pago_aplicacion
                                (pago_id, tipo_documento, documento_id, monto_aplicado, empresa_id)
                                VALUES ($1, 'venta_pos_odoo', $2, $3, $4)
                            """, pago_id, order_id, pago_item['monto'], empresa_id)

                    # Auto-CxC si hay saldo pendiente
                    total_pagos = sum(float(p['monto']) for p in pagos) if pagos else 0
                    saldo_pendiente = amount - total_pagos
                    if saldo_pendiente > 0.01:
                        cxc = await conn.fetchrow("""
                            INSERT INTO finanzas2.cont_cxc
                            (empresa_id, venta_pos_id, monto_original, saldo_pendiente,
                             fecha_vencimiento, estado, tipo_origen, odoo_order_id)
                            VALUES ($1, $2, $3, $3, CURRENT_DATE + 30, 'pendiente', 'venta_pos_saldo', $4)
                            RETURNING id
                        """, empresa_id, venta_pos_internal_id, saldo_pendiente, order_id)
                        await conn.execute("""
                            UPDATE finanzas2.cont_venta_pos_estado SET cxc_id = $1
                            WHERE odoo_order_id = $2 AND empresa_id = $3
                        """, cxc['id'], order_id, empresa_id)

                # Si hubo pagos, crear distribución de cobro (dinero real recibido)
                if amount > 0:
                    total_cobrado = sum(float(p['monto']) for p in pagos) if pagos else amount
                    if total_cobrado > 0:
                        from services.distribucion_analitica import crear_distribucion_cobro
                        await crear_distribucion_cobro(
                            conn, empresa_id, order_id, order_id, total_cobrado, date.today())

            return {"message": "Venta confirmada"}
        else:
            # Fallback: legacy
            await conn.execute("SET search_path TO finanzas2, public")
            venta = await conn.fetchrow(
                "SELECT * FROM finanzas2.cont_venta_pos WHERE id=$1 AND empresa_id=$2",
                order_id, empresa_id)
            if not venta:
                raise HTTPException(404, "Venta not found")
            if venta['estado_local'] in ('confirmada', 'credito', 'descartada'):
                raise HTTPException(400, f"Venta already {venta['estado_local']}")
            await conn.execute(
                "UPDATE finanzas2.cont_venta_pos SET estado_local='confirmada' WHERE id=$1", order_id)
            return {"message": "Venta confirmada"}


@router.post("/ventas-pos/{order_id}/credito")
async def marcar_credito_venta_pos(
    order_id: int,
    fecha_vencimiento: Optional[date] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        company_key = await get_company_key(conn, empresa_id)

        if company_key:
            # Leer desde tablas locales
            order = await conn.fetchrow(
                "SELECT id, amount_total FROM finanzas2.cont_venta_pos WHERE odoo_id=$1 AND empresa_id=$2",
                order_id, empresa_id)
            if not order:
                raise HTTPException(404, "Orden no encontrada")

            estado = await conn.fetchrow(
                "SELECT estado_local FROM finanzas2.cont_venta_pos_estado WHERE odoo_order_id=$1 AND empresa_id=$2",
                order_id, empresa_id)
            if estado and estado['estado_local'] in ('confirmada', 'credito', 'descartada'):
                raise HTTPException(400, f"Venta ya tiene estado: {estado['estado_local']}")

            venc = fecha_vencimiento or (datetime.now().date() + timedelta(days=30))
            venta_pos_internal_id = order['id']

            async with conn.transaction():
                cxc = await conn.fetchrow("""
                    INSERT INTO finanzas2.cont_cxc
                    (empresa_id, venta_pos_id, monto_original, saldo_pendiente,
                     fecha_vencimiento, estado, tipo_origen, odoo_order_id)
                    VALUES ($1, $2, $3, $3, $4, 'pendiente', 'venta_pos_credito', $5)
                    RETURNING id
                """, empresa_id, venta_pos_internal_id, order['amount_total'], venc, order_id)

                await conn.execute("""
                    INSERT INTO finanzas2.cont_venta_pos_estado
                        (empresa_id, odoo_order_id, estado_local, cxc_id, updated_at)
                    VALUES ($1, $2, 'credito', $3, NOW())
                    ON CONFLICT (empresa_id, odoo_order_id)
                    DO UPDATE SET estado_local='credito', cxc_id=$3, updated_at=NOW()
                """, empresa_id, order_id, cxc['id'])

                # Crédito: NO crear distribución de ingreso (no hay movimiento de dinero)
                # El ingreso se registrará cuando se cobre la CxC

            return {"message": "Venta marcada como credito", "cxc_id": cxc['id']}
        else:
            # Fallback
            await conn.execute("SET search_path TO finanzas2, public")
            venta = await conn.fetchrow(
                "SELECT * FROM finanzas2.cont_venta_pos WHERE id=$1 AND empresa_id=$2",
                order_id, empresa_id)
            if not venta:
                raise HTTPException(404, "Venta not found")
            venc = fecha_vencimiento or (datetime.now().date() + timedelta(days=30))
            cxc = await conn.fetchrow("""
                INSERT INTO finanzas2.cont_cxc
                (venta_pos_id, monto_original, saldo_pendiente, fecha_vencimiento, estado, empresa_id, tipo_origen)
                VALUES ($1, $2, $2, $3, 'pendiente', $4, 'venta_pos_credito')
                RETURNING id
            """, order_id, venta['amount_total'], venc, empresa_id)
            await conn.execute(
                "UPDATE finanzas2.cont_venta_pos SET estado_local='credito', cxc_id=$1, is_credit=TRUE WHERE id=$2",
                cxc['id'], order_id)
            return {"message": "Venta marcada como credito", "cxc_id": cxc['id']}


@router.post("/ventas-pos/{order_id}/descartar")
async def descartar_venta_pos(order_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        company_key = await get_company_key(conn, empresa_id)

        if company_key:
            await conn.execute("""
                INSERT INTO finanzas2.cont_venta_pos_estado
                    (empresa_id, odoo_order_id, estado_local, updated_at)
                VALUES ($1, $2, 'descartada', NOW())
                ON CONFLICT (empresa_id, odoo_order_id)
                DO UPDATE SET estado_local='descartada', updated_at=NOW()
            """, empresa_id, order_id)
            return {"message": "Venta descartada"}
        else:
            await conn.execute("SET search_path TO finanzas2, public")
            await conn.execute(
                "UPDATE finanzas2.cont_venta_pos SET estado_local='descartada', is_cancel=TRUE WHERE id=$1",
                order_id)
            return {"message": "Venta descartada"}


@router.post("/ventas-pos/{order_id}/desconfirmar")
async def desconfirmar_venta_pos(order_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        company_key = await get_company_key(conn, empresa_id)

        if company_key:
            estado = await conn.fetchrow(
                "SELECT estado_local FROM finanzas2.cont_venta_pos_estado WHERE odoo_order_id=$1 AND empresa_id=$2",
                order_id, empresa_id)
            if not estado or estado['estado_local'] != 'confirmada':
                raise HTTPException(400, f"La venta debe estar confirmada para desconfirmarla")

            # Reverse official pagos
            pagos_oficiales = await conn.fetch("""
                SELECT p.id as pago_id, pd.medio_pago, pd.monto, pd.referencia,
                       p.fecha, pd.cuenta_financiera_id, p.notas
                FROM finanzas2.cont_pago_aplicacion pa
                JOIN finanzas2.cont_pago p ON p.id = pa.pago_id
                LEFT JOIN finanzas2.cont_pago_detalle pd ON pd.pago_id = p.id
                WHERE pa.tipo_documento = 'venta_pos_odoo' AND pa.documento_id = $1 AND pa.empresa_id = $2
            """, order_id, empresa_id)

            # Restore pagos to venta_pos_pago
            await conn.execute(
                "DELETE FROM finanzas2.cont_venta_pos_pago WHERE odoo_order_id=$1 AND empresa_id=$2",
                order_id, empresa_id)
            if pagos_oficiales:
                for pago in pagos_oficiales:
                    await conn.execute("""
                        INSERT INTO finanzas2.cont_venta_pos_pago
                        (odoo_order_id, forma_pago, cuenta_financiera_id, monto, referencia,
                         fecha_pago, observaciones, empresa_id)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """, order_id, pago['medio_pago'], pago['cuenta_financiera_id'],
                        pago['monto'], pago['referencia'], pago['fecha'],
                        pago['notas'] or 'Pago restaurado desde confirmacion', empresa_id)
                pago_ids = list(set(p['pago_id'] for p in pagos_oficiales))
                for pid in pago_ids:
                    await conn.execute("DELETE FROM finanzas2.cont_pago WHERE id=$1", pid)

            await conn.execute("""
                UPDATE finanzas2.cont_venta_pos_estado
                SET estado_local='pendiente', updated_at=NOW()
                WHERE odoo_order_id=$1 AND empresa_id=$2
            """, order_id, empresa_id)

            # CAPA TESORERIA: Remove treasury movements for this sale
            from services.treasury_service import delete_movimientos_by_origen
            await delete_movimientos_by_origen(conn, empresa_id, 'venta_pos_confirmada', order_id)

            # DISTRIBUCION ANALITICA: Remove analytical distributions
            from services.distribucion_analitica import eliminar_distribucion_by_origen
            await eliminar_distribucion_by_origen(conn, empresa_id, 'venta_pos_ingreso', order_id)
            # Also remove cobro distributions linked to this order
            await conn.execute("""
                DELETE FROM finanzas2.cont_distribucion_analitica
                WHERE empresa_id = $1 AND origen_tipo = 'cobranza_cxc'
                  AND origen_id = $2
            """, empresa_id, order_id)

            return {
                "message": "Venta desconfirmada exitosamente",
                "pagos_restaurados": len(pagos_oficiales),
                "nuevo_estado": "pendiente"
            }
        else:
            # Fallback: legacy desconfirmar
            await conn.execute("SET search_path TO finanzas2, public")
            async with conn.transaction():
                venta = await conn.fetchrow(
                    "SELECT * FROM finanzas2.cont_venta_pos WHERE id=$1 AND empresa_id=$2",
                    order_id, empresa_id)
                if not venta:
                    raise HTTPException(404, "Venta not found")
                if venta['estado_local'] != 'confirmada':
                    raise HTTPException(400, f"Estado actual: {venta['estado_local']}")
                pagos_oficiales = await conn.fetch("""
                    SELECT p.id as pago_id, pd.medio_pago, pd.monto, pd.referencia,
                           p.fecha, pd.cuenta_financiera_id, p.notas
                    FROM finanzas2.cont_pago_aplicacion pa
                    JOIN finanzas2.cont_pago p ON p.id = pa.pago_id
                    LEFT JOIN finanzas2.cont_pago_detalle pd ON pd.pago_id = p.id
                    WHERE pa.tipo_documento = 'venta_pos' AND pa.documento_id = $1
                """, order_id)
                await conn.execute(
                    "DELETE FROM finanzas2.cont_venta_pos_pago WHERE venta_pos_id=$1", order_id)
                if pagos_oficiales:
                    for pago in pagos_oficiales:
                        await conn.execute("""
                            INSERT INTO finanzas2.cont_venta_pos_pago
                            (venta_pos_id, forma_pago, cuenta_financiera_id, monto, referencia,
                             fecha_pago, observaciones, empresa_id)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        """, order_id, pago['medio_pago'], pago['cuenta_financiera_id'],
                            pago['monto'], pago['referencia'], pago['fecha'],
                            pago['notas'] or 'Pago restaurado', empresa_id)
                    pago_ids = list(set(p['pago_id'] for p in pagos_oficiales))
                    for pid in pago_ids:
                        await conn.execute("DELETE FROM finanzas2.cont_pago WHERE id=$1", pid)
                await conn.execute(
                    "UPDATE finanzas2.cont_venta_pos SET estado_local='pendiente' WHERE id=$1", order_id)
                return {"message": "Venta desconfirmada", "pagos_restaurados": len(pagos_oficiales)}


# =====================
# VENTAS POS — DISTRIBUCION ANALITICA POR LINEA DE NEGOCIO
# =====================
@router.get("/ventas-pos/{order_id}/distribucion-analitica")
async def get_distribucion_analitica(order_id: int, empresa_id: int = Depends(get_empresa_id)):
    """Retorna vendido/cobrado/pendiente por linea de negocio para una venta."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        # Vendido por linea
        vendido = await conn.fetch("""
            SELECT da.linea_negocio_id, ln.nombre as linea_negocio_nombre,
                   SUM(da.monto) as monto
            FROM cont_distribucion_analitica da
            LEFT JOIN cont_linea_negocio ln ON ln.id = da.linea_negocio_id
            WHERE da.empresa_id = $1 AND da.origen_tipo = 'venta_pos_ingreso'
              AND da.origen_id = $2
            GROUP BY da.linea_negocio_id, ln.nombre
        """, empresa_id, order_id)

        # Cobrado por linea (puede venir de multiples abonos)
        cobrado = await conn.fetch("""
            SELECT da.linea_negocio_id, ln.nombre as linea_negocio_nombre,
                   SUM(da.monto) as monto
            FROM cont_distribucion_analitica da
            LEFT JOIN cont_linea_negocio ln ON ln.id = da.linea_negocio_id
            WHERE da.empresa_id = $1 AND da.origen_tipo = 'cobranza_cxc'
              AND da.origen_id IN (
                  SELECT a.id FROM cont_cxc_abono a
                  JOIN cont_cxc c ON c.id = a.cxc_id
                  WHERE c.odoo_order_id = $2 AND c.empresa_id = $1
              )
            GROUP BY da.linea_negocio_id, ln.nombre
        """, empresa_id, order_id)

        # Also include cobro from confirmar (origen_id = order_id for direct confirm)
        cobrado_directo = await conn.fetch("""
            SELECT da.linea_negocio_id, ln.nombre as linea_negocio_nombre,
                   SUM(da.monto) as monto
            FROM cont_distribucion_analitica da
            LEFT JOIN cont_linea_negocio ln ON ln.id = da.linea_negocio_id
            WHERE da.empresa_id = $1 AND da.origen_tipo = 'cobranza_cxc'
              AND da.origen_id = $2
            GROUP BY da.linea_negocio_id, ln.nombre
        """, empresa_id, order_id)

        # Merge
        vendido_map = {r['linea_negocio_id']: {"linea_negocio_id": r['linea_negocio_id'],
                       "linea_negocio_nombre": r['linea_negocio_nombre'] or 'SIN CLASIFICAR',
                       "vendido": float(r['monto']), "cobrado": 0} for r in vendido}
        for r in list(cobrado) + list(cobrado_directo):
            ln_id = r['linea_negocio_id']
            if ln_id in vendido_map:
                vendido_map[ln_id]['cobrado'] += float(r['monto'])
            else:
                vendido_map[ln_id] = {
                    "linea_negocio_id": ln_id,
                    "linea_negocio_nombre": r['linea_negocio_nombre'] or 'SIN CLASIFICAR',
                    "vendido": 0, "cobrado": float(r['monto'])}

        result = []
        for v in vendido_map.values():
            v['pendiente'] = round(v['vendido'] - v['cobrado'], 2)
            result.append(v)
        return sorted(result, key=lambda x: x['vendido'], reverse=True)
