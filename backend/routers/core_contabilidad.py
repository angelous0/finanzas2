"""
CORE endpoints extraídos de contabilidad.py (Fase 3 cleanup).
Solo los 2 endpoints usados por CuentasBancarias, Gastos y FacturasProveedor.
Los 18 endpoints restantes quedan en contabilidad.py → legacy.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List
from database import get_pool
from models import CuentaContable
from dependencies import get_empresa_id
from contabilidad import generar_asiento_fprov, generar_asiento_gasto, generar_asiento_pago

router = APIRouter()


@router.get("/cuentas-contables", response_model=List[CuentaContable])
async def list_cuentas_contables(empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        rows = await conn.fetch("""
            SELECT * FROM finanzas2.cont_cuenta
            WHERE empresa_id = $1
            ORDER BY codigo
        """, empresa_id)
        return [dict(r) for r in rows]


@router.post("/asientos/generar")
async def generar_asientos(
    periodo: str = Query(...),
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        results = {"facturas": 0, "gastos": 0, "pagos": 0, "errors": []}
        try:
            year, month = periodo.split('-')
            year, month = int(year), int(month)
        except Exception:
            raise HTTPException(400, "Formato de periodo invalido. Use YYYY-MM")
        from datetime import date as d
        fecha_inicio = d(year, month, 1)
        if month == 12:
            fecha_fin = d(year + 1, 1, 1)
        else:
            fecha_fin = d(year, month + 1, 1)
        facturas = await conn.fetch("""
            SELECT id FROM finanzas2.cont_factura_proveedor
            WHERE empresa_id=$1 AND fecha_contable >= $2 AND fecha_contable < $3
        """, empresa_id, fecha_inicio, fecha_fin)
        for fp in facturas:
            try:
                await generar_asiento_fprov(conn, empresa_id, fp['id'])
                results['facturas'] += 1
            except Exception as e:
                results['errors'].append(f"Factura {fp['id']}: {str(e)}")
        gastos = await conn.fetch("""
            SELECT id FROM finanzas2.cont_gasto
            WHERE empresa_id=$1 AND fecha_contable >= $2 AND fecha_contable < $3
        """, empresa_id, fecha_inicio, fecha_fin)
        for g in gastos:
            try:
                await generar_asiento_gasto(conn, empresa_id, g['id'])
                results['gastos'] += 1
            except Exception as e:
                results['errors'].append(f"Gasto {g['id']}: {str(e)}")
        pagos = await conn.fetch("""
            SELECT id FROM finanzas2.cont_pago
            WHERE empresa_id=$1 AND fecha >= $2 AND fecha < $3
        """, empresa_id, fecha_inicio, fecha_fin)
        for p in pagos:
            try:
                await generar_asiento_pago(conn, empresa_id, p['id'])
                results['pagos'] += 1
            except Exception as e:
                results['errors'].append(f"Pago {p['id']}: {str(e)}")
        return results
