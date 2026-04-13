from fastapi import Query, Header, HTTPException
from typing import Optional
from datetime import datetime, date
from database import get_pool


def safe_date_param(fecha_value):
    """Convert date to string format for PostgreSQL TO_DATE function."""
    if fecha_value is None:
        return None
    if isinstance(fecha_value, str):
        try:
            if 'T' in fecha_value:
                dt = datetime.fromisoformat(fecha_value.replace('Z', '+00:00'))
                return dt.strftime('%Y-%m-%d')
            else:
                return fecha_value
        except:
            return fecha_value
    if isinstance(fecha_value, datetime):
        return fecha_value.strftime('%Y-%m-%d')
    if isinstance(fecha_value, date):
        return fecha_value.strftime('%Y-%m-%d')
    return str(fecha_value)


async def get_empresa_id(
    empresa_id: Optional[int] = Query(None),
    x_empresa_id: Optional[str] = Header(None),
) -> int:
    """Extract empresa_id from query param (priority) or X-Empresa-Id header."""
    eid = empresa_id or (int(x_empresa_id) if x_empresa_id else None)
    if not eid:
        raise HTTPException(400, "empresa_id es requerido")
    return eid


async def get_next_correlativo(conn, empresa_id: int, tipo_documento: str, prefijo: str) -> str:
    """Atomically get next correlative number for a document type."""
    row = await conn.fetchrow("""
        INSERT INTO finanzas2.cont_correlativos (empresa_id, tipo_documento, prefijo, ultimo_numero, updated_at)
        VALUES ($1, $2, $3, 1, NOW())
        ON CONFLICT (empresa_id, tipo_documento, prefijo)
        DO UPDATE SET ultimo_numero = finanzas2.cont_correlativos.ultimo_numero + 1, updated_at = NOW()
        RETURNING ultimo_numero
    """, empresa_id, tipo_documento, prefijo)
    return f"{prefijo}{row['ultimo_numero']:05d}"
