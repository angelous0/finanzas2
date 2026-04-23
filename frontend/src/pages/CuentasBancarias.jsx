import React, { useState, useEffect } from 'react';
import { getCuentasFinancieras, createCuentaFinanciera, updateCuentaFinanciera, deleteCuentaFinanciera, getMonedas, getKardexCuenta, recalcularSaldos, getCuentasContables, mapearCuentasDefault } from '../services/api';
import { useEmpresa } from '../context/EmpresaContext';
import { Plus, Trash2, Edit2, Landmark, X, RefreshCw, FileText, ArrowUpCircle, ArrowDownCircle } from 'lucide-react';
import { toast } from 'sonner';

const formatCurrency = (value, symbol = 'S/') => {
  return `${symbol} ${Number(value || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

export const CuentasBancarias = () => {
  const { empresaActual } = useEmpresa();

  const [cuentas, setCuentas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [monedas, setMonedas] = useState([]);
  const [cuentasContables, setCuentasContables] = useState([]);
  const [kardex, setKardex] = useState(null);
  const [kardexCuentaId, setKardexCuentaId] = useState(null);
  const [kardexLoading, setKardexLoading] = useState(false);
  
  const [formData, setFormData] = useState({
    nombre: '',
    tipo: 'banco',
    banco: '',
    numero_cuenta: '',
    cci: '',
    moneda_id: '',
    saldo_inicial: 0,
    cuenta_contable_id: ''
  });

  useEffect(() => {
    loadData();
  }, [empresaActual]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [cuentasRes, monedasRes, ccRes] = await Promise.all([
        getCuentasFinancieras(),
        getMonedas(),
        getCuentasContables()
      ]);
      setCuentas(cuentasRes.data);
      setMonedas(monedasRes.data);
      setCuentasContables(ccRes.data.filter(c => c.tipo === 'ACTIVO'));
      
      const pen = monedasRes.data.find(m => m.codigo === 'PEN');
      if (pen) {
        setFormData(prev => ({ ...prev, moneda_id: pen.id }));
      }
    } catch (error) {
      toast.error('Error al cargar datos');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    try {
      const payload = {
        ...formData,
        moneda_id: parseInt(formData.moneda_id),
        saldo_inicial: parseFloat(formData.saldo_inicial) || 0,
        saldo_actual: parseFloat(formData.saldo_inicial) || 0,
        cuenta_contable_id: formData.cuenta_contable_id ? parseInt(formData.cuenta_contable_id) : null
      };
      if (editingId) {
        // When editing, only send saldo_inicial - backend will recalculate saldo_actual
        const editPayload = { ...payload };
        delete editPayload.saldo_actual;
        await updateCuentaFinanciera(editingId, editPayload);
        toast.success('Cuenta actualizada');
      } else {
        await createCuentaFinanciera(payload);
        toast.success('Cuenta creada');
      }
      setShowModal(false);
      setEditingId(null);
      resetForm();
      loadData();
    } catch (error) {
      toast.error('Error al guardar cuenta');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = (cuenta) => {
    setEditingId(cuenta.id);
    setFormData({
      nombre: cuenta.nombre || '',
      tipo: cuenta.tipo || 'banco',
      banco: cuenta.banco || '',
      numero_cuenta: cuenta.numero_cuenta || '',
      cci: cuenta.cci || '',
      moneda_id: cuenta.moneda_id || '',
      saldo_inicial: cuenta.saldo_inicial || 0,
      cuenta_contable_id: cuenta.cuenta_contable_id || ''
    });
    setShowModal(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm('¿Está seguro de eliminar esta cuenta?')) return;
    try {
      await deleteCuentaFinanciera(id);
      toast.success('Cuenta eliminada');
      loadData();
    } catch (error) {
      toast.error('Error al eliminar cuenta');
    }
  };

  const handleRecalcular = async () => {
    try {
      const res = await recalcularSaldos();
      toast.success(res.data.message);
      loadData();
    } catch (error) {
      toast.error('Error al recalcular saldos');
    }
  };

  const handleVerKardex = async (cuentaId) => {
    setKardexCuentaId(cuentaId);
    setKardexLoading(true);
    try {
      const res = await getKardexCuenta(cuentaId);
      setKardex(res.data);
    } catch (error) {
      toast.error('Error al cargar kardex');
    } finally {
      setKardexLoading(false);
    }
  };

  const resetForm = () => {
    const pen = monedas.find(m => m.codigo === 'PEN');
    setFormData({
      nombre: '',
      tipo: 'banco',
      banco: '',
      numero_cuenta: '',
      cci: '',
      moneda_id: pen?.id || '',
      saldo_inicial: 0
    });
  };

  const totalSaldo = cuentas.reduce((sum, c) => sum + parseFloat(c.saldo_actual || 0), 0);

  return (
    <div data-testid="cuentas-bancarias-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Cuentas Bancarias</h1>
          <p className="page-subtitle">Saldo total: {formatCurrency(totalSaldo)}</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-outline" onClick={handleRecalcular} data-testid="recalcular-saldos-btn">
            <RefreshCw size={16} /> Recalcular Saldos
          </button>
          <button 
            className="btn btn-primary"
            onClick={() => { resetForm(); setEditingId(null); setShowModal(true); }}
            data-testid="nueva-cuenta-btn"
          >
            <Plus size={18} /> Nueva Cuenta
          </button>
        </div>
      </div>

      <div className="page-content">
        <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
          {loading ? (
            <div className="loading">
              <div className="loading-spinner"></div>
            </div>
          ) : cuentas.length === 0 ? (
            <div className="card" style={{ gridColumn: '1 / -1' }}>
              <div className="empty-state">
                <Landmark className="empty-state-icon" />
                <div className="empty-state-title">No hay cuentas registradas</div>
                <div className="empty-state-description">Agrega tu primera cuenta bancaria o caja</div>
                <button className="btn btn-primary" onClick={() => setShowModal(true)}>
                  <Plus size={18} />
                  Agregar cuenta
                </button>
              </div>
            </div>
          ) : (
            cuentas.map((cuenta) => (
              <div key={cuenta.id} className="card" style={{ padding: '1.25rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
                  <div>
                    <div style={{ 
                      display: 'inline-flex', 
                      padding: '0.25rem 0.5rem', 
                      background: cuenta.tipo === 'banco' ? '#dbeafe' : '#fef3c7',
                      color: cuenta.tipo === 'banco' ? '#1e40af' : '#92400e',
                      borderRadius: '4px',
                      fontSize: '0.7rem',
                      fontWeight: 500,
                      textTransform: 'uppercase',
                      marginBottom: '0.5rem'
                    }}>
                      {cuenta.tipo}
                    </div>
                    <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>{cuenta.nombre}</h3>
                    {cuenta.banco && (
                      <p style={{ fontSize: '0.813rem', color: 'var(--muted)' }}>{cuenta.banco}</p>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: '0.25rem' }}>
                    <button 
                      className="btn btn-outline btn-sm btn-icon"
                      onClick={() => handleVerKardex(cuenta.id)}
                      title="Ver Kardex"
                      data-testid={`kardex-cuenta-${cuenta.id}`}
                    >
                      <FileText size={14} />
                    </button>
                    <button 
                      className="btn btn-outline btn-sm btn-icon"
                      onClick={() => handleEdit(cuenta)}
                      data-testid={`edit-cuenta-${cuenta.id}`}
                    >
                      <Edit2 size={14} />
                    </button>
                    <button 
                      className="btn btn-outline btn-sm btn-icon"
                      onClick={() => handleDelete(cuenta.id)}
                  >
                    <Trash2 size={14} />
                  </button>
                  </div>
                </div>
                
                {cuenta.numero_cuenta && (
                  <div style={{ fontSize: '0.813rem', color: 'var(--muted)', marginBottom: '0.5rem' }}>
                    Cuenta: {cuenta.numero_cuenta}
                  </div>
                )}
                
                <div style={{ 
                  fontSize: '1.5rem', 
                  fontWeight: 600, 
                  fontFamily: "'JetBrains Mono', monospace",
                  color: cuenta.saldo_actual >= 0 ? '#22C55E' : '#EF4444'
                }}>
                  {formatCurrency(cuenta.saldo_actual, cuenta.moneda_codigo === 'USD' ? '$' : 'S/')}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">{editingId ? 'Editar Cuenta' : 'Nueva Cuenta'}</h2>
              <button className="modal-close" onClick={() => { setShowModal(false); setEditingId(null); }}>
                <X size={20} />
              </button>
            </div>
            
            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label required">Nombre</label>
                  <input
                    type="text"
                    className="form-input"
                    value={formData.nombre}
                    onChange={(e) => setFormData(prev => ({ ...prev, nombre: e.target.value }))}
                    placeholder="Ej: Cuenta BCP Soles"
                    required
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div className="form-group">
                    <label className="form-label required">Tipo</label>
                    <select
                      className="form-input form-select"
                      value={formData.tipo}
                      onChange={(e) => setFormData(prev => ({ ...prev, tipo: e.target.value }))}
                    >
                      <option value="banco">Banco</option>
                      <option value="caja">Caja</option>
                    </select>
                  </div>
                  
                  <div className="form-group">
                    <label className="form-label">Moneda</label>
                    <select
                      className="form-input form-select"
                      value={formData.moneda_id}
                      onChange={(e) => setFormData(prev => ({ ...prev, moneda_id: e.target.value }))}
                    >
                      {monedas.map(m => (
                        <option key={m.id} value={m.id}>{m.codigo} - {m.nombre}</option>
                      ))}
                    </select>
                  </div>
                </div>

                {formData.tipo === 'banco' && (
                  <>
                    <div className="form-group">
                      <label className="form-label">Banco</label>
                      <select
                        className="form-input form-select"
                        value={formData.banco}
                        onChange={(e) => setFormData(prev => ({ ...prev, banco: e.target.value }))}
                      >
                        <option value="">Seleccionar banco...</option>
                        <option value="BCP">BCP</option>
                        <option value="BBVA">BBVA</option>
                        <option value="Interbank">Interbank</option>
                        <option value="Scotiabank">Scotiabank</option>
                        <option value="BanBif">BanBif</option>
                        <option value="Otro">Otro</option>
                      </select>
                    </div>

                    <div className="form-group">
                      <label className="form-label">Número de Cuenta</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.numero_cuenta}
                        onChange={(e) => setFormData(prev => ({ ...prev, numero_cuenta: e.target.value }))}
                        placeholder="Ej: 191-12345678-0-12"
                      />
                    </div>

                    <div className="form-group">
                      <label className="form-label">CCI</label>
                      <input
                        type="text"
                        className="form-input"
                        value={formData.cci}
                        onChange={(e) => setFormData(prev => ({ ...prev, cci: e.target.value }))}
                        placeholder="Código Interbancario"
                      />
                    </div>
                  </>
                )}

                <div className="form-group">
                  <label className="form-label">Saldo Inicial</label>
                  <input
                    type="number"
                    step="0.01"
                    className="form-input"
                    value={formData.saldo_inicial}
                    onChange={(e) => setFormData(prev => ({ ...prev, saldo_inicial: e.target.value }))}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Cuenta Contable</label>
                  <select
                    className="form-input form-select"
                    value={formData.cuenta_contable_id}
                    onChange={(e) => setFormData(prev => ({ ...prev, cuenta_contable_id: e.target.value ? parseInt(e.target.value) : '' }))}
                    data-testid="cuenta-contable-select"
                  >
                    <option value="">Sin asignar</option>
                    {cuentasContables.map(cc => (
                      <option key={cc.id} value={cc.id}>{cc.codigo} - {cc.nombre}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-outline" onClick={() => setShowModal(false)}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Guardando...' : (editingId ? 'Guardar Cambios' : 'Crear Cuenta')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Kardex Modal */}
      {kardex && (
        <div className="modal-overlay" onClick={() => setKardex(null)}>
          <div className="modal modal-xl" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">Kardex — {kardex.cuenta?.nombre}</h2>
              <button className="modal-close" onClick={() => setKardex(null)}>
                <X size={20} />
              </button>
            </div>
            <div style={{ padding: '1rem 1.5rem' }}>
              {/* KPI row */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.75rem', marginBottom: '1rem' }}>
                <div style={{ padding: '0.75rem', background: '#f9fafb', borderRadius: '8px' }}>
                  <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: 'var(--muted)', fontWeight: 600 }}>Saldo Inicial</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700 }}>{formatCurrency(kardex.saldo_inicial)}</div>
                </div>
                <div style={{ padding: '0.75rem', background: 'var(--success-bg)', borderRadius: '8px' }}>
                  <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: 'var(--muted)', fontWeight: 600 }}>Ingresos</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#10b981' }}>{formatCurrency(kardex.total_ingresos)}</div>
                </div>
                <div style={{ padding: '0.75rem', background: 'var(--danger-bg)', borderRadius: '8px' }}>
                  <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: 'var(--muted)', fontWeight: 600 }}>Egresos</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#ef4444' }}>{formatCurrency(kardex.total_egresos)}</div>
                </div>
                <div style={{ padding: '0.75rem', background: 'var(--info-bg)', borderRadius: '8px' }}>
                  <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: 'var(--muted)', fontWeight: 600 }}>Saldo Final</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: kardex.saldo_final >= 0 ? '#10b981' : '#ef4444' }}>{formatCurrency(kardex.saldo_final)}</div>
                </div>
              </div>

              {/* Movements Table */}
              {kardexLoading ? (
                <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--muted)' }}>Cargando...</div>
              ) : kardex.movimientos.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--muted)' }}>Sin movimientos registrados</div>
              ) : (
                <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                  <table className="data-table" data-testid="kardex-table">
                    <thead>
                      <tr>
                        <th>Fecha</th>
                        <th>N Pago</th>
                        <th>Concepto</th>
                        <th>Medio</th>
                        <th style={{ textAlign: 'right' }}>Ingreso</th>
                        <th style={{ textAlign: 'right' }}>Egreso</th>
                        <th style={{ textAlign: 'right' }}>Saldo</th>
                      </tr>
                    </thead>
                    <tbody>
                      {kardex.movimientos.map((m, i) => (
                        <tr key={i}>
                          <td>{new Date(m.fecha + 'T00:00:00').toLocaleDateString('es-PE')}</td>
                          <td style={{ fontSize: '0.8rem' }}>{m.numero}</td>
                          <td>{m.concepto || '-'}</td>
                          <td style={{ fontSize: '0.8rem' }}>{m.medio_pago}</td>
                          <td style={{ textAlign: 'right', color: '#10b981', fontWeight: m.ingreso > 0 ? 600 : 400 }}>
                            {m.ingreso > 0 ? formatCurrency(m.ingreso) : '-'}
                          </td>
                          <td style={{ textAlign: 'right', color: '#ef4444', fontWeight: m.egreso > 0 ? 600 : 400 }}>
                            {m.egreso > 0 ? formatCurrency(m.egreso) : '-'}
                          </td>
                          <td style={{ textAlign: 'right', fontWeight: 600 }}>{formatCurrency(m.saldo)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CuentasBancarias;
