import React, { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { Plus, Pencil, Trash2, Save, X, Users, Building2 } from 'lucide-react';
import {
  getUnidadesInternas, createUnidadInterna, updateUnidadInterna, deleteUnidadInterna,
  getPersonasProduccion, updatePersonaTipo
} from '../services/api';

const TIPOS_UNIDAD = ['CORTE', 'COSTURA', 'ACABADO', 'LAVANDERIA', 'ESTAMPADO', 'BORDADO', 'OTRO'];

export default function UnidadesInternas() {
  const [unidades, setUnidades] = useState([]);
  const [personas, setPersonas] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState(null);
  const [form, setForm] = useState({ nombre: '', tipo: '' });
  const [tab, setTab] = useState('unidades'); // 'unidades' | 'personas'

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [uRes, pRes] = await Promise.all([getUnidadesInternas(), getPersonasProduccion()]);
      setUnidades(uRes.data || []);
      setPersonas(pRes.data || []);
    } catch (e) {
      toast.error('Error al cargar datos');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSave = async () => {
    if (!form.nombre.trim()) { toast.error('Nombre es requerido'); return; }
    try {
      if (editId) {
        await updateUnidadInterna(editId, form);
        toast.success('Unidad actualizada');
      } else {
        await createUnidadInterna(form);
        toast.success('Unidad creada');
      }
      setShowForm(false); setEditId(null); setForm({ nombre: '', tipo: '' });
      loadData();
    } catch (e) {
      toast.error('Error al guardar');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Eliminar unidad?')) return;
    try {
      await deleteUnidadInterna(id);
      toast.success('Eliminado');
      loadData();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error al eliminar');
    }
  };

  const handlePersonaTipo = async (personaId, tipo, unidadId) => {
    try {
      await updatePersonaTipo(personaId, {
        tipo_persona: tipo,
        unidad_interna_id: tipo === 'INTERNO' ? unidadId : null
      });
      toast.success('Persona actualizada');
      loadData();
    } catch (e) {
      toast.error('Error al actualizar persona');
    }
  };

  const s = {
    page: { padding: '1.5rem', maxWidth: 1200, margin: '0 auto' },
    header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' },
    title: { fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-heading)', display: 'flex', alignItems: 'center', gap: 10 },
    tabs: { display: 'flex', gap: 4, background: 'var(--card-bg-alt)', borderRadius: 8, padding: 3, marginBottom: '1rem' },
    tab: (active) => ({
      padding: '8px 16px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600,
      background: active ? 'var(--card-bg)' : 'transparent', color: active ? 'var(--text-heading)' : 'var(--muted)',
      boxShadow: active ? '0 1px 3px rgba(0,0,0,0.1)' : 'none', transition: 'all 0.15s'
    }),
    card: { background: 'var(--card-bg)', borderRadius: 10, border: '1px solid var(--border)', overflow: 'hidden' },
    table: { width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' },
    th: { padding: '10px 14px', textAlign: 'left', fontWeight: 600, color: 'var(--muted)', borderBottom: '2px solid var(--border)', background: 'var(--card-bg-hover)', fontSize: '0.75rem', textTransform: 'uppercase' },
    td: { padding: '10px 14px', borderBottom: '1px solid var(--table-row-border)' },
    btn: { padding: '6px 14px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 6 },
    btnPrimary: { background: '#3b82f6', color: 'var(--card-bg)' },
    btnGreen: { background: '#16a34a', color: 'var(--card-bg)' },
    btnGhost: { background: 'transparent', color: 'var(--muted)', border: '1px solid var(--border)' },
    formOverlay: { position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 },
    formCard: { background: 'var(--card-bg)', borderRadius: 12, padding: '1.5rem', width: 420, boxShadow: '0 10px 40px rgba(0,0,0,0.15)' },
    input: { width: '100%', padding: '8px 12px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: '0.85rem', boxSizing: 'border-box' },
    select: { width: '100%', padding: '8px 12px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: '0.85rem', background: 'var(--card-bg)', boxSizing: 'border-box' },
    badge: (color) => ({
      padding: '2px 8px', borderRadius: 4, fontSize: '0.7rem', fontWeight: 700,
      background: color === 'green' ? '#dcfce7' : color === 'blue' ? '#dbeafe' : 'var(--card-bg-alt)',
      color: color === 'green' ? '#15803d' : color === 'blue' ? '#1d4ed8' : 'var(--muted)'
    }),
  };

  return (
    <div style={s.page} data-testid="unidades-internas-page">
      <div style={s.header}>
        <div style={s.title}><Building2 size={22} /> Unidades Internas</div>
        {tab === 'unidades' && (
          <button style={{ ...s.btn, ...s.btnPrimary }} data-testid="add-unidad-btn"
            onClick={() => { setForm({ nombre: '', tipo: '' }); setEditId(null); setShowForm(true); }}>
            <Plus size={16} /> Nueva Unidad
          </button>
        )}
      </div>

      <div style={s.tabs}>
        <button style={s.tab(tab === 'unidades')} onClick={() => setTab('unidades')} data-testid="tab-unidades">
          <Building2 size={14} style={{ marginRight: 4, verticalAlign: 'middle' }} /> Unidades ({unidades.length})
        </button>
        <button style={s.tab(tab === 'personas')} onClick={() => setTab('personas')} data-testid="tab-personas">
          <Users size={14} style={{ marginRight: 4, verticalAlign: 'middle' }} /> Personas ({personas.length})
        </button>
      </div>

      {tab === 'unidades' && (
        <div style={s.card}>
          <table style={s.table}>
            <thead>
              <tr>
                <th style={s.th}>Nombre</th>
                <th style={s.th}>Tipo</th>
                <th style={s.th}>Estado</th>
                <th style={s.th}>Personas</th>
                <th style={{ ...s.th, textAlign: 'right' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {unidades.length === 0 && (
                <tr><td colSpan={5} style={{ ...s.td, textAlign: 'center', color: 'var(--muted)', padding: 32 }}>
                  No hay unidades internas. Cree la primera.
                </td></tr>
              )}
              {unidades.map(u => {
                const personasUnit = personas.filter(p => p.unidad_interna_id === u.id);
                return (
                  <tr key={u.id} data-testid={`unidad-row-${u.id}`}>
                    <td style={{ ...s.td, fontWeight: 600, color: 'var(--text-heading)' }}>{u.nombre}</td>
                    <td style={s.td}><span style={s.badge('blue')}>{u.tipo || '-'}</span></td>
                    <td style={s.td}><span style={s.badge(u.activo ? 'green' : '')}>{u.activo ? 'Activo' : 'Inactivo'}</span></td>
                    <td style={s.td}>{personasUnit.length > 0 ? personasUnit.map(p => p.nombre).join(', ') : <span style={{ color: 'var(--muted)' }}>Sin personas</span>}</td>
                    <td style={{ ...s.td, textAlign: 'right' }}>
                      <button style={{ ...s.btn, ...s.btnGhost, marginRight: 4 }}
                        onClick={() => { setForm({ nombre: u.nombre, tipo: u.tipo || '' }); setEditId(u.id); setShowForm(true); }}>
                        <Pencil size={14} />
                      </button>
                      <button style={{ ...s.btn, background: 'var(--danger-bg)', color: 'var(--danger-text)', border: '1px solid var(--danger-border)' }}
                        onClick={() => handleDelete(u.id)}><Trash2 size={14} /></button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'personas' && (
        <div style={s.card}>
          <div style={{ padding: '0.75rem 1rem', background: 'var(--warning-bg)', borderBottom: '1px solid #fde68a', fontSize: '0.8rem', color: 'var(--warning-text)' }}>
            Marque las personas como <strong>INTERNO</strong> y asigne su unidad interna correspondiente.
          </div>
          <table style={s.table}>
            <thead>
              <tr>
                <th style={s.th}>Persona</th>
                <th style={s.th}>Tipo Actual</th>
                <th style={s.th}>Tipo Persona</th>
                <th style={s.th}>Unidad Interna</th>
              </tr>
            </thead>
            <tbody>
              {personas.length === 0 && (
                <tr><td colSpan={4} style={{ ...s.td, textAlign: 'center', color: 'var(--muted)', padding: 32 }}>
                  No hay personas de producción.
                </td></tr>
              )}
              {personas.map(p => (
                <tr key={p.id} data-testid={`persona-row-${p.id}`}>
                  <td style={{ ...s.td, fontWeight: 600 }}>{p.nombre}</td>
                  <td style={s.td}><span style={s.badge(p.tipo === 'externo' ? '' : 'blue')}>{p.tipo || 'N/A'}</span></td>
                  <td style={s.td}>
                    <select style={{ ...s.select, width: 130 }} value={p.tipo_persona || 'EXTERNO'}
                      onChange={(e) => handlePersonaTipo(p.id, e.target.value, p.unidad_interna_id)}>
                      <option value="EXTERNO">EXTERNO</option>
                      <option value="INTERNO">INTERNO</option>
                    </select>
                  </td>
                  <td style={s.td}>
                    {(p.tipo_persona === 'INTERNO') ? (
                      <select style={{ ...s.select, width: 200 }} value={p.unidad_interna_id || ''}
                        onChange={(e) => handlePersonaTipo(p.id, 'INTERNO', e.target.value ? parseInt(e.target.value) : null)}>
                        <option value="">-- Seleccione --</option>
                        {unidades.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}
                      </select>
                    ) : <span style={{ color: 'var(--muted)' }}>N/A</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Form Modal */}
      {showForm && (
        <div style={s.formOverlay} onClick={() => setShowForm(false)}>
          <div style={s.formCard} onClick={e => e.stopPropagation()} data-testid="unidad-form-modal">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-heading)', margin: 0 }}>
                {editId ? 'Editar Unidad' : 'Nueva Unidad Interna'}
              </h3>
              <button style={{ background: 'none', border: 'none', cursor: 'pointer' }} onClick={() => setShowForm(false)}>
                <X size={18} color="#94a3b8" />
              </button>
            </div>
            <div style={{ marginBottom: '0.75rem' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Nombre</label>
              <input style={s.input} value={form.nombre} onChange={e => setForm({ ...form, nombre: e.target.value })}
                placeholder="Ej: Corte Interno" data-testid="unidad-nombre-input" />
            </div>
            <div style={{ marginBottom: '1rem' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--muted)', display: 'block', marginBottom: 4 }}>Tipo</label>
              <select style={s.select} value={form.tipo} onChange={e => setForm({ ...form, tipo: e.target.value })} data-testid="unidad-tipo-select">
                <option value="">-- Seleccione --</option>
                {TIPOS_UNIDAD.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button style={{ ...s.btn, ...s.btnGhost }} onClick={() => setShowForm(false)}>Cancelar</button>
              <button style={{ ...s.btn, ...s.btnGreen }} onClick={handleSave} data-testid="save-unidad-btn">
                <Save size={14} /> Guardar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
