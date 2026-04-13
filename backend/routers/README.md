# Routers Activos — Finanzas Backend

| Router | Archivo | Dominio |
|--------|---------|---------|
| core | core.py | Health check y status de BD |
| dashboard | dashboard.py | KPIs ejecutivos y resumen gerencial |
| empresas | empresas.py | CRUD multi-empresa con auto-seed |
| maestros | maestros.py | Monedas, categorias, centros de costo, lineas de negocio |
| cuentas_financieras | cuentas_financieras.py | Cuentas bancarias, cajas, kardex de saldos |
| terceros | terceros.py | Proveedores, clientes, empleados (multi-rol) |
| inventario_core | inventario_core.py | Lectura de inventario desde schema produccion |
| compras | compras.py | Ordenes de compra, facturas proveedor, vinculacion MP |
| pagos | pagos.py | Pagos unificados, letras, aplicaciones multi-documento |
| gastos | gastos.py | Gastos con lineas, adelantos de empleados |
| ventas_pos | ventas_pos.py | Ventas POS: sync Odoo, estados, pagos, distribucion |
| cxc_cxp | cxc_cxp.py | Cuentas por cobrar y pagar con abonos |
| banco | banco.py | Conciliacion bancaria: import Excel, matching, historial |
| reportes | reportes.py | Balance, estado resultados, flujo caja, aging, rentabilidad |
| core_contabilidad | core_contabilidad.py | Plan de cuentas y generacion de asientos |
| export | export.py | Exportacion CompraAPP |
| marcas | marcas.py | CRUD marcas/brands |
| flujo_caja | flujo_caja.py | Flujo de caja gerencial con proyecciones |
| tesoreria | tesoreria.py | Posicion de caja en tiempo real |
| valorizacion | valorizacion.py | Valorizacion FIFO de inventario |
| categorias_gasto | categorias_gasto.py | CRUD categorias de gasto |
| prorrateo | prorrateo.py | Distribucion de gastos comunes entre lineas de negocio |
| reportes_simplificados | reportes_simplificados.py | Reportes rapidos: ventas, ingresos, gastos por dimension |
| reportes_linea | reportes_linea.py | Reportes cruzados por linea de negocio |
| libro_analitico | libro_analitico.py | Libro analitico con export Excel |
| unidades_internas | unidades_internas.py | Unidades internas, personas produccion, cargos |
| planilla | planilla.py | Planilla: trabajadores, detalles, resumen |

## Legacy (desactivados)

Archivados en `_legacy_archivo/`. No se importan en server.py.

| Archivo | Motivo |
|---------|--------|
| contabilidad.py | Fase 3 — extraido a core_contabilidad.py |
| articulos.py | Fase 3 — extraido a inventario_core.py |
| finanzas_gerencial.py | Fase 3 — extraido a flujo_caja.py + reportes.py |
| planillas.py | Fase 2 — reemplazado por planilla.py |
| presupuestos.py | Fase 2 — funcionalidad incompleta |
| proyectos.py | Fase 2 — funcionalidad incompleta |
| capital_linea.py | Fase 2 — capital por linea |
| dashboard_financiero.py | Fase 2 — reemplazado por dashboard.py |
| reportes_gerenciales.py | Fase 2 — extraido a modulos especificos |
