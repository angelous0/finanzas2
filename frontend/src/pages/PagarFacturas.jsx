import React, { useState, useEffect } from 'react';
import { 
  getFacturasProveedor, createPago, getCuentasFinancieras 
} from '../services/api';
import { useEmpresa } from '../context/EmpresaContext';
import { DollarSign, CreditCard, X, Check } from 'lucide-react';
import { toast } from 'sonner';

const formatCurrency = (value, symbol = 'S/') => {
  return `${symbol} ${Number(value || 0).toLocaleString('es-PE', { minimumFractionDigits: 2 })}`;
};

const formatDate = (dateStr) => {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString('es-PE');
};

export const PagarFacturas = () => {
  const { empresaActual } = useEmpresa();

  const [facturas, setFacturas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [cuentasFinancieras, setCuentasFinancieras] = useState([]);
  const [facturaAPagar, setFacturaAPagar] = useState(null);
  
  const [pagoForm, setPagoForm] = useState({
    detalles: [{ cuenta_financiera_id: '', medio_pago: 'transferencia', monto: 0, referencia: '' }],
    notas: ''
  });

  useEffect(() => {
    loadData();
  }, [empresaActual]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [facturasRes, cuentasRes] = await Promise.all([
        getFacturasProveedor({ estado: 'pendiente' }),
        getCuentasFinancieras()
      ]);
      
      // Filter only pendiente and parcial
      const pendientes = facturasRes.data.filter(f => 
        f.estado === 'pendiente' || f.estado === 'parcial'
      );
      setFacturas(pendientes);
      setCuentasFinancieras(cuentasRes.data);
    } catch (error) {
      console.error('Error loading data:', error);
      toast.error('Error al cargar datos');
    } finally {
      setLoading(false);
    }
  };

  const openPagarModal = (factura) => {
    setFacturaAPagar(factura);
    setPagoForm({
      detalles: [{ 
        cuenta_financiera_id: cuentasFinancieras[0]?.id || '', 
        medio_pago: 'transferencia', 
        monto: factura.saldo_pendiente,
        referencia: '' 
      }],
      notas: ''
    });
    setShowModal(true);
  };

  const handleAddDetalle = () => {
    setPagoForm(prev => ({
      ...prev,
      detalles: [...prev.detalles, { cuenta_financiera_id: '', medio_pago: 'transferencia', monto: 0, referencia: '' }]
    }));
  };

  const handleRemoveDetalle = (index) => {
    setPagoForm(prev => ({
      ...prev,
      detalles: prev.detalles.filter((_, i) => i !== index)
    }));
  };

  const handleDetalleChange = (index, field, value) => {
    setPagoForm(prev => ({
      ...prev,
      detalles: prev.detalles.map((det, i) => 
        i === index ? { ...det, [field]: value } : det
      )
    }));
  };

  const getTotalPago = () => {
    return pagoForm.detalles.reduce((sum, d) => sum + (parseFloat(d.monto) || 0), 0);
  };

  const handlePagar = async (e) => {
    e.preventDefault();
    if (!facturaAPagar || submitting) return;

    const totalPago = getTotalPago();
    
    if (totalPago <= 0) {
      toast.error('El monto a pagar debe ser mayor a 0');
      return;
    }

    if (totalPago > facturaAPagar.saldo_pendiente) {
      toast.error('El monto no puede superar el saldo pendiente');
      return;
    }

    setSubmitting(true);
    try {
      await createPago({
        tipo: 'egreso',
        fecha: new Date().toISOString().split('T')[0],
        cuenta_financiera_id: parseInt(pagoForm.detalles[0].cuenta_financiera_id),
        monto_total: totalPago,
        notas: pagoForm.notas || `Pago factura ${facturaAPagar.numero}`,
        detalles: pagoForm.detalles.map(d => ({
          cuenta_financiera_id: parseInt(d.cuenta_financiera_id),
          medio_pago: d.medio_pago,
          monto: parseFloat(d.monto),
          referencia: d.referencia
        })),
        aplicaciones: [{
          tipo_documento: 'factura',
          documento_id: facturaAPagar.id,
          monto_aplicado: totalPago
        }]
      });
      
      toast.success('Pago registrado exitosamente');
      setShowModal(false);
      setFacturaAPagar(null);
      loadData();
    } catch (error) {
      console.error('Error creating pago:', error);
      toast.error(error.response?.data?.detail || 'Error al registrar pago');
    } finally {
      setSubmitting(false);
    }
  };

  const totalPendiente = facturas.reduce((sum, f) => sum + parseFloat(f.saldo_pendiente || 0), 0);

  return (
    <div data-testid="pagar-facturas-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Pagar Facturas</h1>
          <p className="page-subtitle">
            {facturas.length} facturas pendientes • Total: {formatCurrency(totalPendiente)}
          </p>
        </div>
      </div>

      <div className="page-content">
        <div className="card">
          <div className="data-table-wrapper">
            {loading ? (
              <div className="loading">
                <div className="loading-spinner"></div>
              </div>
            ) : facturas.length === 0 ? (
              <div className="empty-state">
                <Check className="empty-state-icon" style={{ color: '#22C55E' }} />
                <div className="empty-state-title">No hay facturas pendientes</div>
                <div className="empty-state-description">Todas las facturas están pagadas</div>
              </div>
            ) : (
              <table className="data-table" data-testid="facturas-pendientes-table">
                <thead>
                  <tr>
                    <th>Número</th>
                    <th>Proveedor</th>
                    <th>Fecha</th>
                    <th>Vencimiento</th>
                    <th className="text-right">Total</th>
                    <th className="text-right">Saldo Pendiente</th>
                    <th>Estado</th>
                    <th className="text-center">Acción</th>
                  </tr>
                </thead>
                <tbody>
                  {facturas.map((factura) => (
                    <tr key={factura.id}>
                      <td style={{ fontWeight: 500 }}>{factura.numero}</td>
                      <td>{factura.proveedor_nombre || factura.beneficiario_nombre || '-'}</td>
                      <td>{formatDate(factura.fecha_factura)}</td>
                      <td style={{ 
                        color: new Date(factura.fecha_vencimiento) < new Date() ? '#EF4444' : 'inherit'
                      }}>
                        {formatDate(factura.fecha_vencimiento)}
                      </td>
                      <td className="text-right">{formatCurrency(factura.total)}</td>
                      <td className="text-right" style={{ fontWeight: 600, color: '#EF4444' }}>
                        {formatCurrency(factura.saldo_pendiente)}
                      </td>
                      <td>
                        <span className={`badge ${factura.estado === 'parcial' ? 'badge-info' : 'badge-warning'}`}>
                          {factura.estado}
                        </span>
                      </td>
                      <td className="text-center">
                        <button 
                          className="btn btn-primary btn-sm"
                          onClick={() => openPagarModal(factura)}
                          data-testid={`pagar-${factura.id}`}
                        >
                          <DollarSign size={14} />
                          Pagar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {/* Modal Pagar */}
      {showModal && facturaAPagar && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" style={{ maxWidth: '700px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">
                <CreditCard size={20} style={{ marginRight: '0.5rem' }} />
                Pagar Factura {facturaAPagar.numero}
              </h2>
              <button className="modal-close" onClick={() => setShowModal(false)}>
                <X size={20} />
              </button>
            </div>
            
            <form onSubmit={handlePagar}>
              <div className="modal-body">
                {/* Info factura */}
                <div style={{ 
                  display: 'grid', 
                  gridTemplateColumns: '1fr 1fr', 
                  gap: '1rem',
                  padding: '1rem',
                  background: 'var(--card-bg-hover)',
                  borderRadius: '8px',
                  marginBottom: '1.5rem'
                }}>
                  <div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--muted)', textTransform: 'uppercase' }}>
                      Proveedor
                    </div>
                    <div style={{ fontWeight: 500 }}>
                      {facturaAPagar.proveedor_nombre || facturaAPagar.beneficiario_nombre}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--muted)', textTransform: 'uppercase' }}>
                      Saldo Pendiente
                    </div>
                    <div style={{ fontWeight: 600, fontSize: '1.25rem', color: '#EF4444' }}>
                      {formatCurrency(facturaAPagar.saldo_pendiente)}
                    </div>
                  </div>
                </div>

                {/* Medios de pago */}
                <h3 style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.75rem' }}>
                  Medios de pago (multi-medio)
                </h3>
                
                {pagoForm.detalles.map((detalle, index) => (
                  <div key={index} style={{ 
                    display: 'grid', 
                    gridTemplateColumns: '1fr 1fr 120px 1fr 40px',
                    gap: '0.75rem',
                    marginBottom: '0.75rem',
                    alignItems: 'end'
                  }}>
                    <div className="form-group" style={{ marginBottom: 0 }}>
                      <label className="form-label">Cuenta</label>
                      <select
                        className="form-input form-select"
                        value={detalle.cuenta_financiera_id}
                        onChange={(e) => handleDetalleChange(index, 'cuenta_financiera_id', e.target.value)}
                        required
                      >
                        <option value="">Seleccionar...</option>
                        {cuentasFinancieras.map(c => (
                          <option key={c.id} value={c.id}>
                            {c.nombre} ({formatCurrency(c.saldo_actual)})
                          </option>
                        ))}
                      </select>
                    </div>
                    
                    <div className="form-group" style={{ marginBottom: 0 }}>
                      <label className="form-label">Medio</label>
                      <select
                        className="form-input form-select"
                        value={detalle.medio_pago}
                        onChange={(e) => handleDetalleChange(index, 'medio_pago', e.target.value)}
                      >
                        <option value="transferencia">Transferencia</option>
                        <option value="efectivo">Efectivo</option>
                        <option value="cheque">Cheque</option>
                        <option value="tarjeta">Tarjeta</option>
                      </select>
                    </div>
                    
                    <div className="form-group" style={{ marginBottom: 0 }}>
                      <label className="form-label">Monto</label>
                      <input
                        type="number"
                        step="0.01"
                        className="form-input"
                        value={detalle.monto}
                        onChange={(e) => handleDetalleChange(index, 'monto', e.target.value)}
                        style={{ textAlign: 'right' }}
                        required
                      />
                    </div>
                    
                    <div className="form-group" style={{ marginBottom: 0 }}>
                      <label className="form-label">Referencia</label>
                      <input
                        type="text"
                        className="form-input"
                        placeholder="Nº operación"
                        value={detalle.referencia}
                        onChange={(e) => handleDetalleChange(index, 'referencia', e.target.value)}
                      />
                    </div>
                    
                    <div>
                      {pagoForm.detalles.length > 1 && (
                        <button
                          type="button"
                          className="btn btn-outline btn-sm btn-icon"
                          onClick={() => handleRemoveDetalle(index)}
                        >
                          <X size={14} />
                        </button>
                      )}
                    </div>
                  </div>
                ))}

                <button
                  type="button"
                  className="btn btn-outline btn-sm"
                  onClick={handleAddDetalle}
                  style={{ marginBottom: '1rem' }}
                >
                  + Agregar otro medio de pago
                </button>

                {/* Total */}
                <div className="totals-section">
                  <div className="totals-row">
                    <span>Saldo pendiente</span>
                    <span className="totals-value">{formatCurrency(facturaAPagar.saldo_pendiente)}</span>
                  </div>
                  <div className="totals-row total">
                    <span>Total a pagar</span>
                    <span className="totals-value" style={{
                      color: getTotalPago() > facturaAPagar.saldo_pendiente ? '#EF4444' : '#22C55E'
                    }}>
                      {formatCurrency(getTotalPago())}
                    </span>
                  </div>
                  {getTotalPago() < facturaAPagar.saldo_pendiente && (
                    <div className="totals-row">
                      <span>Nuevo saldo</span>
                      <span className="totals-value" style={{ color: '#F59E0B' }}>
                        {formatCurrency(facturaAPagar.saldo_pendiente - getTotalPago())}
                      </span>
                    </div>
                  )}
                </div>

                {getTotalPago() > facturaAPagar.saldo_pendiente && (
                  <div style={{ 
                    padding: '0.75rem', 
                    background: 'var(--danger-bg)', 
                    borderRadius: '6px',
                    color: 'var(--danger-text)',
                    fontSize: '0.875rem',
                    marginTop: '1rem'
                  }}>
                    El monto total no puede superar el saldo pendiente
                  </div>
                )}
              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-outline" onClick={() => setShowModal(false)}>
                  Cancelar
                </button>
                <button 
                  type="submit" 
                  className="btn btn-primary"
                  disabled={submitting || getTotalPago() > facturaAPagar.saldo_pendiente || getTotalPago() <= 0}
                >
                  <CreditCard size={18} />
                  {submitting ? 'Registrando...' : 'Registrar Pago'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default PagarFacturas;
