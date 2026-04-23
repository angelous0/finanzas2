import React, { useState, useEffect } from 'react';
import { getMarcas, createMarca, updateMarca, deleteMarca } from '../services/api';
import { useEmpresa } from '../context/EmpresaContext';
import { Plus, Edit, Trash2, Tag } from 'lucide-react';
import { toast } from 'sonner';

const Marcas = () => {
  const { empresaActual } = useEmpresa();
  const [marcas, setMarcas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ nombre: '', codigo: '', odoo_marca_key: '', activo: true });

  const loadMarcas = async () => {
    try { setLoading(true); const r = await getMarcas(); setMarcas(r.data); }
    catch { toast.error('Error al cargar marcas'); }
    finally { setLoading(false); }
  };
  useEffect(() => { loadMarcas(); }, [empresaActual]);

  const openNew = () => { setEditing(null); setForm({ nombre: '', codigo: '', odoo_marca_key: '', activo: true }); setShowModal(true); };
  const openEdit = (m) => { setEditing(m); setForm({ nombre: m.nombre, codigo: m.codigo || '', odoo_marca_key: m.odoo_marca_key || '', activo: m.activo }); setShowModal(true); };

  const handleSave = async () => {
    if (!form.nombre.trim()) { toast.error('Nombre es requerido'); return; }
    try {
      if (editing) { await updateMarca(editing.id, form); toast.success('Marca actualizada'); }
      else { await createMarca(form); toast.success('Marca creada'); }
      setShowModal(false); loadMarcas();
    } catch { toast.error('Error al guardar marca'); }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Eliminar esta marca?')) return;
    try { await deleteMarca(id); toast.success('Marca eliminada'); loadMarcas(); }
    catch { toast.error('Error al eliminar marca'); }
  };

  return (
    <div data-testid="marcas-page">
      <div className="page-header">
        <div><h1 className="page-title">Marcas</h1><p className="page-subtitle">Gestion de marcas del grupo empresarial</p></div>
        <button className="btn btn-primary" onClick={openNew} data-testid="nueva-marca-btn"><Plus size={18} /> Nueva Marca</button>
      </div>
      <div className="page-content">
        <div className="card">
          <div className="data-table-wrapper">
            {loading ? (
              <div className="loading"><div className="loading-spinner"></div></div>
            ) : marcas.length === 0 ? (
              <div className="empty-state">
                <Tag className="empty-state-icon" />
                <div className="empty-state-title">No hay marcas</div>
                <div className="empty-state-description" style={{ marginTop: '0.5rem', maxWidth: 480, textAlign: 'center' }}>
                  Las marcas de Finanzas son independientes de las marcas de Producción.<br />
                  Úsalas para agrupar ventas POS y reportes financieros por marca comercial.<br />
                  <span style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>
                    Puedes crear una marca nueva con el botón <strong>Nueva Marca</strong>.
                  </span>
                </div>
              </div>
            ) : (
              <table className="data-table" data-testid="marcas-table">
                <thead><tr><th>Nombre</th><th>Codigo</th><th>Key Odoo</th><th>Estado</th><th className="text-center">Acciones</th></tr></thead>
                <tbody>
                  {marcas.map(m => (
                    <tr key={m.id}>
                      <td style={{ fontWeight: 600 }}>{m.nombre}</td>
                      <td>{m.codigo || '-'}</td>
                      <td style={{ color: 'var(--muted)', fontSize: '0.875rem' }}>{m.odoo_marca_key || '-'}</td>
                      <td><span style={{ padding: '0.25rem 0.75rem', borderRadius: '9999px', fontSize: '0.75rem', fontWeight: 500, backgroundColor: m.activo ? '#d1fae5' : '#fee2e2', color: m.activo ? '#065f46' : '#991b1b' }}>{m.activo ? 'Activa' : 'Inactiva'}</span></td>
                      <td className="text-center">
                        <div style={{ display: 'flex', gap: '0.25rem', justifyContent: 'center' }}>
                          <button className="btn btn-outline btn-sm btn-icon" onClick={() => openEdit(m)} title="Editar"><Edit size={14} /></button>
                          <button className="btn btn-outline btn-sm btn-icon" onClick={() => handleDelete(m.id)} title="Eliminar" style={{ color: 'var(--danger-text)' }}><Trash2 size={14} /></button>
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
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: '500px' }}>
            <div className="modal-header"><h2 className="modal-title">{editing ? 'Editar' : 'Nueva'} Marca</h2><button className="modal-close" onClick={() => setShowModal(false)}>x</button></div>
            <div className="modal-body">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div><label className="form-label">Nombre *</label><input type="text" className="form-input" value={form.nombre} onChange={e => setForm({...form, nombre: e.target.value})} data-testid="marca-nombre-input" /></div>
                <div><label className="form-label">Codigo</label><input type="text" className="form-input" value={form.codigo} onChange={e => setForm({...form, codigo: e.target.value})} /></div>
                <div><label className="form-label">Key Odoo (mapeo a v_pos_line_full.marca)</label><input type="text" className="form-input" value={form.odoo_marca_key} onChange={e => setForm({...form, odoo_marca_key: e.target.value})} /></div>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                  <input type="checkbox" checked={form.activo} onChange={e => setForm({...form, activo: e.target.checked})} style={{ width: '18px', height: '18px' }} /> Activa
                </label>
              </div>
            </div>
            <div className="modal-footer"><button className="btn btn-outline" onClick={() => setShowModal(false)}>Cancelar</button><button className="btn btn-primary" onClick={handleSave}>Guardar</button></div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Marcas;
