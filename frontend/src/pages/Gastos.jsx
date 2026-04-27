import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Plus, FileText, Trash2, Eye, X, DollarSign, Download, Printer, Pencil, Search, SlidersHorizontal } from 'lucide-react';
import { toast } from 'sonner';
import {
  getGastos,
  getGasto,
  createGasto,
  updateGasto,
  deleteGasto,
  deleteGastoPago,
  getNextOtroCorrelativo,
  getProveedores,
  getMonedas,
  getCategorias,
  getLineasNegocio,
  getCentrosCosto,
  getCuentasFinancieras,
  generarAsiento,

  createTercero,
  getCategoriasGasto,
  getUnidadesInternas
} from '../services/api';
import { useEmpresa } from '../context/EmpresaContext';
import SearchableSelect from '../components/SearchableSelect';
import CategoriaSelect from '../components/CategoriaSelect';

const formatCurrency = (value, symbol = 'S/') => {
  const s = symbol || 'S/';
  const num = parseFloat(value) || 0;
  return `${s} ${num.toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const formatDate = (dateStr) => {
  if (!dateStr) return '-';
  const date = new Date(dateStr + 'T00:00:00');
  return date.toLocaleDateString('es-PE', { day: '2-digit', month: '2-digit', year: 'numeric' });
};

const MEDIOS_PAGO = [
  { value: 'efectivo', label: 'Efectivo' },
  { value: 'transferencia', label: 'Transferencia' },
  { value: 'cheque', label: 'Cheque' },
  { value: 'tarjeta', label: 'Tarjeta' }
];

export default function Gastos() {
  const { empresaActual } = useEmpresa();

  const [gastos, setGastos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [showViewModal, setShowViewModal] = useState(false);
  const [selectedGasto, setSelectedGasto] = useState(null);
  const [editingGastoId, setEditingGastoId] = useState(null);
  
  // Master data
  const [proveedores, setProveedores] = useState([]);
  const [monedas, setMonedas] = useState([]);
  const [categorias, setCategorias] = useState([]);
  const [lineas, setLineas] = useState([]);
  const [centros, setCentros] = useState([]);
  const [cuentas, setCuentas] = useState([]);

  const [unidadesInternas, setUnidadesInternas] = useState([]);
  
  // Filters
  const [filtroFechaDesde, setFiltroFechaDesde] = useState('');
  const [filtroFechaHasta, setFiltroFechaHasta] = useState('');
  const [filtroCif, setFiltroCif] = useState(null); // null=all, true=CIF only, false=non-CIF
  const [filtroBusquedaInput, setFiltroBusquedaInput] = useState('');
  const [filtroBusqueda, setFiltroBusqueda] = useState('');
  const [filtroProveedor, setFiltroProveedor] = useState('');

  const [filtroLinea, setFiltroLinea] = useState('');
  const [filtroCentro, setFiltroCentro] = useState('');
  const [filtroUnidad, setFiltroUnidad] = useState('');
  const [showMoreFilters, setShowMoreFilters] = useState(false);
  const [categoriasGasto, setCategoriasGasto] = useState([]);
  const searchTimer = useRef(null);
  
  // Form state
  const [formData, setFormData] = useState({
    fecha: new Date().toISOString().split('T')[0],
    fecha_contable: new Date().toISOString().split('T')[0],
    proveedor_id: '',
    beneficiario_nombre: '',
    moneda_id: '',
    tipo_cambio: '',
    tipo_documento: 'boleta',
    numero_documento: '',
    tipo_comprobante_sunat: '03',
    base_gravada: 0,
    igv_sunat: 0,
    base_no_gravada: 0,
    isc: 0,
    notas: '',
    impuestos_incluidos: true,
    categoria_gasto_id: null,
    unidad_interna_id: ''
  });
  const [fechaContableManual, setFechaContableManual] = useState(false);
  const [showSunat, setShowSunat] = useState(false);

  // Quick-create proveedor
  const [showQuickProv, setShowQuickProv] = useState(false);
  const [quickProvForm, setQuickProvForm] = useState({ nombre: '', tipo_documento: 'RUC', numero_documento: '' });
  const [savingProv, setSavingProv] = useState(false);

  const handleQuickCreateProv = async (e) => {
    e.preventDefault();
    if (!quickProvForm.nombre.trim()) { toast.error('Nombre obligatorio'); return; }
    setSavingProv(true);
    try {
      const res = await createTercero({ ...quickProvForm, es_proveedor: true, es_cliente: false, es_personal: false, activo: true });
      const newProv = res.data;
      setProveedores(prev => [...prev, newProv]);
      setFormData(prev => ({ ...prev, proveedor_id: newProv.id, beneficiario_nombre: '' }));
      setShowQuickProv(false);
      setQuickProvForm({ nombre: '', tipo_documento: 'RUC', numero_documento: '' });
      toast.success(`Proveedor "${newProv.nombre}" creado`);
    } catch { toast.error('Error creando proveedor'); }
    finally { setSavingProv(false); }
  };
  
  // Line items
  const [lineasGasto, setLineasGasto] = useState([{
    categoria_id: '',
    descripcion: '',
    linea_negocio_id: '',
    centro_costo_id: '',
    unidad_interna_id: '',
    importe: 0,
    igv_aplica: true
  }]);
  
  // Payments
  const [pagos, setPagos] = useState([{
    cuenta_financiera_id: '',
    medio_pago: 'efectivo',
    monto: 0,
    referencia: ''
  }]);
  const [pagosExistentes, setPagosExistentes] = useState([]);
  const [totalPagado, setTotalPagado] = useState(0);
  const [saldoPendiente, setSaldoPendiente] = useState(0);

  useEffect(() => {
    loadData();
  }, [filtroFechaDesde, filtroFechaHasta, filtroCif, filtroBusqueda, filtroProveedor, filtroLinea, filtroCentro, filtroUnidad, empresaActual]);

  const loadData = async () => {
    try {
      setLoading(true);
      const params = {};
      if (filtroFechaDesde) params.fecha_desde = filtroFechaDesde;
      if (filtroFechaHasta) params.fecha_hasta = filtroFechaHasta;
      if (filtroCif !== null) params.es_cif = filtroCif;
      if (filtroBusqueda.trim()) params.busqueda = filtroBusqueda.trim();
      if (filtroProveedor) params.proveedor_id = filtroProveedor;

      if (filtroLinea) params.linea_negocio_id = filtroLinea;
      if (filtroCentro) params.centro_costo_id = filtroCentro;
      if (filtroUnidad) params.unidad_interna_id = filtroUnidad;
      const [gastosRes, provRes, monRes, catRes, linRes, cenRes, cueRes, catGastoRes, uiRes] = await Promise.all([
        getGastos(params),
        getProveedores(),
        getMonedas(),
        getCategorias('egreso'),
        getLineasNegocio(),
        getCentrosCosto(),
        getCuentasFinancieras(),
        getCategoriasGasto(),
        getUnidadesInternas().catch(() => ({ data: [] }))
      ]);

      setGastos(gastosRes.data);
      setProveedores(provRes.data);
      setMonedas(monRes.data);
      setCategorias(catRes.data);
      setLineas(linRes.data);
      setCentros(cenRes.data);
      setCuentas(cueRes.data);
      setCategoriasGasto(catGastoRes.data);
      setUnidadesInternas(uiRes.data);
      
      // Set default moneda
      if (monRes.data.length > 0 && !formData.moneda_id) {
        setFormData(prev => ({ ...prev, moneda_id: monRes.data[0].id }));
      }
    } catch (error) {
      toast.error('Error al cargar datos');
    } finally {
      setLoading(false);
    }
  };

  const calcularTotales = () => {
    let subtotal = 0;
    let igv = 0;
    let base_gravada = 0;
    let igv_sunat = 0;
    let base_no_gravada = 0;

    lineasGasto.forEach(l => {
      const importe = parseFloat(l.importe) || 0;
      if (l.igv_aplica) {
        if (formData.impuestos_incluidos) {
          const base = importe / 1.18;
          const lineaIgv = importe - base;
          subtotal += base;
          igv += lineaIgv;
          base_gravada += base;
          igv_sunat += lineaIgv;
        } else {
          subtotal += importe;
          igv += importe * 0.18;
          base_gravada += importe;
          igv_sunat += importe * 0.18;
        }
      } else {
        if (formData.impuestos_incluidos) {
          subtotal += importe;
          base_no_gravada += importe;
        } else {
          subtotal += importe;
          base_no_gravada += importe;
        }
      }
    });

    return {
      subtotal,
      igv,
      total: subtotal + igv,
      base_gravada: parseFloat(base_gravada.toFixed(2)),
      igv_sunat: parseFloat(igv_sunat.toFixed(2)),
      base_no_gravada: parseFloat(base_no_gravada.toFixed(2))
    };
  };

  const calcularTotalPagos = () => {
    return pagos.reduce((sum, p) => sum + (parseFloat(p.monto) || 0), 0);
  };

  const resetForm = () => {
    const hoy = new Date().toISOString().split('T')[0];
    setFormData({
      fecha: hoy,
      fecha_contable: hoy,
      proveedor_id: '',
      beneficiario_nombre: '',
      moneda_id: monedas[0]?.id || '',
      tipo_cambio: '1',
      tipo_documento: 'boleta',
      numero_documento: '',
      tipo_comprobante_sunat: '03',
      base_gravada: 0,
      igv_sunat: 0,
      base_no_gravada: 0,
      isc: 0,
      notas: '',
      impuestos_incluidos: true,
      categoria_gasto_id: null,
      unidad_interna_id: ''
    });
    setFechaContableManual(false);
    setShowSunat(false);
    setLineasGasto([{
      categoria_id: '',
      descripcion: '',
      linea_negocio_id: '',
      centro_costo_id: '',
      unidad_interna_id: '',
      importe: 0,
      igv_aplica: true
    }]);
    setPagos([{
      cuenta_financiera_id: '',
      medio_pago: 'efectivo',
      monto: 0,
      referencia: ''
    }]);
    setPagosExistentes([]);
    setTotalPagado(0);
    setSaldoPendiente(0);
  };

  const handleAddLinea = () => {
    setLineasGasto([...lineasGasto, {
      categoria_id: '',
      descripcion: '',
      linea_negocio_id: '',
      centro_costo_id: '',
      unidad_interna_id: '',
      importe: 0,
      igv_aplica: true
    }]);
  };

  const handleRemoveLinea = (index) => {
    if (lineasGasto.length > 1) {
      setLineasGasto(lineasGasto.filter((_, i) => i !== index));
    }
  };

  const handleLineaChange = (index, field, value) => {
    setLineasGasto(prev => prev.map((l, i) => 
      i === index ? { ...l, [field]: value } : l
    ));
  };

  const handleAddPago = () => {
    setPagos([...pagos, {
      cuenta_financiera_id: '',
      medio_pago: 'efectivo',
      monto: 0,
      referencia: ''
    }]);
  };

  const handleRemovePago = (index) => {
    if (pagos.length > 1) {
      setPagos(pagos.filter((_, i) => i !== index));
    }
  };

  const handlePagoChange = (index, field, value) => {
    setPagos(prev => prev.map((p, i) => 
      i === index ? { ...p, [field]: value } : p
    ));
  };

  const handleDistribuirPago = () => {
    // Distribute total equally among payments
    const totales = calcularTotales();
    const montoPorPago = totales.total / pagos.length;
    setPagos(prev => prev.map(p => ({ ...p, monto: parseFloat(montoPorPago.toFixed(2)) })));
  };

  const handleDeleteExistingPago = async (pagoId) => {
    if (!window.confirm('¿Eliminar este pago? Se revertirá el movimiento en la cuenta.')) return;
    try {
      await deleteGastoPago(editingGastoId, pagoId);
      toast.success('Pago eliminado y revertido');
      // Refresh the gasto data
      const res = await getGasto(editingGastoId);
      const g = res.data;
      setPagosExistentes(g.pagos_vinculados || []);
      setTotalPagado(g.total_pagado || 0);
      setSaldoPendiente(g.saldo_pendiente || 0);
      loadData();
    } catch (error) {
      toast.error(typeof error.response?.data?.detail === 'string' ? error.response?.data?.detail : 'Error eliminando pago');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    
    const totales = calcularTotales();
    const totalPagos = calcularTotalPagos();
    
    // Validations
    if (lineasGasto.every(l => !l.importe || l.importe <= 0)) {
      toast.error('Agregue al menos una línea con importe');
      return;
    }
    
    const hasPagos = pagos.some(p => p.cuenta_financiera_id && p.monto > 0);
    if (!editingGastoId && hasPagos) {
      if (!pagos.every(p => p.cuenta_financiera_id && p.monto > 0)) {
        toast.error('Todos los pagos deben tener cuenta y monto');
        return;
      }
      if (Math.abs(totalPagos - totales.total) > 0.01) {
        toast.error(`Los pagos (${formatCurrency(totalPagos)}) deben sumar el total del gasto (${formatCurrency(totales.total)})`);
        return;
      }
    }
    
    setSubmitting(true);
    try {
      // Auto-determine tipo_asignacion and header-level fields from lines
      const lineasValidas = lineasGasto.filter(l => l.importe > 0);
      const hayLineaNegocio = lineasValidas.some(l => l.linea_negocio_id);
      const catGastoSel = categoriasGasto.find(c => c.id === formData.categoria_gasto_id);
      // Si la categoría de gasto es CIF -> 'comun' (se prorratea); si tiene línea de negocio en la línea -> 'directo'; sino -> 'no_asignado'
      const tipoAsignacion = catGastoSel?.es_cif ? 'comun'
        : hayLineaNegocio ? 'directo' : 'no_asignado';
      const primeraLineaConLinea = lineasValidas.find(l => l.linea_negocio_id);
      const primeraLineaConCentro = lineasValidas.find(l => l.centro_costo_id);
      const primeraLineaConUnidad = lineasValidas.find(l => l.unidad_interna_id);

      const payload = {
        ...formData,
        proveedor_id: formData.proveedor_id || null,
        tipo_cambio: formData.tipo_cambio ? parseFloat(formData.tipo_cambio) : null,
        categoria_gasto_id: formData.categoria_gasto_id || null,
        tipo_asignacion: tipoAsignacion,
        centro_costo_id: primeraLineaConCentro ? parseInt(primeraLineaConCentro.centro_costo_id) : null,
        unidad_interna_id: primeraLineaConUnidad ? parseInt(primeraLineaConUnidad.unidad_interna_id) : null,
        linea_negocio_id: primeraLineaConLinea ? parseInt(primeraLineaConLinea.linea_negocio_id) : null,
        base_gravada: totales.base_gravada,
        igv_sunat: totales.igv_sunat,
        base_no_gravada: totales.base_no_gravada,
        isc: parseFloat(formData.isc) || 0,
        lineas: lineasGasto.filter(l => l.importe > 0).map(l => ({
          categoria_id: l.categoria_id || null,
          descripcion: l.descripcion || null,
          linea_negocio_id: l.linea_negocio_id || null,
          centro_costo_id: l.centro_costo_id || null,
          unidad_interna_id: l.unidad_interna_id ? parseInt(l.unidad_interna_id) : null,
          importe: parseFloat(l.importe),
          igv_aplica: l.igv_aplica
        })),
        pagos: editingGastoId ? [] : pagos.map(p => ({
          cuenta_financiera_id: parseInt(p.cuenta_financiera_id),
          medio_pago: p.medio_pago,
          monto: parseFloat(p.monto),
          referencia: p.referencia || null
        }))
      };
      
      if (editingGastoId) {
        await updateGasto(editingGastoId, payload);
        toast.success('Gasto actualizado exitosamente');
      } else {
        await createGasto(payload);
        toast.success('Gasto registrado exitosamente');
      }
      setShowModal(false);
      setEditingGastoId(null);
      resetForm();
      loadData();
    } catch (error) {
      toast.error(typeof error.response?.data?.detail === 'string' ? error.response?.data?.detail : 'Error al guardar gasto');
    } finally {
      setSubmitting(false);
    }
  };

  const handleView = (gasto) => {
    setSelectedGasto(gasto);
    setShowViewModal(true);
  };

  const handleEdit = async (gasto) => {
    try {
      const res = await getGasto(gasto.id);
      const g = res.data;

      setEditingGastoId(g.id);
      setFormData({
        fecha: g.fecha?.split('T')[0] || '',
        fecha_contable: g.fecha_contable?.split('T')[0] || g.fecha?.split('T')[0] || '',
        proveedor_id: g.proveedor_id || '',
        beneficiario_nombre: g.beneficiario_nombre || '',
        moneda_id: g.moneda_id || '',
        tipo_cambio: g.tipo_cambio || '',
        tipo_documento: g.tipo_documento || 'boleta',
        numero_documento: g.numero_documento || '',
        tipo_comprobante_sunat: g.tipo_comprobante_sunat || '03',
        base_gravada: g.base_gravada || 0,
        igv_sunat: g.igv_sunat || 0,
        base_no_gravada: g.base_no_gravada || 0,
        isc: g.isc || 0,
        notas: g.notas || '',
        impuestos_incluidos: true,
        categoria_gasto_id: g.categoria_gasto_id || null,
        unidad_interna_id: g.unidad_interna_id || '',
      });
      setLineasGasto(g.lineas?.length > 0
        ? g.lineas.map(l => ({
            categoria_id: l.categoria_id || '',
            descripcion: l.descripcion || '',
            importe: l.importe || 0,
            igv_aplica: l.igv_aplica !== false,
            linea_negocio_id: l.linea_negocio_id || '',
            centro_costo_id: l.centro_costo_id || '',
            unidad_interna_id: l.unidad_interna_id || '',
          }))
        : [{ categoria_id: '', descripcion: '', importe: 0, igv_aplica: true, linea_negocio_id: '', centro_costo_id: '', unidad_interna_id: '' }]
      );
      setPagosExistentes(g.pagos_vinculados || []);
      setTotalPagado(g.total_pagado || 0);
      setSaldoPendiente(g.saldo_pendiente || 0);
      setPagos([{ cuenta_financiera_id: '', medio_pago: 'efectivo', monto: 0, referencia: '' }]);
      setShowModal(true);
    } catch (error) {
      toast.error('Error cargando gasto');
    }
  };

  const handleDelete = async (gasto) => {
    if (!window.confirm(`¿Está seguro de eliminar el gasto ${gasto.numero}?`)) return;
    
    try {
      await deleteGasto(gasto.id);
      toast.success('Gasto eliminado exitosamente');
      loadData();
    } catch (error) {
      toast.error(typeof error.response?.data?.detail === 'string' ? error.response?.data?.detail : 'Error al eliminar gasto');
    }
  };

  const handleDownloadPDF = (gasto) => {
    const proveedor = proveedores.find(p => p.id === gasto.proveedor_id);
    const moneda = monedas.find(m => m.id === gasto.moneda_id);
    
    const pdfContent = `
      <html>
      <head>
        <title>Gasto-${gasto.numero}</title>
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
          * { box-sizing: border-box; margin: 0; padding: 0; }
          body { font-family: 'Inter', sans-serif; padding: 40px; color: #1e293b; }
          .header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 2px solid #1B4D3E; }
          .doc-title { font-size: 1.5rem; font-weight: 700; color: #1B4D3E; }
          .doc-number { font-family: 'JetBrains Mono', monospace; font-size: 1.125rem; font-weight: 600; margin-top: 4px; }
          .doc-date { font-size: 0.875rem; color: #64748b; margin-top: 4px; }
          .section { margin-bottom: 24px; }
          .section-title { font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; margin-bottom: 8px; }
          .info-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
          .info-item label { font-size: 0.75rem; color: #64748b; display: block; }
          .info-item p { font-size: 0.9375rem; font-weight: 500; }
          table { width: 100%; border-collapse: collapse; margin-top: 16px; }
          th { background: #f1f5f9; padding: 10px 12px; text-align: left; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em; color: #64748b; border-bottom: 2px solid #e2e8f0; }
          td { padding: 10px 12px; border-bottom: 1px solid #e2e8f0; font-size: 0.875rem; }
          .text-right { text-align: right; }
          .currency { font-family: 'JetBrains Mono', monospace; font-weight: 500; }
          .totals { margin-top: 24px; display: flex; justify-content: flex-end; }
          .totals-box { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px 24px; min-width: 280px; }
          .totals-row { display: flex; justify-content: space-between; padding: 6px 0; font-size: 0.9375rem; }
          .totals-row.total { border-top: 2px solid #1B4D3E; margin-top: 8px; padding-top: 12px; font-weight: 700; font-size: 1.125rem; }
          .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; text-align: center; color: #64748b; font-size: 0.75rem; }
        </style>
      </head>
      <body>
        <div class="header">
          <div>
            <div class="doc-title">COMPROBANTE DE GASTO</div>
            <div class="doc-number">${gasto.numero}</div>
          </div>
          <div style="text-align: right;">
            <div class="doc-date">Fecha: ${formatDate(gasto.fecha)}</div>
            ${gasto.tipo_documento && gasto.numero_documento ? `<div class="doc-date">Doc: ${gasto.tipo_documento.toUpperCase()} ${gasto.numero_documento}</div>` : ''}
          </div>
        </div>
        
        <div class="section">
          <div class="section-title">Datos del Beneficiario</div>
          <div class="info-grid">
            <div class="info-item">
              <label>Proveedor / Beneficiario</label>
              <p>${gasto.proveedor_nombre || gasto.beneficiario_nombre || '-'}</p>
            </div>
            <div class="info-item">
              <label>Moneda</label>
              <p>${gasto.moneda_codigo || 'PEN'}</p>
            </div>
          </div>
        </div>
        
        <div class="section">
          <div class="section-title">Detalle del Gasto</div>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Categoría</th>
                <th>Descripción</th>
                <th class="text-right">Importe</th>
              </tr>
            </thead>
            <tbody>
              ${(gasto.lineas || []).map((linea, i) => `
              <tr>
                <td>${i + 1}</td>
                <td>${linea.categoria_padre_nombre ? `${linea.categoria_padre_nombre} > ${linea.categoria_nombre}` : (linea.categoria_nombre || '-')}</td>
                <td>${linea.descripcion || '-'}</td>
                <td class="text-right currency">${formatCurrency(linea.importe, moneda?.simbolo || 'S/')}</td>
              </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
        
        <div class="totals">
          <div class="totals-box">
            <div class="totals-row">
              <span>Subtotal:</span>
              <span class="currency">${formatCurrency(gasto.subtotal, moneda?.simbolo || 'S/')}</span>
            </div>
            <div class="totals-row">
              <span>IGV (18%):</span>
              <span class="currency">${formatCurrency(gasto.igv, moneda?.simbolo || 'S/')}</span>
            </div>
            <div class="totals-row total">
              <span>TOTAL:</span>
              <span class="currency">${formatCurrency(gasto.total, moneda?.simbolo || 'S/')}</span>
            </div>
          </div>
        </div>
        
        ${gasto.notas ? `
        <div class="section" style="margin-top: 24px;">
          <div class="section-title">Observaciones</div>
          <p style="font-size: 0.875rem; color: #64748b;">${gasto.notas}</p>
        </div>` : ''}
        
        <div class="footer">
          <p>Documento generado el ${new Date().toLocaleDateString('es-PE')} | Finanzas 4.0</p>
        </div>
      </body>
      </html>
    `;
    
    const printWindow = window.open('', '_blank');
    printWindow.document.write(pdfContent);
    printWindow.document.close();
    printWindow.focus();
    printWindow.onload = () => printWindow.print();
  };

  const totales = calcularTotales();
  const totalPagos = calcularTotalPagos();
  const monedaActual = monedas.find(m => m.id === parseInt(formData.moneda_id));
  const totalGastos = gastos.reduce((sum, g) => sum + parseFloat(g.total || 0), 0);

  return (
    <div data-testid="gastos-page" className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Gastos</h1>
          <p className="page-subtitle">Total: {formatCurrency(totalGastos)}</p>
        </div>
        <button 
          className="btn btn-primary"
          onClick={() => { resetForm(); setEditingGastoId(null); setShowModal(true); }}
          data-testid="nuevo-gasto-btn"
        >
          <Plus size={18} />
          Nuevo Gasto
        </button>
      </div>

      <div className="page-content">
        {/* Filters */}
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 16px', marginBottom: 16 }}>
          {/* Row 1: Search + Dates + CIF toggle */}
          <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
            {/* Search */}
            <div style={{ flex: '1 1 220px', minWidth: 180 }}>
              <label style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 4, display: 'block' }}>Buscar</label>
              <div style={{ position: 'relative' }}>
                <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--muted)' }} />
                <input
                  type="text"
                  className="form-input"
                  placeholder="Proveedor, número, notas..."
                  value={filtroBusquedaInput}
                  onChange={(e) => {
                    const val = e.target.value;
                    setFiltroBusquedaInput(val);
                    clearTimeout(searchTimer.current);
                    searchTimer.current = setTimeout(() => setFiltroBusqueda(val), 400);
                  }}
                  style={{ paddingLeft: 32, fontSize: '0.8125rem' }}
                />
              </div>
            </div>
            {/* Fecha Desde */}
            <div style={{ minWidth: 140 }}>
              <label style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 4, display: 'block' }}>Desde</label>
              <input type="date" className="form-input" value={filtroFechaDesde} onChange={(e) => setFiltroFechaDesde(e.target.value)} style={{ fontSize: '0.8125rem' }} />
            </div>
            {/* Fecha Hasta */}
            <div style={{ minWidth: 140 }}>
              <label style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 4, display: 'block' }}>Hasta</label>
              <input type="date" className="form-input" value={filtroFechaHasta} onChange={(e) => setFiltroFechaHasta(e.target.value)} style={{ fontSize: '0.8125rem' }} />
            </div>
            {/* CIF toggle */}
            <div>
              <label style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 4, display: 'block' }}>Tipo</label>
              <div style={{ display: 'flex', gap: 2, background: 'var(--background)', borderRadius: 6, padding: 2 }}>
                {[
                  { val: null, label: 'Todos' },
                  { val: true, label: 'CIF' },
                  { val: false, label: 'No CIF' },
                ].map(f => (
                  <button
                    key={String(f.val)}
                    type="button"
                    onClick={() => setFiltroCif(f.val)}
                    style={{
                      padding: '5px 12px', borderRadius: 5, fontSize: '0.75rem', fontWeight: 600, border: 'none', cursor: 'pointer',
                      background: filtroCif === f.val ? 'var(--primary)' : 'transparent',
                      color: filtroCif === f.val ? '#fff' : 'var(--muted)',
                      transition: 'all 0.15s'
                    }}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </div>
            {/* More filters toggle */}
            <button
              type="button"
              onClick={() => setShowMoreFilters(!showMoreFilters)}
              style={{
                display: 'flex', alignItems: 'center', gap: 6, padding: '7px 12px', borderRadius: 6, fontSize: '0.78rem', fontWeight: 600, border: '1px solid var(--border)', cursor: 'pointer',
                background: showMoreFilters ? 'var(--primary)' : 'var(--background)',
                color: showMoreFilters ? '#fff' : 'var(--muted)',
                transition: 'all 0.15s'
              }}
            >
              <SlidersHorizontal size={14} />
              Filtros
            </button>
            {/* Clear all */}
            {(filtroFechaDesde || filtroFechaHasta || filtroCif !== null || filtroBusqueda || filtroProveedor || filtroLinea || filtroCentro || filtroUnidad) && (
              <button
                type="button"
                onClick={() => {
                  setFiltroFechaDesde(''); setFiltroFechaHasta(''); setFiltroCif(null);
                  setFiltroBusquedaInput(''); setFiltroBusqueda(''); setFiltroProveedor('');
                  setFiltroLinea(''); setFiltroCentro(''); setFiltroUnidad('');
                }}
                style={{ padding: '7px 12px', borderRadius: 6, fontSize: '0.75rem', fontWeight: 500, border: 'none', cursor: 'pointer', background: 'var(--danger-bg)', color: 'var(--danger-text)' }}
              >
                <X size={13} style={{ marginRight: 4, verticalAlign: 'middle' }} />
                Limpiar
              </button>
            )}
          </div>

          {/* Row 2: Advanced filters (collapsible) */}
          {showMoreFilters && (
            <div style={{ display: 'flex', gap: 12, marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)', flexWrap: 'wrap' }}>
              <div style={{ flex: '1 1 160px', minWidth: 140 }}>
                <label style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 4, display: 'block' }}>Proveedor</label>
                <select className="form-input" value={filtroProveedor} onChange={(e) => setFiltroProveedor(e.target.value)} style={{ fontSize: '0.8125rem' }}>
                  <option value="">Todos</option>
                  {proveedores.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                </select>
              </div>
              <div style={{ flex: '1 1 140px', minWidth: 120 }}>
                <label style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 4, display: 'block' }}>Línea Negocio</label>
                <select className="form-input" value={filtroLinea} onChange={(e) => setFiltroLinea(e.target.value)} style={{ fontSize: '0.8125rem' }}>
                  <option value="">Todas</option>
                  {lineas.map(l => <option key={l.id} value={l.id}>{l.nombre}</option>)}
                </select>
              </div>
              <div style={{ flex: '1 1 140px', minWidth: 120 }}>
                <label style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 4, display: 'block' }}>Centro Costo</label>
                <select className="form-input" value={filtroCentro} onChange={(e) => setFiltroCentro(e.target.value)} style={{ fontSize: '0.8125rem' }}>
                  <option value="">Todos</option>
                  {centros.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
                </select>
              </div>
              {unidadesInternas.length > 0 && (
                <div style={{ flex: '1 1 140px', minWidth: 120 }}>
                  <label style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 4, display: 'block' }}>Unidad Interna</label>
                  <select className="form-input" value={filtroUnidad} onChange={(e) => setFiltroUnidad(e.target.value)} style={{ fontSize: '0.8125rem' }}>
                    <option value="">Todas</option>
                    {unidadesInternas.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}
                  </select>
                </div>
              )}
            </div>
          )}

          {/* Active filters count */}
          {(() => {
            const activeCount = [filtroProveedor, filtroLinea, filtroCentro, filtroUnidad].filter(Boolean).length;
            if (activeCount === 0) return null;
            return (
              <div style={{ marginTop: 8, fontSize: '0.75rem', color: 'var(--primary)', fontWeight: 500 }}>
                {activeCount} filtro{activeCount > 1 ? 's' : ''} avanzado{activeCount > 1 ? 's' : ''} activo{activeCount > 1 ? 's' : ''}
              </div>
            );
          })()}
        </div>

        {/* Table */}
        <div className="card">
          <div className="data-table-wrapper">
            {loading ? (
              <div className="loading">
                <div className="loading-spinner"></div>
              </div>
            ) : gastos.length === 0 ? (
              <div className="empty-state">
                <FileText className="empty-state-icon" />
                <div className="empty-state-title">No hay gastos registrados</div>
                <div className="empty-state-description">Registra tu primer gasto</div>
                <button className="btn btn-primary" onClick={() => setShowModal(true)}>
                  <Plus size={18} />
                  Registrar gasto
                </button>
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>Número</th>
                    <th>Proveedor / Beneficiario</th>
                    <th>Tipo</th>
                    <th>Centro Costo</th>
                    <th className="text-right">Total</th>
                    <th className="text-center">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {gastos.map((gasto) => (
                    <tr key={gasto.id}>
                      <td>{formatDate(gasto.fecha)}</td>
                      <td style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.8125rem' }}>
                        {gasto.numero}
                      </td>
                      <td>
                        {gasto.proveedor_nombre || gasto.beneficiario_nombre || '-'}
                      </td>
                      <td>
                        <span style={{
                          display: 'inline-block',
                          padding: '2px 8px',
                          borderRadius: '12px',
                          fontSize: '0.75rem',
                          fontWeight: 500,
                          background: gasto.tipo_asignacion === 'directo' ? '#dbeafe'
                            : gasto.tipo_asignacion === 'comun' ? '#fef9c3' : 'var(--card-bg-alt)',
                          color: gasto.tipo_asignacion === 'directo' ? '#1e40af'
                            : gasto.tipo_asignacion === 'comun' ? '#854d0e' : 'var(--muted)'
                        }}>
                          {gasto.tipo_asignacion || 'no_asignado'}
                        </span>
                        {categoriasGasto.find(c => c.id === gasto.categoria_gasto_id && c.es_cif) && (
                          <span style={{
                            display: 'inline-block',
                            marginLeft: 4,
                            padding: '2px 6px',
                            borderRadius: '12px',
                            fontSize: '0.7rem',
                            fontWeight: 600,
                            background: 'var(--success-bg)',
                            color: 'var(--success-text)',
                            border: '1px solid var(--success-border)'
                          }}>
                            CIF
                          </span>
                        )}
                      </td>
                      <td style={{ fontSize: '0.8rem' }}>{gasto.centro_costo_nombre || '-'}</td>
                      <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 500 }}>
                        {formatCurrency(gasto.total, gasto.moneda_codigo === 'USD' ? '$' : 'S/')}
                      </td>
                      <td>
                        <div className="actions-row">
                          <button
                            className="action-btn"
                            onClick={() => handleView(gasto)}
                            title="Ver detalles"
                          >
                            <Eye size={15} />
                          </button>
                          <button
                            className="action-btn"
                            onClick={() => handleEdit(gasto)}
                            title={gasto.pago_id ? "Ver/Gestionar pagos" : "Editar"}
                          >
                            <Pencil size={15} />
                          </button>
                          <button
                            className="action-btn action-danger"
                            onClick={() => handleDelete(gasto)}
                            title="Eliminar"
                          >
                            <Trash2 size={15} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {/* Modal Crear Gasto */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal modal-xl" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">{editingGastoId ? 'Editar Gasto' : 'Nuevo Gasto'}</h2>
              <button className="modal-close" onClick={() => { setShowModal(false); setEditingGastoId(null); }}>
                <X size={20} />
              </button>
            </div>
            
            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                {/* === CABECERA: Datos del documento === */}
                <div className="form-grid form-grid-4">
                  <div className="form-group">
                    <label className="form-label">Fecha *</label>
                    <input type="date" className="form-input" value={formData.fecha}
                      onChange={async (e) => {
                        const nf = e.target.value;
                        setFormData(prev => ({ ...prev, fecha: nf, ...(!fechaContableManual ? { fecha_contable: nf } : {}) }));
                        // Si está en "Otro", recalcular correlativo del nuevo día
                        if (formData.tipo_documento === 'otro' && nf) {
                          try {
                            const r = await getNextOtroCorrelativo(nf);
                            setFormData(prev => ({ ...prev, fecha: nf, numero_documento: r.data.numero_documento }));
                          } catch { /* silencioso */ }
                        }
                      }} required />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Tipo Doc.</label>
                    <select className="form-input form-select" value={formData.tipo_documento}
                      onChange={async (e) => {
                        const nuevo = e.target.value;
                        setFormData(prev => ({ ...prev, tipo_documento: nuevo }));
                        if (nuevo === 'otro' && formData.fecha) {
                          try {
                            const r = await getNextOtroCorrelativo(formData.fecha);
                            setFormData(prev => ({ ...prev, tipo_documento: 'otro', numero_documento: r.data.numero_documento }));
                          } catch { /* silencioso */ }
                        }
                      }}>
                      <option value="boleta">Boleta</option>
                      <option value="factura">Factura</option>
                      <option value="recibo">Recibo</option>
                      <option value="ticket">Ticket</option>
                      <option value="otro">Otro</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">N Doc.</label>
                    <input type="text" className="form-input" value={formData.numero_documento}
                      onChange={(e) => setFormData({ ...formData, numero_documento: e.target.value })}
                      placeholder={formData.tipo_documento === 'otro' ? 'MM-YYYY-0001' : '001-00001'} />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Moneda</label>
                    <select className="form-input form-select" value={formData.moneda_id}
                      onChange={(e) => {
                        const sel = monedas.find(m => m.id === parseInt(e.target.value));
                        setFormData(prev => ({ ...prev, moneda_id: e.target.value, tipo_cambio: sel?.codigo === 'PEN' ? '1' : prev.tipo_cambio || '' }));
                      }}>
                      {monedas.map(m => <option key={m.id} value={m.id}>{m.nombre} ({m.simbolo})</option>)}
                    </select>
                  </div>
                </div>

                {/* Proveedor / Beneficiario */}
                <div className="form-grid form-grid-2" style={{ marginTop: '0.5rem' }}>
                  <div className="form-group">
                    <label className="form-label">Proveedor</label>
                    <SearchableSelect options={proveedores} value={formData.proveedor_id}
                      onChange={(value) => setFormData({ ...formData, proveedor_id: value, beneficiario_nombre: '' })}
                      placeholder="Seleccionar proveedor..." searchPlaceholder="Buscar..." displayKey="nombre" valueKey="id" clearable
                      onCreateNew={() => setShowQuickProv(true)} createNewLabel="Crear proveedor" />
                  </div>
                  <div className="form-group">
                    <label className="form-label">O Beneficiario (texto libre)</label>
                    <input type="text" className="form-input" value={formData.beneficiario_nombre}
                      onChange={(e) => setFormData({ ...formData, beneficiario_nombre: e.target.value, proveedor_id: '' })}
                      placeholder="Nombre del beneficiario" disabled={!!formData.proveedor_id} />
                  </div>
                </div>

                {/* Opciones secundarias (colapsable) */}
                <div style={{ marginTop: '0.75rem' }}>
                  <button type="button" onClick={() => setShowSunat(!showSunat)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.75rem', color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: '0.375rem', padding: '0.25rem 0' }}>
                    <span style={{ transform: showSunat ? 'rotate(90deg)' : 'rotate(0)', transition: 'transform 0.15s', display: 'inline-block' }}>&#9654;</span>
                    Datos adicionales (SUNAT, fecha contable)
                  </button>
                  {showSunat && (
                    <div style={{ marginTop: '0.5rem', padding: '0.75rem', background: 'var(--card-bg-hover)', borderRadius: '8px', border: '1px solid var(--border)' }}>
                      <div className="form-grid form-grid-4">
                        <div className="form-group">
                          <label className="form-label">Fecha Contable</label>
                          <input type="date" className="form-input" value={formData.fecha_contable}
                            onChange={(e) => { setFechaContableManual(true); setFormData(prev => ({ ...prev, fecha_contable: e.target.value })); }} />
                        </div>
                        <div className="form-group">
                          <label className="form-label">Doc SUNAT</label>
                          <select className="form-input form-select" value={formData.tipo_comprobante_sunat}
                            onChange={(e) => setFormData({ ...formData, tipo_comprobante_sunat: e.target.value })}>
                            <option value="">--</option>
                            <option value="01">01 - Factura</option>
                            <option value="03">03 - Boleta</option>
                            <option value="07">07 - Nota Credito</option>
                            <option value="08">08 - Nota Debito</option>
                            <option value="14">14 - Serv. Publico</option>
                            <option value="02">02 - Recibo Hon.</option>
                            <option value="12">12 - Ticket</option>
                            <option value="00">00 - Otros</option>
                          </select>
                        </div>
                        <div className="form-group">
                          <label className="form-label">Base Gravada</label>
                          <input type="text" className="form-input" value={totales.base_gravada.toFixed(2)} readOnly style={{ background: 'var(--input-bg-readonly)' }} />
                        </div>
                        <div className="form-group">
                          <label className="form-label">IGV</label>
                          <input type="text" className="form-input" value={totales.igv_sunat.toFixed(2)} readOnly style={{ background: 'var(--input-bg-readonly)' }} />
                        </div>
                      </div>
                      <div className="form-grid form-grid-4" style={{ marginTop: '0.5rem' }}>
                        <div className="form-group">
                          <label className="form-label">No Gravada</label>
                          <input type="text" className="form-input" value={totales.base_no_gravada.toFixed(2)} readOnly style={{ background: 'var(--input-bg-readonly)' }} />
                        </div>
                        <div className="form-group">
                          <label className="form-label">ISC</label>
                          <input type="number" step="0.01" min="0" className="form-input" value={formData.isc}
                            onChange={(e) => setFormData({ ...formData, isc: parseFloat(e.target.value) || 0 })} />
                        </div>
                      </div>
                      {monedas.find(m => m.id === parseInt(formData.moneda_id))?.codigo === 'USD' && (
                        <div className="form-grid form-grid-4" style={{ marginTop: '0.5rem' }}>
                          <div className="form-group">
                            <label className="form-label required">Tipo de Cambio</label>
                            <input type="number" step="0.001" className="form-input" placeholder="Ej: 3.72"
                              value={formData.tipo_cambio}
                              onChange={(e) => setFormData(prev => ({ ...prev, tipo_cambio: e.target.value }))} required />
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* === DETALLE: Clasificacion analitica === */}
                <div style={{ marginTop: '1.25rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <h3 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-heading)' }}>Detalle del Gasto</h3>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <label style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 500, userSelect: 'none', color: 'var(--text-label)' }}>
                        <input type="checkbox" checked={formData.impuestos_incluidos}
                          onChange={(e) => setFormData({ ...formData, impuestos_incluidos: e.target.checked })}
                          style={{ width: '16px', height: '16px', accentColor: 'var(--primary)' }} />
                        IGV Incluido
                      </label>
                      <button type="button" className="btn btn-outline btn-sm" onClick={handleAddLinea}>
                        <Plus size={14} /> Linea
                      </button>
                    </div>
                  </div>
                  
                  <div className="items-table-wrapper">
                    <table className="data-table items-table" data-testid="gasto-detalle-table">
                      <thead>
                        <tr>
                          <th style={{ width: '170px' }}>Categoria</th>
                          <th>Descripcion</th>
                          <th style={{ width: '130px' }}>Linea Negocio</th>
                          <th style={{ width: '130px' }}>Centro Costo</th>
                          <th style={{ width: '130px' }}>Unidad Interna</th>
                          <th style={{ width: '100px' }}>Importe</th>
                          <th style={{ width: '45px' }}>IGV</th>
                          <th style={{ width: '36px' }}></th>
                        </tr>
                      </thead>
                      <tbody>
                        {lineasGasto.map((linea, index) => (
                          <tr key={index}>
                            <td>
                              <CategoriaSelect
                                categorias={categorias}
                                value={linea.categoria_id}
                                onChange={(val) => handleLineaChange(index, 'categoria_id', val)}
                                placeholder="Categoria"
                              />
                            </td>
                            <td>
                              <input type="text" className="form-input" value={linea.descripcion}
                                onChange={(e) => handleLineaChange(index, 'descripcion', e.target.value)}
                                placeholder="Descripcion..." style={{ fontSize: '0.8125rem' }} />
                            </td>
                            <td>
                              <select className="form-input form-select" value={linea.linea_negocio_id}
                                onChange={(e) => handleLineaChange(index, 'linea_negocio_id', e.target.value)}
                                style={{ fontSize: '0.8125rem' }}>
                                <option value="">-</option>
                                {lineas.map(l => <option key={l.id} value={l.id}>{l.nombre}</option>)}
                              </select>
                            </td>
                            <td>
                              <select className="form-input form-select" value={linea.centro_costo_id}
                                onChange={(e) => handleLineaChange(index, 'centro_costo_id', e.target.value)}
                                style={{ fontSize: '0.8125rem' }}>
                                <option value="">-</option>
                                {centros.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
                              </select>
                            </td>
                            <td>
                              <select className="form-input form-select" value={linea.unidad_interna_id}
                                onChange={(e) => handleLineaChange(index, 'unidad_interna_id', e.target.value)}
                                style={{ fontSize: '0.8125rem' }}>
                                <option value="">-</option>
                                {unidadesInternas.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}
                              </select>
                            </td>
                            <td>
                              <input type="number" step="0.01" className="form-input text-right" value={linea.importe}
                                onChange={(e) => handleLineaChange(index, 'importe', e.target.value)}
                                style={{ fontSize: '0.8125rem', fontFamily: "'JetBrains Mono', monospace" }} />
                            </td>
                            <td className="text-center">
                              <input type="checkbox" checked={linea.igv_aplica}
                                onChange={(e) => handleLineaChange(index, 'igv_aplica', e.target.checked)} />
                            </td>
                            <td>
                              {lineasGasto.length > 1 && (
                                <button type="button" className="action-btn action-danger"
                                  onClick={() => handleRemoveLinea(index)} style={{ width: '26px', height: '26px' }}>
                                  <Trash2 size={13} />
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr>
                          <td colSpan={5} className="text-right" style={{ fontWeight: 500, fontSize: '0.8125rem' }}>Subtotal:</td>
                          <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.8125rem', whiteSpace: 'nowrap' }}>
                            {formatCurrency(totales.subtotal, monedaActual?.simbolo)}
                          </td>
                          <td colSpan={2}></td>
                        </tr>
                        <tr>
                          <td colSpan={5} className="text-right" style={{ fontWeight: 500, fontSize: '0.8125rem' }}>IGV (18%):</td>
                          <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.8125rem', whiteSpace: 'nowrap' }}>
                            {formatCurrency(totales.igv, monedaActual?.simbolo)}
                          </td>
                          <td colSpan={2}></td>
                        </tr>
                        <tr style={{ background: 'var(--card-bg-hover)' }}>
                          <td colSpan={5} className="text-right" style={{ fontWeight: 700, fontSize: '0.9375rem' }}>TOTAL:</td>
                          <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: '0.9375rem', color: 'var(--primary)', whiteSpace: 'nowrap' }}>
                            {formatCurrency(totales.total, monedaActual?.simbolo)}
                          </td>
                          <td colSpan={2}></td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                </div>

                {/* === PAGOS === */}
                <div style={{ marginTop: '1.25rem', padding: '0.75rem', background: 'var(--success-bg)', borderRadius: '8px', border: '1px solid var(--success-border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <h3 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 600, color: 'var(--success-text)', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                      <DollarSign size={16} /> Pagos
                    </h3>
                    <div style={{ display: 'flex', gap: '0.375rem' }}>
                      {!editingGastoId && (
                        <>
                          <button type="button" className="btn btn-outline btn-sm" onClick={handleDistribuirPago} style={{ fontSize: '0.75rem' }}>Distribuir</button>
                          <button type="button" className="btn btn-outline btn-sm" onClick={handleAddPago} style={{ fontSize: '0.75rem' }}>
                            <Plus size={13} /> Pago
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Existing payments (edit mode) */}
                  {editingGastoId && pagosExistentes.length > 0 && (
                    <table className="data-table" style={{ background: 'var(--card-bg)', fontSize: '0.8125rem', marginBottom: '0.5rem' }}>
                      <thead>
                        <tr>
                          <th style={{ width: '200px' }}>Cuenta</th>
                          <th style={{ width: '120px' }}>Medio</th>
                          <th style={{ width: '110px' }}>Monto</th>
                          <th style={{ width: '100px' }}>Estado</th>
                          <th style={{ width: '50px' }}></th>
                        </tr>
                      </thead>
                      <tbody>
                        {pagosExistentes.map(pe => (
                          <tr key={pe.id}>
                            <td style={{ padding: '0.5rem 0.75rem' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                                {pe.es_ficticia && <span title="Cuenta interna">⚡</span>}
                                <span style={{ fontWeight: 500 }}>{pe.cuenta_nombre || 'Sin cuenta'}</span>
                              </div>
                            </td>
                            <td style={{ padding: '0.5rem 0.75rem', textTransform: 'capitalize' }}>
                              {pe.medio_pago}
                            </td>
                            <td style={{ padding: '0.5rem 0.75rem', fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, textAlign: 'right' }}>
                              {formatCurrency(pe.monto_total, monedaActual?.simbolo)}
                            </td>
                            <td style={{ padding: '0.5rem 0.75rem' }}>
                              <span className={`badge ${pe.conciliado ? 'badge-success' : 'badge-neutral'}`} style={{ fontSize: '0.65rem' }}>
                                {pe.conciliado ? 'Conciliado' : 'Pendiente'}
                              </span>
                            </td>
                            <td style={{ padding: '0.5rem 0.75rem', textAlign: 'center' }}>
                              {!pe.conciliado && (
                                <button type="button" className="action-btn action-danger"
                                  onClick={() => handleDeleteExistingPago(pe.id)}
                                  style={{ width: '26px', height: '26px' }}
                                  title="Eliminar pago">
                                  <X size={13} />
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr style={{ background: 'var(--success-bg)' }}>
                          <td colSpan={2} className="text-right" style={{ fontWeight: 600, fontSize: '0.8125rem' }}>Total Pagado:</td>
                          <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: 'var(--primary)' }}>
                            {formatCurrency(totalPagado, monedaActual?.simbolo)}
                          </td>
                          <td colSpan={2} style={{ fontSize: '0.75rem', fontWeight: 600, color: saldoPendiente > 0.01 ? 'var(--warning-text)' : 'var(--success-text)' }}>
                            {saldoPendiente > 0.01 ? `Saldo: ${formatCurrency(saldoPendiente, monedaActual?.simbolo)}` : '✓ Pagado'}
                          </td>
                        </tr>
                      </tfoot>
                    </table>
                  )}

                  {editingGastoId && pagosExistentes.length === 0 && (
                    <div style={{ padding: '0.75rem', background: 'var(--card-bg)', borderRadius: '6px', marginBottom: '0.5rem', fontSize: '0.8125rem', color: 'var(--muted)', textAlign: 'center' }}>
                      Sin pagos registrados
                    </div>
                  )}

                  {/* New payment rows (create mode only) */}
                  {!editingGastoId && (
                    <>
                      <table className="data-table" style={{ background: 'var(--card-bg)', fontSize: '0.8125rem' }}>
                        <thead>
                          <tr>
                            <th style={{ width: '200px' }}>Cuenta *</th>
                            <th style={{ width: '130px' }}>Medio</th>
                            <th style={{ width: '110px' }}>Monto *</th>
                            <th>Referencia</th>
                            <th style={{ width: '36px' }}></th>
                          </tr>
                        </thead>
                        <tbody>
                          {pagos.map((pago, index) => (
                            <tr key={index}>
                              <td>
                                <select className="form-input form-select" value={pago.cuenta_financiera_id}
                                  onChange={(e) => handlePagoChange(index, 'cuenta_financiera_id', e.target.value)}
                                  style={{ fontSize: '0.8125rem' }} required>
                                  <option value="">Seleccionar...</option>
                                  {cuentas.filter(c => !c.es_ficticia).map(c => <option key={c.id} value={c.id}>{c.nombre} ({formatCurrency(c.saldo_actual)})</option>)}
                                  {cuentas.some(c => c.es_ficticia) && <option disabled>── Unidades Internas ──</option>}
                                  {cuentas.filter(c => c.es_ficticia).map(c => <option key={c.id} value={c.id}>⚡ {c.nombre} ({formatCurrency(c.saldo_actual)})</option>)}
                                </select>
                              </td>
                              <td>
                                <select className="form-input form-select" value={pago.medio_pago}
                                  onChange={(e) => handlePagoChange(index, 'medio_pago', e.target.value)}
                                  style={{ fontSize: '0.8125rem' }}>
                                  {MEDIOS_PAGO.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
                                </select>
                              </td>
                              <td>
                                <input type="number" step="0.01" className="form-input text-right" value={pago.monto}
                                  onChange={(e) => handlePagoChange(index, 'monto', e.target.value)}
                                  style={{ fontSize: '0.8125rem', fontFamily: "'JetBrains Mono', monospace" }} required />
                              </td>
                              <td>
                                <input type="text" className="form-input" value={pago.referencia}
                                  onChange={(e) => handlePagoChange(index, 'referencia', e.target.value)}
                                  placeholder="N operacion..." style={{ fontSize: '0.8125rem' }} />
                              </td>
                              <td>
                                {pagos.length > 1 && (
                                  <button type="button" className="action-btn action-danger"
                                    onClick={() => handleRemovePago(index)} style={{ width: '26px', height: '26px' }}>
                                    <Trash2 size={13} />
                                  </button>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                        <tfoot>
                          <tr style={{ background: totalPagos !== totales.total ? 'var(--danger-bg)' : 'var(--success-bg)' }}>
                            <td colSpan={2} className="text-right" style={{ fontWeight: 600 }}>Total Pagos:</td>
                            <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600,
                              color: Math.abs(totalPagos - totales.total) > 0.01 ? 'var(--danger-text)' : 'var(--success-text)' }}>
                              {formatCurrency(totalPagos, monedaActual?.simbolo)}
                            </td>
                            <td colSpan={2}>
                              {Math.abs(totalPagos - totales.total) > 0.01 && (
                                <span style={{ color: 'var(--danger-text)', fontSize: '0.75rem' }}>
                                  Diferencia: {formatCurrency(totales.total - totalPagos, monedaActual?.simbolo)}
                                </span>
                              )}
                            </td>
                          </tr>
                        </tfoot>
                      </table>
                    </>
                  )}
                </div>

                {/* Warning for fictitious account (only in create mode) */}
                {!editingGastoId && (() => {
                  const cuentaFicticia = pagos.reduce((found, p) => {
                    if (found) return found;
                    return cuentas.find(c => String(c.id) === String(p.cuenta_financiera_id) && c.es_ficticia === true);
                  }, null);
                  if (!cuentaFicticia) return null;
                  return (
                    <div style={{ padding: '8px 12px', background: 'var(--warning-bg)', border: '1px solid var(--warning-border)', borderRadius: 6, marginTop: 8, fontSize: '0.78rem', color: 'var(--warning-text)' }}>
                      ⚠️ Este gasto saldrá de la cuenta de <strong>{cuentaFicticia.unidad_interna_nombre || cuentaFicticia.nombre}</strong>, no de la caja de la empresa.
                    </div>
                  );
                })()}

                {/* Categoría de Gasto (CIF / No CIF) — la Unidad Interna ahora va por línea */}
                <div className="form-group" style={{ marginTop: '0.75rem' }}>
                  <label className="form-label">Categoría de Gasto (CIF / No CIF)</label>
                  <select className="form-input" value={formData.categoria_gasto_id || ''}
                    onChange={(e) => setFormData({ ...formData, categoria_gasto_id: e.target.value ? parseInt(e.target.value) : null })}>
                    <option value="">— Sin clasificar —</option>
                    <optgroup label="CIF (costos indirectos de fabricación)">
                      {categoriasGasto.filter(c => c.es_cif).map(c => (
                        <option key={c.id} value={c.id}>{c.nombre}</option>
                      ))}
                    </optgroup>
                    <optgroup label="No CIF (administrativo / comercial)">
                      {categoriasGasto.filter(c => !c.es_cif).map(c => (
                        <option key={c.id} value={c.id}>{c.nombre}</option>
                      ))}
                    </optgroup>
                  </select>
                  {categoriasGasto.find(c => c.id === formData.categoria_gasto_id && c.es_cif) && (
                    <p style={{ fontSize: '11px', color: 'var(--success-text)', marginTop: 4, background: 'var(--success-bg)', padding: '4px 8px', borderRadius: 6, display: 'inline-block' }}>
                      CIF — se distribuye entre lotes del periodo
                    </p>
                  )}
                </div>

                {/* Notas */}
                <div className="form-group" style={{ marginTop: '0.75rem' }}>
                  <label className="form-label">Glosa / Observaciones</label>
                  <textarea className="form-input" rows={2} value={formData.notas}
                    onChange={(e) => setFormData({ ...formData, notas: e.target.value })}
                    placeholder="Observaciones adicionales..." />
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-outline" onClick={() => setShowModal(false)}>
                  Cancelar
                </button>
                <button 
                  type="submit" 
                  className="btn btn-primary"
                  disabled={submitting || (!editingGastoId && (Math.abs(totalPagos - totales.total) > 0.01)) || totales.total <= 0}
                >
                  <DollarSign size={16} />
                  {submitting ? 'Guardando...' : editingGastoId ? 'Guardar Cambios' : 'Guardar y Pagar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Ver Gasto */}
      {showViewModal && selectedGasto && (
        <div className="modal-overlay" onClick={() => setShowViewModal(false)}>
          <div className="modal modal-lg" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">Gasto {selectedGasto.numero}</h2>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button className="btn btn-outline btn-sm" onClick={() => handleDownloadPDF(selectedGasto)} title="Descargar PDF">
                  <Download size={16} /> PDF
                </button>
                <button className="modal-close" onClick={() => setShowViewModal(false)}>
                  <X size={20} />
                </button>
              </div>
            </div>
            <div className="modal-body">
              {/* Cabecera: datos del documento */}
              <div className="form-grid form-grid-4" style={{ marginBottom: '1rem' }}>
                <div>
                  <label className="form-label">Fecha</label>
                  <p style={{ fontWeight: 500 }}>{formatDate(selectedGasto.fecha)}</p>
                </div>
                <div>
                  <label className="form-label">Proveedor/Beneficiario</label>
                  <p style={{ fontWeight: 500 }}>{selectedGasto.proveedor_nombre || selectedGasto.beneficiario_nombre || '-'}</p>
                </div>
                <div>
                  <label className="form-label">Documento</label>
                  <p style={{ fontWeight: 500 }}>
                    {selectedGasto.tipo_documento && selectedGasto.numero_documento 
                      ? `${selectedGasto.tipo_documento.toUpperCase()} ${selectedGasto.numero_documento}` : '-'}
                  </p>
                </div>
                <div>
                  <label className="form-label">Moneda</label>
                  <p style={{ fontWeight: 500 }}>{selectedGasto.moneda_codigo || 'PEN'}</p>
                </div>
              </div>

              {/* Detalle: clasificacion analitica */}
              <h4 style={{ margin: '0.75rem 0 0.5rem', fontSize: '0.875rem', fontWeight: 600 }}>Detalle del Gasto</h4>
              <table className="data-table" style={{ fontSize: '0.8125rem' }}>
                <thead>
                  <tr>
                    <th>Categoria</th>
                    <th>Descripcion</th>
                    <th>Linea Negocio</th>
                    <th>Centro Costo</th>
                    <th className="text-right">Importe</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedGasto.lineas?.map((linea, i) => (
                    <tr key={i}>
                      <td>
                        {linea.categoria_padre_nombre 
                          ? <span><span style={{ color: 'var(--text-muted)' }}>{linea.categoria_padre_nombre}</span> &gt; {linea.categoria_nombre}</span>
                          : (linea.categoria_nombre || '-')}
                      </td>
                      <td>{linea.descripcion || '-'}</td>
                      <td>{linea.linea_negocio_nombre || '-'}</td>
                      <td>{linea.centro_costo_nombre || '-'}</td>
                      <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                        {formatCurrency(linea.importe)}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <td colSpan={4} className="text-right">Subtotal:</td>
                    <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {formatCurrency(selectedGasto.subtotal)}
                    </td>
                  </tr>
                  <tr>
                    <td colSpan={4} className="text-right">IGV:</td>
                    <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {formatCurrency(selectedGasto.igv)}
                    </td>
                  </tr>
                  <tr style={{ fontWeight: 600 }}>
                    <td colSpan={4} className="text-right">TOTAL:</td>
                    <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--primary)' }}>
                      {formatCurrency(selectedGasto.total)}
                    </td>
                  </tr>
                </tfoot>
              </table>

              {/* Tipo asignacion auto-derivado */}
              {selectedGasto.tipo_asignacion && (
                <div style={{ marginTop: '0.75rem', display: 'flex', gap: '1rem', alignItems: 'center', fontSize: '0.8125rem', color: 'var(--muted)' }}>
                  <span>Asignacion: <span style={{
                    padding: '2px 8px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: 500,
                    background: selectedGasto.tipo_asignacion === 'directo' ? '#dbeafe' : selectedGasto.tipo_asignacion === 'comun' ? '#fef9c3' : 'var(--card-bg-alt)',
                    color: selectedGasto.tipo_asignacion === 'directo' ? '#1e40af' : selectedGasto.tipo_asignacion === 'comun' ? '#854d0e' : 'var(--muted)'
                  }}>{selectedGasto.tipo_asignacion}</span></span>
                  {selectedGasto.unidad_interna_nombre && <span>Unidad: {selectedGasto.unidad_interna_nombre}</span>}
                </div>
              )}

              {selectedGasto.notas && (
                <div style={{ marginTop: '0.75rem' }}>
                  <label className="form-label">Observaciones</label>
                  <p style={{ color: 'var(--muted)', fontSize: '0.875rem' }}>{selectedGasto.notas}</p>
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setShowViewModal(false)}>Cerrar</button>
            </div>
          </div>
        </div>
      )}

      {/* Quick-create Proveedor modal */}
      {showQuickProv && (
        <div className="modal-overlay" onClick={() => setShowQuickProv(false)} style={{ zIndex: 1100 }}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: '420px' }}>
            <div className="modal-header">
              <h2 className="modal-title">Crear Proveedor</h2>
              <button className="modal-close" onClick={() => setShowQuickProv(false)}><X size={18} /></button>
            </div>
            <form onSubmit={handleQuickCreateProv}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Nombre / Razon Social *</label>
                  <input type="text" className="form-input" value={quickProvForm.nombre} autoFocus
                    onChange={e => setQuickProvForm({ ...quickProvForm, nombre: e.target.value })} required data-testid="quick-prov-nombre" />
                </div>
                <div className="form-grid form-grid-2" style={{ marginTop: '0.5rem' }}>
                  <div className="form-group">
                    <label className="form-label">Tipo Doc.</label>
                    <select className="form-input form-select" value={quickProvForm.tipo_documento}
                      onChange={e => setQuickProvForm({ ...quickProvForm, tipo_documento: e.target.value })}>
                      <option value="RUC">RUC</option>
                      <option value="DNI">DNI</option>
                      <option value="CE">CE</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">N Documento</label>
                    <input type="text" className="form-input" value={quickProvForm.numero_documento}
                      onChange={e => setQuickProvForm({ ...quickProvForm, numero_documento: e.target.value })}
                      placeholder="20123456789" data-testid="quick-prov-ruc" />
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-outline" onClick={() => setShowQuickProv(false)}>Cancelar</button>
                <button type="submit" className="btn btn-primary" disabled={savingProv}>
                  {savingProv ? 'Creando...' : 'Crear y Seleccionar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
