"""
Libro Analítico - Historial de entradas y salidas por dimensión analítica
(línea de negocio, marca, centro de costo, categoría)
"""
from fastapi import APIRouter, Depends, Query
from datetime import date, datetime
from typing import Optional
import csv
import io
from starlette.responses import StreamingResponse

from database import get_pool
from dependencies import get_empresa_id

router = APIRouter(prefix="/libro-analitico", tags=["Libro Analítico"])


async def _build_movimientos(conn, empresa_id, dimension, dimension_id, fd, fh):
    """Build unified list of movements for the given analytical dimension."""
    movimientos = []

    if dimension == 'linea_negocio':
        # 1. Distributions (ventas, pagos factura, pagos letra, cobranzas)
        rows = await conn.fetch("""
            SELECT da.id, da.origen_tipo, da.origen_id, da.monto, da.fecha,
                   da.categoria_id, c.nombre as categoria_nombre
            FROM cont_distribucion_analitica da
            LEFT JOIN cont_categoria c ON da.categoria_id = c.id
            WHERE da.empresa_id = $1 AND da.linea_negocio_id = $2
              AND da.fecha BETWEEN $3 AND $4
            ORDER BY da.fecha, da.id
        """, empresa_id, dimension_id, fd, fh)

        for r in rows:
            ot = r['origen_tipo']
            desc, ref_tipo, ref_id = await _resolve_origen(conn, ot, r['origen_id'], empresa_id)
            es_entrada = ot in ('venta_pos_ingreso', 'cobranza_cxc')
            movimientos.append({
                "fecha": str(r['fecha']),
                "tipo": _label_tipo(ot),
                "descripcion": desc,
                "entrada": float(r['monto']) if es_entrada else 0,
                "salida": float(r['monto']) if not es_entrada else 0,
                "ref_tipo": ref_tipo,
                "ref_id": ref_id,
                "categoria": r['categoria_nombre'],
            })

        # 2. Direct expenses
        gastos = await conn.fetch("""
            SELECT g.id, g.notas as descripcion, g.total, g.fecha, cg.nombre as cat_nombre
            FROM cont_gasto g
            LEFT JOIN cont_categoria_gasto cg ON g.categoria_gasto_id = cg.id
            WHERE g.empresa_id = $1 AND g.linea_negocio_id = $2
              AND g.tipo_asignacion = 'directo'
              AND g.fecha BETWEEN $3 AND $4
            ORDER BY g.fecha, g.id
        """, empresa_id, dimension_id, fd, fh)

        for g in gastos:
            movimientos.append({
                "fecha": str(g['fecha']),
                "tipo": "Gasto Directo",
                "descripcion": f"{g['cat_nombre'] or 'Gasto'}: {g['descripcion'] or ''}".strip(': '),
                "entrada": 0,
                "salida": float(g['total']),
                "ref_tipo": "gasto",
                "ref_id": g['id'],
                "categoria": g['cat_nombre'],
            })

        # 3. Prorated expenses
        prorrateos = await conn.fetch("""
            SELECT p.id, p.monto, g.fecha, g.notas as descripcion, cg.nombre as cat_nombre, g.id as gasto_id
            FROM cont_prorrateo_gasto p
            JOIN cont_gasto g ON p.gasto_id = g.id
            LEFT JOIN cont_categoria_gasto cg ON g.categoria_gasto_id = cg.id
            WHERE g.empresa_id = $1 AND p.linea_negocio_id = $2
              AND g.fecha BETWEEN $3 AND $4
            ORDER BY g.fecha, p.id
        """, empresa_id, dimension_id, fd, fh)

        for p in prorrateos:
            movimientos.append({
                "fecha": str(p['fecha']),
                "tipo": "Gasto Prorrateado",
                "descripcion": f"{p['cat_nombre'] or 'Gasto'}: {p['descripcion'] or ''}".strip(': '),
                "entrada": 0,
                "salida": float(p['monto']),
                "ref_tipo": "gasto",
                "ref_id": p['gasto_id'],
                "categoria": p['cat_nombre'],
            })

    elif dimension == 'marca':
        # Ventas by marca
        ventas = await conn.fetch("""
            SELECT v.odoo_id, v.name, v.date_order::date as fecha,
                   COALESCE(SUM(l.price_subtotal_incl), 0) as total
            FROM cont_venta_pos_linea l
            JOIN cont_venta_pos v ON l.venta_pos_id = v.id
            JOIN cont_venta_pos_estado e ON e.odoo_order_id = v.odoo_id AND e.empresa_id = v.empresa_id
            JOIN cont_marca m ON UPPER(l.marca) = UPPER(m.nombre) AND m.empresa_id = v.empresa_id
            WHERE v.empresa_id = $1 AND m.id = $2
              AND v.date_order::date BETWEEN $3 AND $4
              AND e.estado_local IN ('confirmada', 'credito')
            GROUP BY v.odoo_id, v.name, v.date_order
            ORDER BY v.date_order
        """, empresa_id, dimension_id, fd, fh)

        for v in ventas:
            movimientos.append({
                "fecha": str(v['fecha']),
                "tipo": "Venta POS",
                "descripcion": v['name'],
                "entrada": float(v['total']),
                "salida": 0,
                "ref_tipo": "venta_pos",
                "ref_id": v['odoo_id'],
                "categoria": None,
            })

    elif dimension == 'centro_costo':
        # Distributions by centro_costo
        rows = await conn.fetch("""
            SELECT da.id, da.origen_tipo, da.origen_id, da.monto, da.fecha
            FROM cont_distribucion_analitica da
            WHERE da.empresa_id = $1 AND da.centro_costo_id = $2
              AND da.fecha BETWEEN $3 AND $4
            ORDER BY da.fecha, da.id
        """, empresa_id, dimension_id, fd, fh)

        for r in rows:
            ot = r['origen_tipo']
            desc, ref_tipo, ref_id = await _resolve_origen(conn, ot, r['origen_id'], empresa_id)
            es_entrada = ot in ('venta_pos_ingreso', 'cobranza_cxc')
            movimientos.append({
                "fecha": str(r['fecha']),
                "tipo": _label_tipo(ot),
                "descripcion": desc,
                "entrada": float(r['monto']) if es_entrada else 0,
                "salida": float(r['monto']) if not es_entrada else 0,
                "ref_tipo": ref_tipo,
                "ref_id": ref_id,
                "categoria": None,
            })

        # Direct expenses by centro_costo
        gastos = await conn.fetch("""
            SELECT g.id, g.notas as descripcion, g.total, g.fecha, cg.nombre as cat_nombre
            FROM cont_gasto g
            LEFT JOIN cont_categoria_gasto cg ON g.categoria_gasto_id = cg.id
            WHERE g.empresa_id = $1 AND g.centro_costo_id = $2
              AND g.fecha BETWEEN $3 AND $4
            ORDER BY g.fecha, g.id
        """, empresa_id, dimension_id, fd, fh)

        for g in gastos:
            movimientos.append({
                "fecha": str(g['fecha']),
                "tipo": "Gasto",
                "descripcion": f"{g['cat_nombre'] or 'Gasto'}: {g['descripcion'] or ''}".strip(': '),
                "entrada": 0,
                "salida": float(g['total']),
                "ref_tipo": "gasto",
                "ref_id": g['id'],
                "categoria": g['cat_nombre'],
            })

    elif dimension == 'categoria':
        # Distributions by categoria
        rows = await conn.fetch("""
            SELECT da.id, da.origen_tipo, da.origen_id, da.monto, da.fecha,
                   ln.nombre as ln_nombre
            FROM cont_distribucion_analitica da
            LEFT JOIN cont_linea_negocio ln ON da.linea_negocio_id = ln.id
            WHERE da.empresa_id = $1 AND da.categoria_id = $2
              AND da.fecha BETWEEN $3 AND $4
            ORDER BY da.fecha, da.id
        """, empresa_id, dimension_id, fd, fh)

        for r in rows:
            ot = r['origen_tipo']
            desc, ref_tipo, ref_id = await _resolve_origen(conn, ot, r['origen_id'], empresa_id)
            es_entrada = ot in ('venta_pos_ingreso', 'cobranza_cxc')
            movimientos.append({
                "fecha": str(r['fecha']),
                "tipo": _label_tipo(ot),
                "descripcion": desc,
                "entrada": float(r['monto']) if es_entrada else 0,
                "salida": float(r['monto']) if not es_entrada else 0,
                "ref_tipo": ref_tipo,
                "ref_id": ref_id,
                "categoria": r['ln_nombre'],
            })

    # Sort by date then by id-ish order
    movimientos.sort(key=lambda m: m['fecha'])

    # Calculate running balance
    saldo = 0
    for m in movimientos:
        saldo += m['entrada'] - m['salida']
        m['saldo'] = round(saldo, 2)

    return movimientos


