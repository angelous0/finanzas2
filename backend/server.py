from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from datetime import datetime

from database import init_db, close_db, get_pool

# Import all domain routers
from routers.core import router as core_router
from routers.dashboard import router as dashboard_router
from routers.empresas import router as empresas_router
from routers.maestros import router as maestros_router
from routers.cuentas_financieras import router as cuentas_financieras_router
from routers.terceros import router as terceros_router
from routers.inventario_core import router as inventario_core_router
from routers.compras import router as compras_router
from routers.pagos import router as pagos_router
from routers.gastos import router as gastos_router
from routers.import_excel import router as import_excel_router
from routers.factura_extract import router as factura_extract_router
from routers.ventas_pos import router as ventas_pos_router
from routers.cxc_cxp import router as cxc_cxp_router
from routers.banco import router as banco_router
from routers.reportes import router as reportes_router
from routers.core_contabilidad import router as core_contabilidad_router
from routers.export import router as export_router
from routers.marcas import router as marcas_router
from routers.flujo_caja import router as flujo_caja_router
from routers.tesoreria import router as tesoreria_router
from routers.valorizacion import router as valorizacion_router
from routers.categorias_gasto import router as categorias_gasto_router
from routers.prorrateo import router as prorrateo_router
from routers.reportes_simplificados import router as reportes_simplificados_router
from routers.reportes_linea import router as reportes_linea_router
from routers.libro_analitico import router as libro_analitico_router
from routers.unidades_internas import router as unidades_internas_router
from routers.activos_fijos import router as activos_fijos_router
from routers.movimientos_produccion import router as movimientos_produccion_router
# Planilla v3 (reset): trabajadores + ajustes + AFP + adelantos + planilla quincena
from routers.ajustes_planilla import router as ajustes_planilla_router
from routers.afp import router as afp_router
from routers.trabajadores import router as trabajadores_router
from routers.adelantos import router as adelantos_router
from routers.planilla_quincena import router as planilla_quincena_router
from routers.planilla_destajo import router as planilla_destajo_router

# LEGACY routers — desregistrados en Fase 2 (archivos conservados para /legacy/ futuro):
# from routers.planillas import router as planillas_router
# from routers.presupuestos import router as presupuestos_router
# from routers.proyectos import router as proyectos_router
# from routers.capital_linea import router as capital_linea_router
# from routers.dashboard_financiero import router as dashboard_financiero_router
# from routers.reportes_gerenciales import router as reportes_gerenciales_router

# LEGACY routers — desregistrados en Fase 3 (endpoints CORE extraídos a nuevos routers):
# from routers.contabilidad import router as contabilidad_router  → core_contabilidad.py
# from routers.articulos import router as articulos_router        → inventario_core.py
# from routers.finanzas_gerencial import router as finanzas_gerencial_router → flujo_caja.py

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="Finanzas 4.0 API", version="1.0.0")

# Main API router with /api prefix
api_router = APIRouter(prefix="/api")

# Include CORE domain routers
api_router.include_router(core_router)
api_router.include_router(dashboard_router)
api_router.include_router(empresas_router)
api_router.include_router(maestros_router)
api_router.include_router(cuentas_financieras_router)
api_router.include_router(terceros_router)
api_router.include_router(inventario_core_router)
api_router.include_router(import_excel_router)  # ANTES de gastos/compras para que rutas estáticas tengan prioridad
api_router.include_router(factura_extract_router)  # rutas estáticas /facturas-proveedor/extract-* antes que /facturas-proveedor/{id}
api_router.include_router(compras_router)
api_router.include_router(pagos_router)
api_router.include_router(gastos_router)
api_router.include_router(ventas_pos_router)
api_router.include_router(cxc_cxp_router)
api_router.include_router(banco_router)
api_router.include_router(reportes_router)
api_router.include_router(core_contabilidad_router)
api_router.include_router(export_router)
api_router.include_router(marcas_router)
api_router.include_router(flujo_caja_router)
api_router.include_router(tesoreria_router)
api_router.include_router(valorizacion_router)
api_router.include_router(categorias_gasto_router)
api_router.include_router(prorrateo_router)
api_router.include_router(reportes_simplificados_router)
api_router.include_router(reportes_linea_router)
api_router.include_router(libro_analitico_router)
api_router.include_router(unidades_internas_router)
# Planilla v3
api_router.include_router(ajustes_planilla_router)
api_router.include_router(afp_router)
api_router.include_router(trabajadores_router)
api_router.include_router(adelantos_router)
api_router.include_router(planilla_quincena_router)
api_router.include_router(planilla_destajo_router)
api_router.include_router(activos_fijos_router)
api_router.include_router(movimientos_produccion_router)

