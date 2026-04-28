"""
Configuración global de IA (OpenAI) para extracción automática de facturas.

Hay UNA SOLA configuración (cont_config_ia tiene id=1 fijo). Todas las empresas
del sistema comparten la misma API key — el sistema es híbrido:
  - Si hay una key guardada en BD → la usa
  - Si no, cae al .env (OPENAI_API_KEY)
  - Si no hay ninguna → error 500 al intentar usar IA

Endpoints:
  GET  /config-ia            → estado actual (key parcialmente oculta)
  PUT  /config-ia            → guardar key + modelo
  POST /config-ia/test       → probar conexión con OpenAI
"""
import os
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Body

from database import get_pool

logger = logging.getLogger(__name__)
router = APIRouter()


def _mask_key(key: Optional[str]) -> Optional[str]:
    """Devuelve 'sk-proj-•••••••••XXXX' (solo últimos 4)."""
    if not key:
        return None
    if len(key) < 12:
        return "•" * len(key)
    return key[:8] + "•" * 16 + key[-4:]


async def get_active_openai_key_and_model() -> tuple[Optional[str], str]:
    """Devuelve (api_key, model) usando BD primero, .env como fallback.

    Llamada por factura_extract.py para resolver la key activa antes de cada uso.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT openai_api_key, openai_model FROM finanzas2.cont_config_ia WHERE id = 1")
    bd_key = row["openai_api_key"] if row else None
    bd_model = (row["openai_model"] if row else None) or "gpt-4o-mini"
    env_key = os.environ.get("OPENAI_API_KEY")
    env_model = os.environ.get("OPENAI_VISION_MODEL")
    return (bd_key or env_key, bd_model or env_model or "gpt-4o-mini")


@router.get("/config-ia")
async def get_config_ia():
    """Devuelve el estado de la configuración actual (key oculta)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM finanzas2.cont_config_ia WHERE id = 1")
    if not row:
        return {
            "tiene_key_bd": False,
            "tiene_key_env": bool(os.environ.get("OPENAI_API_KEY")),
            "openai_api_key_masked": None,
            "openai_model": "gpt-4o-mini",
            "last_test_at": None,
            "last_test_ok": None,
            "last_test_error": None,
        }
    bd_key = row["openai_api_key"]
    return {
        "tiene_key_bd": bool(bd_key),
        "tiene_key_env": bool(os.environ.get("OPENAI_API_KEY")),
        "openai_api_key_masked": _mask_key(bd_key),
        "openai_model": row["openai_model"] or "gpt-4o-mini",
        "last_test_at": row["last_test_at"].isoformat() if row["last_test_at"] else None,
        "last_test_ok": row["last_test_ok"],
        "last_test_error": row["last_test_error"],
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


@router.put("/config-ia")
async def put_config_ia(body: dict = Body(...)):
    """Guarda API key y/o modelo. Si openai_api_key=null, deja la key actual."""
    api_key = body.get("openai_api_key")  # None = no tocar; "" = borrar; "sk-..." = setear
    model = body.get("openai_model")
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Asegurar fila única
        await conn.execute("""
            INSERT INTO finanzas2.cont_config_ia (id, openai_model)
            VALUES (1, 'gpt-4o-mini') ON CONFLICT (id) DO NOTHING
        """)
        if api_key is not None and model is not None:
            await conn.execute(
                """UPDATE finanzas2.cont_config_ia
                   SET openai_api_key = NULLIF($1, ''),
                       openai_model = $2,
                       updated_at = NOW()
                   WHERE id = 1""", api_key, model)
        elif api_key is not None:
            await conn.execute(
                """UPDATE finanzas2.cont_config_ia
                   SET openai_api_key = NULLIF($1, ''), updated_at = NOW()
                   WHERE id = 1""", api_key)
        elif model is not None:
            await conn.execute(
                """UPDATE finanzas2.cont_config_ia
                   SET openai_model = $1, updated_at = NOW()
                   WHERE id = 1""", model)
    return await get_config_ia()


@router.post("/config-ia/test")
async def test_config_ia():
    """Prueba la API key actual contra OpenAI con un request mínimo. Guarda resultado."""
    api_key, model = await get_active_openai_key_and_model()
    if not api_key:
        raise HTTPException(400, "No hay API key configurada (ni en BD ni en .env)")
    try:
        from openai import OpenAI
    except ImportError:
        raise HTTPException(500, "Librería openai no instalada")

    error_msg = None
    ok = False
    try:
        client = OpenAI(api_key=api_key)
        # Hacemos un request mínimo (5 tokens) solo para validar la key + model
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        ok = bool(resp.choices)
    except Exception as e:
        error_msg = str(e)[:500]
        ok = False

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE finanzas2.cont_config_ia
               SET last_test_at = NOW(),
                   last_test_ok = $1,
                   last_test_error = $2
             WHERE id = 1
        """, ok, error_msg)

    if ok:
        return {"ok": True, "model": model, "tested_at": datetime.utcnow().isoformat()}
    raise HTTPException(400, f"Falló la prueba: {error_msg}")


@router.get("/config-ia/usage")
async def get_usage():
    """Resumen de uso de la IA: gasto este mes, total histórico, # facturas, etc."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Mes actual
        mes_actual = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE ok) AS llamadas_ok,
                COUNT(*) FILTER (WHERE NOT ok) AS llamadas_error,
                COALESCE(SUM(tokens_input), 0)::int AS tokens_in,
                COALESCE(SUM(tokens_output), 0)::int AS tokens_out,
                COALESCE(SUM(costo_usd), 0)::numeric AS costo
              FROM finanzas2.cont_uso_ia
             WHERE date_trunc('month', fecha) = date_trunc('month', NOW())
        """)
        # Total histórico
        total = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE ok) AS llamadas_ok,
                COUNT(*) FILTER (WHERE NOT ok) AS llamadas_error,
                COALESCE(SUM(tokens_input), 0)::int AS tokens_in,
                COALESCE(SUM(tokens_output), 0)::int AS tokens_out,
                COALESCE(SUM(costo_usd), 0)::numeric AS costo,
                MIN(fecha) AS primera_llamada,
                MAX(fecha) AS ultima_llamada
              FROM finanzas2.cont_uso_ia
        """)
        # Por modelo (mes actual)
        por_modelo = await conn.fetch("""
            SELECT modelo,
                   COUNT(*) AS llamadas,
                   COALESCE(SUM(costo_usd),0)::numeric AS costo
              FROM finanzas2.cont_uso_ia
             WHERE date_trunc('month', fecha) = date_trunc('month', NOW())
               AND ok
             GROUP BY modelo
             ORDER BY costo DESC
        """)
        # Últimas 20 llamadas
        recientes = await conn.fetch("""
            SELECT id, fecha, modelo, fuente, tokens_input, tokens_output, costo_usd, ok, error
              FROM finanzas2.cont_uso_ia
             ORDER BY fecha DESC
             LIMIT 20
        """)

    def _f(v): return float(v or 0)
    return {
        "mes_actual": {
            "llamadas_ok": int(mes_actual["llamadas_ok"] or 0),
            "llamadas_error": int(mes_actual["llamadas_error"] or 0),
            "tokens_in": int(mes_actual["tokens_in"] or 0),
            "tokens_out": int(mes_actual["tokens_out"] or 0),
            "costo_usd": round(_f(mes_actual["costo"]), 4),
        },
        "total": {
            "llamadas_ok": int(total["llamadas_ok"] or 0),
            "llamadas_error": int(total["llamadas_error"] or 0),
            "tokens_in": int(total["tokens_in"] or 0),
            "tokens_out": int(total["tokens_out"] or 0),
            "costo_usd": round(_f(total["costo"]), 4),
            "primera_llamada": total["primera_llamada"].isoformat() if total["primera_llamada"] else None,
            "ultima_llamada": total["ultima_llamada"].isoformat() if total["ultima_llamada"] else None,
        },
        "por_modelo_mes": [
            {"modelo": r["modelo"], "llamadas": int(r["llamadas"]), "costo_usd": round(_f(r["costo"]), 4)}
            for r in por_modelo
        ],
        "recientes": [
            {
                "id": r["id"],
                "fecha": r["fecha"].isoformat() if r["fecha"] else None,
                "modelo": r["modelo"],
                "fuente": r["fuente"],
                "tokens_input": int(r["tokens_input"] or 0),
                "tokens_output": int(r["tokens_output"] or 0),
                "costo_usd": round(_f(r["costo_usd"]), 6),
                "ok": r["ok"],
                "error": r["error"],
            } for r in recientes
        ],
    }
