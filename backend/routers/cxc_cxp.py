from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Optional, List
from datetime import date, datetime
from database import get_pool
from dependencies import get_empresa_id
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Models ──

class AbonoCreate(BaseModel):
    fecha: date
    monto: float
    cuenta_financiera_id: Optional[int] = None
    forma_pago: Optional[str] = None
    referencia: Optional[str] = None
    notas: Optional[str] = None


class CxCManualCreate(BaseModel):
    cliente_id: Optional[int] = None
    tercero_nombre: Optional[str] = None
    monto_original: float
    fecha_vencimiento: Optional[date] = None
    tipo_origen: Optional[str] = 'manual'
    documento_referencia: Optional[str] = None
    marca_id: Optional[int] = None
    proyecto_id: Optional[int] = None
    notas: Optional[str] = None


class CxPManualCreate(BaseModel):
    proveedor_id: Optional[int] = None
    tercero_nombre: Optional[str] = None
    monto_original: float
    fecha_vencimiento: Optional[date] = None
    tipo_origen: Optional[str] = 'manual'
    documento_referencia: Optional[str] = None
    marca_id: Optional[int] = None
    proyecto_id: Optional[int] = None
    categoria_id: Optional[int] = None
    notas: Optional[str] = None


# ══════════════════════════════════════
# CXC (Cuentas por Cobrar)
# ══════════════════════════════════════

def _aging_bucket(dias):
    if dias is None or dias <= 0:
        return 'vigente'
    if dias <= 30:
        return '0_30'
    if dias <= 60:
        return '31_60'
    if dias <= 90:
        return '61_90'
    return '90_plus'


