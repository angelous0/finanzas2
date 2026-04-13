"""
distribucion_service.py - Servicio de distribución analítica.
Calcula y registra la distribución proporcional de pagos según las líneas de factura.
"""
import logging

logger = logging.getLogger(__name__)


async def calcular_distribucion_factura(conn, empresa_id: int, factura_id: int,
                                         movimiento_id: int, monto_pago: float,
                                         fecha, origen_tipo: str = 'pago_egreso'):
    """
    Crea distribuciones analíticas para un pago vinculado a una factura.
    Prorratea el monto del pago según la proporción de cada línea de la factura.
    """
    lineas = await conn.fetch("""
        SELECT linea_negocio_id, categoria_id, centro_costo_id, importe
        FROM finanzas2.cont_factura_proveedor_linea
        WHERE factura_id = $1
    """, factura_id)

    if not lineas:
        return

    total_factura = sum(float(l['importe']) for l in lineas)
    if total_factura <= 0:
        return

    for linea in lineas:
        if not linea['linea_negocio_id'] and not linea['categoria_id']:
            continue
        proporcion = float(linea['importe']) / total_factura
        monto_dist = round(monto_pago * proporcion, 2)
        if monto_dist <= 0:
            continue
        await conn.execute("""
            INSERT INTO finanzas2.cont_distribucion_analitica
            (empresa_id, origen_tipo, origen_id, linea_negocio_id, categoria_id, centro_costo_id, monto, fecha)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """, empresa_id, origen_tipo, movimiento_id,
            linea['linea_negocio_id'], linea['categoria_id'], linea['centro_costo_id'],
            monto_dist, fecha)


async def recalcular_distribuciones_factura(conn, empresa_id: int, factura_id: int):
    """
    Recalcula TODAS las distribuciones analíticas de pagos vinculados a una factura.
    Se llama cuando el usuario edita la clasificación de una factura (línea, categoría, etc).
    """
    aplicaciones = await conn.fetch("""
        SELECT pa.movimiento_tesoreria_id, pa.pago_id, pa.monto_aplicado,
               COALESCE(mt.fecha, p.fecha) as fecha,
               COALESCE(mt.tipo, p.tipo::text) as tipo
        FROM finanzas2.cont_pago_aplicacion pa
        LEFT JOIN finanzas2.cont_movimiento_tesoreria mt ON pa.movimiento_tesoreria_id = mt.id
        LEFT JOIN finanzas2.cont_pago p ON pa.pago_id = p.id
        WHERE pa.tipo_documento = 'factura' AND pa.documento_id = $1
    """, factura_id)

    for app in aplicaciones:
        mov_id = app['movimiento_tesoreria_id'] or app['pago_id']
        if not mov_id:
            continue
        origen_tipo = f"pago_{app['tipo']}" if app['tipo'] else 'pago_egreso'

        await conn.execute("""
            DELETE FROM finanzas2.cont_distribucion_analitica
            WHERE origen_tipo = $1 AND origen_id = $2
        """, origen_tipo, mov_id)

        await calcular_distribucion_factura(
            conn, empresa_id, factura_id,
            mov_id, float(app['monto_aplicado']),
            app['fecha'], origen_tipo
        )

    # Also handle letras linked to this factura
    letras = await conn.fetch("""
        SELECT l.id FROM finanzas2.cont_letra l WHERE l.factura_id = $1
    """, factura_id)

    for letra in letras:
        letra_apps = await conn.fetch("""
            SELECT pa.movimiento_tesoreria_id, pa.pago_id, pa.monto_aplicado,
                   COALESCE(mt.fecha, p.fecha) as fecha
            FROM finanzas2.cont_pago_aplicacion pa
            LEFT JOIN finanzas2.cont_movimiento_tesoreria mt ON pa.movimiento_tesoreria_id = mt.id
            LEFT JOIN finanzas2.cont_pago p ON pa.pago_id = p.id
            WHERE pa.tipo_documento = 'letra' AND pa.documento_id = $1
        """, letra['id'])

        for la in letra_apps:
            mov_id = la['movimiento_tesoreria_id'] or la['pago_id']
            if not mov_id:
                continue

            await conn.execute("""
                DELETE FROM finanzas2.cont_distribucion_analitica
                WHERE origen_tipo = 'pago_letra' AND origen_id = $1
            """, mov_id)

            await calcular_distribucion_factura(
                conn, empresa_id, factura_id,
                mov_id, float(la['monto_aplicado']),
                la['fecha'], 'pago_letra'
            )

    logger.info(f"Distribuciones recalculadas para factura {factura_id}")
