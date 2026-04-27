from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from datetime import date, datetime, timedelta
from database import get_pool
from models import OC, OCCreate, OCUpdate, FacturaProveedor, FacturaProveedorCreate, FacturaProveedorUpdate
from dependencies import get_empresa_id, get_next_correlativo, safe_date_param
from services.distribucion_service import recalcular_distribuciones_factura
import logging
import re

logger = logging.getLogger(__name__)

router = APIRouter()


def normalize_factura_numero(numero: str) -> str:
    """Normalize FC-NNN (any digit count) to FC-NNNN (4 digits)."""
    if not numero:
        return numero
    m = re.match(r'^(FC-)(\d+)$', numero.strip().upper())
    if m:
        prefix, digits = m.groups()
        return f"{prefix}{int(digits):04d}"
    return numero


@router.get("/servicios-produccion")
async def get_servicios_produccion(empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, nombre, descripcion, tarifa, orden
            FROM produccion.prod_servicios_produccion
            ORDER BY orden, nombre
        """)
        return [dict(r) for r in rows]



async def generate_oc_number(conn, empresa_id: int) -> str:
    year = datetime.now().year
    prefijo = f"OC-{year}-"
    return await get_next_correlativo(conn, empresa_id, 'oc', prefijo)


async def generate_factura_number(conn, empresa_id: int) -> str:
    year = datetime.now().year
    prefijo = f"FP-{year}-"
    return await get_next_correlativo(conn, empresa_id, 'factura_proveedor', prefijo)


async def get_factura_proveedor(id: int, empresa_id: int) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        row = await conn.fetchrow("""
            SELECT fp.*, t.nombre as proveedor_nombre, m.codigo as moneda_codigo, m.simbolo as moneda_simbolo
            FROM finanzas2.cont_factura_proveedor fp
            LEFT JOIN finanzas2.cont_tercero t ON fp.proveedor_id = t.id
            LEFT JOIN finanzas2.cont_moneda m ON fp.moneda_id = m.id
            WHERE fp.id = $1 AND fp.empresa_id = $2
        """, id, empresa_id)
        if not row:
            raise HTTPException(404, "Factura not found")
        fp_dict = dict(row)
        lineas = await conn.fetch("""
            SELECT fpl.*, c.nombre as categoria_nombre, c.padre_id as categoria_padre_id,
                   cp.nombre as categoria_padre_nombre,
                   ln.nombre as linea_negocio_nombre, cc.nombre as centro_costo_nombre,
                   ui.nombre as unidad_interna_nombre
            FROM finanzas2.cont_factura_proveedor_linea fpl
            LEFT JOIN finanzas2.cont_categoria c ON fpl.categoria_id = c.id
            LEFT JOIN finanzas2.cont_categoria cp ON c.padre_id = cp.id
            LEFT JOIN finanzas2.cont_linea_negocio ln ON fpl.linea_negocio_id = ln.id
            LEFT JOIN finanzas2.cont_centro_costo cc ON fpl.centro_costo_id = cc.id
            LEFT JOIN finanzas2.fin_unidad_interna ui ON fpl.unidad_interna_id = ui.id
            WHERE fpl.factura_id = $1 ORDER BY fpl.id
        """, id)
        fp_dict['lineas'] = [dict(l) for l in lineas]
        return fp_dict


# =====================
# ORDENES DE COMPRA
# =====================
@router.get("/ordenes-compra", response_model=List[OC])
async def list_ordenes_compra(
    estado: Optional[str] = None,
    proveedor_id: Optional[int] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        conditions = ["oc.empresa_id = $1"]
        params = [empresa_id]
        idx = 2
        if estado:
            conditions.append(f"oc.estado = ${idx}"); params.append(estado); idx += 1
        if proveedor_id:
            conditions.append(f"oc.proveedor_id = ${idx}"); params.append(proveedor_id); idx += 1
        if fecha_desde:
            conditions.append(f"oc.fecha >= ${idx}"); params.append(fecha_desde); idx += 1
        if fecha_hasta:
            conditions.append(f"oc.fecha <= ${idx}"); params.append(fecha_hasta); idx += 1
        query = f"""
            SELECT oc.*, t.nombre as proveedor_nombre, m.codigo as moneda_codigo
            FROM finanzas2.cont_oc oc
            LEFT JOIN finanzas2.cont_tercero t ON oc.proveedor_id = t.id
            LEFT JOIN finanzas2.cont_moneda m ON oc.moneda_id = m.id
            WHERE {' AND '.join(conditions)}
            ORDER BY oc.fecha DESC, oc.id DESC
        """
        rows = await conn.fetch(query, *params)
        result = []
        for row in rows:
            oc_dict = dict(row)
            lineas = await conn.fetch("SELECT * FROM finanzas2.cont_oc_linea WHERE oc_id = $1 ORDER BY id", row['id'])
            oc_dict['lineas'] = [dict(l) for l in lineas]
            result.append(oc_dict)
        return result


@router.get("/ordenes-compra/{id}", response_model=OC)
async def get_orden_compra(id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        row = await conn.fetchrow("""
            SELECT oc.*, t.nombre as proveedor_nombre, m.codigo as moneda_codigo
            FROM finanzas2.cont_oc oc
            LEFT JOIN finanzas2.cont_tercero t ON oc.proveedor_id = t.id
            LEFT JOIN finanzas2.cont_moneda m ON oc.moneda_id = m.id
            WHERE oc.id = $1 AND oc.empresa_id = $2
        """, id, empresa_id)
        if not row:
            raise HTTPException(404, "Orden de compra not found")
        oc_dict = dict(row)
        lineas = await conn.fetch("SELECT * FROM finanzas2.cont_oc_linea WHERE oc_id = $1 ORDER BY id", id)
        oc_dict['lineas'] = [dict(l) for l in lineas]
        return oc_dict


@router.post("/ordenes-compra", response_model=OC)
async def create_orden_compra(data: OCCreate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        async with conn.transaction():
            numero = await generate_oc_number(conn, empresa_id)
            subtotal = 0
            igv = 0
            for linea in data.lineas:
                if data.igv_incluido and linea.igv_aplica:
                    base = linea.cantidad * linea.precio_unitario / 1.18
                    linea_igv = linea.cantidad * linea.precio_unitario - base
                    subtotal += base
                    igv += linea_igv
                else:
                    linea_subtotal = linea.cantidad * linea.precio_unitario
                    subtotal += linea_subtotal
                    if linea.igv_aplica:
                        igv += linea_subtotal * 0.18
            total = subtotal + igv
            row = await conn.fetchrow("""
                INSERT INTO finanzas2.cont_oc
                (empresa_id, numero, fecha, proveedor_id, moneda_id, estado, subtotal, igv, total, notas)
                VALUES ($1, $2, $3, $4, $5, 'borrador', $6, $7, $8, $9)
                RETURNING *
            """, empresa_id, numero, data.fecha, data.proveedor_id, data.moneda_id, subtotal, igv, total, data.notas)
            oc_id = row['id']
            for linea in data.lineas:
                if data.igv_incluido and linea.igv_aplica:
                    linea_subtotal = linea.cantidad * linea.precio_unitario / 1.18
                else:
                    linea_subtotal = linea.cantidad * linea.precio_unitario
                await conn.execute("""
                    INSERT INTO finanzas2.cont_oc_linea
                    (empresa_id, oc_id, articulo_id, descripcion, cantidad, precio_unitario, igv_aplica, subtotal)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """, empresa_id, oc_id, linea.articulo_id or None, linea.descripcion, linea.cantidad,
                    linea.precio_unitario, linea.igv_aplica, linea_subtotal)
            oc_row = await conn.fetchrow("""
                SELECT oc.*, t.nombre as proveedor_nombre, m.codigo as moneda_codigo
                FROM finanzas2.cont_oc oc
                LEFT JOIN finanzas2.cont_tercero t ON oc.proveedor_id = t.id
                LEFT JOIN finanzas2.cont_moneda m ON oc.moneda_id = m.id
                WHERE oc.id = $1
            """, oc_id)
            oc_dict = dict(oc_row)
            lineas_rows = await conn.fetch("SELECT * FROM finanzas2.cont_oc_linea WHERE oc_id = $1 ORDER BY id", oc_id)
            oc_dict['lineas'] = [dict(l) for l in lineas_rows]
            return oc_dict


@router.put("/ordenes-compra/{id}", response_model=OC)
async def update_orden_compra(id: int, data: OCUpdate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        oc = await conn.fetchrow("SELECT * FROM finanzas2.cont_oc WHERE id = $1 AND empresa_id = $2", id, empresa_id)
        if not oc:
            raise HTTPException(404, "Orden de compra not found")
        if oc['estado'] != 'borrador':
            raise HTTPException(400, "Solo se pueden editar órdenes en estado borrador")

        async with conn.transaction():
            data_dict = data.model_dump(exclude_unset=True)
            lineas_data = data_dict.pop('lineas', None)
            igv_incluido = data_dict.pop('igv_incluido', None)

            # Update header fields
            updates = []
            values = []
            idx = 1
            for field, value in data_dict.items():
                updates.append(f"{field} = ${idx}"); values.append(value); idx += 1

            if updates:
                values.append(id)
                query = f"UPDATE finanzas2.cont_oc SET {', '.join(updates)}, updated_at = NOW() WHERE id = ${idx}"
                await conn.execute(query, *values)

            # Replace lines if provided
            if lineas_data is not None:
                await conn.execute("DELETE FROM finanzas2.cont_oc_linea WHERE oc_id = $1", id)
                use_igv_incluido = igv_incluido if igv_incluido is not None else False
                subtotal = 0
                igv = 0
                for linea in lineas_data:
                    if use_igv_incluido and linea.get('igv_aplica', True):
                        base = linea['cantidad'] * linea['precio_unitario'] / 1.18
                        linea_igv = linea['cantidad'] * linea['precio_unitario'] - base
                        subtotal += base
                        igv += linea_igv
                        linea_subtotal = base
                    else:
                        linea_subtotal = linea['cantidad'] * linea['precio_unitario']
                        subtotal += linea_subtotal
                        if linea.get('igv_aplica', True):
                            igv += linea_subtotal * 0.18
                    articulo_id_value = linea.get('articulo_id') or None
                    await conn.execute("""
                        INSERT INTO finanzas2.cont_oc_linea
                        (empresa_id, oc_id, articulo_id, descripcion, cantidad, precio_unitario, igv_aplica, subtotal)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """, empresa_id, id, articulo_id_value, linea.get('descripcion'),
                        linea['cantidad'], linea['precio_unitario'], linea.get('igv_aplica', True), linea_subtotal)
                total = subtotal + igv
                await conn.execute("""
                    UPDATE finanzas2.cont_oc SET subtotal = $1, igv = $2, total = $3, updated_at = NOW() WHERE id = $4
                """, subtotal, igv, total, id)

        return await get_orden_compra(id, empresa_id)


@router.delete("/ordenes-compra/{id}")
async def delete_orden_compra(id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        oc = await conn.fetchrow("SELECT * FROM finanzas2.cont_oc WHERE id = $1 AND empresa_id = $2", id, empresa_id)
        if not oc:
            raise HTTPException(404, "Orden de compra not found")
        if oc['factura_generada_id']:
            raise HTTPException(400, "Cannot delete OC that has generated a factura")
        await conn.execute("DELETE FROM finanzas2.cont_oc WHERE id = $1 AND empresa_id = $2", id, empresa_id)
        return {"message": "Orden de compra deleted"}


@router.post("/ordenes-compra/{id}/generar-factura", response_model=FacturaProveedor)
async def generar_factura_desde_oc(id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        async with conn.transaction():
            oc = await conn.fetchrow("SELECT * FROM finanzas2.cont_oc WHERE id = $1", id)
            if not oc:
                raise HTTPException(404, "Orden de compra not found")
            if oc['factura_generada_id']:
                raise HTTPException(400, "Esta OC ya genero una factura")
            year = datetime.now().year
            prefix = f"FP-{year}-"
            last = await conn.fetchval(f"""
                SELECT numero FROM finanzas2.cont_factura_proveedor
                WHERE numero LIKE '{prefix}%' ORDER BY id DESC LIMIT 1
            """)
            if last:
                num = int(last.split('-')[-1]) + 1
            else:
                num = 1
            numero = f"{prefix}{num:05d}"
            factura = await conn.fetchrow("""
                INSERT INTO finanzas2.cont_factura_proveedor
                (empresa_id, numero, proveedor_id, moneda_id, fecha_factura, fecha_vencimiento,
                 terminos_dias, tipo_documento, estado, subtotal, igv, total, saldo_pendiente,
                 notas, oc_origen_id)
                VALUES ($1, $2, $3, $4, TO_DATE($5, 'YYYY-MM-DD'), TO_DATE($6, 'YYYY-MM-DD'), $7, 'factura', 'pendiente', $8, $9, $10, $10, $11, $12)
                RETURNING *
            """, empresa_id, numero, oc['proveedor_id'], oc['moneda_id'], safe_date_param(datetime.now().date()),
                safe_date_param(datetime.now().date() + timedelta(days=30)), 30,
                oc['subtotal'], oc['igv'], oc['total'], oc['notas'], id)
            factura_id = factura['id']
            oc_lineas = await conn.fetch("SELECT * FROM finanzas2.cont_oc_linea WHERE oc_id = $1", id)
            for linea in oc_lineas:
                await conn.execute("""
                    INSERT INTO finanzas2.cont_factura_proveedor_linea
                    (empresa_id, factura_id, articulo_id, descripcion, importe, igv_aplica)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, empresa_id, factura_id, linea['articulo_id'], linea['descripcion'],
                    linea['subtotal'], linea['igv_aplica'])
            await conn.execute("""
                INSERT INTO finanzas2.cont_cxp
                (empresa_id, factura_id, proveedor_id, monto_original, saldo_pendiente, fecha_vencimiento, estado)
                VALUES ($1, $2, $3, $4, $4, $5, 'pendiente')
            """, empresa_id, factura_id, oc['proveedor_id'], oc['total'],
                datetime.now().date() + timedelta(days=30))
            await conn.execute("""
                UPDATE finanzas2.cont_oc SET estado = 'facturada', factura_generada_id = $1 WHERE id = $2 AND empresa_id = $3
            """, factura_id, id, empresa_id)
            f_row = await conn.fetchrow("""
                SELECT fp.*, t.nombre as proveedor_nombre, m.codigo as moneda_codigo, m.simbolo as moneda_simbolo
                FROM finanzas2.cont_factura_proveedor fp
                LEFT JOIN finanzas2.cont_tercero t ON fp.proveedor_id = t.id
                LEFT JOIN finanzas2.cont_moneda m ON fp.moneda_id = m.id
                WHERE fp.id = $1
            """, factura_id)
            factura_dict = dict(f_row)
            f_lineas = await conn.fetch("""
                SELECT fpl.*, c.nombre as categoria_nombre
                FROM finanzas2.cont_factura_proveedor_linea fpl
                LEFT JOIN finanzas2.cont_categoria c ON fpl.categoria_id = c.id
                WHERE fpl.factura_id = $1 ORDER BY fpl.id
            """, factura_id)
            factura_dict['lineas'] = [dict(l) for l in f_lineas]
            return factura_dict