# LEGACY (Fase 2+3): planillas, presupuestos, proyectos, capital_linea,
# dashboard_financiero, reportes_gerenciales, contabilidad, articulos, finanzas_gerencial

# Include main router in app
app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================
# STARTUP / SHUTDOWN
# =====================
@app.on_event("startup")
async def startup():
    logger.info("Starting Finanzas 4.0 API...")
    await init_db()
    await seed_data()
    await sync_correlativos()
    await seed_servicios_produccion_categoria()
    await migrate_factura_numeros()
    logger.info("Finanzas 4.0 API started successfully")


@app.on_event("shutdown")
async def shutdown():
    await close_db()
    logger.info("Finanzas 4.0 API shutdown complete")


# =====================
# HEALTH CHECK
# =====================
@app.get("/api/health")
async def health_check():
    try:
        p = await get_pool()
        async with p.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        return {"status": "degraded", "db": str(e)}


async def seed_data():
    """Create initial seed data"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        empresa_count = await conn.fetchval("SELECT COUNT(*) FROM finanzas2.cont_empresa")
        if empresa_count > 0:
            logger.info("Seed data already exists, skipping...")
            return
        logger.info("Creating seed data...")
        empresa_id = await conn.fetchval("""
            INSERT INTO finanzas2.cont_empresa (nombre, ruc, direccion, telefono, email)
            VALUES ('Mi Empresa S.A.C.', '20123456789', 'Av. Principal 123, Lima', '01-1234567', 'contacto@miempresa.com')
            RETURNING id
        """)
        pen_id = await conn.fetchval("""
            INSERT INTO finanzas2.cont_moneda (codigo, nombre, simbolo, es_principal)
            VALUES ('PEN', 'Sol Peruano', 'S/', TRUE) RETURNING id
        """)
        await conn.execute("INSERT INTO finanzas2.cont_moneda (codigo, nombre, simbolo, es_principal) VALUES ('USD', 'Dolar Americano', '$', FALSE)")
        await conn.execute("""
            INSERT INTO finanzas2.cont_categoria (empresa_id, codigo, nombre, tipo) VALUES
            ($1, 'ING-001', 'Ventas', 'ingreso'), ($1, 'ING-002', 'Otros Ingresos', 'ingreso'),
            ($1, 'EGR-001', 'Compras Mercaderia', 'egreso'), ($1, 'EGR-002', 'Servicios', 'egreso'),
            ($1, 'EGR-003', 'Planilla', 'egreso'), ($1, 'EGR-004', 'Alquileres', 'egreso'),
            ($1, 'EGR-005', 'Servicios Publicos', 'egreso'), ($1, 'EGR-006', 'Otros Gastos', 'egreso')
        """, empresa_id)
        await conn.execute("""
            INSERT INTO finanzas2.cont_centro_costo (empresa_id, codigo, nombre) VALUES
            ($1, 'CC-001', 'Administracion'), ($1, 'CC-002', 'Ventas'), ($1, 'CC-003', 'Operaciones')
        """, empresa_id)
        await conn.execute("""
            INSERT INTO finanzas2.cont_linea_negocio (empresa_id, codigo, nombre) VALUES
            ($1, 'LN-001', 'Linea Principal'), ($1, 'LN-002', 'Linea Secundaria')
        """, empresa_id)
        await conn.execute("""
            INSERT INTO finanzas2.cont_cuenta_financiera (empresa_id, nombre, tipo, banco, numero_cuenta, moneda_id, saldo_actual)
            VALUES ($1, 'Cuenta BCP Soles', 'banco', 'BCP', '191-12345678-0-12', $2, 0)
        """, empresa_id, pen_id)
        await conn.execute("""
            INSERT INTO finanzas2.cont_cuenta_financiera (empresa_id, nombre, tipo, moneda_id, saldo_actual)
            VALUES ($1, 'Caja Chica', 'caja', $2, 0)
        """, empresa_id, pen_id)
        await conn.execute("""
            INSERT INTO finanzas2.cont_tercero (empresa_id, tipo_documento, numero_documento, nombre, es_proveedor, terminos_pago_dias)
            VALUES ($1, 'RUC', '20987654321', 'Proveedor Demo S.A.C.', TRUE, 30)
        """, empresa_id)
        logger.info("Seed data created successfully")


async def seed_servicios_produccion_categoria():
    """Inserta la categoría 'SERVICIOS DE PRODUCCIÓN' y sus hijos para cada empresa (idempotente)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        empresas = await conn.fetch("SELECT id FROM finanzas2.cont_empresa")
        for empresa_row in empresas:
            empresa_id = empresa_row["id"]
            existing = await conn.fetchval(
                "SELECT id FROM finanzas2.cont_categoria WHERE empresa_id=$1 AND nombre=$2 AND padre_id IS NULL",
                empresa_id, "SERVICIOS DE PRODUCCIÓN",
            )
            if existing:
                continue
            parent_id = await conn.fetchval("""
                INSERT INTO finanzas2.cont_categoria (empresa_id, codigo, nombre, tipo, activo)
                VALUES ($1, 'EGR-PROD', 'SERVICIOS DE PRODUCCIÓN', 'egreso', TRUE)
                RETURNING id
            """, empresa_id)
            await conn.execute("""
                INSERT INTO finanzas2.cont_categoria
                    (empresa_id, codigo, nombre, tipo, padre_id, descripcion, activo)
                VALUES
                    ($1, 'EGR-PROD-001', 'Servicio externo producción', 'egreso', $2,
                     'Costura, lavandería, estampado, etc.', TRUE),
                    ($1, 'EGR-PROD-002', 'Compra de Materia Prima', 'egreso', $2,
                     'Telas, avíos, hilos', TRUE)
            """, empresa_id, parent_id)
            logger.info(f"Seeded SERVICIOS DE PRODUCCIÓN category for empresa {empresa_id}")


