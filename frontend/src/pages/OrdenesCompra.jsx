import React, { useState, useEffect, useRef } from 'react';
import { Plus, FileText, Trash2, Eye, X, FileCheck, ShoppingCart, ArrowLeft, Printer, Edit2, Check, Search, Download, ChevronDown } from 'lucide-react';
import { toast } from 'sonner';
import { 
  getOrdenesCompra, 
  createOrdenCompra,
  updateOrdenCompra,
  deleteOrdenCompra,
  generarFacturaDesdeOC,
  getProveedores, 
  getMonedas,
  getArticulosOC,
  getEmpresas,
  createTercero
} from '../services/api';
import { useEmpresa } from '../context/EmpresaContext';
import SearchableSelect from '../components/SearchableSelect';

const formatCurrency = (value, symbol = 'S/') => {
  const num = parseFloat(value) || 0;
  return `${symbol} ${num.toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const formatDate = (dateStr) => {
  if (!dateStr) return '-';
  const date = new Date(dateStr + 'T00:00:00');
  return date.toLocaleDateString('es-PE', { day: '2-digit', month: '2-digit', year: 'numeric' });
};

const estadoBadge = (estado) => {
  const badges = {
    borrador: 'badge badge-warning',
    aprobada: 'badge badge-info',
    facturada: 'badge badge-success',
    anulada: 'badge badge-error'
  };
  return badges[estado] || 'badge badge-neutral';
};

// Helper function to extract error message from backend response
const getErrorMessage = (error, defaultMessage = 'Error en la operación') => {
  if (!error.response) return defaultMessage;
  
  const detail = error.response.data?.detail;
  
  // If detail is a string, return it
  if (typeof detail === 'string') return detail;
  
  // If detail is an array (Pydantic validation errors)
  if (Array.isArray(detail)) {
    // Extract messages from all errors
    const messages = detail.map(err => {
      if (typeof err === 'string') return err;
      if (err.msg) return `${err.loc?.join('.') || 'Campo'}: ${err.msg}`;
      return JSON.stringify(err);
    });
    return messages.join('; ');
  }
  
  // If detail is an object
  if (typeof detail === 'object') {
    return detail.message || detail.msg || JSON.stringify(detail);
  }
  
  return defaultMessage;
};

export default function OrdenesCompra() {
  const { empresaActual } = useEmpresa();

  const [ordenes, setOrdenes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [showViewModal, setShowViewModal] = useState(false);
  const [selectedOC, setSelectedOC] = useState(null);
  const [editingOC, setEditingOC] = useState(null);
  const printRef = useRef();
  
  // Master data
  const [proveedores, setProveedores] = useState([]);
  const [monedas, setMonedas] = useState([]);
  const [articulos, setArticulos] = useState([]);
  const [empresas, setEmpresas] = useState([]);
  
  // Filters
  const [filtroEstado, setFiltroEstado] = useState('');
  const [filtroProveedor, setFiltroProveedor] = useState('');
  
  // Form state
  const [formData, setFormData] = useState({
    fecha: new Date().toISOString().split('T')[0],
    proveedor_id: '',
    moneda_id: '',
    empresa_id: '',
    notas: '',
    condicion_pago: 'contado',
    dias_credito: 0,
    direccion_entrega: ''
  });
  
  // Line items
  const [lineas, setLineas] = useState([{
    articulo_id: '',
    descripcion: '',
    cantidad: 1,
    precio_unitario: 0,
    igv_aplica: true,
    codigo: '',
    unidad: 'UND'
  }]);
  
  const [igvIncluido, setIgvIncluido] = useState(true); // Por defecto IGV incluido
  
  // State for create new provider modal
  const [showProveedorModal, setShowProveedorModal] = useState(false);
  const [newProveedorData, setNewProveedorData] = useState({
    nombre: '',
    ruc: '',
    direccion: '',
    telefono: '',
    email: ''
  });
  const [creatingProveedor, setCreatingProveedor] = useState(false);
  
  // State for articulo search
  const [articuloSearchTerm, setArticuloSearchTerm] = useState({});
  const [articuloDropdownOpen, setArticuloDropdownOpen] = useState({});

  useEffect(() => {
    loadData();
  }, [filtroEstado, filtroProveedor, empresaActual]);

  const loadData = async () => {
    try {
      setLoading(true);
      const params = {};
      if (filtroEstado) params.estado = filtroEstado;
      if (filtroProveedor) params.proveedor_id = filtroProveedor;
      
      const [ordenesRes, provRes, monRes, artRes, empRes] = await Promise.all([
        getOrdenesCompra(params),
        getProveedores(),
        getMonedas(),
        getArticulosOC(),
        getEmpresas()
      ]);
      
      setOrdenes(ordenesRes.data);
      setProveedores(provRes.data);
      setMonedas(monRes.data);
      setArticulos(artRes.data);
      setEmpresas(empRes.data);
      
      if (monRes.data.length > 0 && !formData.moneda_id) {
        setFormData(prev => ({ ...prev, moneda_id: monRes.data[0].id }));
      }
      if (empRes.data.length > 0 && !formData.empresa_id) {
        setFormData(prev => ({ ...prev, empresa_id: empRes.data[0].id }));
      }
    } catch (error) {
      console.error('Error loading data:', error);
      toast.error(getErrorMessage(error, 'Error al cargar datos'));
    } finally {
      setLoading(false);
    }
  };

  const calcularTotales = () => {
    let subtotal = 0;
    let igv = 0;
    
    lineas.forEach(linea => {
      const lineaSubtotal = (parseFloat(linea.cantidad) || 0) * (parseFloat(linea.precio_unitario) || 0);
      if (igvIncluido) {
        const base = lineaSubtotal / 1.18;
        subtotal += base;
        if (linea.igv_aplica) {
          igv += lineaSubtotal - base;
        }
      } else {
        subtotal += lineaSubtotal;
        if (linea.igv_aplica) {
          igv += lineaSubtotal * 0.18;
        }
      }
    });
    
    return { subtotal, igv, total: subtotal + igv };
  };

  const resetForm = () => {
    setFormData({
      fecha: new Date().toISOString().split('T')[0],
      proveedor_id: '',
      moneda_id: monedas[0]?.id || '',
      empresa_id: empresas[0]?.id || '',
      notas: '',
      condicion_pago: 'contado',
      dias_credito: 0,
      direccion_entrega: ''
    });
    setLineas([{
      articulo_id: '',
      descripcion: '',
      cantidad: 1,
      precio_unitario: 0,
      igv_aplica: true,
      codigo: '',
      unidad: 'UND'
    }]);
    setIgvIncluido(true);
    setEditingOC(null);
  };

  const handleAddLinea = () => {
    setLineas([...lineas, {
      articulo_id: '',
      descripcion: '',
      cantidad: 1,
      precio_unitario: 0,
      igv_aplica: true,
      codigo: '',
      unidad: 'UND'
    }]);
  };

  const handleRemoveLinea = (index) => {
    if (lineas.length > 1) {
      setLineas(lineas.filter((_, i) => i !== index));
    }
  };

  const handleLineaChange = (index, field, value) => {
    setLineas(prev => prev.map((l, i) => 
      i === index ? { ...l, [field]: value } : l
    ));
  };

  const handleSelectArticulo = (index, articuloId) => {
    const articulo = articulos.find(a => String(a.id) === String(articuloId));
    if (articulo) {
      setLineas(prev => prev.map((l, i) => 
        i === index ? { 
          ...l, 
          articulo_id: articulo.id,
          descripcion: articulo.descripcion || articulo.nombre,
          codigo: articulo.codigo || '',
          unidad: articulo.unidad_medida || 'UND',
          precio_unitario: parseFloat(articulo.ultimo_precio) || 0
        } : l
      ));
      setArticuloSearchTerm(prev => ({ ...prev, [index]: '' }));
    }
  };

  // Filter articles based on search term
  const getFilteredArticulos = (index) => {
    const term = articuloSearchTerm[index] || '';
    if (!term) return articulos;
    return articulos.filter(a => 
      (a.nombre?.toLowerCase().includes(term.toLowerCase())) ||
      (a.codigo?.toLowerCase().includes(term.toLowerCase())) ||
      (a.linea_negocio_nombre?.toLowerCase().includes(term.toLowerCase()))
    );
  };

  // Handle create new provider
  const handleCreateProveedor = (searchTerm) => {
    console.log('handleCreateProveedor called with:', searchTerm);
    setNewProveedorData({
      nombre: searchTerm || '',
      ruc: '',
      direccion: '',
      telefono: '',
      email: ''
    });
    setShowProveedorModal(true);
    console.log('showProveedorModal set to true');
  };

  const handleSaveNewProveedor = async () => {
    if (!newProveedorData.nombre.trim()) {
      toast.error('El nombre del proveedor es requerido');
      return;
    }
    
    setCreatingProveedor(true);
    try {
      const payload = {
        tipo: 'proveedor',
        nombre: newProveedorData.nombre,
        ruc: newProveedorData.ruc || null,
        direccion: newProveedorData.direccion || null,
        telefono: newProveedorData.telefono || null,
        email: newProveedorData.email || null
      };
      
      const response = await createTercero(payload);
      const newProveedor = response.data;
      
      // Add to proveedores list and select it
      setProveedores(prev => [...prev, newProveedor]);
      setFormData(prev => ({ ...prev, proveedor_id: newProveedor.id }));
      
      toast.success(`Proveedor "${newProveedor.nombre}" creado exitosamente`);
      setShowProveedorModal(false);
      setNewProveedorData({ nombre: '', ruc: '', direccion: '', telefono: '', email: '' });
    } catch (error) {
      console.error('Error creating proveedor:', error);
      toast.error(getErrorMessage(error, 'Error al crear proveedor'));
    } finally {
      setCreatingProveedor(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    
    if (!formData.proveedor_id) {
      toast.error('Seleccione un proveedor');
      return;
    }
    
    if (lineas.every(l => !l.cantidad || l.cantidad <= 0)) {
      toast.error('Agregue al menos un artículo');
      return;
    }
    
    setSubmitting(true);
    try {
      const payload = {
        ...formData,
        proveedor_id: parseInt(formData.proveedor_id),
        moneda_id: parseInt(formData.moneda_id),
        igv_incluido: igvIncluido,
        lineas: lineas.filter(l => l.cantidad > 0).map(l => ({
          articulo_id: l.articulo_id || null,
          descripcion: l.descripcion || null,
          cantidad: parseFloat(l.cantidad),
          precio_unitario: parseFloat(l.precio_unitario),
          igv_aplica: l.igv_aplica
        }))
      };
      
      if (editingOC) {
        await updateOrdenCompra(editingOC.id, payload);
        toast.success('Orden de compra actualizada');
      } else {
        await createOrdenCompra(payload);
        toast.success('Orden de compra creada');
      }
      setShowModal(false);
      resetForm();
      loadData();
    } catch (error) {
      console.error('Error saving OC:', error);
      toast.error(getErrorMessage(error, 'Error al guardar orden de compra'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleGenerarFactura = async (oc) => {
    if (!window.confirm(`¿Generar factura desde la OC ${oc.numero}?`)) return;
    
    try {
      const response = await generarFacturaDesdeOC(oc.id);
      toast.success(`Factura ${response.data.numero} generada exitosamente`);
      loadData();
    } catch (error) {
      console.error('Error generating factura:', error);
      toast.error(getErrorMessage(error, 'Error al generar factura'));
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('¿Eliminar esta orden de compra?')) return;
    
    try {
      await deleteOrdenCompra(id);
      toast.success('Orden eliminada');
      loadData();
    } catch (error) {
      toast.error(getErrorMessage(error, 'Error al eliminar orden de compra'));
    }
  };

  const handleEdit = (oc) => {
    // Pre-fill form with OC data
    setFormData({
      fecha: oc.fecha?.split('T')[0] || new Date().toISOString().split('T')[0],
      proveedor_id: oc.proveedor_id || '',
      moneda_id: oc.moneda_id || '',
      empresa_id: oc.empresa_id || empresas[0]?.id || '',
      notas: oc.notas || '',
      condicion_pago: oc.condicion_pago || 'contado',
      dias_credito: oc.dias_credito || 0,
      direccion_entrega: oc.direccion_entrega || ''
    });
    
    // Set lineas
    if (oc.lineas && oc.lineas.length > 0) {
      setLineas(oc.lineas.map(l => ({
        articulo_id: l.articulo_id || '',
        descripcion: l.descripcion || '',
        cantidad: l.cantidad || 1,
        precio_unitario: l.precio_unitario || 0,
        igv_aplica: l.igv_aplica !== false,
        codigo: l.codigo || '',
        unidad: l.unidad || 'UND'
      })));
    }
    
    setEditingOC(oc);
    setShowModal(true);
  };

  const handleView = (oc) => {
    setSelectedOC(oc);
    setShowViewModal(true);
  };

  const handlePrint = () => {
    window.print();
  };

  // Generate and download PDF
  const handleDownloadPDF = (oc) => {
    const empresa = empresas.find(e => e.id === oc.empresa_id);
    const proveedor = proveedores.find(p => p.id === oc.proveedor_id);
    const moneda = monedas.find(m => m.id === oc.moneda_id);
    
    // Create PDF content
    const pdfContent = `
      <html>
      <head>
        <title>OC-${oc.numero}</title>
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
          * { box-sizing: border-box; margin: 0; padding: 0; }
          html, body { background-color: #ffffff !important; }
          body { font-family: 'Inter', sans-serif; padding: 40px; color: #1e293b; background: #ffffff; }
          .header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 2px solid #1B4D3E; }
          .company-info { }
          .company-name { font-size: 1.5rem; font-weight: 700; color: #1B4D3E; }
          .company-details { font-size: 0.875rem; color: #64748b; margin-top: 4px; }
          .doc-info { text-align: right; }
          .doc-title { font-size: 1.25rem; font-weight: 700; color: #1B4D3E; }
          .doc-number { font-family: 'JetBrains Mono', monospace; font-size: 1.125rem; font-weight: 600; margin-top: 4px; }
          .doc-date { font-size: 0.875rem; color: #64748b; margin-top: 4px; }
          .section { margin-bottom: 24px; }
          .section-title { font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; margin-bottom: 8px; }
          .info-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
          .info-item label { font-size: 0.75rem; color: #64748b; display: block; }
          .info-item p { font-size: 0.9375rem; font-weight: 500; }
          table { width: 100%; border-collapse: collapse; margin-top: 16px; }
          th { background: #f1f5f9; padding: 10px 12px; text-align: left; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em; color: #64748b; border-bottom: 2px solid #e2e8f0; }
          td { padding: 10px 12px; border-bottom: 1px solid #e2e8f0; font-size: 0.875rem; }
          .text-right { text-align: right; }
          .text-center { text-align: center; }
          .currency { font-family: 'JetBrains Mono', monospace; font-weight: 500; }
          .totals { margin-top: 24px; display: flex; justify-content: flex-end; }
          .totals-box { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px 24px; min-width: 320px; }
          .totals-row { display: flex; justify-content: space-between; padding: 6px 0; font-size: 0.9375rem; gap: 24px; }
          .totals-row.total { border-top: 2px solid #1B4D3E; margin-top: 8px; padding-top: 12px; font-weight: 700; font-size: 1.25rem; }
          .totals-row .currency { color: #1B4D3E; }
          .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; text-align: center; color: #64748b; font-size: 0.75rem; }
        </style>
      </head>
      <body>
        <div class="header">
          <div class="company-info">
            <div class="company-name">${empresa?.nombre || 'Mi Empresa S.A.C.'}</div>
            <div class="company-details">${empresa?.ruc ? 'RUC: ' + empresa.ruc : ''}</div>
          </div>
          <div class="doc-info">
            <div class="doc-title">ORDEN DE COMPRA</div>
            <div class="doc-number">${oc.numero}</div>
            <div class="doc-date">Fecha: ${formatDate(oc.fecha)}</div>
          </div>
        </div>
        
        <div class="section">
          <div class="section-title">Datos del Proveedor</div>
          <div class="info-grid">
            <div class="info-item">
              <label>Proveedor</label>
              <p>${oc.proveedor_nombre || proveedor?.nombre || '-'}</p>
            </div>
            <div class="info-item">
              <label>Condición de Pago</label>
              <p>${oc.condicion_pago || 'Contado'}${oc.dias_credito ? ` (${oc.dias_credito} días)` : ''}</p>
            </div>
            ${oc.direccion_entrega ? `
            <div class="info-item">
              <label>Dirección de Entrega</label>
              <p>${oc.direccion_entrega}</p>
            </div>` : ''}
          </div>
        </div>
        
        <div class="section">
          <div class="section-title">Detalle de Artículos</div>
          <table>
            <thead>
              <tr>
                <th style="width: 36px">#</th>
                <th>Descripción</th>
                <th class="text-center" style="width: 70px">Cant.</th>
                <th class="text-center" style="width: 55px">Und.</th>
                <th class="text-right" style="width: 130px">P. Unit.</th>
                <th class="text-right" style="width: 140px">Subtotal</th>
              </tr>
            </thead>
            <tbody>
              ${(oc.lineas || []).map((linea, i) => `
              <tr>
                <td class="text-center">${i + 1}</td>
                <td>${linea.descripcion || '-'}</td>
                <td class="text-center">${linea.cantidad}</td>
                <td class="text-center">${linea.unidad || 'UND'}</td>
                <td class="text-right currency">${formatCurrency(linea.precio_unitario, moneda?.simbolo || 'S/')}</td>
                <td class="text-right currency">${formatCurrency(linea.subtotal, moneda?.simbolo || 'S/')}</td>
              </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
        
        <div class="totals">
          <div class="totals-box">
            <div class="totals-row">
              <span>Subtotal:</span>
              <span class="currency">${formatCurrency(oc.subtotal, moneda?.simbolo || 'S/')}</span>
            </div>
            <div class="totals-row">
              <span>IGV (18%):</span>
              <span class="currency">${formatCurrency(oc.igv, moneda?.simbolo || 'S/')}</span>
            </div>
            <div class="totals-row total">
              <span>TOTAL:</span>
              <span class="currency">${formatCurrency(oc.total, moneda?.simbolo || 'S/')}</span>
            </div>
          </div>
        </div>
        
        ${oc.notas ? `
        <div class="section" style="margin-top: 24px;">
          <div class="section-title">Observaciones</div>
          <p style="font-size: 0.875rem; color: #64748b;">${oc.notas}</p>
        </div>` : ''}
        
        <div class="footer">
          <p>Documento generado el ${new Date().toLocaleDateString('es-PE')} | Finanzas 4.0</p>
        </div>
      </body>
      </html>
    `;
    
    // Open in new window and trigger print
    const printWindow = window.open('', '_blank');
    printWindow.document.write(pdfContent);
    printWindow.document.close();
    printWindow.focus();
    
    // Auto print after content loads
    printWindow.onload = () => {
      printWindow.print();
    };
  };

  const totales = calcularTotales();
  const monedaActual = monedas.find(m => m.id === parseInt(formData.moneda_id));
  const totalOrdenes = ordenes.reduce((sum, o) => sum + parseFloat(o.total || 0), 0);
  const cantidadArticulos = lineas.filter(l => l.cantidad > 0 && (l.articulo_id || l.descripcion)).length;

  return (
    <div data-testid="ordenes-compra-page" className="page-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Órdenes de Compra</h1>
          <p className="page-subtitle">Total: {formatCurrency(totalOrdenes)}</p>
        </div>
        <button 
          className="btn btn-primary"
          onClick={() => { resetForm(); setShowModal(true); }}
          data-testid="nueva-oc-btn"
        >
          <Plus size={18} />
          Nueva Orden
        </button>
      </div>

      <div className="page-content">
        {/* Filters */}
        <div className="filters-bar">
          <div className="filter-group">
            <label className="filter-label">Proveedor</label>
            <SearchableSelect
              options={[{ id: '', nombre: 'Todos' }, ...proveedores]}
              value={filtroProveedor}
              onChange={(value) => setFiltroProveedor(value || '')}
              placeholder="Todos"
              searchPlaceholder="Buscar..."
              displayKey="nombre"
              valueKey="id"
              style={{ width: '180px' }}
            />
          </div>
          <div className="filter-group">
            <label className="filter-label">Estado</label>
            <select 
              className="form-input form-select"
              value={filtroEstado}
              onChange={(e) => setFiltroEstado(e.target.value)}
              style={{ width: '140px' }}
            >
              <option value="">Todos</option>
              <option value="borrador">Borrador</option>
              <option value="aprobada">Aprobada</option>
              <option value="facturada">Facturada</option>
              <option value="anulada">Anulada</option>
            </select>
          </div>
          {(filtroEstado || filtroProveedor) && (
            <button 
              className="btn btn-ghost btn-sm"
              onClick={() => { setFiltroEstado(''); setFiltroProveedor(''); }}
            >
              <X size={16} />
            </button>
          )}
        </div>

        {/* Table */}
        <div className="card">
          <div className="data-table-wrapper">
            {loading ? (
              <div className="loading">
                <div className="loading-spinner"></div>
              </div>
            ) : ordenes.length === 0 ? (
              <div className="empty-state">
                <ShoppingCart className="empty-state-icon" />
                <div className="empty-state-title">No hay órdenes de compra</div>
                <div className="empty-state-description">Crea tu primera orden de compra</div>
                <button className="btn btn-primary" onClick={() => setShowModal(true)}>
                  <Plus size={18} />
                  Nueva Orden
                </button>
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>Número</th>
                    <th>Proveedor</th>
                    <th>Estado</th>
                    <th className="text-right">Total</th>
                    <th className="text-center">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {ordenes.map((oc) => (
                    <tr key={oc.id}>
                      <td>{formatDate(oc.fecha)}</td>
                      <td style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.8125rem' }}>
                        {oc.numero}
                      </td>
                      <td>{oc.proveedor_nombre || '-'}</td>
                      <td>
                        <span className={estadoBadge(oc.estado)}>
                          {oc.estado}
                        </span>
                      </td>
                      <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 500 }}>
                        {formatCurrency(oc.total, oc.moneda_codigo === 'USD' ? '$' : 'S/')}
                      </td>
                      <td>
                        <div className="actions-row">
                          {(oc.estado === 'borrador' || oc.estado === 'aprobada') && !oc.factura_generada_id && (
                            <button 
                              className="action-btn action-success"
                              onClick={() => handleGenerarFactura(oc)}
                              title="Generar Factura"
                            >
                              <FileCheck size={15} />
                            </button>
                          )}
                          <button 
                            className="action-btn"
                            onClick={() => handleView(oc)}
                            title="Ver detalles"
                          >
                            <Eye size={15} />
                          </button>
                          {oc.estado === 'borrador' && (
                            <>
                              <button 
                                className="action-btn action-info"
                                onClick={() => handleEdit(oc)}
                                title="Editar"
                              >
                                <Edit2 size={15} />
                              </button>
                              <button 
                                className="action-btn action-danger"
                                onClick={() => handleDelete(oc.id)}
                                title="Eliminar"
                              >
                                <Trash2 size={15} />
                              </button>
                            </>
                          )}
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

      {/* Modal Nueva/Editar OC - FULLSCREEN */}
      {showModal && (
        <div className="modal-fullscreen" style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 9999, background: 'var(--card-bg)', display: 'flex', flexDirection: 'column' }}>
          <div className="modal-fullscreen-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.875rem 1.5rem', background: 'var(--card-bg)', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <button type="button" className="btn btn-ghost" onClick={() => { setShowModal(false); setEditingOC(null); }}>
                <ArrowLeft size={20} />
              </button>
              <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 600 }}>
                {editingOC ? `Editar OC ${editingOC.numero}` : 'Nueva Orden de Compra'}
              </h2>
            </div>
            <button type="button" className="btn btn-primary" onClick={handleSubmit} disabled={submitting}>
              <FileCheck size={16} />
              {submitting ? 'Guardando...' : (editingOC ? 'Actualizar' : 'Guardar')}
            </button>
          </div>
          
          <div className="modal-fullscreen-body" style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', background: 'var(--card-bg-hover)' }}>
            <form onSubmit={handleSubmit}>
              {/* Top Section: Form Fields + Summary Bar */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '1.5rem', marginBottom: '1.5rem' }}>
                {/* Form Fields */}
                <div>
                  {/* Row 1: Empresa + N° Orden | Fecha + Moneda */}
                  <div className="oc-section">
                    <div className="form-grid form-grid-4">
                      <div className="form-group">
                        <label className="form-label">Empresa *</label>
                        <select
                          className="form-input form-select"
                          value={formData.empresa_id}
                          onChange={(e) => setFormData({ ...formData, empresa_id: e.target.value })}
                          required
                        >
                          <option value="">Seleccionar...</option>
                          {empresas.map(e => (
                            <option key={e.id} value={e.id}>{e.nombre}</option>
                          ))}
                        </select>
                      </div>
                      <div className="form-group">
                        <label className="form-label">N° Orden</label>
                        <input
                          type="text"
                          className="form-input"
                          value={editingOC?.numero || "(Automático)"}
                          disabled
                          style={{ background: 'var(--card-bg-hover)', color: 'var(--muted)' }}
                        />
                      </div>
                      <div className="form-group">
                        <label className="form-label">Fecha *</label>
                        <input
                          type="date"
                          className="form-input"
                          value={formData.fecha}
                          onChange={(e) => setFormData({ ...formData, fecha: e.target.value })}
                          required
                        />
                      </div>
                      <div className="form-group">
                        <label className="form-label">Moneda *</label>
                        <select
                          className="form-input form-select"
                          value={formData.moneda_id}
                          onChange={(e) => setFormData({ ...formData, moneda_id: e.target.value })}
                          required
                        >
                          {monedas.map(m => (
                            <option key={m.id} value={m.id}>{m.nombre} ({m.simbolo})</option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </div>

                  {/* Row 2: Proveedor + Condición + Días + Dirección */}
                  <div className="oc-section">
                    <div className="form-grid form-grid-4">
                      <div className="form-group">
                        <label className="form-label">Proveedor *</label>
                        <SearchableSelect
                          options={proveedores}
                          value={formData.proveedor_id}
                          onChange={(value) => setFormData({ ...formData, proveedor_id: value })}
                          placeholder="Seleccionar proveedor..."
                          searchPlaceholder="Buscar proveedor..."
                          displayKey="nombre"
                          valueKey="id"
                          onCreateNew={handleCreateProveedor}
                          createNewLabel="+ Crear nuevo proveedor"
                        />
                      </div>
                      <div className="form-group">
                        <label className="form-label">Condición de Pago</label>
                        <select
                          className="form-input form-select"
                          value={formData.condicion_pago}
                          onChange={(e) => {
                            const val = e.target.value;
                            let dias = 0;
                            if (val === 'credito_15') dias = 15;
                            else if (val === 'credito_30') dias = 30;
                            else if (val === 'credito_45') dias = 45;
                            else if (val === 'credito_60') dias = 60;
                            setFormData({ ...formData, condicion_pago: val, dias_credito: dias });
                          }}
                        >
                          <option value="contado">Contado</option>
                          <option value="credito_15">Crédito 15 días</option>
                          <option value="credito_30">Crédito 30 días</option>
                          <option value="credito_45">Crédito 45 días</option>
                          <option value="credito_60">Crédito 60 días</option>
                        </select>
                      </div>
                      <div className="form-group">
                        <label className="form-label">Dirección de Entrega</label>
                        <input
                          type="text"
                          className="form-input"
                          value={formData.direccion_entrega}
                          onChange={(e) => setFormData({ ...formData, direccion_entrega: e.target.value })}
                          placeholder="Dirección"
                        />
                      </div>
                      <div className="form-group">
                        <label className="form-label">Observaciones</label>
                        <input
                          type="text"
                          className="form-input"
                          value={formData.notas}
                          onChange={(e) => setFormData({ ...formData, notas: e.target.value })}
                          placeholder="Notas"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Summary Card - Compact */}
                <div className="oc-summary-compact">
                  <div className="summary-compact-title">Resumen</div>
                  {igvIncluido && <div className="summary-compact-badge">IGV incluido</div>}
                  <div className="summary-compact-row">
                    <span>Subtotal:</span>
                    <span className="currency-display">{monedaActual?.simbolo || 'S/'} {totales.subtotal.toFixed(2)}</span>
                  </div>
                  <div className="summary-compact-row">
                    <span>IGV:</span>
                    <span className="currency-display">{monedaActual?.simbolo || 'S/'} {totales.igv.toFixed(2)}</span>
                  </div>
                  <div className="summary-compact-total">
                    <span>Total:</span>
                    <span className="currency-display">{monedaActual?.simbolo || 'S/'} {totales.total.toFixed(2)}</span>
                  </div>
                  <div className="summary-compact-count">{cantidadArticulos} artículo(s)</div>
                </div>
              </div>

              {/* Detalle de Artículos - FULL WIDTH */}
              <div className="oc-section-fullwidth">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', padding: '0 0.5rem' }}>
                  <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Detalle de Artículos</h3>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <label className="toggle-switch">
                      <input
                        type="checkbox"
                        checked={igvIncluido}
                        onChange={(e) => setIgvIncluido(e.target.checked)}
                      />
                      <span className="toggle-slider"></span>
                      <span className="toggle-label">IGV incluido</span>
                    </label>
                    <button type="button" className="btn btn-outline btn-sm" onClick={handleAddLinea}>
                      <Plus size={14} /> Agregar Línea
                    </button>
                  </div>
                </div>
                
                <div className="articulos-table-fullwidth">
                  <table className="articulos-table">
                    <thead>
                      <tr>
                        <th style={{ width: '40px' }}>#</th>
                        <th style={{ width: '320px' }}>Artículo</th>
                        <th style={{ width: '100px' }}>Código</th>
                        <th>Descripción</th>
                        <th style={{ width: '90px' }}>Cant.</th>
                        <th style={{ width: '70px' }}>Und.</th>
                        <th style={{ width: '120px' }}>P. Unit.</th>
                        <th style={{ width: '130px' }}>Subtotal</th>
                        <th style={{ width: '50px' }}></th>
                      </tr>
                    </thead>
                    <tbody>
                      {lineas.map((linea, index) => {
                        const subtotal = (parseFloat(linea.cantidad) || 0) * (parseFloat(linea.precio_unitario) || 0);
                        const articuloSeleccionado = articulos.find(a => String(a.id) === String(linea.articulo_id));
                        const filteredArts = getFilteredArticulos(index);
                        const searchTerm = articuloSearchTerm[index] || '';
                        const isDropdownOpen = articuloDropdownOpen[index] === true || searchTerm.length > 0;
                        
                        return (
                          <tr key={index}>
                            <td className="text-center" style={{ background: 'var(--card-bg-hover)', fontWeight: 500, color: 'var(--muted)' }}>{index + 1}</td>
                            <td style={{ padding: '0.375rem', position: 'relative' }}>
                              {/* Combo Search Select */}
                              <div className="articulo-combo-select">
                                <div className="articulo-combo-trigger">
                                  <Search size={14} className="combo-search-icon" />
                                  <input
                                    type="text"
                                    className="combo-input"
                                    placeholder={articuloSeleccionado ? articuloSeleccionado.nombre : 'Buscar artículo...'}
                                    value={searchTerm}
                                    onChange={(e) => {
                                      setArticuloSearchTerm(prev => ({ ...prev, [index]: e.target.value }));
                                      setArticuloDropdownOpen(prev => ({ ...prev, [index]: true }));
                                    }}
                                    onFocus={() => {
                                      setArticuloDropdownOpen(prev => ({ ...prev, [index]: true }));
                                    }}
                                    onBlur={() => {
                                      // Delay to allow click on dropdown item
                                      setTimeout(() => {
                                        setArticuloDropdownOpen(prev => ({ ...prev, [index]: false }));
                                        // Clear search term if nothing selected
                                        if (!articuloSeleccionado) {
                                          setArticuloSearchTerm(prev => ({ ...prev, [index]: '' }));
                                        }
                                      }, 250);
                                    }}
                                  />
                                  <ChevronDown size={14} className="combo-chevron" style={{ transform: isDropdownOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
                                </div>
                                
                                {/* Dropdown */}
                                {isDropdownOpen && (
                                  <div className="articulo-combo-dropdown">
                                    {filteredArts.length === 0 ? (
                                      <div className="combo-empty">No se encontraron artículos</div>
                                    ) : (
                                      filteredArts.slice(0, 12).map(a => (
                                        <div
                                          key={a.id}
                                          className={`combo-option ${String(a.id) === String(linea.articulo_id) ? 'selected' : ''}`}
                                          onMouseDown={(e) => e.preventDefault()}
                                          onClick={() => {
                                            handleSelectArticulo(index, a.id);
                                            setArticuloSearchTerm(prev => ({ ...prev, [index]: '' }));
                                            setArticuloDropdownOpen(prev => ({ ...prev, [index]: false }));
                                          }}
                                          data-testid={`articulo-option-${a.id}`}
                                        >
                                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%', gap: '8px' }}>
                                            <div style={{ flex: 1, minWidth: 0 }}>
                                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                                {a.codigo && <span className="combo-code">[{a.codigo}]</span>}
                                                <span className="combo-name" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.nombre}</span>
                                              </div>
                                              {a.linea_negocio_nombre && (
                                                <div style={{ fontSize: '0.6875rem', color: 'var(--muted)', marginTop: '1px' }}>{a.linea_negocio_nombre}</div>
                                              )}
                                            </div>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                                              <span style={{ 
                                                fontSize: '0.6875rem', 
                                                fontFamily: "'JetBrains Mono', monospace",
                                                padding: '1px 6px', 
                                                borderRadius: '4px',
                                                background: parseFloat(a.stock_actual) > 0 ? '#ecfdf5' : 'var(--danger-bg)',
                                                color: parseFloat(a.stock_actual) > 0 ? '#059669' : '#dc2626'
                                              }}>
                                                {parseFloat(a.stock_actual || 0).toFixed(0)} {a.unidad_medida || ''}
                                              </span>
                                              {parseFloat(a.ultimo_precio) > 0 && (
                                                <span style={{ 
                                                  fontSize: '0.6875rem', 
                                                  fontFamily: "'JetBrains Mono', monospace",
                                                  color: 'var(--muted)'
                                                }}>
                                                  S/{parseFloat(a.ultimo_precio).toFixed(2)}
                                                </span>
                                              )}
                                            </div>
                                          </div>
                                        </div>
                                      ))
                                    )}
                                  </div>
                                )}
                              </div>
                            </td>
                            <td>
                              <input
                                type="text"
                                className="form-input text-center"
                                value={linea.codigo}
                                readOnly
                                style={{ background: 'var(--card-bg-alt)', fontSize: '0.8125rem' }}
                              />
                            </td>
                            <td>
                              <input
                                type="text"
                                className="form-input"
                                value={linea.descripcion}
                                onChange={(e) => handleLineaChange(index, 'descripcion', e.target.value)}
                                placeholder="Descripción del artículo"
                                style={{ fontSize: '0.8125rem' }}
                              />
                            </td>
                            <td>
                              <input
                                type="number"
                                step="0.01"
                                min="0"
                                className="form-input text-center"
                                value={linea.cantidad}
                                onChange={(e) => handleLineaChange(index, 'cantidad', e.target.value)}
                                style={{ fontSize: '0.8125rem' }}
                              />
                            </td>
                            <td>
                              <input
                                type="text"
                                className="form-input text-center"
                                value={linea.unidad}
                                readOnly
                                style={{ background: 'var(--card-bg-alt)', fontSize: '0.8125rem' }}
                              />
                            </td>
                            <td>
                              <input
                                type="number"
                                step="0.01"
                                min="0"
                                className="form-input text-right currency-input"
                                value={linea.precio_unitario}
                                onChange={(e) => handleLineaChange(index, 'precio_unitario', e.target.value)}
                                style={{ fontSize: '0.8125rem' }}
                              />
                            </td>
                            <td className="text-right currency-display" style={{ fontWeight: 600, color: 'var(--primary)', fontSize: '0.9375rem', padding: '0.5rem 0.75rem' }}>
                              {formatCurrency(subtotal, monedaActual?.simbolo)}
                            </td>
                            <td style={{ background: 'var(--card-bg-hover)', padding: '0.25rem' }}>
                              {lineas.length > 1 && (
                                <button
                                  type="button"
                                  className="action-btn action-danger"
                                  onClick={() => handleRemoveLinea(index)}
                                  style={{ width: '28px', height: '28px' }}
                                >
                                  <Trash2 size={14} />
                                </button>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Ver OC */}
      {showViewModal && selectedOC && (
        <div className="modal-overlay" onClick={() => setShowViewModal(false)}>
          <div className="modal modal-lg print-content" onClick={(e) => e.stopPropagation()} ref={printRef}>
            <div className="modal-header no-print">
              <h2 className="modal-title">Orden de Compra {selectedOC.numero}</h2>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button className="btn btn-outline btn-sm" onClick={() => handleDownloadPDF(selectedOC)} title="Descargar PDF">
                  <Download size={16} />
                  PDF
                </button>
                <button className="btn btn-outline btn-sm" onClick={handlePrint} title="Imprimir">
                  <Printer size={16} />
                  Imprimir
                </button>
                <button className="modal-close" onClick={() => setShowViewModal(false)}>
                  <X size={20} />
                </button>
              </div>
            </div>
            
            {/* Print Header */}
            <div className="print-header">
              <h1>ORDEN DE COMPRA</h1>
              <p className="oc-number">{selectedOC.numero}</p>
            </div>
            
            <div className="modal-body">
              <div className="form-grid form-grid-4" style={{ marginBottom: '1rem' }}>
                <div>
                  <label className="form-label">Fecha</label>
                  <p style={{ fontWeight: 500 }}>{formatDate(selectedOC.fecha)}</p>
                </div>
                <div>
                  <label className="form-label">Proveedor</label>
                  <p style={{ fontWeight: 500 }}>{selectedOC.proveedor_nombre || '-'}</p>
                </div>
                <div>
                  <label className="form-label">Estado</label>
                  <p><span className={estadoBadge(selectedOC.estado)}>{selectedOC.estado}</span></p>
                </div>
                <div>
                  <label className="form-label">Factura</label>
                  <p style={{ fontWeight: 500 }}>{selectedOC.factura_generada_id ? `#${selectedOC.factura_generada_id}` : '-'}</p>
                </div>
              </div>

              <h4 style={{ margin: '1rem 0 0.5rem', fontSize: '0.875rem' }}>Detalle</h4>
              <table className="data-table" style={{ fontSize: '0.8125rem' }}>
                <thead>
                  <tr>
                    <th>Descripción</th>
                    <th className="text-center">Cantidad</th>
                    <th className="text-right">P. Unit.</th>
                    <th className="text-right">Subtotal</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedOC.lineas?.map((linea, i) => (
                    <tr key={i}>
                      <td>{linea.descripcion || '-'}</td>
                      <td className="text-center">{linea.cantidad}</td>
                      <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                        {formatCurrency(linea.precio_unitario)}
                      </td>
                      <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                        {formatCurrency(linea.subtotal)}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <td colSpan={3} className="text-right">Subtotal:</td>
                    <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {formatCurrency(selectedOC.subtotal)}
                    </td>
                  </tr>
                  <tr>
                    <td colSpan={3} className="text-right">IGV:</td>
                    <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {formatCurrency(selectedOC.igv)}
                    </td>
                  </tr>
                  <tr style={{ fontWeight: 600 }}>
                    <td colSpan={3} className="text-right">TOTAL:</td>
                    <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--primary)' }}>
                      {formatCurrency(selectedOC.total)}
                    </td>
                  </tr>
                </tfoot>
              </table>

              {selectedOC.notas && (
                <div style={{ marginTop: '1rem' }}>
                  <label className="form-label">Notas</label>
                  <p style={{ color: 'var(--muted)' }}>{selectedOC.notas}</p>
                </div>
              )}
            </div>
            <div className="modal-footer no-print">
              {(selectedOC.estado === 'borrador' || selectedOC.estado === 'aprobada') && !selectedOC.factura_generada_id && (
                <button 
                  className="btn btn-success"
                  onClick={() => { setShowViewModal(false); handleGenerarFactura(selectedOC); }}
                >
                  <FileCheck size={16} />
                  Generar Factura
                </button>
              )}
              <button className="btn btn-outline" onClick={() => setShowViewModal(false)}>
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Crear Nuevo Proveedor */}
      {showProveedorModal && (
        <div className="mini-modal-overlay" style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10000 }} onClick={() => setShowProveedorModal(false)}>
          <div className="mini-modal" style={{ background: 'var(--card-bg)', borderRadius: '12px', maxWidth: '450px', width: '100%', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)' }} onClick={(e) => e.stopPropagation()}>
            <div className="mini-modal-header">
              <h3 className="mini-modal-title">Crear Nuevo Proveedor</h3>
              <button className="modal-close" onClick={() => setShowProveedorModal(false)}>
                <X size={18} />
              </button>
            </div>
            <div className="mini-modal-body">
              <div className="form-group">
                <label className="form-label">Nombre / Razón Social *</label>
                <input
                  type="text"
                  className="form-input"
                  value={newProveedorData.nombre}
                  onChange={(e) => setNewProveedorData(prev => ({ ...prev, nombre: e.target.value }))}
                  placeholder="Nombre del proveedor"
                  autoFocus
                />
              </div>
              <div className="form-group">
                <label className="form-label">RUC</label>
                <input
                  type="text"
                  className="form-input"
                  value={newProveedorData.ruc}
                  onChange={(e) => setNewProveedorData(prev => ({ ...prev, ruc: e.target.value }))}
                  placeholder="20XXXXXXXXX"
                  maxLength={11}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Dirección</label>
                <input
                  type="text"
                  className="form-input"
                  value={newProveedorData.direccion}
                  onChange={(e) => setNewProveedorData(prev => ({ ...prev, direccion: e.target.value }))}
                  placeholder="Dirección fiscal"
                />
              </div>
              <div className="form-grid form-grid-2">
                <div className="form-group">
                  <label className="form-label">Teléfono</label>
                  <input
                    type="text"
                    className="form-input"
                    value={newProveedorData.telefono}
                    onChange={(e) => setNewProveedorData(prev => ({ ...prev, telefono: e.target.value }))}
                    placeholder="Teléfono"
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Email</label>
                  <input
                    type="email"
                    className="form-input"
                    value={newProveedorData.email}
                    onChange={(e) => setNewProveedorData(prev => ({ ...prev, email: e.target.value }))}
                    placeholder="correo@ejemplo.com"
                  />
                </div>
              </div>
            </div>
            <div className="mini-modal-footer">
              <button 
                className="btn btn-outline" 
                onClick={() => setShowProveedorModal(false)}
                disabled={creatingProveedor}
              >
                Cancelar
              </button>
              <button 
                className="btn btn-primary" 
                onClick={handleSaveNewProveedor}
                disabled={creatingProveedor || !newProveedorData.nombre.trim()}
              >
                {creatingProveedor ? 'Guardando...' : 'Guardar Proveedor'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