@router.get("/cxc")
async def list_cxc(
    estado: Optional[str] = None,
    aging: Optional[str] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        conditions = ["cxc.empresa_id = $1"]
        params: list = [empresa_id]
        idx = 2

        if estado:
            conditions.append(f"cxc.estado = ${idx}")
            params.append(estado)
            idx += 1

        if aging and aging != 'all':
            if aging == 'vigente':
                conditions.append("(cxc.fecha_vencimiento IS NULL OR cxc.fecha_vencimiento >= CURRENT_DATE)")
            elif aging == '0_30':
                conditions.append("cxc.fecha_vencimiento < CURRENT_DATE AND CURRENT_DATE - cxc.fecha_vencimiento <= 30")
            elif aging == '31_60':
                conditions.append("CURRENT_DATE - cxc.fecha_vencimiento BETWEEN 31 AND 60")
            elif aging == '61_90':
                conditions.append("CURRENT_DATE - cxc.fecha_vencimiento BETWEEN 61 AND 90")
            elif aging == '90_plus':
                conditions.append("CURRENT_DATE - cxc.fecha_vencimiento > 90")

        query = f"""
            SELECT cxc.id, cxc.empresa_id, cxc.venta_pos_id, cxc.cliente_id,
                   cxc.monto_original, cxc.saldo_pendiente, cxc.fecha_vencimiento,
                   cxc.estado, cxc.notas, cxc.created_at, cxc.updated_at,
                   cxc.tipo_origen, cxc.documento_referencia, cxc.odoo_order_id,
                   cxc.marca_id, cxc.linea_negocio_id, cxc.centro_costo_id, cxc.proyecto_id,
                   COALESCE(t.nombre, 'Sin Cliente') as cliente_nombre,
                   m.nombre as marca_nombre,
                   CASE
                       WHEN cxc.fecha_vencimiento IS NULL THEN NULL
                       WHEN cxc.fecha_vencimiento >= CURRENT_DATE THEN 0
                       ELSE CURRENT_DATE - cxc.fecha_vencimiento
                   END as dias_atraso,
                   COALESCE(
                       (SELECT SUM(a.monto) FROM cont_cxc_abono a WHERE a.cxc_id = cxc.id), 0
                   ) as total_abonado
            FROM cont_cxc cxc
            LEFT JOIN cont_tercero t ON cxc.cliente_id = t.id
            LEFT JOIN cont_marca m ON cxc.marca_id = m.id
            WHERE {' AND '.join(conditions)}
            ORDER BY
                CASE WHEN cxc.estado IN ('cobrada', 'anulada') THEN 1 ELSE 0 END,
                cxc.fecha_vencimiento ASC NULLS LAST
        """
        rows = await conn.fetch(query, *params)
        result = []
        for r in rows:
            d = dict(r)
            d['aging_bucket'] = _aging_bucket(d.get('dias_atraso'))
            result.append(d)
        return result


@router.get("/cxc/resumen")
async def cxc_resumen(empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        totals = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE estado NOT IN ('cobrada', 'anulada')) as total_docs,
                COALESCE(SUM(saldo_pendiente) FILTER (WHERE estado NOT IN ('cobrada', 'anulada')), 0) as total_pendiente,
                COALESCE(SUM(saldo_pendiente) FILTER (
                    WHERE estado NOT IN ('cobrada', 'anulada')
                    AND fecha_vencimiento < CURRENT_DATE
                ), 0) as total_vencido,
                COUNT(*) FILTER (
                    WHERE estado NOT IN ('cobrada', 'anulada')
                    AND fecha_vencimiento < CURRENT_DATE
                ) as docs_vencidos,
                COALESCE(SUM(saldo_pendiente) FILTER (
                    WHERE estado NOT IN ('cobrada', 'anulada')
                    AND fecha_vencimiento >= CURRENT_DATE AND fecha_vencimiento <= CURRENT_DATE + 7
                ), 0) as por_vencer_7d
            FROM cont_cxc
            WHERE empresa_id = $1
        """, empresa_id)

        aging = await conn.fetch("""
            SELECT
                CASE
                    WHEN fecha_vencimiento IS NULL OR fecha_vencimiento >= CURRENT_DATE THEN 'vigente'
                    WHEN CURRENT_DATE - fecha_vencimiento <= 30 THEN '0_30'
                    WHEN CURRENT_DATE - fecha_vencimiento <= 60 THEN '31_60'
                    WHEN CURRENT_DATE - fecha_vencimiento <= 90 THEN '61_90'
                    ELSE '90_plus'
                END as bucket,
                COUNT(*) as count,
                COALESCE(SUM(saldo_pendiente), 0) as total
            FROM cont_cxc
            WHERE empresa_id = $1 AND estado NOT IN ('cobrada', 'anulada')
            GROUP BY bucket
        """, empresa_id)

        aging_dict = {r['bucket']: {"count": int(r['count']), "total": float(r['total'])} for r in aging}
        for b in ['vigente', '0_30', '31_60', '61_90', '90_plus']:
            if b not in aging_dict:
                aging_dict[b] = {"count": 0, "total": 0}

        return {
            "total_docs": int(totals['total_docs'] or 0),
            "total_pendiente": float(totals['total_pendiente'] or 0),
            "total_vencido": float(totals['total_vencido'] or 0),
            "docs_vencidos": int(totals['docs_vencidos'] or 0),
            "por_vencer_7d": float(totals['por_vencer_7d'] or 0),
            "aging": aging_dict,
        }


@router.post("/cxc")
async def create_cxc(data: CxCManualCreate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        row = await conn.fetchrow("""
            INSERT INTO cont_cxc
                (empresa_id, cliente_id, monto_original, saldo_pendiente, fecha_vencimiento,
                 estado, tipo_origen, documento_referencia, marca_id, proyecto_id, notas)
            VALUES ($1, $2, $3, $3, $4, 'pendiente', $5, $6, $7, $8, $9)
            RETURNING id
        """, empresa_id, data.cliente_id, data.monto_original,
            data.fecha_vencimiento, data.tipo_origen, data.documento_referencia,
            data.marca_id, data.proyecto_id, data.notas)
        return {"id": row['id'], "message": "CxC creada"}


@router.get("/cxc/{cxc_id}/abonos")
async def list_cxc_abonos(cxc_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        rows = await conn.fetch("""
            SELECT a.*, cf.nombre as cuenta_nombre
            FROM cont_cxc_abono a
            LEFT JOIN cont_cuenta_financiera cf ON a.cuenta_financiera_id = cf.id
            WHERE a.cxc_id = $1 AND a.empresa_id = $2
            ORDER BY a.fecha DESC
        """, cxc_id, empresa_id)
        return [dict(r) for r in rows]


@router.post("/cxc/{cxc_id}/abonos")
async def create_cxc_abono(cxc_id: int, data: AbonoCreate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        cxc = await conn.fetchrow(
            "SELECT id, saldo_pendiente, estado, marca_id, linea_negocio_id, centro_costo_id, proyecto_id, odoo_order_id, venta_pos_id FROM cont_cxc WHERE id=$1 AND empresa_id=$2",
            cxc_id, empresa_id)
        if not cxc:
            raise HTTPException(404, "CxC no encontrada")
        if cxc['estado'] in ('cobrada', 'anulada'):
            raise HTTPException(400, f"CxC ya esta {cxc['estado']}")
        if data.monto <= 0:
            raise HTTPException(400, "El monto del abono debe ser positivo")
        if data.monto > float(cxc['saldo_pendiente']):
            raise HTTPException(400, f"El abono excede el saldo pendiente ({cxc['saldo_pendiente']})")

        async with conn.transaction():
            abono_row = await conn.fetchrow("""
                INSERT INTO cont_cxc_abono
                    (empresa_id, cxc_id, fecha, monto, cuenta_financiera_id, forma_pago, referencia, notas)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
            """, empresa_id, cxc_id, data.fecha, data.monto,
                data.cuenta_financiera_id, data.forma_pago, data.referencia, data.notas)

            new_saldo = float(cxc['saldo_pendiente']) - data.monto
            new_estado = 'cobrada' if new_saldo <= 0.01 else 'parcial'
            await conn.execute("""
                UPDATE cont_cxc SET saldo_pendiente = $1, estado = $2, updated_at = NOW()
                WHERE id = $3
            """, max(new_saldo, 0), new_estado, cxc_id)

            # CAPA TESORERIA: 1 movimiento REAL por el monto total cobrado
            from services.treasury_service import create_movimiento_tesoreria

            await create_movimiento_tesoreria(
                conn, empresa_id, data.fecha, 'ingreso', data.monto,
                cuenta_financiera_id=data.cuenta_financiera_id,
                forma_pago=data.forma_pago,
                referencia=data.referencia,
                concepto=f"Cobranza CxC #{cxc_id}",
                origen_tipo='cobranza_cxc',
                origen_id=abono_row['id'],
                marca_id=cxc['marca_id'],
                linea_negocio_id=cxc['linea_negocio_id'],
                centro_costo_id=cxc['centro_costo_id'],
                proyecto_id=cxc['proyecto_id'],
            )

            # CAPA PAGOS: cont_pago para que aparezca en Movimientos/Pagos
            moneda_id = await conn.fetchval(
                "SELECT id FROM cont_moneda WHERE codigo='PEN'")
            if not moneda_id:
                moneda_id = await conn.fetchval(
                    "SELECT id FROM cont_moneda ORDER BY id LIMIT 1")

            from dependencies import get_next_correlativo
            numero_pago = await get_next_correlativo(conn, empresa_id, 'pago_ingreso', f"PAG-I-{data.fecha.year}-")
            pago_result = await conn.fetchrow("""
                INSERT INTO cont_pago
                (numero, tipo, fecha, cuenta_financiera_id, moneda_id, monto_total,
                 referencia, notas, empresa_id)
                VALUES ($1, 'ingreso', $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
            """, numero_pago, data.fecha, data.cuenta_financiera_id,
                moneda_id, data.monto, data.referencia,
                f"Cobranza CxC #{cxc_id} - {data.notas or ''}", empresa_id)
            pago_id = pago_result['id']
            await conn.execute("""
                INSERT INTO cont_pago_detalle
                (pago_id, cuenta_financiera_id, medio_pago, monto, referencia, empresa_id)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, pago_id, data.cuenta_financiera_id, data.forma_pago,
                data.monto, data.referencia, empresa_id)

            # DISTRIBUCION ANALITICA: prorrateo por linea de negocio
            odoo_oid = cxc['odoo_order_id'] or cxc['venta_pos_id']
            if odoo_oid:
                from services.distribucion_analitica import crear_distribucion_cobro
                await crear_distribucion_cobro(
                    conn, empresa_id, odoo_oid,
                    abono_row['id'], data.monto, data.fecha)

        return {"message": "Abono registrado", "nuevo_saldo": max(new_saldo, 0), "nuevo_estado": new_estado}


# ══════════════════════════════════════
# CXP (Cuentas por Pagar)
# ══════════════════════════════════════

@router.get("/cxp")
async def list_cxp(
    estado: Optional[str] = None,
    aging: Optional[str] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        conditions = ["cxp.empresa_id = $1"]
        params: list = [empresa_id]
        idx = 2

        if estado:
            conditions.append(f"cxp.estado = ${idx}::finanzas2.estado_factura")
            params.append(estado)
            idx += 1

        if aging and aging != 'all':
            if aging == 'vigente':
                conditions.append("(cxp.fecha_vencimiento IS NULL OR cxp.fecha_vencimiento >= CURRENT_DATE)")
            elif aging == '0_30':
                conditions.append("cxp.fecha_vencimiento < CURRENT_DATE AND CURRENT_DATE - cxp.fecha_vencimiento <= 30")
            elif aging == '31_60':
                conditions.append("CURRENT_DATE - cxp.fecha_vencimiento BETWEEN 31 AND 60")
            elif aging == '61_90':
                conditions.append("CURRENT_DATE - cxp.fecha_vencimiento BETWEEN 61 AND 90")
            elif aging == '90_plus':
                conditions.append("CURRENT_DATE - cxp.fecha_vencimiento > 90")

        query = f"""
            SELECT cxp.id, cxp.empresa_id, cxp.factura_id, cxp.proveedor_id,
                   cxp.monto_original, cxp.saldo_pendiente, cxp.fecha_vencimiento,
                   cxp.estado::text as estado, cxp.created_at, cxp.updated_at,
                   cxp.tipo_origen, cxp.documento_referencia,
                   cxp.marca_id, cxp.linea_negocio_id, cxp.centro_costo_id,
                   cxp.proyecto_id, cxp.categoria_id,
                   COALESCE(t.nombre, 'Sin Proveedor') as proveedor_nombre,
                   fp.numero as factura_numero,
                   m.nombre as marca_nombre,
                   CASE
                       WHEN cxp.fecha_vencimiento IS NULL THEN NULL
                       WHEN cxp.fecha_vencimiento >= CURRENT_DATE THEN 0
                       ELSE CURRENT_DATE - cxp.fecha_vencimiento
                   END as dias_vencido,
                   COALESCE(
                       (SELECT SUM(a.monto) FROM cont_cxp_abono a WHERE a.cxp_id = cxp.id), 0
                   ) as total_abonado
            FROM cont_cxp cxp
            LEFT JOIN cont_tercero t ON cxp.proveedor_id = t.id
            LEFT JOIN cont_factura_proveedor fp ON cxp.factura_id = fp.id
            LEFT JOIN cont_marca m ON cxp.marca_id = m.id
            WHERE {' AND '.join(conditions)}
            ORDER BY
                CASE WHEN cxp.estado::text IN ('pagado', 'anulada') THEN 1 ELSE 0 END,
                cxp.fecha_vencimiento ASC NULLS LAST
        """
        rows = await conn.fetch(query, *params)
        result = []
        for r in rows:
            d = dict(r)
            d['aging_bucket'] = _aging_bucket(d.get('dias_vencido'))
            result.append(d)
        return result


@router.get("/cxp/resumen")
async def cxp_resumen(empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        totals = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE estado NOT IN ('pagado', 'anulada')) as total_docs,
                COALESCE(SUM(saldo_pendiente) FILTER (WHERE estado NOT IN ('pagado', 'anulada')), 0) as total_pendiente,
                COALESCE(SUM(saldo_pendiente) FILTER (
                    WHERE estado NOT IN ('pagado', 'anulada')
                    AND fecha_vencimiento < CURRENT_DATE
                ), 0) as total_vencido,
                COUNT(*) FILTER (
                    WHERE estado NOT IN ('pagado', 'anulada')
                    AND fecha_vencimiento < CURRENT_DATE
                ) as docs_vencidos,
                COALESCE(SUM(saldo_pendiente) FILTER (
                    WHERE estado NOT IN ('pagado', 'anulada')
                    AND fecha_vencimiento >= CURRENT_DATE AND fecha_vencimiento <= CURRENT_DATE + 7
                ), 0) as por_vencer_7d
            FROM cont_cxp
            WHERE empresa_id = $1
        """, empresa_id)

        aging = await conn.fetch("""
            SELECT
                CASE
                    WHEN fecha_vencimiento IS NULL OR fecha_vencimiento >= CURRENT_DATE THEN 'vigente'
                    WHEN CURRENT_DATE - fecha_vencimiento <= 30 THEN '0_30'
                    WHEN CURRENT_DATE - fecha_vencimiento <= 60 THEN '31_60'
                    WHEN CURRENT_DATE - fecha_vencimiento <= 90 THEN '61_90'
                    ELSE '90_plus'
                END as bucket,
                COUNT(*) as count,
                COALESCE(SUM(saldo_pendiente), 0) as total
            FROM cont_cxp
            WHERE empresa_id = $1 AND estado NOT IN ('pagado', 'anulada')
            GROUP BY bucket
        """, empresa_id)

        aging_dict = {r['bucket']: {"count": int(r['count']), "total": float(r['total'])} for r in aging}
        for b in ['vigente', '0_30', '31_60', '61_90', '90_plus']:
            if b not in aging_dict:
                aging_dict[b] = {"count": 0, "total": 0}

        return {
            "total_docs": int(totals['total_docs'] or 0),
            "total_pendiente": float(totals['total_pendiente'] or 0),
            "total_vencido": float(totals['total_vencido'] or 0),
            "docs_vencidos": int(totals['docs_vencidos'] or 0),
            "por_vencer_7d": float(totals['por_vencer_7d'] or 0),
            "aging": aging_dict,
        }


@router.post("/cxp")
async def create_cxp(data: CxPManualCreate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        row = await conn.fetchrow("""
            INSERT INTO cont_cxp
                (empresa_id, proveedor_id, monto_original, saldo_pendiente, fecha_vencimiento,
                 estado, tipo_origen, documento_referencia, marca_id, proyecto_id, categoria_id)
            VALUES ($1, $2, $3, $3, $4, 'pendiente', $5, $6, $7, $8, $9)
            RETURNING id
        """, empresa_id, data.proveedor_id, data.monto_original,
            data.fecha_vencimiento, data.tipo_origen, data.documento_referencia,
            data.marca_id, data.proyecto_id, data.categoria_id)
        return {"id": row['id'], "message": "CxP creada"}


@router.get("/cxp/{cxp_id}/abonos")
async def list_cxp_abonos(cxp_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        rows = await conn.fetch("""
            SELECT a.*, cf.nombre as cuenta_nombre
            FROM cont_cxp_abono a
            LEFT JOIN cont_cuenta_financiera cf ON a.cuenta_financiera_id = cf.id
            WHERE a.cxp_id = $1 AND a.empresa_id = $2
            ORDER BY a.fecha DESC
        """, cxp_id, empresa_id)
        return [dict(r) for r in rows]


@router.post("/cxp/{cxp_id}/abonos")
async def create_cxp_abono(cxp_id: int, data: AbonoCreate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        cxp = await conn.fetchrow(
            "SELECT id, saldo_pendiente, estado::text as estado, marca_id, linea_negocio_id, centro_costo_id, proyecto_id FROM cont_cxp WHERE id=$1 AND empresa_id=$2",
            cxp_id, empresa_id)
        if not cxp:
            raise HTTPException(404, "CxP no encontrada")
        if cxp['estado'] in ('pagado', 'anulada'):
            raise HTTPException(400, f"CxP ya esta {cxp['estado']}")
        if cxp['estado'] == 'canjeado':
            raise HTTPException(400, "Esta CxP fue canjeada por letras. Debe pagar las letras directamente.")
        if data.monto <= 0:
            raise HTTPException(400, "El monto del abono debe ser positivo")
        if data.monto > float(cxp['saldo_pendiente']):
            raise HTTPException(400, f"El abono excede el saldo pendiente ({cxp['saldo_pendiente']})")

        async with conn.transaction():
            abono_row = await conn.fetchrow("""
                INSERT INTO cont_cxp_abono
                    (empresa_id, cxp_id, fecha, monto, cuenta_financiera_id, forma_pago, referencia, notas)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
            """, empresa_id, cxp_id, data.fecha, data.monto,
                data.cuenta_financiera_id, data.forma_pago, data.referencia, data.notas)

            new_saldo = float(cxp['saldo_pendiente']) - data.monto
            new_estado = 'pagado' if new_saldo <= 0.01 else 'parcial'
            await conn.execute("""
                UPDATE cont_cxp SET saldo_pendiente = $1, estado = $2::finanzas2.estado_factura, updated_at = NOW()
                WHERE id = $3
            """, max(new_saldo, 0), new_estado, cxp_id)

            # CAPA TESORERIA: Pago real -> movimiento de tesoreria
            from services.treasury_service import create_movimiento_tesoreria
            await create_movimiento_tesoreria(
                conn, empresa_id, data.fecha, 'egreso', data.monto,
                cuenta_financiera_id=data.cuenta_financiera_id,
                forma_pago=data.forma_pago,
                referencia=data.referencia,
                concepto=f"Pago CxP #{cxp_id}",
                origen_tipo='pago_cxp',
                origen_id=abono_row['id'],
                marca_id=cxp['marca_id'],
                linea_negocio_id=cxp['linea_negocio_id'],
                centro_costo_id=cxp['centro_costo_id'],
                proyecto_id=cxp['proyecto_id'],
            )

        return {"message": "Abono registrado", "nuevo_saldo": max(new_saldo, 0), "nuevo_estado": new_estado}
