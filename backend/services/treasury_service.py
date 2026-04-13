"""
Treasury Service - Unified financial movements.
cont_movimiento_tesoreria is the SINGLE source of truth for all cash movements.
"""
import logging
from datetime import date

logger = logging.getLogger(__name__)


async def create_movimiento_tesoreria(
    conn,
    empresa_id: int,
    fecha,
    tipo: str,  # 'ingreso' or 'egreso'
    monto: float,
    cuenta_financiera_id: int = None,
    forma_pago: str = None,
    referencia: str = None,
    concepto: str = None,
    origen_tipo: str = None,
    origen_id: int = None,
    marca_id: int = None,
    linea_negocio_id: int = None,
    centro_costo_id: int = None,
    proyecto_id: int = None,
    notas: str = None,
    numero: str = None,
    moneda_id: int = None,
    documento_tipo: str = None,
    documento_id: int = None,
) -> int:
    """Insert a unified treasury movement and return its id.
    documento_tipo/documento_id track which document this payment applies to (factura, letra, etc.)
    """
    row = await conn.fetchrow("""
        INSERT INTO finanzas2.cont_movimiento_tesoreria
            (empresa_id, fecha, tipo, monto, cuenta_financiera_id, forma_pago,
             referencia, concepto, origen_tipo, origen_id,
             marca_id, linea_negocio_id, centro_costo_id, proyecto_id, notas,
             numero, moneda_id, documento_tipo, documento_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
        RETURNING id
    """, empresa_id, fecha, tipo, monto, cuenta_financiera_id, forma_pago,
        referencia, concepto, origen_tipo, origen_id,
        marca_id, linea_negocio_id, centro_costo_id, proyecto_id, notas,
        numero, moneda_id, documento_tipo, documento_id)
    logger.info(f"Movement created: id={row['id']} num={numero} tipo={tipo} monto={monto} origen={origen_tipo}:{origen_id}")
    return row['id']


async def delete_movimientos_by_origen(conn, empresa_id: int, origen_tipo: str, origen_id: int):
    """Delete all movements linked to a specific origin (for reversals)."""
    deleted = await conn.execute("""
        DELETE FROM finanzas2.cont_movimiento_tesoreria
        WHERE empresa_id = $1 AND origen_tipo = $2 AND origen_id = $3
    """, empresa_id, origen_tipo, origen_id)
    logger.info(f"Movements deleted for origen={origen_tipo}:{origen_id}")
    return deleted
