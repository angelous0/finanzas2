"""
Contabilidad de doble partida - Servicio de posting y reportes.
Genera asientos automáticos para FPROV, GASTO, PAGO.
"""
import logging
from fastapi import HTTPException

logger = logging.getLogger("contabilidad")


async def get_config_contable(conn, empresa_id: int) -> dict:
    """Get accounting config with account codes resolved."""
    row = await conn.fetchrow(
        "SELECT * FROM finanzas2.cont_config_empresa WHERE empresa_id = $1", empresa_id
    )
    if not row:
        raise HTTPException(400, "Config contable no encontrada. Ejecute primero el seed de cuentas.")
    cfg = dict(row)

    # Resolve ids to account codes
    ids = [v for v in [cfg.get('cta_gastos_default_id'), cfg.get('cta_igv_default_id'),
                       cfg.get('cta_xpagar_default_id'), cfg.get('cta_otrib_default_id')] if v]
    code_map = {}
    if ids:
        rows = await conn.fetch("SELECT id, codigo FROM finanzas2.cont_cuenta WHERE id = ANY($1)", ids)
        code_map = {r['id']: r['codigo'] for r in rows}

    cfg['_code'] = code_map
    return cfg


async def check_periodo_cerrado(conn, empresa_id: int, fecha):
    """Raise if the period is closed."""
    closed = await conn.fetchval("""
        SELECT cerrado FROM finanzas2.cont_periodo_cerrado
        WHERE empresa_id = $1 AND anio = $2 AND mes = $3
    """, empresa_id, fecha.year, fecha.month)
    if closed:
        raise HTTPException(400, f"Periodo {fecha.year}-{fecha.month:02d} está cerrado.")


async def upsert_asiento(conn, empresa_id, fecha_contable, origen_tipo, origen_id,
                          origen_numero, glosa, moneda, tipo_cambio, lineas):
    """Create or replace an asiento with its lines. Returns asiento row."""
    # Validate balance
    total_debe = round(sum(l['debe'] for l in lineas), 2)
    total_haber = round(sum(l['haber'] for l in lineas), 2)
    if abs(total_debe - total_haber) > 0.01:
        raise HTTPException(400, f"Asiento descuadrado: Debe={total_debe}, Haber={total_haber}")

    if not lineas:
        raise HTTPException(400, "Asiento sin líneas")

    await check_periodo_cerrado(conn, empresa_id, fecha_contable)

    # Check if exists and is posteado
    existing = await conn.fetchrow("""
        SELECT id, estado FROM finanzas2.cont_asiento
        WHERE empresa_id = $1 AND origen_tipo = $2 AND origen_id = $3
    """, empresa_id, origen_tipo, origen_id)

    if existing and existing['estado'] == 'posteado':
        raise HTTPException(400, "El asiento ya está posteado. Anule primero para regenerar.")

    if existing:
        # Delete old and recreate
        await conn.execute("DELETE FROM finanzas2.cont_asiento WHERE id = $1", existing['id'])

    asiento = await conn.fetchrow("""
        INSERT INTO finanzas2.cont_asiento
        (empresa_id, fecha_contable, origen_tipo, origen_id, origen_numero, glosa, moneda, tipo_cambio, estado)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'borrador')
        RETURNING *
    """, empresa_id, fecha_contable, origen_tipo, origen_id, origen_numero, glosa, moneda, tipo_cambio)

    asiento_id = asiento['id']
    tc = float(tipo_cambio)

    for l in lineas:
        debe = round(float(l['debe']), 2)
        haber = round(float(l['haber']), 2)
        debe_base = round(debe * tc, 2)
        haber_base = round(haber * tc, 2)
        await conn.execute("""
            INSERT INTO finanzas2.cont_asiento_linea
            (asiento_id, empresa_id, cuenta_id, tercero_id, centro_costo_id, presupuesto_id,
             debe, haber, debe_base, haber_base, glosa)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """, asiento_id, empresa_id, l['cuenta_id'], l.get('tercero_id'),
            l.get('centro_costo_id'), l.get('presupuesto_id'),
            debe, haber, debe_base, haber_base, l.get('glosa'))

    return asiento


async def resolve_cuenta_id(conn, empresa_id, codigo):
    """Resolve account code to id."""
    cid = await conn.fetchval(
        "SELECT id FROM finanzas2.cont_cuenta WHERE empresa_id = $1 AND codigo = $2",
        empresa_id, codigo)
    return cid


