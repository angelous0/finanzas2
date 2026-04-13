import React, { useState, useEffect, useCallback } from 'react';
import { 
  getVentasPOS, refreshVentasPOS, confirmarVentaPOS, desconfirmarVentaPOS,
  marcarCreditoVentaPOS, descartarVentaPOS,
  getPagosVentaPOS, getPagosOficialesVentaPOS, addPagoVentaPOS, updatePagoVentaPOS, deletePagoVentaPOS,
  getCuentasFinancieras, getLineasVentaPOS, syncLocalVentasPOS,
  getOdooCompanyMap, setOdooCompanyMap, getPagosCreditoVentaPOS
} from '../services/api';
import { useEmpresa } from '../context/EmpresaContext';
import { Check, CreditCard, X, ShoppingCart, Download, Plus, Trash2, Eye, RotateCcw, Search, Edit, ChevronLeft, ChevronRight, Settings, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import * as XLSX from 'xlsx';

const formatCurrency = (value, symbol = 'S/') => {
  return `${symbol} ${Number(value || 0).toLocaleString('es-PE', { minimumFractionDigits: 2 })}`;
};

const formatDateTime = (dateStr) => {
  if (!dateStr) return '';
  const raw = String(dateStr);
  const utcDate = new Date(raw.endsWith('Z') ? raw : raw + 'Z');
  return utcDate.toLocaleString('es-PE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'America/Lima'
  });
};

const getYesterdayInLima = () => {
  const now = new Date();
  const limaTime = new Date(now.getTime() - (5 * 60 * 60 * 1000));
  limaTime.setDate(limaTime.getDate() - 1);
  return limaTime.toISOString().split('T')[0];
};

const getTodayInLima = () => {
  const now = new Date();
  const limaTime = new Date(now.getTime() - (5 * 60 * 60 * 1000));
  return limaTime.toISOString().split('T')[0];
};

// ===== MISSING COMPANY KEY CONFIG SCREEN =====
const MissingCompanyKeyScreen = ({ onConfigured }) => {
  const [companyKey, setCompanyKey] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!companyKey.trim()) {
      toast.error('Ingrese un company_key');
      return;
    }
    setSaving(true);
    try {
      await setOdooCompanyMap({ company_key: companyKey.trim() });
      toast.success('Mapeo configurado correctamente');
      onConfigured();
    } catch (error) {
      toast.error('Error al guardar el mapeo');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div data-testid="missing-company-key-screen" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '60vh' }}>
      <div style={{ maxWidth: '500px', width: '100%', textAlign: 'center', padding: '2.5rem', border: '2px solid var(--border)', borderRadius: '16px', background: 'var(--card-bg)' }}>
        <Settings size={48} style={{ color: '#6366f1', marginBottom: '1.5rem' }} />
        <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#111827', marginBottom: '0.75rem' }}>
          Configurar Conexion Odoo
        </h2>
        <p style={{ color: 'var(--muted)', marginBottom: '2rem', lineHeight: 1.6 }}>
          No hay un mapeo empresa - company_key configurado para esta empresa.
          Ingrese el <strong>company_key</strong> de Odoo para habilitar la lectura de ventas POS.
        </p>
        <div style={{ textAlign: 'left', marginBottom: '1.5rem' }}>
          <label className="form-label" style={{ fontWeight: 600, marginBottom: '0.5rem', display: 'block' }}>
            Company Key de Odoo
          </label>
          <input
            type="text"
            className="form-input"
            placeholder="Ej: Ambission"
            value={companyKey}
            onChange={(e) => setCompanyKey(e.target.value)}
            data-testid="company-key-input"
            style={{ width: '100%', padding: '0.75rem', borderRadius: '8px', border: '2px solid #d1d5db', fontSize: '1rem' }}
          />
        </div>
        <button
          className="btn btn-primary"
          onClick={handleSave}
          disabled={saving || !companyKey.trim()}
          data-testid="save-company-key-btn"
          style={{ width: '100%', padding: '0.75rem', fontSize: '1rem', fontWeight: 600, borderRadius: '8px' }}
        >
          {saving ? 'Guardando...' : 'Guardar y Continuar'}
        </button>
      </div>
    </div>
  );
};

