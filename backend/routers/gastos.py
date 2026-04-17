from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from datetime import date, datetime
from database import get_pool
from models import Gasto, GastoCreate, Adelanto, AdelantoCreate
from dependencies import get_empresa_id, safe_date_param, get_next_correlativo
from routers.pagos import generate_pago_number

router = APIRouter()


async def generate_gasto_number(conn, empresa_id: int) -> str:
    """Generate auto-incrementing gasto number"""
    year = datetime.now().year
    prefijo = f"GAS-{year}-"
    return await get_next_correlativo(conn, empresa_id, 'gasto', prefijo)


# =====================
# GASTOS
# =====================
@router.get("/gastos", response_model=List[Gasto])
async def list_gastos(
    categoria_id: Optional[int] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    es_cif: Optional[bool] = None,
    unidad_interna_id: Optional[int] = None,
    linea_negocio_id: Optional[int] = None,
    centro_costo_id: Optional[int] = None,
    proveedor_id: Optional[int] = None,
    busqueda: Optional[str] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        conditions = ["g.empresa_id = $1"]
        params = [empresa_id]
        idx = 2
        if categoria_id:
            conditions.append(f"gl.categoria_id = ${idx}"); params.append(categoria_id); idx += 1
        if fecha_desde:
            conditions.append(f"g.fecha >= ${idx}"); params.append(fecha_desde); idx += 1
        if fecha_hasta:
            conditions.append(f"g.fecha <= ${idx}"); params.append(fecha_hasta); idx += 1
        if es_cif is not None:
            conditions.append(f"COALESCE(cg.es_cif, false) = ${idx}"); params.append(es_cif); idx += 1
        if unidad_interna_id:
            conditions.append(f"g.unidad_interna_id = ${idx}"); params.append(unidad_interna_id); idx += 1
        if linea_negocio_id:
            conditions.append(f"g.linea_negocio_id = ${idx}"); params.append(linea_negocio_id); idx += 1
        if centro_costo_id:
            conditions.append(f"g.centro_costo_id = ${idx}"); params.append(centro_costo_id); idx += 1
        if proveedor_id:
            conditions.append(f"g.proveedor_id = ${idx}"); params.append(proveedor_id); idx += 1
        if busqueda:
            conditions.append(f"(g.beneficiario_nombre ILIKE ${idx} OR g.numero ILIKE ${idx} OR g.notas ILIKE ${idx} OR t.nombre ILIKE ${idx})")
            params.append(f"%{busqueda}%"); idx += 1
        query = f"""
            SELECT DISTINCT ON (g.id)
                   g.*, m.codigo as moneda_codigo, m.simbolo as moneda_simbolo,
                   t.nombre as proveedor_nombre,
                   cg.nombre as categoria_gasto_nombre,
                   cc.nombre as centro_costo_nombre,
                   ln.nombre as linea_negocio_nombre,
                   ui.nombre as unidad_interna_nombre,
                   cfp.nombre as cuenta_pago_nombre
            FROM finanzas2.cont_gasto g
            LEFT JOIN finanzas2.cont_gasto_linea gl ON g.id = gl.gasto_id
            LEFT JOIN finanzas2.cont_moneda m ON g.moneda_id = m.id
            LEFT JOIN finanzas2.cont_tercero t ON g.proveedor_id = t.id
            LEFT JOIN finanzas2.cont_categoria_gasto cg ON g.categoria_gasto_id = cg.id
            LEFT JOIN finanzas2.cont_centro_costo cc ON g.centro_costo_id = cc.id
            LEFT JOIN finanzas2.cont_linea_negocio ln ON g.linea_negocio_id = ln.id
            LEFT JOIN finanzas2.fin_unidad_interna ui ON g.unidad_interna_id = ui.id
            LEFT JOIN finanzas2.cont_cuenta_financiera cfp ON g.cuenta_pago_id = cfp.id
            WHERE {' AND '.join(conditions)}
            ORDER BY g.id, g.fecha DESC
        """
        rows = await conn.fetch(query, *params)
        result = []
        for row in rows:
            gasto_dict = dict(row)
            lineas = await conn.fetch("""
                SELECT gl.*, c.nombre as categoria_nombre,
                       ln.nombre as linea_negocio_nombre, cc.nombre as centro_costo_nombre
                FROM finanzas2.cont_gasto_linea gl
                LEFT JOIN finanzas2.cont_categoria c ON gl.categoria_id = c.id
                LEFT JOIN finanzas2.cont_linea_negocio ln ON gl.linea_negocio_id = ln.id
                LEFT JOIN finanzas2.cont_centro_costo cc ON gl.centro_costo_id = cc.id
                WHERE gl.gasto_id = $1
            """, row['id'])
            gasto_dict['lineas'] = [dict(l) for l in lineas]
            result.append(gasto_dict)
        return result


@router.post("/gastos", response_model=Gasto)
async def create_gasto(data: GastoCreate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        async with conn.transaction():
            # Generate auto-incrementing gasto number
            numero = await generate_gasto_number(conn, empresa_id)
            
            # Calculate totals from line items (authoritative source)
            isc_val = data.isc or 0.0
            base_gravada = 0.0
            base_no_gravada = 0.0
            for linea in data.lineas:
                if linea.igv_aplica:
                    base_gravada += linea.importe
                else:
                    base_no_gravada += linea.importe
            igv = round(base_gravada * 0.18, 2)
            subtotal = base_gravada + base_no_gravada
            total = round(subtotal + igv + isc_val, 2)
            # Fall back to body values if no lineas provided
            if not data.lineas:
                base_gravada = data.base_gravada
                base_no_gravada = data.base_no_gravada
                igv = data.igv_sunat
                subtotal = base_gravada + base_no_gravada
                total = round(subtotal + igv + isc_val, 2)
            
            fecha_contable = data.fecha_contable or data.fecha
            # Resolve header-level dimensions
            tipo_asignacion = data.tipo_asignacion or 'directo'
            categoria_gasto_id = data.categoria_gasto_id
            centro_costo_id_header = data.centro_costo_id
            linea_negocio_id_header = data.linea_negocio_id if tipo_asignacion == 'directo' else None

            # Determine cuenta_pago_id: use body value if provided, else auto-detect from pagos
            cuenta_pago_id = data.cuenta_pago_id
            if not cuenta_pago_id and data.pagos:
                for pago_item in data.pagos:
                    is_fict = await conn.fetchval(
                        "SELECT es_ficticia FROM finanzas2.cont_cuenta_financiera WHERE id=$1",
                        pago_item.cuenta_financiera_id)
                    if is_fict:
                        cuenta_pago_id = pago_item.cuenta_financiera_id
                        break

            row = await conn.fetchrow("""
                INSERT INTO finanzas2.cont_gasto
                (empresa_id, numero, fecha, fecha_contable, beneficiario_nombre, proveedor_id, moneda_id, subtotal, igv, total,
                 tipo_documento, numero_documento, notas, tipo_comprobante_sunat, base_gravada, igv_sunat, base_no_gravada, isc, tipo_cambio,
                 categoria_gasto_id, tipo_asignacion, centro_costo_id, linea_negocio_id, unidad_interna_id, cuenta_pago_id)
                VALUES ($1, $2, TO_DATE($3, 'YYYY-MM-DD'), TO_DATE($4, 'YYYY-MM-DD'), $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19,
                        $20, $21, $22, $23, $24, $25)
                RETURNING *
            """, empresa_id, numero, safe_date_param(data.fecha), safe_date_param(fecha_contable), data.beneficiario_nombre,
                data.proveedor_id, data.moneda_id, subtotal, igv, total,
                data.tipo_documento, data.numero_documento, data.notas,
                data.tipo_comprobante_sunat, base_gravada, igv, base_no_gravada, isc_val, data.tipo_cambio,
                categoria_gasto_id, tipo_asignacion, centro_costo_id_header, linea_negocio_id_header,
                data.unidad_interna_id, cuenta_pago_id)
            gasto_id = row['id']
            
            # Insert line items
            for linea in data.lineas:
                await conn.execute("""
                    INSERT INTO finanzas2.cont_gasto_linea
                    (empresa_id, gasto_id, categoria_id, descripcion, importe, igv_aplica, linea_negocio_id, centro_costo_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """, empresa_id, gasto_id, linea.categoria_id, linea.descripcion, linea.importe, linea.igv_aplica,
                    linea.linea_negocio_id, linea.centro_costo_id)
            
            # Process payments from the pagos array (new frontend structure)
            pago_id = None
            if data.pagos and len(data.pagos) > 0:
                centro_costo_id_val = data.lineas[0].centro_costo_id if data.lineas and data.lineas[0].centro_costo_id else None
                linea_negocio_id_val = data.lineas[0].linea_negocio_id if data.lineas and data.lineas[0].linea_negocio_id else None
                
                # Create a single pago record for the gasto
                pago_numero = await generate_pago_number(conn, 'egreso', empresa_id)
                pago = await conn.fetchrow("""
                    INSERT INTO finanzas2.cont_pago
                    (empresa_id, numero, tipo, fecha, cuenta_financiera_id, moneda_id, monto_total, referencia, notas, centro_costo_id, linea_negocio_id)
                    VALUES ($1, $2, 'egreso', TO_DATE($3, 'YYYY-MM-DD'), $4, $5, $6, $7, $8, $9, $10)
                    RETURNING id
                """, empresa_id, pago_numero, safe_date_param(data.fecha), data.pagos[0].cuenta_financiera_id,
                    data.moneda_id, total, data.numero_documento or numero, data.notas, centro_costo_id_val, linea_negocio_id_val)
                pago_id = pago['id']
                
                # Insert pago detalles for each payment in the array
                for pago_item in data.pagos:
                    await conn.execute("""
                        INSERT INTO finanzas2.cont_pago_detalle
                        (empresa_id, pago_id, cuenta_financiera_id, medio_pago, monto)
                        VALUES ($1, $2, $3, $4, $5)
                    """, empresa_id, pago_id, pago_item.cuenta_financiera_id, pago_item.medio_pago, pago_item.monto)
                    
                    # Update cuenta financiera balance
                    await conn.execute("UPDATE finanzas2.cont_cuenta_financiera SET saldo_actual = saldo_actual - $1 WHERE id = $2",
                                       pago_item.monto, pago_item.cuenta_financiera_id)

                    # If fictitious account, register EGRESO movement
                    is_ficticia = await conn.fetchval(
                        "SELECT es_ficticia FROM finanzas2.cont_cuenta_financiera WHERE id=$1",
                        pago_item.cuenta_financiera_id)
                    if is_ficticia:
                        await conn.execute("""
                            INSERT INTO finanzas2.fin_movimiento_cuenta
                            (cuenta_id, empresa_id, tipo, monto, descripcion, fecha, referencia_id, referencia_tipo)
                            VALUES ($1, $2, 'EGRESO', $3, $4, TO_DATE($5, 'YYYY-MM-DD'), $6, 'GASTO')
                        """, pago_item.cuenta_financiera_id, empresa_id, pago_item.monto,
                            data.notas or data.beneficiario_nombre or 'Gasto',
                            safe_date_param(data.fecha), str(gasto_id))
                
                # Create pago aplicacion
                await conn.execute("""
                    INSERT INTO finanzas2.cont_pago_aplicacion
                    (empresa_id, pago_id, tipo_documento, documento_id, monto_aplicado)
                    VALUES ($1, $2, 'gasto', $3, $4)
                """, empresa_id, pago_id, gasto_id, total)
                
                # Link pago to gasto
                await conn.execute("UPDATE finanzas2.cont_gasto SET pago_id = $1 WHERE id = $2", pago_id, gasto_id)

                # CAPA TESORERIA: Gasto pagado -> movimiento de tesoreria (egreso)
                from services.treasury_service import create_movimiento_tesoreria
                centro_costo_id_mov = data.lineas[0].centro_costo_id if data.lineas else None
                linea_negocio_id_mov = data.lineas[0].linea_negocio_id if data.lineas else None
                await create_movimiento_tesoreria(
                    conn, empresa_id, data.fecha, 'egreso', total,
                    cuenta_financiera_id=data.pagos[0].cuenta_financiera_id,
                    forma_pago=data.pagos[0].medio_pago,
                    referencia=data.numero_documento or numero,
                    concepto=f"Gasto {numero}",
                    origen_tipo='gasto_directo',
                    origen_id=gasto_id,
                    linea_negocio_id=linea_negocio_id_mov,
                    centro_costo_id=centro_costo_id_mov,
                    proyecto_id=getattr(data, 'proyecto_id', None),
                )
            elif data.proveedor_id:
                # CAPA OBLIGACION: Gasto sin pago con proveedor -> auto-crear CxP
                # Solo se crea CxP si hay proveedor_id; gastos directos sin proveedor no generan CxP
                await conn.execute("""
                    INSERT INTO finanzas2.cont_cxp
                    (empresa_id, monto_original, saldo_pendiente, fecha_vencimiento,
                     estado, proveedor_id, tipo_origen, documento_referencia,
                     categoria_id)
                    VALUES ($1, $2, $2, CURRENT_DATE + 30, 'pendiente', $3, 'gasto', $4,
                            $5)
                """, empresa_id, total, data.proveedor_id, numero,
                    data.lineas[0].categoria_id if data.lineas else None)
            
            # If cuenta_pago_id is a fictitious account and wasn't already handled by pagos,
            # create EGRESO movement and update saldo
            if cuenta_pago_id:
                already_handled = False
                if data.pagos:
                    for p in data.pagos:
                        if p.cuenta_financiera_id == cuenta_pago_id:
                            already_handled = True
                            break
                if not already_handled:
                    is_fict = await conn.fetchval(
                        "SELECT es_ficticia FROM finanzas2.cont_cuenta_financiera WHERE id=$1",
                        cuenta_pago_id)
                    if is_fict:
                        await conn.execute("""
                            INSERT INTO finanzas2.fin_movimiento_cuenta
                            (cuenta_id, empresa_id, tipo, monto, descripcion, fecha, referencia_id, referencia_tipo)
                            VALUES ($1, $2, 'EGRESO', $3, $4, TO_DATE($5, 'YYYY-MM-DD'), $6, 'GASTO')
                        """, cuenta_pago_id, empresa_id, total,
                            data.notas or data.beneficiario_nombre or 'Gasto',
                            safe_date_param(data.fecha), str(gasto_id))
                        await conn.execute(
                            "UPDATE finanzas2.cont_cuenta_financiera SET saldo_actual = saldo_actual - $1 WHERE id = $2",
                            total, cuenta_pago_id)

            gasto_dict = dict(row)
            gasto_dict['pago_id'] = pago_id
            # Enrich with joined names
            enriched = await conn.fetchrow("""
                SELECT cg.nombre as categoria_gasto_nombre,
                       cc.nombre as centro_costo_nombre,
                       ln.nombre as linea_negocio_nombre,
                       ui.nombre as unidad_interna_nombre,
                       cfp.nombre as cuenta_pago_nombre
                FROM finanzas2.cont_gasto g
                LEFT JOIN finanzas2.cont_categoria_gasto cg ON g.categoria_gasto_id = cg.id
                LEFT JOIN finanzas2.cont_centro_costo cc ON g.centro_costo_id = cc.id
                LEFT JOIN finanzas2.cont_linea_negocio ln ON g.linea_negocio_id = ln.id
                LEFT JOIN finanzas2.fin_unidad_interna ui ON g.unidad_interna_id = ui.id
                LEFT JOIN finanzas2.cont_cuenta_financiera cfp ON g.cuenta_pago_id = cfp.id
                WHERE g.id = $1
            """, gasto_id)
            if enriched:
                gasto_dict.update(dict(enriched))
            lineas = await conn.fetch("""
                SELECT gl.*, c.nombre as categoria_nombre,
                       ln.nombre as linea_negocio_nombre, cc.nombre as centro_costo_nombre
                FROM finanzas2.cont_gasto_linea gl
                LEFT JOIN finanzas2.cont_categoria c ON gl.categoria_id = c.id
                LEFT JOIN finanzas2.cont_linea_negocio ln ON gl.linea_negocio_id = ln.id
                LEFT JOIN finanzas2.cont_centro_costo cc ON gl.centro_costo_id = cc.id
                WHERE gl.gasto_id = $1
            """, gasto_id)
            gasto_dict['lineas'] = [dict(l) for l in lineas]
            return gasto_dict


@router.get("/gastos/cif-produccion")
async def get_cif_produccion(
    mes: Optional[int] = None,
    anio: Optional[int] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    """Retorna resumen de gastos CIF para producción en un mes/año dado."""
    from datetime import timedelta
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        hoy = date.today()
        m = mes or hoy.month
        a = anio or hoy.year
        primer_dia = date(a, m, 1)
        ultimo_dia = (primer_dia + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        # Gastos CIF del mes: cont_gasto_linea → cont_categoria donde padre = "CIF Producción"
        gastos = await conn.fetch("""
            SELECT DISTINCT g.id, g.numero, g.fecha, g.total,
                   c.nombre as categoria_nombre, c.codigo as categoria_codigo,
                   g.notas
            FROM finanzas2.cont_gasto g
            JOIN finanzas2.cont_gasto_linea gl ON g.id = gl.gasto_id
            JOIN finanzas2.cont_categoria c ON gl.categoria_id = c.id
            LEFT JOIN finanzas2.cont_categoria cp ON c.padre_id = cp.id
            WHERE g.empresa_id = $1
              AND g.fecha >= $2 AND g.fecha <= $3
              AND (c.nombre = 'CIF Producción' OR cp.nombre = 'CIF Producción')
            ORDER BY g.fecha
        """, empresa_id, primer_dia, ultimo_dia)

        total_gastos_cif = sum(float(g['total'] or 0) for g in gastos)

        # Depreciación del mes
        periodo_str = f"{a}-{m:02d}"
        depreciacion = await conn.fetchval("""
            SELECT COALESCE(SUM(d.valor_depreciacion), 0)
            FROM finanzas2.fin_depreciacion_activo d
            JOIN finanzas2.fin_activo_fijo a ON d.activo_id = a.id
            WHERE d.periodo = $1 AND a.empresa_id = $2 AND a.estado = 'activo'
        """, periodo_str, empresa_id)
        depreciacion_mes = float(depreciacion or 0)

        return {
            "periodo": periodo_str,
            "total_gastos_cif": round(total_gastos_cif, 2),
            "depreciacion_mes": round(depreciacion_mes, 2),
            "total_cif": round(total_gastos_cif + depreciacion_mes, 2),
            "gastos": [dict(g) for g in gastos],
        }


@router.get("/gastos/{id}")
async def get_gasto(id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        row = await conn.fetchrow("""
            SELECT g.*, m.codigo as moneda_codigo, m.simbolo as moneda_simbolo,
                   t.nombre as proveedor_nombre,
                   cg.nombre as categoria_gasto_nombre,
                   cc.nombre as centro_costo_nombre,
                   ln.nombre as linea_negocio_nombre,
                   ui.nombre as unidad_interna_nombre,
                   cfp.nombre as cuenta_pago_nombre
            FROM finanzas2.cont_gasto g
            LEFT JOIN finanzas2.cont_moneda m ON g.moneda_id = m.id
            LEFT JOIN finanzas2.cont_tercero t ON g.proveedor_id = t.id
            LEFT JOIN finanzas2.cont_categoria_gasto cg ON g.categoria_gasto_id = cg.id
            LEFT JOIN finanzas2.cont_centro_costo cc ON g.centro_costo_id = cc.id
            LEFT JOIN finanzas2.cont_linea_negocio ln ON g.linea_negocio_id = ln.id
            LEFT JOIN finanzas2.fin_unidad_interna ui ON g.unidad_interna_id = ui.id
            LEFT JOIN finanzas2.cont_cuenta_financiera cfp ON g.cuenta_pago_id = cfp.id
            WHERE g.id = $1 AND g.empresa_id = $2
        """, id, empresa_id)
        if not row:
            raise HTTPException(404, "Gasto not found")
        gasto_dict = dict(row)
        lineas = await conn.fetch("""
            SELECT gl.*, c.nombre as categoria_nombre
            FROM finanzas2.cont_gasto_linea gl
            LEFT JOIN finanzas2.cont_categoria c ON gl.categoria_id = c.id
            WHERE gl.gasto_id = $1
        """, id)
        gasto_dict['lineas'] = [dict(l) for l in lineas]

        # Fetch pagos vinculados
        pago_id = gasto_dict.get('pago_id')
        numero = gasto_dict.get('numero')
        pagos_vinculados = []
        if pago_id or numero:
            conditions = []
            params = [empresa_id]
            idx = 2
            if pago_id:
                conditions.append(f"p.id = ${idx}")
                params.append(pago_id)
                idx += 1
            if numero:
                conditions.append(f"p.referencia = ${idx}")
                params.append(numero)
                idx += 1
            where_clause = " OR ".join(conditions)
            pagos_rows = await conn.fetch(f"""
                SELECT p.id, p.numero, p.fecha, p.monto_total,
                       p.cuenta_financiera_id, cf.nombre as cuenta_nombre,
                       cf.es_ficticia,
                       p.referencia, p.conciliado,
                       pd.medio_pago, pd.referencia as ref_operacion
                FROM finanzas2.cont_pago p
                LEFT JOIN finanzas2.cont_cuenta_financiera cf
                    ON p.cuenta_financiera_id = cf.id
                LEFT JOIN finanzas2.cont_pago_detalle pd
                    ON pd.pago_id = p.id
                WHERE p.empresa_id = $1
                  AND ({where_clause})
            """, *params)
            seen_ids = set()
            for pr in pagos_rows:
                if pr['id'] in seen_ids:
                    continue
                seen_ids.add(pr['id'])
                pagos_vinculados.append({
                    "id": pr['id'],
                    "numero": pr['numero'],
                    "fecha": pr['fecha'].isoformat() if pr['fecha'] else None,
                    "monto_total": float(pr['monto_total'] or 0),
                    "cuenta_id": pr['cuenta_financiera_id'],
                    "cuenta_nombre": pr['cuenta_nombre'],
                    "es_ficticia": pr['es_ficticia'] or False,
                    "medio_pago": pr['medio_pago'] or 'efectivo',
                    "ref_operacion": pr['ref_operacion'],
                    "conciliado": pr['conciliado'] or False,
                })

        total_pagado = sum(p['monto_total'] for p in pagos_vinculados)
        gasto_dict['pagos_vinculados'] = pagos_vinculados
        gasto_dict['total_pagado'] = round(total_pagado, 2)
        gasto_dict['saldo_pendiente'] = round(float(gasto_dict.get('total', 0)) - total_pagado, 2)
        return gasto_dict


@router.put("/gastos/{id}", response_model=Gasto)
async def update_gasto(id: int, data: GastoCreate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        async with conn.transaction():
            existing = await conn.fetchrow(
                "SELECT * FROM finanzas2.cont_gasto WHERE id = $1 AND empresa_id = $2", id, empresa_id)
            if not existing:
                raise HTTPException(404, "Gasto not found")
            if existing['pago_id']:
                raise HTTPException(400, "No se puede editar un gasto pagado")

            # Recalculate totals from lines
            isc_val = data.isc or 0.0
            base_gravada = 0.0
            base_no_gravada = 0.0
            for linea in data.lineas:
                if linea.igv_aplica:
                    base_gravada += linea.importe
                else:
                    base_no_gravada += linea.importe
            igv = round(base_gravada * 0.18, 2)
            subtotal = base_gravada + base_no_gravada
            total = round(subtotal + igv + isc_val, 2)
            if not data.lineas:
                base_gravada = data.base_gravada
                base_no_gravada = data.base_no_gravada
                igv = data.igv_sunat
                subtotal = base_gravada + base_no_gravada
                total = round(subtotal + igv + isc_val, 2)

            fecha_contable = data.fecha_contable or data.fecha
            tipo_asignacion = data.tipo_asignacion or 'directo'
            linea_negocio_id = data.linea_negocio_id if tipo_asignacion == 'directo' else None

            await conn.execute("""
                UPDATE finanzas2.cont_gasto SET
                    fecha = TO_DATE($1, 'YYYY-MM-DD'), fecha_contable = TO_DATE($2, 'YYYY-MM-DD'),
                    beneficiario_nombre = $3, proveedor_id = $4, moneda_id = $5,
                    subtotal = $6, igv = $7, total = $8,
                    tipo_documento = $9, numero_documento = $10, notas = $11,
                    tipo_comprobante_sunat = $12, base_gravada = $13, igv_sunat = $14,
                    base_no_gravada = $15, isc = $16, tipo_cambio = $17,
                    categoria_gasto_id = $18, tipo_asignacion = $19,
                    centro_costo_id = $20, linea_negocio_id = $21,
                    unidad_interna_id = $22, updated_at = NOW()
                WHERE id = $23 AND empresa_id = $24
            """, safe_date_param(data.fecha), safe_date_param(fecha_contable),
                data.beneficiario_nombre, data.proveedor_id, data.moneda_id,
                subtotal, igv, total,
                data.tipo_documento, data.numero_documento, data.notas,
                data.tipo_comprobante_sunat, base_gravada, igv, base_no_gravada, isc_val, data.tipo_cambio,
                data.categoria_gasto_id, tipo_asignacion,
                data.centro_costo_id, linea_negocio_id,
                data.unidad_interna_id, id, empresa_id)

            # Replace line items
            await conn.execute("DELETE FROM finanzas2.cont_gasto_linea WHERE gasto_id = $1", id)
            for linea in data.lineas:
                await conn.execute("""
                    INSERT INTO finanzas2.cont_gasto_linea
                    (empresa_id, gasto_id, categoria_id, descripcion, importe, igv_aplica, linea_negocio_id, centro_costo_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """, empresa_id, id, linea.categoria_id, linea.descripcion, linea.importe, linea.igv_aplica,
                    linea.linea_negocio_id, linea.centro_costo_id)

            # Return enriched gasto
            row = await conn.fetchrow("""
                SELECT g.*, m.codigo as moneda_codigo, m.simbolo as moneda_simbolo,
                       t.nombre as proveedor_nombre, cg.nombre as categoria_gasto_nombre,
                       cc.nombre as centro_costo_nombre,
                       ln.nombre as linea_negocio_nombre, ui.nombre as unidad_interna_nombre,
                       cfp.nombre as cuenta_pago_nombre
                FROM finanzas2.cont_gasto g
                LEFT JOIN finanzas2.cont_moneda m ON g.moneda_id = m.id
                LEFT JOIN finanzas2.cont_tercero t ON g.proveedor_id = t.id
                LEFT JOIN finanzas2.cont_categoria_gasto cg ON g.categoria_gasto_id = cg.id
                LEFT JOIN finanzas2.cont_centro_costo cc ON g.centro_costo_id = cc.id
                LEFT JOIN finanzas2.cont_linea_negocio ln ON g.linea_negocio_id = ln.id
                LEFT JOIN finanzas2.fin_unidad_interna ui ON g.unidad_interna_id = ui.id
                LEFT JOIN finanzas2.cont_cuenta_financiera cfp ON g.cuenta_pago_id = cfp.id
                WHERE g.id = $1
            """, id)
            gasto_dict = dict(row)
            lineas_rows = await conn.fetch("""
                SELECT gl.*, c.nombre as categoria_nombre
                FROM finanzas2.cont_gasto_linea gl
                LEFT JOIN finanzas2.cont_categoria c ON gl.categoria_id = c.id
                WHERE gl.gasto_id = $1
            """, id)
            gasto_dict['lineas'] = [dict(l) for l in lineas_rows]
            return gasto_dict


@router.delete("/gastos/{gasto_id}/pagos/{pago_id}")
async def delete_gasto_pago(gasto_id: int, pago_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        async with conn.transaction():
            # Verify gasto exists
            gasto = await conn.fetchrow(
                "SELECT * FROM finanzas2.cont_gasto WHERE id = $1 AND empresa_id = $2",
                gasto_id, empresa_id)
            if not gasto:
                raise HTTPException(404, "Gasto not found")

            # Verify pago exists and belongs to this gasto
            pago = await conn.fetchrow(
                "SELECT * FROM finanzas2.cont_pago WHERE id = $1 AND empresa_id = $2",
                pago_id, empresa_id)
            if not pago:
                raise HTTPException(404, "Pago not found")

            # Check pago belongs to gasto (via pago_id link or referencia)
            is_linked = (gasto['pago_id'] == pago_id or
                         pago['referencia'] == gasto['numero'])
            if not is_linked:
                raise HTTPException(400, "El pago no pertenece a este gasto")

            if pago.get('conciliado'):
                raise HTTPException(400, "No se puede eliminar un pago conciliado")

            # Reverse account balances from pago detalles
            detalles = await conn.fetch(
                "SELECT * FROM finanzas2.cont_pago_detalle WHERE pago_id = $1", pago_id)
            for detalle in detalles:
                # Reverse the egreso: add back to account
                await conn.execute(
                    "UPDATE finanzas2.cont_cuenta_financiera SET saldo_actual = saldo_actual + $1 WHERE id = $2",
                    detalle['monto'], detalle['cuenta_financiera_id'])

                # If fictitious account, register reversal INGRESO movement
                is_ficticia = await conn.fetchval(
                    "SELECT es_ficticia FROM finanzas2.cont_cuenta_financiera WHERE id=$1",
                    detalle['cuenta_financiera_id'])
                if is_ficticia:
                    await conn.execute("""
                        INSERT INTO finanzas2.fin_movimiento_cuenta
                        (cuenta_id, empresa_id, tipo, monto, descripcion, fecha, referencia_id, referencia_tipo)
                        VALUES ($1, $2, 'INGRESO', $3, $4, CURRENT_DATE, $5, 'GASTO_REVERSO')
                    """, detalle['cuenta_financiera_id'], empresa_id, detalle['monto'],
                        f"Reversión pago gasto {gasto['numero']}", str(gasto_id))

            # If no detalles, reverse using pago header
            if not detalles and pago['cuenta_financiera_id']:
                await conn.execute(
                    "UPDATE finanzas2.cont_cuenta_financiera SET saldo_actual = saldo_actual + $1 WHERE id = $2",
                    pago['monto_total'], pago['cuenta_financiera_id'])

            # Unlink from gasto FIRST (before deleting pago, due to FK constraint)
            if gasto['pago_id'] == pago_id:
                await conn.execute(
                    "UPDATE finanzas2.cont_gasto SET pago_id = NULL WHERE id = $1", gasto_id)

            # Clean up linked records
            await conn.execute("DELETE FROM finanzas2.cont_pago_detalle WHERE pago_id = $1", pago_id)
            await conn.execute("DELETE FROM finanzas2.cont_pago_aplicacion WHERE pago_id = $1", pago_id)

            # Delete related movimiento_tesoreria
            await conn.execute(
                "DELETE FROM finanzas2.cont_movimiento_tesoreria WHERE origen_tipo = 'gasto_directo' AND origen_id = $1 AND empresa_id = $2",
                gasto_id, empresa_id)

            # Delete the pago record
            await conn.execute("DELETE FROM finanzas2.cont_pago WHERE id = $1", pago_id)

            return {"message": "Pago eliminado y revertido exitosamente"}


@router.delete("/gastos/{id}")
async def delete_gasto(id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        async with conn.transaction():
            gasto = await conn.fetchrow("SELECT * FROM finanzas2.cont_gasto WHERE id = $1 AND empresa_id = $2", id, empresa_id)
            if not gasto:
                raise HTTPException(404, "Gasto not found")
            if gasto['pago_id']:
                raise HTTPException(400, "No se puede eliminar un gasto pagado. Primero elimine el pago.")
            await conn.execute("DELETE FROM finanzas2.cont_gasto WHERE id = $1 AND empresa_id = $2", id, empresa_id)
            return {"message": "Gasto deleted"}


# =====================
# ADELANTOS
# =====================
@router.get("/adelantos", response_model=List[Adelanto])
async def list_adelantos(
    empleado_id: Optional[int] = None,
    pagado: Optional[bool] = None,
    descontado: Optional[bool] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        conditions = ["a.empresa_id = $1"]
        params = [empresa_id]
        idx = 2
        if empleado_id:
            conditions.append(f"a.empleado_id = ${idx}"); params.append(empleado_id); idx += 1
        if pagado is not None:
            conditions.append(f"a.pagado = ${idx}"); params.append(pagado); idx += 1
        if descontado is not None:
            conditions.append(f"a.descontado = ${idx}"); params.append(descontado); idx += 1
        query = f"""
            SELECT a.*, t.nombre as empleado_nombre
            FROM finanzas2.cont_adelanto_empleado a
            LEFT JOIN finanzas2.cont_tercero t ON a.empleado_id = t.id
            WHERE {' AND '.join(conditions)}
            ORDER BY a.fecha DESC
        """
        rows = await conn.fetch(query, *params)
        return [dict(r) for r in rows]


@router.post("/adelantos", response_model=Adelanto)
async def create_adelanto(data: AdelantoCreate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        async with conn.transaction():
            pago_id = None
            if data.pagar and data.cuenta_financiera_id:
                emp_info = await conn.fetchrow("""
                    SELECT centro_costo_id, linea_negocio_id
                    FROM finanzas2.cont_empleado_detalle WHERE tercero_id = $1
                """, data.empleado_id)
                cc_id = emp_info['centro_costo_id'] if emp_info else None
                ln_id = emp_info['linea_negocio_id'] if emp_info else None
                pago_numero = await generate_pago_number(conn, 'egreso', empresa_id)
                pago = await conn.fetchrow("""
                    INSERT INTO finanzas2.cont_pago
                    (numero, tipo, fecha, cuenta_financiera_id, monto_total, notas, centro_costo_id, linea_negocio_id, empresa_id)
                    VALUES ($1, 'egreso', TO_DATE($2, 'YYYY-MM-DD'), $3, $4, $5, $6, $7, $8)
                    RETURNING id
                """, pago_numero, safe_date_param(data.fecha), data.cuenta_financiera_id, data.monto,
                    "Adelanto a empleado", cc_id, ln_id, empresa_id)
                pago_id = pago['id']
                await conn.execute("""
                    INSERT INTO finanzas2.cont_pago_detalle
                    (pago_id, cuenta_financiera_id, medio_pago, monto, empresa_id)
                    VALUES ($1, $2, $3, $4, $5)
                """, pago_id, data.cuenta_financiera_id, data.medio_pago, data.monto, empresa_id)
                await conn.execute("""
                    UPDATE finanzas2.cont_cuenta_financiera
                    SET saldo_actual = saldo_actual - $1 WHERE id = $2
                """, data.monto, data.cuenta_financiera_id)
            row = await conn.fetchrow("""
                INSERT INTO finanzas2.cont_adelanto_empleado
                (empleado_id, fecha, monto, motivo, pagado, pago_id, empresa_id)
                VALUES ($1, TO_DATE($2, 'YYYY-MM-DD'), $3, $4, $5, $6, $7)
                RETURNING *
            """, data.empleado_id, safe_date_param(data.fecha), data.monto, data.motivo,
                data.pagar, pago_id, empresa_id)
            if pago_id:
                await conn.execute("""
                    INSERT INTO finanzas2.cont_pago_aplicacion
                    (pago_id, tipo_documento, documento_id, monto_aplicado, empresa_id)
                    VALUES ($1, 'adelanto', $2, $3, $4)
                """, pago_id, row['id'], data.monto, empresa_id)
            emp = await conn.fetchrow("SELECT nombre FROM finanzas2.cont_tercero WHERE id = $1 AND empresa_id = $2", data.empleado_id, empresa_id)
            result = dict(row)
            result['empleado_nombre'] = emp['nombre'] if emp else None
            return result


@router.post("/adelantos/{id}/pagar", response_model=Adelanto)
async def pagar_adelanto(
    id: int,
    cuenta_financiera_id: int = Query(...),
    medio_pago: str = Query(default="efectivo"),
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        async with conn.transaction():
            adelanto = await conn.fetchrow("SELECT * FROM finanzas2.cont_adelanto_empleado WHERE id = $1 AND empresa_id = $2", id, empresa_id)
            if not adelanto:
                raise HTTPException(404, "Adelanto no encontrado")
            if adelanto['pagado']:
                raise HTTPException(400, "Este adelanto ya fue pagado")
            emp_info = await conn.fetchrow("SELECT centro_costo_id, linea_negocio_id FROM finanzas2.cont_empleado_detalle WHERE tercero_id = $1", adelanto['empleado_id'])
            cc_id = emp_info['centro_costo_id'] if emp_info else None
            ln_id = emp_info['linea_negocio_id'] if emp_info else None
            pago_numero = await generate_pago_number(conn, 'egreso', empresa_id)
            pago = await conn.fetchrow("""
                INSERT INTO finanzas2.cont_pago
                (numero, tipo, fecha, cuenta_financiera_id, monto_total, notas, centro_costo_id, linea_negocio_id, empresa_id)
                VALUES ($1, 'egreso', CURRENT_DATE, $2, $3, $4, $5, $6, $7)
                RETURNING id
            """, pago_numero, cuenta_financiera_id, adelanto['monto'],
                "Pago de adelanto a empleado", cc_id, ln_id, empresa_id)
            pago_id = pago['id']
            await conn.execute("""
                INSERT INTO finanzas2.cont_pago_detalle
                (pago_id, cuenta_financiera_id, medio_pago, monto, empresa_id)
                VALUES ($1, $2, $3, $4, $5)
            """, pago_id, cuenta_financiera_id, medio_pago, adelanto['monto'], empresa_id)
            await conn.execute("UPDATE finanzas2.cont_cuenta_financiera SET saldo_actual = saldo_actual - $1 WHERE id = $2", adelanto['monto'], cuenta_financiera_id)
            row = await conn.fetchrow("UPDATE finanzas2.cont_adelanto_empleado SET pagado = TRUE, pago_id = $1 WHERE id = $2 RETURNING *", pago_id, id)
            await conn.execute("""
                INSERT INTO finanzas2.cont_pago_aplicacion
                (pago_id, tipo_documento, documento_id, monto_aplicado, empresa_id)
                VALUES ($1, 'adelanto', $2, $3, $4)
            """, pago_id, id, adelanto['monto'], empresa_id)
            emp = await conn.fetchrow("SELECT nombre FROM finanzas2.cont_tercero WHERE id = $1 AND empresa_id = $2", row['empleado_id'], empresa_id)
            result = dict(row)
            result['empleado_nombre'] = emp['nombre'] if emp else None
            return result


@router.put("/adelantos/{id}", response_model=Adelanto)
async def update_adelanto(id: int, data: AdelantoCreate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        existing = await conn.fetchrow("SELECT * FROM finanzas2.cont_adelanto_empleado WHERE id = $1 AND empresa_id = $2", id, empresa_id)
        if not existing:
            raise HTTPException(404, "Adelanto no encontrado")
        if existing['pagado'] or existing['descontado']:
            raise HTTPException(400, "No se puede editar un adelanto pagado o descontado")
        row = await conn.fetchrow("""
            UPDATE finanzas2.cont_adelanto_empleado
            SET empleado_id = $1, fecha = $2, monto = $3, motivo = $4
            WHERE id = $5
            RETURNING *
        """, data.empleado_id, data.fecha, data.monto, data.motivo, id)
        emp = await conn.fetchrow("SELECT nombre FROM finanzas2.cont_tercero WHERE id = $1 AND empresa_id = $2", row['empleado_id'], empresa_id)
        result = dict(row)
        result['empleado_nombre'] = emp['nombre'] if emp else None
        return result


@router.delete("/adelantos/{id}")
async def delete_adelanto(id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        existing = await conn.fetchrow("SELECT * FROM finanzas2.cont_adelanto_empleado WHERE id = $1 AND empresa_id = $2", id, empresa_id)
        if not existing:
            raise HTTPException(404, "Adelanto no encontrado")
        if existing['pagado']:
            raise HTTPException(400, "No se puede eliminar un adelanto pagado. Primero anule el pago.")
        if existing['descontado']:
            raise HTTPException(400, "No se puede eliminar un adelanto ya descontado en planilla")
        await conn.execute("DELETE FROM finanzas2.cont_adelanto_empleado WHERE id = $1 AND empresa_id = $2", id, empresa_id)
        return {"message": "Adelanto eliminado"}
