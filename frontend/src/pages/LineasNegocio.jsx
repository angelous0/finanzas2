import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getLineasNegocio, getLineaNegocioDetalle, createLineaNegocio, updateLineaNegocio, deleteLineaNegocio, getOdooLineasNegocioOpciones } from '../services/api';
import { useEmpresa } from '../context/EmpresaContext';
import { Plus, Trash2, GitBranch, X, Edit, Eye, ExternalLink, FileText, ArrowRightLeft, Receipt, Landmark, BarChart3 } from 'lucide-react';
import { toast } from 'sonner';

export const LineasNegocio = () => {
  const { empresaActual } = useEmpresa();
  const navigate = useNavigate();

  const [lineas, setLineas] = useState([]);
  const [odooOpciones, setOdooOpciones] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [detalleData, setDetalleData] = useState(null);
  const [showDetalle, setShowDetalle] = useState(false);
  const [loadingDetalle, setLoadingDetalle] = useState(false);
  
  const [formData, setFormData] = useState({ codigo: '', nombre: '', descripcion: '', odoo_linea_negocio_id: '', odoo_linea_negocio_nombre: '' });

  useEffect(() => { loadData(); }, [empresaActual]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [lineasRes, odooRes] = await Promise.all([
        getLineasNegocio(),
        getOdooLineasNegocioOpciones().catch(() => ({ data: [] }))
      ]);
      setLineas(lineasRes.data);
      setOdooOpciones(odooRes.data || []);
    } catch (error) {
      toast.error('Error al cargar lineas de negocio');
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
        await updateLineaNegocio(editingId, formData);
        toast.success('Línea de negocio actualizada');
      } else {
        await createLineaNegocio(formData);
        toast.success('Línea de negocio creada');
      }
      setShowModal(false);
      resetForm();
      loadData();
    } catch (error) {
      toast.error('Error al guardar línea de negocio');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = (linea) => {
    setFormData({
      codigo: linea.codigo || '', nombre: linea.nombre, descripcion: linea.descripcion || '',
      odoo_linea_negocio_id: linea.odoo_linea_negocio_id || '',
      odoo_linea_negocio_nombre: linea.odoo_linea_negocio_nombre || ''
    });
    setEditingId(linea.id);
    setShowModal(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm('¿Eliminar esta línea de negocio?')) return;
    try {
      await deleteLineaNegocio(id);
      toast.success('Línea de negocio eliminada');
      loadData();
    } catch (error) {
      const msg = error.response?.data?.detail || 'Error al eliminar';
      toast.error(msg);
      if (msg.includes('datos asociados')) {
        handleVerDetalle(id);
      }
    }
  };

  const handleVerDetalle = async (id) => {
    try {
      setLoadingDetalle(true);
      setShowDetalle(true);
      const res = await getLineaNegocioDetalle(id);
      setDetalleData(res.data);
    } catch (e) {
      toast.error('Error al cargar detalle');
      setShowDetalle(false);
    } finally {
      setLoadingDetalle(false);
    }
  };

  const resetForm = () => {
    setFormData({ codigo: '', nombre: '', descripcion: '', odoo_linea_negocio_id: '', odoo_linea_negocio_nombre: '' });
    setEditingId(null);
  };

  return (
    <div data-testid="lineas-negocio-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Líneas de Negocio</h1>
          <p className="page-subtitle">{lineas.length} líneas</p>
        </div>
        <button className="btn btn-primary" onClick={() => { resetForm(); setShowModal(true); }} data-testid="nueva-linea-btn">
          <Plus size={18} /> Nueva Línea
        </button>
      </div>

      <div className="page-content">
        <div className="card">
          <div className="data-table-wrapper">
            {loading ? (
              <div className="loading"><div className="loading-spinner"></div></div>
            ) : lineas.length === 0 ? (
              <div className="empty-state">
                <GitBranch className="empty-state-icon" />
                <div className="empty-state-title">No hay líneas de negocio</div>
                <div className="empty-state-description">Crea tu primera línea para organizar tus operaciones</div>
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Codigo</th>
                    <th>Nombre</th>
                    <th>Descripcion</th>
                    <th>Vinculo Odoo</th>
                    <th className="text-center">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {lineas.map((linea) => (
                    <tr key={linea.id}>
                      <td style={{ fontFamily: "'JetBrains Mono', monospace" }}>{linea.codigo || '-'}</td>
                      <td style={{ fontWeight: 500 }}>{linea.nombre}</td>
                      <td>{linea.descripcion || '-'}</td>
                      <td>
                        {linea.odoo_linea_negocio_id ? (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', padding: '0.2rem 0.6rem', backgroundColor: '#d1fae5', color: 'var(--success-text)', borderRadius: '9999px', fontSize: '0.75rem' }} data-testid={`odoo-mapped-${linea.id}`}>
                            {linea.odoo_linea_negocio_nombre || `ID: ${linea.odoo_linea_negocio_id}`}
                          </span>
                        ) : (
                          <span style={{ padding: '0.2rem 0.6rem', backgroundColor: 'var(--warning-bg)', color: 'var(--warning-text)', borderRadius: '9999px', fontSize: '0.75rem' }} data-testid={`odoo-unmapped-${linea.id}`}>
                            Sin vincular
                          </span>
                        )}
                      </td>
                      <td className="text-center" style={{ display: 'flex', gap: '0.25rem', justifyContent: 'center' }}>
                        <button className="btn btn-outline btn-sm btn-icon" onClick={() => handleVerDetalle(linea.id)} title="Ver vinculos" data-testid={`ver-linea-${linea.id}`}>
                          <Eye size={14} />
                        </button>
                        <button className="btn btn-outline btn-sm btn-icon" onClick={() => handleEdit(linea)} title="Editar" data-testid={`edit-linea-${linea.id}`}>
                          <Edit size={14} />
                        </button>
                        <button className="btn btn-outline btn-sm btn-icon" onClick={() => handleDelete(linea.id)} title="Eliminar" data-testid={`delete-linea-${linea.id}`}>
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
              <h2 className="modal-title">{editingId ? 'Editar' : 'Nueva'} Línea de Negocio</h2>
              <button className="modal-close" onClick={() => setShowModal(false)}><X size={20} /></button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="modal-body">
                <div className="form-group">
                  <label className="form-label">Código</label>
                  <input type="text" className="form-input" value={formData.codigo}
                    onChange={(e) => setFormData(prev => ({ ...prev, codigo: e.target.value }))} placeholder="LN-001" />
                </div>
                <div className="form-group">
                  <label className="form-label required">Nombre</label>
                  <input type="text" className="form-input" value={formData.nombre}
                    onChange={(e) => setFormData(prev => ({ ...prev, nombre: e.target.value }))} required data-testid="linea-nombre-input" />
                </div>
                <div className="form-group">
                  <label className="form-label">Descripcion</label>
                  <textarea className="form-input" rows={2} value={formData.descripcion}
                    onChange={(e) => setFormData(prev => ({ ...prev, descripcion: e.target.value }))} />
                </div>
                <div style={{ borderTop: '1px solid var(--border)', paddingTop: '1rem', marginTop: '0.5rem' }}>
                  <p style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--muted)', marginBottom: '0.75rem' }}>VINCULO CON ODOO</p>
                  <div className="form-group">
                    <label className="form-label">Linea de Negocio en Odoo</label>
                    {odooOpciones.length > 0 ? (
                      <select
                        className="form-input"
                        value={formData.odoo_linea_negocio_id || ''}
                        onChange={(e) => {
                          const val = e.target.value;
                          if (!val) {
                            setFormData(prev => ({ ...prev, odoo_linea_negocio_id: '', odoo_linea_negocio_nombre: '' }));
                          } else {
                            const opcion = odooOpciones.find(o => String(o.odoo_id) === val);
                            setFormData(prev => ({
                              ...prev,
                              odoo_linea_negocio_id: parseInt(val),
                              odoo_linea_negocio_nombre: opcion ? opcion.nombre : ''
                            }));
                          }
                        }}
                        data-testid="odoo-linea-select"
                      >
                        <option value="">-- Sin vincular --</option>
                        {odooOpciones.map(op => (
                          <option key={op.odoo_id} value={op.odoo_id}>
                            {op.nombre} (ID: {op.odoo_id})
                          </option>
                        ))}
                      </select>
                    ) : (
                      <div style={{ padding: '0.75rem', backgroundColor: '#fefce8', border: '1px solid var(--warning-border)', borderRadius: '8px', fontSize: '0.8rem', color: 'var(--warning-text)' }}>
                        No hay lineas de negocio sincronizadas desde Odoo. Ejecute el sync del extractor para cargar las opciones.
                        <div style={{ marginTop: '0.5rem', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                          <span style={{ color: 'var(--muted)' }}>Vinculo manual:</span>
                          <input type="number" className="form-input" style={{ width: '80px', padding: '0.25rem 0.5rem' }}
                            value={formData.odoo_linea_negocio_id || ''}
                            onChange={(e) => setFormData(prev => ({ ...prev, odoo_linea_negocio_id: e.target.value ? parseInt(e.target.value) : '' }))}
                            placeholder="ID" data-testid="odoo-id-input" />
                          <input type="text" className="form-input" style={{ flex: 1, padding: '0.25rem 0.5rem' }}
                            value={formData.odoo_linea_negocio_nombre || ''}
                            onChange={(e) => setFormData(prev => ({ ...prev, odoo_linea_negocio_nombre: e.target.value }))}
                            placeholder="Nombre" data-testid="odoo-nombre-input" />
                        </div>
                      </div>
                    )}
                    {formData.odoo_linea_negocio_id && (
                      <p style={{ marginTop: '0.35rem', fontSize: '0.75rem', color: '#059669' }}>
                        Vinculada: ID {formData.odoo_linea_negocio_id} - {formData.odoo_linea_negocio_nombre || '(sin nombre)'}
                      </p>
                    )}
                  </div>
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-outline" onClick={() => setShowModal(false)}>Cancelar</button>
                <button type="submit" className="btn btn-primary" data-testid="guardar-linea-btn" disabled={submitting}>
                  {submitting ? 'Guardando...' : (editingId ? 'Guardar Cambios' : 'Crear')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      {showDetalle && (
        <DetalleLineaModal
          data={detalleData}
          loading={loadingDetalle}
          onClose={() => { setShowDetalle(false); setDetalleData(null); }}
          onNavigate={(ruta) => { setShowDetalle(false); navigate(ruta); }}
        />
      )}
    </div>
  );
};

const TIPO_ICONS = {
  'Distribucion Analitica': BarChart3,
  'Movimiento Tesoreria': ArrowRightLeft,
  'Gasto': Receipt,
  'Linea de Gasto': Receipt,
  'Factura Proveedor': FileText,
  'Prorrateo': BarChart3,
  'Movimiento Banco': Landmark,
};

const TIPO_COLORS = {
  'Distribucion Analitica': { bg: '#ede9fe', text: '#7c3aed', border: '#c4b5fd' },
  'Movimiento Tesoreria': { bg: '#dbeafe', text: '#2563eb', border: '#93c5fd' },
  'Gasto': { bg: 'var(--danger-bg)', text: '#dc2626', border: '#fecaca' },
  'Linea de Gasto': { bg: 'var(--danger-bg)', text: '#dc2626', border: '#fecaca' },
  'Factura Proveedor': { bg: '#fff7ed', text: '#c2410c', border: '#fdba74' },
  'Prorrateo': { bg: '#fefce8', text: '#a16207', border: '#fde68a' },
  'Movimiento Banco': { bg: 'var(--success-bg)', text: '#16a34a', border: '#bbf7d0' },
};

const fmtMoney = (v) => `S/ ${(Math.abs(v) || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

function DetalleLineaModal({ data, loading, onClose, onNavigate }) {
  if (!data && !loading) return null;

  const tipoKeys = data ? Object.keys(data.por_tipo) : [];

  return (
    <div className="modal-overlay" onClick={onClose} data-testid="detalle-linea-modal">
      <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 720, maxHeight: '85vh', overflow: 'auto' }}>
        <div className="modal-header" style={{ position: 'sticky', top: 0, background: 'var(--card-bg)', zIndex: 2 }}>
          <h2 className="modal-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <GitBranch size={18} />
            {data?.linea?.nombre || 'Cargando...'}
          </h2>
          <button className="modal-close" onClick={onClose}><X size={20} /></button>
        </div>

        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--muted)' }}>Cargando vinculos...</div>
        ) : data?.resumen?.total_vinculos === 0 ? (
          <div style={{ padding: 40, textAlign: 'center' }}>
            <div style={{ fontSize: '0.9rem', color: 'var(--muted)', marginBottom: 8 }}>Esta linea no tiene registros vinculados.</div>
            <div style={{ fontSize: '0.8rem', color: '#16a34a' }}>Se puede eliminar sin problema.</div>
          </div>
        ) : (
          <>
            {/* Summary */}
            <div style={{ display: 'flex', gap: 12, padding: '0.75rem 1.25rem', background: 'var(--card-bg-hover)', borderBottom: '1px solid var(--border)', flexWrap: 'wrap' }}>
              <div style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>
                <strong style={{ color: 'var(--text-heading)' }}>{data.resumen.total_vinculos}</strong> registros vinculados
              </div>
              {tipoKeys.map(tipo => (
                <span key={tipo} style={{
                  padding: '2px 8px', borderRadius: 4, fontSize: '0.7rem', fontWeight: 600,
                  background: (TIPO_COLORS[tipo] || { bg: 'var(--card-bg-alt)' }).bg,
                  color: (TIPO_COLORS[tipo] || { text: 'var(--muted)' }).text,
                }}>
                  {tipo}: {data.resumen.tipos[tipo]}
                </span>
              ))}
            </div>

            {/* Groups */}
            <div style={{ padding: '0.5rem 0' }}>
              {tipoKeys.map(tipo => {
                const items = data.por_tipo[tipo];
                const color = TIPO_COLORS[tipo] || { bg: 'var(--card-bg-alt)', text: 'var(--muted)', border: 'var(--border)' };
                const Icon = TIPO_ICONS[tipo] || FileText;

                return (
                  <div key={tipo} style={{ marginBottom: 4 }}>
                    <div style={{
                      display: 'flex', alignItems: 'center', gap: 8, padding: '0.5rem 1.25rem',
                      background: color.bg, fontSize: '0.8rem', fontWeight: 700, color: color.text,
                    }}>
                      <Icon size={14} />
                      {tipo} ({items.length})
                    </div>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
                      <thead>
                        <tr>
                          <th style={{ padding: '6px 14px', textAlign: 'left', fontWeight: 600, color: 'var(--muted)', fontSize: '0.7rem', borderBottom: '1px solid var(--table-row-border)' }}>Fecha</th>
                          <th style={{ padding: '6px 14px', textAlign: 'left', fontWeight: 600, color: 'var(--muted)', fontSize: '0.7rem', borderBottom: '1px solid var(--table-row-border)' }}>Numero/Detalle</th>
                          <th style={{ padding: '6px 14px', textAlign: 'right', fontWeight: 600, color: 'var(--muted)', fontSize: '0.7rem', borderBottom: '1px solid var(--table-row-border)' }}>Monto</th>
                          <th style={{ padding: '6px 14px', width: 40, borderBottom: '1px solid var(--table-row-border)' }}></th>
                        </tr>
                      </thead>
                      <tbody>
                        {items.map((item, idx) => (
                          <tr key={idx}
                            style={{
                              cursor: item.ruta ? 'pointer' : 'default',
                              transition: 'background 0.1s',
                            }}
                            onMouseEnter={e => { if (item.ruta) e.currentTarget.style.background = 'var(--card-bg-hover)'; }}
                            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                            onClick={() => item.ruta && onNavigate(item.ruta)}
                            data-testid={`vinculo-row-${tipo}-${idx}`}
                          >
                            <td style={{ padding: '6px 14px', borderBottom: '1px solid #f8fafc', color: 'var(--muted)' }}>
                              {item.fecha || '-'}
                            </td>
                            <td style={{ padding: '6px 14px', borderBottom: '1px solid #f8fafc' }}>
                              <span style={{ fontWeight: 600, color: 'var(--text-heading)' }}>{item.numero || ''}</span>
                              {item.detalle && <span style={{ color: 'var(--muted)', marginLeft: 6 }}>{item.detalle}</span>}
                              {item.origen_tipo && <span style={{ color: 'var(--muted)', marginLeft: 6 }}>({item.origen_tipo})</span>}
                            </td>
                            <td style={{
                              padding: '6px 14px', borderBottom: '1px solid #f8fafc', textAlign: 'right',
                              fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", fontSize: '0.78rem',
                              color: item.monto < 0 ? '#dc2626' : 'var(--text-heading)'
                            }}>
                              {fmtMoney(item.monto)}
                            </td>
                            <td style={{ padding: '6px 14px', borderBottom: '1px solid #f8fafc' }}>
                              {item.ruta && <ExternalLink size={12} color="#94a3b8" />}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default LineasNegocio;
