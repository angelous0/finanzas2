"""
Servicio de distribución analítica por línea de negocio.

- 'venta_pos_ingreso': Ingreso analítico al aprobar/crédito una venta POS
- 'cobranza_cxc': Cobro analítico al registrar abono en CxC
"""
import logging
from services.linea_mapping import get_linea_negocio_map, resolve_linea

logger = logging.getLogger(__name__)


async def crear_distribucion_ingreso(conn, empresa_id: int, odoo_order_id: int, fecha):
    """Crea distribución analítica de ingreso desde el detalle POS.
    Se usa al confirmar o marcar crédito una venta.
    Distribuye amount_total proporcionalmente por línea de negocio."""
    # Get sale total (IGV included)
    amount_total = await conn.fetchval("""
        SELECT amount_total FROM finanzas2.cont_venta_pos WHERE odoo_id = $1
    """, odoo_order_id)
    if not amount_total or float(amount_total) <= 0:
        return 0

    lineas = await conn.fetch("""
        SELECT l.odoo_linea_negocio_id, COALESCE(SUM(l.price_subtotal), 0) as subtotal
        FROM finanzas2.cont_venta_pos_linea l
        JOIN finanzas2.cont_venta_pos v ON l.venta_pos_id = v.id
        WHERE v.odoo_id = $1
        GROUP BY l.odoo_linea_negocio_id
        HAVING SUM(l.price_subtotal) > 0
    """, odoo_order_id)

    if not lineas:
        return 0

    ln_map = await get_linea_negocio_map(conn, empresa_id)
    total_subtotal = sum(float(r['subtotal']) for r in lineas)
    if total_subtotal <= 0:
        return 0

    count = 0
    restante = float(amount_total)
    for i, r in enumerate(lineas):
        mapped = resolve_linea(ln_map, r['odoo_linea_negocio_id'])
        if i == len(lineas) - 1:
            monto = round(restante, 2)
        else:
            proporcion = float(r['subtotal']) / total_subtotal
            monto = round(float(amount_total) * proporcion, 2)
            restante -= monto
        if monto > 0:
            await conn.execute("""
                INSERT INTO finanzas2.cont_distribucion_analitica
                    (empresa_id, origen_tipo, origen_id, linea_negocio_id, monto, fecha)
                VALUES ($1, 'venta_pos_ingreso', $2, $3, $4, $5)
            """, empresa_id, odoo_order_id, mapped['id'], monto, fecha)
            count += 1
    return count


async def crear_distribucion_cobro(conn, empresa_id: int, odoo_order_id: int,
                                    abono_id: int, monto_cobro: float, fecha):
    """Crea distribución analítica de cobro prorrateada por línea de negocio."""
    lineas = await conn.fetch("""
        SELECT l.odoo_linea_negocio_id, COALESCE(SUM(l.price_subtotal), 0) as subtotal
        FROM finanzas2.cont_venta_pos_linea l
        JOIN finanzas2.cont_venta_pos v ON l.venta_pos_id = v.id
        WHERE v.odoo_id = $1
        GROUP BY l.odoo_linea_negocio_id
        HAVING SUM(l.price_subtotal) > 0
    """, odoo_order_id)

    if not lineas:
        return 0

    ln_map = await get_linea_negocio_map(conn, empresa_id)
    total_venta = sum(float(r['subtotal']) for r in lineas)
    if total_venta <= 0:
        return 0

    count = 0
    restante = float(monto_cobro)
    for i, r in enumerate(lineas):
        mapped = resolve_linea(ln_map, r['odoo_linea_negocio_id'])
        if i == len(lineas) - 1:
            monto_linea = round(restante, 2)
        else:
            proporcion = float(r['subtotal']) / float(total_venta)
            monto_linea = round(float(monto_cobro) * proporcion, 2)
            restante -= monto_linea
        if monto_linea > 0:
            await conn.execute("""
                INSERT INTO finanzas2.cont_distribucion_analitica
                    (empresa_id, origen_tipo, origen_id, linea_negocio_id, monto, fecha)
                VALUES ($1, 'cobranza_cxc', $2, $3, $4, $5)
            """, empresa_id, abono_id, mapped['id'], monto_linea, fecha)
            count += 1
    return count


async def eliminar_distribucion_by_origen(conn, empresa_id: int, origen_tipo: str, origen_id: int):
    """Elimina distribuciones analíticas por origen (para desconfirmar)."""
    result = await conn.execute("""
        DELETE FROM finanzas2.cont_distribucion_analitica
        WHERE empresa_id = $1 AND origen_tipo = $2 AND origen_id = $3
    """, empresa_id, origen_tipo, origen_id)
    return result
