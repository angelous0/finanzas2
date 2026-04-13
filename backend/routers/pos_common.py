"""Utilidades compartidas para los módulos POS."""
from typing import Optional


async def get_company_key(conn, empresa_id: int) -> Optional[str]:
    """Get odoo company_key for an empresa_id. Returns None if no mapping."""
    row = await conn.fetchrow(
        "SELECT company_key FROM finanzas2.cont_empresa_odoo_map WHERE empresa_id = $1",
        empresa_id)
    return row['company_key'] if row else None