// ===== PAGINATION COMPONENT =====
const Pagination = ({ page, totalPages, total, pageSize, onPageChange }) => {
  if (totalPages <= 1) return null;

  const pages = [];
  const maxVisible = 5;
  let start = Math.max(1, page - Math.floor(maxVisible / 2));
  let end = Math.min(totalPages, start + maxVisible - 1);
  if (end - start + 1 < maxVisible) start = Math.max(1, end - maxVisible + 1);
  for (let i = start; i <= end; i++) pages.push(i);

  return (
    <div data-testid="pagination" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1rem 0', borderTop: '1px solid var(--border)', marginTop: '0.5rem' }}>
      <span style={{ fontSize: '0.875rem', color: 'var(--muted)' }}>
        Mostrando {((page - 1) * pageSize) + 1}-{Math.min(page * pageSize, total)} de {total} registros
      </span>
      <div style={{ display: 'flex', gap: '0.25rem', alignItems: 'center' }}>
        <button
          className="btn btn-outline btn-sm"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          data-testid="pagination-prev"
          style={{ padding: '0.375rem 0.5rem' }}
        >
          <ChevronLeft size={16} />
        </button>
        {start > 1 && (
          <>
            <button className="btn btn-outline btn-sm" onClick={() => onPageChange(1)} style={{ minWidth: '2rem' }}>1</button>
            {start > 2 && <span style={{ color: 'var(--muted)' }}>...</span>}
          </>
        )}
        {pages.map(p => (
          <button
            key={p}
            className={`btn btn-sm ${p === page ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => onPageChange(p)}
            style={{ minWidth: '2rem' }}
          >
            {p}
          </button>
        ))}
        {end < totalPages && (
          <>
            {end < totalPages - 1 && <span style={{ color: 'var(--muted)' }}>...</span>}
            <button className="btn btn-outline btn-sm" onClick={() => onPageChange(totalPages)} style={{ minWidth: '2rem' }}>{totalPages}</button>
          </>
        )}
        <button
          className="btn btn-outline btn-sm"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
          data-testid="pagination-next"
          style={{ padding: '0.375rem 0.5rem' }}
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
};

// ===== MAIN COMPONENT =====
export const VentasPOS = () => {
  const { empresaActual } = useEmpresa();

  const [ventas, setVentas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [activeTab, setActiveTab] = useState('pendiente');
  const [missingCompanyKey, setMissingCompanyKey] = useState(false);

  // Pagination
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [totalRecords, setTotalRecords] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [maxDateOrder, setMaxDateOrder] = useState(null);

  // Filters - default to current month
  const [fechaDesde, setFechaDesde] = useState(() => {
    const d = new Date(); d.setDate(1);
    return d.toISOString().split('T')[0];
  });
  const [fechaHasta, setFechaHasta] = useState(() => new Date().toISOString().split('T')[0]);
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => setSearch(searchInput), 300);
    return () => clearTimeout(timer);
  }, [searchInput]);

  // Reset page when filters change
  useEffect(() => { setPage(1); }, [activeTab, fechaDesde, fechaHasta, search, empresaActual]);

  // Modal pagos
  const [showPagosModal, setShowPagosModal] = useState(false);
  const [ventaSeleccionada, setVentaSeleccionada] = useState(null);
  const [pagos, setPagos] = useState([]);
  const [loadingPagos, setLoadingPagos] = useState(false);
  const [cuentasFinancieras, setCuentasFinancieras] = useState([]);
  const [nuevoPago, setNuevoPago] = useState({
    forma_pago: 'Efectivo', cuenta_financiera_id: '', monto: '', referencia: '',
    fecha_pago: new Date().toISOString().split('T')[0], observaciones: ''
  });

  // Modal pagos oficiales
  const [showPagosOficialesModal, setShowPagosOficialesModal] = useState(false);
  const [pagosOficiales, setPagosOficiales] = useState([]);
  const [loadingPagosOficiales, setLoadingPagosOficiales] = useState(false);

  // Modal editar pago
  const [showEditPagoModal, setShowEditPagoModal] = useState(false);
  const [pagoEditando, setPagoEditando] = useState(null);

  // Modal ver lineas
  const [showLineasModal, setShowLineasModal] = useState(false);
  const [lineasProductos, setLineasProductos] = useState([]);
  const [loadingLineas, setLoadingLineas] = useState(false);

  // Modal pagos credito (CxC abonos)
  const [showPagosCreditoModal, setShowPagosCreditoModal] = useState(false);
  const [pagosCreditoData, setPagosCreditoData] = useState({ abonos: [], cxc: null });
  const [loadingPagosCredito, setLoadingPagosCredito] = useState(false);

  const loadVentas = useCallback(async () => {
    try {
      setLoading(true);
      setMissingCompanyKey(false);
      const params = {
        estado: activeTab !== 'todas' ? activeTab : undefined,
        fecha_desde: fechaDesde || undefined,
        fecha_hasta: fechaHasta || undefined,
        search: search || undefined,
        page,
        page_size: pageSize
      };
      const response = await getVentasPOS(params);
      const data = response.data;

      if (data.error_code === 'MISSING_ODOO_COMPANY_KEY') {
        setMissingCompanyKey(true);
        setVentas([]);
        setTotalRecords(0);
        setTotalPages(0);
        setMaxDateOrder(null);
        return;
      }

      setVentas(data.data || []);
      setTotalRecords(data.total || 0);
      setTotalPages(data.total_pages || 0);
      setMaxDateOrder(data.max_date_order || null);
    } catch (error) {
      console.error('Error loading ventas:', error);
      toast.error('Error al cargar ventas');
    } finally {
      setLoading(false);
    }
  }, [activeTab, fechaDesde, fechaHasta, search, empresaActual, page, pageSize]);

  useEffect(() => { loadVentas(); }, [loadVentas]);

  // Actions
  const handleConfirmar = async (id) => {
    if (!window.confirm('Confirmar esta venta? Debe tener pagos asignados.')) return;
    try {
      await confirmarVentaPOS(id);
      toast.success('Venta confirmada');
      loadVentas();
    } catch (error) {
      if (error.response?.data?.detail?.includes('pago')) {
        toast.error('Error: Debe asignar pagos antes de confirmar');
      } else {
        toast.error('Error al confirmar venta');
      }
    }
  };

  const handleCredito = async (id) => {
    try {
      await marcarCreditoVentaPOS(id);
      toast.success('Venta marcada como credito');
      loadVentas();
    } catch (error) {
      toast.error('Error al marcar como credito');
    }
  };

  const handleDescartar = async (id) => {
    if (!window.confirm('Esta seguro de descartar esta venta?')) return;
    try {
      await descartarVentaPOS(id);
      toast.success('Venta descartada');
      loadVentas();
    } catch (error) {
      toast.error('Error al descartar venta');
    }
  };

  const handleDesconfirmar = async (ventaDirecta) => {
    const venta = ventaDirecta || ventaSeleccionada;
    if (!venta) return;
    const confirmado = window.confirm(
      `Desconfirmar venta?\n\nVenta: ${venta.name}\nCliente: ${venta.partner_name}\nTotal: ${formatCurrency(venta.amount_total)}\n\nLa venta volvera a estado PENDIENTE y los pagos oficiales se eliminaran.`
    );
    if (!confirmado) return;
    try {
      const response = await desconfirmarVentaPOS(venta.id);
      toast.success(response.data.message);
      closePagosOficialesModal();
      loadVentas();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al desconfirmar venta');
    }
  };

  const handleExportExcel = () => {
    try {
      const excelData = ventas.map(v => ({
        'Fecha': formatDateTime(v.date_order),
        'Orden': v.name || '-',
        'Cliente': v.partner_name || '-',
        'Vendedor': v.vendedor_name || '-',
        'Estado': v.estado_local || '-',
        'Pagos Asignados': v.pagos_asignados || 0,
        'Total': v.amount_total || 0
      }));
      const ws = XLSX.utils.json_to_sheet(excelData);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, 'Ventas POS');
      ws['!cols'] = [
        { wch: 18 }, { wch: 20 }, { wch: 30 }, { wch: 25 },
        { wch: 12 }, { wch: 18 }, { wch: 12 }
      ];
      const today = new Date().toISOString().split('T')[0];
      XLSX.writeFile(wb, `ventas_pos_${today}.xlsx`);
      toast.success(`Exportadas ${excelData.length} ventas a Excel`);
    } catch (error) {
      toast.error('Error al exportar a Excel');
    }
  };

  // ===== PAGOS MODAL =====
  const openPagosModal = async (venta) => {
    setVentaSeleccionada(venta);
    setShowPagosModal(true);
    setLoadingPagos(true);
    try {
      const response = await getPagosVentaPOS(venta.id);
      setPagos(response.data);
      const cuentasResp = await getCuentasFinancieras();
      setCuentasFinancieras(cuentasResp.data);
      const totalPagos = response.data.reduce((sum, p) => sum + parseFloat(p.monto || 0), 0);
      const faltante = parseFloat(venta.amount_total) - totalPagos;
      const numPagosExistentes = response.data.length;
      const referenciaAuto = numPagosExistentes === 0
        ? (venta.num_comp || venta.name)
        : `${venta.num_comp || venta.name}-${numPagosExistentes + 1}`;
      setNuevoPago({
        forma_pago: 'Efectivo',
        cuenta_financiera_id: cuentasResp.data.length > 0 ? cuentasResp.data[0].id : '',
        monto: faltante > 0 ? faltante.toFixed(2) : '',
        referencia: referenciaAuto,
        fecha_pago: new Date().toISOString().split('T')[0],
        observaciones: ''
      });
    } catch (error) {
      toast.error('Error al cargar pagos');
    } finally {
      setLoadingPagos(false);
    }
  };

  const closePagosModal = () => {
    setShowPagosModal(false);
    setVentaSeleccionada(null);
    setPagos([]);
    setCuentasFinancieras([]);
    setNuevoPago({
      forma_pago: 'Efectivo', cuenta_financiera_id: '', monto: '', referencia: '',
      fecha_pago: new Date().toISOString().split('T')[0], observaciones: ''
    });
  };

  const handleAddPago = async () => {
    if (submitting) return;
    if (!nuevoPago.monto || parseFloat(nuevoPago.monto) <= 0) { toast.error('Ingrese un monto valido'); return; }
    if (!nuevoPago.cuenta_financiera_id) { toast.error('Seleccione una cuenta'); return; }
    setSubmitting(true);
    try {
      const response = await addPagoVentaPOS(ventaSeleccionada.id, {
        ...nuevoPago, monto: parseFloat(nuevoPago.monto)
      });
      if (response.data.auto_confirmed) {
        toast.success(response.data.message);
        closePagosModal();
        loadVentas();
      } else {
        toast.success(response.data.message + ` (Falta: S/ ${response.data.faltante.toFixed(2)})`);
        const pagosResp = await getPagosVentaPOS(ventaSeleccionada.id);
        setPagos(pagosResp.data);
        loadVentas();
        const totalPagos = pagosResp.data.reduce((sum, p) => sum + parseFloat(p.monto || 0), 0);
        const faltante = parseFloat(ventaSeleccionada.amount_total) - totalPagos;
        const numPagos = pagosResp.data.length;
        setVentaSeleccionada({ ...ventaSeleccionada, pagos_asignados: totalPagos });
        setNuevoPago({
          ...nuevoPago,
          monto: faltante > 0 ? faltante.toFixed(2) : '',
          referencia: `${ventaSeleccionada.num_comp || ventaSeleccionada.name}-${numPagos + 1}`,
          observaciones: ''
        });
      }
    } catch (error) {
      toast.error('Error al agregar pago');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeletePago = async (pagoId) => {
    if (!window.confirm('Eliminar este pago?')) return;
    try {
      await deletePagoVentaPOS(ventaSeleccionada.id, pagoId);
      toast.success('Pago eliminado');
      const response = await getPagosVentaPOS(ventaSeleccionada.id);
      setPagos(response.data);
    } catch (error) {
      toast.error('Error al eliminar pago');
    }
  };

  const handleEditPago = (pago) => { setPagoEditando({...pago}); setShowEditPagoModal(true); };

  const handleUpdatePago = async () => {
    if (!pagoEditando || !pagoEditando.monto || parseFloat(pagoEditando.monto) <= 0) {
      toast.error('El monto debe ser mayor a 0');
      return;
    }
    try {
      await updatePagoVentaPOS(ventaSeleccionada.id, pagoEditando.id, pagoEditando);
      toast.success('Pago actualizado correctamente');
      setShowEditPagoModal(false);
      setPagoEditando(null);
      const response = await getPagosVentaPOS(ventaSeleccionada.id);
      setPagos(response.data);
    } catch (error) {
      toast.error('Error al actualizar pago');
    }
  };

  // ===== PAGOS OFICIALES MODAL =====
  const verPagosConfirmada = async (venta) => {
    setVentaSeleccionada(venta);
    setShowPagosOficialesModal(true);
    setLoadingPagosOficiales(true);
    try {
      const response = await getPagosOficialesVentaPOS(venta.id);
      setPagosOficiales(response.data);
    } catch (error) {
      toast.error('Error al cargar pagos');
    } finally {
      setLoadingPagosOficiales(false);
    }
  };

  const closePagosOficialesModal = () => {
    setShowPagosOficialesModal(false);
    setVentaSeleccionada(null);
    setPagosOficiales([]);
  };

  const exportarPagosOficiales = () => {
    if (!pagosOficiales?.length) { toast.error('No hay pagos para exportar'); return; }
    try {
      const excelData = pagosOficiales.map(p => ({
        'Numero': p.numero, 'Forma de Pago': p.forma_pago, 'Monto': p.monto,
        'Cuenta': p.cuenta_nombre || '-', 'Referencia': p.referencia || '-',
        'Fecha': new Date(p.fecha).toLocaleDateString('es-PE'), 'Observaciones': p.observaciones || '-'
      }));
      const ws = XLSX.utils.json_to_sheet(excelData);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, 'Pagos');
      XLSX.writeFile(wb, `pagos_${ventaSeleccionada.name}_${new Date().toISOString().split('T')[0]}.xlsx`);
      toast.success(`Exportados ${pagosOficiales.length} pagos a Excel`);
    } catch (error) {
      toast.error('Error al exportar pagos');
    }
  };

  // ===== LINEAS MODAL =====
  const verLineasProductos = async (venta) => {
    setVentaSeleccionada(venta);
    setShowLineasModal(true);
    setLoadingLineas(true);
    try {
      const response = await getLineasVentaPOS(venta.id);
      setLineasProductos(response.data);
    } catch (error) {
      toast.error('Error al cargar lineas de productos');
    } finally {
      setLoadingLineas(false);
    }
  };

  const closeLineasModal = () => {
    setShowLineasModal(false);
    setVentaSeleccionada(null);
    setLineasProductos([]);
  };

  // ===== PAGOS CREDITO MODAL =====
  const verPagosCredito = async (venta) => {
    setVentaSeleccionada(venta);
    setShowPagosCreditoModal(true);
    setLoadingPagosCredito(true);
    try {
      const response = await getPagosCreditoVentaPOS(venta.id);
      setPagosCreditoData(response.data);
    } catch (error) {
      toast.error('Error al cargar pagos de credito');
    } finally {
      setLoadingPagosCredito(false);
    }
  };

  const closePagosCreditoModal = () => {
    setShowPagosCreditoModal(false);
    setVentaSeleccionada(null);
    setPagosCreditoData({ abonos: [], cxc: null });
  };

  // KPIs - only confirmed sales
  const ventasConfirmadas = ventas.filter(v => v.estado_local === 'confirmada');
  const totalVentas = ventasConfirmadas.length;
  const montoTotal = ventasConfirmadas.reduce((sum, v) => sum + parseFloat(v.amount_total || 0), 0);

  const tabs = [
    { id: 'pendiente', label: 'Pendientes' },
    { id: 'confirmada', label: 'Confirmadas' },
    { id: 'credito', label: 'Credito' },
    { id: 'descartada', label: 'Descartadas' },
    { id: 'todas', label: 'Todas' }
  ];

  // ===== RENDER =====
  if (missingCompanyKey) {
    return (
      <div data-testid="ventas-pos-page">
        <div className="page-header">
          <div>
            <h1 className="page-title">Ventas POS</h1>
            <p className="page-subtitle">Configuracion requerida</p>
          </div>
        </div>
        <div className="page-content">
          <MissingCompanyKeyScreen onConfigured={loadVentas} />
        </div>
      </div>
    );
  }

  return (
    <div data-testid="ventas-pos-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Ventas POS</h1>
          <p className="page-subtitle">
            Ventas desde Odoo {totalRecords > 0 && `(${totalRecords} registros)`}
            {maxDateOrder && (
              <span style={{ marginLeft: '0.75rem', fontSize: '0.8rem', color: 'var(--muted)' }}>
                | Ultima venta: {formatDateTime(maxDateOrder)}
              </span>
            )}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            className="btn btn-primary"
            onClick={async () => {
              setRefreshing(true);
              try {
                const result = await refreshVentasPOS({
                  desde: fechaDesde || undefined,
                  hasta: fechaHasta || undefined
                });
                const d = result.data;
                toast.success(`Sync completado: ${d.inserted || 0} nuevos, ${d.updated || 0} actualizados`);
                // Also sync lines to local tables
                try {
                  await syncLocalVentasPOS({
                    fecha_desde: fechaDesde || undefined,
                    fecha_hasta: fechaHasta || undefined
                  });
                } catch(syncErr) {
                  console.warn('Local sync error:', syncErr);
                }
                loadVentas();
              } catch (error) {
                const detail = error.response?.data?.detail;
                if (typeof detail === 'object' && detail?.error === 'MISSING_ODOO_COMPANY_KEY') {
                  toast.error('Falta configurar el mapeo empresa - Odoo');
                } else {
                  toast.error(typeof detail === 'string' ? detail : 'Error al sincronizar con Odoo');
                }
              } finally {
                setRefreshing(false);
              }
            }}
            disabled={refreshing || loading}
            data-testid="refresh-ventas-btn"
          >
            <RefreshCw size={18} className={refreshing ? 'animate-spin' : ''} />
            {refreshing ? 'Sincronizando...' : 'Actualizar'}
          </button>
          <button 
            className="btn btn-success"
            onClick={handleExportExcel}
            disabled={ventas.length === 0}
            data-testid="export-excel-btn"
          >
            <Download size={18} />
            Exportar Excel
          </button>
        </div>
      </div>

      <div className="page-content">
        {/* KPIs */}
        <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)', marginBottom: '1rem' }}>
          <div className="kpi-card">
            <div className="kpi-label">Confirmadas (pag.)</div>
            <div className="kpi-value">{totalVentas}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Monto Confirmado (pag.)</div>
            <div className="kpi-value positive">{formatCurrency(montoTotal)}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Total Registros</div>
            <div className="kpi-value">{totalRecords}</div>
          </div>
        </div>

        {/* Filters */}
        <div className="filters-bar">
          <div style={{ position: 'relative', minWidth: '300px' }}>
            <Search size={18} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--muted)', pointerEvents: 'none' }} />
            <input
              type="text"
              className="form-input filter-input"
              placeholder="Buscar por cliente o vendedor..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              data-testid="search-input"
              style={{ paddingLeft: '40px', paddingRight: searchInput ? '40px' : '12px', minWidth: '300px' }}
            />
            {searchInput && (
              <button onClick={() => setSearchInput('')} style={{ position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', padding: '4px', color: 'var(--muted)', borderRadius: '4px' }} title="Limpiar busqueda">
                <X size={16} />
              </button>
            )}
          </div>
          <input type="date" className="form-input filter-input" value={fechaDesde} onChange={(e) => setFechaDesde(e.target.value)} data-testid="fecha-desde" />
          <input type="date" className="form-input filter-input" value={fechaHasta} onChange={(e) => setFechaHasta(e.target.value)} data-testid="fecha-hasta" />
        </div>

        {/* Tabs */}
        <div className="tabs">
          {tabs.map(tab => (
            <button key={tab.id} className={`tab ${activeTab === tab.id ? 'active' : ''}`} onClick={() => setActiveTab(tab.id)} data-testid={`tab-${tab.id}`}>
              {tab.label}
            </button>
          ))}
        </div>

        {/* Table */}
        <div className="card">
          <div className="data-table-wrapper">
            {loading ? (
              <div className="loading"><div className="loading-spinner"></div></div>
            ) : ventas.length === 0 ? (
              <div className="empty-state">
                <ShoppingCart className="empty-state-icon" />
                <div className="empty-state-title">{search ? 'No se encontraron resultados' : 'No hay ventas'}</div>
                <div className="empty-state-description">
                  {search ? `No se encontraron ventas para "${search}".` : 'No hay ventas POS en el rango de fechas seleccionado'}
                </div>
              </div>
            ) : (
              <>
                <table className="data-table" data-testid="ventas-table" style={{ fontSize: '0.8125rem' }}>
                  <thead>
                    <tr>
                      <th style={{ padding: '6px 8px' }}>Fecha</th>
                      <th style={{ padding: '6px 8px' }}>Comp.</th>
                      <th style={{ padding: '6px 8px' }}>N° Comp.</th>
                      <th style={{ padding: '6px 8px' }}>Cliente</th>
                      <th style={{ padding: '6px 8px' }}>Vendedor</th>
                      <th style={{ padding: '6px 8px' }}>Tienda</th>
                      <th style={{ padding: '6px 8px' }}>Empresa</th>
                      <th style={{ padding: '6px 8px' }}>Pagos</th>
                      <th className="text-right" style={{ padding: '6px 8px' }}>Cant.</th>
                      <th className="text-right" style={{ padding: '6px 8px' }}>Total</th>
                      <th style={{ padding: '6px 8px' }}>Estado</th>
                      <th style={{ padding: '6px 8px' }}>Pagos Asoc.</th>
                      <th className="text-center" style={{ padding: '6px 8px' }}>Acc.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ventas.map((venta) => (
                      <tr key={venta.id} data-testid={`venta-row-${venta.id}`}>
                        <td style={{ padding: '5px 8px', whiteSpace: 'nowrap' }}>{formatDateTime(venta.date_order)}</td>
                        <td style={{ padding: '5px 8px' }}>{venta.tipo_comp || '-'}</td>
                        <td style={{ padding: '5px 8px', fontFamily: 'monospace', fontSize: '0.75rem' }}>{venta.num_comp || '-'}</td>
                        <td style={{ padding: '5px 8px' }}>{venta.partner_name || '-'}</td>
                        <td style={{ padding: '5px 8px' }}>{venta.vendedor_name || '-'}</td>
                        <td style={{ padding: '5px 8px', fontWeight: 500 }}>{venta.tienda_name || '-'}</td>
                        <td style={{ padding: '5px 8px', fontSize: '0.75rem' }}>{venta.company_name || '-'}</td>
                        <td style={{ padding: '5px 8px', fontSize: '0.75rem', color: 'var(--muted)' }}>{venta.x_pagos || '-'}</td>
                        <td className="text-right" style={{ padding: '5px 8px' }}>{venta.quantity_total || '-'}</td>
                        <td className="text-right" style={{ padding: '5px 8px', fontWeight: 600 }}>{formatCurrency(venta.amount_total)}</td>
                        <td style={{ padding: '5px 8px' }}>
                          <span style={{
                            padding: '2px 8px',
                            borderRadius: '9999px',
                            fontSize: '0.7rem',
                            fontWeight: 500,
                            backgroundColor: venta.estado_local === 'confirmada' ? '#d1fae5' : venta.estado_local === 'credito' ? '#dbeafe' : venta.estado_local === 'descartada' ? '#fee2e2' : '#fef3c7',
                            color: venta.estado_local === 'confirmada' ? '#065f46' : venta.estado_local === 'credito' ? '#1e40af' : venta.estado_local === 'descartada' ? '#991b1b' : '#92400e'
                          }}>
                            {venta.estado_local}
                          </span>
                        </td>
                        <td style={{ padding: '5px 8px' }}>
                          {venta.estado_local === 'pendiente' ? (
                            <button className="btn btn-sm btn-primary" onClick={() => openPagosModal(venta)} title="Asignar pagos" style={{ fontSize: '0.7rem', padding: '2px 6px' }}>
                              <Plus size={11} /> S/ {venta.pagos_asignados ? parseFloat(venta.pagos_asignados).toFixed(2) : '0.00'}
                            </button>
                          ) : venta.estado_local === 'credito' ? (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                              <span style={{ color: venta.pagos_cxc > 0 ? '#059669' : '#9ca3af', fontSize: '0.8rem', fontWeight: 600 }}>
                                S/ {venta.pagos_cxc ? parseFloat(venta.pagos_cxc).toFixed(2) : '0.00'}
                              </span>
                              <button className="btn btn-sm btn-outline" onClick={() => verPagosCredito(venta)} title="Ver pagos de credito" data-testid={`ver-pagos-credito-${venta.id}`} style={{ padding: '2px', fontSize: '0.65rem' }}>
                                <Eye size={11} />
                              </button>
                            </div>
                          ) : (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                              <span style={{ color: '#059669', fontSize: '0.8rem', fontWeight: 600 }}>
                                S/ {venta.pagos_oficiales ? parseFloat(venta.pagos_oficiales).toFixed(2) : '0.00'}
                              </span>
                              {venta.num_pagos_oficiales > 0 && (
                                <button className="btn btn-sm btn-outline" onClick={() => verPagosConfirmada(venta)} title="Ver pagos" style={{ padding: '2px', fontSize: '0.65rem' }}>
                                  <Eye size={11} />
                                </button>
                              )}
                            </div>
                          )}
                        </td>
                        <td className="text-center" style={{ padding: '5px 8px' }}>
                          <div style={{ display: 'flex', gap: '2px', justifyContent: 'center' }}>
                            <button className="btn btn-outline btn-sm btn-icon" onClick={() => verLineasProductos(venta)} title="Ver productos" style={{ fontSize: '0.65rem', padding: '2px 4px' }} data-testid={`ver-lineas-${venta.id}`}>
                              <ShoppingCart size={13} />
                            </button>
                            {venta.estado_local === 'confirmada' && (
                              <button className="btn btn-outline btn-sm btn-icon" onClick={() => handleDesconfirmar(venta)} title="Desconfirmar" data-testid={`desconfirmar-${venta.id}`} style={{ color: 'var(--danger-text)', padding: '2px 4px' }}>
                                <RotateCcw size={13} />
                              </button>
                            )}
                            {venta.estado_local === 'pendiente' && (
                              <>
                                <button className="btn btn-outline btn-sm btn-icon" onClick={() => handleConfirmar(venta.id)} title="Confirmar" data-testid={`confirmar-${venta.id}`} style={{ padding: '2px 4px' }}>
                                  <Check size={13} />
                                </button>
                                <button className="btn btn-outline btn-sm btn-icon" onClick={() => handleCredito(venta.id)} title="Credito" data-testid={`credito-${venta.id}`} style={{ padding: '2px 4px' }}>
                                  <CreditCard size={13} />
                                </button>
                                <button className="btn btn-outline btn-sm btn-icon" onClick={() => handleDescartar(venta.id)} title="Descartar" data-testid={`descartar-${venta.id}`} style={{ padding: '2px 4px' }}>
                                  <X size={13} />
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <Pagination page={page} totalPages={totalPages} total={totalRecords} pageSize={pageSize} onPageChange={setPage} />
              </>
            )}
          </div>
        </div>
      </div>

      {/* Modal Asignar Pagos */}
      {showPagosModal && ventaSeleccionada && (
        <div className="modal-overlay" onClick={closePagosModal} style={{ backgroundColor: 'rgba(0, 0, 0, 0.6)', backdropFilter: 'blur(4px)' }}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '800px', backgroundColor: 'var(--card-bg)', boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)' }}>
            <div className="modal-header" style={{ borderBottom: '2px solid #f3f4f6', paddingBottom: '1rem' }}>
              <div>
                <h2 className="modal-title" style={{ fontSize: '1.25rem', fontWeight: 600, color: '#111827' }}>Asignar Pagos</h2>
                <p style={{ fontSize: '0.875rem', color: 'var(--muted)', marginTop: '0.25rem' }}>
                  {ventaSeleccionada.name} - {ventaSeleccionada.partner_name}
                </p>
              </div>
              <button className="modal-close" onClick={closePagosModal} style={{ fontSize: '1.75rem', color: 'var(--muted)' }}>x</button>
            </div>
            <div className="modal-body" style={{ padding: '1.5rem' }}>
              {/* Info venta */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '1.5rem', padding: '1.25rem', background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', borderRadius: '12px', color: 'white' }}>
                <div>
                  <div style={{ fontSize: '0.7rem', opacity: 0.9, marginBottom: '0.25rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Cliente</div>
                  <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>{ventaSeleccionada.partner_name}</div>
                </div>
                <div>
                  <div style={{ fontSize: '0.7rem', opacity: 0.9, marginBottom: '0.25rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Total Venta</div>
                  <div style={{ fontWeight: 700, fontSize: '1.25rem' }}>{formatCurrency(ventaSeleccionada.amount_total)}</div>
                </div>
                <div>
                  <div style={{ fontSize: '0.7rem', opacity: 0.9, marginBottom: '0.25rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Pagado</div>
                  <div style={{ fontWeight: 700, fontSize: '1.25rem', color: '#a7f3d0' }}>
                    {formatCurrency(pagos.reduce((sum, p) => sum + parseFloat(p.monto || 0), 0))}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '0.7rem', opacity: 0.9, marginBottom: '0.25rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Faltante</div>
                  <div style={{ fontWeight: 700, fontSize: '1.25rem', color: '#fca5a5' }}>
                    {formatCurrency(ventaSeleccionada.amount_total - pagos.reduce((sum, p) => sum + parseFloat(p.monto || 0), 0))}
                  </div>
                </div>
              </div>

              {/* Pagos existentes */}
              {pagos.length > 0 && (
                <div style={{ marginBottom: '1.5rem' }}>
                  <h4 style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.75rem', color: '#374151' }}>Pagos Registrados</h4>
                  <div style={{ border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden', backgroundColor: '#fafbfc' }}>
                    {pagos.map(pago => (
                      <div key={pago.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.875rem 1rem', borderBottom: '1px solid var(--table-row-border)', backgroundColor: 'var(--card-bg)' }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 600, color: '#111827', marginBottom: '0.125rem' }}>{pago.forma_pago} - {formatCurrency(pago.monto)}</div>
                          {pago.referencia && <div style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>Ref: {pago.referencia}</div>}
                        </div>
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          <button className="btn btn-sm" onClick={() => handleEditPago(pago)} style={{ color: '#2563eb', padding: '0.375rem', backgroundColor: 'var(--info-bg)', border: '1px solid var(--info-border)', borderRadius: '6px' }} title="Editar"><Edit size={14} /></button>
                          <button className="btn btn-sm" onClick={() => handleDeletePago(pago.id)} style={{ color: 'var(--danger-text)', padding: '0.375rem', backgroundColor: 'var(--danger-bg)', border: '1px solid var(--danger-border)', borderRadius: '6px' }} title="Eliminar"><Trash2 size={14} /></button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Nuevo pago form */}
              <div style={{ border: '2px solid var(--border)', borderRadius: '12px', padding: '1.25rem', background: 'var(--card-bg)' }}>
                <h4 style={{ fontSize: '0.9375rem', fontWeight: 600, marginBottom: '1.25rem', color: '#111827', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Plus size={18} style={{ color: '#10b981' }} /> Agregar Nuevo Pago
                </h4>
                <div style={{ marginBottom: '1rem' }}>
                  <label className="form-label" style={{ fontWeight: 600, marginBottom: '0.5rem', display: 'block', color: '#111827', fontSize: '0.9375rem' }}>
                    Cuenta / Caja <span style={{ color: 'var(--danger-text)' }}>*</span>
                  </label>
                  <select className="form-select" value={nuevoPago.cuenta_financiera_id} onChange={(e) => setNuevoPago({...nuevoPago, cuenta_financiera_id: e.target.value})} style={{ fontSize: '0.9375rem', padding: '0.75rem', borderRadius: '8px', border: '2px solid #d1d5db', fontWeight: 500 }}>
                    <option value="">Seleccione una cuenta...</option>
                    {cuentasFinancieras.map(cuenta => (
                      <option key={cuenta.id} value={cuenta.id}>{cuenta.tipo === 'banco' ? 'Banco' : 'Caja'} {cuenta.nombre} {cuenta.banco ? `- ${cuenta.banco}` : ''}</option>
                    ))}
                  </select>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
                  <div>
                    <label className="form-label" style={{ fontWeight: 500, marginBottom: '0.5rem', display: 'block' }}>Forma de Pago <span style={{ color: 'var(--danger-text)' }}>*</span></label>
                    <select className="form-select" value={nuevoPago.forma_pago} onChange={(e) => setNuevoPago({...nuevoPago, forma_pago: e.target.value})} style={{ fontSize: '0.9375rem', padding: '0.625rem 0.75rem', borderRadius: '8px', border: '1.5px solid #d1d5db' }}>
                      <option value="Efectivo">Efectivo</option>
                      <option value="Yape">Yape</option>
                      <option value="Plin">Plin</option>
                      <option value="Transferencia">Transferencia</option>
                      <option value="Tarjeta Debito">Tarjeta Debito</option>
                      <option value="Tarjeta Credito">Tarjeta Credito</option>
                    </select>
                  </div>
                  <div>
                    <label className="form-label" style={{ fontWeight: 500, marginBottom: '0.5rem', display: 'block' }}>Monto <span style={{ color: 'var(--danger-text)' }}>*</span></label>
                    <input type="number" className="form-input" placeholder="0.00" step="0.01" value={nuevoPago.monto} onChange={(e) => setNuevoPago({...nuevoPago, monto: e.target.value})} style={{ fontSize: '0.9375rem', padding: '0.625rem 0.75rem', borderRadius: '8px', border: '1.5px solid #d1d5db', fontWeight: 600 }} />
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
                  <div>
                    <label className="form-label" style={{ fontWeight: 500, marginBottom: '0.5rem', display: 'block' }}>Referencia</label>
                    <input type="text" className="form-input" placeholder="Auto-generado..." value={nuevoPago.referencia} onChange={(e) => setNuevoPago({...nuevoPago, referencia: e.target.value})} style={{ fontSize: '0.875rem', padding: '0.625rem 0.75rem', borderRadius: '8px', border: '1.5px solid #d1d5db' }} />
                  </div>
                  <div>
                    <label className="form-label" style={{ fontWeight: 500, marginBottom: '0.5rem', display: 'block' }}>Fecha</label>
                    <input type="date" className="form-input" value={nuevoPago.fecha_pago} onChange={(e) => setNuevoPago({...nuevoPago, fecha_pago: e.target.value})} style={{ fontSize: '0.875rem', padding: '0.625rem 0.75rem', borderRadius: '8px', border: '1.5px solid #d1d5db' }} />
                  </div>
                </div>
                <div style={{ marginBottom: '1.25rem' }}>
                  <label className="form-label" style={{ fontWeight: 500, marginBottom: '0.5rem', display: 'block' }}>Observaciones</label>
                  <textarea className="form-input" rows="2" placeholder="Opcional..." value={nuevoPago.observaciones} onChange={(e) => setNuevoPago({...nuevoPago, observaciones: e.target.value})} style={{ fontSize: '0.875rem', padding: '0.625rem 0.75rem', borderRadius: '8px', border: '1.5px solid #d1d5db', resize: 'vertical' }} />
                </div>
                <button className="btn btn-primary" onClick={handleAddPago} style={{ width: '100%', padding: '0.75rem', fontSize: '0.9375rem', fontWeight: 600, borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
                  <Plus size={18} /> Agregar Pago
                </button>
              </div>
              <div style={{ marginTop: '1.25rem', padding: '1rem', background: 'var(--info-bg)', border: '1.5px solid #bfdbfe', borderRadius: '8px', fontSize: '0.8125rem', color: 'var(--info-text)' }}>
                <strong>Nota:</strong> Cuando la suma de pagos sea igual al total, la venta se confirmara automaticamente.
              </div>
            </div>
            <div className="modal-footer" style={{ borderTop: '2px solid #f3f4f6', paddingTop: '1rem', display: 'flex', justifyContent: 'flex-end' }}>
              <button className="btn btn-outline" onClick={closePagosModal} style={{ padding: '0.625rem 1.25rem', borderRadius: '8px' }}>Cerrar</button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Ver Pagos Oficiales */}
      {showPagosOficialesModal && ventaSeleccionada && (
        <div className="modal-overlay" onClick={closePagosOficialesModal} style={{ backgroundColor: 'rgba(0, 0, 0, 0.6)', backdropFilter: 'blur(4px)' }}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '900px', backgroundColor: 'var(--card-bg)' }}>
            <div className="modal-header" style={{ borderBottom: '2px solid #f3f4f6', paddingBottom: '1rem' }}>
              <div>
                <h2 className="modal-title" style={{ fontSize: '1.25rem', fontWeight: 600, color: '#111827' }}>Pagos Registrados</h2>
                <p style={{ fontSize: '0.875rem', color: 'var(--muted)', marginTop: '0.25rem' }}>{ventaSeleccionada.name} - {ventaSeleccionada.partner_name}</p>
              </div>
              <button className="modal-close" onClick={closePagosOficialesModal} style={{ fontSize: '1.75rem', color: 'var(--muted)' }}>x</button>
            </div>
            <div className="modal-body" style={{ padding: '1.5rem' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '1.5rem', padding: '1.25rem', background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', borderRadius: '12px', color: 'white' }}>
                <div><div style={{ fontSize: '0.7rem', opacity: 0.9, textTransform: 'uppercase' }}>Cliente</div><div style={{ fontWeight: 600 }}>{ventaSeleccionada.partner_name}</div></div>
                <div><div style={{ fontSize: '0.7rem', opacity: 0.9, textTransform: 'uppercase' }}>Total Venta</div><div style={{ fontWeight: 700, fontSize: '1.25rem' }}>{formatCurrency(ventaSeleccionada.amount_total)}</div></div>
                <div><div style={{ fontSize: '0.7rem', opacity: 0.9, textTransform: 'uppercase' }}>Total Pagado</div><div style={{ fontWeight: 700, fontSize: '1.25rem', color: '#d1fae5' }}>{formatCurrency(ventaSeleccionada.pagos_oficiales || 0)}</div></div>
              </div>
              {loadingPagosOficiales ? (
                <div style={{ textAlign: 'center', padding: '2rem' }}><div className="loading loading-spinner loading-lg"></div><p style={{ marginTop: '1rem', color: 'var(--muted)' }}>Cargando pagos...</p></div>
              ) : pagosOficiales.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '3rem', backgroundColor: 'var(--card-bg-hover)', borderRadius: '12px' }}><p style={{ color: 'var(--muted)' }}>No hay pagos registrados</p></div>
              ) : (
                <div style={{ border: '1px solid var(--border)', borderRadius: '12px', overflow: 'hidden' }}>
                  <table className="table table-zebra" style={{ marginBottom: 0 }}>
                    <thead style={{ backgroundColor: 'var(--card-bg-hover)' }}>
                      <tr>
                        <th style={{ fontWeight: 600 }}>Numero</th>
                        <th style={{ fontWeight: 600 }}>Fecha</th>
                        <th style={{ fontWeight: 600 }}>Forma de Pago</th>
                        <th style={{ fontWeight: 600 }}>Cuenta</th>
                        <th style={{ fontWeight: 600 }}>Referencia</th>
                        <th className="text-right" style={{ fontWeight: 600 }}>Monto</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pagosOficiales.map((pago) => (
                        <tr key={pago.id}>
                          <td style={{ fontWeight: 500 }}>{pago.numero}</td>
                          <td>{new Date(pago.fecha).toLocaleDateString('es-PE')}</td>
                          <td><span style={{ padding: '0.25rem 0.75rem', backgroundColor: '#dbeafe', color: 'var(--info-text)', borderRadius: '9999px', fontSize: '0.75rem', fontWeight: 500 }}>{pago.forma_pago}</span></td>
                          <td style={{ fontSize: '0.875rem', color: 'var(--muted)' }}>{pago.cuenta_nombre || '-'}</td>
                          <td style={{ fontSize: '0.875rem', color: 'var(--muted)' }}>{pago.referencia || '-'}</td>
                          <td className="text-right" style={{ fontWeight: 600, color: '#059669' }}>{formatCurrency(pago.monto)}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot style={{ backgroundColor: 'var(--card-bg-hover)', borderTop: '2px solid var(--border)' }}>
                      <tr>
                        <td colSpan="5" style={{ fontWeight: 600, fontSize: '0.9375rem' }}>TOTAL</td>
                        <td className="text-right" style={{ fontWeight: 700, fontSize: '1.125rem', color: '#059669' }}>{formatCurrency(pagosOficiales.reduce((sum, p) => sum + parseFloat(p.monto || 0), 0))}</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              )}
            </div>
            <div className="modal-footer" style={{ borderTop: '2px solid #f3f4f6', paddingTop: '1rem', display: 'flex', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', gap: '0.75rem' }}>
                <button className="btn btn-outline" onClick={closePagosOficialesModal} style={{ padding: '0.625rem 1.25rem', borderRadius: '8px' }}>Cerrar</button>
                {pagosOficiales.length > 0 && (
                  <button className="btn btn-error btn-outline" onClick={() => handleDesconfirmar()} style={{ padding: '0.625rem 1.25rem', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <RotateCcw size={16} /> Desconfirmar Venta
                  </button>
                )}
              </div>
              {pagosOficiales.length > 0 && (
                <button className="btn btn-primary" onClick={exportarPagosOficiales} style={{ padding: '0.625rem 1.25rem', borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Download size={16} /> Exportar a Excel
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Modal Ver Lineas de Productos */}
      {showLineasModal && ventaSeleccionada && (
        <div className="modal-overlay" onClick={closeLineasModal} style={{ backgroundColor: 'rgba(0, 0, 0, 0.6)', backdropFilter: 'blur(4px)' }}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '1100px', backgroundColor: 'var(--card-bg)' }}>
            <div className="modal-header" style={{ borderBottom: '2px solid #f3f4f6' }}>
              <div>
                <h2 className="modal-title" style={{ fontSize: '1.25rem', fontWeight: 600 }}>Detalle de Venta POS</h2>
                <p style={{ fontSize: '0.875rem', color: 'var(--muted)', marginTop: '0.25rem' }}>
                  {ventaSeleccionada.name} - {ventaSeleccionada.partner_name} - Total: {formatCurrency(ventaSeleccionada.amount_total)}
                </p>
              </div>
              <button className="modal-close" onClick={closeLineasModal}>x</button>
            </div>
            <div className="modal-body" style={{ padding: '1.5rem' }}>
              {loadingLineas ? (
                <div style={{ textAlign: 'center', padding: '2rem' }}><div className="loading loading-spinner loading-lg"></div><p style={{ marginTop: '1rem', color: 'var(--muted)' }}>Cargando productos...</p></div>
              ) : lineasProductos.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '3rem', backgroundColor: 'var(--card-bg-hover)', borderRadius: '12px' }}>
                  <p style={{ color: 'var(--muted)' }}>No hay lineas de productos para esta venta.</p>
                  <p style={{ color: 'var(--muted)', fontSize: '0.8rem', marginTop: '0.5rem' }}>Sincronice desde el boton "Sincronizar" para traer el detalle.</p>
                </div>
              ) : (
                <>
                  <div style={{ border: '1px solid var(--border)', borderRadius: '12px', overflow: 'hidden', marginBottom: '1.5rem' }}>
                    <table className="table table-zebra" style={{ marginBottom: 0, fontSize: '0.8rem' }} data-testid="pos-detail-table">
                      <thead style={{ backgroundColor: 'var(--card-bg-hover)' }}>
                        <tr>
                          <th style={{ padding: '6px 10px' }}>Producto</th>
                          <th className="text-right" style={{ width: '40px', padding: '6px 10px' }}>Cant.</th>
                          <th className="text-right" style={{ width: '80px', padding: '6px 10px' }}>P. Unit</th>
                          <th className="text-right" style={{ width: '85px', padding: '6px 10px' }}>Subtotal</th>
                          <th style={{ padding: '6px 10px' }}>Marca</th>
                          <th style={{ padding: '6px 10px' }}>Linea de Negocio</th>
                        </tr>
                      </thead>
                      <tbody>
                        {lineasProductos.map((linea, index) => (
                          <tr key={index} data-testid={`pos-line-${index}`}>
                            <td style={{ fontWeight: 500, padding: '5px 10px' }}>{linea.product_name}</td>
                            <td className="text-right" style={{ padding: '5px 10px' }}>{linea.qty}</td>
                            <td className="text-right" style={{ padding: '5px 10px' }}>{formatCurrency(linea.price_unit)}</td>
                            <td className="text-right" style={{ fontWeight: 600, padding: '5px 10px' }}>{formatCurrency(linea.price_subtotal_incl || linea.price_subtotal)}</td>
                            <td style={{ padding: '5px 10px', color: '#4b5563' }}>{linea.marca || '-'}</td>
                            <td style={{ padding: '5px 10px' }}>
                              {linea.linea_negocio_nombre ? (
                                <span style={{
                                  fontSize: '0.78rem', fontWeight: 500,
                                  color: linea.linea_negocio_nombre === 'SIN CLASIFICAR' ? '#92400e' : '#065f46',
                                }}>{linea.linea_negocio_nombre}</span>
                              ) : '-'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot style={{ backgroundColor: 'var(--card-bg-hover)', borderTop: '2px solid var(--border)' }}>
                        <tr>
                          <td colSpan="3" style={{ fontWeight: 600, padding: '6px 10px' }}>TOTAL</td>
                          <td className="text-right" style={{ fontWeight: 700, fontSize: '0.9rem', color: '#059669', padding: '6px 10px' }}>
                            {formatCurrency(lineasProductos.reduce((sum, l) => sum + parseFloat(l.price_subtotal_incl || l.price_subtotal || 0), 0))}
                          </td>
                          <td colSpan="2"></td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                  {/* Resumen por Linea de Negocio (prioritario) y por Marca */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem' }}>
                    <div style={{ border: '2px solid #059669', borderRadius: '12px', padding: '1rem', backgroundColor: 'var(--success-bg)' }} data-testid="resumen-linea-negocio">
                      <h4 style={{ fontSize: '0.9375rem', fontWeight: 700, marginBottom: '0.75rem', color: 'var(--success-text)' }}>Total por Linea de Negocio</h4>
                      {(() => {
                        const porLN = {};
                        lineasProductos.forEach(l => {
                          const ln = l.linea_negocio_nombre || 'SIN CLASIFICAR';
                          porLN[ln] = (porLN[ln] || 0) + parseFloat(l.price_subtotal_incl || l.price_subtotal || 0);
                        });
                        const total = Object.values(porLN).reduce((s, v) => s + v, 0);
                        return Object.entries(porLN).sort((a, b) => b[1] - a[1]).map(([ln, sum]) => (
                          <div key={ln} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem 0', borderBottom: '1px solid #d1fae5' }}>
                            <span style={{ fontSize: '0.875rem', fontWeight: 500 }}>{ln}</span>
                            <div style={{ textAlign: 'right' }}>
                              <span style={{ fontWeight: 700, color: '#059669' }}>{formatCurrency(sum)}</span>
                              <span style={{ fontSize: '0.75rem', color: 'var(--muted)', marginLeft: '0.5rem' }}>({total > 0 ? ((sum / total) * 100).toFixed(1) : 0}%)</span>
                            </div>
                          </div>
                        ));
                      })()}
                    </div>
                    <div style={{ border: '1px solid var(--border)', borderRadius: '12px', padding: '1rem', backgroundColor: 'var(--card-bg-hover)' }} data-testid="resumen-marca">
                      <h4 style={{ fontSize: '0.9375rem', fontWeight: 600, marginBottom: '0.75rem' }}>Total por Marca</h4>
                      {(() => {
                        const porMarca = {};
                        lineasProductos.forEach(l => { const m = l.marca || 'Sin Marca'; porMarca[m] = (porMarca[m] || 0) + parseFloat(l.price_subtotal_incl || l.price_subtotal || 0); });
                        return Object.entries(porMarca).sort((a, b) => b[1] - a[1]).map(([marca, total]) => (
                          <div key={marca} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0', borderBottom: '1px solid #e5e7eb' }}>
                            <span style={{ fontSize: '0.875rem' }}>{marca}</span>
                            <span style={{ fontWeight: 600, color: '#059669' }}>{formatCurrency(total)}</span>
                          </div>
                        ));
                      })()}
                    </div>
                  </div>
                </>
              )}
            </div>
            <div className="modal-footer" style={{ borderTop: '2px solid #f3f4f6' }}>
              <button className="btn btn-outline" onClick={closeLineasModal}>Cerrar</button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Ver Pagos de Credito (CxC Abonos) */}
      {showPagosCreditoModal && ventaSeleccionada && (
        <div className="modal-overlay" onClick={closePagosCreditoModal} style={{ backgroundColor: 'rgba(0, 0, 0, 0.6)', backdropFilter: 'blur(4px)' }}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '800px', backgroundColor: 'var(--card-bg)' }}>
            <div className="modal-header" style={{ borderBottom: '2px solid #f3f4f6', paddingBottom: '1rem' }}>
              <div>
                <h2 className="modal-title" style={{ fontSize: '1.25rem', fontWeight: 600, color: '#111827' }}>Pagos de Credito</h2>
                <p style={{ fontSize: '0.875rem', color: 'var(--muted)', marginTop: '0.25rem' }}>{ventaSeleccionada.name} - {ventaSeleccionada.partner_name}</p>
              </div>
              <button className="modal-close" onClick={closePagosCreditoModal} style={{ fontSize: '1.75rem', color: 'var(--muted)' }}>x</button>
            </div>
            <div className="modal-body" style={{ padding: '1.5rem' }}>
              {/* CxC Info */}
              {pagosCreditoData.cxc && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '1.5rem', padding: '1.25rem', background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)', borderRadius: '12px', color: 'white' }}>
                  <div>
                    <div style={{ fontSize: '0.7rem', opacity: 0.9, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Monto Original</div>
                    <div style={{ fontWeight: 700, fontSize: '1.125rem' }}>{formatCurrency(pagosCreditoData.cxc.monto_original)}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.7rem', opacity: 0.9, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Total Cobrado</div>
                    <div style={{ fontWeight: 700, fontSize: '1.125rem', color: '#a7f3d0' }}>
                      {formatCurrency(pagosCreditoData.abonos.reduce((sum, a) => sum + parseFloat(a.monto || 0), 0))}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.7rem', opacity: 0.9, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Saldo Pendiente</div>
                    <div style={{ fontWeight: 700, fontSize: '1.125rem', color: '#fca5a5' }}>{formatCurrency(pagosCreditoData.cxc.saldo_pendiente)}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.7rem', opacity: 0.9, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Estado CxC</div>
                    <div style={{ fontWeight: 600, fontSize: '0.9rem', textTransform: 'capitalize' }}>{pagosCreditoData.cxc.estado}</div>
                    {pagosCreditoData.cxc.fecha_vencimiento && (
                      <div style={{ fontSize: '0.7rem', opacity: 0.8, marginTop: '0.125rem' }}>Vence: {new Date(pagosCreditoData.cxc.fecha_vencimiento).toLocaleDateString('es-PE')}</div>
                    )}
                  </div>
                </div>
              )}
              {loadingPagosCredito ? (
                <div style={{ textAlign: 'center', padding: '2rem' }}><div className="loading loading-spinner loading-lg"></div><p style={{ marginTop: '1rem', color: 'var(--muted)' }}>Cargando pagos...</p></div>
              ) : pagosCreditoData.abonos.length === 0 ? (
                <div data-testid="no-pagos-credito" style={{ textAlign: 'center', padding: '3rem', backgroundColor: 'var(--card-bg-hover)', borderRadius: '12px' }}>
                  <CreditCard size={40} style={{ color: '#d1d5db', margin: '0 auto 1rem' }} />
                  <p style={{ color: 'var(--muted)', fontWeight: 500 }}>No hay pagos registrados para esta venta a credito</p>
                  <p style={{ color: 'var(--muted)', fontSize: '0.8rem', marginTop: '0.5rem' }}>Los pagos se registran desde el modulo de Cuentas por Cobrar (CxC)</p>
                </div>
              ) : (
                <div style={{ border: '1px solid var(--border)', borderRadius: '12px', overflow: 'hidden' }}>
                  <table className="table table-zebra" style={{ marginBottom: 0 }} data-testid="pagos-credito-table">
                    <thead style={{ backgroundColor: 'var(--card-bg-hover)' }}>
                      <tr>
                        <th style={{ fontWeight: 600 }}>Fecha</th>
                        <th style={{ fontWeight: 600 }}>Forma de Pago</th>
                        <th style={{ fontWeight: 600 }}>Cuenta</th>
                        <th style={{ fontWeight: 600 }}>Referencia</th>
                        <th style={{ fontWeight: 600 }}>Notas</th>
                        <th className="text-right" style={{ fontWeight: 600 }}>Monto</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pagosCreditoData.abonos.map((abono) => (
                        <tr key={abono.id} data-testid={`abono-row-${abono.id}`}>
                          <td>{abono.fecha ? new Date(abono.fecha).toLocaleDateString('es-PE') : '-'}</td>
                          <td><span style={{ padding: '0.25rem 0.75rem', backgroundColor: '#dbeafe', color: 'var(--info-text)', borderRadius: '9999px', fontSize: '0.75rem', fontWeight: 500 }}>{abono.forma_pago || '-'}</span></td>
                          <td style={{ fontSize: '0.875rem', color: 'var(--muted)' }}>{abono.cuenta_nombre || '-'}</td>
                          <td style={{ fontSize: '0.875rem', color: 'var(--muted)' }}>{abono.referencia || '-'}</td>
                          <td style={{ fontSize: '0.8rem', color: 'var(--muted)', maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{abono.notas || '-'}</td>
                          <td className="text-right" style={{ fontWeight: 600, color: '#059669' }}>{formatCurrency(abono.monto)}</td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot style={{ backgroundColor: 'var(--card-bg-hover)', borderTop: '2px solid var(--border)' }}>
                      <tr>
                        <td colSpan="5" style={{ fontWeight: 600, fontSize: '0.9375rem' }}>TOTAL COBRADO</td>
                        <td className="text-right" style={{ fontWeight: 700, fontSize: '1.125rem', color: '#059669' }}>
                          {formatCurrency(pagosCreditoData.abonos.reduce((sum, a) => sum + parseFloat(a.monto || 0), 0))}
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              )}
            </div>
            <div className="modal-footer" style={{ borderTop: '2px solid #f3f4f6', paddingTop: '1rem', display: 'flex', justifyContent: 'flex-end' }}>
              <button className="btn btn-outline" onClick={closePagosCreditoModal} style={{ padding: '0.625rem 1.25rem', borderRadius: '8px' }}>Cerrar</button>
            </div>
          </div>
        </div>
      )}


      {/* Modal Editar Pago */}
      {showEditPagoModal && pagoEditando && (
        <div className="modal-overlay" onClick={() => setShowEditPagoModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '500px' }}>
            <div className="modal-header">
              <h2 className="modal-title">Editar Pago</h2>
              <button className="modal-close" onClick={() => setShowEditPagoModal(false)}>x</button>
            </div>
            <div className="modal-body">
              <div style={{ marginBottom: '1rem' }}>
                <label className="form-label">Cuenta / Caja</label>
                <select className="form-select" value={pagoEditando.cuenta_financiera_id || ''} onChange={(e) => setPagoEditando({...pagoEditando, cuenta_financiera_id: parseInt(e.target.value)})}>
                  <option value="">Seleccione una cuenta...</option>
                  {cuentasFinancieras.map((c) => (<option key={c.id} value={c.id}>{c.nombre}</option>))}
                </select>
              </div>
              <div style={{ marginBottom: '1rem' }}>
                <label className="form-label">Forma de Pago</label>
                <select className="form-select" value={pagoEditando.forma_pago || 'Efectivo'} onChange={(e) => setPagoEditando({...pagoEditando, forma_pago: e.target.value})}>
                  <option value="Efectivo">Efectivo</option>
                  <option value="Transferencia">Transferencia</option>
                  <option value="Tarjeta">Tarjeta</option>
                  <option value="Yape">Yape</option>
                  <option value="Plin">Plin</option>
                </select>
              </div>
              <div style={{ marginBottom: '1rem' }}>
                <label className="form-label">Monto</label>
                <input type="number" className="form-input" step="0.01" value={pagoEditando.monto || ''} onChange={(e) => setPagoEditando({...pagoEditando, monto: parseFloat(e.target.value)})} />
              </div>
              <div style={{ marginBottom: '1rem' }}>
                <label className="form-label">Referencia</label>
                <input type="text" className="form-input" value={pagoEditando.referencia || ''} onChange={(e) => setPagoEditando({...pagoEditando, referencia: e.target.value})} />
              </div>
              <div style={{ marginBottom: '1rem' }}>
                <label className="form-label">Fecha</label>
                <input type="date" className="form-input" value={pagoEditando.fecha_pago || ''} onChange={(e) => setPagoEditando({...pagoEditando, fecha_pago: e.target.value})} />
              </div>
              <div style={{ marginBottom: '1rem' }}>
                <label className="form-label">Observaciones</label>
                <textarea className="form-input" rows="2" value={pagoEditando.observaciones || ''} onChange={(e) => setPagoEditando({...pagoEditando, observaciones: e.target.value})} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setShowEditPagoModal(false)}>Cancelar</button>
              <button className="btn btn-primary" onClick={handleUpdatePago}>Guardar Cambios</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default VentasPOS;
