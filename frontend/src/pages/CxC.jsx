import React, { useState, useEffect, useCallback } from 'react';
import { getCxC, getCxCResumen, getCxCAbonos, createCxCAbono, createCxC, getCuentasFinancieras, getTerceros } from '../services/api';
import { useEmpresa } from '../context/EmpresaContext';
import { Clock, AlertTriangle, Plus, DollarSign, CreditCard, X, ChevronDown, ChevronRight } from 'lucide-react';
import { toast } from 'sonner';

const fmt = (v) => `S/ ${Number(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtDate = (d) => d ? new Date(d + (d.includes('T') ? '' : 'T00:00:00')).toLocaleDateString('es-PE') : '-';
const isVencido = (f) => f && new Date(f) < new Date();

const AGING_LABELS = { vigente: 'Vigente', '0_30': '1-30 dias', '31_60': '31-60 dias', '61_90': '61-90 dias', '90_plus': '90+ dias' };
const AGING_COLORS = { vigente: '#22C55E', '0_30': '#F59E0B', '31_60': '#F97316', '61_90': '#EF4444', '90_plus': '#991B1B' };

export default function CxC() {
  const { empresaActual } = useEmpresa();
  const [items, setItems] = useState([]);
  const [resumen, setResumen] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filtroEstado, setFiltroEstado] = useState('');
  const [filtroAging, setFiltroAging] = useState('');

  // Detail/Abono
  const [selectedId, setSelectedId] = useState(null);
  const [abonos, setAbonos] = useState([]);
  const [showAbono, setShowAbono] = useState(false);
  const [abonoForm, setAbonoForm] = useState({ fecha: new Date().toISOString().split('T')[0], monto: '', forma_pago: 'efectivo', referencia: '', cuenta_financiera_id: '' });
  const [saving, setSaving] = useState(false);

  // Create
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({ cliente_id: '', monto_original: '', fecha_vencimiento: '', documento_referencia: '', notas: '' });

  // Catalogs
  const [cuentas, setCuentas] = useState([]);
  const [clientes, setClientes] = useState([]);

  const loadData = useCallback(async () => {
    if (!empresaActual) return;
    setLoading(true);
    try {
      const params = {};
      if (filtroEstado) params.estado = filtroEstado;
      if (filtroAging) params.aging = filtroAging;
      const [listRes, resRes] = await Promise.all([getCxC(params), getCxCResumen()]);
      setItems(listRes.data);
      setResumen(resRes.data);
    } catch (e) {
      toast.error('Error al cargar CxC');
    } finally {
      setLoading(false);
    }
  }, [empresaActual, filtroEstado, filtroAging]);

  useEffect(() => { loadData(); }, [loadData]);

  useEffect(() => {
    if (empresaActual) {
      getCuentasFinancieras().then(r => setCuentas(r.data || [])).catch(() => {});
      getTerceros().then(r => setClientes((r.data || []).filter(t => t.es_cliente))).catch(() => {});
    }
  }, [empresaActual]);

  const selectItem = async (id) => {
    if (selectedId === id) { setSelectedId(null); return; }
    setSelectedId(id);
    try {
      const res = await getCxCAbonos(id);
      setAbonos(res.data || []);
    } catch { setAbonos([]); }
  };

  const handleAbono = async (e) => {
    e.preventDefault();
    if (!abonoForm.monto || parseFloat(abonoForm.monto) <= 0) { toast.error('Monto invalido'); return; }
    setSaving(true);
    try {
      const payload = { ...abonoForm, monto: parseFloat(abonoForm.monto), cuenta_financiera_id: abonoForm.cuenta_financiera_id ? parseInt(abonoForm.cuenta_financiera_id) : null };
      await createCxCAbono(selectedId, payload);
      toast.success('Abono registrado');
      setShowAbono(false);
      setAbonoForm({ fecha: new Date().toISOString().split('T')[0], monto: '', forma_pago: 'efectivo', referencia: '', cuenta_financiera_id: '' });
      const [abRes] = await Promise.all([getCxCAbonos(selectedId), loadData()]);
      setAbonos(abRes.data || []);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al registrar abono');
    } finally { setSaving(false); }
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!createForm.monto_original) { toast.error('Monto requerido'); return; }
    setSaving(true);
    try {
      await createCxC({ ...createForm, monto_original: parseFloat(createForm.monto_original), cliente_id: createForm.cliente_id ? parseInt(createForm.cliente_id) : null });
      toast.success('CxC creada');
      setShowCreate(false);
      setCreateForm({ cliente_id: '', monto_original: '', fecha_vencimiento: '', documento_referencia: '', notas: '' });
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error');
    } finally { setSaving(false); }
  };

  const selected = items.find(i => i.id === selectedId);
  const ag = resumen?.aging || {};

  return (
    <div data-testid="cxc-page">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 className="page-title">Cuentas por Cobrar</h1>
          <p className="page-subtitle">Total pendiente: {fmt(resumen?.total_pendiente)} | Vencido: {fmt(resumen?.total_vencido)}</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)} data-testid="create-cxc-btn">
          <Plus size={16} /> Nueva CxC
        </button>
      </div>

      <div className="page-content">
        {/* KPIs */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
          <div className="kpi-card" data-testid="kpi-total-pendiente">
            <div className="kpi-label">Total Pendiente</div>
            <div className="kpi-value positive">{fmt(resumen?.total_pendiente)}</div>
            <div style={{ fontSize: '0.7rem', color: 'var(--muted)' }}>{resumen?.total_docs || 0} documentos</div>
          </div>
          <div className="kpi-card" data-testid="kpi-total-vencido">
            <div className="kpi-label">Vencido</div>
            <div className="kpi-value" style={{ color: '#EF4444' }}>{fmt(resumen?.total_vencido)}</div>
            <div style={{ fontSize: '0.7rem', color: 'var(--muted)' }}>{resumen?.docs_vencidos || 0} docs</div>
          </div>
          <div className="kpi-card" data-testid="kpi-por-vencer">
            <div className="kpi-label">Por Vencer (7d)</div>
            <div className="kpi-value" style={{ color: '#F59E0B' }}>{fmt(resumen?.por_vencer_7d)}</div>
          </div>
        </div>

        {/* Aging Buckets */}
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
          <button className={`btn ${filtroAging === '' ? 'btn-primary' : 'btn-outline'}`} style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem' }}
            onClick={() => setFiltroAging('')} data-testid="aging-all">
            Todos
          </button>
          {Object.entries(AGING_LABELS).map(([key, label]) => (
            <button key={key}
              className={`btn ${filtroAging === key ? 'btn-primary' : 'btn-outline'}`}
              style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem', borderColor: AGING_COLORS[key], color: filtroAging === key ? '#fff' : AGING_COLORS[key], background: filtroAging === key ? AGING_COLORS[key] : 'transparent' }}
              onClick={() => setFiltroAging(filtroAging === key ? '' : key)} data-testid={`aging-${key}`}>
              {label} ({ag[key]?.count || 0}) {fmt(ag[key]?.total)}
            </button>
          ))}
        </div>

        {/* Estado filter */}
        <div className="filters-bar" style={{ marginBottom: '1rem' }}>
          <select className="form-input form-select filter-input" value={filtroEstado} onChange={e => setFiltroEstado(e.target.value)} data-testid="filter-estado">
            <option value="">Todos los estados</option>
            <option value="pendiente">Pendiente</option>
            <option value="parcial">Parcial</option>
            <option value="cobrada">Cobrada</option>
            <option value="anulada">Anulada</option>
          </select>
        </div>

        {/* Table */}
        <div className="card">
          <div className="data-table-wrapper">
            {loading ? (
              <div className="loading"><div className="loading-spinner"></div></div>
            ) : items.length === 0 ? (
              <div className="empty-state">
                <Clock className="empty-state-icon" />
                <div className="empty-state-title">No hay cuentas por cobrar</div>
              </div>
            ) : (
              <table className="data-table" data-testid="cxc-table">
                <thead>
                  <tr>
                    <th style={{ width: 30 }}></th>
                    <th>Cliente</th>
                    <th>Origen</th>
                    <th>Vencimiento</th>
                    <th className="text-right">Monto</th>
                    <th className="text-right">Abonado</th>
                    <th className="text-right">Saldo</th>
                    <th>Estado</th>
                    <th style={{ width: 90 }}>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map(item => (
                    <React.Fragment key={item.id}>
                      <tr onClick={() => selectItem(item.id)} style={{ cursor: 'pointer', background: selectedId === item.id ? 'var(--primary-light)' : undefined }}>
                        <td>{selectedId === item.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</td>
                        <td style={{ fontWeight: 500 }}>{item.cliente_nombre}</td>
                        <td style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>{item.tipo_origen || 'manual'}{item.documento_referencia ? ` - ${item.documento_referencia}` : ''}</td>
                        <td style={{ color: isVencido(item.fecha_vencimiento) && item.estado !== 'cobrada' ? '#EF4444' : 'inherit', display: 'flex', alignItems: 'center', gap: 4 }}>
                          {isVencido(item.fecha_vencimiento) && item.estado !== 'cobrada' && <AlertTriangle size={14} color="#EF4444" />}
                          {fmtDate(item.fecha_vencimiento)}
                          {item.dias_atraso > 0 && item.estado !== 'cobrada' && <span style={{ fontSize: '0.7rem', color: '#EF4444', marginLeft: 4 }}>({item.dias_atraso}d)</span>}
                        </td>
                        <td className="text-right">{fmt(item.monto_original)}</td>
                        <td className="text-right" style={{ color: '#3B82F6' }}>{fmt(item.total_abonado)}</td>
                        <td className="text-right" style={{ fontWeight: 600, color: item.saldo_pendiente > 0 ? 'var(--primary)' : '#22C55E' }}>{fmt(item.saldo_pendiente)}</td>
                        <td>
                          <span className={`badge ${item.estado === 'pendiente' ? 'badge-warning' : item.estado === 'parcial' ? 'badge-info' : item.estado === 'cobrada' ? 'badge-success' : 'badge-neutral'}`}>
                            {item.estado}
                          </span>
                        </td>
                        <td>
                          {item.estado !== 'cobrada' && item.estado !== 'anulada' && (
                            <button className="btn btn-outline" style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}
                              onClick={e => { e.stopPropagation(); setSelectedId(item.id); setShowAbono(true); getCxCAbonos(item.id).then(r => setAbonos(r.data || [])); }}
                              data-testid={`abono-btn-${item.id}`}>
                              <DollarSign size={12} /> Abonar
                            </button>
                          )}
                        </td>
                      </tr>
                      {/* Detail row */}
                      {selectedId === item.id && (
                        <tr>
                          <td colSpan={9} style={{ padding: '0.75rem 1rem', background: '#F8FAFC' }}>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                              <div>
                                <div style={{ fontSize: '0.75rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--muted)', textTransform: 'uppercase' }}>Detalle</div>
                                <div style={{ fontSize: '0.8rem' }}>
                                  {item.marca_nombre && <div>Marca: <strong>{item.marca_nombre}</strong></div>}
                                  {item.tipo_origen && <div>Tipo: {item.tipo_origen}</div>}
                                  {item.notas && <div>Notas: {item.notas}</div>}
                                </div>
                              </div>
                              <div>
                                <div style={{ fontSize: '0.75rem', fontWeight: 600, marginBottom: '0.5rem', color: 'var(--muted)', textTransform: 'uppercase' }}>Abonos ({abonos.length})</div>
                                {abonos.length === 0 ? (
                                  <div style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>Sin abonos registrados</div>
                                ) : (
                                  <div style={{ fontSize: '0.8rem' }}>
                                    {abonos.map(a => (
                                      <div key={a.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.2rem 0', borderBottom: '1px solid var(--border)' }}>
                                        <span>{fmtDate(a.fecha)} - {a.forma_pago}</span>
                                        <span style={{ fontWeight: 600 }}>{fmt(a.monto)}</span>
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {/* Abono Modal */}
      {showAbono && selected && (
        <div className="modal-overlay" onClick={() => setShowAbono(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 420 }} data-testid="abono-modal">
            <div className="modal-header">
              <h3>Registrar Abono</h3>
              <button onClick={() => setShowAbono(false)} className="modal-close"><X size={18} /></button>
            </div>
            <div style={{ padding: '1rem', fontSize: '0.85rem', background: 'var(--card-bg-hover)', borderBottom: '1px solid var(--border)' }}>
              <div>Cliente: <strong>{selected.cliente_nombre}</strong></div>
              <div>Saldo pendiente: <strong style={{ color: 'var(--primary)' }}>{fmt(selected.saldo_pendiente)}</strong></div>
            </div>
            <form onSubmit={handleAbono} style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div>
                <label className="form-label required">Fecha</label>
                <input type="date" className="form-input" value={abonoForm.fecha} onChange={e => setAbonoForm(p => ({ ...p, fecha: e.target.value }))} required data-testid="abono-fecha" />
              </div>
              <div>
                <label className="form-label required">Monto</label>
                <input type="number" step="0.01" className="form-input" value={abonoForm.monto} onChange={e => setAbonoForm(p => ({ ...p, monto: e.target.value }))} required placeholder={`Max: ${selected.saldo_pendiente}`} data-testid="abono-monto" />
              </div>
              <div>
                <label className="form-label">Forma de Pago</label>
                <select className="form-input" value={abonoForm.forma_pago} onChange={e => setAbonoForm(p => ({ ...p, forma_pago: e.target.value }))} data-testid="abono-forma-pago">
                  <option value="efectivo">Efectivo</option>
                  <option value="transferencia">Transferencia</option>
                  <option value="yape">Yape</option>
                  <option value="plin">Plin</option>
                  <option value="tarjeta">Tarjeta</option>
                </select>
              </div>
              <div>
                <label className="form-label">Cuenta Destino</label>
                <select className="form-input" value={abonoForm.cuenta_financiera_id} onChange={e => setAbonoForm(p => ({ ...p, cuenta_financiera_id: e.target.value }))} data-testid="abono-cuenta">
                  <option value="">Sin asignar</option>
                  {cuentas.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
                </select>
              </div>
              <div>
                <label className="form-label">Referencia</label>
                <input className="form-input" value={abonoForm.referencia} onChange={e => setAbonoForm(p => ({ ...p, referencia: e.target.value }))} placeholder="Nro operacion" data-testid="abono-referencia" />
              </div>
              <button type="submit" className="btn btn-primary" disabled={saving} data-testid="submit-abono-btn" style={{ marginTop: '0.5rem' }}>
                {saving ? 'Guardando...' : 'Registrar Abono'}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Create CxC Modal */}
      {showCreate && (
        <div className="modal-overlay" onClick={() => setShowCreate(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 420 }} data-testid="create-cxc-modal">
            <div className="modal-header">
              <h3>Nueva Cuenta por Cobrar</h3>
              <button onClick={() => setShowCreate(false)} className="modal-close"><X size={18} /></button>
            </div>
            <form onSubmit={handleCreate} style={{ padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div>
                <label className="form-label">Cliente</label>
                <select className="form-input" value={createForm.cliente_id} onChange={e => setCreateForm(p => ({ ...p, cliente_id: e.target.value }))} data-testid="create-cliente">
                  <option value="">Sin asignar</option>
                  {clientes.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
                </select>
              </div>
              <div>
                <label className="form-label required">Monto</label>
                <input type="number" step="0.01" className="form-input" value={createForm.monto_original} onChange={e => setCreateForm(p => ({ ...p, monto_original: e.target.value }))} required data-testid="create-monto" />
              </div>
              <div>
                <label className="form-label">Fecha Vencimiento</label>
                <input type="date" className="form-input" value={createForm.fecha_vencimiento} onChange={e => setCreateForm(p => ({ ...p, fecha_vencimiento: e.target.value }))} data-testid="create-vencimiento" />
              </div>
              <div>
                <label className="form-label">Doc. Referencia</label>
                <input className="form-input" value={createForm.documento_referencia} onChange={e => setCreateForm(p => ({ ...p, documento_referencia: e.target.value }))} data-testid="create-referencia" />
              </div>
              <div>
                <label className="form-label">Notas</label>
                <textarea className="form-input" rows={2} value={createForm.notas} onChange={e => setCreateForm(p => ({ ...p, notas: e.target.value }))} data-testid="create-notas" />
              </div>
              <button type="submit" className="btn btn-primary" disabled={saving} data-testid="submit-create-cxc-btn" style={{ marginTop: '0.5rem' }}>
                {saving ? 'Guardando...' : 'Crear CxC'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
