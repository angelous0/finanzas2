import React, { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { Plus, Pencil, Trash2, Save, X, FileText, Calendar, Filter } from 'lucide-react';
import {
  getGastosUnidadInterna, createGastoUnidadInterna, updateGastoUnidadInterna,
  deleteGastoUnidadInterna, getUnidadesInternas
} from '../services/api';

const TIPOS_GASTO = ['PLANILLA_JORNAL', 'DESTAJO', 'GASTO_CORTE', 'ALQUILER', 'LUZ', 'MANTENIMIENTO', 'OTRO'];
const formatCurrency = (v) => `S/ ${(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function GastosUnidadInterna() {
  const [gastos, setGastos] = useState([]);
  const [unidades, setUnidades] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState(null);
  const [filtroUnidad, setFiltroUnidad] = useState('');
  const [form, setForm] = useState({
    fecha: new Date().toISOString().slice(0, 10),
    unidad_interna_id: '',
    tipo_gasto: '',
    descripcion: '',
    monto: '',
    registro_id: '',
    movimiento_id: ''
  });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const params = {};
      if (filtroUnidad) params.unidad_interna_id = filtroUnidad;
      const [gRes, uRes] = await Promise.all([getGastosUnidadInterna(params), getUnidadesInternas()]);
      setGastos(gRes.data || []);
      setUnidades(uRes.data || []);
    } catch (e) {
      toast.error('Error al cargar datos');
    } finally {
      setLoading(false);
    }
  }, [filtroUnidad]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSave = async () => {
    if (!form.unidad_interna_id || !form.tipo_gasto || !form.monto) {
      toast.error('Complete unidad, tipo y monto'); return;
    }
    try {
      const payload = {
        ...form,
        unidad_interna_id: parseInt(form.unidad_interna_id),
        monto: parseFloat(form.monto),
        registro_id: form.registro_id || null,
        movimiento_id: form.movimiento_id || null
      };
      if (editId) {
        await updateGastoUnidadInterna(editId, payload);
        toast.success('Gasto actualizado');
      } else {
        await createGastoUnidadInterna(payload);
        toast.success('Gasto registrado');
      }
      setShowForm(false); setEditId(null);
      setForm({ fecha: new Date().toISOString().slice(0, 10), unidad_interna_id: '', tipo_gasto: '', descripcion: '', monto: '', registro_id: '', movimiento_id: '' });
      loadData();
    } catch (e) {
      toast.error(typeof e.response?.data?.detail === 'string' ? e.response?.data?.detail : 'Error al guardar');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Eliminar gasto?')) return;
    try {
      await deleteGastoUnidadInterna(id);
      toast.success('Eliminado');
      loadData();
    } catch (e) {
      toast.error('Error al eliminar');
    }
  };

  const startEdit = (g) => {
    setForm({
      fecha: g.fecha?.slice(0, 10) || '',
      unidad_interna_id: g.unidad_interna_id?.toString() || '',
      tipo_gasto: g.tipo_gasto || '',
      descripcion: g.descripcion || '',
      monto: g.monto?.toString() || '',
      registro_id: g.registro_id || '',
      movimiento_id: g.movimiento_id || ''
    });
    setEditId(g.id);
    setShowForm(true);
  };

  const totalGastos = gastos.reduce((sum, g) => sum + (g.monto || 0), 0);

  const s = {
    page: { padding: '1.5rem', maxWidth: 1200, margin: '0 auto' },
    header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' },
    title: { fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-heading)', display: 'flex', alignItems: 'center', gap: 10 },
    card: { background: 'var(--card-bg)', borderRadius: 10, border: '1px solid var(--border)', overflow: 'hidden' },
    table: { width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' },
    th: { padding: '10px 14px', textAlign: 'left', fontWeight: 600, color: 'var(--muted)', borderBottom: '2px solid var(--border)', background: 'var(--card-bg-hover)', fontSize: '0.75rem', textTransform: 'uppercase' },
    td: { padding: '10px 14px', borderBottom: '1px solid var(--table-row-border)' },
    btn: { padding: '6px 14px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 6 },
    btnPrimary: { background: '#3b82f6', color: 'var(--card-bg)' },
    btnGreen: { background: '#16a34a', color: 'var(--card-bg)' },
    btnGhost: { background: 'transparent', color: 'var(--muted)', border: '1px solid var(--border)' },
    formOverlay: { position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 },
    formCard: { background: 'var(--card-bg)', borderRadius: 12, padding: '1.5rem', width: 480, boxShadow: '0 10px 40px rgba(0,0,0,0.15)' },
    input: { width: '100%', padding: '8px 12px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: '0.85rem', boxSizing: 'border-box' },
    select: { width: '100%', padding: '8px 12px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: '0.85rem', background: 'var(--card-bg)', boxSizing: 'border-box' },
    badge: (color) => ({
      padding: '2px 8px', borderRadius: 4, fontSize: '0.7rem', fontWeight: 700,
      background: color === 'red' ? '#fef2f2' : color === 'amber' ? '#fffbeb' : 'var(--card-bg-alt)',
      color: color === 'red' ? '#dc2626' : color === 'amber' ? '#d97706' : 'var(--muted)'
    }),
    filterBar: { display: 'flex', gap: 12, alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap' },
    summaryCard: { background: 'var(--danger-bg)', borderRadius: 8, padding: '0.75rem 1rem', display: 'flex', alignItems: 'center', gap: 12, marginBottom: '0.75rem' },
  };

  return (
    <div style={s.page} data-testid="gastos-unidad-page">
      <div style={s.header}>
        <div style={s.title}><FileText size={22} /> Gastos Unidad Interna</div>
        <button style={{ ...s.btn, ...s.btnPrimary }} onClick={() => {
          setForm({ fecha: new Date().toISOString().slice(0, 10), unidad_interna_id: '', tipo_gasto: '', descripcion: '', monto: '', registro_id: '', movimiento_id: '' });
          setEditId(null); setShowForm(true);
        }} data-testid="add-gasto-btn">
          <Plus size={16} /> Registrar Gasto
        </button>
      </div>

      <div style={s.filterBar}>
        <Filter size={16} color="#64748b" />
        <select style={{ ...s.select, width: 220 }} value={filtroUnidad}
          onChange={e => setFiltroUnidad(e.target.value)} data-testid="filtro-unidad-select">
          <option value="">Todas las unidades</option>
          {unidades.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}
        </select>
      </div>

      {gastos.length > 0 && (
        <div style={s.summaryCard}>
          <span style={{ fontWeight: 700, color: 'var(--danger-text)', fontSize: '0.85rem' }}>Total Gastos:</span>
          <span style={{ fontWeight: 800, color: 'var(--danger-text)', fontSize: '1rem', fontFamily: "'JetBrains Mono', monospace" }}>
            {formatCurrency(totalGastos)}
          </span>
          <span style={{ color: 'var(--muted)', fontSize: '0.75rem' }}>({gastos.length} registros)</span>
        </div>
      )}

      <div style={s.card}>
        <table style={s.table}>
          <thead>
            <tr>
              <th style={s.th}>Fecha</th>
              <th style={s.th}>Unidad</th>
              <th style={s.th}>Tipo Gasto</th>
              <th style={s.th}>Descripcion</th>
              <th style={{ ...s.th, textAlign: 'right' }}>Monto</th>
              <th style={s.th}>Registro</th>
              <th style={{ ...s.th, textAlign: 'right' }}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {gastos.length === 0 && (
              <tr><td colSpan={7} style={{ ...s.td, textAlign: 'center', color: 'var(--muted)', padding: 32 }}>
                No hay gastos registrados.
              </td></tr>
            )}
            {gastos.map(g => (
              <tr key={g.id} data-testid={`gasto-row-${g.id}`}>
                <td style={s.td}>{g.fecha?.slice(0, 10)}</td>
                <td style={{ ...s.td, fontWeight: 600 }}>{g.unidad_nombre || '-'}</td>
                <td style={s.td}><span style={s.badge('amber')}>{g.tipo_gasto}</span></td>
                <td style={s.td}>{g.descripcion || '-'}</td>
                <td style={{ ...s.td, textAlign: 'right', fontWeight: 700, color: 'var(--danger-text)', fontFamily: "'JetBrains Mono', monospace" }}>
                  {formatCurrency(g.monto)}
                </td>
                <td style={s.td}>{g.registro_id || g.movimiento_id ? <span style={s.badge('')}>{g.registro_id || g.movimiento_id}</span> : <span style={{ color: 'var(--muted)' }}>General</span>}</td>
                <td style={{ ...s.td, textAlign: 'right' }}>
                  <button style={{ ...s.btn, ...s.btnGhost, marginRight: 4 }} onClick={() => startEdit(g)}><Pencil size={14} /></button>
                  <button style={{ ...s.btn, background: 'var(--danger-bg)', color: 'var(--danger-text)', border: '1px solid var(--danger-border)' }}
                    onClick={() => handleDelete(g.id)}><Trash2 size={14} /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Form Modal */}
      {showForm && (
        <div style={s.formOverlay} onClick={() => setShowForm(false)}>
          <div style={s.formCard} onClick={e => e.stopPropagation()} data-testid="gasto-form-modal">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, margin: 0 }}>
                {editId ? 'Editar Gasto' : 'Registrar Gasto'}
              </h3>
              <button style={{ background: 'none', border: 'none', cursor: 'pointer' }} onClick={() => setShowForm(false)}>
                <X size={18} color="#94a3b8" />
              </button>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
              <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--muted)', marginBottom: 4, display: 'block' }}>Fecha</label>
                <input type="date" style={s.input} value={form.fecha} onChange={e => setForm({ ...form, fecha: e.target.value })} data-testid="gasto-fecha-input" />
              </div>
              <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--muted)', marginBottom: 4, display: 'block' }}>Unidad Interna</label>
                <select style={s.select} value={form.unidad_interna_id} onChange={e => setForm({ ...form, unidad_interna_id: e.target.value })} data-testid="gasto-unidad-select">
                  <option value="">-- Seleccione --</option>
                  {unidades.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}
                </select>
              </div>
              <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--muted)', marginBottom: 4, display: 'block' }}>Tipo de Gasto</label>
                <select style={s.select} value={form.tipo_gasto} onChange={e => setForm({ ...form, tipo_gasto: e.target.value })} data-testid="gasto-tipo-select">
                  <option value="">-- Seleccione --</option>
                  {TIPOS_GASTO.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--muted)', marginBottom: 4, display: 'block' }}>Monto</label>
                <input type="number" step="0.01" style={s.input} value={form.monto} onChange={e => setForm({ ...form, monto: e.target.value })}
                  placeholder="0.00" data-testid="gasto-monto-input" />
              </div>
              <div style={{ gridColumn: '1 / -1' }}>
                <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--muted)', marginBottom: 4, display: 'block' }}>Descripcion</label>
                <input style={s.input} value={form.descripcion} onChange={e => setForm({ ...form, descripcion: e.target.value })}
                  placeholder="Detalle del gasto" data-testid="gasto-desc-input" />
              </div>
              <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--muted)', marginBottom: 4, display: 'block' }}>Registro ID (opcional)</label>
                <input style={s.input} value={form.registro_id} onChange={e => setForm({ ...form, registro_id: e.target.value })} placeholder="ID de registro/corte" />
              </div>
              <div>
                <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--muted)', marginBottom: 4, display: 'block' }}>Movimiento ID (opcional)</label>
                <input style={s.input} value={form.movimiento_id} onChange={e => setForm({ ...form, movimiento_id: e.target.value })} placeholder="ID de movimiento" />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: '1rem' }}>
              <button style={{ ...s.btn, ...s.btnGhost }} onClick={() => setShowForm(false)}>Cancelar</button>
              <button style={{ ...s.btn, ...s.btnGreen }} onClick={handleSave} data-testid="save-gasto-btn">
                <Save size={14} /> Guardar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
