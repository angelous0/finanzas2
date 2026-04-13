from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from datetime import date, datetime
from database import get_pool
from models import CuentaContable, CuentaContableCreate
from dependencies import get_empresa_id, safe_date_param
from contabilidad import (
    generar_asiento_fprov, generar_asiento_gasto, generar_asiento_pago,
    reporte_mayor, reporte_balance, reporte_pnl
)

router = APIRouter()


# =====================
# CUENTAS CONTABLES
# =====================
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


@router.post("/cuentas-contables", response_model=CuentaContable)
async def create_cuenta_contable(data: CuentaContableCreate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        existing = await conn.fetchrow(
            "SELECT id FROM finanzas2.cont_cuenta WHERE codigo=$1 AND empresa_id=$2", data.codigo, empresa_id)
        if existing:
            raise HTTPException(400, f"Ya existe una cuenta con codigo {data.codigo}")
        row = await conn.fetchrow("""
            INSERT INTO finanzas2.cont_cuenta
            (codigo, nombre, tipo, es_activa, empresa_id)
            VALUES ($1,$2,$3,$4,$5) RETURNING *
        """, data.codigo, data.nombre, data.tipo, data.es_activa, empresa_id)
        return dict(row)


@router.put("/cuentas-contables/{id}", response_model=CuentaContable)
async def update_cuenta_contable(id: int, data: CuentaContableCreate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        row = await conn.fetchrow("""
            UPDATE finanzas2.cont_cuenta SET codigo=$1, nombre=$2, tipo=$3, es_activa=$4
            WHERE id=$5 AND empresa_id=$6 RETURNING *
        """, data.codigo, data.nombre, data.tipo, data.es_activa, id, empresa_id)
        if not row:
            raise HTTPException(404, "Cuenta no encontrada")
        return dict(row)


@router.delete("/cuentas-contables/{id}")
async def delete_cuenta_contable(id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        result = await conn.execute("DELETE FROM finanzas2.cont_cuenta WHERE id=$1 AND empresa_id=$2", id, empresa_id)
        if result == "DELETE 0":
            raise HTTPException(404, "Cuenta no encontrada")
        return {"message": "Cuenta eliminada"}


@router.post("/cuentas-contables/seed-peru")
async def seed_cuentas_peru(empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        existing = await conn.fetchval("SELECT COUNT(*) FROM finanzas2.cont_cuenta WHERE empresa_id=$1", empresa_id)
        if existing > 0:
            return {"message": f"Ya existen {existing} cuentas contables. No se re-sembraron."}
        # Plan Contable General Empresarial Peru - Cuentas principales
        PLAN_CONTABLE = [
            ('10', 'Efectivo y Equivalentes de Efectivo', 'activo'),
            ('101', 'Caja', 'activo'),
            ('104', 'Cuentas Corrientes', 'activo'),
            ('1041', 'Cuentas Corrientes Operativas', 'activo'),
            ('1042', 'Cuentas Corrientes - BBVA', 'activo'),
            ('1043', 'Cuentas Corrientes - IBK', 'activo'),
            ('12', 'Cuentas por Cobrar Comerciales', 'activo'),
            ('121', 'Facturas por Cobrar', 'activo'),
            ('40', 'Tributos por Pagar', 'pasivo'),
            ('4011', 'IGV - Cuenta Propia', 'impuesto'),
            ('4017', 'Impuesto a la Renta', 'impuesto'),
            ('42', 'Cuentas por Pagar Comerciales', 'pasivo'),
            ('421', 'Facturas por Pagar', 'pasivo'),
            ('46', 'Cuentas por Pagar Diversas', 'pasivo'),
            ('60', 'Compras', 'gasto'),
            ('601', 'Mercaderias', 'gasto'),
            ('602', 'Suministros', 'gasto'),
            ('63', 'Gastos de Servicios', 'gasto'),
            ('631', 'Transporte y Almacenamiento', 'gasto'),
            ('632', 'Comunicaciones', 'gasto'),
            ('634', 'Mantenimiento y Reparaciones', 'gasto'),
            ('636', 'Servicios Basicos', 'gasto'),
            ('639', 'Otros Servicios', 'gasto'),
            ('62', 'Gastos de Personal', 'gasto'),
            ('621', 'Remuneraciones', 'gasto'),
            ('627', 'Seguridad Social', 'gasto'),
            ('65', 'Otros Gastos de Gestion', 'gasto'),
            ('659', 'Otros Gastos Diversos', 'gasto'),
            ('70', 'Ventas', 'ingreso'),
            ('701', 'Mercaderias', 'ingreso'),
            ('75', 'Otros Ingresos de Gestion', 'ingreso'),
        ]
        inserted = 0
        for codigo, nombre, tipo in PLAN_CONTABLE:
            await conn.execute("""
                INSERT INTO finanzas2.cont_cuenta (codigo, nombre, tipo, es_activa, empresa_id)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (empresa_id, codigo) DO NOTHING
            """, codigo, nombre, tipo, True, empresa_id)
            inserted += 1
        return {"message": f"Plan contable Peru sembrado: {inserted} cuentas", "total": inserted}


# =====================
# CONFIG CONTABLE
# =====================
@router.get("/config-contable")
async def get_config_contable(empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        row = await conn.fetchrow("SELECT * FROM finanzas2.cont_config_empresa WHERE empresa_id=$1", empresa_id)
        if not row:
            return {"empresa_id": empresa_id, "cta_gastos_default_id": None, "cta_igv_default_id": None, "cta_xpagar_default_id": None, "cta_otrib_default_id": None}
        return dict(row)


@router.post("/config-contable")
async def save_config_contable(data: dict, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        existing = await conn.fetchrow("SELECT * FROM finanzas2.cont_config_empresa WHERE empresa_id=$1", empresa_id)
        if existing:
            await conn.execute("""
                UPDATE finanzas2.cont_config_empresa
                SET cta_gastos_default_id=$1, cta_igv_default_id=$2, cta_xpagar_default_id=$3, cta_otrib_default_id=$4
                WHERE empresa_id=$5
            """, data.get('cta_gastos_default_id'), data.get('cta_igv_default_id'),
                data.get('cta_xpagar_default_id'), data.get('cta_otrib_default_id'), empresa_id)
        else:
            await conn.execute("""
                INSERT INTO finanzas2.cont_config_empresa
                (empresa_id, cta_gastos_default_id, cta_igv_default_id, cta_xpagar_default_id, cta_otrib_default_id)
                VALUES ($1, $2, $3, $4, $5)
            """, empresa_id, data.get('cta_gastos_default_id'), data.get('cta_igv_default_id'),
                data.get('cta_xpagar_default_id'), data.get('cta_otrib_default_id'))
        return {"message": "Configuracion guardada"}


# =====================
# RETENCION DETALLE
# =====================
@router.get("/retencion-detalle")
async def get_retencion_detalle(
    origen_tipo: str = Query(...),
    origen_id: int = Query(...),
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        rows = await conn.fetch("""
            SELECT * FROM finanzas2.cont_retencion_detalle WHERE origen_tipo=$1 AND origen_id=$2 AND empresa_id=$3
        """, origen_tipo, origen_id, empresa_id)
        return [dict(r) for r in rows]


@router.post("/retencion-detalle")
async def create_or_update_retencion_detalle(data: dict, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        existing = await conn.fetchrow("""
            SELECT id FROM finanzas2.cont_retencion_detalle
            WHERE origen_tipo=$1 AND origen_id=$2 AND empresa_id=$3
        """, data.get('origen_tipo', 'factura'), data.get('origen_id') or data.get('factura_id'), empresa_id)
        origen_tipo = data.get('origen_tipo', 'factura')
        origen_id = data.get('origen_id') or data.get('factura_id')
        if existing:
            row = await conn.fetchrow("""
                UPDATE finanzas2.cont_retencion_detalle
                SET r_doc=$1, r_numero=$2, r_fecha=$3, d_numero=$4, d_fecha=$5,
                    retencion_01=$6, pdb_ndes=$7, codtasa=$8, ind_ret=$9, b_imp=$10, igv_ret=$11, updated_at=NOW()
                WHERE origen_tipo=$12 AND origen_id=$13 AND empresa_id=$14 RETURNING *
            """, data.get('r_doc'), data.get('r_numero'), data.get('r_fecha'),
                data.get('d_numero'), data.get('d_fecha'), data.get('retencion_01'),
                data.get('pdb_ndes'), data.get('codtasa'), data.get('ind_ret'),
                data.get('b_imp'), data.get('igv_ret'), origen_tipo, origen_id, empresa_id)
        else:
            row = await conn.fetchrow("""
                INSERT INTO finanzas2.cont_retencion_detalle
                (empresa_id, origen_tipo, origen_id, r_doc, r_numero, r_fecha, d_numero, d_fecha,
                 retencion_01, pdb_ndes, codtasa, ind_ret, b_imp, igv_ret)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14) RETURNING *
            """, empresa_id, origen_tipo, origen_id,
                data.get('r_doc'), data.get('r_numero'), data.get('r_fecha'),
                data.get('d_numero'), data.get('d_fecha'), data.get('retencion_01'),
                data.get('pdb_ndes'), data.get('codtasa'), data.get('ind_ret'),
                data.get('b_imp'), data.get('igv_ret'))
        return dict(row)


# =====================
# ASIENTOS CONTABLES
# =====================
@router.post("/asientos/generar")
async def generar_asientos(
    periodo: str = Query(...),
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        results = {"facturas": 0, "gastos": 0, "pagos": 0, "errors": []}
        # Parse periodo: YYYY-MM
        try:
            year, month = periodo.split('-')
            year, month = int(year), int(month)
        except:
            raise HTTPException(400, "Formato de periodo invalido. Use YYYY-MM")
        from datetime import date as d
        fecha_inicio = d(year, month, 1)
        if month == 12:
            fecha_fin = d(year + 1, 1, 1)
        else:
            fecha_fin = d(year, month + 1, 1)
        # Generate for facturas
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
        # Generate for gastos
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
        # Generate for pagos
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


@router.post("/asientos/{id}/postear")
async def postear_asiento(id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        asiento = await conn.fetchrow(
            "SELECT * FROM finanzas2.cont_asiento WHERE id=$1 AND empresa_id=$2", id, empresa_id)
        if not asiento:
            raise HTTPException(404, "Asiento no encontrado")
        if asiento['estado'] == 'posteado':
            raise HTTPException(400, "El asiento ya esta posteado")
        await conn.execute(
            "UPDATE finanzas2.cont_asiento SET estado='posteado', updated_at=NOW() WHERE id=$1", id)
        return {"message": "Asiento posteado"}


@router.post("/asientos/{id}/anular")
async def anular_asiento(id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        asiento = await conn.fetchrow(
            "SELECT * FROM finanzas2.cont_asiento WHERE id=$1 AND empresa_id=$2", id, empresa_id)
        if not asiento:
            raise HTTPException(404, "Asiento no encontrado")
        await conn.execute(
            "UPDATE finanzas2.cont_asiento SET estado='anulado', updated_at=NOW() WHERE id=$1", id)
        return {"message": "Asiento anulado"}


@router.get("/asientos")
async def list_asientos(
    periodo: Optional[str] = None,
    estado: Optional[str] = None,
    origen_tipo: Optional[str] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        conditions = ["a.empresa_id = $1"]
        params = [empresa_id]
        idx = 2
        if periodo:
            # Filter by periodo YYYY-MM via fecha_contable
            try:
                year, month = periodo.split('-')
                from datetime import date as d
                fecha_inicio = d(int(year), int(month), 1)
                if int(month) == 12:
                    fecha_fin = d(int(year) + 1, 1, 1)
                else:
                    fecha_fin = d(int(year), int(month) + 1, 1)
                conditions.append(f"a.fecha_contable >= ${idx}")
                params.append(fecha_inicio); idx += 1
                conditions.append(f"a.fecha_contable < ${idx}")
                params.append(fecha_fin); idx += 1
            except:
                pass
        if estado:
            conditions.append(f"a.estado = ${idx}"); params.append(estado); idx += 1
        if origen_tipo:
            conditions.append(f"a.origen_tipo = ${idx}"); params.append(origen_tipo); idx += 1
        query = f"""
            SELECT a.* FROM finanzas2.cont_asiento a
            WHERE {' AND '.join(conditions)} ORDER BY a.fecha_contable DESC, a.id DESC
        """
        rows = await conn.fetch(query, *params)
        result = []
        for row in rows:
            asiento = dict(row)
            lineas = await conn.fetch("""
                SELECT al.*, c.codigo as cuenta_codigo, c.nombre as cuenta_nombre
                FROM finanzas2.cont_asiento_linea al
                LEFT JOIN finanzas2.cont_cuenta c ON al.cuenta_id = c.id
                WHERE al.asiento_id = $1 ORDER BY al.id
            """, row['id'])
            asiento['lineas'] = [dict(l) for l in lineas]
            result.append(asiento)
        return result


@router.get("/asientos/{id}")
async def get_asiento(id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        row = await conn.fetchrow("SELECT * FROM finanzas2.cont_asiento WHERE id=$1 AND empresa_id=$2", id, empresa_id)
        if not row:
            raise HTTPException(404, "Asiento no encontrado")
        asiento = dict(row)
        lineas = await conn.fetch("""
            SELECT al.*, c.codigo as cuenta_codigo, c.nombre as cuenta_nombre
            FROM finanzas2.cont_asiento_linea al
            LEFT JOIN finanzas2.cont_cuenta c ON al.cuenta_id = c.id
            WHERE al.asiento_id = $1 ORDER BY al.id
        """, id)
        asiento['lineas'] = [dict(l) for l in lineas]
        return asiento


# =====================
# REPORTES CONTABLES
# =====================
@router.get("/reportes/libro-mayor")
async def reporte_libro_mayor(
    periodo: str = Query(...),
    cuenta_id: Optional[int] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        return await reporte_mayor(conn, empresa_id, cuenta_id, hasta=periodo)


@router.get("/reportes/balance-comprobacion")
async def reporte_balance_comprobacion(
    periodo: str = Query(...),
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        return await reporte_balance(conn, empresa_id, hasta=periodo)


@router.get("/reportes/estado-resultados-contable")
async def reporte_pnl_contable(
    periodo: str = Query(...),
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        return await reporte_pnl(conn, empresa_id, hasta=periodo)


# =====================
# PERIODOS CONTABLES
# =====================
@router.get("/periodos-contables")
async def list_periodos_contables(empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        rows = await conn.fetch("""
            SELECT * FROM finanzas2.cont_periodo_cerrado WHERE empresa_id=$1 ORDER BY anio DESC, mes DESC
        """, empresa_id)
        return [dict(r) for r in rows]


@router.post("/periodos-contables/{anio}/{mes}/abrir")
async def abrir_periodo(anio: int, mes: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        existing = await conn.fetchrow(
            "SELECT * FROM finanzas2.cont_periodo_cerrado WHERE anio=$1 AND mes=$2 AND empresa_id=$3", anio, mes, empresa_id)
        if existing:
            if not existing['cerrado']:
                return {"message": f"Periodo {anio}-{mes:02d} ya esta abierto"}
            await conn.execute(
                "UPDATE finanzas2.cont_periodo_cerrado SET cerrado=FALSE, cerrado_por=NULL, cerrado_at=NULL WHERE id=$1", existing['id'])
        else:
            await conn.execute("""
                INSERT INTO finanzas2.cont_periodo_cerrado (anio, mes, cerrado, empresa_id) VALUES ($1, $2, FALSE, $3)
            """, anio, mes, empresa_id)
        return {"message": f"Periodo {anio}-{mes:02d} abierto"}


@router.post("/periodos-contables/{anio}/{mes}/cerrar")
async def cerrar_periodo(anio: int, mes: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        existing = await conn.fetchrow(
            "SELECT * FROM finanzas2.cont_periodo_cerrado WHERE anio=$1 AND mes=$2 AND empresa_id=$3", anio, mes, empresa_id)
        if not existing:
            await conn.execute("""
                INSERT INTO finanzas2.cont_periodo_cerrado (anio, mes, cerrado, cerrado_at, empresa_id)
                VALUES ($1, $2, TRUE, NOW(), $3)
            """, anio, mes, empresa_id)
        else:
            await conn.execute(
                "UPDATE finanzas2.cont_periodo_cerrado SET cerrado=TRUE, cerrado_at=NOW() WHERE id=$1", existing['id'])
        return {"message": f"Periodo {anio}-{mes:02d} cerrado"}