# =====================
# FACTURAS PROVEEDOR
# =====================
@router.get("/facturas-proveedor")
async def list_facturas_proveedor(
    estado: Optional[str] = None,
    proveedor_id: Optional[int] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        conditions = ["fp.empresa_id = $1"]
        params = [empresa_id]
        idx = 2
        if estado:
            conditions.append(f"fp.estado = ${idx}"); params.append(estado); idx += 1
        if proveedor_id:
            conditions.append(f"fp.proveedor_id = ${idx}"); params.append(proveedor_id); idx += 1
        if fecha_desde:
            conditions.append(f"fp.fecha_factura >= ${idx}"); params.append(fecha_desde); idx += 1
        if fecha_hasta:
            conditions.append(f"fp.fecha_factura <= ${idx}"); params.append(fecha_hasta); idx += 1
        query = f"""
            SELECT fp.*, t.nombre as proveedor_nombre, m.codigo as moneda_codigo, m.simbolo as moneda_simbolo,
                   ui.nombre as unidad_interna_nombre
            FROM finanzas2.cont_factura_proveedor fp
            LEFT JOIN finanzas2.cont_tercero t ON fp.proveedor_id = t.id
            LEFT JOIN finanzas2.cont_moneda m ON fp.moneda_id = m.id
            LEFT JOIN finanzas2.fin_unidad_interna ui ON fp.unidad_interna_id = ui.id
            WHERE {' AND '.join(conditions)}
            ORDER BY fp.fecha_factura DESC, fp.id DESC
        """
        rows = await conn.fetch(query, *params)
        result = []
        for row in rows:
            fp_dict = {k: (v.isoformat() if isinstance(v, (date, datetime)) else (float(v) if isinstance(v, __import__('decimal').Decimal) else v)) for k, v in dict(row).items()}
            lineas = await conn.fetch("""
                SELECT fpl.*, c.nombre as categoria_nombre, c.padre_id as categoria_padre_id,
                       cp.nombre as categoria_padre_nombre,
                       ln.nombre as linea_negocio_nombre, cc.nombre as centro_costo_nombre
                FROM finanzas2.cont_factura_proveedor_linea fpl
                LEFT JOIN finanzas2.cont_categoria c ON fpl.categoria_id = c.id
                LEFT JOIN finanzas2.cont_categoria cp ON c.padre_id = cp.id
                LEFT JOIN finanzas2.cont_linea_negocio ln ON fpl.linea_negocio_id = ln.id
                LEFT JOIN finanzas2.cont_centro_costo cc ON fpl.centro_costo_id = cc.id
                WHERE fpl.factura_id = $1 ORDER BY fpl.id
            """, row['id'])
            fp_dict['lineas'] = [{k: (v.isoformat() if isinstance(v, (date, datetime)) else (float(v) if isinstance(v, __import__('decimal').Decimal) else v)) for k, v in dict(l).items()} for l in lineas]
            # Add vinculacion summary
            vinc_summary = await conn.fetch("""
                SELECT factura_linea_id, SUM(cantidad_aplicada) as total_vinculado
                FROM finanzas2.cont_factura_ingreso_mp
                WHERE factura_id = $1
                GROUP BY factura_linea_id
            """, row['id'])
            vinc_map = {v['factura_linea_id']: float(v['total_vinculado']) for v in vinc_summary}
            has_art_lines = False
            total_art_cant = 0
            total_vinculado = 0
            for l in fp_dict['lineas']:
                if l.get('articulo_id'):
                    has_art_lines = True
                    cant = float(l.get('cantidad') or 0)
                    total_art_cant += cant
                    vinc = vinc_map.get(l['id'], 0)
                    total_vinculado += vinc
                    l['cantidad_vinculada'] = vinc
            fp_dict['vinculacion_resumen'] = {
                'tiene_articulos': has_art_lines,
                'total_cantidad': total_art_cant,
                'total_vinculado': total_vinculado,
                'estado': 'completo' if has_art_lines and total_art_cant > 0 and total_vinculado >= total_art_cant else ('parcial' if total_vinculado > 0 else ('pendiente' if has_art_lines else 'na'))
            }
            # Resumen de letras: cuánto se ha pagado de las letras y cuánto está pendiente
            letras_agg = await conn.fetchrow("""
                SELECT
                    COALESCE(SUM(monto), 0)::numeric AS total,
                    COALESCE(SUM(monto - COALESCE(saldo_pendiente, monto)), 0)::numeric AS pagado,
                    COALESCE(SUM(saldo_pendiente), 0)::numeric AS pendiente,
                    COUNT(*) AS cantidad
                  FROM finanzas2.cont_letra
                 WHERE factura_id = $1
            """, row['id'])
            fp_dict['letras_resumen'] = {
                'total': float(letras_agg['total'] or 0),
                'pagado': float(letras_agg['pagado'] or 0),
                'pendiente': float(letras_agg['pendiente'] or 0),
                'cantidad': int(letras_agg['cantidad'] or 0),
            }
            result.append(fp_dict)
        return result


@router.get("/facturas-proveedor/{id}", response_model=FacturaProveedor)
async def get_factura_proveedor_endpoint(id: int, empresa_id: int = Depends(get_empresa_id)):
    return await get_factura_proveedor(id, empresa_id)


@router.post("/facturas-proveedor", response_model=FacturaProveedor)
async def create_factura_proveedor(data: FacturaProveedorCreate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        async with conn.transaction():
            numero = normalize_factura_numero(data.numero) if data.numero else await generate_factura_number(conn, empresa_id)
            if data.numero:
                exists = await conn.fetchval(
                    "SELECT 1 FROM finanzas2.cont_factura_proveedor WHERE numero = $1 AND empresa_id = $2",
                    numero, empresa_id)
                if exists:
                    raise HTTPException(400, f"Ya existe una factura con el número '{numero}'")

            subtotal = sum(l.importe for l in data.lineas)
            if data.impuestos_incluidos:
                subtotal = subtotal / 1.18
                igv = subtotal * 0.18
            else:
                igv = sum(l.importe * 0.18 for l in data.lineas if l.igv_aplica)
            total = subtotal + igv
            base_gravada = 0.0
            igv_sunat = 0.0
            base_no_gravada = 0.0
            for linea in data.lineas:
                imp = linea.importe
                if linea.igv_aplica:
                    if data.impuestos_incluidos:
                        base = imp / 1.18
                        base_gravada += base
                        igv_sunat += imp - base
                    else:
                        base_gravada += imp
                        igv_sunat += imp * 0.18
                else:
                    base_no_gravada += imp
            base_gravada = round(base_gravada, 2)
            igv_sunat = round(igv_sunat, 2)
            base_no_gravada = round(base_no_gravada, 2)
            isc_val = data.isc or 0.0
            fecha_vencimiento = data.fecha_vencimiento
            if not fecha_vencimiento and data.terminos_dias:
                fecha_vencimiento = data.fecha_factura + timedelta(days=data.terminos_dias)
            fecha_contable = data.fecha_contable or data.fecha_factura
            row = await conn.fetchrow("""
                INSERT INTO finanzas2.cont_factura_proveedor
                (empresa_id, numero, proveedor_id, beneficiario_nombre, moneda_id, fecha_factura, fecha_contable, fecha_vencimiento,
                 terminos_dias, tipo_documento, estado, subtotal, igv, total, saldo_pendiente,
                 impuestos_incluidos, tipo_comprobante_sunat, base_gravada, igv_sunat, base_no_gravada, isc, tipo_cambio, notas)
                VALUES ($1, $2, $3, $4, $5, TO_DATE($6, 'YYYY-MM-DD'), TO_DATE($7, 'YYYY-MM-DD'), TO_DATE($8, 'YYYY-MM-DD'), $9, $10, 'pendiente', $11, $12, $13, $13, $14, $15, $16, $17, $18, $19, $20, $21)
                RETURNING id
            """, empresa_id, numero, data.proveedor_id, data.beneficiario_nombre, data.moneda_id,
                safe_date_param(data.fecha_factura), safe_date_param(fecha_contable), safe_date_param(fecha_vencimiento), data.terminos_dias, data.tipo_documento,
                subtotal, igv, total, data.impuestos_incluidos, data.tipo_comprobante_sunat, base_gravada, igv_sunat, base_no_gravada, isc_val, data.tipo_cambio, data.notas)
            factura_id = row['id']
            for linea in data.lineas:
                await conn.execute("""
                    INSERT INTO finanzas2.cont_factura_proveedor_linea
                    (empresa_id, factura_id, categoria_id, articulo_id, servicio_id, servicio_detalle, tipo_linea, descripcion, linea_negocio_id,
                     centro_costo_id, importe, igv_aplica, cantidad, precio_unitario, modelo_corte_id, unidad_interna_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                """, empresa_id, factura_id, linea.categoria_id, linea.articulo_id, linea.servicio_id, linea.servicio_detalle, linea.tipo_linea,
                    linea.descripcion, linea.linea_negocio_id, linea.centro_costo_id, linea.importe, linea.igv_aplica,
                    linea.cantidad, linea.precio_unitario, linea.modelo_corte_id, linea.unidad_interna_id)
            await conn.execute("""
                INSERT INTO finanzas2.cont_cxp
                (empresa_id, factura_id, proveedor_id, monto_original, saldo_pendiente, fecha_vencimiento, estado)
                VALUES ($1, $2, $3, $4, $4, $5, 'pendiente')
            """, empresa_id, factura_id, data.proveedor_id, total, fecha_vencimiento)
            row = await conn.fetchrow("""
                SELECT fp.*, t.nombre as proveedor_nombre, m.codigo as moneda_codigo, m.simbolo as moneda_simbolo
                FROM finanzas2.cont_factura_proveedor fp
                LEFT JOIN finanzas2.cont_tercero t ON fp.proveedor_id = t.id
                LEFT JOIN finanzas2.cont_moneda m ON fp.moneda_id = m.id
                WHERE fp.id = $1
            """, factura_id)
            if not row:
                raise HTTPException(404, "Factura not found after creation")
            fp_dict = dict(row)
            lineas = await conn.fetch("""
                SELECT fpl.*, c.nombre as categoria_nombre, c.padre_id as categoria_padre_id,
                       cp.nombre as categoria_padre_nombre,
                       ln.nombre as linea_negocio_nombre, cc.nombre as centro_costo_nombre,
                       ui.nombre as unidad_interna_nombre
                FROM finanzas2.cont_factura_proveedor_linea fpl
                LEFT JOIN finanzas2.cont_categoria c ON fpl.categoria_id = c.id
                LEFT JOIN finanzas2.cont_categoria cp ON c.padre_id = cp.id
                LEFT JOIN finanzas2.cont_linea_negocio ln ON fpl.linea_negocio_id = ln.id
                LEFT JOIN finanzas2.cont_centro_costo cc ON fpl.centro_costo_id = cc.id
                LEFT JOIN finanzas2.fin_unidad_interna ui ON fpl.unidad_interna_id = ui.id
                WHERE fpl.factura_id = $1 ORDER BY fpl.id
            """, factura_id)
            fp_dict['lineas'] = [dict(l) for l in lineas]
            return fp_dict


@router.put("/facturas-proveedor/{id}", response_model=FacturaProveedor)
async def update_factura_proveedor(id: int, data: FacturaProveedorUpdate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        factura = await conn.fetchrow("SELECT * FROM finanzas2.cont_factura_proveedor WHERE id = $1 AND empresa_id = $2", id, empresa_id)
        if not factura:
            raise HTTPException(404, "Factura not found")
        if factura['estado'] == 'anulada':
            raise HTTPException(400, "No se puede editar una factura anulada")

        is_locked = factura['estado'] in ('pagado', 'canjeado')
        es_nota_interna = (factura['tipo_documento'] == 'nota_interna')
        CLASSIFICATION_FIELDS = {'notas', 'fecha_contable', 'tipo_comprobante_sunat'}

        data_dict = data.model_dump(exclude_unset=True)
        lineas_data = data_dict.pop('lineas', None)

        updates = []
        values = []
        idx = 1
        for field, value in data_dict.items():
            if is_locked and field not in CLASSIFICATION_FIELDS:
                continue
            updates.append(f"{field} = ${idx}"); values.append(value); idx += 1

        if updates:
            values.append(id)
            query = f"UPDATE finanzas2.cont_factura_proveedor SET {', '.join(updates)}, updated_at = NOW() WHERE id = ${idx}"
            await conn.execute(query, *values)

        # Para propagación NI: guardamos snapshot de líneas viejas ANTES del UPDATE
        lineas_viejas_map = {}
        if es_nota_interna and lineas_data is not None:
            lineas_viejas = await conn.fetch("""
                SELECT id, servicio_id, modelo_corte_id, cantidad, precio_unitario, importe
                FROM finanzas2.cont_factura_proveedor_linea
                WHERE factura_id = $1
            """, id)
            lineas_viejas_map = {l['id']: dict(l) for l in lineas_viejas}

        if lineas_data is not None:
            LINEA_CLASS_FIELDS = {'categoria_id', 'descripcion', 'linea_negocio_id', 'centro_costo_id', 'unidad_interna_id'}
            LINEA_ALL_FIELDS = {'categoria_id', 'descripcion', 'linea_negocio_id', 'centro_costo_id',
                                'articulo_id', 'servicio_id', 'servicio_detalle', 'tipo_linea',
                                'modelo_corte_id', 'cantidad', 'precio_unitario', 'importe', 'igv_aplica',
                                'unidad_interna_id'}
            allowed_fields = LINEA_CLASS_FIELDS if is_locked else LINEA_ALL_FIELDS
            classification_changed = False

            incoming_ids = set()
            # Para propagación NI: acumulamos cambios detectados y los aplicamos al final
            cambios_ni = []  # lista de dicts: {linea_id, servicio_id, modelo_corte_id, precio_nuevo, cant_nueva, importe_nuevo, ..._viejo}
            for linea in lineas_data:
                linea_id = linea.get('id')
                if linea_id:
                    incoming_ids.add(linea_id)
                    lu = []
                    lv = []
                    li = 1
                    for lf in allowed_fields:
                        if lf in linea:
                            lu.append(f"{lf} = ${li}"); lv.append(linea[lf]); li += 1
                            if lf in ('linea_negocio_id', 'categoria_id', 'centro_costo_id'):
                                classification_changed = True
                    if lu:
                        lv.append(linea_id)
                        await conn.execute(
                            f"UPDATE finanzas2.cont_factura_proveedor_linea SET {', '.join(lu)} WHERE id = ${li}", *lv)
                    # Detectar cambios relevantes para propagar a NI
                    if es_nota_interna and linea_id in lineas_viejas_map:
                        vieja = lineas_viejas_map[linea_id]
                        cambios_ni.append({
                            'linea_id': linea_id,
                            'servicio_id': vieja['servicio_id'],
                            'modelo_corte_id': vieja['modelo_corte_id'],
                            'precio_viejo': float(vieja['precio_unitario'] or 0),
                            'precio_nuevo': float(linea.get('precio_unitario', vieja['precio_unitario']) or 0),
                            'cant_vieja': int(vieja['cantidad'] or 0),
                            'cant_nueva': int(linea.get('cantidad', vieja['cantidad']) or 0),
                            'importe_viejo': float(vieja['importe'] or 0),
                            'importe_nuevo': float(linea.get('importe', vieja['importe']) or 0),
                        })
                elif not is_locked:
                    await conn.execute("""
                        INSERT INTO finanzas2.cont_factura_proveedor_linea
                        (empresa_id, factura_id, categoria_id, articulo_id, servicio_id, servicio_detalle, tipo_linea,
                         descripcion, linea_negocio_id, centro_costo_id, importe, igv_aplica, cantidad, precio_unitario, modelo_corte_id, unidad_interna_id)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                    """, empresa_id, id, linea.get('categoria_id'), linea.get('articulo_id'),
                        linea.get('servicio_id'), linea.get('servicio_detalle'), linea.get('tipo_linea'),
                        linea.get('descripcion'), linea.get('linea_negocio_id'), linea.get('centro_costo_id'),
                        linea.get('importe', 0), linea.get('igv_aplica', True),
                        linea.get('cantidad', 0), linea.get('precio_unitario', 0), linea.get('modelo_corte_id'),
                        linea.get('unidad_interna_id'))

            if not is_locked and incoming_ids:
                existing = await conn.fetch(
                    "SELECT id FROM finanzas2.cont_factura_proveedor_linea WHERE factura_id = $1", id)
                for row in existing:
                    if row['id'] not in incoming_ids:
                        await conn.execute(
                            "DELETE FROM finanzas2.cont_factura_proveedor_linea WHERE id = $1", row['id'])

            if classification_changed:
                await recalcular_distribuciones_factura(conn, empresa_id, id)

            # ─────────────────────────────────────────────────────────────
            # PROPAGACIÓN NOTA INTERNA → cargos + cuenta ficticia + movimiento
            # Si la factura es nota_interna y se editaron precios/cantidades,
            # propagar los cambios al cargo interno, al movimiento en cuenta
            # ficticia, al saldo de la cuenta, y al movimiento de producción.
            # Todo transaccional (estamos dentro del pool.acquire context).
            # ─────────────────────────────────────────────────────────────
            if es_nota_interna and cambios_ni:
                factura_numero = factura['numero']
                for ch in cambios_ni:
                    precio_cambio = abs(ch['precio_nuevo'] - ch['precio_viejo']) > 0.0001
                    cant_cambio = ch['cant_nueva'] != ch['cant_vieja']
                    importe_cambio = abs(ch['importe_nuevo'] - ch['importe_viejo']) > 0.01
                    if not (precio_cambio or cant_cambio or importe_cambio):
                        continue

                    diff_importe = ch['importe_nuevo'] - ch['importe_viejo']

                    # Encontrar el movimiento de producción asociado
                    mov = await conn.fetchrow("""
                        SELECT mp.id
                        FROM produccion.prod_movimientos_produccion mp
                        WHERE mp.factura_numero = $1
                          AND mp.registro_id = $2
                          AND mp.servicio_id = $3
                        LIMIT 1
                    """, factura_numero, ch['modelo_corte_id'], ch['servicio_id'])
                    if not mov:
                        continue
                    mov_id = mov['id']

                    # 1) Propagar al movimiento de producción
                    await conn.execute("""
                        UPDATE produccion.prod_movimientos_produccion
                        SET tarifa_aplicada = $1, costo_calculado = $2
                        WHERE id = $3
                    """, ch['precio_nuevo'], ch['importe_nuevo'], mov_id)

                    # 2) Propagar al cargo interno
                    cargo = await conn.fetchrow("""
                        SELECT id, unidad_interna_id
                        FROM finanzas2.fin_cargo_interno
                        WHERE movimiento_id = $1
                    """, mov_id)
                    if cargo:
                        await conn.execute("""
                            UPDATE finanzas2.fin_cargo_interno
                            SET tarifa = $1, cantidad = $2, importe = $3, updated_at = NOW()
                            WHERE id = $4
                        """, ch['precio_nuevo'], ch['cant_nueva'], ch['importe_nuevo'], cargo['id'])

                        # 3) Actualizar movimiento en cuenta ficticia
                        await conn.execute("""
                            UPDATE finanzas2.fin_movimiento_cuenta
                            SET monto = $1,
                                descripcion = $2
                            WHERE referencia_tipo = 'CARGO_INTERNO' AND referencia_id = $3
                        """, ch['importe_nuevo'],
                            f"Cobro {ch['cant_nueva']} prendas - editado (NI {factura_numero})",
                            str(cargo['id']))

                        # 4) Ajustar saldo de la cuenta ficticia
                        cuenta_id = await conn.fetchval("""
                            SELECT id FROM finanzas2.cont_cuenta_financiera
                            WHERE unidad_interna_id = $1 AND es_ficticia = TRUE AND empresa_id = $2
                            LIMIT 1
                        """, cargo['unidad_interna_id'], empresa_id)
                        if cuenta_id:
                            await conn.execute("""
                                UPDATE finanzas2.cont_cuenta_financiera
                                SET saldo_actual = COALESCE(saldo_actual, 0) + $1
                                WHERE id = $2
                            """, diff_importe, cuenta_id)

                        # 5) Log de auditoría
                        await conn.execute("""
                            INSERT INTO finanzas2.fin_cargo_interno_log
                                (cargo_id, factura_id, factura_linea_id, movimiento_id,
                                 tarifa_vieja, tarifa_nueva,
                                 cantidad_vieja, cantidad_nueva,
                                 importe_viejo, importe_nuevo, diff_importe,
                                 motivo, empresa_id)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'edicion_ni', $12)
                        """,
                            cargo['id'], id, ch['linea_id'], mov_id,
                            ch['precio_viejo'], ch['precio_nuevo'],
                            ch['cant_vieja'], ch['cant_nueva'],
                            ch['importe_viejo'], ch['importe_nuevo'], diff_importe,
                            empresa_id)

        # ─── Recalcular totales de cabecera desde las líneas ───
        # Se ejecuta SIEMPRE al final del update (aunque no haya cambios en líneas),
        # porque el frontend manda base_gravada/igv_sunat pero NO total/subtotal,
        # y en facturas con líneas con impuestos_incluidos hay que recalcular.
        f_actual = await conn.fetchrow(
            "SELECT impuestos_incluidos FROM finanzas2.cont_factura_proveedor WHERE id = $1",
            id
        )
        impuestos_incluidos = f_actual['impuestos_incluidos'] if f_actual else True
        # total_pagado = suma de aplicaciones de pago a esta factura
        total_pagado = float(await conn.fetchval(
            """SELECT COALESCE(SUM(pa.monto_aplicado), 0)
                 FROM finanzas2.cont_pago_aplicacion pa
                WHERE pa.tipo_documento = 'factura' AND pa.documento_id = $1""",
            id
        ) or 0)

        agg = await conn.fetchrow("""
            SELECT
                COALESCE(SUM(CASE WHEN igv_aplica THEN importe ELSE 0 END), 0)::numeric AS imp_grav,
                COALESCE(SUM(CASE WHEN NOT igv_aplica THEN importe ELSE 0 END), 0)::numeric AS imp_no_grav
              FROM finanzas2.cont_factura_proveedor_linea
             WHERE factura_id = $1
        """, id)
        imp_grav = float(agg['imp_grav'] or 0)
        imp_no_grav = float(agg['imp_no_grav'] or 0)

        if impuestos_incluidos:
            base_grav = round(imp_grav / 1.18, 2)
            igv_calc = round(imp_grav - base_grav, 2)
        else:
            base_grav = round(imp_grav, 2)
            igv_calc = round(imp_grav * 0.18, 2)

        subtotal_calc = round(base_grav + imp_no_grav, 2)
        total_calc = round(subtotal_calc + igv_calc, 2)
        saldo_calc = round(total_calc - total_pagado, 2)

        # Determinar nuevo estado según pagos
        if total_pagado <= 0:
            nuevo_estado = 'pendiente' if total_calc > 0 else (factura['estado'] or 'pendiente')
        elif total_pagado < total_calc - 0.01:
            nuevo_estado = 'parcial'
        else:
            nuevo_estado = 'pagado'

        # No pisar estado 'canjeado' ni 'anulada'
        estado_actual = factura['estado']
        if estado_actual in ('canjeado', 'anulada'):
            nuevo_estado = estado_actual

        await conn.execute("""
            UPDATE finanzas2.cont_factura_proveedor
               SET subtotal = $1, igv = $2, total = $3,
                   base_gravada = $4, igv_sunat = $5, base_no_gravada = $6,
                   saldo_pendiente = $7, estado = $8, updated_at = NOW()
             WHERE id = $9
        """, subtotal_calc, igv_calc, total_calc,
            base_grav, igv_calc, round(imp_no_grav, 2),
            saldo_calc, nuevo_estado, id)

        # Sincronizar CxP
        await conn.execute("""
            UPDATE finanzas2.cont_cxp
               SET monto_original = $1, saldo_pendiente = $2, updated_at = NOW()
             WHERE factura_id = $3
        """, total_calc, saldo_calc, id)

        return await get_factura_proveedor(id, empresa_id)


@router.delete("/facturas-proveedor/{id}")
async def delete_factura_proveedor(id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        async with conn.transaction():
            factura = await conn.fetchrow("SELECT * FROM finanzas2.cont_factura_proveedor WHERE id = $1 AND empresa_id = $2", id, empresa_id)
            if not factura:
                raise HTTPException(404, "Factura not found")
            pagos = await conn.fetchval("""
                SELECT COUNT(*) FROM finanzas2.cont_pago_aplicacion
                WHERE tipo_documento = 'factura' AND documento_id = $1
            """, id)
            if pagos > 0:
                raise HTTPException(400, "Cannot delete factura with payments. Reverse payments first.")
            letras = await conn.fetchval("SELECT COUNT(*) FROM finanzas2.cont_letra WHERE factura_id = $1", id)
            if letras > 0:
                raise HTTPException(400, "Cannot delete factura with letras. Delete letras first.")

            factura_id_str = str(id)
            factura_numero = factura["numero"]
            tipo_doc = factura["tipo_documento"] or ""

            # 1) Si era NOTA INTERNA: revertir cargos internos ANTES de desvincular
            if tipo_doc == "nota_interna":
                cargos = await conn.fetch(
                    """
                    SELECT ci.id, ci.unidad_interna_id, ci.importe, ci.estado
                    FROM finanzas2.fin_cargo_interno ci
                    WHERE ci.movimiento_id IN (
                        SELECT id::text FROM produccion.prod_movimientos_produccion
                        WHERE factura_numero = $1
                    )
                    """,
                    factura_numero,
                )
                for c in cargos:
                    # Solo si el cargo estaba PROCESADO ('pagado') hay movimiento de cuenta
                    # que revertir (el 'generado' es solo una CxC virtual, no tocó el saldo).
                    if c["estado"] == "pagado":
                        cuenta_id = await conn.fetchval(
                            """
                            SELECT id FROM finanzas2.cont_cuenta_financiera
                            WHERE unidad_interna_id = $1 AND es_ficticia = TRUE
                              AND empresa_id = $2
                            LIMIT 1
                            """,
                            c["unidad_interna_id"], empresa_id,
                        )
                        if cuenta_id:
                            await conn.execute(
                                """
                                DELETE FROM finanzas2.fin_movimiento_cuenta
                                WHERE referencia_tipo = 'CARGO_INTERNO' AND referencia_id = $1
                                """,
                                str(c["id"]),
                            )
                            await conn.execute(
                                """
                                UPDATE finanzas2.cont_cuenta_financiera
                                SET saldo_actual = COALESCE(saldo_actual, 0) - $1
                                WHERE id = $2
                                """,
                                c["importe"], cuenta_id,
                            )
                    # Borrar el cargo interno (tanto si era 'generado' como 'pagado')
                    await conn.execute("DELETE FROM finanzas2.fin_cargo_interno WHERE id = $1", c["id"])

            # 2) Desvincular movimientos de producción (vuelven a "Pendiente" en el reporte)
            await conn.execute(
                """
                UPDATE produccion.prod_movimientos_produccion
                SET factura_numero = NULL, factura_id = NULL
                WHERE factura_id = $1 OR factura_numero = $2
                """,
                factura_id_str, factura_numero,
            )

            await conn.execute("DELETE FROM finanzas2.cont_cxp WHERE factura_id = $1", id)
            await conn.execute("DELETE FROM finanzas2.cont_factura_proveedor WHERE id = $1 AND empresa_id = $2", id, empresa_id)
            return {"message": "Factura deleted"}


# ══════════════════════════════════════════════════════════════════════════
# PROCESAR NOTA INTERNA — "pagar" internamente la NI, materializando el ingreso
# ══════════════════════════════════════════════════════════════════════════
@router.post("/facturas-proveedor/{id}/procesar-nota-interna")
async def procesar_nota_interna(id: int, empresa_id: int = Depends(get_empresa_id)):
    """
    Marca una Nota Interna como 'procesada': crea los movimientos INGRESO en la
    cuenta ficticia de la unidad, sube el saldo, y pasa los cargos de 'generado'
    a 'pagado'. Es análogo a cobrar una factura.
    Idempotente: si ya está procesada, no hace nada (retorna sin error).
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        async with conn.transaction():
            factura = await conn.fetchrow(
                "SELECT * FROM finanzas2.cont_factura_proveedor WHERE id = $1 AND empresa_id = $2",
                id, empresa_id,
            )
            if not factura:
                raise HTTPException(404, "Factura no encontrada")
            if factura["tipo_documento"] != "nota_interna":
                raise HTTPException(400, "Solo se pueden procesar notas internas")
            if factura["estado"] == "pagado":
                return {"message": "Ya estaba procesada", "procesada": False}

            # Traer cargos 'generado' vinculados a esta NI
            cargos = await conn.fetch(
                """
                SELECT ci.id, ci.unidad_interna_id, ci.importe, ci.cantidad,
                       ci.servicio_nombre, ci.fecha
                FROM finanzas2.fin_cargo_interno ci
                WHERE ci.estado = 'generado'
                  AND ci.movimiento_id IN (
                      SELECT id::text FROM produccion.prod_movimientos_produccion
                      WHERE factura_numero = $1
                  )
                """,
                factura["numero"],
            )

            procesados = 0
            total_ingresado = 0.0
            for c in cargos:
                cuenta_id = await conn.fetchval(
                    """
                    SELECT id FROM finanzas2.cont_cuenta_financiera
                    WHERE unidad_interna_id = $1 AND es_ficticia = TRUE AND empresa_id = $2
                    LIMIT 1
                    """,
                    c["unidad_interna_id"], empresa_id,
                )
                if cuenta_id:
                    await conn.execute(
                        """
                        INSERT INTO finanzas2.fin_movimiento_cuenta
                            (cuenta_id, empresa_id, tipo, monto, descripcion, fecha,
                             referencia_id, referencia_tipo)
                        VALUES ($1, $2, 'INGRESO', $3, $4, $5, $6, 'CARGO_INTERNO')
                        """,
                        cuenta_id, empresa_id, c["importe"],
                        f"Cobro {c['cantidad']} prendas - {c['servicio_nombre']} (NI {factura['numero']})",
                        c["fecha"], str(c["id"]),
                    )
                    await conn.execute(
                        """
                        UPDATE finanzas2.cont_cuenta_financiera
                        SET saldo_actual = COALESCE(saldo_actual, 0) + $1
                        WHERE id = $2
                        """,
                        c["importe"], cuenta_id,
                    )
                # Marcar el cargo como pagado
                await conn.execute(
                    "UPDATE finanzas2.fin_cargo_interno SET estado = 'pagado', updated_at = NOW() WHERE id = $1",
                    c["id"],
                )
                procesados += 1
                total_ingresado += float(c["importe"])

            # Marcar la factura como pagada
            await conn.execute(
                "UPDATE finanzas2.cont_factura_proveedor SET estado = 'pagado', updated_at = NOW() WHERE id = $1",
                id,
            )

            return {
                "message": f"Nota interna procesada: {procesados} cargo(s) por S/ {total_ingresado:.2f}",
                "procesada": True,
                "cargos_procesados": procesados,
                "total_ingresado": round(total_ingresado, 2),
            }


@router.post("/facturas-proveedor/{id}/anular-procesamiento-nota-interna")
async def anular_procesamiento_nota_interna(id: int, empresa_id: int = Depends(get_empresa_id)):
    """
    Revierte el procesamiento de una NI: borra los movimientos INGRESO de la cuenta
    ficticia, resta el saldo, y vuelve los cargos a 'generado'. La NI vuelve a
    estado 'pendiente' (CxC virtual).
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        async with conn.transaction():
            factura = await conn.fetchrow(
                "SELECT * FROM finanzas2.cont_factura_proveedor WHERE id = $1 AND empresa_id = $2",
                id, empresa_id,
            )
            if not factura:
                raise HTTPException(404, "Factura no encontrada")
            if factura["tipo_documento"] != "nota_interna":
                raise HTTPException(400, "Solo aplicable a notas internas")
            if factura["estado"] != "pagado":
                return {"message": "No estaba procesada", "revertida": False}

            cargos = await conn.fetch(
                """
                SELECT ci.id, ci.unidad_interna_id, ci.importe
                FROM finanzas2.fin_cargo_interno ci
                WHERE ci.estado = 'pagado'
                  AND ci.movimiento_id IN (
                      SELECT id::text FROM produccion.prod_movimientos_produccion
                      WHERE factura_numero = $1
                  )
                """,
                factura["numero"],
            )

            revertidos = 0
            total_revertido = 0.0
            for c in cargos:
                cuenta_id = await conn.fetchval(
                    """
                    SELECT id FROM finanzas2.cont_cuenta_financiera
                    WHERE unidad_interna_id = $1 AND es_ficticia = TRUE AND empresa_id = $2
                    LIMIT 1
                    """,
                    c["unidad_interna_id"], empresa_id,
                )
                if cuenta_id:
                    await conn.execute(
                        """
                        DELETE FROM finanzas2.fin_movimiento_cuenta
                        WHERE referencia_tipo = 'CARGO_INTERNO' AND referencia_id = $1
                        """,
                        str(c["id"]),
                    )
                    await conn.execute(
                        """
                        UPDATE finanzas2.cont_cuenta_financiera
                        SET saldo_actual = COALESCE(saldo_actual, 0) - $1
                        WHERE id = $2
                        """,
                        c["importe"], cuenta_id,
                    )
                await conn.execute(
                    "UPDATE finanzas2.fin_cargo_interno SET estado = 'generado', updated_at = NOW() WHERE id = $1",
                    c["id"],
                )
                revertidos += 1
                total_revertido += float(c["importe"])

            await conn.execute(
                "UPDATE finanzas2.cont_factura_proveedor SET estado = 'pendiente', updated_at = NOW() WHERE id = $1",
                id,
            )

            return {
                "message": f"Procesamiento anulado: {revertidos} cargo(s) por S/ {total_revertido:.2f} revertidos",
                "revertida": True,
                "cargos_revertidos": revertidos,
                "total_revertido": round(total_revertido, 2),
            }


@router.get("/facturas-proveedor/{id}/pagos")
async def get_pagos_de_factura(id: int, empresa_id: int = Depends(get_empresa_id)):
    """Devuelve historial unificado de pagos: directos + pagos a letras canjeadas."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        rows = await conn.fetch("""
            -- Pagos directos a la factura
            SELECT COALESCE(mt.id, p.id) as id,
                   COALESCE(mt.numero, p.numero) as numero,
                   COALESCE(mt.tipo, p.tipo::text) as tipo,
                   COALESCE(mt.fecha, p.fecha) as fecha,
                   COALESCE(mt.monto, p.monto_total) as monto_total,
                   pa.monto_aplicado,
                   COALESCE(cf_mt.nombre, cf_p.nombre) as cuenta_nombre,
                   COALESCE(mon_mt.codigo, mon_p.codigo) as moneda_codigo,
                   COALESCE(mon_mt.simbolo, mon_p.simbolo) as moneda_simbolo,
                   COALESCE(mt.referencia, p.referencia) as referencia,
                   COALESCE(mt.conciliado, false) as conciliado,
                   'factura' as origen,
                   NULL::text as letra_numero
            FROM finanzas2.cont_pago_aplicacion pa
            LEFT JOIN finanzas2.cont_movimiento_tesoreria mt ON pa.movimiento_tesoreria_id = mt.id
            LEFT JOIN finanzas2.cont_pago p ON pa.pago_id = p.id
            LEFT JOIN finanzas2.cont_cuenta_financiera cf_mt ON mt.cuenta_financiera_id = cf_mt.id
            LEFT JOIN finanzas2.cont_cuenta_financiera cf_p ON p.cuenta_financiera_id = cf_p.id
            LEFT JOIN finanzas2.cont_moneda mon_mt ON mt.moneda_id = mon_mt.id
            LEFT JOIN finanzas2.cont_moneda mon_p ON p.moneda_id = mon_p.id
            WHERE pa.tipo_documento = 'factura' AND pa.documento_id = $1

            UNION ALL

            -- Pagos hechos a letras de esta factura (cuando está canjeada)
            SELECT COALESCE(mt.id, p.id, pa.id) as id,
                   COALESCE(mt.numero, p.numero, 'L-' || l.numero) as numero,
                   COALESCE(mt.tipo, p.tipo::text, 'egreso') as tipo,
                   COALESCE(mt.fecha, p.fecha, l.updated_at::date) as fecha,
                   COALESCE(mt.monto, p.monto_total, pa.monto_aplicado) as monto_total,
                   pa.monto_aplicado,
                   COALESCE(cf_mt.nombre, cf_p.nombre, '—') as cuenta_nombre,
                   COALESCE(mon_mt.codigo, mon_p.codigo, 'PEN') as moneda_codigo,
                   COALESCE(mon_mt.simbolo, mon_p.simbolo, 'S/') as moneda_simbolo,
                   COALESCE(mt.referencia, p.referencia, l.numero) as referencia,
                   COALESCE(mt.conciliado, false) as conciliado,
                   'letra' as origen,
                   l.numero as letra_numero
            FROM finanzas2.cont_letra l
            JOIN finanzas2.cont_pago_aplicacion pa
              ON pa.tipo_documento = 'letra' AND pa.documento_id = l.id
            LEFT JOIN finanzas2.cont_movimiento_tesoreria mt ON pa.movimiento_tesoreria_id = mt.id
            LEFT JOIN finanzas2.cont_pago p ON pa.pago_id = p.id
            LEFT JOIN finanzas2.cont_cuenta_financiera cf_mt ON mt.cuenta_financiera_id = cf_mt.id
            LEFT JOIN finanzas2.cont_cuenta_financiera cf_p ON p.cuenta_financiera_id = cf_p.id
            LEFT JOIN finanzas2.cont_moneda mon_mt ON mt.moneda_id = mon_mt.id
            LEFT JOIN finanzas2.cont_moneda mon_p ON p.moneda_id = mon_p.id
            WHERE l.factura_id = $1

            ORDER BY fecha DESC NULLS LAST
        """, id)
        return [dict(r) for r in rows]


@router.get("/facturas-proveedor/{id}/letras")
async def get_letras_de_factura(id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        rows = await conn.fetch("""
            SELECT l.*, fp.moneda_id, m.codigo as moneda_codigo, m.simbolo as moneda_simbolo
            FROM finanzas2.cont_letra l
            LEFT JOIN finanzas2.cont_factura_proveedor fp ON l.factura_id = fp.id
            LEFT JOIN finanzas2.cont_moneda m ON fp.moneda_id = m.id
            WHERE l.factura_id = $1
            ORDER BY l.fecha_vencimiento ASC
        """, id)
        return [dict(r) for r in rows]


@router.post("/facturas-proveedor/{id}/deshacer-canje")
async def deshacer_canje_letras(id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        async with conn.transaction():
            factura = await conn.fetchrow("SELECT * FROM finanzas2.cont_factura_proveedor WHERE id = $1 AND empresa_id = $2", id, empresa_id)
            if not factura:
                raise HTTPException(404, "Factura not found")
            if factura['estado'] != 'canjeado':
                raise HTTPException(400, "Factura is not in canjeado state")
            pagos_letras = await conn.fetchval("""
                SELECT COUNT(*) FROM finanzas2.cont_pago_aplicacion pa
                JOIN finanzas2.cont_letra l ON pa.tipo_documento = 'letra' AND pa.documento_id = l.id
                WHERE l.factura_id = $1
            """, id)
            if pagos_letras > 0:
                raise HTTPException(400, "Cannot undo canje - some letras have payments. Delete payments first.")
            await conn.execute("DELETE FROM finanzas2.cont_letra WHERE factura_id = $1", id)
            await conn.execute("""
                UPDATE finanzas2.cont_factura_proveedor
                SET estado = 'pendiente', updated_at = NOW()
                WHERE id = $1
            """, id)
            return {"message": "Canje reversed successfully"}


# =====================
# VINCULACION FACTURA ↔ INGRESOS MP
# =====================

@router.get("/facturas-proveedor/{factura_id}/vinculaciones")
async def get_vinculaciones_factura(factura_id: int, empresa_id: int = Depends(get_empresa_id)):
    """Get all vinculaciones for a factura, grouped by linea"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        rows = await conn.fetch("""
            SELECT v.id, v.factura_linea_id, v.ingreso_id, v.articulo_id, v.cantidad_aplicada, v.created_at,
                   i.fecha as ingreso_fecha, i.numero_documento as ingreso_ref, i.cantidad as ingreso_cantidad,
                   i.proveedor as ingreso_proveedor,
                   inv.nombre as articulo_nombre, inv.codigo as articulo_codigo
            FROM finanzas2.cont_factura_ingreso_mp v
            LEFT JOIN produccion.prod_inventario_ingresos i ON v.ingreso_id = i.id
            LEFT JOIN produccion.prod_inventario inv ON v.articulo_id = inv.id
            WHERE v.factura_id = $1 AND v.empresa_id = $2
            ORDER BY v.factura_linea_id, v.created_at
        """, factura_id, empresa_id)
        return [dict(r) for r in rows]


@router.get("/facturas-proveedor/{factura_id}/linea/{linea_id}/ingresos-disponibles")
async def get_ingresos_disponibles(factura_id: int, linea_id: int, empresa_id: int = Depends(get_empresa_id)):
    """Get compatible ingresos for a specific factura line (same articulo_id)"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        # Get the articulo_id of this line
        linea = await conn.fetchrow("""
            SELECT articulo_id, cantidad, descripcion FROM finanzas2.cont_factura_proveedor_linea
            WHERE id = $1 AND factura_id = $2
        """, linea_id, factura_id)
        if not linea:
            raise HTTPException(404, "Línea de factura no encontrada")
        if not linea['articulo_id']:
            return {"linea": dict(linea), "ingresos": [], "message": "Esta línea no tiene artículo asignado"}

        articulo_id = linea['articulo_id']

        # Get cantidad already linked for this line
        ya_vinculado_linea = await conn.fetchval("""
            SELECT COALESCE(SUM(cantidad_aplicada), 0) FROM finanzas2.cont_factura_ingreso_mp
            WHERE factura_linea_id = $1
        """, linea_id) or 0

        # Get compatible ingresos with their available (unlinked) quantities
        ingresos = await conn.fetch("""
            SELECT i.id, i.item_id, i.cantidad, i.costo_unitario, i.proveedor, i.numero_documento,
                   i.fecha, inv.nombre as articulo_nombre, inv.codigo as articulo_codigo,
                   COALESCE(vinc.total_vinculado, 0) as total_vinculado
            FROM produccion.prod_inventario_ingresos i
            LEFT JOIN produccion.prod_inventario inv ON i.item_id = inv.id
            LEFT JOIN (
                SELECT ingreso_id, SUM(cantidad_aplicada) as total_vinculado
                FROM finanzas2.cont_factura_ingreso_mp
                GROUP BY ingreso_id
            ) vinc ON i.id = vinc.ingreso_id
            WHERE i.item_id = $1 AND i.empresa_id = $2
            ORDER BY i.fecha DESC
        """, articulo_id, empresa_id)

        result_ingresos = []
        for ing in ingresos:
            d = dict(ing)
            d['saldo_disponible'] = float(d['cantidad']) - float(d['total_vinculado'])
            result_ingresos.append(d)

        return {
            "linea": {
                "id": linea_id,
                "articulo_id": articulo_id,
                "cantidad": float(linea['cantidad'] or 0),
                "descripcion": linea['descripcion'],
                "ya_vinculado": float(ya_vinculado_linea)
            },
            "ingresos": result_ingresos
        }


@router.post("/facturas-proveedor/{factura_id}/linea/{linea_id}/vincular-ingreso")
async def vincular_ingreso(factura_id: int, linea_id: int, empresa_id: int = Depends(get_empresa_id), body: dict = {}):
    """Link an ingreso to a factura line"""
    ingreso_id = body.get('ingreso_id')
    cantidad = body.get('cantidad_aplicada')
    if not ingreso_id or not cantidad or float(cantidad) <= 0:
        raise HTTPException(400, "ingreso_id y cantidad_aplicada son requeridos (cantidad > 0)")
    cantidad = float(cantidad)

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")

        # Validate line exists and get articulo
        linea = await conn.fetchrow("""
            SELECT articulo_id, cantidad FROM finanzas2.cont_factura_proveedor_linea
            WHERE id = $1 AND factura_id = $2
        """, linea_id, factura_id)
        if not linea:
            raise HTTPException(404, "Línea de factura no encontrada")
        if not linea['articulo_id']:
            raise HTTPException(400, "Esta línea no tiene artículo asignado")

        # Validate ingreso exists and articulo matches
        ingreso = await conn.fetchrow("""
            SELECT id, item_id, cantidad FROM produccion.prod_inventario_ingresos
            WHERE id = $1 AND empresa_id = $2
        """, ingreso_id, empresa_id)
        if not ingreso:
            raise HTTPException(404, "Ingreso no encontrado")
        if ingreso['item_id'] != linea['articulo_id']:
            raise HTTPException(400, "El artículo del ingreso no coincide con el de la línea")

        # Validate: don't exceed factura line quantity
        ya_vinculado_linea = await conn.fetchval("""
            SELECT COALESCE(SUM(cantidad_aplicada), 0) FROM finanzas2.cont_factura_ingreso_mp
            WHERE factura_linea_id = $1
        """, linea_id) or 0
        if float(ya_vinculado_linea) + cantidad > float(linea['cantidad']):
            raise HTTPException(400, f"Excede cantidad facturada. Facturado: {linea['cantidad']}, ya vinculado: {ya_vinculado_linea}, intentando: {cantidad}")

        # Validate: don't exceed ingreso total quantity
        ya_vinculado_ingreso = await conn.fetchval("""
            SELECT COALESCE(SUM(cantidad_aplicada), 0) FROM finanzas2.cont_factura_ingreso_mp
            WHERE ingreso_id = $1
        """, ingreso_id) or 0
        if float(ya_vinculado_ingreso) + cantidad > float(ingreso['cantidad']):
            raise HTTPException(400, f"Excede cantidad del ingreso. Ingreso: {ingreso['cantidad']}, ya vinculado: {ya_vinculado_ingreso}, intentando: {cantidad}")

        row = await conn.fetchrow("""
            INSERT INTO finanzas2.cont_factura_ingreso_mp
            (empresa_id, factura_id, factura_linea_id, ingreso_id, articulo_id, cantidad_aplicada)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, factura_linea_id, ingreso_id, articulo_id, cantidad_aplicada, created_at
        """, empresa_id, factura_id, linea_id, ingreso_id, linea['articulo_id'], cantidad)
        return dict(row)


@router.delete("/facturas-proveedor/vinculacion/{vinculacion_id}")
async def desvincular_ingreso(vinculacion_id: int, empresa_id: int = Depends(get_empresa_id)):
    """Remove a vinculacion"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        row = await conn.fetchrow("""
            DELETE FROM finanzas2.cont_factura_ingreso_mp WHERE id = $1 AND empresa_id = $2 RETURNING id
        """, vinculacion_id, empresa_id)
        if not row:
            raise HTTPException(404, "Vinculación no encontrada")
        return {"message": "Vinculación eliminada"}
