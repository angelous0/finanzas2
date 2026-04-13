import React, { useState, useEffect } from 'react';
import { getCentrosCosto, createCentroCosto, updateCentroCosto, deleteCentroCosto } from '../services/api';
import { useEmpresa } from '../context/EmpresaContext';
import { Plus, Trash2, Target, X, Edit } from 'lucide-react';
import { toast } from 'sonner';

export const CentrosCosto = () => {
  const { empresaActual } = useEmpresa();

  const [centros, setCentros] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  
  const [formData, setFormData] = useState({ codigo: '', nombre: '', descripcion: '' });

  useEffect(() => { loadData(); }, [empresaActual]);

  const loadData = async () => {
    try {
      setLoading(true);
      const response = await getCentrosCosto();
      setCentros(response.data);
    } catch (error) {
      toast.error('Error al cargar centros de costo');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    try {
      if (editingId) {
        await updateCentroCosto(editingId, formData);
        toast.success('Centro de costo actualizado');
      } else {
        await createCentroCosto(formData);
        toast.success('Centro de costo creado');
      }
      setShowModal(false);
      resetForm();
      loadData();
    } catch (error) {
      toast.error('Error al guardar centro de costo');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = (centro) => {
    setFormData({ codigo: centro.codigo || '', nombre: centro.nombre, descripcion: centro.descripcion || '' });
    setEditingId(centro.id);
    setShowModal(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm('¿Eliminar este centro de costo?')) return;
    try {
      await deleteCentroCosto(id);
      toast.success('Centro de costo eliminado');
      loadData();
    } catch (error) {
      toast.error('Error al eliminar');
    }
  };

  const resetForm = () => {
    setFormData({ codigo: '', nombre: '', descripcion: '' });
    setEditingId(null);
  };

  return (
    <div data-testid="centros-costo-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Centros de Costo</h1>
          <p className="page-subtitle">{centros.length} centros</p>
        </div>
        <button className="btn btn-primary" onClick={() => { resetForm(); setShowModal(true); }} data-testid="nuevo-centro-btn">
          <Plus size={18} /> Nuevo Centro
        </button>
      </div>

      <div className="page-content">
        <div className="card">
          <div className="data-table-wrapper">
            {loading ? (
              <div className="loading"><div className="loading-spinner"></div></div>
            ) : centros.length === 0 ? (
              <div className="empty-state">
                <Target className="empty-state-icon" />
                <div className="empty-state-title">No hay centros de costo</div>
                <div className="empty-state-description">Crea tu primer centro para asignar gastos</div>
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Código</th>
                    <th>Nombre</th>
                    <th>Descripción</th>
                    <th className="text-center">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {centros.map((centro) => (
                    <tr key={centro.id}>
                      <td style={{ fontFamily: "'JetBrains Mono', monospace" }}>{centro.codigo || '-'}</td>
                      <td style={{ fontWeight: 500 }}>{centro.nombre}</td>
                      <td>{centro.descripcion || '-'}</td>
                      <td className="text-center" style={{ display: 'flex', gap: '0.25rem', justifyContent: 'center' }}>
                        <button className="btn btn-outline btn-sm btn-icon" onClick={() => handleEdit(centro)} title="Editar" data-testid={`edit-centro-${centro.id}`}>
                          <Edit size={14} />
                        </button>
                        <button className="btn btn-outline btn-sm btn-icon" onClick={() => handleDelete(centro.id)} title="Eliminar" data-testid={`delete-centro-${centro.id}`}>
                          <Trash2 size={14} />
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

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">{editingId ? 'Editar' : 'Nuevo'} Centro de Costo</h2>
              <button className="modal-close" onClick={() => setShowModal(false)}><X size={20} /></button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Código</label>
                  <input type="text" className="form-input" value={formData.codigo}
                    onChange={(e) => setFormData(prev => ({ ...prev, codigo: e.target.value }))} placeholder="CC-001" />
                </div>
                <div className="form-group">
                  <label className="form-label required">Nombre</label>
                  <input type="text" className="form-input" value={formData.nombre}
                    onChange={(e) => setFormData(prev => ({ ...prev, nombre: e.target.value }))} required data-testid="centro-nombre-input" />
                </div>
                <div className="form-group">
                  <label className="form-label">Descripción</label>
                  <textarea className="form-input" rows={2} value={formData.descripcion}
                    onChange={(e) => setFormData(prev => ({ ...prev, descripcion: e.target.value }))} />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-outline" onClick={() => setShowModal(false)}>Cancelar</button>
                <button type="submit" className="btn btn-primary" data-testid="guardar-centro-btn" disabled={submitting}>
                  {submitting ? 'Guardando...' : (editingId ? 'Guardar Cambios' : 'Crear')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default CentrosCosto;