async def migrate_factura_numeros():
    """Normalize FC-NNN (3 digits) → FC-NNNN (4 digits) for existing records.
    Skips any record where the normalized number already exists (avoids UniqueViolation)."""
    import re
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, empresa_id, numero
            FROM finanzas2.cont_factura_proveedor
            WHERE numero ~ '^FC-[0-9]{1,3}$'
        """)
        updated = 0
        for row in rows:
            m = re.match(r'^FC-(\d+)$', row['numero'])
            if not m:
                continue
            normalized = f"FC-{int(m.group(1)):04d}"
            if normalized == row['numero']:
                continue
            exists = await conn.fetchval(
                "SELECT 1 FROM finanzas2.cont_factura_proveedor WHERE numero = $1 AND empresa_id = $2",
                normalized, row['empresa_id'])
            if not exists:
                await conn.execute(
                    "UPDATE finanzas2.cont_factura_proveedor SET numero = $1 WHERE id = $2",
                    normalized, row['id'])
                updated += 1
        if updated:
            logger.info(f"Migrated {updated} factura number(s) to 4-digit FC format")


async def sync_correlativos():
    """Sync cont_correlativos with existing document numbers on startup."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("SET search_path TO finanzas2, public")
        year = datetime.now().year
        doc_types = [
            ('cont_oc', 'numero', 'oc', f'OC-{year}-'),
            ('cont_factura_proveedor', 'numero', 'factura_proveedor', f'FP-{year}-'),
            ('cont_movimiento_tesoreria', 'numero', 'pago_ingreso', f'PAG-I-{year}-'),
            ('cont_movimiento_tesoreria', 'numero', 'pago_egreso', f'PAG-E-{year}-'),
            ('cont_gasto', 'numero', 'gasto', f'GAS-{year}-'),
        ]
        for table, col, tipo_doc, prefix in doc_types:
            tipo_filter = ""
            if tipo_doc == 'pago_ingreso':
                tipo_filter = "AND tipo = 'ingreso' AND origen_tipo = 'pago_ingreso'"
            elif tipo_doc == 'pago_egreso':
                tipo_filter = "AND tipo = 'egreso' AND origen_tipo = 'pago_egreso'"
            rows = await conn.fetch(f"""
                SELECT empresa_id, MAX(
                    CASE WHEN {col} LIKE $1 || '%'
                    THEN CAST(SPLIT_PART({col}, '-', {len(prefix.split('-'))}) AS INTEGER)
                    ELSE 0 END
                ) as max_num
                FROM finanzas2.{table}
                WHERE {col} LIKE $1 || '%' {tipo_filter}
                GROUP BY empresa_id
            """, prefix)
            for row in rows:
                if row['max_num'] and row['max_num'] > 0:
                    await conn.execute("""
                        INSERT INTO finanzas2.cont_correlativos (empresa_id, tipo_documento, prefijo, ultimo_numero, updated_at)
                        VALUES ($1, $2, $3, $4, NOW())
                        ON CONFLICT (empresa_id, tipo_documento, prefijo)
                        DO UPDATE SET ultimo_numero = GREATEST(finanzas2.cont_correlativos.ultimo_numero, $4), updated_at = NOW()
                    """, row['empresa_id'], tipo_doc, prefix, row['max_num'])
        logger.info("Correlatives synced with existing data")
