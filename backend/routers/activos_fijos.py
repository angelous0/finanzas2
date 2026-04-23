from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from datetime import date
from decimal import Decimal
from pydantic import BaseModel
from database import get_pool
from dependencies import get_empresa_id

router = APIRouter()


# ── Pydantic Models ──

class ActivoFijoCreate(BaseModel):
    nombre: str
    codigo: Optional[str] = None
    descripcion: Optional[str] = None
    categoria: Optional[str] = None
    fecha_adquisicion: Optional[date] = None
    valor_adquisicion: Optional[float] = None
    vida_util_anios: Optional[int] = None
    metodo_depreciacion: Optional[str] = "lineal"
    valor_residual: Optional[float] = 0
    proveedor_id: Optional[int] = None
    factura_referencia: Optional[str] = None
    ubicacion: Optional[str] = None
    responsable: Optional[str] = None
    linea_negocio_id: Optional[int] = None


class ActivoFijoUpdate(BaseModel):
    nombre: Optional[str] = None
    codigo: Optional[str] = None
    descripcion: Optional[str] = None
    categoria: Optional[str] = None
    fecha_adquisicion: Optional[date] = None
    valor_adquisicion: Optional[float] = None
    vida_util_anios: Optional[int] = None
    metodo_depreciacion: Optional[str] = None
    valor_residual: Optional[float] = None
    proveedor_id: Optional[int] = None
    factura_referencia: Optional[str] = None
    ubicacion: Optional[str] = None
    responsable: Optional[str] = None
    estado: Optional[str] = None
    linea_negocio_id: Optional[int] = None


# ── RESUMEN ──

@router.get("/activos-fijos/resumen")
async def resumen_activos(empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        stats = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE estado = 'activo') AS total_activos,
                COALESCE(SUM(valor_adquisicion) FILTER (WHERE estado = 'activo'), 0) AS valor_total,
                COALESCE(SUM(valor_adquisicion) FILTER (WHERE estado = 'activo'), 0)
                    - COALESCE((
                        SELECT SUM(d.valor_depreciacion)
                        FROM finanzas2.fin_depreciacion_activo d
                        JOIN finanzas2.fin_activo_fijo a2 ON d.activo_id = a2.id
                        WHERE a2.empresa_id = $1 AND a2.estado = 'activo'
                    ), 0) AS valor_libro_total,
                COUNT(*) AS total_registros
            FROM finanzas2.fin_activo_fijo
            WHERE empresa_id = $1
        """, empresa_id)

        # Depreciacion del mes actual — solo activos vigentes (no en baja)
        periodo_actual = date.today().strftime("%Y-%m")
        dep_mes = await conn.fetchval("""
            SELECT COALESCE(SUM(d.valor_depreciacion), 0)
            FROM finanzas2.fin_depreciacion_activo d
            JOIN finanzas2.fin_activo_fijo a ON d.activo_id = a.id
            WHERE a.empresa_id = $1 AND d.periodo = $2
              AND a.estado = 'activo'
        """, empresa_id, periodo_actual)

        return {
            "total_activos": stats["total_activos"],
            "valor_total": float(stats["valor_total"]),
            "valor_libro_total": float(stats["valor_libro_total"]),
            "depreciacion_mes": float(dep_mes or 0),
            "total_registros": stats["total_registros"],
        }


# ── LIST ──

@router.get("/activos-fijos")
async def list_activos(
    categoria: Optional[str] = None,
    estado: Optional[str] = None,
    linea_negocio_id: Optional[int] = None,
    search: Optional[str] = None,
    empresa_id: int = Depends(get_empresa_id),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        conds = ["a.empresa_id = $1"]
        params: list = [empresa_id]
        idx = 2
        if categoria:
            conds.append(f"a.categoria = ${idx}")
            params.append(categoria); idx += 1
        if estado:
            conds.append(f"a.estado = ${idx}")
            params.append(estado); idx += 1
        if linea_negocio_id:
            conds.append(f"a.linea_negocio_id = ${idx}")
            params.append(linea_negocio_id); idx += 1
        if search:
            conds.append(f"(a.nombre ILIKE '%' || ${idx} || '%' OR a.codigo ILIKE '%' || ${idx} || '%')")
            params.append(search); idx += 1

        rows = await conn.fetch(f"""
            SELECT a.*,
                   t.nombre AS proveedor_nombre,
                   ln.nombre AS linea_negocio_nombre,
                   COALESCE(dep.total_dep, 0) AS depreciacion_acumulada,
                   a.valor_adquisicion - COALESCE(dep.total_dep, 0) AS valor_libro,
                   CASE WHEN a.estado = 'activo' AND a.vida_util_anios > 0 AND a.valor_adquisicion > 0
                        THEN (a.valor_adquisicion - COALESCE(a.valor_residual, 0)) / (a.vida_util_anios * 12.0)
                        ELSE 0 END AS dep_mensual
            FROM finanzas2.fin_activo_fijo a
            LEFT JOIN finanzas2.cont_tercero t ON a.proveedor_id = t.id
            LEFT JOIN finanzas2.cont_linea_negocio ln ON a.linea_negocio_id = ln.id
            LEFT JOIN LATERAL (
                SELECT SUM(valor_depreciacion) AS total_dep
                FROM finanzas2.fin_depreciacion_activo
                WHERE activo_id = a.id
            ) dep ON true
            WHERE {' AND '.join(conds)}
            ORDER BY a.created_at DESC
        """, *params)
        return [dict(r) for r in rows]


# ── GET BY ID ──

@router.get("/activos-fijos/{activo_id}")
async def get_activo(activo_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT a.*,
                   t.nombre AS proveedor_nombre,
                   ln.nombre AS linea_negocio_nombre
            FROM finanzas2.fin_activo_fijo a
            LEFT JOIN finanzas2.cont_tercero t ON a.proveedor_id = t.id
            LEFT JOIN finanzas2.cont_linea_negocio ln ON a.linea_negocio_id = ln.id
            WHERE a.id = $1 AND a.empresa_id = $2
        """, activo_id, empresa_id)
        if not row:
            raise HTTPException(404, "Activo no encontrado")
        return dict(row)