async def _resolve_origen(conn, origen_tipo, origen_id, empresa_id):
    """Resolve document description and reference link from origen."""
    try:
        if origen_tipo == 'venta_pos_ingreso':
            v = await conn.fetchrow(
                "SELECT name, id FROM cont_venta_pos WHERE odoo_id = $1", origen_id)
            if v:
                return f"Venta {v['name']}", "venta_pos", v['id']
            return f"Venta #{origen_id}", "venta_pos", origen_id

        elif origen_tipo == 'cobranza_cxc':
            mt = await conn.fetchrow(
                "SELECT numero FROM cont_movimiento_tesoreria WHERE id = $1", origen_id)
            if mt:
                return f"Cobranza {mt['numero']}", "pago", origen_id
            return f"Cobranza #{origen_id}", "pago", origen_id

        elif origen_tipo == 'pago_egreso':
            mt = await conn.fetchrow(
                "SELECT numero FROM cont_movimiento_tesoreria WHERE id = $1", origen_id)
            # Find which factura this payment was applied to
            app = await conn.fetchrow("""
                SELECT fp.numero FROM cont_pago_aplicacion pa
                JOIN cont_factura_proveedor fp ON pa.documento_id = fp.id
                WHERE pa.movimiento_tesoreria_id = $1 AND pa.tipo_documento = 'factura'
                LIMIT 1
            """, origen_id)
            desc = f"Pago {mt['numero'] if mt else f'#{origen_id}'}"
            if app:
                desc += f" - {app['numero']}"
            return desc, "pago", origen_id

        elif origen_tipo == 'pago_letra':
            mt = await conn.fetchrow(
                "SELECT numero FROM cont_movimiento_tesoreria WHERE id = $1", origen_id)
            # Find letra and factura
            app = await conn.fetchrow("""
                SELECT l.numero as letra_num, fp.numero as fp_num
                FROM cont_pago_aplicacion pa
                JOIN cont_letra l ON pa.documento_id = l.id
                LEFT JOIN cont_factura_proveedor fp ON l.factura_id = fp.id
                WHERE pa.movimiento_tesoreria_id = $1 AND pa.tipo_documento = 'letra'
                LIMIT 1
            """, origen_id)
            desc = f"Pago Letra"
            if app:
                desc += f" {app['letra_num']} - {app['fp_num']}"
            return desc, "letra", origen_id
    except Exception:
        pass

    return f"{origen_tipo} #{origen_id}", None, None


