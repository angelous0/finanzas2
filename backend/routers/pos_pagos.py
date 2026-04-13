"""POS Pagos: CRUD de pagos para ventas POS."""
from fastapi import APIRouter, HTTPException, Depends
from datetime import date, datetime
from database import get_pool
from dependencies import get_empresa_id
from routers.pos_common import get_company_key
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# =====================
# VENTAS POS — PAGOS
# =====================
@router.get("/ventas-pos/{order_id}/pagos")
async def get_pagos_venta_pos(order_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        company_key = await get_company_key(conn, empresa_id)

        if company_key:
            pagos = await conn.fetch("""
                SELECT id, odoo_order_id as venta_pos_id, forma_pago, monto, referencia,
                       fecha_pago, observaciones, created_at
                FROM finanzas2.cont_venta_pos_pago
                WHERE odoo_order_id = $1 AND empresa_id = $2
                ORDER BY created_at DESC
            """, order_id, empresa_id)
            return [dict(p) for p in pagos]
        else:
            await conn.execute("SET search_path TO finanzas2, public")
            pagos = await conn.fetch("""
                SELECT id, venta_pos_id, forma_pago, monto, referencia, fecha_pago, observaciones, created_at
                FROM finanzas2.cont_venta_pos_pago WHERE venta_pos_id = $1 ORDER BY created_at DESC
            """, order_id)
            return [dict(p) for p in pagos]


@router.get("/ventas-pos/{order_id}/pagos-oficiales")
async def get_pagos_oficiales_venta_pos(order_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        company_key = await get_company_key(conn, empresa_id)
        tipo_doc = 'venta_pos_odoo' if company_key else 'venta_pos'

        pagos = await conn.fetch(f"""
            SELECT p.id, p.numero, p.fecha, pd.medio_pago as forma_pago, pd.monto,
                   pd.referencia, p.notas as observaciones, cf.nombre as cuenta_nombre
            FROM finanzas2.cont_pago_aplicacion pa
            JOIN finanzas2.cont_pago p ON p.id = pa.pago_id
            LEFT JOIN finanzas2.cont_pago_detalle pd ON pd.pago_id = p.id
            LEFT JOIN finanzas2.cont_cuenta_financiera cf ON cf.id = pd.cuenta_financiera_id
            WHERE pa.tipo_documento = $1 AND pa.documento_id = $2 AND pa.empresa_id = $3
            ORDER BY p.fecha DESC, p.id DESC
        """, tipo_doc, order_id, empresa_id)
        return [dict(p) for p in pagos]


@router.post("/ventas-pos/{order_id}/pagos")
async def add_pago_venta_pos(order_id: int, pago: dict, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        company_key = await get_company_key(conn, empresa_id)

        if company_key:
            order = await conn.fetchrow(
                "SELECT amount_total FROM finanzas2.cont_venta_pos WHERE odoo_id=$1 AND empresa_id=$2",
                order_id, empresa_id)
            if not order:
                raise HTTPException(404, "Orden no encontrada")

            estado = await conn.fetchrow(
                "SELECT estado_local FROM finanzas2.cont_venta_pos_estado WHERE odoo_order_id=$1 AND empresa_id=$2",
                order_id, empresa_id)
            if estado and estado['estado_local'] != 'pendiente':
                raise HTTPException(400, f"Venta ya tiene estado: {estado['estado_local']}")

            await conn.execute("""
                INSERT INTO finanzas2.cont_venta_pos_pago
                (odoo_order_id, forma_pago, cuenta_financiera_id, monto, referencia,
                 fecha_pago, observaciones, empresa_id)
                VALUES ($1, $2, $3, $4, $5, TO_DATE($6, 'YYYY-MM-DD'), $7, $8)
            """, order_id, pago.get('forma_pago'), int(pago.get('cuenta_financiera_id')),
                pago.get('monto'), pago.get('referencia'),
                pago.get('fecha_pago'), pago.get('observaciones'), empresa_id)

            total_pagos = await conn.fetchval(
                "SELECT COALESCE(SUM(monto), 0) FROM finanzas2.cont_venta_pos_pago WHERE odoo_order_id=$1 AND empresa_id=$2",
                order_id, empresa_id)
            amount_total = float(order['amount_total'])

            if abs(float(total_pagos) - amount_total) < 0.01 or float(total_pagos) >= amount_total:
                # Auto-confirm ONLY when fully paid
                await conn.execute("""
                    INSERT INTO finanzas2.cont_venta_pos_estado
                        (empresa_id, odoo_order_id, estado_local, updated_at)
                    VALUES ($1, $2, 'confirmada', NOW())
                    ON CONFLICT (empresa_id, odoo_order_id)
                    DO UPDATE SET estado_local='confirmada', updated_at=NOW()
                """, empresa_id, order_id)

                # Get default moneda (PEN)
                moneda_id = await conn.fetchval(
                    "SELECT id FROM finanzas2.cont_moneda WHERE codigo='PEN'")
                if not moneda_id:
                    moneda_id = await conn.fetchval(
                        "SELECT id FROM finanzas2.cont_moneda ORDER BY id LIMIT 1")

                # Create analytical distribution for the confirmed sale
                from services.distribucion_analitica import crear_distribucion_ingreso, crear_distribucion_cobro
                from services.treasury_service import create_movimiento_tesoreria
                await crear_distribucion_ingreso(conn, empresa_id, order_id, date.today())

                pagos_venta = await conn.fetch(
                    "SELECT * FROM finanzas2.cont_venta_pos_pago WHERE odoo_order_id=$1 AND empresa_id=$2",
                    order_id, empresa_id)
                for pago_item in pagos_venta:
                    # 1. CAPA TESORERIA: movimiento real
                    await create_movimiento_tesoreria(
                        conn, empresa_id, date.today(), 'ingreso', float(pago_item['monto']),
                        cuenta_financiera_id=pago_item['cuenta_financiera_id'],
                        forma_pago=pago_item['forma_pago'],
                        concepto=f"Venta POS #{order_id} confirmada",
                        origen_tipo='venta_pos_confirmada',
                        origen_id=order_id,
                    )
                    # 2. CAPA PAGOS: cont_pago + detalle + aplicacion
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
                    """, numero_pago, pago_item['fecha_pago'], pago_item['cuenta_financiera_id'],
                        moneda_id, pago_item['monto'], pago_item['referencia'],
                        f"Pago venta POS Odoo #{order_id} - {pago_item['observaciones'] or ''}",
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
                    # 3. DISTRIBUCION ANALITICA: cobro por linea
                    await crear_distribucion_cobro(conn, empresa_id, order_id, pago_id, pago_item['monto'], date.today())

                return {
                    "message": "Pago agregado y venta confirmada automaticamente",
                    "total_pagos": float(total_pagos),
                    "auto_confirmed": True,
                    "pagos_registrados": len(pagos_venta)
                }

            return {
                "message": "Pago agregado",
                "total_pagos": float(total_pagos),
                "faltante": amount_total - float(total_pagos),
                "auto_confirmed": False
            }
        else:
            # Fallback: legacy flow
            await conn.execute("SET search_path TO finanzas2, public")
            async with conn.transaction():
                venta = await conn.fetchrow(
                    "SELECT * FROM finanzas2.cont_venta_pos WHERE id=$1 AND empresa_id=$2",
                    order_id, empresa_id)
                if not venta:
                    raise HTTPException(404, "Venta not found")
                if venta['estado_local'] != 'pendiente':
                    raise HTTPException(400, f"Venta already {venta['estado_local']}")
                await conn.execute("""
                    INSERT INTO finanzas2.cont_venta_pos_pago
                    (venta_pos_id, forma_pago, cuenta_financiera_id, monto, referencia,
                     fecha_pago, observaciones, empresa_id)
                    VALUES ($1, $2, $3, $4, $5, TO_DATE($6, 'YYYY-MM-DD'), $7, $8)
                """, order_id, pago.get('forma_pago'), int(pago.get('cuenta_financiera_id')),
                    pago.get('monto'), pago.get('referencia'),
                    pago.get('fecha_pago'), pago.get('observaciones'), empresa_id)
                total_pagos = await conn.fetchval(
                    "SELECT COALESCE(SUM(monto), 0) FROM finanzas2.cont_venta_pos_pago WHERE venta_pos_id=$1",
                    order_id)
                amount_total = float(venta['amount_total'])
                if abs(float(total_pagos) - amount_total) < 0.01 or float(total_pagos) >= amount_total:
                    await conn.execute(
                        "UPDATE finanzas2.cont_venta_pos SET estado_local='confirmada' WHERE id=$1", order_id)
                    moneda_id = await conn.fetchval(
                        "SELECT id FROM finanzas2.cont_moneda WHERE codigo='PEN'")
                    if not moneda_id:
                        moneda_id = await conn.fetchval(
                            "SELECT id FROM finanzas2.cont_moneda ORDER BY id LIMIT 1")
                    pagos_venta = await conn.fetch(
                        "SELECT * FROM finanzas2.cont_venta_pos_pago WHERE venta_pos_id=$1", order_id)
                    for pago_item in pagos_venta:
                        last_pago = await conn.fetchval(
                            "SELECT numero FROM finanzas2.cont_pago WHERE tipo='ingreso' ORDER BY id DESC LIMIT 1")
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
                        """, numero_pago, pago_item['fecha_pago'],
                            pago_item['cuenta_financiera_id'],
                            moneda_id, pago_item['monto'], pago_item['referencia'],
                            f"Pago venta POS {venta['name']} - {pago_item['observaciones'] or ''}",
                            empresa_id)
                        pago_id = pago_result['id']
                        await conn.execute("""
                            INSERT INTO finanzas2.cont_pago_detalle
                            (pago_id, cuenta_financiera_id, medio_pago, monto, referencia, empresa_id)
                            VALUES ($1, $2, $3, $4, $5, $6)
                        """, pago_id, pago_item['cuenta_financiera_id'],
                            pago_item['forma_pago'], pago_item['monto'],
                            pago_item['referencia'], empresa_id)
                        await conn.execute("""
                            INSERT INTO finanzas2.cont_pago_aplicacion
                            (pago_id, tipo_documento, documento_id, monto_aplicado, empresa_id)
                            VALUES ($1, 'venta_pos', $2, $3, $4)
                        """, pago_id, order_id, pago_item['monto'], empresa_id)
                    return {
                        "message": "Pago agregado y venta confirmada automaticamente",
                        "total_pagos": float(total_pagos), "auto_confirmed": True,
                        "pagos_registrados": len(pagos_venta)
                    }
                return {
                    "message": "Pago agregado",
                    "total_pagos": float(total_pagos),
                    "faltante": amount_total - float(total_pagos),
                    "auto_confirmed": False
                }


@router.put("/ventas-pos/{order_id}/pagos/{pago_id}")
async def update_pago_venta_pos(order_id: int, pago_id: int, pago: dict, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        company_key = await get_company_key(conn, empresa_id)

        if company_key:
            await conn.execute("""
                UPDATE finanzas2.cont_venta_pos_pago
                SET forma_pago=$1, cuenta_financiera_id=$2, monto=$3, referencia=$4,
                    fecha_pago=TO_DATE($5, 'YYYY-MM-DD'), observaciones=$6
                WHERE id=$7 AND odoo_order_id=$8 AND empresa_id=$9
            """, pago['forma_pago'], pago.get('cuenta_financiera_id'),
                pago['monto'], pago.get('referencia'),
                pago.get('fecha_pago'), pago.get('observaciones'),
                pago_id, order_id, empresa_id)
        else:
            await conn.execute("""
                UPDATE finanzas2.cont_venta_pos_pago
                SET forma_pago=$1, cuenta_financiera_id=$2, monto=$3, referencia=$4,
                    fecha_pago=TO_DATE($5, 'YYYY-MM-DD'), observaciones=$6
                WHERE id=$7 AND venta_pos_id=$8
            """, pago['forma_pago'], pago.get('cuenta_financiera_id'),
                pago['monto'], pago.get('referencia'),
                pago.get('fecha_pago'), pago.get('observaciones'),
                pago_id, order_id)
        return {"message": "Pago actualizado correctamente"}


@router.delete("/ventas-pos/{order_id}/pagos/{pago_id}")
async def delete_pago_venta_pos(order_id: int, pago_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        company_key = await get_company_key(conn, empresa_id)

        if company_key:
            await conn.execute(
                "DELETE FROM finanzas2.cont_venta_pos_pago WHERE id=$1 AND odoo_order_id=$2 AND empresa_id=$3",
                pago_id, order_id, empresa_id)
        else:
            await conn.execute(
                "DELETE FROM finanzas2.cont_venta_pos_pago WHERE id=$1 AND venta_pos_id=$2",
                pago_id, order_id)
        return {"message": "Pago eliminado"}