# ── CREATE ──

@router.post("/activos-fijos")
async def create_activo(data: ActivoFijoCreate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Auto-generate code if not provided
        codigo = data.codigo
        if not codigo:
            last = await conn.fetchval(
                "SELECT codigo FROM finanzas2.fin_activo_fijo WHERE empresa_id=$1 ORDER BY id DESC LIMIT 1",
                empresa_id
            )
            if last and last.startswith("AF-"):
                try:
                    num = int(last.split("-")[1]) + 1
                except (ValueError, IndexError):
                    num = 1
            else:
                num = 1
            codigo = f"AF-{num:04d}"

        row = await conn.fetchrow("""
            INSERT INTO finanzas2.fin_activo_fijo
                (empresa_id, codigo, nombre, descripcion, categoria, fecha_adquisicion,
                 valor_adquisicion, vida_util_anios, metodo_depreciacion, valor_residual,
                 proveedor_id, factura_referencia, ubicacion, responsable, linea_negocio_id,
                 estado, created_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,'activo',NOW())
            RETURNING *
        """, empresa_id, codigo, data.nombre, data.descripcion, data.categoria,
            data.fecha_adquisicion, data.valor_adquisicion, data.vida_util_anios,
            data.metodo_depreciacion, data.valor_residual or 0,
            data.proveedor_id, data.factura_referencia, data.ubicacion, data.responsable,
            data.linea_negocio_id)
        return dict(row)


# ── UPDATE ──

@router.put("/activos-fijos/{activo_id}")
async def update_activo(activo_id: int, data: ActivoFijoUpdate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM finanzas2.fin_activo_fijo WHERE id=$1 AND empresa_id=$2",
            activo_id, empresa_id
        )
        if not existing:
            raise HTTPException(404, "Activo no encontrado")

        sets = []
        params = []
        idx = 1
        for field in ["nombre", "codigo", "descripcion", "categoria", "fecha_adquisicion",
                       "valor_adquisicion", "vida_util_anios", "metodo_depreciacion", "valor_residual",
                       "proveedor_id", "factura_referencia", "ubicacion", "responsable", "estado",
                       "linea_negocio_id"]:
            val = getattr(data, field, None)
            if val is not None:
                sets.append(f"{field} = ${idx}")
                params.append(val); idx += 1

        if not sets:
            raise HTTPException(400, "No hay campos para actualizar")

        params.append(activo_id)
        await conn.execute(
            f"UPDATE finanzas2.fin_activo_fijo SET {', '.join(sets)} WHERE id = ${idx}",
            *params
        )

        row = await conn.fetchrow("SELECT * FROM finanzas2.fin_activo_fijo WHERE id=$1", activo_id)
        return dict(row)


# ── DELETE (soft) ──

@router.delete("/activos-fijos/{activo_id}")
async def delete_activo(activo_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM finanzas2.fin_activo_fijo WHERE id=$1 AND empresa_id=$2",
            activo_id, empresa_id
        )
        if not existing:
            raise HTTPException(404, "Activo no encontrado")
        await conn.execute(
            "UPDATE finanzas2.fin_activo_fijo SET estado='baja' WHERE id=$1",
            activo_id
        )
        return {"ok": True}


# ── DEPRECIACION ──

@router.get("/activos-fijos/{activo_id}/depreciacion")
async def get_depreciacion(activo_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM finanzas2.fin_activo_fijo WHERE id=$1 AND empresa_id=$2",
            activo_id, empresa_id
        )
        if not existing:
            raise HTTPException(404, "Activo no encontrado")

        rows = await conn.fetch("""
            SELECT * FROM finanzas2.fin_depreciacion_activo
            WHERE activo_id = $1
            ORDER BY periodo
        """, activo_id)
        return [dict(r) for r in rows]


@router.post("/activos-fijos/calcular-depreciacion")
async def calcular_depreciacion(empresa_id: int = Depends(get_empresa_id)):
    """Calculate and save depreciation for current month for all active assets."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        periodo = date.today().strftime("%Y-%m")

        activos = await conn.fetch("""
            SELECT id, valor_adquisicion, valor_residual, vida_util_anios, metodo_depreciacion
            FROM finanzas2.fin_activo_fijo
            WHERE empresa_id = $1 AND estado = 'activo'
              AND valor_adquisicion > 0 AND vida_util_anios > 0
        """, empresa_id)

        count = 0
        for a in activos:
            # Check if already calculated
            exists = await conn.fetchval(
                "SELECT 1 FROM finanzas2.fin_depreciacion_activo WHERE activo_id=$1 AND periodo=$2",
                a["id"], periodo
            )
            if exists:
                continue

            # Linear depreciation
            valor_dep = (float(a["valor_adquisicion"]) - float(a["valor_residual"] or 0)) / (a["vida_util_anios"] * 12)
            valor_dep = round(valor_dep, 2)

            # Get accumulated
            acumulado_prev = await conn.fetchval(
                "SELECT COALESCE(SUM(valor_depreciacion), 0) FROM finanzas2.fin_depreciacion_activo WHERE activo_id=$1",
                a["id"]
            )
            nuevo_acumulado = float(acumulado_prev) + valor_dep
            valor_libro = float(a["valor_adquisicion"]) - nuevo_acumulado

            # Don't depreciate below residual
            if valor_libro < float(a["valor_residual"] or 0):
                continue

            await conn.execute("""
                INSERT INTO finanzas2.fin_depreciacion_activo
                    (activo_id, periodo, valor_depreciacion, valor_acumulado, valor_libro, created_at)
                VALUES ($1, $2, $3, $4, $5, NOW())
            """, a["id"], periodo, valor_dep, nuevo_acumulado, valor_libro)
            count += 1

        return {"periodo": periodo, "activos_procesados": count}
