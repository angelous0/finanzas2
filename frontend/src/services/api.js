import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';
const API = `${API_URL}/api`;

const api = axios.create({
  baseURL: API,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor: inject empresa_id on every request (except global endpoints)
const GLOBAL_ENDPOINTS = ['/empresas', '/monedas'];

api.interceptors.request.use((config) => {
  const url = config.url || '';
  const isGlobal = GLOBAL_ENDPOINTS.some(ep => url === ep || url.startsWith(ep + '/'));
  if (!isGlobal) {
    const empresaId = localStorage.getItem('empresaActualId');
    if (empresaId) {
      config.params = { ...config.params, empresa_id: parseInt(empresaId) };
    }
  }
  return config;
});

// Dashboard
export const getDashboardResumen = () => api.get('/dashboard/resumen-ejecutivo');

// Empresas
export const getEmpresas = () => api.get('/empresas');
export const createEmpresa = (data) => api.post('/empresas', data);
export const updateEmpresa = (id, data) => api.put(`/empresas/${id}`, data);
export const deleteEmpresa = (id) => api.delete(`/empresas/${id}`);

// Monedas
export const getMonedas = () => api.get('/monedas');

// Categorias
export const getCategorias = (tipo) => api.get('/categorias', { params: { tipo } });
export const createCategoria = (data) => api.post('/categorias', data);
export const updateCategoria = (id, data) => api.put(`/categorias/${id}`, data);
export const deleteCategoria = (id) => api.delete(`/categorias/${id}`);

// Centros de Costo
export const getCentrosCosto = () => api.get('/centros-costo');
export const createCentroCosto = (data) => api.post('/centros-costo', data);
export const updateCentroCosto = (id, data) => api.put(`/centros-costo/${id}`, data);
export const deleteCentroCosto = (id) => api.delete(`/centros-costo/${id}`);

// Lineas de Negocio
export const getLineasNegocio = () => api.get('/lineas-negocio');
export const getLineaNegocioDetalle = (id) => api.get(`/lineas-negocio/${id}/detalle`);
export const getOdooLineasNegocioOpciones = () => api.get('/lineas-negocio/odoo-opciones');
export const createLineaNegocio = (data) => api.post('/lineas-negocio', data);
export const updateLineaNegocio = (id, data) => api.put(`/lineas-negocio/${id}`, data);
export const deleteLineaNegocio = (id) => api.delete(`/lineas-negocio/${id}`);

// Cuentas Financieras
export const getCuentasFinancieras = (tipo) => api.get('/cuentas-financieras', { params: { tipo } });
export const createCuentaFinanciera = (data) => api.post('/cuentas-financieras', data);
export const updateCuentaFinanciera = (id, data) => api.put(`/cuentas-financieras/${id}`, data);
export const deleteCuentaFinanciera = (id) => api.delete(`/cuentas-financieras/${id}`);
export const getKardexCuenta = (id, params) => api.get(`/cuentas-financieras/${id}/kardex`, { params });
export const recalcularSaldos = () => api.post('/cuentas-financieras/recalcular-saldos');
export const getResumenCuentasInternas = (params) => api.get('/cuentas-internas/resumen', { params });

// Terceros (Proveedores, Clientes, Empleados)
export const getTerceros = (params) => api.get('/terceros', { params });
export const getTercero = (id) => api.get(`/terceros/${id}`);
export const createTercero = (data) => api.post('/terceros', data);
export const updateTercero = (id, data) => api.put(`/terceros/${id}`, data);
export const deleteTercero = (id) => api.delete(`/terceros/${id}`);
export const getProveedores = (search) => api.get('/proveedores', { params: { search } });
export const getEmpleados = (search) => api.get('/empleados', { params: { search } });

// Inventario (public.prod_inventario)
export const getInventario = (search) => api.get('/inventario', { params: { search } });
export const getArticulosOC = (search) => api.get('/articulos-oc', { params: { search } });

// Modelos/Cortes (public.prod_registros + prod_modelos)
export const getModelosCortes = (search) => api.get('/modelos-cortes', { params: { search } });
export const getModelos = (search) => api.get('/modelos', { params: { search } });

// Servicios de Produccion
export const getServiciosProduccion = () => api.get('/servicios-produccion');


// Ordenes de Compra (REVISAR Fase 2)
export const getOrdenesCompra = (params) => api.get('/ordenes-compra', { params });
export const getOrdenCompra = (id) => api.get(`/ordenes-compra/${id}`);
export const createOrdenCompra = (data) => api.post('/ordenes-compra', data);
export const updateOrdenCompra = (id, data) => api.put(`/ordenes-compra/${id}`, data);
export const deleteOrdenCompra = (id) => api.delete(`/ordenes-compra/${id}`);
export const generarFacturaDesdeOC = (id) => api.post(`/ordenes-compra/${id}/generar-factura`);

// Facturas Proveedor
export const getFacturasProveedor = (params) => api.get('/facturas-proveedor', { params });
export const getFacturaProveedor = (id) => api.get(`/facturas-proveedor/${id}`);
export const createFacturaProveedor = (data) => api.post('/facturas-proveedor', data);
export const updateFacturaProveedor = (id, data) => api.put(`/facturas-proveedor/${id}`, data);
export const deleteFacturaProveedor = (id) => api.delete(`/facturas-proveedor/${id}`);

// Pagos
export const getPagos = (params) => api.get('/pagos', { params });
export const getPago = (id) => api.get(`/pagos/${id}`);
export const createPago = (data) => api.post('/pagos', data);
export const updatePago = (id, data) => api.put(`/pagos/${id}`, data);
export const deletePago = (id) => api.delete(`/pagos/${id}`);
export const getPagosDeFactura = (facturaId) => api.get(`/facturas-proveedor/${facturaId}/pagos`);

// Letras (REVISAR Fase 2)
export const getLetras = (params) => api.get('/letras', { params });
export const getLetra = (id) => api.get(`/letras/${id}`);
export const generarLetras = (data) => api.post('/letras/generar', data);
export const deleteLetra = (id) => api.delete(`/letras/${id}`);
export const updateLetraNumeroUnico = (id, data) => api.put(`/letras/${id}/numero-unico`, data);
export const getLetrasDeFactura = (facturaId) => api.get(`/facturas-proveedor/${facturaId}/letras`);
export const deshacerCanjeLetras = (facturaId) => api.post(`/facturas-proveedor/${facturaId}/deshacer-canje`);

// Vinculaciones Factura ↔ Ingresos MP
export const getVinculacionesFactura = (facturaId) => api.get(`/facturas-proveedor/${facturaId}/vinculaciones`);
export const getIngresosDisponibles = (facturaId, lineaId) => api.get(`/facturas-proveedor/${facturaId}/linea/${lineaId}/ingresos-disponibles`);
export const vincularIngreso = (facturaId, lineaId, data) => api.post(`/facturas-proveedor/${facturaId}/linea/${lineaId}/vincular-ingreso`, data);
export const desvincularIngreso = (vinculacionId) => api.delete(`/facturas-proveedor/vinculacion/${vinculacionId}`);


// Gastos
export const getGastos = (params) => api.get('/gastos', { params });
export const getGasto = (id) => api.get(`/gastos/${id}`);
export const createGasto = (data) => api.post('/gastos', data);
export const updateGasto = (id, data) => api.put(`/gastos/${id}`, data);
export const deleteGasto = (id) => api.delete(`/gastos/${id}`);
export const deleteGastoPago = (gastoId, pagoId) => api.delete(`/gastos/${gastoId}/pagos/${pagoId}`);
export const getCifProduccion = (params) => api.get('/gastos/cif-produccion', { params });

// Categorias de Gasto
export const getCategoriasGasto = () => api.get('/categorias-gasto');
export const createCategoriaGasto = (data) => api.post('/categorias-gasto', data);
export const updateCategoriaGasto = (id, data) => api.put(`/categorias-gasto/${id}`, data);
export const deleteCategoriaGasto = (id) => api.delete(`/categorias-gasto/${id}`);

// Prorrateo
export const getProrratePendientes = (params) => api.get('/prorrateo/pendientes', { params });
export const getProrratePreview = (data) => api.post('/prorrateo/preview', data);
export const ejecutarProrrateo = (data) => api.post('/prorrateo/ejecutar', data);
export const getProrrateHistorial = (params) => api.get('/prorrateo/historial', { params });
export const eliminarProrrateo = (gastoId) => api.delete(`/prorrateo/${gastoId}`);

// Ventas POS
export const getVentasPOS = (params) => api.get('/ventas-pos', { params });
export const refreshVentasPOS = (data) => api.post('/ventas-pos/refresh', data);
export const confirmarVentaPOS = (id) => api.post(`/ventas-pos/${id}/confirmar`);
export const desconfirmarVentaPOS = (id) => api.post(`/ventas-pos/${id}/desconfirmar`);
export const marcarCreditoVentaPOS = (id, fechaVencimiento) => 
  api.post(`/ventas-pos/${id}/credito`, null, { params: { fecha_vencimiento: fechaVencimiento } });
export const descartarVentaPOS = (id) => api.post(`/ventas-pos/${id}/descartar`);

// Ventas POS - Pagos
export const getPagosVentaPOS = (ventaId) => api.get(`/ventas-pos/${ventaId}/pagos`);
export const getPagosOficialesVentaPOS = (ventaId) => api.get(`/ventas-pos/${ventaId}/pagos-oficiales`);
export const addPagoVentaPOS = (ventaId, pago) => api.post(`/ventas-pos/${ventaId}/pagos`, pago);
export const updatePagoVentaPOS = (ventaId, pagoId, pago) => api.put(`/ventas-pos/${ventaId}/pagos/${pagoId}`, pago);
export const deletePagoVentaPOS = (ventaId, pagoId) => api.delete(`/ventas-pos/${ventaId}/pagos/${pagoId}`);

// Ventas POS - Líneas de productos
export const getLineasVentaPOS = (ventaId) => api.get(`/ventas-pos/${ventaId}/lineas`);
export const syncLocalVentasPOS = (params) => api.post('/ventas-pos/sync-local', null, { params });
export const getDistribucionAnalitica = (ventaId) => api.get(`/ventas-pos/${ventaId}/distribucion-analitica`);
export const getPagosCreditoVentaPOS = (ventaId) => api.get(`/ventas-pos/${ventaId}/pagos-credito`);

// Config - Odoo Company Map
export const getOdooCompanyMap = () => api.get('/config/odoo-company-map');
export const setOdooCompanyMap = (data) => api.put('/config/odoo-company-map', data);

// CxC
export const getCxC = (params) => api.get('/cxc', { params });
export const getCxCResumen = () => api.get('/cxc/resumen');
export const createCxC = (data) => api.post('/cxc', data);
export const getCxCAbonos = (cxcId) => api.get(`/cxc/${cxcId}/abonos`);
export const createCxCAbono = (cxcId, data) => api.post(`/cxc/${cxcId}/abonos`, data);

// CxP
export const getCxP = (params) => api.get('/cxp', { params });
export const getCxPResumen = () => api.get('/cxp/resumen');
export const createCxP = (data) => api.post('/cxp', data);
export const getCxPAbonos = (cxpId) => api.get(`/cxp/${cxpId}/abonos`);
export const createCxPAbono = (cxpId, data) => api.post(`/cxp/${cxpId}/abonos`, data);

// Conciliacion (REVISAR Fase 2)
export const getConciliaciones = (cuentaFinancieraId) => 
  api.get('/conciliaciones', { params: { cuenta_financiera_id: cuentaFinancieraId } });
export const createConciliacion = (data) => api.post('/conciliaciones', data);
export const getMovimientosBanco = (params) => api.get('/conciliacion/movimientos-banco', { params });
export const importarExcelBanco = (file, cuentaFinancieraId, banco) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post(`/conciliacion/importar-excel?cuenta_financiera_id=${cuentaFinancieraId}&banco=${banco}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
export const previsualizarExcelBanco = (file, banco) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post(`/conciliacion/previsualizar-excel?banco=${banco}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
export const conciliarMovimientos = (bancoIds, pagoIds) => {
  const params = new URLSearchParams();
  bancoIds.forEach(id => params.append('banco_ids', id));
  pagoIds.forEach(id => params.append('pago_ids', id));
  return api.post(`/conciliacion/conciliar?${params.toString()}`);
};
export const crearGastoBancario = (bancoIds, categoriaId, cuentaFinancieraId, descripcion) => {
  const params = new URLSearchParams();
  bancoIds.forEach(id => params.append('banco_ids', id));
  params.append('categoria_id', categoriaId);
  params.append('cuenta_financiera_id', cuentaFinancieraId);
  if (descripcion) params.append('descripcion', descripcion);
  return api.post(`/conciliacion/crear-gasto-bancario?${params.toString()}`);
};
export const getConciliacionesDetalladas = () => api.get('/conciliacion/historial');
export const desconciliarMovimientos = (bancoId, pagoId) => 
  api.post('/conciliacion/desconciliar', { banco_id: bancoId, pago_id: pagoId });
export const getSugerenciasConciliacion = (cuentaFinancieraId) =>
  api.get('/conciliacion/sugerencias', { params: { cuenta_financiera_id: cuentaFinancieraId } });
export const confirmarSugerencias = (sugerencias) =>
  api.post('/conciliacion/confirmar-sugerencias', { sugerencias });

// Tesoreria
export const getTesoreria = (params) => api.get('/tesoreria', { params });
export const getTesoreriaResumen = (params) => api.get('/tesoreria/resumen', { params });

// Valorizacion Inventario
export const getValorizacionInventario = (params) => api.get('/valorizacion-inventario', { params });

// Export
export const exportCompraAPP = (params) => api.get('/export/compraapp', { params, responseType: 'blob' });

// Retencion/Detraccion (REVISAR Fase 2 — usado en FacturasProveedor)
export const getRetencionDetalle = (origen_tipo, origen_id) => api.get('/retencion-detalle', { params: { origen_tipo, origen_id } });
export const upsertRetencionDetalle = (origen_tipo, origen_id, data) => api.put('/retencion-detalle', data, { params: { origen_tipo, origen_id } });

// Cuentas Financieras Mapeo
export const mapearCuentasDefault = () => api.post('/cuentas-financieras/mapear-cuentas-default');

// Cuentas Contables (usado por CuentasBancarias para mapeo)
export const getCuentasContables = () => api.get('/cuentas-contables');

// Asientos Contables (usado por Gastos y FacturasProveedor CORE)
export const generarAsiento = (data) => api.post('/asientos/generar', data);

// Flujo de Caja Gerencial
export const getFlujoCajaGerencial = (params) => api.get('/flujo-caja-gerencial', { params });

// Marcas
export const getMarcas = () => api.get('/marcas');
export const createMarca = (data) => api.post('/marcas', data);
export const updateMarca = (id, data) => api.put(`/marcas/${id}`, data);
export const deleteMarca = (id) => api.delete(`/marcas/${id}`);

// Reportes Simplificados
export const getReporteVentasPendientes = () => api.get('/reportes/ventas-pendientes');
export const getReporteIngresosPorLinea = (params) => api.get('/reportes/ingresos-por-linea', { params });
export const getReporteIngresosPorMarca = (params) => api.get('/reportes/ingresos-por-marca', { params });
export const getReporteCobranzasPorLinea = (params) => api.get('/reportes/cobranzas-por-linea', { params });
export const getReportePendienteCobrar = () => api.get('/reportes/pendiente-cobrar-por-linea');
export const getReporteGastosPorCategoria = (params) => api.get('/reportes/gastos-por-categoria', { params });
export const getReporteGastosPorCentro = (params) => api.get('/reportes/gastos-por-centro-costo', { params });
export const getReporteUtilidadPorLinea = (params) => api.get('/reportes/utilidad-por-linea', { params });

// Reportes por Linea de Negocio
export const getReporteVentasPorLinea = (params) => api.get('/reportes/ventas-por-linea', { params });
export const getReporteCobranzaPorLinea2 = (params) => api.get('/reportes/cobranza-por-linea', { params });
export const getReporteCruceLineaMarca = (params) => api.get('/reportes/cruce-linea-marca', { params });
export const getReporteGastosDirectosPorLinea = (params) => api.get('/reportes/gastos-directos-por-linea', { params });
export const getReporteDineroPorLinea = (params) => api.get('/reportes/dinero-por-linea', { params });

// Reportes Financieros Gerenciales
export const getReporteBalanceGeneral = (params) => api.get('/reportes/balance-general', { params });
export const getReporteEstadoResultados = (params) => api.get('/reportes/estado-resultados', { params });
export const getReporteFlujoCaja = (params) => api.get('/reportes/flujo-caja', { params });
export const getReporteInventarioValorizado = (params) => api.get('/reportes/inventario-valorizado', { params });
export const getReporteRentabilidadLinea = (params) => api.get('/reportes/rentabilidad-linea', { params });
export const getReporteCxpAging = (params) => api.get('/reportes/cxp-aging', { params });
export const getReporteCxcAging = (params) => api.get('/reportes/cxc-aging', { params });

// Libro Analitico
export const getLibroAnalitico = (params) => api.get('/libro-analitico', { params });
export const exportLibroAnalitico = (params) => api.get('/libro-analitico/export', { params, responseType: 'blob' });

// Unidades Internas de Producción
export const getUnidadesInternas = () => api.get('/unidades-internas');
export const createUnidadInterna = (data) => api.post('/unidades-internas', data);
export const updateUnidadInterna = (id, data) => api.put(`/unidades-internas/${id}`, data);
export const deleteUnidadInterna = (id) => api.delete(`/unidades-internas/${id}`);
export const getPersonasProduccion = () => api.get('/personas-produccion');
export const updatePersonaTipo = (id, data) => api.put(`/personas-produccion/${id}/tipo`, data);
export const getCargosInternos = (params) => api.get('/cargos-internos', { params });
export const generarCargosInternos = () => api.post('/cargos-internos/generar');
export const getGastosUnidadInterna = (params) => api.get('/gastos-unidad-interna', { params });
export const createGastoUnidadInterna = (data) => api.post('/gastos-unidad-interna', data);
export const updateGastoUnidadInterna = (id, data) => api.put(`/gastos-unidad-interna/${id}`, data);
export const deleteGastoUnidadInterna = (id) => api.delete(`/gastos-unidad-interna/${id}`);
export const getTiposGastoUnidad = () => api.get('/tipos-gasto-unidad');
export const getReporteUnidadesInternas = (params) => api.get('/reporte-unidades-internas', { params });

// ─── Planilla v3 ─────────────────────────────────────────────
// Ajustes
export const getAjustesPlanilla = () => api.get('/ajustes-planilla');
export const updateAjustesPlanilla = (data) => api.put('/ajustes-planilla', data);

// AFP
export const getAfps = (params) => api.get('/afp', { params });
export const getAfp = (id) => api.get(`/afp/${id}`);
export const updateAfp = (id, data) => api.put(`/afp/${id}`, data);

// Trabajadores
export const getTrabajadores = (params) => api.get('/trabajadores', { params });
export const getTrabajador = (id) => api.get(`/trabajadores/${id}`);
export const createTrabajador = (data) => api.post('/trabajadores', data);
export const updateTrabajador = (id, data) => api.put(`/trabajadores/${id}`, data);
export const deleteTrabajador = (id) => api.delete(`/trabajadores/${id}`);
export const previewCalculosTrabajador = (data) => api.post('/trabajadores/calculos-preview', data);

// Medios de pago por defecto por trabajador
export const getMediosPagoTrabajador = (id) => api.get(`/trabajadores/${id}/medios-pago`);
export const setMediosPagoTrabajador = (id, medios) => api.put(`/trabajadores/${id}/medios-pago`, medios);

// Adelantos a trabajadores
export const getAdelantos = (params) => api.get('/adelantos-trabajador', { params });
export const createAdelanto = (data) => api.post('/adelantos-trabajador', data);
export const deleteAdelanto = (id) => api.delete(`/adelantos-trabajador/${id}`);
export const getAdelantosPendientesTrabajador = (trabajadorId) =>
  api.get(`/adelantos-trabajador/trabajador/${trabajadorId}/pendientes`);

// Planilla Quincena
export const getPlanillasQuincena = (params) => api.get('/planillas-quincena', { params });
export const getPlanillaQuincena = (id) => api.get(`/planillas-quincena/${id}`);
export const calcularPreviewPlanilla = (data) => api.post('/planillas-quincena/calcular', data);
export const createPlanillaQuincena = (data) => api.post('/planillas-quincena', data);
export const updatePlanillaQuincena = (id, data) => api.put(`/planillas-quincena/${id}`, data);
export const aprobarPlanillaQuincena = (id) => api.post(`/planillas-quincena/${id}/aprobar`);
export const pagarPlanillaQuincena = (id, data) => api.post(`/planillas-quincena/${id}/pagar`, data);
export const anularPagoPlanillaQuincena = (id) => api.post(`/planillas-quincena/${id}/anular-pago`);
export const deletePlanillaQuincena = (id) => api.delete(`/planillas-quincena/${id}`);

// Activos Fijos
export const getActivosFijos = (params) => api.get('/activos-fijos', { params });
export const getActivoFijo = (id) => api.get(`/activos-fijos/${id}`);
export const createActivoFijo = (data) => api.post('/activos-fijos', data);
export const updateActivoFijo = (id, data) => api.put(`/activos-fijos/${id}`, data);
export const deleteActivoFijo = (id) => api.delete(`/activos-fijos/${id}`);
export const getResumenActivos = () => api.get('/activos-fijos/resumen');
export const getDepreciacionActivo = (id) => api.get(`/activos-fijos/${id}/depreciacion`);
export const calcularDepreciacion = () => api.post('/activos-fijos/calcular-depreciacion');

// Movimientos desde Producción
export const getMovimientosProduccion = (params) => api.get('/movimientos-produccion', { params });
export const getMovimientosProduccionFinanzas = (params) => api.get('/movimientos-produccion-finanzas', { params });

// Producción backend directo — vincular facturas con movimientos
const PROD_API_URL = process.env.REACT_APP_PRODUCCION_URL || 'http://localhost:8000';

export const getMovimientosProduccionSinFactura = (params) =>
  axios.get(`${PROD_API_URL}/api/movimientos-produccion-sin-factura`, { params });

export const vincularFacturaMovimiento = (movimientoId, data) =>
  axios.patch(`${PROD_API_URL}/api/movimientos-produccion/${movimientoId}/factura`, data);

// Procesar / Anular Nota Interna (materializa o revierte el ingreso en cuenta ficticia)
export const procesarNotaInterna = (facturaId) =>
  api.post(`/facturas-proveedor/${facturaId}/procesar-nota-interna`);

export const anularProcesamientoNotaInterna = (facturaId) =>
  api.post(`/facturas-proveedor/${facturaId}/anular-procesamiento-nota-interna`);

// P&L detallado por unidad interna
export const getReportePnLUnidad = (unidadId, params) =>
  api.get(`/reporte-pnl-unidad/${unidadId}`, { params });

export default api;
