import React, { useState, useEffect, useCallback } from 'react';
import { Layers, Eye, Play, History, ChevronDown, ChevronUp, Trash2 } from 'lucide-react';
import { getProrratePendientes, getProrratePreview, ejecutarProrrateo, getProrrateHistorial, eliminarProrrateo, getLineasNegocio } from '../services/api';
import { toast } from 'sonner';

const formatCurrency = (n) => new Intl.NumberFormat('es-PE', { style: 'currency', currency: 'PEN' }).format(n || 0);
const formatDate = (d) => d ? new Date(d).toLocaleDateString('es-PE') : '-';

export default function ProrrateoGastos() {
  const [tab, setTab] = useState('pendientes');
  const [pendientes, setPendientes] = useState([]);
  const [historial, setHistorial] = useState([]);
  const [lineas, setLineas] = useState([]);
  const [loading, setLoading] = useState(true);

  // Preview state
  const [previewGasto, setPreviewGasto] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [metodo, setMetodo] = useState('ventas_mes');
  const [periodoDesde, setPeriodoDesde] = useState('');
  const [periodoHasta, setPeriodoHasta] = useState('');
  const [manualLineas, setManualLineas] = useState([]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [pendRes, histRes, linRes] = await Promise.all([
        getProrratePendientes(),
        getProrrateHistorial(),
        getLineasNegocio()
      ]);
      setPendientes(pendRes.data);
      setHistorial(histRes.data);
      setLineas(linRes.data.filter(l => l.activo));
    } catch {
      toast.error('Error cargando datos');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handlePreview = async (gasto) => {
    setPreviewGasto(gasto);
    setPreviewData(null);
    setMetodo('ventas_mes');
    setManualLineas(lineas.map(l => ({ linea_negocio_id: l.id, nombre: l.nombre, porcentaje: 0, monto: 0 })));
    
    setPreviewLoading(true);
    try {
      const res = await getProrratePreview({
        gasto_id: gasto.id,
        metodo: 'ventas_mes'
      });
      setPreviewData(res.data);
    } catch {
      toast.error('No hay datos de ventas para calcular prorrateo');
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleChangeMetodo = async (newMetodo) => {
    setMetodo(newMetodo);
    if (newMetodo === 'manual') {
      setPreviewData(null);
      return;
    }
    setPreviewLoading(true);
    try {
      const payload = { gasto_id: previewGasto.id, metodo: newMetodo };
      if (newMetodo === 'ventas_rango' && periodoDesde && periodoHasta) {
        payload.periodo_desde = periodoDesde;
        payload.periodo_hasta = periodoHasta;
      }
      const res = await getProrratePreview(payload);
      setPreviewData(res.data);
    } catch {
      toast.error('Error calculando preview');
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleRangoPreview = async () => {
    if (!periodoDesde || !periodoHasta) { toast.error('Selecciona rango de fechas'); return; }
    setPreviewLoading(true);
    try {
      const res = await getProrratePreview({
        gasto_id: previewGasto.id,
        metodo: 'ventas_rango',
        periodo_desde: periodoDesde,
        periodo_hasta: periodoHasta
      });
      setPreviewData(res.data);
    } catch {
      toast.error('Error calculando preview');
    } finally {
      setPreviewLoading(false);
    }
  };

  const updateManualPct = (idx, pct) => {
    const updated = [...manualLineas];
    updated[idx].porcentaje = parseFloat(pct) || 0;
    updated[idx].monto = (previewGasto.total * (updated[idx].porcentaje / 100));
    setManualLineas(updated);
  };

  const handleEjecutar = async () => {
    if (!previewGasto) return;
    try {
      const payload = { gasto_id: previewGasto.id, metodo };
      if (metodo === 'manual') {
        const totalPct = manualLineas.reduce((s, l) => s + l.porcentaje, 0);
        if (Math.abs(totalPct - 100) > 0.01) { toast.error(`Los porcentajes suman ${totalPct.toFixed(2)}%, deben sumar 100%`); return; }
        payload.lineas = manualLineas.filter(l => l.porcentaje > 0).map(l => ({
          linea_negocio_id: l.linea_negocio_id,
          porcentaje: l.porcentaje,
          monto: l.monto
        }));
      } else if (metodo === 'ventas_rango') {
        payload.periodo_desde = periodoDesde;
        payload.periodo_hasta = periodoHasta;
      }
      await ejecutarProrrateo(payload);
      toast.success('Prorrateo ejecutado correctamente');
      setPreviewGasto(null);
      setPreviewData(null);
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error ejecutando prorrateo');
    }
  };

  const handleEliminar = async (gastoId) => {
    if (!window.confirm('Eliminar prorrateo? Los montos se reversan.')) return;
    try {
      await eliminarProrrateo(gastoId);
      toast.success('Prorrateo eliminado');
      loadData();
    } catch {
      toast.error('Error eliminando');
    }
  };

  return (
    <div style={{ padding: '1.5rem' }} data-testid="prorrateo-page">
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0 }}>Prorrateo de Gastos</h1>
        <p style={{ fontSize: '0.8125rem', color: 'var(--muted)', margin: '0.25rem 0 0' }}>
          Distribuye gastos comunes entre líneas de negocio
        </p>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0', borderBottom: '2px solid var(--border)', marginBottom: '1.5rem' }}>
        {[
          { key: 'pendientes', label: 'Pendientes', count: pendientes.length },
          { key: 'historial', label: 'Historial', count: historial.length }
        ].map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            data-testid={`tab-${t.key}`}
            style={{
              padding: '0.5rem 1.25rem',
              fontSize: '0.8125rem',
              fontWeight: tab === t.key ? 600 : 400,
              color: tab === t.key ? '#1e40af' : 'var(--muted)',
              background: 'none',
              border: 'none',
              borderBottom: tab === t.key ? '2px solid #1e40af' : '2px solid transparent',
              cursor: 'pointer',
              marginBottom: '-2px'
            }}
          >
            {t.label} ({t.count})
          </button>
        ))}
      </div>

      {loading ? (
        <p style={{ textAlign: 'center', color: 'var(--muted)', padding: '2rem' }}>Cargando...</p>
      ) : tab === 'pendientes' ? (
        <>
          {pendientes.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--muted)' }}>
              <Layers size={40} strokeWidth={1} />
              <p style={{ marginTop: '0.5rem' }}>No hay gastos comunes pendientes de prorrateo</p>
            </div>
          ) : (
            <table className="data-table" data-testid="pendientes-table">
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Número</th>
                  <th>Beneficiario</th>
                  <th>Categoría</th>
                  <th>Centro Costo</th>
                  <th className="text-right">Total</th>
                  <th className="text-center">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {pendientes.map(g => (
                  <tr key={g.id}>
                    <td>{formatDate(g.fecha)}</td>
                    <td style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.8125rem' }}>{g.numero}</td>
                    <td>{g.beneficiario_nombre || '-'}</td>
                    <td>{g.categoria_gasto_nombre || '-'}</td>
                    <td>{g.centro_costo_nombre || '-'}</td>
                    <td className="text-right" style={{ fontWeight: 600 }}>{formatCurrency(g.total)}</td>
                    <td className="text-center">
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={() => handlePreview(g)}
                        data-testid={`prorratear-${g.id}`}
                      >
                        <Eye size={14} /> Prorratear
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {/* Preview Modal */}
          {previewGasto && (
            <div className="modal-overlay" onClick={() => setPreviewGasto(null)}>
              <div className="modal-content" style={{ maxWidth: '700px' }} onClick={e => e.stopPropagation()}>
                <div className="modal-header">
                  <h2 className="modal-title">Prorrateo: {previewGasto.numero}</h2>
                  <button className="modal-close" onClick={() => setPreviewGasto(null)}><Layers size={20} /></button>
                </div>
                <div className="modal-body">
                  <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', fontSize: '0.8125rem' }}>
                    <div><strong>Total:</strong> {formatCurrency(previewGasto.total)}</div>
                    <div><strong>Categoría:</strong> {previewGasto.categoria_gasto_nombre || '-'}</div>
                    <div><strong>Centro Costo:</strong> {previewGasto.centro_costo_nombre || '-'}</div>
                  </div>

                  {/* Metodo selector */}
                  <div style={{ marginBottom: '1rem' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 500, color: 'var(--muted)', display: 'block', marginBottom: '6px' }}>Método de prorrateo</label>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      {[
                        { value: 'ventas_mes', label: 'Ventas del mes' },
                        { value: 'ventas_rango', label: 'Rango fechas' },
                        { value: 'manual', label: 'Manual' }
                      ].map(m => (
                        <button
                          key={m.value}
                          className={`btn btn-sm ${metodo === m.value ? 'btn-primary' : 'btn-outline'}`}
                          onClick={() => handleChangeMetodo(m.value)}
                          data-testid={`metodo-${m.value}`}
                        >
                          {m.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {metodo === 'ventas_rango' && (
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-end', marginBottom: '1rem' }}>
                      <div>
                        <label style={{ fontSize: '0.75rem', color: 'var(--muted)', display: 'block', marginBottom: '4px' }}>Desde</label>
                        <input type="date" className="form-input" value={periodoDesde} onChange={e => setPeriodoDesde(e.target.value)} data-testid="periodo-desde" />
                      </div>
                      <div>
                        <label style={{ fontSize: '0.75rem', color: 'var(--muted)', display: 'block', marginBottom: '4px' }}>Hasta</label>
                        <input type="date" className="form-input" value={periodoHasta} onChange={e => setPeriodoHasta(e.target.value)} data-testid="periodo-hasta" />
                      </div>
                      <button className="btn btn-primary btn-sm" onClick={handleRangoPreview}>Calcular</button>
                    </div>
                  )}

                  {/* Preview results */}
                  {previewLoading ? (
                    <p style={{ textAlign: 'center', color: 'var(--muted)', padding: '1rem' }}>Calculando...</p>
                  ) : metodo !== 'manual' && previewData?.lineas ? (
                    <table className="data-table" style={{ fontSize: '0.8125rem' }} data-testid="preview-table">
                      <thead>
                        <tr>
                          <th>Línea de Negocio</th>
                          <th className="text-right">% Participación</th>
                          <th className="text-right">Monto</th>
                        </tr>
                      </thead>
                      <tbody>
                        {previewData.lineas.map((l, i) => (
                          <tr key={i}>
                            <td style={{ fontWeight: 500 }}>{l.linea_negocio_nombre || `Línea ${l.linea_negocio_id}`}</td>
                            <td className="text-right">{(l.porcentaje || 0).toFixed(2)}%</td>
                            <td className="text-right" style={{ fontWeight: 600 }}>{formatCurrency(l.monto)}</td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr style={{ fontWeight: 700 }}>
                          <td>Total</td>
                          <td className="text-right">{previewData.lineas.reduce((s, l) => s + (l.porcentaje || 0), 0).toFixed(2)}%</td>
                          <td className="text-right">{formatCurrency(previewData.lineas.reduce((s, l) => s + (l.monto || 0), 0))}</td>
                        </tr>
                      </tfoot>
                    </table>
                  ) : metodo === 'manual' ? (
                    <table className="data-table" style={{ fontSize: '0.8125rem' }} data-testid="manual-table">
                      <thead>
                        <tr>
                          <th>Línea de Negocio</th>
                          <th style={{ width: '120px' }}>% Manual</th>
                          <th className="text-right">Monto</th>
                        </tr>
                      </thead>
                      <tbody>
                        {manualLineas.map((l, i) => (
                          <tr key={i}>
                            <td style={{ fontWeight: 500 }}>{l.nombre}</td>
                            <td>
                              <input
                                type="number"
                                className="form-input"
                                style={{ width: '100px', textAlign: 'right' }}
                                value={l.porcentaje || ''}
                                onChange={e => updateManualPct(i, e.target.value)}
                                min="0" max="100" step="0.01"
                                data-testid={`manual-pct-${i}`}
                              />
                            </td>
                            <td className="text-right" style={{ fontWeight: 600 }}>{formatCurrency(l.monto)}</td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr style={{ fontWeight: 700 }}>
                          <td>Total</td>
                          <td style={{ color: Math.abs(manualLineas.reduce((s, l) => s + l.porcentaje, 0) - 100) > 0.01 ? '#ef4444' : '#166534' }}>
                            {manualLineas.reduce((s, l) => s + l.porcentaje, 0).toFixed(2)}%
                          </td>
                          <td className="text-right">{formatCurrency(manualLineas.reduce((s, l) => s + l.monto, 0))}</td>
                        </tr>
                      </tfoot>
                    </table>
                  ) : null}
                </div>
                <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
                  <button className="btn btn-outline btn-sm" onClick={() => setPreviewGasto(null)}>Cancelar</button>
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={handleEjecutar}
                    disabled={metodo !== 'manual' && !previewData?.lineas?.length}
                    data-testid="ejecutar-prorrateo-btn"
                  >
                    <Play size={14} /> Ejecutar Prorrateo
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      ) : (
        /* Historial tab */
        historial.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--muted)' }}>
            <History size={40} strokeWidth={1} />
            <p style={{ marginTop: '0.5rem' }}>No hay prorrateos ejecutados</p>
          </div>
        ) : (
          <table className="data-table" data-testid="historial-table">
            <thead>
              <tr>
                <th>Fecha Ejecución</th>
                <th>Gasto</th>
                <th>Método</th>
                <th>Período</th>
                <th className="text-right">Monto Total</th>
                <th className="text-center">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {historial.map(h => (
                <HistorialRow key={h.id} item={h} onEliminar={handleEliminar} />
              ))}
            </tbody>
          </table>
        )
      )}
    </div>
  );
}

function HistorialRow({ item, onEliminar }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <>
      <tr>
        <td>{formatDate(item.created_at)}</td>
        <td style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.8125rem' }}>
          Gasto #{item.gasto_id}
        </td>
        <td>
          <span style={{
            padding: '2px 8px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: 500,
            background: item.metodo === 'manual' ? '#fef9c3' : '#dbeafe',
            color: item.metodo === 'manual' ? '#854d0e' : '#1e40af'
          }}>
            {item.metodo}
          </span>
        </td>
        <td style={{ fontSize: '0.8125rem' }}>
          {item.periodo_desde && item.periodo_hasta
            ? `${formatDate(item.periodo_desde)} - ${formatDate(item.periodo_hasta)}`
            : '-'}
        </td>
        <td className="text-right" style={{ fontWeight: 600 }}>{formatCurrency(item.monto_total)}</td>
        <td className="text-center">
          <div style={{ display: 'flex', gap: '0.25rem', justifyContent: 'center' }}>
            <button className="btn btn-outline btn-sm" onClick={() => setExpanded(!expanded)} data-testid={`expand-${item.id}`}>
              {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
            <button className="btn btn-outline btn-sm" style={{ color: '#ef4444' }} onClick={() => onEliminar(item.gasto_id)} data-testid={`del-prorrateo-${item.id}`}>
              <Trash2 size={14} />
            </button>
          </div>
        </td>
      </tr>
      {expanded && item.detalle?.length > 0 && (
        <tr>
          <td colSpan={6} style={{ padding: '0.5rem 2rem', background: 'var(--card-bg-hover)' }}>
            <table style={{ width: '100%', fontSize: '0.8125rem' }}>
              <thead>
                <tr style={{ color: 'var(--muted)' }}>
                  <th style={{ padding: '4px 8px', textAlign: 'left' }}>Línea</th>
                  <th style={{ padding: '4px 8px', textAlign: 'right' }}>%</th>
                  <th style={{ padding: '4px 8px', textAlign: 'right' }}>Monto</th>
                </tr>
              </thead>
              <tbody>
                {item.detalle.map((d, i) => (
                  <tr key={i}>
                    <td style={{ padding: '4px 8px' }}>{d.linea_negocio_nombre || `Línea ${d.linea_negocio_id}`}</td>
                    <td style={{ padding: '4px 8px', textAlign: 'right' }}>{(d.porcentaje || 0).toFixed(2)}%</td>
                    <td style={{ padding: '4px 8px', textAlign: 'right', fontWeight: 600 }}>{formatCurrency(d.monto)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </td>
        </tr>
      )}
    </>
  );
}