async def generar_asiento_fprov(conn, empresa_id: int, factura_id: int):
    """Generate journal entry for a provider invoice."""
    cfg = await get_config_contable(conn, empresa_id)

    fp = await conn.fetchrow("""
        SELECT fp.*, t.id as tercero_id, t.nombre as proveedor_nombre,
               m.codigo as moneda_codigo
        FROM finanzas2.cont_factura_proveedor fp
        LEFT JOIN finanzas2.cont_tercero t ON fp.proveedor_id = t.id
        LEFT JOIN finanzas2.cont_moneda m ON fp.moneda_id = m.id
        WHERE fp.id = $1 AND fp.empresa_id = $2
    """, factura_id, empresa_id)
    if not fp:
        raise HTTPException(404, "Factura no encontrada")

    fecha = fp['fecha_contable'] or fp['fecha_factura']
    moneda = 'PEN' if fp.get('moneda_codigo') != 'USD' else 'USD'
    tc = float(fp['tipo_cambio'] or 1)
    total = round(float(fp['total'] or 0), 2)
    tercero_id = fp['tercero_id']
    base_gravada = round(float(fp['base_gravada'] or 0), 2)
    igv_sunat = round(float(fp['igv_sunat'] or 0), 2)
    base_no_gravada = round(float(fp['base_no_gravada'] or 0), 2)

    # Get lines to determine account per category (use first category with account, else default)
    fp_lineas = await conn.fetch("""
        SELECT fpl.*, cat.cuenta_gasto_id
        FROM finanzas2.cont_factura_proveedor_linea fpl
        LEFT JOIN finanzas2.cont_categoria cat ON fpl.categoria_id = cat.id
        WHERE fpl.factura_id = $1
    """, factura_id)

    lineas = []
    default_gastos_id = cfg.get('cta_gastos_default_id')
    cta_igv_id = cfg.get('cta_igv_default_id')
    cta_xpagar_id = cfg.get('cta_xpagar_default_id')

    # Determine gasto account: use category account if all lines share the same, else default
    cta_gasto_id = default_gastos_id
    unique_accounts = set()
    for fl in fp_lineas:
        if fl['cuenta_gasto_id']:
            unique_accounts.add(fl['cuenta_gasto_id'])
    if len(unique_accounts) == 1:
        cta_gasto_id = unique_accounts.pop()

    if not cta_gasto_id:
        raise HTTPException(400, "Sin cuenta de gasto configurada")

    # Debe: base gravada + no gravada
    monto_gasto = base_gravada + base_no_gravada
    if monto_gasto > 0:
        centro_costo_id = fp_lineas[0].get('centro_costo_id') if len(fp_lineas) == 1 else None
        presupuesto_id = fp_lineas[0].get('presupuesto_id') if len(fp_lineas) == 1 else None
        lineas.append({
            'cuenta_id': cta_gasto_id,
            'tercero_id': tercero_id,
            'centro_costo_id': centro_costo_id,
            'presupuesto_id': presupuesto_id,
            'debe': monto_gasto, 'haber': 0,
            'glosa': f"Compra {fp['numero']}"
        })

    # Debe: IGV
    if igv_sunat > 0 and cta_igv_id:
        lineas.append({
            'cuenta_id': cta_igv_id,
            'tercero_id': tercero_id,
            'debe': igv_sunat, 'haber': 0,
            'glosa': f"IGV {fp['numero']}"
        })

    # Haber: CxP por total
    if not cta_xpagar_id:
        raise HTTPException(400, "Sin cuenta por pagar default configurada")

    lineas.append({
        'cuenta_id': cta_xpagar_id,
        'tercero_id': tercero_id,
        'debe': 0, 'haber': total,
        'glosa': f"CxP {fp['numero']}"
    })

    glosa = f"Factura proveedor {fp['numero']} - {fp.get('proveedor_nombre', '')}"
    return await upsert_asiento(conn, empresa_id, fecha, 'FPROV', factura_id,
                                 fp['numero'], glosa, moneda, tc, lineas)