def _label_tipo(origen_tipo):
    labels = {
        'venta_pos_ingreso': 'Venta POS',
        'cobranza_cxc': 'Cobranza CxC',
        'pago_egreso': 'Pago Factura',
        'pago_letra': 'Pago Letra',
    }
    return labels.get(origen_tipo, origen_tipo)


@router.get("")
async def get_libro_analitico(
    dimension: str = Query(..., description="linea_negocio|marca|centro_costo|categoria"),
    dimension_id: int = Query(...),
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        fd = fecha_desde or date.today().replace(day=1)
        fh = fecha_hasta or date.today()

        movimientos = await _build_movimientos(conn, empresa_id, dimension, dimension_id, fd, fh)

        # Get dimension name
        nombre = ""
        if dimension == 'linea_negocio':
            r = await conn.fetchrow("SELECT nombre FROM cont_linea_negocio WHERE id = $1", dimension_id)
            nombre = r['nombre'] if r else ""
        elif dimension == 'marca':
            r = await conn.fetchrow("SELECT nombre FROM cont_marca WHERE id = $1", dimension_id)
            nombre = r['nombre'] if r else ""
        elif dimension == 'centro_costo':
            r = await conn.fetchrow("SELECT nombre FROM cont_centro_costo WHERE id = $1", dimension_id)
            nombre = r['nombre'] if r else ""
        elif dimension == 'categoria':
            r = await conn.fetchrow("SELECT nombre FROM cont_categoria WHERE id = $1", dimension_id)
            nombre = r['nombre'] if r else ""

        total_entradas = sum(m['entrada'] for m in movimientos)
        total_salidas = sum(m['salida'] for m in movimientos)

        return {
            "dimension": dimension,
            "dimension_id": dimension_id,
            "dimension_nombre": nombre,
            "fecha_desde": str(fd),
            "fecha_hasta": str(fh),
            "total_entradas": round(total_entradas, 2),
            "total_salidas": round(total_salidas, 2),
            "saldo_final": round(total_entradas - total_salidas, 2),
            "movimientos": movimientos,
        }


@router.get("/export")
async def export_libro_analitico(
    dimension: str = Query(...),
    dimension_id: int = Query(...),
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        fd = fecha_desde or date.today().replace(day=1)
        fh = fecha_hasta or date.today()

        movimientos = await _build_movimientos(conn, empresa_id, dimension, dimension_id, fd, fh)

        # Get dimension name
        nombre = ""
        if dimension == 'linea_negocio':
            r = await conn.fetchrow("SELECT nombre FROM cont_linea_negocio WHERE id = $1", dimension_id)
            nombre = r['nombre'] if r else ""
        elif dimension == 'marca':
            r = await conn.fetchrow("SELECT nombre FROM cont_marca WHERE id = $1", dimension_id)
            nombre = r['nombre'] if r else ""
        elif dimension == 'centro_costo':
            r = await conn.fetchrow("SELECT nombre FROM cont_centro_costo WHERE id = $1", dimension_id)
            nombre = r['nombre'] if r else ""
        elif dimension == 'categoria':
            r = await conn.fetchrow("SELECT nombre FROM cont_categoria WHERE id = $1", dimension_id)
            nombre = r['nombre'] if r else ""

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([f"Libro Analítico - {nombre}"])
        writer.writerow([f"Período: {fd} a {fh}"])
        writer.writerow([])
        writer.writerow(["Fecha", "Tipo", "Descripción", "Categoría", "Entrada", "Salida", "Saldo"])

        for m in movimientos:
            writer.writerow([
                m['fecha'], m['tipo'], m['descripcion'], m.get('categoria', ''),
                f"{m['entrada']:.2f}" if m['entrada'] else '',
                f"{m['salida']:.2f}" if m['salida'] else '',
                f"{m['saldo']:.2f}",
            ])

        total_e = sum(m['entrada'] for m in movimientos)
        total_s = sum(m['salida'] for m in movimientos)
        writer.writerow([])
        writer.writerow(["", "", "TOTALES", "", f"{total_e:.2f}", f"{total_s:.2f}", f"{total_e - total_s:.2f}"])

        output.seek(0)
        safe_name = nombre.replace(' ', '_').replace('/', '-')
        filename = f"libro_analitico_{safe_name}_{fd}_{fh}.csv"

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
