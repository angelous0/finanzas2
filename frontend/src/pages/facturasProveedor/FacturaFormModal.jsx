import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { createFacturaProveedor, updateFacturaProveedor, createTercero, getVinculacionesFactura, getMovimientosProduccionSinFactura, vincularFacturaMovimiento } from '../../services/api';
import { formatCurrency, calcularTotales, calcularImporteArticulo, getEmptyLinea, getEmptyFormData } from './helpers';
import { Plus, Trash2, X, FileText, ChevronDown, ChevronUp, Copy, DollarSign, Download, Link2, History, FileSpreadsheet, Package, Factory, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import SearchableSelect from '../../components/SearchableSelect';
import TableSearchSelect from '../../components/TableSearchSelect';
import CategoriaSelect from '../../components/CategoriaSelect';

const FacturaFormModal = ({
  show, editingFactura, readOnly, proveedores, monedas, categorias, lineasNegocio,
  centrosCosto, inventario, modelosCortes, serviciosProduccion = [], unidadesInternas = [], valorizacionMap,
  onClose, onSaved, onProveedorCreated,
  onOpenPago, onDownloadPDF, onVincularIngresos, onVerPagos, onOpenLetras, onVerLetras
}) => {
  const [formData, setFormData] = useState(getEmptyFormData());
  const [fechaContableManual, setFechaContableManual] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [showDetallesArticulo, setShowDetallesArticulo] = useState(true);
  const [showVinculados, setShowVinculados] = useState(false);
  const [vinculados, setVinculados] = useState([]);
  const [movimientosProduccion, setMovimientosProduccion] = useState([]);
  const [loadingMovimientos, setLoadingMovimientos] = useState(false);

  // Initialize form when modal opens
  useEffect(() => {
    if (!show) return;
    if (editingFactura) {
      populateFromFactura(editingFactura);
    } else {
      resetForm();
    }
  }, [show, editingFactura]);

  // Calculate fecha_vencimiento when fecha_factura or terminos change
  useEffect(() => {
    if (formData.fecha_factura && formData.terminos_dias) {
      const fecha = new Date(formData.fecha_factura);
      fecha.setDate(fecha.getDate() + parseInt(formData.terminos_dias));
      const updates = { fecha_vencimiento: fecha.toISOString().split('T')[0] };
      if (!fechaContableManual) {
        updates.fecha_contable = formData.fecha_factura;
      }
      setFormData(prev => ({ ...prev, ...updates }));
    }
  }, [formData.fecha_factura, formData.terminos_dias]);

  const resetForm = () => {
    const pen = monedas.find(m => m.codigo === 'PEN');
    setFormData(getEmptyFormData(pen?.id || ''));
    setFechaContableManual(false);
  };

  const populateFromFactura = (factura) => {
    setFormData({
      proveedor_id: factura.proveedor_id || '',
      beneficiario_nombre: factura.beneficiario_nombre || '',
      moneda_id: factura.moneda_id || '',
      tipo_cambio: factura.tipo_cambio || '',
      fecha_factura: factura.fecha_factura ? factura.fecha_factura.split('T')[0] : new Date().toISOString().split('T')[0],
      fecha_contable: factura.fecha_contable ? factura.fecha_contable.split('T')[0] : (factura.fecha_factura ? factura.fecha_factura.split('T')[0] : new Date().toISOString().split('T')[0]),
      fecha_vencimiento: factura.fecha_vencimiento ? factura.fecha_vencimiento.split('T')[0] : '',
      terminos_dias: factura.terminos_dias || 30,
      tipo_documento: factura.tipo_documento || 'factura',
      numero: factura.numero || '',
      impuestos_incluidos: factura.impuestos_incluidos !== false,
      tipo_comprobante_sunat: factura.tipo_comprobante_sunat || '',
      base_gravada: factura.base_gravada || 0,
      igv_sunat: factura.igv_sunat || 0,
      base_no_gravada: factura.base_no_gravada || 0,
      isc: factura.isc || 0,
      notas: factura.notas || '',
      lineas: (() => {
        const catLines = (factura.lineas || []).filter(l => !l.articulo_id && !l.servicio_id);
        return catLines.length > 0
          ? catLines.map(l => ({ id: l.id, categoria_id: l.categoria_id || '', descripcion: l.descripcion || '', linea_negocio_id: l.linea_negocio_id || '', centro_costo_id: l.centro_costo_id || '', unidad_interna_id: l.unidad_interna_id || '', importe: l.importe || 0, igv_aplica: l.igv_aplica !== false, movimiento_id: '' }))
          : [getEmptyLinea()];
      })(),
      articulos: (() => {
        const artLines = (factura.lineas || []).filter(l => l.articulo_id || l.servicio_id);
        return artLines.map(a => ({
          id: a.id,
          tipo_linea: a.tipo_linea || (a.servicio_id ? 'servicio' : 'inventariable'),
          articulo_id: a.articulo_id || '',
          servicio_id: a.servicio_id || '',
          servicio_detalle: a.servicio_detalle || '',
          modelo_corte_id: a.modelo_corte_id || '',
          unidad: a.descripcion || '',
          cantidad: a.cantidad || 1,
          precio: a.precio_unitario || 0,
          linea_negocio_id: a.linea_negocio_id || '',
          igv_aplica: a.igv_aplica !== false
        }));
      })()
    });
  };

  // Helper: detect if category belongs to SERVICIOS DE PRODUCCIÓN
  const esServicioProduccion = useCallback((categoriaId) => {
    if (!categoriaId) return false;
    const cat = categorias.find(c => String(c.id) === String(categoriaId));
    return (
      cat?.nombre_completo?.startsWith('SERVICIOS DE PRODUCCIÓN >') ||
      cat?.nombre === 'SERVICIOS DE PRODUCCIÓN'
    );
  }, [categorias]);

  // Fetch movimientos without factura from produccion backend
  const fetchMovimientosProduccion = useCallback(async (proveedorId) => {
    setLoadingMovimientos(true);
    try {
      const pid = proveedorId ?? formData.proveedor_id;
      const proveedor = proveedores.find(p => String(p.id) === String(pid));
      const params = {};
      if (proveedor?.nombre) params.persona_nombre = proveedor.nombre;
      const res = await getMovimientosProduccionSinFactura(params);
      setMovimientosProduccion(res.data || []);
    } catch {
      setMovimientosProduccion([]);
    }
    setLoadingMovimientos(false);
  }, [formData.proveedor_id, proveedores]);

  // Line handlers
  const handleAddLinea = () => setFormData(prev => ({ ...prev, lineas: [...prev.lineas, getEmptyLinea()] }));
  const handleRemoveLinea = (index) => { if (formData.lineas.length > 1) setFormData(prev => ({ ...prev, lineas: prev.lineas.filter((_, i) => i !== index) })); };
  const handleDuplicateLinea = (index) => setFormData(prev => ({ ...prev, lineas: [...prev.lineas.slice(0, index + 1), { ...prev.lineas[index] }, ...prev.lineas.slice(index + 1)] }));
  const handleLineaChange = (index, field, value) => {
    setFormData(prev => ({
      ...prev,
      lineas: prev.lineas.map((linea, i) => {
        if (i !== index) return linea;
        const updated = { ...linea, [field]: value };
        // Auto-fill importe when movimiento is selected
        if (field === 'movimiento_id' && value) {
          const mov = movimientosProduccion.find(m => m.id === value);
          if (mov) {
            updated.importe = parseFloat(mov.costo_calculado) || 0;
            if (!updated.descripcion) updated.descripcion = mov.servicio_nombre || '';
          }
        }
        // Clear movimiento when category changes away from servicios produccion
        if (field === 'categoria_id' && !esServicioProduccion(value)) {
          updated.movimiento_id = '';
        }
        return updated;
      })
    }));
    // Trigger movimientos fetch when a servicios-produccion category is selected
    if (field === 'categoria_id' && esServicioProduccion(value) && movimientosProduccion.length === 0) {
      fetchMovimientosProduccion();
    }
  };

  // Article handlers
  const handleAddArticulo = () => setFormData(prev => ({ ...prev, articulos: [...prev.articulos, { tipo_linea: 'inventariable', articulo_id: '', servicio_id: '', servicio_detalle: '', modelo_corte_id: '', unidad: '', cantidad: 1, precio: 0, linea_negocio_id: '', igv_aplica: true }] }));
  const handleRemoveArticulo = (index) => setFormData(prev => ({ ...prev, articulos: prev.articulos.filter((_, i) => i !== index) }));
  const handleDuplicateArticulo = (index) => setFormData(prev => ({ ...prev, articulos: [...prev.articulos.slice(0, index + 1), { ...prev.articulos[index] }, ...prev.articulos.slice(index + 1)] }));
  const handleArticuloChange = (index, field, value) => {
    setFormData(prev => ({
      ...prev,
      articulos: prev.articulos.map((art, i) => {
        if (i !== index) return art;
        const updated = { ...art, [field]: value };
        // Reset fields on tipo_linea change
        if (field === 'tipo_linea') {
          updated.articulo_id = '';
          updated.servicio_id = '';
          updated.servicio_detalle = '';
          updated.unidad = '';
          updated.precio = 0;
          updated.modelo_corte_id = '';
        }
        if (field === 'articulo_id' && value) {
          const selectedArticulo = inventario.find(inv => inv.id === value);
          if (selectedArticulo) {
            updated.unidad = selectedArticulo.unidad_medida || 'UND';
            const fifo = valorizacionMap[value];
            updated.precio = fifo?.costo_fifo_unitario || parseFloat(selectedArticulo.costo_compra) || parseFloat(selectedArticulo.precio_ref) || 0;
            if (selectedArticulo.linea_negocio_id) {
              updated.linea_negocio_id = selectedArticulo.linea_negocio_id;
            }
          }
        }
        if (field === 'servicio_id' && value) {
          const selectedServicio = serviciosProduccion.find(s => s.id === value);
          if (selectedServicio) {
            updated.unidad = 'SRV';
            updated.precio = selectedServicio.tarifa || 0;
          }
        }
        return updated;
      })
    }));
  };

  // Proveedor creation
  const handleCreateProveedor = async (nombre) => {
    if (!nombre || nombre.trim() === '') return;
    try {
      const response = await createTercero({ nombre: nombre.trim(), es_proveedor: true, tipo_documento: 'RUC', numero_documento: '', terminos_pago_dias: 30 });
      setFormData(prev => ({ ...prev, proveedor_id: response.data.id, beneficiario_nombre: '' }));
      toast.success(`Proveedor "${nombre}" creado exitosamente`);
      if (onProveedorCreated) onProveedorCreated(response.data);
    } catch (error) {
      console.error('Error creating proveedor:', error);
      toast.error('Error al crear proveedor');
    }
  };

  // Submit
  const handleSubmit = async (e, createNew = false) => {
    e.preventDefault();
    if (submitting) return;
    try {
      const tots = calcularTotales(formData);
      const dataToSend = {
        ...formData,
        proveedor_id: formData.proveedor_id ? parseInt(formData.proveedor_id) : null,
        moneda_id: formData.moneda_id ? parseInt(formData.moneda_id) : null,
        terminos_dias: parseInt(formData.terminos_dias) || 0,
        tipo_cambio: formData.tipo_cambio ? parseFloat(formData.tipo_cambio) : null,
        base_gravada: tots.base_gravada,
        igv_sunat: tots.igv_sunat,
        base_no_gravada: tots.base_no_gravada,
        isc: parseFloat(formData.isc) || 0,
        fecha_factura: formData.fecha_factura || null,
        fecha_contable: formData.fecha_contable || formData.fecha_factura || null,
        fecha_vencimiento: formData.fecha_vencimiento || null,
        lineas: [
          ...formData.lineas.map(l => {
            // eslint-disable-next-line no-unused-vars
            const { movimiento_id, ...rest } = l;
            return {
              ...rest,
              categoria_id: l.categoria_id ? parseInt(l.categoria_id) : null,
              linea_negocio_id: l.linea_negocio_id ? parseInt(l.linea_negocio_id) : null,
              centro_costo_id: l.centro_costo_id ? parseInt(l.centro_costo_id) : null,
              unidad_interna_id: l.unidad_interna_id ? parseInt(l.unidad_interna_id) : null,
              importe: parseFloat(l.importe) || 0
            };
          }),
          ...formData.articulos.map(art => {
            const isServicio = art.tipo_linea === 'servicio';
            const selectedArticulo = !isServicio ? inventario.find(inv => inv.id === art.articulo_id) : null;
            const selectedServicio = isServicio ? serviciosProduccion.find(s => s.id === art.servicio_id) : null;
            return {
              id: art.id || undefined,
              tipo_linea: art.tipo_linea || 'inventariable',
              articulo_id: isServicio ? null : (art.articulo_id || null),
              servicio_id: isServicio ? (art.servicio_id || null) : null,
              servicio_detalle: isServicio ? (art.servicio_detalle || null) : null,
              modelo_corte_id: isServicio ? (art.modelo_corte_id || null) : null,
              linea_negocio_id: art.linea_negocio_id ? parseInt(art.linea_negocio_id) : null,
              descripcion: selectedArticulo
                ? `${selectedArticulo.codigo || ''} ${selectedArticulo.nombre}`.trim()
                : (art.servicio_detalle || (selectedServicio ? selectedServicio.nombre : null)),
              cantidad: parseFloat(art.cantidad) || 0,
              precio_unitario: parseFloat(art.precio) || 0,
              importe: (parseFloat(art.cantidad) || 0) * (parseFloat(art.precio) || 0),
              igv_aplica: art.igv_aplica !== false
            };
          })
        ]
      };
      delete dataToSend.articulos;
      if (!dataToSend.fecha_factura) { toast.error('La fecha de factura es requerida'); return; }

      setSubmitting(true);
      // Collect lineas with movimiento before saving
      const lineasConMovimiento = formData.lineas.filter(l => l.movimiento_id);
      let savedFacturaNro = null;
      let savedFacturaId = null;

      if (editingFactura) {
        const isLockedState = editingFactura.estado === 'pagado' || editingFactura.estado === 'canjeado';
        if (isLockedState) {
          const classificationData = {
            notas: dataToSend.notas,
            fecha_contable: dataToSend.fecha_contable,
            tipo_comprobante_sunat: dataToSend.tipo_comprobante_sunat,
            lineas: formData.lineas.map(l => ({
              id: l.id,
              categoria_id: l.categoria_id ? parseInt(l.categoria_id) : null,
              descripcion: l.descripcion,
              linea_negocio_id: l.linea_negocio_id ? parseInt(l.linea_negocio_id) : null,
              centro_costo_id: l.centro_costo_id ? parseInt(l.centro_costo_id) : null,
              unidad_interna_id: l.unidad_interna_id ? parseInt(l.unidad_interna_id) : null,
            }))
          };
          await updateFacturaProveedor(editingFactura.id, classificationData);
          toast.success('Clasificacion actualizada exitosamente');
          savedFacturaNro = editingFactura.numero;
          savedFacturaId = String(editingFactura.id);
        } else {
          await updateFacturaProveedor(editingFactura.id, dataToSend);
          toast.success('Factura actualizada exitosamente');
          savedFacturaNro = editingFactura.numero;
          savedFacturaId = String(editingFactura.id);
        }
      } else {
        const savedRes = await createFacturaProveedor(dataToSend);
        toast.success('Factura creada exitosamente');
        savedFacturaNro = savedRes?.data?.numero;
        savedFacturaId = String(savedRes?.data?.id || '');
      }

      // Vincular movimientos de producción con la factura guardada
      if (savedFacturaNro && lineasConMovimiento.length > 0) {
        for (const linea of lineasConMovimiento) {
          try {
            await vincularFacturaMovimiento(linea.movimiento_id, {
              factura_numero: savedFacturaNro,
              factura_id: savedFacturaId,
            });
          } catch (e) {
            console.error('Error vinculando movimiento a factura:', e);
          }
        }
      }

      if (createNew) { resetForm(); } else { onClose(); }
      onSaved();
    } catch (error) {
      console.error('Error saving factura:', error);
      const detail = error.response?.data?.detail;
      if (Array.isArray(detail)) {
        const firstError = detail[0];
        toast.error(firstError?.msg || firstError?.message || 'Error de validacion');
      } else if (typeof detail === 'string') {
        toast.error(detail);
      } else {
        toast.error('Error al guardar factura');
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (!show) return null;

  const totales = calcularTotales(formData);
  const monedaActual = monedas.find(m => m.id === parseInt(formData.moneda_id));
  const isLocked = !readOnly && editingFactura && (editingFactura.estado === 'pagado' || editingFactura.estado === 'canjeado');
  const lockedStyle = { background: 'var(--card-bg-alt)', pointerEvents: 'none', opacity: 0.7 };

  // Computed flags for toolbar
  const saldo = parseFloat(editingFactura?.saldo_pendiente) || 0;
  const totalFact = parseFloat(editingFactura?.total) || 0;
  const pagado = totalFact - saldo;
  const puedePagar = editingFactura && (editingFactura.estado === 'pendiente' || editingFactura.estado === 'parcial') && saldo > 0;
  const puedeLetras = editingFactura && editingFactura.estado === 'pendiente' && saldo > 0;
  const estaCanjeado = editingFactura?.estado === 'canjeado';
  const tienePagos = pagado > 0;
  const tieneArticulos = editingFactura && formData.lineas_articulos?.some(l => l.articulo_id);
  const tieneVinculados = editingFactura?.vinculacion_resumen?.estado === 'completo' || editingFactura?.vinculacion_resumen?.estado === 'parcial';
  const showToolbar = editingFactura && (readOnly || isLocked);

  const loadVinculados = async () => {
    if (!editingFactura?.id) return;
    try {
      const res = await getVinculacionesFactura(editingFactura.id);
      setVinculados(res.data);
      setShowVinculados(true);
    } catch { toast.error('Error al cargar vinculaciones'); }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="factura-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="factura-modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <FileText size={24} color="var(--primary)" />
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600, margin: 0 }}>
              {readOnly ? `Ver Factura ${editingFactura?.numero || ''}` : isLocked ? `Editar Clasificacion - ${editingFactura?.numero || ''}` : editingFactura ? `Editar Factura ${editingFactura.numero}` : 'Factura de proveedor'}
            </h2>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>SALDO PENDIENTE</div>
              <div style={{ fontSize: '1.5rem', fontWeight: 600, fontFamily: "'JetBrains Mono', monospace" }}>
                {formatCurrency(totales.total, monedaActual?.simbolo || 'S/.')}
              </div>
            </div>
            <button className="modal-close" onClick={onClose}><X size={20} /></button>
          </div>
        </div>

        {/* Action Toolbar */}
        {showToolbar && (
          <div data-testid="factura-toolbar" style={{
            display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 1.5rem',
            borderBottom: '1px solid var(--border)', background: 'var(--card-bg-hover)', flexWrap: 'wrap'
          }}>
            {onDownloadPDF && (
              <button type="button" className="btn btn-outline btn-sm" onClick={() => onDownloadPDF(editingFactura)}
                data-testid="toolbar-pdf" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem' }}>
                <Download size={13} /> PDF
              </button>
            )}
            {puedePagar && !estaCanjeado && onOpenPago && (
              <button type="button" className="btn btn-sm" onClick={() => { onClose(); setTimeout(() => onOpenPago(editingFactura), 100); }}
                data-testid="toolbar-pagar" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', background: '#059669', color: 'var(--card-bg)', border: 'none' }}>
                <DollarSign size={13} /> Registrar Pago
              </button>
            )}
            {tieneArticulos && onVincularIngresos && (
              <button type="button" className="btn btn-outline btn-sm" onClick={() => { onClose(); setTimeout(() => onVincularIngresos(editingFactura), 100); }}
                data-testid="toolbar-vincular" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem' }}>
                <Link2 size={13} /> Vincular Ingresos
              </button>
            )}
            {tieneVinculados && (
              <button type="button" className="btn btn-outline btn-sm" onClick={loadVinculados}
                data-testid="toolbar-ver-vinculados" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem' }}>
                <Package size={13} /> Ver Vinculados
              </button>
            )}
            {tienePagos && !estaCanjeado && onVerPagos && (
              <button type="button" className="btn btn-outline btn-sm" onClick={() => { onClose(); setTimeout(() => onVerPagos(editingFactura), 100); }}
                data-testid="toolbar-ver-pagos" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem' }}>
                <History size={13} /> Ver Pagos ({pagado > 0 ? `${editingFactura?.moneda_simbolo || 'S/.'} ${pagado.toFixed(2)}` : ''})
              </button>
            )}
            {puedeLetras && onOpenLetras && (
              <button type="button" className="btn btn-outline btn-sm" onClick={() => { onClose(); setTimeout(() => onOpenLetras(editingFactura), 100); }}
                data-testid="toolbar-letras" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem' }}>
                <FileSpreadsheet size={13} /> Canjear Letras
              </button>
            )}
            {estaCanjeado && onVerLetras && (
              <button type="button" className="btn btn-outline btn-sm" onClick={() => { onClose(); setTimeout(() => onVerLetras(editingFactura), 100); }}
                data-testid="toolbar-ver-letras" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem' }}>
                <FileSpreadsheet size={13} /> Ver Letras
              </button>
            )}
          </div>
        )}

        <form onSubmit={(e) => { if (readOnly) { e.preventDefault(); return; } handleSubmit(e, false); }}>
          <fieldset disabled={readOnly} style={{ display: 'contents' }}>
          <div className="factura-modal-body">
            {/* Proveedor row */}
            <div className="form-row">
              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label required">Proveedor</label>
                <SearchableSelect
                  options={proveedores}
                  value={formData.proveedor_id}
                  onChange={(value) => setFormData(prev => ({ ...prev, proveedor_id: value, beneficiario_nombre: value ? '' : prev.beneficiario_nombre }))}
                  placeholder="Buscar proveedor..."
                  searchPlaceholder="Buscar por nombre..."
                  displayKey="nombre"
                  valueKey="id"
                  onCreateNew={isLocked ? undefined : handleCreateProveedor}
                  createNewLabel="Crear proveedor"
                  data-testid="proveedor-select"
                  disabled={isLocked}
                />
              </div>
              {!formData.proveedor_id && (
                <div className="form-group" style={{ flex: 1 }}>
                  <label className="form-label">O escribir beneficiario</label>
                  <input type="text" className="form-input" placeholder="Nombre del beneficiario" value={formData.beneficiario_nombre} onChange={(e) => setFormData(prev => ({ ...prev, beneficiario_nombre: e.target.value }))} data-testid="beneficiario-input" />
                </div>
              )}
            </div>

            {/* Terms, Currency, Dates */}
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Terminos</label>
                <input type="text" className="form-input" placeholder="Ej: 30 dias" value={formData.terminos_dias} onChange={(e) => setFormData(prev => ({ ...prev, terminos_dias: e.target.value }))} disabled={isLocked} style={isLocked ? lockedStyle : undefined} />
              </div>
              <div className="form-group">
                <label className="form-label">Moneda</label>
                <select className="form-input form-select" value={formData.moneda_id} disabled={isLocked} style={isLocked ? lockedStyle : undefined} onChange={(e) => {
                  const selMoneda = monedas.find(m => m.id === parseInt(e.target.value));
                  setFormData(prev => ({ ...prev, moneda_id: e.target.value, tipo_cambio: selMoneda?.codigo === 'PEN' ? '1' : prev.tipo_cambio || '' }));
                }}>
                  <option value="">Moneda</option>
                  {monedas.map(m => (<option key={m.id} value={m.id}>{m.codigo}</option>))}
                </select>
              </div>
              {monedas.find(m => m.id === parseInt(formData.moneda_id))?.codigo === 'USD' && (
                <div className="form-group">
                  <label className="form-label required">T.C.</label>
                  <input type="number" step="0.001" className="form-input" placeholder="Ej: 3.72" value={formData.tipo_cambio} onChange={(e) => setFormData(prev => ({ ...prev, tipo_cambio: e.target.value }))} data-testid="tipo-cambio-input" required disabled={isLocked} style={isLocked ? lockedStyle : undefined} />
                </div>
              )}
              <div className="form-group">
                <label className="form-label required">Fecha de factura</label>
                <input type="date" className="form-input" value={formData.fecha_factura} onChange={(e) => setFormData(prev => ({ ...prev, fecha_factura: e.target.value }))} required disabled={isLocked} style={isLocked ? lockedStyle : undefined} />
              </div>
              <div className="form-group">
                <label className="form-label">Fecha contable {isLocked && <span style={{ fontSize: '0.65rem', color: '#22C55E' }}>editable</span>}</label>
                <input type="date" className="form-input" value={formData.fecha_contable} onChange={(e) => { setFechaContableManual(true); setFormData(prev => ({ ...prev, fecha_contable: e.target.value })); }} data-testid="factura-fecha-contable" />
              </div>
              <div className="form-group">
                <label className="form-label">Fecha de vencimiento</label>
                <input type="date" className="form-input" value={formData.fecha_vencimiento} onChange={(e) => setFormData(prev => ({ ...prev, fecha_vencimiento: e.target.value }))} disabled={isLocked} style={isLocked ? lockedStyle : undefined} />
              </div>
            </div>

            {/* Document type and number */}
            <div className="form-row">
              <div className="form-group" style={{ maxWidth: '200px' }}>
                <label className="form-label required">Tipo de documento</label>
                <select className="form-input form-select" value={formData.tipo_documento} onChange={(e) => setFormData(prev => ({ ...prev, tipo_documento: e.target.value }))} disabled={isLocked} style={isLocked ? lockedStyle : undefined}>
                  <option value="factura">Factura</option>
                  <option value="boleta">Boleta</option>
                  <option value="recibo">Recibo por Honorarios</option>
                  <option value="nota_credito">Nota de Credito</option>
                </select>
              </div>
              <div className="form-group" style={{ maxWidth: '200px' }}>
                <label className="form-label required">N. de documento</label>
                <input type="text" className="form-input" placeholder="NV001-00001" value={formData.numero} onChange={(e) => setFormData(prev => ({ ...prev, numero: e.target.value }))} disabled={isLocked} style={isLocked ? lockedStyle : undefined} />
              </div>
            </div>

            {/* SUNAT */}
            <div className="form-row" style={{ marginTop: '0.75rem', gap: '0.75rem', flexWrap: 'wrap' }}>
              <div className="form-group" style={{ maxWidth: '140px' }}>
                <label className="form-label">Doc SUNAT</label>
                <select className="form-input form-select" value={formData.tipo_comprobante_sunat} onChange={(e) => setFormData(prev => ({ ...prev, tipo_comprobante_sunat: e.target.value }))} data-testid="factura-tipo-sunat">
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
              <div className="form-group" style={{ maxWidth: '140px' }}>
                <label className="form-label">Base Gravada</label>
                <input type="text" className="form-input" value={totales.base_gravada.toFixed(2)} readOnly style={{ background: 'var(--input-bg-readonly)' }} data-testid="factura-base-gravada" />
              </div>
              <div className="form-group" style={{ maxWidth: '130px' }}>
                <label className="form-label">IGV</label>
                <input type="text" className="form-input" value={totales.igv_sunat.toFixed(2)} readOnly style={{ background: 'var(--input-bg-readonly)' }} data-testid="factura-igv-sunat" />
              </div>
              <div className="form-group" style={{ maxWidth: '140px' }}>
                <label className="form-label">No Gravada</label>
                <input type="text" className="form-input" value={totales.base_no_gravada.toFixed(2)} readOnly style={{ background: 'var(--input-bg-readonly)' }} data-testid="factura-base-no-gravada" />
              </div>
              <div className="form-group" style={{ maxWidth: '120px' }}>
                <label className="form-label">ISC</label>
                <input type="number" step="0.01" min="0" className="form-input" value={formData.isc} onChange={(e) => setFormData(prev => ({ ...prev, isc: parseFloat(e.target.value) || 0 }))} data-testid="factura-isc" disabled={isLocked} style={isLocked ? lockedStyle : undefined} />
              </div>
            </div>

            {/* Category lines section */}
            <div className="factura-section">
              <div className="factura-section-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <ChevronUp size={18} />
                  <span style={{ fontWeight: 600 }}>Detalles de la categoria</span>
                  <span style={{ color: 'var(--muted)', fontSize: '0.875rem' }}>({formData.lineas.length} linea{formData.lineas.length !== 1 ? 's' : ''})</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ fontSize: '0.875rem', color: 'var(--muted)' }}>Los importes son</span>
                  <select className="form-input form-select" style={{ width: 'auto', padding: '0.375rem 2rem 0.375rem 0.75rem', fontSize: '0.875rem' }} value={formData.impuestos_incluidos ? 'incluidos' : 'sin_igv'} onChange={(e) => setFormData(prev => ({ ...prev, impuestos_incluidos: e.target.value === 'incluidos' }))} disabled={isLocked}>
                    <option value="sin_igv">Sin IGV</option>
                    <option value="incluidos">Impuestos incluidos</option>
                  </select>
                </div>
              </div>
              <div className="table-scroll-wrapper">
                <table className="factura-table">
                  <thead>
                    <tr>
                      <th style={{ width: '40px' }}>#</th>
                      <th style={{ minWidth: '160px' }}>CATEGORIA</th>
                      <th style={{ minWidth: '180px' }}>DESCRIPCION</th>
                      <th style={{ minWidth: '140px' }}>LINEA NEGOCIO</th>
                      <th style={{ minWidth: '130px' }}>UNIDAD INTERNA</th>
                      <th style={{ width: '100px' }}>IMPORTE</th>
                      <th style={{ width: '80px' }}>IGV 18%</th>
                      <th style={{ width: '100px' }}>ACCIONES</th>
                    </tr>
                  </thead>
                  <tbody>
                    {formData.lineas.map((linea, index) => (
                      <React.Fragment key={index}>
                        <tr>
                          <td className="row-number">{index + 1}</td>
                          <td>
                            <CategoriaSelect categorias={categorias} value={linea.categoria_id} onChange={(value) => handleLineaChange(index, 'categoria_id', value)} placeholder="Categoria" />
                          </td>
                          <td>
                            <input type="text" placeholder="Descripcion" value={linea.descripcion} onChange={(e) => handleLineaChange(index, 'descripcion', e.target.value)} />
                          </td>
                          <td>
                            <TableSearchSelect options={lineasNegocio} value={linea.linea_negocio_id} onChange={(value) => handleLineaChange(index, 'linea_negocio_id', value)} placeholder="Linea" displayKey="nombre" valueKey="id" />
                          </td>
                          <td>
                            <select value={linea.unidad_interna_id || ''} onChange={(e) => handleLineaChange(index, 'unidad_interna_id', e.target.value)}>
                              <option value="">Sin asignar</option>
                              {unidadesInternas.map(ui => (
                                <option key={ui.id} value={ui.id}>{ui.nombre}</option>
                              ))}
                            </select>
                          </td>
                          <td>
                            <input type="number" step="0.01" placeholder="0.00" value={linea.importe} onChange={(e) => handleLineaChange(index, 'importe', e.target.value)} style={{ textAlign: 'right', ...(isLocked ? lockedStyle : {}) }} data-testid={`linea-importe-${index}`} disabled={isLocked} />
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            <input type="checkbox" checked={linea.igv_aplica} onChange={(e) => handleLineaChange(index, 'igv_aplica', e.target.checked)} style={{ width: '18px', height: '18px', accentColor: 'var(--primary)' }} disabled={isLocked} />
                          </td>
                          <td className="actions-cell">
                            {!isLocked && (
                              <>
                                <button type="button" className="btn-icon-small" onClick={() => handleDuplicateLinea(index)} title="Duplicar"><Copy size={14} /></button>
                                <button type="button" className="btn-icon-small" onClick={() => handleRemoveLinea(index)} title="Eliminar" disabled={formData.lineas.length === 1}><Trash2 size={14} /></button>
                              </>
                            )}
                          </td>
                        </tr>
                        {/* Sub-fila: Movimiento de Producción (solo para SERVICIOS DE PRODUCCIÓN) */}
                        {esServicioProduccion(linea.categoria_id) && (
                          <tr style={{ background: '#fffbeb' }}>
                            <td />
                            <td colSpan="7" style={{ paddingBottom: '0.5rem', paddingTop: '0.25rem' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <Factory size={13} style={{ color: '#d97706', flexShrink: 0 }} />
                                <span style={{ fontSize: '0.7rem', fontWeight: 600, color: '#d97706', whiteSpace: 'nowrap' }}>Movimiento de Producción</span>
                                {loadingMovimientos
                                  ? <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} />
                                  : (
                                    <select
                                      value={linea.movimiento_id || ''}
                                      onChange={e => handleLineaChange(index, 'movimiento_id', e.target.value)}
                                      disabled={isLocked}
                                      style={{
                                        flex: 1, fontSize: '0.75rem', padding: '0.25rem 0.5rem',
                                        border: '1px solid #fbbf24', borderRadius: '4px',
                                        background: linea.movimiento_id ? '#d1fae5' : 'white',
                                        color: linea.movimiento_id ? '#065f46' : 'inherit',
                                        minWidth: 0,
                                      }}
                                    >
                                      <option value="">— Sin vincular —</option>
                                      {movimientosProduccion.map(m => (
                                        <option key={m.id} value={m.id}>{m.label}</option>
                                      ))}
                                    </select>
                                  )
                                }
                                {movimientosProduccion.length === 0 && !loadingMovimientos && (
                                  <button
                                    type="button"
                                    style={{ fontSize: '0.7rem', color: '#d97706', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}
                                    onClick={() => fetchMovimientosProduccion()}
                                  >
                                    Cargar
                                  </button>
                                )}
                                {linea.movimiento_id && (
                                  <span style={{ fontSize: '0.65rem', padding: '1px 6px', borderRadius: '999px', background: '#d1fae5', color: '#065f46', fontWeight: 600 }}>
                                    ✓ Vinculado
                                  </span>
                                )}
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
              <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.75rem' }}>
                {!isLocked && (
                  <>
                    <button type="button" className="btn btn-outline btn-sm" onClick={handleAddLinea}><Plus size={16} /> Agregar linea</button>
                    <button type="button" className="btn btn-outline btn-sm" onClick={() => setFormData(prev => ({ ...prev, lineas: [getEmptyLinea()] }))}>Borrar todas las lineas</button>
                  </>
                )}
              </div>
            </div>

            {/* Article lines section */}
            <div className="factura-section">
              <button type="button" className="factura-section-header" onClick={() => setShowDetallesArticulo(!showDetallesArticulo)} style={{ width: '100%', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  {showDetallesArticulo ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                  <span style={{ fontWeight: 600 }}>Detalles del articulo / servicio</span>
                  <span style={{ color: 'var(--muted)', fontSize: '0.875rem' }}>({formData.articulos.length} linea{formData.articulos.length !== 1 ? 's' : ''})</span>
                </div>
              </button>
              {showDetallesArticulo && (
                <>
                  {formData.articulos.length > 0 ? (() => {
                    const hayServicio = formData.articulos.some(a => a.tipo_linea === 'servicio');
                    return (
                    <div className="table-scroll-wrapper">
                      <table className="factura-table">
                        <thead>
                          <tr>
                            <th style={{ width: '36px' }}>#</th>
                            <th style={{ width: '110px' }}>TIPO</th>
                            <th style={{ minWidth: '150px' }}>ART. / SRV. PADRE</th>
                            {hayServicio && <th style={{ minWidth: '140px' }}>DETALLE SERVICIO</th>}
                            {hayServicio && <th style={{ minWidth: '140px' }}>REGISTRO / CORTE</th>}
                            <th style={{ width: '60px' }}>CANT.</th>
                            <th style={{ width: '85px' }}>COSTO U.</th>
                            <th style={{ minWidth: '120px' }}>LINEA NEG.</th>
                            <th style={{ width: '90px' }}>IMPORTE</th>
                            <th style={{ width: '40px' }}>IGV</th>
                            <th style={{ width: '60px' }}></th>
                          </tr>
                        </thead>
                        <tbody>
                          {formData.articulos.map((articulo, index) => {
                            const isServicio = articulo.tipo_linea === 'servicio';
                            return (
                              <tr key={index}>
                                <td className="row-number">{index + 1}</td>
                                <td>
                                  <select
                                    value={articulo.tipo_linea || 'inventariable'}
                                    onChange={(e) => handleArticuloChange(index, 'tipo_linea', e.target.value)}
                                    style={{ width: '100%', fontSize: '0.75rem', padding: '0.3rem', border: '1px solid var(--border)', borderRadius: '4px', background: isServicio ? '#eff6ff' : 'var(--success-bg)' }}
                                    data-testid={`tipo-linea-${index}`}
                                  >
                                    <option value="inventariable">Inventariable</option>
                                    <option value="servicio">Srv. Produc.</option>
                                  </select>
                                </td>
                                <td>
                                  {isServicio ? (
                                    <TableSearchSelect
                                      options={serviciosProduccion}
                                      value={articulo.servicio_id}
                                      onChange={(value) => handleArticuloChange(index, 'servicio_id', value)}
                                      placeholder="Srv. padre..."
                                      displayKey="nombre"
                                      valueKey="id"
                                      renderOption={(s) => s.nombre}
                                    />
                                  ) : (
                                    <TableSearchSelect
                                      options={inventario}
                                      value={articulo.articulo_id}
                                      onChange={(value) => handleArticuloChange(index, 'articulo_id', value)}
                                      placeholder="Articulo..."
                                      displayKey="nombre_completo"
                                      valueKey="id"
                                      renderOption={(inv) => `${inv.codigo ? inv.codigo + ' - ' : ''}${inv.nombre}`}
                                    />
                                  )}
                                </td>
                                {hayServicio && (
                                <td>
                                  {isServicio ? (
                                    <input
                                      type="text"
                                      value={articulo.servicio_detalle || ''}
                                      onChange={(e) => handleArticuloChange(index, 'servicio_detalle', e.target.value)}
                                      placeholder="Ej: Cerrado, Remallado..."
                                      style={{ width: '100%', fontSize: '0.8125rem', padding: '0.375rem', border: '1px solid var(--border)', borderRadius: '4px' }}
                                      data-testid={`servicio-detalle-${index}`}
                                    />
                                  ) : (
                                    <span style={{ display: 'block', textAlign: 'center', color: '#cbd5e1', fontSize: '0.8125rem' }}>-</span>
                                  )}
                                </td>
                                )}
                                {hayServicio && (
                                <td>
                                  {isServicio ? (
                                    <TableSearchSelect
                                      options={modelosCortes}
                                      value={articulo.modelo_corte_id}
                                      onChange={(value) => handleArticuloChange(index, 'modelo_corte_id', value)}
                                      placeholder="Registro / Corte"
                                      displayKey="display_name"
                                      valueKey="id"
                                      renderOption={(mc) => mc.display_name || `${mc.modelo_nombre || 'Sin modelo'} - Corte ${mc.n_corte}`}
                                    />
                                  ) : (
                                    <span style={{ display: 'block', textAlign: 'center', color: '#cbd5e1', fontSize: '0.8125rem' }}>-</span>
                                  )}
                                </td>
                                )}
                                <td><input type="number" step="1" min="1" placeholder="1" value={articulo.cantidad} onChange={(e) => handleArticuloChange(index, 'cantidad', e.target.value)} style={{ textAlign: 'center', fontSize: '0.8125rem' }} data-testid={`articulo-cantidad-${index}`} /></td>
                                <td><input type="number" step="0.01" placeholder="0.00" value={articulo.precio} onChange={(e) => handleArticuloChange(index, 'precio', e.target.value)} style={{ textAlign: 'right', fontSize: '0.8125rem' }} data-testid={`articulo-precio-${index}`} /></td>
                                <td>
                                  <TableSearchSelect options={lineasNegocio} value={articulo.linea_negocio_id} onChange={(value) => handleArticuloChange(index, 'linea_negocio_id', value)} placeholder="Linea" displayKey="nombre" valueKey="id" />
                                </td>
                                <td style={{ textAlign: 'right', fontWeight: 500, fontFamily: "'JetBrains Mono', monospace", fontSize: '0.8125rem', padding: '0.5rem' }}>{calcularImporteArticulo(articulo).toFixed(2)}</td>
                                <td style={{ textAlign: 'center' }}>
                                  <input type="checkbox" checked={articulo.igv_aplica} onChange={(e) => handleArticuloChange(index, 'igv_aplica', e.target.checked)} style={{ width: '15px', height: '15px', accentColor: 'var(--primary)' }} />
                                </td>
                                <td className="actions-cell">
                                  <button type="button" className="btn-icon-small" onClick={() => handleDuplicateArticulo(index)} title="Duplicar"><Copy size={14} /></button>
                                  <button type="button" className="btn-icon-small" onClick={() => handleRemoveArticulo(index)} title="Eliminar"><Trash2 size={14} /></button>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                    );
                  })() : null}
                  <div style={{ display: 'flex', gap: '0.75rem', padding: '0.75rem' }}>
                    <button type="button" className="btn btn-outline btn-sm" onClick={handleAddArticulo} data-testid="agregar-articulo-btn"><Plus size={16} /> Agregar linea</button>
                    {formData.articulos.length > 0 && (
                      <button type="button" className="btn btn-outline btn-sm" onClick={() => setFormData(prev => ({ ...prev, articulos: [] }))}>Borrar todos</button>
                    )}
                  </div>
                </>
              )}
            </div>

            {/* Notes and Totals */}
            <div className="form-row" style={{ alignItems: 'flex-start', marginTop: '1rem' }}>
              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">Nota</label>
                <textarea className="form-input" rows={4} placeholder="Anadir una nota..." value={formData.notas} onChange={(e) => setFormData(prev => ({ ...prev, notas: e.target.value }))} style={{ resize: 'vertical' }} />
              </div>
              <div className="factura-totales">
                <div className="totales-row"><span>Subtotal</span><span>{formatCurrency(totales.subtotal, monedaActual?.simbolo || 'S/.')}</span></div>
                <div className="totales-row"><span>IGV (18%)</span><span>{formatCurrency(totales.igv, monedaActual?.simbolo || 'S/.')}</span></div>
                <div className="totales-row total"><span>Total</span><span>{formatCurrency(totales.total, monedaActual?.simbolo || 'S/.')}</span></div>
              </div>
            </div>
          </div>
          </fieldset>

          {/* Popup: Ver Vinculados */}
          {showVinculados && (
            <div style={{
              position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.3)', display: 'flex',
              alignItems: 'center', justifyContent: 'center', zIndex: 1100
            }} onClick={() => setShowVinculados(false)}>
              <div style={{
                background: 'var(--card-bg)', borderRadius: '12px', boxShadow: '0 20px 60px rgba(0,0,0,0.2)',
                maxWidth: '700px', width: '90%', maxHeight: '70vh', overflow: 'hidden'
              }} onClick={e => e.stopPropagation()}>
                <div style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '0.75rem 1rem', borderBottom: '1px solid var(--border)', background: 'var(--card-bg-hover)'
                }}>
                  <h3 style={{ margin: 0, fontSize: '0.875rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Package size={16} color="#059669" /> Ingresos Vinculados
                  </h3>
                  <button onClick={() => setShowVinculados(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px' }}>
                    <X size={18} color="#64748b" />
                  </button>
                </div>
                <div style={{ padding: '0.75rem 1rem', maxHeight: '55vh', overflow: 'auto' }} data-testid="vinculados-popup-content">
                  {vinculados.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--muted)', fontSize: '0.85rem' }}>
                      Sin ingresos vinculados
                    </div>
                  ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }} data-testid="vinculados-table">
                      <thead>
                        <tr style={{ background: 'var(--card-bg-hover)' }}>
                          {['Articulo', 'Codigo', 'Referencia Ingreso', 'Proveedor', 'Cant. Aplicada', 'Cant. Ingreso', 'Fecha'].map((h, i) => (
                            <th key={i} style={{ padding: '6px 10px', textAlign: i >= 4 ? 'right' : 'left', color: 'var(--muted)', fontWeight: 600, borderBottom: '2px solid var(--border)', fontSize: '0.72rem' }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {vinculados.map((v, i) => (
                          <tr key={i} style={{ borderBottom: '1px solid var(--table-row-border)' }}>
                            <td style={{ padding: '6px 10px', fontWeight: 500 }}>{v.articulo_nombre || '-'}</td>
                            <td style={{ padding: '6px 10px', color: 'var(--muted)', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.75rem' }}>{v.articulo_codigo || '-'}</td>
                            <td style={{ padding: '6px 10px', color: '#2563eb', fontWeight: 500 }}>{v.ingreso_ref || '-'}</td>
                            <td style={{ padding: '6px 10px', color: 'var(--muted)' }}>{v.ingreso_proveedor || '-'}</td>
                            <td style={{ padding: '6px 10px', textAlign: 'right', fontWeight: 600, color: '#059669', fontFamily: "'JetBrains Mono', monospace" }}>
                              {parseFloat(v.cantidad_aplicada || 0).toLocaleString('es-PE')}
                            </td>
                            <td style={{ padding: '6px 10px', textAlign: 'right', fontFamily: "'JetBrains Mono', monospace", color: 'var(--muted)' }}>
                              {parseFloat(v.ingreso_cantidad || 0).toLocaleString('es-PE')}
                            </td>
                            <td style={{ padding: '6px 10px', textAlign: 'right', color: 'var(--muted)' }}>
                              {v.ingreso_fecha ? new Date(v.ingreso_fecha).toLocaleDateString('es-PE') : '-'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr style={{ borderTop: '2px solid var(--border)', background: 'var(--success-bg)' }}>
                          <td colSpan={4} style={{ padding: '6px 10px', fontWeight: 700 }}>Total Aplicado</td>
                          <td style={{ padding: '6px 10px', textAlign: 'right', fontWeight: 700, color: '#059669', fontFamily: "'JetBrains Mono', monospace" }}>
                            {vinculados.reduce((s, v) => s + parseFloat(v.cantidad_aplicada || 0), 0).toLocaleString('es-PE')}
                          </td>
                          <td colSpan={2}></td>
                        </tr>
                      </tfoot>
                    </table>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Footer */}
          <div className="factura-modal-footer">
            <button type="button" className="btn btn-outline" onClick={onClose}>{readOnly ? 'Cerrar' : 'Cancelar'}</button>
            {!readOnly && (
              <div style={{ display: 'flex', gap: '0.75rem' }}>
                <button type="submit" className="btn btn-secondary" data-testid="guardar-factura-btn" disabled={submitting}>
                  <FileText size={16} /> {submitting ? 'Guardando...' : 'Guardar'}
                </button>
                <button type="button" className="btn btn-primary" onClick={(e) => handleSubmit(e, true)} data-testid="guardar-crear-btn" disabled={submitting}>
                  {submitting ? 'Guardando...' : 'Guardar y crear nueva'}
                </button>
              </div>
            )}
          </div>
        </form>
      </div>
    </div>
  );
};

export default FacturaFormModal;