async def generar_asiento_gasto(conn, empresa_id: int, gasto_id: int):
    """Generate journal entry for an expense."""
    cfg = await get_config_contable(conn, empresa_id)

    g = await conn.fetchrow("""
        SELECT g.*, t.id as tercero_id, t.nombre as proveedor_nombre,
               m.codigo as moneda_codigo
        FROM finanzas2.cont_gasto g
        LEFT JOIN finanzas2.cont_tercero t ON g.proveedor_id = t.id
        LEFT JOIN finanzas2.cont_moneda m ON g.moneda_id = m.id
        WHERE g.id = $1 AND g.empresa_id = $2
    """, gasto_id, empresa_id)
    if not g:
        raise HTTPException(404, "Gasto no encontrado")

    fecha = g['fecha_contable'] or g['fecha']
    moneda = 'PEN' if g.get('moneda_codigo') != 'USD' else 'USD'
    tc = float(g['tipo_cambio'] or 1)
    total = round(float(g['total'] or 0), 2)
    tercero_id = g['tercero_id']
    base_gravada = round(float(g['base_gravada'] or 0), 2)
    igv_sunat = round(float(g['igv_sunat'] or 0), 2)
    base_no_gravada = round(float(g['base_no_gravada'] or 0), 2)

    g_lineas = await conn.fetch("""
        SELECT gl.*, cat.cuenta_gasto_id
        FROM finanzas2.cont_gasto_linea gl
        LEFT JOIN finanzas2.cont_categoria cat ON gl.categoria_id = cat.id
        WHERE gl.gasto_id = $1
    """, gasto_id)

    lineas = []
    default_gastos_id = cfg.get('cta_gastos_default_id')
    cta_igv_id = cfg.get('cta_igv_default_id')
    cta_xpagar_id = cfg.get('cta_xpagar_default_id')

    # Determine gasto account
    cta_gasto_id = default_gastos_id
    unique_accounts = set()
    for gl in g_lineas:
        if gl['cuenta_gasto_id']:
            unique_accounts.add(gl['cuenta_gasto_id'])
    if len(unique_accounts) == 1:
        cta_gasto_id = unique_accounts.pop()

    if not cta_gasto_id:
        raise HTTPException(400, "Sin cuenta de gasto configurada")

    monto_gasto = base_gravada + base_no_gravada
    if monto_gasto > 0:
        centro_costo_id = g_lineas[0].get('centro_costo_id') if len(g_lineas) == 1 else None
        presupuesto_id = g_lineas[0].get('presupuesto_id') if len(g_lineas) == 1 else None
        lineas.append({
            'cuenta_id': cta_gasto_id,
            'tercero_id': tercero_id,
            'centro_costo_id': centro_costo_id,
            'presupuesto_id': presupuesto_id,
            'debe': monto_gasto, 'haber': 0,
            'glosa': f"Gasto {g['numero_documento']}"
        })

    if igv_sunat > 0 and cta_igv_id:
        lineas.append({
            'cuenta_id': cta_igv_id,
            'tercero_id': tercero_id,
            'debe': igv_sunat, 'haber': 0,
            'glosa': f"IGV {g['numero_documento']}"
        })

    # Haber: check if paid (has pago_id) => Banco/Caja; else => CxP
    has_pago = g.get('pago_id') is not None
    if has_pago:
        # Find the payment's financial account and its accounting account
        pago = await conn.fetchrow("""
            SELECT p.cuenta_financiera_id, cf.cuenta_contable_id
            FROM finanzas2.cont_pago p
            LEFT JOIN finanzas2.cont_cuenta_financiera cf ON p.cuenta_financiera_id = cf.id
            WHERE p.id = $1
        """, g['pago_id'])
        haber_cuenta_id = pago['cuenta_contable_id'] if pago and pago['cuenta_contable_id'] else None
        if not haber_cuenta_id:
            # Fallback: try to find Caja account
            haber_cuenta_id = await resolve_cuenta_id(conn, empresa_id, '101')
        if not haber_cuenta_id:
            raise HTTPException(400, "Cuenta financiera sin cuenta contable asociada")
        haber_glosa = f"Pago {g['numero_documento']}"
    else:
        haber_cuenta_id = cta_xpagar_id
        if not haber_cuenta_id:
            raise HTTPException(400, "Sin cuenta por pagar default configurada")
        haber_glosa = f"CxP {g['numero_documento']}"

    lineas.append({
        'cuenta_id': haber_cuenta_id,
        'tercero_id': tercero_id,
        'debe': 0, 'haber': total,
        'glosa': haber_glosa
    })

    glosa = f"Gasto {g['numero_documento']} - {g.get('proveedor_nombre', '')}"
    return await upsert_asiento(conn, empresa_id, fecha, 'GASTO', gasto_id,
                                 g['numero_documento'], glosa, moneda, tc, lineas)


