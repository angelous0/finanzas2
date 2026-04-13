from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from datetime import date
from database import get_pool
from models import Tercero, TerceroCreate, TerceroUpdate, EmpleadoDetalle, EmpleadoDetalleCreate
from dependencies import get_empresa_id

router = APIRouter()


@router.get("/terceros", response_model=List[Tercero])
async def list_terceros(
    empresa_id: int = Depends(get_empresa_id),
    es_cliente: Optional[bool] = None,
    es_proveedor: Optional[bool] = None,
    es_personal: Optional[bool] = None,
    search: Optional[str] = None
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        conditions = ["activo = TRUE", "empresa_id = $1"]
        params = [empresa_id]
        idx = 2
        if es_cliente is not None:
            conditions.append(f"es_cliente = ${idx}"); params.append(es_cliente); idx += 1
        if es_proveedor is not None:
            conditions.append(f"es_proveedor = ${idx}"); params.append(es_proveedor); idx += 1
        if es_personal is not None:
            conditions.append(f"es_personal = ${idx}"); params.append(es_personal); idx += 1
        if search:
            conditions.append(f"(nombre ILIKE ${idx} OR numero_documento ILIKE ${idx})")
            params.append(f"%{search}%"); idx += 1
        query = f"SELECT * FROM finanzas2.cont_tercero WHERE {' AND '.join(conditions)} ORDER BY nombre"
        rows = await conn.fetch(query, *params)
        return [dict(r) for r in rows]


@router.get("/terceros/{id}", response_model=Tercero)
async def get_tercero(id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        row = await conn.fetchrow("SELECT * FROM finanzas2.cont_tercero WHERE id = $1 AND empresa_id = $2", id, empresa_id)
        if not row:
            raise HTTPException(404, "Tercero not found")
        return dict(row)


@router.post("/terceros", response_model=Tercero)
async def create_tercero(data: TerceroCreate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        row = await conn.fetchrow("""
            INSERT INTO finanzas2.cont_tercero
            (empresa_id, tipo_documento, numero_documento, nombre, nombre_comercial, direccion, telefono, email,
             es_cliente, es_proveedor, es_personal, terminos_pago_dias, limite_credito, notas, activo)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
            RETURNING *
        """, empresa_id, data.tipo_documento, data.numero_documento, data.nombre, data.nombre_comercial,
            data.direccion, data.telefono, data.email, data.es_cliente, data.es_proveedor,
            data.es_personal, data.terminos_pago_dias, data.limite_credito, data.notas, data.activo)
        return dict(row)


@router.put("/terceros/{id}", response_model=Tercero)
async def update_tercero(id: int, data: TerceroUpdate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        updates = []
        values = []
        idx = 1
        for field, value in data.model_dump(exclude_unset=True).items():
            updates.append(f"{field} = ${idx}"); values.append(value); idx += 1
        if not updates:
            raise HTTPException(400, "No fields to update")
        values.append(empresa_id); values.append(id)
        query = f"UPDATE finanzas2.cont_tercero SET {', '.join(updates)}, updated_at = NOW() WHERE empresa_id = ${idx} AND id = ${idx+1} RETURNING *"
        row = await conn.fetchrow(query, *values)
        if not row:
            raise HTTPException(404, "Tercero not found")
        return dict(row)


@router.delete("/terceros/{id}")
async def delete_tercero(id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        result = await conn.execute("UPDATE finanzas2.cont_tercero SET activo = FALSE WHERE id = $1 AND empresa_id = $2", id, empresa_id)
        if result == "UPDATE 0":
            raise HTTPException(404, "Tercero not found")
        return {"message": "Tercero deactivated"}


@router.get("/proveedores", response_model=List[Tercero])
async def list_proveedores(empresa_id: int = Depends(get_empresa_id), search: Optional[str] = None):
    return await list_terceros(empresa_id=empresa_id, es_proveedor=True, search=search)


@router.get("/clientes", response_model=List[Tercero])
async def list_clientes(empresa_id: int = Depends(get_empresa_id), search: Optional[str] = None):
    return await list_terceros(empresa_id=empresa_id, es_cliente=True, search=search)


@router.get("/empleados")
async def list_empleados(empresa_id: int = Depends(get_empresa_id), search: Optional[str] = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        conditions = ["t.activo = TRUE", "t.es_personal = TRUE", "t.empresa_id = $1"]
        params = [empresa_id]
        idx = 2
        if search:
            conditions.append(f"(t.nombre ILIKE ${idx} OR t.numero_documento ILIKE ${idx})")
            params.append(f"%{search}%"); idx += 1
        query = f"""
            SELECT t.*,
                   ed.salario_base, ed.cargo, ed.fecha_ingreso, ed.cuenta_bancaria, ed.banco,
                   ed.centro_costo_id, ed.linea_negocio_id,
                   cc.nombre as centro_costo_nombre, ln.nombre as linea_negocio_nombre
            FROM finanzas2.cont_tercero t
            LEFT JOIN finanzas2.cont_empleado_detalle ed ON t.id = ed.tercero_id
            LEFT JOIN finanzas2.cont_centro_costo cc ON ed.centro_costo_id = cc.id
            LEFT JOIN finanzas2.cont_linea_negocio ln ON ed.linea_negocio_id = ln.id
            WHERE {' AND '.join(conditions)}
            ORDER BY t.nombre
        """
        rows = await conn.fetch(query, *params)
        result = []
        for r in rows:
            emp = dict(r)
            if emp.get('salario_base') is not None:
                emp['salario_base'] = float(emp['salario_base'])
            result.append(emp)
        return result


@router.post("/empleados/{tercero_id}/detalle", response_model=EmpleadoDetalle)
async def create_or_update_empleado_detalle(tercero_id: int, data: EmpleadoDetalleCreate, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        tercero = await conn.fetchrow("SELECT * FROM finanzas2.cont_tercero WHERE id = $1 AND es_personal = TRUE", tercero_id)
        if not tercero:
            raise HTTPException(404, "Empleado no encontrado")
        existing = await conn.fetchrow("SELECT * FROM finanzas2.cont_empleado_detalle WHERE tercero_id = $1", tercero_id)
        if existing:
            row = await conn.fetchrow("""
                UPDATE finanzas2.cont_empleado_detalle
                SET fecha_ingreso = $1, cargo = $2, salario_base = $3,
                    cuenta_bancaria = $4, banco = $5, activo = $6,
                    centro_costo_id = $7, linea_negocio_id = $8
                WHERE tercero_id = $9
                RETURNING *
            """, data.fecha_ingreso, data.cargo, data.salario_base,
                data.cuenta_bancaria, data.banco, data.activo,
                data.centro_costo_id, data.linea_negocio_id, tercero_id)
        else:
            row = await conn.fetchrow("""
                INSERT INTO finanzas2.cont_empleado_detalle
                (tercero_id, fecha_ingreso, cargo, salario_base, cuenta_bancaria, banco, activo,
                 centro_costo_id, linea_negocio_id, empresa_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING *
            """, tercero_id, data.fecha_ingreso, data.cargo, data.salario_base,
                data.cuenta_bancaria, data.banco, data.activo,
                data.centro_costo_id, data.linea_negocio_id, empresa_id)
        return dict(row)


@router.get("/empleados/{tercero_id}/detalle", response_model=EmpleadoDetalle)
async def get_empleado_detalle(tercero_id: int, empresa_id: int = Depends(get_empresa_id)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        row = await conn.fetchrow("SELECT * FROM finanzas2.cont_empleado_detalle WHERE tercero_id = $1", tercero_id)
        if not row:
            raise HTTPException(404, "Detalle de empleado no encontrado")
        return dict(row)
