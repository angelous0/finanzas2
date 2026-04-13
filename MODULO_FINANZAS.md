# Modulo Finanzas 4.0

Sistema de gestion financiera para ERP textil. Cubre compras, pagos, gastos, ventas POS (Odoo), cuentas por cobrar/pagar, conciliacion bancaria, planilla y reporteria gerencial.

## Puertos

| Servicio | Puerto | URL |
|----------|--------|-----|
| Frontend | 3001 | http://localhost:3001 |
| Backend | 8001 | http://localhost:8001 |
| Docs API | 8001 | http://localhost:8001/docs |

## Como levantar

```bash
# Desde la raiz de erp-textil/
./start-finanzas.sh
```

## Secciones del Sidebar

### Operaciones
| Seccion | Ruta | Que hace | Estado |
|---------|------|----------|--------|
| Dashboard | `/` | KPIs ejecutivos: CxP, CxC, saldos bancarios, ventas/gastos del mes | Funciona |
| Ventas POS | `/ventas-pos` | Sync desde Odoo, confirmar/descartar, pagos, distribucion analitica | Funciona |
| CxC | `/cxc` | Cuentas por cobrar con aging (vigente, 0-30, 31-60, 61-90, 90+), abonos | Funciona |
| Gastos | `/gastos` | Gastos multi-linea con categorias, prorrateo, compliance SUNAT | Funciona |
| Prorrateo | `/prorrateo` | Distribucion de gastos comunes entre lineas de negocio por proporcion de ventas | Funciona |
| Factura Proveedor | `/facturas-proveedor` | CRUD facturas, vinculacion con ingresos MP, canje por letras | Funciona |
| Ordenes de Compra | `/ordenes-compra` | OC con lineas, generacion automatica de factura | Funciona |
| CxP | `/cxp` | Cuentas por pagar con abonos | Funciona |
| Letras | `/letras` | Letras de cambio generadas desde facturas | Funciona |

### Tesoreria
| Seccion | Ruta | Que hace | Estado |
|---------|------|----------|--------|
| Tesoreria | `/tesoreria` | Movimientos reales de caja/banco - fuente unica de verdad | Funciona |
| Cuentas Bancarias | `/cuentas-bancarias` | Setup de cuentas, mapeo contable | Funciona |
| Pagos | `/pagos` | Registro de pagos con detalles (efectivo/transferencia/cheque/tarjeta) y aplicaciones multi-documento | Funciona |
| Conciliacion | `/conciliacion` | Import Excel (BCP, BBVA, IBK), matching automatico/manual | Funciona |
| Historial Conciliaciones | `/historial-conciliaciones` | Audit trail de conciliaciones | Funciona |

### Reportes
| Seccion | Ruta | Que hace | Estado |
|---------|------|----------|--------|
| Reportes Financieros | `/reportes-financieros` | Balance general, estado resultados, flujo caja, aging CxP/CxC, rentabilidad | Funciona |
| Libro Analitico | `/libro-analitico` | Libro analitico con export Excel | Funciona |
| Valorizacion Inventario | `/valorizacion-inventario` | Inventario valorizado FIFO desde schema produccion | Funciona |

### Produccion Interna
| Seccion | Ruta | Que hace | Estado |
|---------|------|----------|--------|
| Unidades Internas | `/unidades-internas` | Unidades organizacionales internas | Funciona |
| Cargos Internos | `/cargos-internos` | Auto-generacion de cargos desde produccion | Funciona |
| Gastos Unidad | `/gastos-unidad-interna` | Gastos por unidad interna | Funciona |
| Reporte Gerencial | `/reporte-unidades-internas` | Reporte consolidado de unidades | Funciona |
| Planilla | `/planilla` | Planillas quincenales/mensuales con detalle por trabajador | Funciona |

### Catalogos
| Seccion | Ruta | Que hace | Estado |
|---------|------|----------|--------|
| Lineas de Negocio | `/lineas-negocio` | Segmentos de negocio (element, qepo, etc.) | Funciona |
| Marcas | `/marcas` | Marcas de producto | Funciona |
| Centros de Costo | `/centros-costo` | Centros de costo (admin, ventas, operaciones) | Funciona |
| Categorias | `/categorias-gasto` | Categorias de gasto | Funciona |
| Proveedores | `/proveedores` | Maestro de proveedores | Funciona |
| Clientes | `/clientes` | Maestro de clientes | Placeholder |
| Empresas | `/empresas` | Multi-empresa con auto-seed | Funciona |

### Paginas sin ruta (huerfanas)
- `FlujoCaja.jsx` — existe en src/pages/ pero no tiene ruta en App.js
- `RentabilidadLinea.jsx` — existe en src/pages/ pero no tiene ruta en App.js
- `ReportesSimplificados.jsx` — existe en src/pages/ pero no tiene ruta en App.js

## Dependencias cross-schema con produccion

Ambos schemas (`finanzas2` y `produccion`) viven en la misma BD `datos` en PostgreSQL 9595. Las queries cross-schema funcionan via JOINs directos.

### Tablas de produccion leidas por Finanzas

| Tabla | Usado en | Para que |
|-------|----------|----------|
| `prod_inventario` | inventario_core, compras, reportes, valorizacion | Inventario de materiales |
| `prod_inventario_ingresos` | inventario_core, compras, reportes, valorizacion | Ingresos de MP |
| `prod_inventario_salidas` | reportes, valorizacion | Salidas de MP |
| `prod_registros` | inventario_core, unidades_internas | Registros de produccion |
| `prod_modelos` | inventario_core | Modelos de producto |
| `prod_personas_produccion` | planilla, unidades_internas | Trabajadores |
| `prod_servicios_produccion` | compras | Servicios tercerizados |
| `prod_movimientos_produccion` | unidades_internas | Movimientos de produccion |
| `prod_registro_requerimiento_mp` | reportes | Requerimientos de MP |
| `prod_registro_costos_servicio` | reportes | Costos de servicios |

### Tablas de finanzas2 leidas por Produccion

| Tabla | Usado en | Para que |
|-------|----------|----------|
| `cont_empresa` | catalogos, cierre, costos, reportes_valorizacion | Empresa activa |
| `cont_linea_negocio` | catalogos, inventario, registros, modelos, trazabilidad, auditoria, transferencias | Linea de negocio |
| `cont_tercero` | integracion_finanzas | Proveedores |
| `cont_factura_proveedor` | integracion_finanzas | Facturas vinculadas a ingresos MP |
| `cont_factura_ingreso_mp` | integracion_finanzas, inventario | Bridge table factura-ingreso |
| `fin_unidad_interna` | integracion_finanzas, catalogos | Unidades internas |

## Stack tecnico

- **Backend**: FastAPI + asyncpg (raw SQL) + PostgreSQL
- **Frontend**: React 19 + Tailwind + shadcn/ui + Axios
- **Build**: CRA + CRACO
- **Estado**: Context API (EmpresaContext)
- **Base de datos**: PostgreSQL en 72.60.241.216:9595, BD `datos`, schema `finanzas2`