async def generar_asiento_pago(conn, empresa_id: int, pago_id: int):
    """Generate journal entry for a payment applied to invoices/letras."""
    cfg = await get_config_contable(conn, empresa_id)
    cta_xpagar_id = cfg.get('cta_xpagar_default_id')

    pago = await conn.fetchrow("""
        SELECT p.*, cf.cuenta_contable_id, m.codigo as moneda_codigo
        FROM finanzas2.cont_pago p
        LEFT JOIN finanzas2.cont_cuenta_financiera cf ON p.cuenta_financiera_id = cf.id
        LEFT JOIN finanzas2.cont_moneda m ON p.moneda_id = m.id
        WHERE p.id = $1 AND p.empresa_id = $2
    """, pago_id, empresa_id)
    if not pago:
        raise HTTPException(404, "Pago no encontrado")

    fecha = pago['fecha']
    moneda = 'PEN' if pago.get('moneda_codigo') != 'USD' else 'USD'
    tc = 1.0  # pagos typically in same currency
    total = round(float(pago['monto_total'] or 0), 2)

    haber_cuenta_id = pago['cuenta_contable_id']
    if not haber_cuenta_id:
        haber_cuenta_id = await resolve_cuenta_id(conn, empresa_id, '101')
    if not haber_cuenta_id:
        raise HTTPException(400, "Cuenta financiera sin cuenta contable asociada")

    if not cta_xpagar_id:
        raise HTTPException(400, "Sin cuenta por pagar default configurada")

    # Get aplicaciones for tercero info
    aplicaciones = await conn.fetch("""
        SELECT pa.*, fp.proveedor_id
        FROM finanzas2.cont_pago_aplicacion pa
        LEFT JOIN finanzas2.cont_factura_proveedor fp ON pa.tipo_documento = 'factura' AND pa.documento_id = fp.id
        WHERE pa.pago_id = $1
    """, pago_id)

    tercero_id = None
    for ap in aplicaciones:
        if ap['proveedor_id']:
            tercero_id = ap['proveedor_id']
            break

    lineas = [
        {
            'cuenta_id': cta_xpagar_id,
            'tercero_id': tercero_id,
            'debe': total, 'haber': 0,
            'glosa': f"Pago {pago['numero']}"
        },
        {
            'cuenta_id': haber_cuenta_id,
            'tercero_id': tercero_id,
            'debe': 0, 'haber': total,
            'glosa': f"Banco/Caja {pago['numero']}"
        }
    ]

    glosa = f"Pago {pago['numero']} ({pago['tipo']})"
    return await upsert_asiento(conn, empresa_id, fecha, 'PAGO', pago_id,
                                 pago['numero'], glosa, moneda, tc, lineas)


# ── Report Helpers ──

async def reporte_mayor(conn, empresa_id: int, cuenta_id: int = None,
                         desde=None, hasta=None):
    """Libro Mayor: movements per account."""
    conditions = ["a.empresa_id = $1", "a.estado = 'posteado'"]
    params = [empresa_id]
    idx = 2

    if cuenta_id:
        conditions.append(f"al.cuenta_id = ${idx}")
        params.append(cuenta_id)
        idx += 1
    if desde:
        conditions.append(f"a.fecha_contable >= ${idx}")
        params.append(desde)
        idx += 1
    if hasta:
        conditions.append(f"a.fecha_contable <= ${idx}")
        params.append(hasta)
        idx += 1

    rows = await conn.fetch(f"""
        SELECT al.cuenta_id, cc.codigo as cuenta_codigo, cc.nombre as cuenta_nombre,
               a.fecha_contable, a.origen_tipo, a.origen_numero, a.glosa as asiento_glosa,
               al.debe, al.haber, al.debe_base, al.haber_base, al.glosa as linea_glosa,
               t.nombre as tercero_nombre
        FROM finanzas2.cont_asiento_linea al
        JOIN finanzas2.cont_asiento a ON al.asiento_id = a.id
        JOIN finanzas2.cont_cuenta cc ON al.cuenta_id = cc.id
        LEFT JOIN finanzas2.cont_tercero t ON al.tercero_id = t.id
        WHERE {' AND '.join(conditions)}
        ORDER BY cc.codigo, a.fecha_contable, a.id
    """, *params)

    return [dict(r) for r in rows]


