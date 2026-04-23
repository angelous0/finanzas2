import React, { useState, useEffect } from 'react';
import { getIngresosDisponibles, getVinculacionesFactura, vincularIngreso, desvincularIngreso } from '../../services/api';
import { X, Link2, Trash2, Package, CheckCircle } from 'lucide-react';
import { toast } from 'sonner';

const formatDate = (d) => {
  if (!d) return '-';
  return new Date(d).toLocaleDateString('es-PE', { day: '2-digit', month: '2-digit', year: 'numeric' });
};

const VincularIngresosModal = ({ show, factura, onClose, onDataChanged }) => {
  const [vinculaciones, setVinculaciones] = useState([]);
  const [selectedLinea, setSelectedLinea] = useState(null);
  const [ingresosData, setIngresosData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [cantidades, setCantidades] = useState({});
  const [submitting, setSubmitting] = useState({});

  useEffect(() => {
    if (show && factura) {
      loadVinculaciones();
      setSelectedLinea(null);
      setIngresosData(null);
    }
  }, [show, factura?.id]);

  const loadVinculaciones = async () => {
    try {
      const res = await getVinculacionesFactura(factura.id);
      setVinculaciones(res.data);
    } catch (e) {
      console.error(e);
    }
  };

  const loadIngresos = async (linea) => {
    setSelectedLinea(linea);
    setLoading(true);
    setCantidades({});
    try {
      const res = await getIngresosDisponibles(factura.id, linea.id);
      setIngresosData(res.data);
    } catch (e) {
      toast.error(typeof e.response?.data?.detail === 'string' ? e.response?.data?.detail : 'Error al cargar ingresos');
    } finally {
      setLoading(false);
    }
  };

  const handleVincular = async (ingreso) => {
    const cant = parseFloat(cantidades[ingreso.id]);
    if (!cant || cant <= 0) {
      toast.error('Ingrese una cantidad válida');
      return;
    }
    setSubmitting(prev => ({ ...prev, [ingreso.id]: true }));
    try {
      await vincularIngreso(factura.id, selectedLinea.id, {
        ingreso_id: ingreso.id,
        cantidad_aplicada: cant
      });
      toast.success(`Vinculado: ${cant} uds`);
      setCantidades(prev => ({ ...prev, [ingreso.id]: '' }));
      await Promise.all([loadVinculaciones(), loadIngresos(selectedLinea)]);
      if (onDataChanged) onDataChanged();
    } catch (e) {
      toast.error(typeof e.response?.data?.detail === 'string' ? e.response?.data?.detail : 'Error al vincular');
    } finally {
      setSubmitting(prev => ({ ...prev, [ingreso.id]: false }));
    }
  };

  const handleDesvincular = async (vincId) => {
    try {
      await desvincularIngreso(vincId);
      toast.success('Desvinculado');
      await loadVinculaciones();
      if (selectedLinea) await loadIngresos(selectedLinea);
      if (onDataChanged) onDataChanged();
    } catch (e) {
      toast.error(typeof e.response?.data?.detail === 'string' ? e.response?.data?.detail : 'Error al desvincular');
    }
  };

  if (!show || !factura) return null;

  const lineasConArticulo = (factura.lineas || []).filter(l => l.articulo_id);
  const vinculacionesPorLinea = {};
  vinculaciones.forEach(v => {
    if (!vinculacionesPorLinea[v.factura_linea_id]) vinculacionesPorLinea[v.factura_linea_id] = [];
    vinculacionesPorLinea[v.factura_linea_id].push(v);
  });

  return (
    <div className="modal-overlay" style={{ zIndex: 10000 }} onClick={onClose}>
      <div className="modal" style={{ maxWidth: '950px', width: '95%', maxHeight: '90vh', display: 'flex', flexDirection: 'column' }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Link2 size={20} /> Vincular Ingresos MP - {factura.numero}
          </h2>
          <button className="modal-close" onClick={onClose}><X size={20} /></button>
        </div>

        <div className="modal-body" style={{ overflowY: 'auto', padding: '1rem 1.5rem' }}>
          {/* Lines with articles */}
          <div style={{ marginBottom: '1.25rem' }}>
            <h4 style={{ fontSize: '0.8125rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.03em', color: 'var(--muted)', marginBottom: '0.75rem' }}>
              Lineas inventariables ({lineasConArticulo.length})
            </h4>
            {lineasConArticulo.length === 0 ? (
              <p style={{ color: 'var(--muted)', padding: '1rem', textAlign: 'center' }}>No hay lineas con articulo asignado</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {lineasConArticulo.map(linea => {
                  const vincs = vinculacionesPorLinea[linea.id] || [];
                  const totalVinculado = vincs.reduce((s, v) => s + parseFloat(v.cantidad_aplicada || 0), 0);
                  const cantFacturada = parseFloat(linea.cantidad || 0);
                  const pct = cantFacturada > 0 ? Math.min(100, (totalVinculado / cantFacturada) * 100) : 0;
                  const isSelected = selectedLinea?.id === linea.id;
                  const isComplete = pct >= 100;

                  return (
                    <div key={linea.id}>
                      <div
                        data-testid={`linea-vincular-${linea.id}`}
                        onClick={() => loadIngresos(linea)}
                        style={{
                          display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.75rem 1rem',
                          border: `1.5px solid ${isSelected ? 'var(--primary)' : 'var(--border)'}`,
                          borderRadius: '8px', cursor: 'pointer', transition: 'all 0.15s',
                          background: isSelected ? 'var(--success-bg)' : 'var(--card-bg)'
                        }}
                      >
                        <Package size={16} style={{ color: isComplete ? '#16a34a' : 'var(--muted)', flexShrink: 0 }} />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontWeight: 500, fontSize: '0.875rem' }}>{linea.descripcion || linea.articulo_nombre || '-'}</div>
                          <div style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>{linea.articulo_codigo || linea.articulo_id}</div>
                        </div>
                        <div style={{ textAlign: 'right', flexShrink: 0 }}>
                          <div style={{ fontSize: '0.8125rem', fontWeight: 600, fontFamily: "'JetBrains Mono', monospace" }}>
                            {totalVinculado.toFixed(0)} / {cantFacturada.toFixed(0)}
                          </div>
                          <div style={{ width: '80px', height: '4px', background: 'var(--border)', borderRadius: '2px', marginTop: '4px' }}>
                            <div style={{ width: `${pct}%`, height: '100%', background: isComplete ? '#16a34a' : '#f59e0b', borderRadius: '2px', transition: 'width 0.3s' }} />
                          </div>
                        </div>
                        {isComplete && <CheckCircle size={16} style={{ color: '#16a34a', flexShrink: 0 }} />}
                      </div>

                      {/* Show existing vinculaciones inline */}
                      {vincs.length > 0 && (
                        <div style={{ marginLeft: '2rem', marginTop: '0.25rem', marginBottom: '0.25rem' }}>
                          {vincs.map(v => (
                            <div key={v.id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.25rem 0.5rem', fontSize: '0.75rem', color: 'var(--muted)' }}>
                              <span style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--primary)', fontWeight: 500 }}>{parseFloat(v.cantidad_aplicada).toFixed(0)} uds</span>
                              <span style={{ color: 'var(--muted)' }}>&larr;</span>
                              <span>{v.ingreso_ref || v.ingreso_id?.substring(0, 8)}</span>
                              <span style={{ color: 'var(--muted)' }}>({formatDate(v.ingreso_fecha)})</span>
                              <button onClick={(e) => { e.stopPropagation(); handleDesvincular(v.id); }}
                                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444', padding: '2px' }}
                                title="Desvincular"
                              ><Trash2 size={12} /></button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Ingresos disponibles for selected line */}
          {selectedLinea && (
            <div style={{ borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
              <h4 style={{ fontSize: '0.8125rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.03em', color: 'var(--muted)', marginBottom: '0.75rem' }}>
                Ingresos disponibles para: {selectedLinea.descripcion || selectedLinea.articulo_nombre}
              </h4>

              {loading ? (
                <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--muted)' }}>Cargando...</div>
              ) : ingresosData?.ingresos?.length === 0 ? (
                <p style={{ color: 'var(--muted)', padding: '1rem', textAlign: 'center' }}>No hay ingresos para este articulo</p>
              ) : ingresosData?.message ? (
                <p style={{ color: '#f59e0b', padding: '1rem', textAlign: 'center' }}>{ingresosData.message}</p>
              ) : (
                <div className="data-table-wrapper">
                  <table className="data-table" style={{ fontSize: '0.8125rem' }}>
                    <thead>
                      <tr>
                        <th>Fecha</th>
                        <th>Referencia</th>
                        <th>Proveedor</th>
                        <th className="text-right">Recibido</th>
                        <th className="text-right">Vinculado</th>
                        <th className="text-right">Disponible</th>
                        <th style={{ width: '100px' }}>Aplicar</th>
                        <th style={{ width: '70px' }}></th>
                      </tr>
                    </thead>
                    <tbody>
                      {(ingresosData?.ingresos || []).map(ing => {
                        const disponible = ing.saldo_disponible;
                        const lineaInfo = ingresosData?.linea;
                        const maxLinea = lineaInfo ? lineaInfo.cantidad - lineaInfo.ya_vinculado : disponible;
                        const maxAplicar = Math.min(disponible, maxLinea);

                        return (
                          <tr key={ing.id} style={{ opacity: disponible <= 0 ? 0.4 : 1 }}>
                            <td>{formatDate(ing.fecha)}</td>
                            <td style={{ fontFamily: "'JetBrains Mono', monospace" }}>{ing.numero_documento || '-'}</td>
                            <td>{ing.proveedor || '-'}</td>
                            <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace" }}>{parseFloat(ing.cantidad).toFixed(0)}</td>
                            <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace", color: '#f59e0b' }}>{parseFloat(ing.total_vinculado).toFixed(0)}</td>
                            <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600, color: disponible > 0 ? '#16a34a' : '#ef4444' }}>{disponible.toFixed(0)}</td>
                            <td>
                              <input
                                type="number" step="1" min="0" max={maxAplicar}
                                placeholder={maxAplicar > 0 ? maxAplicar.toFixed(0) : '0'}
                                value={cantidades[ing.id] || ''}
                                onChange={e => setCantidades(prev => ({ ...prev, [ing.id]: e.target.value }))}
                                disabled={disponible <= 0 || maxLinea <= 0}
                                style={{ width: '100%', textAlign: 'center', padding: '0.25rem', fontSize: '0.8125rem', border: '1px solid var(--border)', borderRadius: '4px' }}
                                data-testid={`aplicar-cantidad-${ing.id}`}
                              />
                            </td>
                            <td>
                              <button
                                className="btn btn-primary btn-sm"
                                disabled={!cantidades[ing.id] || parseFloat(cantidades[ing.id]) <= 0 || submitting[ing.id] || disponible <= 0}
                                onClick={() => handleVincular(ing)}
                                style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                                data-testid={`vincular-btn-${ing.id}`}
                              >
                                {submitting[ing.id] ? '...' : 'Aplicar'}
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-outline" onClick={onClose}>Cerrar</button>
        </div>
      </div>
    </div>
  );
};

export default VincularIngresosModal;
