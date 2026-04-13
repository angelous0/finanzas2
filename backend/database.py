import os
import asyncpg
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Global connection pool
pool: Optional[asyncpg.Pool] = None

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgres://admin:admin@72.60.241.216:9595/datos?sslmode=disable')

async def init_db():
    """Initialize PostgreSQL connection pool and create schema"""
    global pool
    try:
        logger.info(f"Connecting to PostgreSQL...")
        pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=60
        )
        logger.info("PostgreSQL connection pool created successfully")
        
        # Create schema and tables
        await create_schema()
        return pool
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        raise

async def get_pool() -> asyncpg.Pool:
    """Get the database connection pool"""
    global pool
    if pool is None:
        await init_db()
    return pool

async def close_db():
    """Close the database connection pool"""
    global pool
    if pool:
        await pool.close()
        pool = None
        logger.info("PostgreSQL connection pool closed")

async def create_schema():
    """Create the finanzas2 schema and all tables.
    
    Convention:
    - All transactional and per-empresa config tables carry empresa_id NOT NULL FK.
    - Global tables (cont_empresa, cont_moneda, cont_tipo_cambio) do NOT have empresa_id.
    """
    global pool
    if not pool:
        return
    
    async with pool.acquire() as conn:
        await conn.execute("CREATE SCHEMA IF NOT EXISTS finanzas2")
        await conn.execute("SET search_path TO finanzas2, public")
        
        # ── ENUMs ──
        for enum_sql in [
            "CREATE TYPE finanzas2.tipo_tercero AS ENUM ('cliente', 'proveedor', 'personal')",
            "CREATE TYPE finanzas2.tipo_categoria AS ENUM ('ingreso', 'egreso')",
            "CREATE TYPE finanzas2.estado_oc AS ENUM ('borrador', 'enviada', 'recibida', 'facturada', 'cancelada')",
            "CREATE TYPE finanzas2.estado_factura AS ENUM ('pendiente', 'parcial', 'pagado', 'canjeado', 'anulada')",
            "CREATE TYPE finanzas2.estado_letra AS ENUM ('pendiente', 'parcial', 'pagada', 'vencida', 'protestada', 'anulada')",
            "CREATE TYPE finanzas2.tipo_pago AS ENUM ('ingreso', 'egreso')",
            "CREATE TYPE finanzas2.estado_presupuesto AS ENUM ('borrador', 'aprobado', 'cerrado')",
        ]:
            await conn.execute(f"DO $$ BEGIN {enum_sql}; EXCEPTION WHEN duplicate_object THEN null; END $$;")

        # ══════════════════════════════════════
        # GLOBAL TABLES (no empresa_id)
        # ══════════════════════════════════════

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_empresa (
                id SERIAL PRIMARY KEY,
                nombre VARCHAR(200) NOT NULL,
                ruc VARCHAR(20),
                direccion TEXT,
                telefono VARCHAR(50),
                email VARCHAR(100),
                logo_url TEXT,
                activo BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_moneda (
                id SERIAL PRIMARY KEY,
                codigo VARCHAR(10) NOT NULL UNIQUE,
                nombre VARCHAR(50) NOT NULL,
                simbolo VARCHAR(5) NOT NULL,
                es_principal BOOLEAN DEFAULT FALSE,
                activo BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_tipo_cambio (
                id SERIAL PRIMARY KEY,
                moneda_id INTEGER REFERENCES finanzas2.cont_moneda(id),
                fecha DATE NOT NULL,
                tasa_compra DECIMAL(12, 4) NOT NULL,
                tasa_venta DECIMAL(12, 4) NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(moneda_id, fecha)
            )
        """)

        # ══════════════════════════════════════
        # PER-EMPRESA CONFIG TABLES
        # ══════════════════════════════════════

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_categoria (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                codigo VARCHAR(20),
                nombre VARCHAR(100) NOT NULL,
                tipo finanzas2.tipo_categoria NOT NULL,
                padre_id INTEGER REFERENCES finanzas2.cont_categoria(id),
                descripcion TEXT,
                activo BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_centro_costo (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                codigo VARCHAR(20),
                nombre VARCHAR(100) NOT NULL,
                descripcion TEXT,
                activo BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_linea_negocio (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                codigo VARCHAR(20),
                nombre VARCHAR(100) NOT NULL,
                descripcion TEXT,
                activo BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_cuenta_financiera (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                nombre VARCHAR(100) NOT NULL,
                tipo VARCHAR(20) NOT NULL,
                banco VARCHAR(100),
                numero_cuenta VARCHAR(50),
                cci VARCHAR(30),
                moneda_id INTEGER REFERENCES finanzas2.cont_moneda(id),
                saldo_actual DECIMAL(15, 2) DEFAULT 0,
                activo BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_tercero (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                tipo_documento VARCHAR(20),
                numero_documento VARCHAR(20),
                nombre VARCHAR(200) NOT NULL,
                nombre_comercial VARCHAR(200),
                direccion TEXT,
                telefono VARCHAR(50),
                email VARCHAR(100),
                es_cliente BOOLEAN DEFAULT FALSE,
                es_proveedor BOOLEAN DEFAULT FALSE,
                es_personal BOOLEAN DEFAULT FALSE,
                terminos_pago_dias INTEGER DEFAULT 0,
                limite_credito DECIMAL(15, 2) DEFAULT 0,
                notas TEXT,
                activo BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_empleado_detalle (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                tercero_id INTEGER REFERENCES finanzas2.cont_tercero(id) UNIQUE,
                fecha_ingreso DATE,
                cargo VARCHAR(100),
                salario_base DECIMAL(12, 2),
                cuenta_bancaria VARCHAR(50),
                banco VARCHAR(100),
                centro_costo_id INTEGER REFERENCES finanzas2.cont_centro_costo(id),
                linea_negocio_id INTEGER REFERENCES finanzas2.cont_linea_negocio(id),
                activo BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_articulo_ref (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                prod_inventario_id INTEGER,
                codigo VARCHAR(50),
                nombre VARCHAR(200),
                descripcion TEXT,
                precio_referencia DECIMAL(12, 2),
                activo BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # ══════════════════════════════════════
        # TRANSACTIONAL TABLES
        # ══════════════════════════════════════

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_oc (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                numero VARCHAR(20) NOT NULL,
                fecha DATE NOT NULL,
                proveedor_id INTEGER REFERENCES finanzas2.cont_tercero(id),
                moneda_id INTEGER REFERENCES finanzas2.cont_moneda(id),
                estado finanzas2.estado_oc DEFAULT 'borrador',
                subtotal DECIMAL(15, 2) DEFAULT 0,
                igv DECIMAL(15, 2) DEFAULT 0,
                total DECIMAL(15, 2) DEFAULT 0,
                notas TEXT,
                factura_generada_id INTEGER,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(empresa_id, numero)
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_oc_linea (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                oc_id INTEGER REFERENCES finanzas2.cont_oc(id) ON DELETE CASCADE,
                articulo_id INTEGER REFERENCES finanzas2.cont_articulo_ref(id),
                descripcion TEXT,
                cantidad DECIMAL(12, 4) NOT NULL,
                precio_unitario DECIMAL(12, 4) NOT NULL,
                igv_aplica BOOLEAN DEFAULT TRUE,
                subtotal DECIMAL(15, 2) DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_factura_proveedor (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                numero VARCHAR(30) NOT NULL,
                proveedor_id INTEGER REFERENCES finanzas2.cont_tercero(id),
                beneficiario_nombre VARCHAR(200),
                moneda_id INTEGER REFERENCES finanzas2.cont_moneda(id),
                fecha_factura DATE NOT NULL,
                fecha_contable DATE,
                fecha_vencimiento DATE,
                terminos_dias INTEGER DEFAULT 0,
                tipo_documento VARCHAR(20) DEFAULT 'factura',
                estado finanzas2.estado_factura DEFAULT 'pendiente',
                subtotal DECIMAL(15, 2) DEFAULT 0,
                igv DECIMAL(15, 2) DEFAULT 0,
                total DECIMAL(15, 2) DEFAULT 0,
                saldo_pendiente DECIMAL(15, 2) DEFAULT 0,
                impuestos_incluidos BOOLEAN DEFAULT FALSE,
                notas TEXT,
                oc_origen_id INTEGER REFERENCES finanzas2.cont_oc(id),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_factura_proveedor_linea (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                factura_id INTEGER REFERENCES finanzas2.cont_factura_proveedor(id) ON DELETE CASCADE,
                categoria_id INTEGER REFERENCES finanzas2.cont_categoria(id),
                articulo_id INTEGER REFERENCES finanzas2.cont_articulo_ref(id),
                descripcion TEXT,
                linea_negocio_id INTEGER REFERENCES finanzas2.cont_linea_negocio(id),
                centro_costo_id INTEGER REFERENCES finanzas2.cont_centro_costo(id),
                importe DECIMAL(15, 2) NOT NULL,
                igv_aplica BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_cxp (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                factura_id INTEGER REFERENCES finanzas2.cont_factura_proveedor(id) ON DELETE CASCADE UNIQUE,
                proveedor_id INTEGER REFERENCES finanzas2.cont_tercero(id),
                monto_original DECIMAL(15, 2) NOT NULL,
                saldo_pendiente DECIMAL(15, 2) NOT NULL,
                fecha_vencimiento DATE,
                estado finanzas2.estado_factura DEFAULT 'pendiente',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_pago (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                numero VARCHAR(20) NOT NULL,
                tipo finanzas2.tipo_pago NOT NULL,
                fecha DATE NOT NULL,
                cuenta_financiera_id INTEGER REFERENCES finanzas2.cont_cuenta_financiera(id),
                moneda_id INTEGER REFERENCES finanzas2.cont_moneda(id),
                monto_total DECIMAL(15, 2) NOT NULL,
                referencia VARCHAR(100),
                notas TEXT,
                centro_costo_id INTEGER REFERENCES finanzas2.cont_centro_costo(id),
                linea_negocio_id INTEGER REFERENCES finanzas2.cont_linea_negocio(id),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(empresa_id, numero)
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_pago_detalle (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                pago_id INTEGER REFERENCES finanzas2.cont_pago(id) ON DELETE CASCADE,
                cuenta_financiera_id INTEGER REFERENCES finanzas2.cont_cuenta_financiera(id),
                medio_pago VARCHAR(50) NOT NULL,
                monto DECIMAL(15, 2) NOT NULL,
                referencia VARCHAR(100),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_pago_aplicacion (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                pago_id INTEGER REFERENCES finanzas2.cont_pago(id) ON DELETE CASCADE,
                tipo_documento VARCHAR(50) NOT NULL,
                documento_id INTEGER NOT NULL,
                monto_aplicado DECIMAL(15, 2) NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_letra (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                numero VARCHAR(30) NOT NULL,
                numero_unico VARCHAR(50),
                factura_id INTEGER REFERENCES finanzas2.cont_factura_proveedor(id),
                proveedor_id INTEGER REFERENCES finanzas2.cont_tercero(id),
                monto DECIMAL(15, 2) NOT NULL,
                fecha_emision DATE NOT NULL,
                fecha_vencimiento DATE NOT NULL,
                estado finanzas2.estado_letra DEFAULT 'pendiente',
                saldo_pendiente DECIMAL(15, 2) NOT NULL,
                notas TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(empresa_id, numero)
            )
        """)
        await conn.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_letra' AND column_name='numero_unico') THEN
                    ALTER TABLE finanzas2.cont_letra ADD COLUMN numero_unico VARCHAR(50);
                END IF;
            END $$;
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_gasto (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                numero VARCHAR(20) NOT NULL,
                fecha DATE NOT NULL,
                fecha_contable DATE,
                proveedor_id INTEGER REFERENCES finanzas2.cont_tercero(id),
                beneficiario_nombre VARCHAR(200),
                moneda_id INTEGER REFERENCES finanzas2.cont_moneda(id),
                subtotal DECIMAL(15, 2) DEFAULT 0,
                igv DECIMAL(15, 2) DEFAULT 0,
                total DECIMAL(15, 2) DEFAULT 0,
                tipo_documento VARCHAR(20),
                numero_documento VARCHAR(50),
                notas TEXT,
                pago_id INTEGER REFERENCES finanzas2.cont_pago(id),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(empresa_id, numero)
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_gasto_linea (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                gasto_id INTEGER REFERENCES finanzas2.cont_gasto(id) ON DELETE CASCADE,
                categoria_id INTEGER REFERENCES finanzas2.cont_categoria(id),
                descripcion TEXT,
                linea_negocio_id INTEGER REFERENCES finanzas2.cont_linea_negocio(id),
                centro_costo_id INTEGER REFERENCES finanzas2.cont_centro_costo(id),
                importe DECIMAL(15, 2) NOT NULL,
                igv_aplica BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_adelanto_empleado (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                empleado_id INTEGER REFERENCES finanzas2.cont_tercero(id),
                fecha DATE NOT NULL,
                monto DECIMAL(12, 2) NOT NULL,
                motivo TEXT,
                pagado BOOLEAN DEFAULT FALSE,
                pago_id INTEGER REFERENCES finanzas2.cont_pago(id),
                descontado BOOLEAN DEFAULT FALSE,
                planilla_id INTEGER,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_planilla (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                periodo VARCHAR(20) NOT NULL,
                fecha_inicio DATE NOT NULL,
                fecha_fin DATE NOT NULL,
                total_bruto DECIMAL(15, 2) DEFAULT 0,
                total_adelantos DECIMAL(15, 2) DEFAULT 0,
                total_descuentos DECIMAL(15, 2) DEFAULT 0,
                total_neto DECIMAL(15, 2) DEFAULT 0,
                estado VARCHAR(20) DEFAULT 'borrador',
                pago_id INTEGER REFERENCES finanzas2.cont_pago(id),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(empresa_id, periodo)
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_planilla_detalle (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                planilla_id INTEGER REFERENCES finanzas2.cont_planilla(id) ON DELETE CASCADE,
                empleado_id INTEGER REFERENCES finanzas2.cont_tercero(id),
                salario_base DECIMAL(12, 2) DEFAULT 0,
                bonificaciones DECIMAL(12, 2) DEFAULT 0,
                adelantos DECIMAL(12, 2) DEFAULT 0,
                otros_descuentos DECIMAL(12, 2) DEFAULT 0,
                neto_pagar DECIMAL(12, 2) DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_venta_pos (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                odoo_id INTEGER UNIQUE,
                date_order TIMESTAMP,
                name VARCHAR(100),
                tipo_comp VARCHAR(50),
                num_comp VARCHAR(50),
                partner_id INTEGER,
                partner_name VARCHAR(200),
                tienda_id INTEGER,
                tienda_name VARCHAR(200),
                vendedor_id INTEGER,
                vendedor_name VARCHAR(200),
                company_id INTEGER,
                company_name VARCHAR(200),
                x_pagos TEXT,
                quantity_total DECIMAL(12, 4),
                amount_total DECIMAL(15, 2),
                state VARCHAR(50),
                reserva_pendiente DECIMAL(15, 2) DEFAULT 0,
                reserva_facturada DECIMAL(15, 2) DEFAULT 0,
                is_cancel BOOLEAN DEFAULT FALSE,
                order_cancel VARCHAR(100),
                reserva BOOLEAN DEFAULT FALSE,
                is_credit BOOLEAN DEFAULT FALSE,
                reserva_use_id INTEGER,
                estado_local VARCHAR(50) DEFAULT 'pendiente',
                cxc_id INTEGER,
                synced_at TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_venta_pos_pago (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                venta_pos_id INTEGER REFERENCES finanzas2.cont_venta_pos(id) ON DELETE CASCADE,
                forma_pago VARCHAR(50) NOT NULL,
                monto DECIMAL(15, 2) NOT NULL,
                referencia VARCHAR(100),
                fecha_pago DATE DEFAULT CURRENT_DATE,
                observaciones TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                created_by VARCHAR(100)
            )
        """)
        
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_venta_pos_linea (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                venta_pos_id INTEGER REFERENCES finanzas2.cont_venta_pos(id) ON DELETE CASCADE,
                odoo_line_id INTEGER,
                product_id INTEGER,
                product_name VARCHAR(255),
                product_code VARCHAR(50),
                qty DECIMAL(12, 3) NOT NULL,
                price_unit DECIMAL(15, 2) NOT NULL,
                price_subtotal DECIMAL(15, 2) NOT NULL,
                price_subtotal_incl DECIMAL(15, 2),
                discount DECIMAL(5, 2) DEFAULT 0,
                marca VARCHAR(100),
                tipo VARCHAR(100),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_cxc (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                venta_pos_id INTEGER REFERENCES finanzas2.cont_venta_pos(id),
                cliente_id INTEGER REFERENCES finanzas2.cont_tercero(id),
                monto_original DECIMAL(15, 2) NOT NULL,
                saldo_pendiente DECIMAL(15, 2) NOT NULL,
                fecha_vencimiento DATE,
                estado VARCHAR(20) DEFAULT 'pendiente',
                notas TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_presupuesto (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                nombre VARCHAR(100) NOT NULL,
                anio INTEGER NOT NULL,
                version INTEGER DEFAULT 1,
                estado finanzas2.estado_presupuesto DEFAULT 'borrador',
                notas TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_presupuesto_linea (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                presupuesto_id INTEGER REFERENCES finanzas2.cont_presupuesto(id) ON DELETE CASCADE,
                categoria_id INTEGER REFERENCES finanzas2.cont_categoria(id),
                centro_costo_id INTEGER REFERENCES finanzas2.cont_centro_costo(id),
                linea_negocio_id INTEGER REFERENCES finanzas2.cont_linea_negocio(id),
                mes INTEGER NOT NULL,
                monto_presupuestado DECIMAL(15, 2) DEFAULT 0,
                monto_real DECIMAL(15, 2) DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_banco_mov_raw (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                cuenta_financiera_id INTEGER REFERENCES finanzas2.cont_cuenta_financiera(id),
                banco VARCHAR(50),
                fecha DATE,
                descripcion TEXT,
                referencia VARCHAR(100),
                cargo DECIMAL(15, 2),
                abono DECIMAL(15, 2),
                saldo DECIMAL(15, 2),
                raw_data JSONB,
                procesado BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_banco_mov (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                raw_id INTEGER REFERENCES finanzas2.cont_banco_mov_raw(id),
                cuenta_financiera_id INTEGER REFERENCES finanzas2.cont_cuenta_financiera(id),
                fecha DATE NOT NULL,
                tipo VARCHAR(20) NOT NULL,
                monto DECIMAL(15, 2) NOT NULL,
                descripcion TEXT,
                referencia VARCHAR(100),
                conciliado BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_conciliacion (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                cuenta_financiera_id INTEGER REFERENCES finanzas2.cont_cuenta_financiera(id),
                fecha_inicio DATE NOT NULL,
                fecha_fin DATE NOT NULL,
                saldo_inicial DECIMAL(15, 2),
                saldo_final DECIMAL(15, 2),
                diferencia DECIMAL(15, 2),
                estado VARCHAR(20) DEFAULT 'borrador',
                notas TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_conciliacion_linea (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                conciliacion_id INTEGER REFERENCES finanzas2.cont_conciliacion(id) ON DELETE CASCADE,
                banco_mov_id INTEGER REFERENCES finanzas2.cont_banco_mov(id),
                pago_id INTEGER REFERENCES finanzas2.cont_pago(id),
                tipo VARCHAR(50),
                documento_id INTEGER,
                monto DECIMAL(15, 2),
                conciliado BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # ── Correlativos (secure per-company sequences) ──
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_correlativos (
                id SERIAL PRIMARY KEY,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                tipo_documento VARCHAR(30) NOT NULL,
                prefijo VARCHAR(30) NOT NULL,
                ultimo_numero INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(empresa_id, tipo_documento, prefijo)
            )
        """)

        # Add UNIQUE constraint on cont_factura_proveedor(empresa_id, numero) if missing
        await conn.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'cont_factura_proveedor_empresa_numero_key'
                ) THEN
                    ALTER TABLE finanzas2.cont_factura_proveedor
                    ADD CONSTRAINT cont_factura_proveedor_empresa_numero_key
                    UNIQUE(empresa_id, numero);
                END IF;
            END $$;
        """)

        # ── Add columns if missing (migrations) ──
        await conn.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_empleado_detalle' AND column_name='centro_costo_id') THEN
                    ALTER TABLE finanzas2.cont_empleado_detalle ADD COLUMN centro_costo_id INTEGER REFERENCES finanzas2.cont_centro_costo(id);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_empleado_detalle' AND column_name='linea_negocio_id') THEN
                    ALTER TABLE finanzas2.cont_empleado_detalle ADD COLUMN linea_negocio_id INTEGER REFERENCES finanzas2.cont_linea_negocio(id);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_pago' AND column_name='centro_costo_id') THEN
                    ALTER TABLE finanzas2.cont_pago ADD COLUMN centro_costo_id INTEGER REFERENCES finanzas2.cont_centro_costo(id);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_pago' AND column_name='linea_negocio_id') THEN
                    ALTER TABLE finanzas2.cont_pago ADD COLUMN linea_negocio_id INTEGER REFERENCES finanzas2.cont_linea_negocio(id);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_factura_proveedor' AND column_name='fecha_contable') THEN
                    ALTER TABLE finanzas2.cont_factura_proveedor ADD COLUMN fecha_contable DATE;
                    UPDATE finanzas2.cont_factura_proveedor SET fecha_contable = fecha_factura WHERE fecha_contable IS NULL;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_gasto' AND column_name='fecha_contable') THEN
                    ALTER TABLE finanzas2.cont_gasto ADD COLUMN fecha_contable DATE;
                    UPDATE finanzas2.cont_gasto SET fecha_contable = fecha WHERE fecha_contable IS NULL;
                END IF;
            END $$;
        """)

        # ── compraAPP columns (SUNAT tax breakdown) ──
        await conn.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_factura_proveedor' AND column_name='tipo_comprobante_sunat') THEN
                    ALTER TABLE finanzas2.cont_factura_proveedor ADD COLUMN tipo_comprobante_sunat VARCHAR(2);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_factura_proveedor' AND column_name='base_gravada') THEN
                    ALTER TABLE finanzas2.cont_factura_proveedor ADD COLUMN base_gravada NUMERIC(18,8) DEFAULT 0;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_factura_proveedor' AND column_name='igv_sunat') THEN
                    ALTER TABLE finanzas2.cont_factura_proveedor ADD COLUMN igv_sunat NUMERIC(18,8) DEFAULT 0;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_factura_proveedor' AND column_name='base_no_gravada') THEN
                    ALTER TABLE finanzas2.cont_factura_proveedor ADD COLUMN base_no_gravada NUMERIC(18,8) DEFAULT 0;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_factura_proveedor' AND column_name='isc') THEN
                    ALTER TABLE finanzas2.cont_factura_proveedor ADD COLUMN isc NUMERIC(18,8) DEFAULT 0;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_gasto' AND column_name='tipo_comprobante_sunat') THEN
                    ALTER TABLE finanzas2.cont_gasto ADD COLUMN tipo_comprobante_sunat VARCHAR(2);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_gasto' AND column_name='base_gravada') THEN
                    ALTER TABLE finanzas2.cont_gasto ADD COLUMN base_gravada NUMERIC(18,8) DEFAULT 0;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_gasto' AND column_name='igv_sunat') THEN
                    ALTER TABLE finanzas2.cont_gasto ADD COLUMN igv_sunat NUMERIC(18,8) DEFAULT 0;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_gasto' AND column_name='base_no_gravada') THEN
                    ALTER TABLE finanzas2.cont_gasto ADD COLUMN base_no_gravada NUMERIC(18,8) DEFAULT 0;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_gasto' AND column_name='isc') THEN
                    ALTER TABLE finanzas2.cont_gasto ADD COLUMN isc NUMERIC(18,8) DEFAULT 0;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_factura_proveedor' AND column_name='vou_numero') THEN
                    ALTER TABLE finanzas2.cont_factura_proveedor ADD COLUMN vou_numero VARCHAR(10);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_gasto' AND column_name='vou_numero') THEN
                    ALTER TABLE finanzas2.cont_gasto ADD COLUMN vou_numero VARCHAR(10);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_factura_proveedor' AND column_name='tipo_cambio') THEN
                    ALTER TABLE finanzas2.cont_factura_proveedor ADD COLUMN tipo_cambio NUMERIC(18,8);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_gasto' AND column_name='tipo_cambio') THEN
                    ALTER TABLE finanzas2.cont_gasto ADD COLUMN tipo_cambio NUMERIC(18,8);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_categoria' AND column_name='cuenta_gasto_id') THEN
                    ALTER TABLE finanzas2.cont_categoria ADD COLUMN cuenta_gasto_id INT;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_config_empresa' AND column_name='cta_otrib_default_id') THEN
                    ALTER TABLE finanzas2.cont_config_empresa ADD COLUMN cta_otrib_default_id INT REFERENCES finanzas2.cont_cuenta(id);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_factura_proveedor_linea' AND column_name='presupuesto_id') THEN
                    ALTER TABLE finanzas2.cont_factura_proveedor_linea ADD COLUMN presupuesto_id INT REFERENCES finanzas2.cont_presupuesto(id);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_gasto_linea' AND column_name='presupuesto_id') THEN
                    ALTER TABLE finanzas2.cont_gasto_linea ADD COLUMN presupuesto_id INT REFERENCES finanzas2.cont_presupuesto(id);
                END IF;
            END $$;
        """)

        # ── Table: cont_cuenta (chart of accounts) ──
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_cuenta (
                id SERIAL PRIMARY KEY,
                empresa_id INT NOT NULL REFERENCES finanzas2.cont_empresa(id),
                codigo TEXT NOT NULL,
                nombre TEXT NOT NULL,
                tipo TEXT NOT NULL,
                es_activa BOOLEAN NOT NULL DEFAULT true,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (empresa_id, codigo)
            )
        """)

        # ── Table: cont_config_empresa (accounting config per company) ──
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_config_empresa (
                empresa_id INT PRIMARY KEY REFERENCES finanzas2.cont_empresa(id),
                cta_gastos_default_id INT REFERENCES finanzas2.cont_cuenta(id),
                cta_igv_default_id INT REFERENCES finanzas2.cont_cuenta(id),
                cta_xpagar_default_id INT REFERENCES finanzas2.cont_cuenta(id)
            )
        """)

        # ── Migration: Fix FK on conciliacion_linea to point to banco_mov_raw ──
        await conn.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.table_constraints 
                    WHERE constraint_name = 'cont_conciliacion_linea_banco_mov_id_fkey'
                    AND table_schema = 'finanzas2'
                ) THEN
                    ALTER TABLE finanzas2.cont_conciliacion_linea 
                    DROP CONSTRAINT cont_conciliacion_linea_banco_mov_id_fkey;
                END IF;
            END $$;
        """)
        await conn.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.table_constraints 
                    WHERE constraint_name = 'cont_conciliacion_linea_banco_mov_raw_fkey'
                    AND table_schema = 'finanzas2'
                ) THEN
                    ALTER TABLE finanzas2.cont_conciliacion_linea 
                    ADD CONSTRAINT cont_conciliacion_linea_banco_mov_raw_fkey
                    FOREIGN KEY (banco_mov_id) REFERENCES finanzas2.cont_banco_mov_raw(id);
                END IF;
            END $$;
        """)

        # ── Migration: Drop pago_id FK from cont_conciliacion_linea (cont_pago deprecated) ──
        await conn.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.table_constraints
                    WHERE constraint_name = 'cont_conciliacion_linea_pago_id_fkey'
                    AND table_schema = 'finanzas2'
                ) THEN
                    ALTER TABLE finanzas2.cont_conciliacion_linea
                    DROP CONSTRAINT cont_conciliacion_linea_pago_id_fkey;
                END IF;
            END $$;
        """)

        # ── Unidades Internas de Producción (Gerencial) ──
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.fin_unidad_interna (
                id SERIAL PRIMARY KEY,
                nombre VARCHAR(100) NOT NULL,
                tipo VARCHAR(50),
                activo BOOLEAN DEFAULT TRUE,
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.fin_cargo_interno (
                id SERIAL PRIMARY KEY,
                fecha DATE NOT NULL,
                registro_id VARCHAR(100),
                movimiento_id VARCHAR(100),
                unidad_interna_id INTEGER NOT NULL REFERENCES finanzas2.fin_unidad_interna(id),
                servicio_nombre VARCHAR(100),
                persona_nombre VARCHAR(100),
                cantidad INTEGER DEFAULT 0,
                tarifa DECIMAL(15, 4) DEFAULT 0,
                importe DECIMAL(15, 2) DEFAULT 0,
                estado VARCHAR(30) DEFAULT 'generado',
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(movimiento_id)
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.fin_gasto_unidad_interna (
                id SERIAL PRIMARY KEY,
                fecha DATE NOT NULL,
                unidad_interna_id INTEGER NOT NULL REFERENCES finanzas2.fin_unidad_interna(id),
                tipo_gasto VARCHAR(50) NOT NULL,
                descripcion TEXT,
                monto DECIMAL(15, 2) NOT NULL,
                registro_id VARCHAR(100),
                movimiento_id VARCHAR(100),
                empresa_id INTEGER NOT NULL REFERENCES finanzas2.cont_empresa(id),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Migration: Add tipo_persona and unidad_interna_id to prod_personas_produccion
        await conn.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_schema='produccion' AND table_name='prod_personas_produccion' AND column_name='tipo_persona')
                THEN
                    ALTER TABLE produccion.prod_personas_produccion ADD COLUMN tipo_persona VARCHAR(20) DEFAULT 'EXTERNO';
                END IF;
            END $$;
        """)
        await conn.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_schema='produccion' AND table_name='prod_personas_produccion' AND column_name='unidad_interna_id')
                THEN
                    ALTER TABLE produccion.prod_personas_produccion ADD COLUMN unidad_interna_id INTEGER;
                END IF;
            END $$;
        """)

        # ── Indexes ──
        index_stmts = [
            "CREATE INDEX IF NOT EXISTS idx_cont_venta_pos_pago_venta ON finanzas2.cont_venta_pos_pago(venta_pos_id)",
            "CREATE INDEX IF NOT EXISTS idx_cont_venta_pos_linea_venta ON finanzas2.cont_venta_pos_linea(venta_pos_id)",
            "CREATE INDEX IF NOT EXISTS idx_cont_venta_pos_linea_marca ON finanzas2.cont_venta_pos_linea(marca)",
            "CREATE INDEX IF NOT EXISTS idx_cont_venta_pos_linea_tipo ON finanzas2.cont_venta_pos_linea(tipo)",
        ]
        for stmt in index_stmts:
            await conn.execute(stmt)

        # ── Contabilidad: Asientos (Journal Entries) ──
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_asiento (
                id SERIAL PRIMARY KEY,
                empresa_id INT NOT NULL REFERENCES finanzas2.cont_empresa(id),
                fecha_contable DATE NOT NULL,
                origen_tipo TEXT NOT NULL,
                origen_id INT NOT NULL,
                origen_numero TEXT,
                glosa TEXT,
                moneda TEXT NOT NULL DEFAULT 'PEN',
                tipo_cambio NUMERIC(18,6) NOT NULL DEFAULT 1,
                estado TEXT NOT NULL DEFAULT 'borrador',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (empresa_id, origen_tipo, origen_id)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_asiento_linea (
                id SERIAL PRIMARY KEY,
                asiento_id INT NOT NULL REFERENCES finanzas2.cont_asiento(id) ON DELETE CASCADE,
                empresa_id INT NOT NULL,
                cuenta_id INT NOT NULL REFERENCES finanzas2.cont_cuenta(id),
                tercero_id INT REFERENCES finanzas2.cont_tercero(id),
                centro_costo_id INT REFERENCES finanzas2.cont_centro_costo(id),
                presupuesto_id INT REFERENCES finanzas2.cont_presupuesto(id),
                debe NUMERIC(18,2) NOT NULL DEFAULT 0,
                haber NUMERIC(18,2) NOT NULL DEFAULT 0,
                debe_base NUMERIC(18,2) NOT NULL DEFAULT 0,
                haber_base NUMERIC(18,2) NOT NULL DEFAULT 0,
                glosa TEXT,
                CHECK ( (debe >= 0 AND haber >= 0) AND (debe > 0 OR haber > 0) )
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_periodo_cerrado (
                id SERIAL PRIMARY KEY,
                empresa_id INT NOT NULL REFERENCES finanzas2.cont_empresa(id),
                anio INT NOT NULL,
                mes INT NOT NULL,
                cerrado BOOLEAN NOT NULL DEFAULT false,
                cerrado_por TEXT,
                cerrado_at TIMESTAMP,
                UNIQUE (empresa_id, anio, mes)
            )
        """)
        # Indexes for asientos
        asiento_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_cont_asiento_empresa_fecha ON finanzas2.cont_asiento(empresa_id, fecha_contable)",
            "CREATE INDEX IF NOT EXISTS idx_cont_asiento_origen ON finanzas2.cont_asiento(empresa_id, origen_tipo, origen_id)",
            "CREATE INDEX IF NOT EXISTS idx_cont_asiento_linea_cuenta ON finanzas2.cont_asiento_linea(empresa_id, cuenta_id)",
            "CREATE INDEX IF NOT EXISTS idx_cont_asiento_linea_asiento ON finanzas2.cont_asiento_linea(asiento_id)",
        ]
        for stmt in asiento_indexes:
            await conn.execute(stmt)

        # Migration: add cuenta_contable_id to cont_cuenta_financiera
        await conn.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_cuenta_financiera' AND column_name='cuenta_contable_id') THEN
                    ALTER TABLE finanzas2.cont_cuenta_financiera ADD COLUMN cuenta_contable_id INT REFERENCES finanzas2.cont_cuenta(id);
                END IF;
            END $$;
        """)

        # Table: cont_retencion_detalle (manual retention/deduction fields per document)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_retencion_detalle (
                id SERIAL PRIMARY KEY,
                empresa_id INT NOT NULL REFERENCES finanzas2.cont_empresa(id),
                origen_tipo TEXT NOT NULL CHECK (origen_tipo IN ('FPROV','GASTO')),
                origen_id INT NOT NULL,
                r_doc TEXT, r_numero TEXT, r_fecha DATE,
                d_numero TEXT, d_fecha DATE,
                retencion_01 SMALLINT,
                pdb_ndes TEXT, codtasa TEXT, ind_ret TEXT,
                b_imp NUMERIC(18,2), igv_ret NUMERIC(18,2),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (empresa_id, origen_tipo, origen_id)
            )
        """)

        # Migration: add persona natural fields to cont_tercero
        await conn.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_tercero' AND column_name='tipo_persona') THEN
                    ALTER TABLE finanzas2.cont_tercero ADD COLUMN tipo_persona TEXT;
                    ALTER TABLE finanzas2.cont_tercero ADD COLUMN tip_doc_iden TEXT;
                    ALTER TABLE finanzas2.cont_tercero ADD COLUMN apellido1 TEXT;
                    ALTER TABLE finanzas2.cont_tercero ADD COLUMN apellido2 TEXT;
                    ALTER TABLE finanzas2.cont_tercero ADD COLUMN nombres TEXT;
                END IF;
            END $$;
        """)

        # ══════════════════════════════════════
        # FASE 1: FINANZAS GERENCIALES
        # ══════════════════════════════════════

        # -- cont_marca
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_marca (
                id SERIAL PRIMARY KEY,
                empresa_id INT NOT NULL REFERENCES finanzas2.cont_empresa(id),
                nombre VARCHAR(100) NOT NULL,
                codigo VARCHAR(20),
                odoo_marca_key VARCHAR(100),
                activo BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # -- cont_proyecto
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_proyecto (
                id SERIAL PRIMARY KEY,
                empresa_id INT NOT NULL REFERENCES finanzas2.cont_empresa(id),
                nombre VARCHAR(200) NOT NULL,
                codigo VARCHAR(30),
                marca_id INT REFERENCES finanzas2.cont_marca(id),
                linea_negocio_id INT REFERENCES finanzas2.cont_linea_negocio(id),
                centro_costo_id INT REFERENCES finanzas2.cont_centro_costo(id),
                fecha_inicio DATE,
                fecha_fin DATE,
                presupuesto NUMERIC(14,2) DEFAULT 0,
                estado VARCHAR(20) DEFAULT 'activo',
                notas TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # -- cont_cxc_abono
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_cxc_abono (
                id SERIAL PRIMARY KEY,
                empresa_id INT NOT NULL REFERENCES finanzas2.cont_empresa(id),
                cxc_id INT NOT NULL REFERENCES finanzas2.cont_cxc(id) ON DELETE CASCADE,
                fecha DATE NOT NULL,
                monto NUMERIC(14,2) NOT NULL,
                cuenta_financiera_id INT REFERENCES finanzas2.cont_cuenta_financiera(id),
                forma_pago VARCHAR(30),
                referencia VARCHAR(200),
                notas TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # -- cont_cxp_abono
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_cxp_abono (
                id SERIAL PRIMARY KEY,
                empresa_id INT NOT NULL REFERENCES finanzas2.cont_empresa(id),
                cxp_id INT NOT NULL REFERENCES finanzas2.cont_cxp(id) ON DELETE CASCADE,
                fecha DATE NOT NULL,
                monto NUMERIC(14,2) NOT NULL,
                cuenta_financiera_id INT REFERENCES finanzas2.cont_cuenta_financiera(id),
                forma_pago VARCHAR(30),
                referencia VARCHAR(200),
                notas TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # -- Migrations: extend cont_venta_pos_estado with cobranza fields
        await conn.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_venta_pos_estado' AND column_name='monto_cobrado') THEN
                    ALTER TABLE finanzas2.cont_venta_pos_estado ADD COLUMN monto_cobrado NUMERIC(14,2) DEFAULT 0;
                    ALTER TABLE finanzas2.cont_venta_pos_estado ADD COLUMN saldo_pendiente NUMERIC(14,2) DEFAULT 0;
                    ALTER TABLE finanzas2.cont_venta_pos_estado ADD COLUMN estado_cobranza VARCHAR(20) DEFAULT 'no_cobrado';
                END IF;
            END $$;
        """)

        # -- Migrations: extend cont_cxc with analytical fields
        await conn.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_cxc' AND column_name='tipo_origen') THEN
                    ALTER TABLE finanzas2.cont_cxc ADD COLUMN tipo_origen VARCHAR(30);
                    ALTER TABLE finanzas2.cont_cxc ADD COLUMN documento_referencia VARCHAR(100);
                    ALTER TABLE finanzas2.cont_cxc ADD COLUMN odoo_order_id INT;
                    ALTER TABLE finanzas2.cont_cxc ADD COLUMN marca_id INT;
                    ALTER TABLE finanzas2.cont_cxc ADD COLUMN linea_negocio_id INT;
                    ALTER TABLE finanzas2.cont_cxc ADD COLUMN centro_costo_id INT;
                    ALTER TABLE finanzas2.cont_cxc ADD COLUMN proyecto_id INT;
                    ALTER TABLE finanzas2.cont_cxc ADD COLUMN dias_atraso INT DEFAULT 0;
                END IF;
            END $$;
        """)

        # -- Migrations: extend cont_cxp with analytical fields
        await conn.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_cxp' AND column_name='tipo_origen') THEN
                    ALTER TABLE finanzas2.cont_cxp ADD COLUMN tipo_origen VARCHAR(30);
                    ALTER TABLE finanzas2.cont_cxp ADD COLUMN documento_referencia VARCHAR(100);
                    ALTER TABLE finanzas2.cont_cxp ADD COLUMN marca_id INT;
                    ALTER TABLE finanzas2.cont_cxp ADD COLUMN linea_negocio_id INT;
                    ALTER TABLE finanzas2.cont_cxp ADD COLUMN centro_costo_id INT;
                    ALTER TABLE finanzas2.cont_cxp ADD COLUMN proyecto_id INT;
                    ALTER TABLE finanzas2.cont_cxp ADD COLUMN dias_vencido INT DEFAULT 0;
                    ALTER TABLE finanzas2.cont_cxp ADD COLUMN categoria_id INT;
                END IF;
            END $$;
        """)

        # -- Migrations: add marca_id, proyecto_id to cont_gasto
        await conn.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_gasto' AND column_name='marca_id') THEN
                    ALTER TABLE finanzas2.cont_gasto ADD COLUMN marca_id INT;
                    ALTER TABLE finanzas2.cont_gasto ADD COLUMN proyecto_id INT;
                END IF;
            END $$;
        """)

        # -- Migrations: add marca_id, proyecto_id to cont_pago
        await conn.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_pago' AND column_name='marca_id') THEN
                    ALTER TABLE finanzas2.cont_pago ADD COLUMN marca_id INT;
                    ALTER TABLE finanzas2.cont_pago ADD COLUMN proyecto_id INT;
                END IF;
            END $$;
        """)

        # -- Migrations: extend cont_presupuesto_linea
        await conn.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_presupuesto_linea' AND column_name='marca_id') THEN
                    ALTER TABLE finanzas2.cont_presupuesto_linea ADD COLUMN marca_id INT;
                    ALTER TABLE finanzas2.cont_presupuesto_linea ADD COLUMN proyecto_id INT;
                    ALTER TABLE finanzas2.cont_presupuesto_linea ADD COLUMN tipo VARCHAR(20) DEFAULT 'gasto';
                END IF;
            END $$;
        """)

        # -- Migrations: add odoo_order_id to cont_venta_pos_pago (for Odoo-source orders)
        await conn.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_venta_pos_pago' AND column_name='odoo_order_id') THEN
                    ALTER TABLE finanzas2.cont_venta_pos_pago ADD COLUMN odoo_order_id INT;
                    ALTER TABLE finanzas2.cont_venta_pos_pago ADD COLUMN cuenta_financiera_id INT REFERENCES finanzas2.cont_cuenta_financiera(id);
                END IF;
            END $$;
        """)

        # -- Indexes for Fase 1
        fase1_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_cont_marca_empresa ON finanzas2.cont_marca(empresa_id)",
            "CREATE INDEX IF NOT EXISTS idx_cont_proyecto_empresa ON finanzas2.cont_proyecto(empresa_id)",
            "CREATE INDEX IF NOT EXISTS idx_cont_cxc_abono_cxc ON finanzas2.cont_cxc_abono(cxc_id)",
            "CREATE INDEX IF NOT EXISTS idx_cont_cxp_abono_cxp ON finanzas2.cont_cxp_abono(cxp_id)",
            "CREATE INDEX IF NOT EXISTS idx_cont_cxc_odoo_order ON finanzas2.cont_cxc(odoo_order_id)",
        ]
        for stmt in fase1_indexes:
            await conn.execute(stmt)

        # ══════════════════════════════════════
        # REFACTORING: CAPA DE TESORERIA
        # ══════════════════════════════════════

        # -- cont_movimiento_tesoreria: Fuente unica de verdad UNIFICADA de todos los movimientos
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_movimiento_tesoreria (
                id SERIAL PRIMARY KEY,
                empresa_id INT NOT NULL REFERENCES finanzas2.cont_empresa(id),
                fecha DATE NOT NULL,
                tipo VARCHAR(10) NOT NULL CHECK (tipo IN ('ingreso', 'egreso')),
                monto NUMERIC(15,2) NOT NULL CHECK (monto > 0),
                cuenta_financiera_id INT REFERENCES finanzas2.cont_cuenta_financiera(id),
                forma_pago VARCHAR(50),
                referencia VARCHAR(200),
                concepto TEXT,
                -- Trazabilidad de origen
                origen_tipo VARCHAR(30) NOT NULL,
                origen_id INT,
                -- Documento vinculado (factura, letra, etc.)
                documento_tipo VARCHAR(30),
                documento_id INT,
                -- Campos unificados de cont_pago
                numero VARCHAR(50),
                moneda_id INT REFERENCES finanzas2.cont_moneda(id),
                conciliado BOOLEAN DEFAULT FALSE,
                -- Dimensiones analiticas
                marca_id INT REFERENCES finanzas2.cont_marca(id),
                linea_negocio_id INT REFERENCES finanzas2.cont_linea_negocio(id),
                centro_costo_id INT REFERENCES finanzas2.cont_centro_costo(id),
                proyecto_id INT REFERENCES finanzas2.cont_proyecto(id),
                -- Metadata
                notas TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # Add unified columns if not exist (migration for existing tables)
        for col_def in [
            ("numero", "VARCHAR(50)"),
            ("moneda_id", "INT REFERENCES finanzas2.cont_moneda(id)"),
            ("conciliado", "BOOLEAN DEFAULT FALSE"),
            ("documento_tipo", "VARCHAR(30)"),
            ("documento_id", "INT"),
        ]:
            try:
                await conn.execute(f"ALTER TABLE finanzas2.cont_movimiento_tesoreria ADD COLUMN IF NOT EXISTS {col_def[0]} {col_def[1]}")
            except Exception:
                pass

        # -- Indexes for tesoreria
        tesoreria_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_mov_tesoreria_empresa ON finanzas2.cont_movimiento_tesoreria(empresa_id)",
            "CREATE INDEX IF NOT EXISTS idx_mov_tesoreria_fecha ON finanzas2.cont_movimiento_tesoreria(empresa_id, fecha)",
            "CREATE INDEX IF NOT EXISTS idx_mov_tesoreria_tipo ON finanzas2.cont_movimiento_tesoreria(empresa_id, tipo)",
            "CREATE INDEX IF NOT EXISTS idx_mov_tesoreria_origen ON finanzas2.cont_movimiento_tesoreria(empresa_id, origen_tipo, origen_id)",
        ]
        for stmt in tesoreria_indexes:
            await conn.execute(stmt)

        # ══════════════════════════════════════
        # CAPITAL POR LINEA DE NEGOCIO
        # ══════════════════════════════════════
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_capital_linea_negocio (
                id SERIAL PRIMARY KEY,
                empresa_id INT NOT NULL REFERENCES finanzas2.cont_empresa(id),
                linea_negocio_id INT NOT NULL REFERENCES finanzas2.cont_linea_negocio(id),
                marca_id INT REFERENCES finanzas2.cont_marca(id),
                proyecto_id INT REFERENCES finanzas2.cont_proyecto(id),
                fecha DATE NOT NULL,
                tipo_movimiento VARCHAR(20) NOT NULL CHECK (tipo_movimiento IN ('capital_inicial', 'aporte', 'retiro')),
                monto NUMERIC(15,2) NOT NULL CHECK (monto > 0),
                observacion TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_capital_ln_empresa ON finanzas2.cont_capital_linea_negocio(empresa_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_capital_ln_linea ON finanzas2.cont_capital_linea_negocio(empresa_id, linea_negocio_id)")

        # ══════════════════════════════════════
        # MAPEO ODOO -> LINEA DE NEGOCIO
        # ══════════════════════════════════════
        for col_stmt in [
            "ALTER TABLE finanzas2.cont_linea_negocio ADD COLUMN IF NOT EXISTS odoo_linea_negocio_id INT",
            "ALTER TABLE finanzas2.cont_linea_negocio ADD COLUMN IF NOT EXISTS odoo_linea_negocio_nombre VARCHAR(200)",
        ]:
            try:
                await conn.execute(col_stmt)
            except Exception:
                pass
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_ln_odoo_id ON finanzas2.cont_linea_negocio(empresa_id, odoo_linea_negocio_id)")

        # ══════════════════════════════════════
        # DESACOPLAMIENTO ODOO: campos linea_negocio en detalle POS
        # ══════════════════════════════════════
        for col_stmt in [
            "ALTER TABLE finanzas2.cont_venta_pos_linea ADD COLUMN IF NOT EXISTS odoo_linea_negocio_id INT",
            "ALTER TABLE finanzas2.cont_venta_pos_linea ADD COLUMN IF NOT EXISTS odoo_linea_negocio_nombre VARCHAR(200)",
        ]:
            try:
                await conn.execute(col_stmt)
            except Exception:
                pass

        # ══════════════════════════════════════
        # DISTRIBUCION ANALITICA POR LINEA DE NEGOCIO
        # ══════════════════════════════════════
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_distribucion_analitica (
                id SERIAL PRIMARY KEY,
                empresa_id INT NOT NULL,
                origen_tipo VARCHAR(30) NOT NULL,
                origen_id INT NOT NULL,
                linea_negocio_id INT REFERENCES finanzas2.cont_linea_negocio(id),
                categoria_id INT REFERENCES finanzas2.cont_categoria(id),
                centro_costo_id INT REFERENCES finanzas2.cont_centro_costo(id),
                monto NUMERIC(15,2) NOT NULL,
                fecha DATE NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_distribucion_analitica' AND column_name='categoria_id') THEN
                    ALTER TABLE finanzas2.cont_distribucion_analitica ADD COLUMN categoria_id INT REFERENCES finanzas2.cont_categoria(id);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_distribucion_analitica' AND column_name='centro_costo_id') THEN
                    ALTER TABLE finanzas2.cont_distribucion_analitica ADD COLUMN centro_costo_id INT REFERENCES finanzas2.cont_centro_costo(id);
                END IF;
            END $$;
        """)
        # Migration: fix FK from cont_categoria_gasto to cont_categoria
        await conn.execute("""
            DO $$ BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.constraint_column_usage ccu
                    JOIN information_schema.table_constraints tc ON tc.constraint_name = ccu.constraint_name
                    WHERE tc.table_name = 'cont_distribucion_analitica' AND tc.constraint_type = 'FOREIGN KEY'
                    AND ccu.table_name = 'cont_categoria_gasto' AND ccu.column_name = 'id'
                ) THEN
                    ALTER TABLE finanzas2.cont_distribucion_analitica DROP CONSTRAINT cont_distribucion_analitica_categoria_id_fkey;
                    ALTER TABLE finanzas2.cont_distribucion_analitica ADD CONSTRAINT cont_distribucion_analitica_categoria_id_fkey FOREIGN KEY (categoria_id) REFERENCES finanzas2.cont_categoria(id);
                END IF;
            END $$;
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_dist_analitica_empresa ON finanzas2.cont_distribucion_analitica(empresa_id, origen_tipo)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_dist_analitica_ln ON finanzas2.cont_distribucion_analitica(empresa_id, linea_negocio_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_dist_analitica_origen ON finanzas2.cont_distribucion_analitica(empresa_id, origen_tipo, origen_id)")

        # Unique indexes for sync upsert
        await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_venta_pos_empresa_odoo ON finanzas2.cont_venta_pos(empresa_id, odoo_id)")
        await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_venta_pos_linea_empresa_odoo ON finanzas2.cont_venta_pos_linea(empresa_id, odoo_line_id)")

        # ══════════════════════════════════════
        # CATEGORIA DE GASTO
        # ══════════════════════════════════════
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_categoria_gasto (
                id SERIAL PRIMARY KEY,
                empresa_id INT NOT NULL REFERENCES finanzas2.cont_empresa(id),
                codigo VARCHAR(20),
                nombre VARCHAR(200) NOT NULL,
                activo BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # ══════════════════════════════════════
        # TIPO ASIGNACION Y CATEGORIA EN GASTO
        # ══════════════════════════════════════
        for col_stmt in [
            "ALTER TABLE finanzas2.cont_gasto ADD COLUMN IF NOT EXISTS tipo_asignacion VARCHAR(20) DEFAULT 'no_asignado'",
            "ALTER TABLE finanzas2.cont_gasto ADD COLUMN IF NOT EXISTS categoria_gasto_id INT REFERENCES finanzas2.cont_categoria_gasto(id)",
            "ALTER TABLE finanzas2.cont_gasto ADD COLUMN IF NOT EXISTS centro_costo_id INT REFERENCES finanzas2.cont_centro_costo(id)",
            "ALTER TABLE finanzas2.cont_gasto ADD COLUMN IF NOT EXISTS linea_negocio_id INT REFERENCES finanzas2.cont_linea_negocio(id)",
        ]:
            try:
                await conn.execute(col_stmt)
            except Exception:
                pass

        # ══════════════════════════════════════
        # PRORRATEO DE GASTOS COMUNES
        # ══════════════════════════════════════
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS finanzas2.cont_prorrateo_gasto (
                id SERIAL PRIMARY KEY,
                empresa_id INT NOT NULL,
                gasto_id INT NOT NULL REFERENCES finanzas2.cont_gasto(id),
                linea_negocio_id INT NOT NULL REFERENCES finanzas2.cont_linea_negocio(id),
                monto NUMERIC(15,2) NOT NULL,
                porcentaje NUMERIC(8,4) NOT NULL,
                metodo VARCHAR(20) NOT NULL,
                periodo_desde DATE,
                periodo_hasta DATE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_prorrateo_empresa ON finanzas2.cont_prorrateo_gasto(empresa_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_prorrateo_gasto ON finanzas2.cont_prorrateo_gasto(gasto_id)")


        # ══════════════════════════════════════
        # UNIFICACIÓN PAGOS: cont_movimiento_tesoreria como fuente única
        # ══════════════════════════════════════
        await conn.execute("""
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_pago_aplicacion' AND column_name='movimiento_tesoreria_id') THEN
                    ALTER TABLE finanzas2.cont_pago_aplicacion ADD COLUMN movimiento_tesoreria_id INT REFERENCES finanzas2.cont_movimiento_tesoreria(id) ON DELETE CASCADE;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='finanzas2' AND table_name='cont_pago_detalle' AND column_name='movimiento_tesoreria_id') THEN
                    ALTER TABLE finanzas2.cont_pago_detalle ADD COLUMN movimiento_tesoreria_id INT REFERENCES finanzas2.cont_movimiento_tesoreria(id) ON DELETE CASCADE;
                END IF;
            END $$;
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_pago_aplicacion_mov_tes ON finanzas2.cont_pago_aplicacion(movimiento_tesoreria_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_pago_detalle_mov_tes ON finanzas2.cont_pago_detalle(movimiento_tesoreria_id)")

        logger.info("Schema finanzas2 and all tables created/verified successfully")