async def reporte_balance(conn, empresa_id: int, hasta=None):
    """Balance General: ACTIVO / PASIVO / PATRIMONIO."""
    conditions = ["a.empresa_id = $1", "a.estado = 'posteado'"]
    params = [empresa_id]
    idx = 2
    if hasta:
        conditions.append(f"a.fecha_contable <= ${idx}")
        params.append(hasta)
        idx += 1

    rows = await conn.fetch(f"""
        SELECT cc.tipo, cc.codigo, cc.nombre,
               COALESCE(SUM(al.debe_base), 0) as total_debe,
               COALESCE(SUM(al.haber_base), 0) as total_haber
        FROM finanzas2.cont_asiento_linea al
        JOIN finanzas2.cont_asiento a ON al.asiento_id = a.id
        JOIN finanzas2.cont_cuenta cc ON al.cuenta_id = cc.id
        WHERE {' AND '.join(conditions)}
          AND cc.tipo IN ('ACTIVO','PASIVO','PATRIMONIO','IMPUESTO')
        GROUP BY cc.tipo, cc.codigo, cc.nombre
        ORDER BY cc.codigo
    """, *params)

    result = {'ACTIVO': [], 'PASIVO': [], 'PATRIMONIO': []}
    totals = {'ACTIVO': 0, 'PASIVO': 0, 'PATRIMONIO': 0}
    for r in rows:
        tipo = r['tipo']
        debe = float(r['total_debe'])
        haber = float(r['total_haber'])
        # IMPUESTO accounts with debit balance (like IGV crédito) go to ACTIVO
        if tipo == 'IMPUESTO':
            saldo = debe - haber
            bucket = 'ACTIVO' if saldo >= 0 else 'PASIVO'
        elif tipo == 'ACTIVO':
            saldo = debe - haber
            bucket = 'ACTIVO'
        else:
            saldo = haber - debe
            bucket = tipo
        entry = {'codigo': r['codigo'], 'nombre': r['nombre'], 'tipo_original': tipo, 'debe': debe, 'haber': haber, 'saldo': round(saldo, 2)}
        result[bucket].append(entry)
        totals[bucket] += saldo

    return {
        'cuentas': result,
        'totales': {k: round(v, 2) for k, v in totals.items()},
        'cuadra': abs(totals['ACTIVO'] - totals['PASIVO'] - totals['PATRIMONIO']) < 0.02
    }


async def reporte_pnl(conn, empresa_id: int, desde=None, hasta=None):
    """Estado de Resultados: INGRESO / GASTO / COSTO."""
    conditions = ["a.empresa_id = $1", "a.estado = 'posteado'"]
    params = [empresa_id]
    idx = 2
    if desde:
        conditions.append(f"a.fecha_contable >= ${idx}")
        params.append(desde)
        idx += 1
    if hasta:
        conditions.append(f"a.fecha_contable <= ${idx}")
        params.append(hasta)
        idx += 1

    rows = await conn.fetch(f"""
        SELECT cc.tipo, cc.codigo, cc.nombre,
               COALESCE(SUM(al.debe_base), 0) as total_debe,
               COALESCE(SUM(al.haber_base), 0) as total_haber
        FROM finanzas2.cont_asiento_linea al
        JOIN finanzas2.cont_asiento a ON al.asiento_id = a.id
        JOIN finanzas2.cont_cuenta cc ON al.cuenta_id = cc.id
        WHERE {' AND '.join(conditions)}
          AND cc.tipo IN ('INGRESO','GASTO','COSTO')
        GROUP BY cc.tipo, cc.codigo, cc.nombre
        ORDER BY cc.codigo
    """, *params)

    result = {'INGRESO': [], 'GASTO': [], 'COSTO': []}
    totals = {'INGRESO': 0, 'GASTO': 0, 'COSTO': 0}
    for r in rows:
        tipo = r['tipo']
        debe = float(r['total_debe'])
        haber = float(r['total_haber'])
        saldo = haber - debe if tipo == 'INGRESO' else debe - haber
        entry = {'codigo': r['codigo'], 'nombre': r['nombre'], 'debe': debe, 'haber': haber, 'saldo': round(saldo, 2)}
        result[tipo].append(entry)
        totals[tipo] += saldo

    total_ingresos = totals['INGRESO']
    total_egresos = totals['GASTO'] + totals['COSTO']
    return {
        'cuentas': result,
        'totales': {k: round(v, 2) for k, v in totals.items()},
        'utilidad_neta': round(total_ingresos - total_egresos, 2)
    }
