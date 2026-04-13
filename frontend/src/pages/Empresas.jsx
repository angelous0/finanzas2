import React, { useState, useEffect } from 'react';
import { getEmpresas, createEmpresa, updateEmpresa, deleteEmpresa } from '../services/api';
import { Plus, Edit2, Trash2, Building2, X } from 'lucide-react';
import { toast } from 'sonner';

export const Empresas = () => {
  const [empresas, setEmpresas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  
  const [formData, setFormData] = useState({
    nombre: '',
    ruc: '',
    direccion: '',
    telefono: '',
    email: ''
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const response = await getEmpresas();
      setEmpresas(response.data);
    } catch (error) {
      console.error('Error loading empresas:', error);
      toast.error('Error al cargar empresas');
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
        await updateEmpresa(editingId, formData);
        toast.success('Empresa actualizada');
      } else {
        await createEmpresa(formData);
        toast.success('Empresa creada');
      }
      setShowModal(false);
      resetForm();
      loadData();
    } catch (error) {
      console.error('Error saving:', error);
      toast.error('Error al guardar empresa');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = (empresa) => {
    setFormData({
      nombre: empresa.nombre || '',
      ruc: empresa.ruc || '',
      direccion: empresa.direccion || '',
      telefono: empresa.telefono || '',
      email: empresa.email || ''
    });
    setEditingId(empresa.id);
    setShowModal(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm('¿Eliminar esta empresa?')) return;
    try {
      await deleteEmpresa(id);
      toast.success('Empresa eliminada');
      loadData();
    } catch (error) {
      console.error('Error deleting:', error);
      toast.error('Error al eliminar');
    }
  };

  const resetForm = () => {
    setFormData({
      nombre: '',
      ruc: '',
      direccion: '',
      telefono: '',
      email: ''
    });
    setEditingId(null);
  };

  return (
    <div data-testid="empresas-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Empresas</h1>
          <p className="page-subtitle">{empresas.length} empresas</p>
        </div>
        <button 
          className="btn btn-primary"
          onClick={() => { resetForm(); setShowModal(true); }}
          data-testid="nueva-empresa-btn"
        >
          <Plus size={18} />
          Nueva Empresa
        </button>
      </div>

      <div className="page-content">
        <div className="card">
          <div className="data-table-wrapper">
            {loading ? (
              <div className="loading">
                <div className="loading-spinner"></div>
              </div>
            ) : empresas.length === 0 ? (
              <div className="empty-state">
                <Building2 className="empty-state-icon" />
                <div className="empty-state-title">No hay empresas registradas</div>
                <div className="empty-state-description">Agrega tu primera empresa para comenzar</div>
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>RUC</th>
                    <th>Nombre / Razón Social</th>
                    <th>Dirección</th>
                    <th>Contacto</th>
                    <th className="text-center">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {empresas.map((empresa) => (
                    <tr key={empresa.id}>
                      <td style={{ fontFamily: "'JetBrains Mono', monospace" }}>{empresa.ruc || '-'}</td>
                      <td style={{ fontWeight: 500 }}>{empresa.nombre}</td>
                      <td>{empresa.direccion || '-'}</td>
                      <td>
                        {empresa.telefono && <div>{empresa.telefono}</div>}
                        {empresa.email && <div style={{ color: 'var(--muted)', fontSize: '0.8125rem' }}>{empresa.email}</div>}
                      </td>
                      <td className="text-center">
                        <div style={{ display: 'flex', gap: '0.25rem', justifyContent: 'center' }}>
                          <button 
                            className="btn btn-outline btn-sm btn-icon"
                            onClick={() => handleEdit(empresa)}
                            data-testid={`edit-empresa-${empresa.id}`}
                          >
                            <Edit2 size={14} />
                          </button>
                          <button 
                            className="btn btn-outline btn-sm btn-icon"
                            onClick={() => handleDelete(empresa.id)}
                            data-testid={`delete-empresa-${empresa.id}`}
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

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="modal-title">{editingId ? 'Editar Empresa' : 'Nueva Empresa'}</h2>
              <button className="modal-close" onClick={() => setShowModal(false)}>
                <X size={20} />
              </button>
            </div>
            
            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '1rem' }}>
                  <div className="form-group">
                    <label className="form-label">RUC</label>
                    <input
                      type="text"
                      className="form-input"
                      value={formData.ruc}
                      onChange={(e) => setFormData(prev => ({ ...prev, ruc: e.target.value }))}
                      placeholder="20123456789"
                      maxLength={11}
                    />
                  </div>
                  
                  <div className="form-group">
                    <label className="form-label required">Nombre / Razón Social</label>
                    <input
                      type="text"
                      className="form-input"
                      value={formData.nombre}
                      onChange={(e) => setFormData(prev => ({ ...prev, nombre: e.target.value }))}
                      required
                      data-testid="empresa-nombre-input"
                    />
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">Dirección</label>
                  <input
                    type="text"
                    className="form-input"
                    value={formData.direccion}
                    onChange={(e) => setFormData(prev => ({ ...prev, direccion: e.target.value }))}
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div className="form-group">
                    <label className="form-label">Teléfono</label>
                    <input
                      type="text"
                      className="form-input"
                      value={formData.telefono}
                      onChange={(e) => setFormData(prev => ({ ...prev, telefono: e.target.value }))}
                    />
                  </div>
                  
                  <div className="form-group">
                    <label className="form-label">Email</label>
                    <input
                      type="email"
                      className="form-input"
                      value={formData.email}
                      onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
                    />
                  </div>
                </div>
              </div>

              <div className="modal-footer">
                <button type="button" className="btn btn-outline" onClick={() => setShowModal(false)}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" data-testid="guardar-empresa-btn" disabled={submitting}>
                  {submitting ? 'Guardando...' : (editingId ? 'Guardar cambios' : 'Crear')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Empresas;
