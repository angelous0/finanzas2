"""
Mapping service: resolves odoo_linea_negocio_id -> cont_linea_negocio.id
Falls back to 'SIN CLASIFICAR' for unmapped lines.
"""
import logging

logger = logging.getLogger(__name__)

_SIN_CLASIFICAR = "SIN CLASIFICAR"


async def get_linea_negocio_map(conn, empresa_id: int) -> dict:
    """
    Returns a dict mapping odoo_linea_negocio_id -> cont_linea_negocio row.
    Includes a None key for the SIN CLASIFICAR fallback.
    """
    rows = await conn.fetch("""
        SELECT id, nombre, odoo_linea_negocio_id, odoo_linea_negocio_nombre
        FROM finanzas2.cont_linea_negocio
        WHERE empresa_id = $1 AND activo = TRUE
    """, empresa_id)

    mapping = {}
    sin_clasificar_id = None
    for r in rows:
        if r['nombre'] == _SIN_CLASIFICAR:
            sin_clasificar_id = r['id']
        if r['odoo_linea_negocio_id'] is not None:
            mapping[r['odoo_linea_negocio_id']] = {
                "id": r['id'], "nombre": r['nombre']
            }

    # Ensure SIN CLASIFICAR exists
    if sin_clasificar_id is None:
        row = await conn.fetchrow("""
            INSERT INTO finanzas2.cont_linea_negocio (empresa_id, codigo, nombre, activo)
            VALUES ($1, 'SIN-CLAS', $2, TRUE)
            ON CONFLICT DO NOTHING
            RETURNING id
        """, empresa_id, _SIN_CLASIFICAR)
        if row:
            sin_clasificar_id = row['id']
        else:
            row = await conn.fetchrow("""
                SELECT id FROM finanzas2.cont_linea_negocio
                WHERE empresa_id = $1 AND nombre = $2
            """, empresa_id, _SIN_CLASIFICAR)
            sin_clasificar_id = row['id'] if row else None

    mapping[None] = {"id": sin_clasificar_id, "nombre": _SIN_CLASIFICAR}
    return mapping


def resolve_linea(mapping: dict, odoo_ln_id) -> dict:
    """Resolve an odoo_linea_negocio_id to a cont_linea_negocio entry."""
    if odoo_ln_id and odoo_ln_id in mapping:
        return mapping[odoo_ln_id]
    return mapping.get(None, {"id": None, "nombre": _SIN_CLASIFICAR})


async def auto_register_lineas_from_odoo(conn, empresa_id: int, odoo_lines: list):
    """
    Given a list of dicts with odoo_linea_negocio_id and odoo_linea_negocio_nombre,
    auto-register any new ones into cont_linea_negocio and return the updated mapping.
    """
    mapping = await get_linea_negocio_map(conn, empresa_id)
    new_count = 0
    for line in odoo_lines:
        oid = line.get('odoo_linea_negocio_id') or line.get('linea_negocio_id')
        oname = line.get('odoo_linea_negocio_nombre') or line.get('linea_negocio_nombre')
        if oid and oid not in mapping:
            row = await conn.fetchrow("""
                INSERT INTO finanzas2.cont_linea_negocio
                    (empresa_id, codigo, nombre, odoo_linea_negocio_id, odoo_linea_negocio_nombre, activo)
                VALUES ($1, $2, $3, $4, $5, TRUE)
                ON CONFLICT DO NOTHING
                RETURNING id
            """, empresa_id, f"LN-ODOO-{oid}", oname or f"Linea Odoo {oid}", oid, oname)
            if row:
                mapping[oid] = {"id": row['id'], "nombre": oname or f"Linea Odoo {oid}"}
                new_count += 1
                logger.info(f"Auto-registered linea negocio: odoo_id={oid} name={oname}")
    if new_count:
        logger.info(f"Auto-registered {new_count} new lineas de negocio from Odoo")
    return mapping
