import React, { useState, useEffect, useCallback } from 'react';
import { Plus, Pencil, Trash2, Tag, X, Check, ChevronDown, ChevronRight } from 'lucide-react';
import { getCategorias, createCategoria, updateCategoria, deleteCategoria } from '../services/api';
import { toast } from 'sonner';

export default function CategoriasGasto() {
  const [categorias, setCategorias] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [formData, setFormData] = useState({ nombre: '', tipo: 'egreso', padre_id: null, descripcion: '' });
  const [collapsedGroups, setCollapsedGroups] = useState({});

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const res = await getCategorias('egreso');
      setCategorias(res.data);
    } catch {
      toast.error('Error cargando categorias');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const padres = categorias.filter(c => !c.padre_id).sort((a, b) => a.nombre.localeCompare(b.nombre));
  const hijos = categorias.filter(c => c.padre_id);

  const getChildren = (padreId) => hijos.filter(h => h.padre_id === padreId).sort((a, b) => a.nombre.localeCompare(b.nombre));

  const toggleGroup = (id) => setCollapsedGroups(prev => ({ ...prev, [id]: !prev[id] }));

  const resetForm = () => {
    setFormData({ nombre: '', tipo: 'egreso', padre_id: null, descripcion: '' });
    setEditingId(null);
    setShowForm(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.nombre.trim()) { toast.error('Nombre es requerido'); return; }
    try {
      const payload = {
        nombre: formData.nombre.trim(),
        tipo: 'egreso',
        padre_id: formData.padre_id ? parseInt(formData.padre_id) : null,
        descripcion: formData.descripcion?.trim() || null,
      };
      if (editingId) {
        await updateCategoria(editingId, payload);
        toast.success('Categoria actualizada');
      } else {
        await createCategoria(payload);
        toast.success('Categoria creada');
      }
      resetForm();
      loadData();
    } catch {
      toast.error('Error guardando categoria');
    }
  };

  const handleEdit = (cat) => {
    setFormData({
      nombre: cat.nombre,
      tipo: cat.tipo || 'egreso',
      padre_id: cat.padre_id || '',
      descripcion: cat.descripcion || '',
    });
    setEditingId(cat.id);
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    const children = getChildren(id);
    if (children.length > 0) {
      toast.error('No se puede eliminar: tiene subcategorias');
      return;
    }
    if (!window.confirm('Eliminar esta categoria?')) return;
    try {
      await deleteCategoria(id);
      toast.success('Categoria eliminada');
      loadData();
    } catch {
      toast.error('Error eliminando categoria');
    }
  };

  const thStyle = { padding: '0.6rem 1rem', textAlign: 'left', color: 'var(--muted)', fontWeight: 600, fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' };

  return (
    <div style={{ padding: '1.5rem', maxWidth: '900px' }} data-testid="categorias-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, color: 'var(--text-heading)' }}>Categorias</h1>
          <p style={{ fontSize: '0.8rem', color: 'var(--muted)', margin: '0.25rem 0 0' }}>
            Categorias para lineas de detalle de gastos ({categorias.length} total)
          </p>
        </div>
        <button className="btn btn-primary btn-sm" onClick={() => { resetForm(); setShowForm(true); }} data-testid="add-categoria-btn">
          <Plus size={14} /> Nueva Categoria
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} style={{
          background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: '8px',
          padding: '1rem', marginBottom: '1rem'
        }}>
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div style={{ flex: '0 0 160px' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-label)', display: 'block', marginBottom: '0.25rem' }}>Tipo</label>
              <select className="form-input" value={formData.padre_id || ''} onChange={e => setFormData(p => ({ ...p, padre_id: e.target.value || null }))}>
                <option value="">Categoria padre</option>
                {padres.map(p => (
                  <option key={p.id} value={p.id} disabled={editingId === p.id}>Subcategoria de: {p.nombre}</option>
                ))}
              </select>
            </div>
            <div style={{ flex: 1, minWidth: '200px' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-label)', display: 'block', marginBottom: '0.25rem' }}>Nombre</label>
              <input className="form-input" value={formData.nombre} onChange={e => setFormData(p => ({ ...p, nombre: e.target.value }))}
                placeholder="Ej: Telas, Servicios, Alquiler..." autoFocus data-testid="categoria-nombre-input" />
            </div>
            <div style={{ flex: 1, minWidth: '200px' }}>
              <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-label)', display: 'block', marginBottom: '0.25rem' }}>Descripcion</label>
              <input className="form-input" value={formData.descripcion} onChange={e => setFormData(p => ({ ...p, descripcion: e.target.value }))}
                placeholder="Opcional..." />
            </div>
            <button type="submit" className="btn btn-primary btn-sm" data-testid="categoria-save-btn">
              <Check size={14} /> {editingId ? 'Actualizar' : 'Crear'}
            </button>
            <button type="button" className="btn btn-outline btn-sm" onClick={resetForm}><X size={14} /></button>
          </div>
        </form>
      )}

      {loading ? (
        <div className="loading"><div className="loading-spinner"></div></div>
      ) : categorias.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--muted)' }}>
          <Tag size={40} style={{ margin: '0 auto 0.5rem', opacity: 0.3 }} />
          <p style={{ fontSize: '0.875rem' }}>No hay categorias. Crea la primera.</p>
        </div>
      ) : (
        <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem' }} data-testid="categorias-table">
            <thead>
              <tr style={{ borderBottom: '2px solid var(--border)', background: 'var(--card-bg-hover)' }}>
                <th style={{ ...thStyle, width: '40%' }}>Nombre</th>
                <th style={{ ...thStyle, width: '35%' }}>Descripcion</th>
                <th style={{ ...thStyle, width: '10%', textAlign: 'center' }}>Codigo</th>
                <th style={{ ...thStyle, width: '15%', textAlign: 'right' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {padres.map(padre => {
                const children = getChildren(padre.id);
                const isCollapsed = collapsedGroups[padre.id];
                return (
                  <React.Fragment key={padre.id}>
                    {/* Parent row */}
                    <tr style={{
                      background: 'var(--card-bg-alt)',
                      borderBottom: '1px solid var(--border)',
                      borderTop: '2px solid var(--border)',
                    }}>
                      <td style={{ padding: '0.6rem 1rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          {children.length > 0 && (
                            <button
                              type="button"
                              onClick={() => toggleGroup(padre.id)}
                              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', color: 'var(--muted)' }}
                            >
                              {isCollapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
                            </button>
                          )}
                          {children.length === 0 && <span style={{ width: 16 }} />}
                          <span style={{ fontWeight: 600, color: 'var(--text-heading)', fontSize: '0.8125rem' }}>
                            {padre.nombre}
                          </span>
                          {children.length > 0 && (
                            <span style={{
                              fontSize: '0.6875rem', background: 'var(--badge-bg)', color: 'var(--text-label)',
                              padding: '1px 8px', borderRadius: '10px', fontWeight: 500
                            }}>
                              {children.length} subcategoria{children.length !== 1 ? 's' : ''}
                            </span>
                          )}
                        </div>
                      </td>
                      <td style={{ padding: '0.6rem 1rem', color: 'var(--muted)', fontSize: '0.8rem' }}>
                        {padre.descripcion || ''}
                      </td>
                      <td style={{ padding: '0.6rem 1rem', textAlign: 'center', color: 'var(--muted)', fontSize: '0.75rem', fontFamily: "'JetBrains Mono', monospace" }}>
                        {padre.codigo || '-'}
                      </td>
                      <td style={{ padding: '0.6rem 1rem', textAlign: 'right' }}>
                        <button className="btn btn-outline btn-sm" onClick={() => handleEdit(padre)} style={{ marginRight: '0.25rem' }} data-testid={`edit-cat-${padre.id}`}>
                          <Pencil size={13} />
                        </button>
                        <button className="btn btn-outline btn-sm" onClick={() => handleDelete(padre.id)} style={{ color: 'var(--error)' }} data-testid={`delete-cat-${padre.id}`}>
                          <Trash2 size={13} />
                        </button>
                      </td>
                    </tr>
                    {/* Children rows */}
                    {!isCollapsed && children.map(child => (
                      <tr key={child.id} style={{ borderBottom: '1px solid var(--table-row-border)' }}>
                        <td style={{ padding: '0.5rem 1rem', paddingLeft: '2.5rem' }}>
                          <span style={{ color: 'var(--muted)', marginRight: '0.4rem' }}>&lsaquo;</span>
                          <span style={{ color: 'var(--text-secondary)' }}>{child.nombre}</span>
                        </td>
                        <td style={{ padding: '0.5rem 1rem', color: 'var(--muted)', fontSize: '0.8rem' }}>
                          {child.descripcion || ''}
                        </td>
                        <td style={{ padding: '0.5rem 1rem', textAlign: 'center', color: 'var(--muted)', fontSize: '0.75rem', fontFamily: "'JetBrains Mono', monospace" }}>
                          {child.codigo || '-'}
                        </td>
                        <td style={{ padding: '0.5rem 1rem', textAlign: 'right' }}>
                          <button className="btn btn-outline btn-sm" onClick={() => handleEdit(child)} style={{ marginRight: '0.25rem' }} data-testid={`edit-cat-${child.id}`}>
                            <Pencil size={13} />
                          </button>
                          <button className="btn btn-outline btn-sm" onClick={() => handleDelete(child.id)} style={{ color: 'var(--error)' }} data-testid={`delete-cat-${child.id}`}>
                            <Trash2 size={13} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </React.Fragment>
                );
              })}
              {/* Orphan children (padre not in list) */}
              {hijos.filter(h => !padres.find(p => p.id === h.padre_id)).map(cat => (
                <tr key={cat.id} style={{ borderBottom: '1px solid var(--table-row-border)' }}>
                  <td style={{ padding: '0.5rem 1rem', paddingLeft: '2.5rem' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>{cat.nombre_completo || cat.nombre}</span>
                  </td>
                  <td style={{ padding: '0.5rem 1rem', color: 'var(--muted)', fontSize: '0.8rem' }}>
                    {cat.descripcion || ''}
                  </td>
                  <td style={{ padding: '0.5rem 1rem', textAlign: 'center', color: 'var(--muted)', fontSize: '0.75rem' }}>
                    {cat.codigo || '-'}
                  </td>
                  <td style={{ padding: '0.5rem 1rem', textAlign: 'right' }}>
                    <button className="btn btn-outline btn-sm" onClick={() => handleEdit(cat)} style={{ marginRight: '0.25rem' }}><Pencil size={13} /></button>
                    <button className="btn btn-outline btn-sm" onClick={() => handleDelete(cat.id)} style={{ color: 'var(--error)' }}><Trash2 size={13} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
