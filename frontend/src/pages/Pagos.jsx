import React, { useState, useEffect } from 'react';
import { getPagos, deletePago, updatePago } from '../services/api';
import { useEmpresa } from '../context/EmpresaContext';
import { Trash2, DollarSign, TrendingUp, TrendingDown, Edit2, X, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';

const formatCurrency = (value, symbol = 'S/') => {
  return `${symbol} ${Number(value || 0).toLocaleString('es-PE', { minimumFractionDigits: 2 })}`;
};

const formatDate = (dateStr) => {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString('es-PE');
};

export const Pagos = () => {
  const { empresaActual } = useEmpresa();

  const [pagos, setPagos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filtroTipo, setFiltroTipo] = useState('');
  
  // Edit modal states
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingPago, setEditingPago] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [editForm, setEditForm] = useState({
    fecha: '',
    referencia: '',
    notas: ''
  });

  useEffect(() => {
    loadData();
  }, [filtroTipo, empresaActual]);

  const loadData = async () => {
    try {
      setLoading(true);
      const response = await getPagos({ tipo: filtroTipo || undefined });
      setPagos(response.data);
    } catch (error) {
      toast.error('Error al cargar pagos');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (pago) => {
    setEditingPago(pago);
    setEditForm({
      fecha: pago.fecha ? pago.fecha.split('T')[0] : '',
      referencia: pago.referencia || '',
      notas: pago.notas || ''
    });
    setShowEditModal(true);
  };

  const handleSaveEdit = async () => {
    if (submitting) return;
    setSubmitting(true);
    try {
      await updatePago(editingPago.id, editForm);
      toast.success('Pago actualizado exitosamente');
      setShowEditModal(false);
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al actualizar pago');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (pago) => {
    // Check if conciliado
    if (pago.conciliado) {
      toast.error('No se puede eliminar un pago que ya está conciliado. Primero desconcilie el movimiento.');
      return;
    }

    if (!window.confirm('¿Eliminar este pago? Se revertirán los cambios en saldos.')) return;
    try {
      await deletePago(pago.id);
      toast.success('Pago eliminado y revertido');
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al eliminar pago');
    }
  };

  const totalIngresos = pagos.filter(p => p.tipo === 'ingreso').reduce((sum, p) => sum + parseFloat(p.monto_total || 0), 0);
  const totalEgresos = pagos.filter(p => p.tipo === 'egreso').reduce((sum, p) => sum + parseFloat(p.monto_total || 0), 0);

  return (
    <div data-testid="pagos-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Movimientos / Pagos</h1>
          <p className="page-subtitle">Historial de pagos e ingresos</p>
        </div>
      </div>

      <div className="page-content">
        {/* KPIs */}
        <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)', marginBottom: '1rem' }}>
          <div className="kpi-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <TrendingUp size={18} color="#22C55E" />
              <span className="kpi-label" style={{ marginBottom: 0 }}>Ingresos</span>
            </div>
            <div className="kpi-value positive">{formatCurrency(totalIngresos)}</div>
          </div>
          <div className="kpi-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <TrendingDown size={18} color="#EF4444" />
              <span className="kpi-label" style={{ marginBottom: 0 }}>Egresos</span>
            </div>
            <div className="kpi-value negative">{formatCurrency(totalEgresos)}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Neto</div>
            <div className="kpi-value" style={{ color: totalIngresos - totalEgresos >= 0 ? '#22C55E' : '#EF4444' }}>
              {formatCurrency(totalIngresos - totalEgresos)}
            </div>
          </div>
        </div>

        {/* Filtros */}
        <div className="filters-bar">
          <select 
            className="form-input form-select filter-input"
            value={filtroTipo}
            onChange={(e) => setFiltroTipo(e.target.value)}
          >
            <option value="">Todos los tipos</option>
            <option value="ingreso">Ingresos</option>
            <option value="egreso">Egresos</option>
          </select>
        </div>

        {/* Tabla */}
        <div className="card">
          <div className="data-table-wrapper">
            {loading ? (
              <div className="loading">
                <div className="loading-spinner"></div>
              </div>
            ) : pagos.length === 0 ? (
              <div className="empty-state">
                <DollarSign className="empty-state-icon" />
                <div className="empty-state-title">No hay pagos registrados</div>
              </div>
            ) : (
              <table className="data-table" data-testid="pagos-table">
                <thead>
                  <tr>
                    <th>Número</th>
                    <th>Fecha</th>
                    <th>Tipo</th>
                    <th>Cuenta</th>
                    <th className="text-right">Monto</th>
                    <th>Referencia</th>
                    <th>Estado</th>
                    <th className="text-center">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {pagos.map((pago) => (
                    <tr key={pago.id}>
                      <td style={{ fontWeight: 500 }}>{pago.numero}</td>
                      <td>{formatDate(pago.fecha)}</td>
                      <td>
                        <span className={`badge ${pago.tipo === 'ingreso' ? 'badge-success' : 'badge-error'}`}>
                          {pago.tipo}
                        </span>
                      </td>
                      <td>{pago.cuenta_nombre || '-'}</td>
                      <td className="text-right" style={{ 
                        fontWeight: 600,
                        color: pago.tipo === 'ingreso' ? '#22C55E' : '#EF4444'
                      }}>
                        {pago.tipo === 'egreso' ? '-' : '+'}{formatCurrency(pago.monto_total)}
                      </td>
                      <td>{pago.referencia || '-'}</td>
                      <td>
                        {pago.conciliado ? (
                          <span className="badge badge-success" style={{ fontSize: '0.75rem' }}>
                            Conciliado
                          </span>
                        ) : (
                          <span className="badge" style={{ fontSize: '0.75rem', background: 'var(--border)', color: 'var(--muted)' }}>
                            Pendiente
                          </span>
                        )}
                      </td>
                      <td className="text-center">
                        <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center' }}>
                          <button 
                            className="btn btn-outline btn-sm btn-icon"
                            onClick={() => handleEdit(pago)}
                            title={pago.conciliado ? "Editar referencia" : "Editar pago"}
                          >
                            <Edit2 size={14} />
                          </button>
                          <button 
                            className="btn btn-outline btn-sm btn-icon"
                            onClick={() => handleDelete(pago)}
                            title={pago.conciliado ? "No se puede eliminar (conciliado)" : "Eliminar y revertir"}
                            style={pago.conciliado ? { opacity: 0.5, cursor: 'not-allowed' } : {}}
                          >
                            <Trash2 size={14} />
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

      {/* Edit Modal */}
      {showEditModal && editingPago && (
        <div className="modal-overlay" onClick={() => setShowEditModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '500px' }}>
            <div className="modal-header">
              <div>
                <h2 className="modal-title">
                  <Edit2 size={20} style={{ display: 'inline', marginRight: '0.5rem' }} />
                  Editar Pago
                </h2>
                {editingPago.conciliado && (
                  <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '0.5rem', 
                    marginTop: '0.5rem',
                    padding: '0.5rem',
                    background: 'var(--warning-bg)',
                    borderRadius: '6px',
                    fontSize: '0.875rem',
                    color: 'var(--warning-text)'
                  }}>
                    <AlertTriangle size={16} />
                    <span>Este pago está conciliado. Solo puede editar la referencia.</span>
                  </div>
                )}
              </div>
              <button className="modal-close" onClick={() => setShowEditModal(false)}>
                <X size={20} />
              </button>
            </div>

            <div className="modal-body">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {/* Número y Tipo (solo lectura) */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div>
                    <label className="form-label">Número</label>
                    <input
                      type="text"
                      className="form-input"
                      value={editingPago.numero}
                      disabled
                      style={{ background: 'var(--card-bg-hover)', cursor: 'not-allowed' }}
                    />
                  </div>
                  <div>
                    <label className="form-label">Tipo</label>
                    <input
                      type="text"
                      className="form-input"
                      value={editingPago.tipo}
                      disabled
                      style={{ background: 'var(--card-bg-hover)', cursor: 'not-allowed' }}
                    />
                  </div>
                </div>

                {/* Fecha */}
                <div>
                  <label className="form-label">Fecha</label>
                  <input
                    type="date"
                    className="form-input"
                    value={editForm.fecha}
                    onChange={(e) => setEditForm({ ...editForm, fecha: e.target.value })}
                    disabled={editingPago.conciliado}
                    style={editingPago.conciliado ? { background: 'var(--card-bg-hover)', cursor: 'not-allowed' } : {}}
                  />
                </div>

                {/* Referencia */}
                <div>
                  <label className="form-label">
                    Referencia {editingPago.conciliado && <span style={{ color: '#22c55e' }}>✓ Editable</span>}
                  </label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="Ingrese referencia del pago"
                    value={editForm.referencia}
                    onChange={(e) => setEditForm({ ...editForm, referencia: e.target.value })}
                  />
                </div>

                {/* Notas */}
                <div>
                  <label className="form-label">Notas</label>
                  <textarea
                    className="form-input"
                    placeholder="Notas adicionales"
                    value={editForm.notas}
                    onChange={(e) => setEditForm({ ...editForm, notas: e.target.value })}
                    disabled={editingPago.conciliado}
                    style={editingPago.conciliado ? { background: 'var(--card-bg-hover)', cursor: 'not-allowed' } : {}}
                    rows={3}
                  />
                </div>
              </div>
            </div>

            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setShowEditModal(false)}>
                <X size={16} /> Cancelar
              </button>
              <button className="btn btn-primary" onClick={handleSaveEdit} disabled={submitting}>
                <Edit2 size={16} /> {submitting ? 'Guardando...' : 'Guardar Cambios'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Pagos;
