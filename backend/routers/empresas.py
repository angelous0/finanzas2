from fastapi import APIRouter, HTTPException
from typing import List
from database import get_pool
from models import Empresa, EmpresaCreate, EmpresaUpdate

router = APIRouter()


@router.get("/empresas", response_model=List[Empresa])
async def list_empresas():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        rows = await conn.fetch("SELECT * FROM finanzas2.cont_empresa ORDER BY nombre")
        return [dict(r) for r in rows]


@router.post("/empresas", response_model=Empresa)
async def create_empresa(data: EmpresaCreate):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        row = await conn.fetchrow("""
            INSERT INTO finanzas2.cont_empresa (nombre, ruc, direccion, telefono, email, logo_url, activo)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
        """, data.nombre, data.ruc, data.direccion, data.telefono, data.email, data.logo_url, data.activo)

        empresa_id = row['id']

        moneda_count = await conn.fetchval("SELECT COUNT(*) FROM finanzas2.cont_moneda")
        if moneda_count == 0:
            await conn.execute("INSERT INTO finanzas2.cont_moneda (codigo, nombre, simbolo, es_principal) VALUES ('PEN', 'Sol Peruano', 'S/', TRUE)")
            await conn.execute("INSERT INTO finanzas2.cont_moneda (codigo, nombre, simbolo, es_principal) VALUES ('USD', 'Dólar Americano', '$', FALSE)")

        cat_count = await conn.fetchval("SELECT COUNT(*) FROM finanzas2.cont_categoria WHERE empresa_id = $1", empresa_id)
        if cat_count == 0:
            await conn.execute("""
                INSERT INTO finanzas2.cont_categoria (empresa_id, codigo, nombre, tipo) VALUES
                ($1, 'ING-001', 'Ventas', 'ingreso'),
                ($1, 'ING-002', 'Otros Ingresos', 'ingreso'),
                ($1, 'EGR-001', 'Compras Mercadería', 'egreso'),
                ($1, 'EGR-002', 'Servicios', 'egreso'),
                ($1, 'EGR-003', 'Planilla', 'egreso'),
                ($1, 'EGR-004', 'Alquileres', 'egreso'),
                ($1, 'EGR-005', 'Servicios Públicos', 'egreso'),
                ($1, 'EGR-006', 'Otros Gastos', 'egreso')
            """, empresa_id)

        return dict(row)


@router.put("/empresas/{id}", response_model=Empresa)
async def update_empresa(id: int, data: EmpresaUpdate):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        updates = []
        values = []
        idx = 1
        for field, value in data.model_dump(exclude_unset=True).items():
            updates.append(f"{field} = ${idx}")
            values.append(value)
            idx += 1
        if not updates:
            raise HTTPException(400, "No fields to update")
        values.append(id)
        query = f"UPDATE finanzas2.cont_empresa SET {', '.join(updates)}, updated_at = NOW() WHERE id = ${idx} RETURNING *"
        row = await conn.fetchrow(query, *values)
        if not row:
            raise HTTPException(404, "Empresa not found")
        return dict(row)


@router.delete("/empresas/{id}")
async def delete_empresa(id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        result = await conn.execute("DELETE FROM finanzas2.cont_empresa WHERE id = $1", id)
        if result == "DELETE 0":
            raise HTTPException(404, "Empresa not found")
        return {"message": "Empresa deleted"}
