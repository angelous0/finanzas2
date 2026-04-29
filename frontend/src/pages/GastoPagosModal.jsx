import React, { useEffect, useState } from 'react';
import { X, DollarSign, Plus, CheckCircle2, AlertCircle, Loader2, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { getGasto, addPagoToGasto, deleteGastoPago, getCuentasFinancieras } from '../services/api';

const MEDIOS = ['efectivo', 'transferencia', 'cheque', 'tarjeta'];

/**
 * Modal: Pagos del Gasto
 * Lista los pagos vinculados a un gasto y permite agregar uno nuevo si no hay
 * (o si hay saldo pendiente).
 */
export default function GastoPagosModal({ show, gastoId, onClose, onChanged }) {
  const [gasto, setGasto] = useState(null);
  const [cuentas, setCuentas] = useState([]);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ cuenta_financiera_id: '', medio_pago: 'efectivo', monto: '', referencia: '' });

  const load = async () => {
    if (!gastoId) return;
    setLoading(true);
    try {
      const [g, c] = await Promise.all([getGasto(gastoId), getCuentasFinancieras()]);
      setGasto(g.data);
      setCuentas(c.data);
      // Si no hay pagos, abrir form automáticamente
      if (!(g.data.pagos_vinculados || []).length) {
        const pen = (g.data.total || 0) - (g.data.total_pagado || 0);
        setForm(f => ({ ...f, monto: pen > 0 ? pen.toFixed(2) : '' }));
        setShowForm(true);
      } else {
        setShowForm(false);
      }
    } catch (e) {
      toast.error('Error cargando');
    } finally { setLoading(false); }
  };

  useEffect(() => { if (show) load(); }, [show, gastoId]);

  if (!show) return null;

  const saldo = gasto ? Math.max(0, (gasto.total || 0) - (gasto.total_pagado || 0)) : 0;
  const totalPagado = gasto?.total_pagado || 0;

  const handleAdd = async () => {
    if (adding) return;
    const monto = parseFloat(form.monto || 0);
    if (!form.cuenta_financiera_id) { toast.error('Selecciona una cuenta'); return; }
    if (monto <= 0) { toast.error('Monto debe ser > 0'); return; }
    setAdding(true);
    try {
      await addPagoToGasto(gastoId, {
        cuenta_financiera_id: parseInt(form.cuenta_financiera_id),
        medio_pago: form.medio_pago,
        monto,
        referencia: form.referencia || null,
      });
      toast.success(`Pago de S/ ${monto.toFixed(2)} agregado`);
      setForm({ cuenta_financiera_id: '', medio_pago: 'efectivo', monto: '', referencia: '' });
      setShowForm(false);
      await load();
      onChanged?.();
    } catch (e) {
      const msg = e.response?.data?.detail || 'Error al agregar pago';
      toast.error(typeof msg === 'string' ? msg : 'Error al agregar pago');
    } finally { setAdding(false); }
  };

  const handleDelete = async (pagoId) => {
    if (!window.confirm('¿Eliminar este pago? Se devolverá el saldo a la cuenta.')) return;
    try {
      await deleteGastoPago(gastoId, pagoId);
      toast.success('Pago eliminado');
      await load();
      onChanged?.();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error al eliminar');
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose} style={{ zIndex: 1100 }}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '720px' }}>
        <div className="modal-header">
          <h2 className="modal-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <DollarSign size={20} /> Pagos del gasto {gasto?.numero || ''}
          </h2>
          <button className="modal-close" onClick={onClose}><X size={20} /></button>
        </div>

        <div className="modal-body">
          {loading || !gasto ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}><Loader2 className="animate-spin" /></div>
          ) : (
            <>
              {/* KPIs */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem', marginBottom: '1rem' }}>
                <div style={{ padding: '0.625rem', background: 'var(--card-bg-hover)', border: '1px solid var(--border)', borderRadius: 8 }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--muted)', fontWeight: 600 }}>TOTAL GASTO</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>S/ {(gasto.total || 0).toFixed(2)}</div>
                </div>
                <div style={{ padding: '0.625rem', background: 'rgba(34,197,94,0.05)', border: '1px solid rgba(34,197,94,0.3)', borderRadius: 8 }}>
                  <div style={{ fontSize: '0.7rem', color: '#15803d', fontWeight: 600 }}>PAGADO</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#15803d', fontFamily: "'JetBrains Mono', monospace" }}>S/ {totalPagado.toFixed(2)}</div>
                </div>
                <div style={{ padding: '0.625rem', background: saldo > 0.01 ? 'rgba(245,158,11,0.05)' : 'rgba(99,102,241,0.05)', border: `1px solid ${saldo > 0.01 ? 'rgba(245,158,11,0.3)' : 'rgba(99,102,241,0.2)'}`, borderRadius: 8 }}>
                  <div style={{ fontSize: '0.7rem', color: saldo > 0.01 ? '#b45309' : '#4f46e5', fontWeight: 600 }}>SALDO</div>
                  <div style={{ fontSize: '1.1rem', fontWeight: 700, color: saldo > 0.01 ? '#b45309' : '#4f46e5', fontFamily: "'JetBrains Mono', monospace" }}>S/ {saldo.toFixed(2)}</div>
                </div>
              </div>

              {/* Lista pagos */}
              {(gasto.pagos_vinculados || []).length > 0 ? (
                <table className="data-table" style={{ fontSize: '0.85rem', marginBottom: '1rem' }}>
                  <thead>
                    <tr>
                      <th>Fecha</th><th>N° Pago</th><th>Cuenta</th><th>Medio</th>
                      <th className="text-right">Monto</th><th>Referencia</th><th className="text-center">Acción</th>
                    </tr>
                  </thead>
                  <tbody>
                    {gasto.pagos_vinculados.map(p => (
                      <tr key={p.id}>
                        <td>{p.fecha ? new Date(p.fecha + 'T00:00:00').toLocaleDateString('es-PE') : '-'}</td>
                        <td style={{ fontFamily: "'JetBrains Mono', monospace" }}>{p.numero}</td>
                        <td>{p.cuenta_nombre} {p.es_ficticia && <span style={{ background: '#fef3c7', color: '#92400e', padding: '1px 6px', borderRadius: 4, fontSize: '0.65rem', marginLeft: 4 }}>Ficticia</span>}</td>
                        <td style={{ textTransform: 'capitalize' }}>{p.medio_pago}</td>
                        <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, color: '#15803d' }}>S/ {p.monto_total.toFixed(2)}</td>
                        <td style={{ fontSize: '0.7rem', color: 'var(--muted)' }}>{p.ref_operacion || '-'}</td>
                        <td className="text-center">
                          <button className="action-btn action-danger" onClick={() => handleDelete(p.id)} title="Eliminar pago" style={{ width: 28, height: 28 }}>
                            <Trash2 size={13} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div style={{ padding: '1rem', background: 'var(--card-bg-hover)', borderRadius: 8, textAlign: 'center', fontSize: '0.85rem', color: 'var(--muted)', marginBottom: '1rem' }}>
                  <AlertCircle size={20} style={{ marginBottom: 4 }} />
                  <div>Sin pagos registrados</div>
                </div>
              )}

              {/* Form para agregar */}
              {!showForm && saldo > 0.01 && (
                <button type="button" className="btn btn-outline" onClick={() => { setForm(f => ({ ...f, monto: saldo.toFixed(2) })); setShowForm(true); }}>
                  <Plus size={14} /> Agregar pago (saldo S/ {saldo.toFixed(2)})
                </button>
              )}
              {!showForm && saldo <= 0.01 && (gasto.pagos_vinculados || []).length > 0 && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 0.75rem', background: 'rgba(34,197,94,0.05)', border: '1px solid rgba(34,197,94,0.3)', borderRadius: 6, color: '#15803d', fontSize: '0.85rem' }}>
                  <CheckCircle2 size={16} /> Gasto totalmente pagado
                </div>
              )}

              {showForm && (
                <div style={{ background: 'var(--card-bg-hover)', border: '1px solid var(--border)', borderRadius: 8, padding: '1rem' }}>
                  <h3 style={{ marginTop: 0, marginBottom: '0.75rem', fontSize: '0.95rem', fontWeight: 600 }}>Nuevo pago</h3>
                  <div className="form-grid form-grid-2" style={{ gap: '0.75rem' }}>
                    <div className="form-group">
                      <label className="form-label">Cuenta *</label>
                      <select className="form-input form-select" value={form.cuenta_financiera_id}
                        onChange={(e) => setForm({ ...form, cuenta_financiera_id: e.target.value })}>
                        <option value="">— Seleccionar —</option>
                        {cuentas.map(c => (
                          <option key={c.id} value={c.id}>
                            {c.nombre} {c.es_ficticia ? '(Ficticia)' : ''}
                            {c.saldo_actual !== undefined ? ` · Saldo S/ ${parseFloat(c.saldo_actual).toFixed(2)}` : ''}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="form-group">
                      <label className="form-label">Medio de pago</label>
                      <select className="form-input form-select" value={form.medio_pago}
                        onChange={(e) => setForm({ ...form, medio_pago: e.target.value })}>
                        {MEDIOS.map(m => <option key={m} value={m} style={{ textTransform: 'capitalize' }}>{m}</option>)}
                      </select>
                    </div>
                    <div className="form-group">
                      <label className="form-label">Monto *</label>
                      <input type="number" step="0.01" className="form-input" value={form.monto}
                        onChange={(e) => setForm({ ...form, monto: e.target.value })}
                        onWheel={(e) => e.currentTarget.blur()}
                        placeholder={saldo.toFixed(2)} />
                    </div>
                    <div className="form-group">
                      <label className="form-label">Referencia</label>
                      <input type="text" className="form-input" value={form.referencia}
                        onChange={(e) => setForm({ ...form, referencia: e.target.value })}
                        placeholder="N° operación, voucher..." />
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '0.75rem' }}>
                    <button type="button" className="btn btn-outline" onClick={() => setShowForm(false)} disabled={adding}>Cancelar</button>
                    <button type="button" className="btn btn-primary" onClick={handleAdd} disabled={adding}>
                      {adding ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                      {adding ? 'Guardando...' : 'Registrar pago'}
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        <div className="modal-footer">
          <button type="button" className="btn btn-outline" onClick={onClose}>Cerrar</button>
        </div>
      </div>
    </div>
  );
}
