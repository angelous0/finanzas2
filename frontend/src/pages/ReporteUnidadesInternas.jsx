import React, { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { BarChart3, Calendar, TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight, Minus, ShieldCheck, ShieldAlert } from 'lucide-react';
import { getReporteUnidadesInternas } from '../services/api';

const formatCurrency = (v) => `S/ ${(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function ReporteUnidadesInternas() {
  const [reporte, setReporte] = useState(null);
  const [loading, setLoading] = useState(false);
  const [fechaDesde, setFechaDesde] = useState('');
  const [fechaHasta, setFechaHasta] = useState('');
  const [vista, setVista] = useState('empresa'); // 'empresa' | 'unidades'

  const loadReporte = useCallback(async () => {
    try {
      setLoading(true);
      const params = {};
      if (fechaDesde) params.fecha_desde = fechaDesde;
      if (fechaHasta) params.fecha_hasta = fechaHasta;
      const res = await getReporteUnidadesInternas(params);
      setReporte(res.data);
    } catch (e) {
      toast.error('Error al cargar reporte');
    } finally {
      setLoading(false);
    }
  }, [fechaDesde, fechaHasta]);

  useEffect(() => { loadReporte(); }, [loadReporte]);

  const s = {
    page: { padding: '1.5rem', maxWidth: 1200, margin: '0 auto' },
    header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: 12 },
    title: { fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-heading)', display: 'flex', alignItems: 'center', gap: 10 },
    tabs: { display: 'flex', gap: 4, background: 'var(--card-bg-alt)', borderRadius: 8, padding: 3, marginBottom: '1rem' },
    tab: (active) => ({
      padding: '8px 20px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600,
      background: active ? 'var(--card-bg)' : 'transparent', color: active ? 'var(--text-heading)' : 'var(--muted)',
      boxShadow: active ? '0 1px 3px rgba(0,0,0,0.1)' : 'none', transition: 'all 0.15s'
    }),
    filterBar: { display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' },
    input: { padding: '8px 12px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: '0.85rem' },
    card: { background: 'var(--card-bg)', borderRadius: 10, border: '1px solid var(--border)', overflow: 'hidden' },
    table: { width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' },
    th: { padding: '10px 14px', textAlign: 'left', fontWeight: 600, color: 'var(--muted)', borderBottom: '2px solid var(--border)', background: 'var(--card-bg-hover)', fontSize: '0.75rem', textTransform: 'uppercase' },
    td: { padding: '12px 14px', borderBottom: '1px solid var(--table-row-border)' },
    summaryRow: { display: 'flex', gap: 16, marginBottom: '1rem', flexWrap: 'wrap' },
    summaryCard: (bg, border) => ({
      background: bg, borderRadius: 10, padding: '1rem 1.25rem', flex: 1, minWidth: 200,
      border: `1px solid ${border}`
    }),
    summaryLabel: { fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', marginBottom: 4 },
    summaryValue: { fontSize: '1.25rem', fontWeight: 800, fontFamily: "'JetBrains Mono', monospace" },
    badge: (positive) => ({
      padding: '3px 10px', borderRadius: 6, fontSize: '0.75rem', fontWeight: 700,
      background: positive ? '#dcfce7' : 'var(--danger-bg)',
      color: positive ? '#15803d' : '#dc2626',
      display: 'inline-flex', alignItems: 'center', gap: 4
    }),
  };

  const resumen = reporte?.resumen || {};

  return (
    <div style={s.page} data-testid="reporte-unidades-page">
      <div style={s.header}>
        <div style={s.title}><BarChart3 size={22} /> Reporte Gerencial - Unidades Internas</div>
        <div style={s.filterBar}>
          <Calendar size={16} color="#64748b" />
          <input type="date" style={s.input} value={fechaDesde} onChange={e => setFechaDesde(e.target.value)} data-testid="reporte-fecha-desde" />
          <span style={{ color: 'var(--muted)' }}>a</span>
          <input type="date" style={s.input} value={fechaHasta} onChange={e => setFechaHasta(e.target.value)} data-testid="reporte-fecha-hasta" />
        </div>
      </div>

      {/* Global summary */}
      <div style={s.summaryRow}>
        <div style={s.summaryCard('#f0fdf4', '#bbf7d0')}>
          <div style={{ ...s.summaryLabel, color: 'var(--success-text)' }}>Total Ingresos Internos</div>
          <div style={{ ...s.summaryValue, color: 'var(--success-text)' }}>{formatCurrency(resumen.total_ingresos_internos)}</div>
        </div>
        <div style={s.summaryCard('#fef2f2', '#fecaca')}>
          <div style={{ ...s.summaryLabel, color: 'var(--danger-text)' }}>Total Gastos Reales</div>
          <div style={{ ...s.summaryValue, color: 'var(--danger-text)' }}>{formatCurrency(resumen.total_gastos_reales)}</div>
        </div>
        <div style={s.summaryCard(
          (resumen.resultado_global || 0) >= 0 ? '#f0fdf4' : 'var(--danger-bg)',
          (resumen.resultado_global || 0) >= 0 ? '#bbf7d0' : '#fecaca'
        )}>
          <div style={{ ...s.summaryLabel, color: (resumen.resultado_global || 0) >= 0 ? '#15803d' : '#dc2626' }}>Resultado Global</div>
          <div style={{ ...s.summaryValue, color: (resumen.resultado_global || 0) >= 0 ? '#15803d' : '#dc2626' }}>
            {formatCurrency(resumen.resultado_global)}
          </div>
        </div>
        <div style={s.summaryCard('var(--card-bg-hover)', 'var(--border)')}>
          <div style={{ ...s.summaryLabel, color: 'var(--muted)' }}>Unidades Activas</div>
          <div style={{ ...s.summaryValue, color: 'var(--text-secondary)' }}>{resumen.num_unidades || 0}</div>
        </div>
      </div>

      {/* View toggle */}
      <div style={s.tabs}>
        <button style={s.tab(vista === 'empresa')} onClick={() => setVista('empresa')} data-testid="tab-vista-empresa">
          Vista Empresa Principal
        </button>
        <button style={s.tab(vista === 'unidades')} onClick={() => setVista('unidades')} data-testid="tab-vista-unidades">
          Vista por Unidad Interna
        </button>
      </div>

      {/* Vista Empresa */}
      {vista === 'empresa' && (
        <div style={s.card}>
          <div style={{ padding: '0.75rem 1rem', background: 'var(--warning-bg)', borderBottom: '1px solid #fde68a', fontSize: '0.8rem', color: 'var(--warning-text)' }}>
            La empresa principal solo ve el <strong>costo consolidado</strong> por unidad interna. No se muestra detalle de gastos.
          </div>
          <table style={s.table}>
            <thead>
              <tr>
                <th style={s.th}>Unidad Interna</th>
                <th style={{ ...s.th, textAlign: 'right' }}>Costo Interno Consolidado</th>
              </tr>
            </thead>
            <tbody>
              {(reporte?.vista_empresa || []).length === 0 && (
                <tr><td colSpan={2} style={{ ...s.td, textAlign: 'center', color: 'var(--muted)', padding: 32 }}>
                  Sin datos. Cree unidades y genere cargos internos.
                </td></tr>
              )}
              {(reporte?.vista_empresa || []).map(v => (
                <tr key={v.unidad_id} data-testid={`empresa-row-${v.unidad_id}`}>
                  <td style={{ ...s.td, fontWeight: 600 }}>{v.unidad_nombre}</td>
                  <td style={{ ...s.td, textAlign: 'right', fontWeight: 700, color: 'var(--danger-text)', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.9rem' }}>
                    {formatCurrency(v.costo_consolidado)}
                  </td>
                </tr>
              ))}
              {(reporte?.vista_empresa || []).length > 0 && (
                <tr style={{ background: 'var(--card-bg-hover)' }}>
                  <td style={{ ...s.td, fontWeight: 800, color: 'var(--text-heading)' }}>TOTAL</td>
                  <td style={{ ...s.td, textAlign: 'right', fontWeight: 800, color: 'var(--danger-text)', fontFamily: "'JetBrains Mono', monospace", fontSize: '1rem' }}>
                    {formatCurrency(resumen.total_costo_empresa)}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Vista Unidades */}
      {vista === 'unidades' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {(reporte?.vista_unidades || []).length === 0 && (
            <div style={{ ...s.card, padding: 32, textAlign: 'center', color: 'var(--muted)' }}>
              Sin datos. Cree unidades y genere cargos internos.
            </div>
          )}
          {(reporte?.vista_unidades || []).map(u => {
            const positivo = u.resultado >= 0;
            return (
              <div key={u.unidad_id} style={s.card} data-testid={`unidad-report-${u.unidad_id}`}>
                <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '1rem', color: 'var(--text-heading)' }}>{u.unidad_nombre}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>{u.tipo || 'Unidad Interna'}</div>
                  </div>
                  <span style={s.badge(positivo)}>
                    {positivo ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
                    {positivo ? 'GANANCIA' : 'PERDIDA'}: {formatCurrency(Math.abs(u.resultado))}
                  </span>
                </div>
                <div style={{ padding: '1rem 1.25rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '1rem' }}>
                  <div>
                    <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--success-text)', textTransform: 'uppercase', marginBottom: 2 }}>Ingresos Internos</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--success-text)', fontFamily: "'JetBrains Mono', monospace" }}>
                      {formatCurrency(u.ingresos_internos)}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--danger-text)', textTransform: 'uppercase', marginBottom: 2 }}>Gastos Reales</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--danger-text)', fontFamily: "'JetBrains Mono', monospace" }}>
                      {formatCurrency(u.gastos_reales)}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: 2 }}>Resultado</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: positivo ? '#15803d' : '#dc2626', fontFamily: "'JetBrains Mono', monospace" }}>
                      {formatCurrency(u.resultado)}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: 2 }}>Cantidad Trabajada</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#1d4ed8', fontFamily: "'JetBrains Mono', monospace" }}>
                      {u.cantidad_trabajada?.toLocaleString() || 0}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: 2 }}>Costo Promedio</div>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--muted)', fontFamily: "'JetBrains Mono', monospace" }}>
                      S/ {(u.costo_promedio || 0).toFixed(4)}
                    </div>
                  </div>
                </div>

                {/* Tarifas y Sostenibilidad */}
                <div style={{ padding: '0 1.25rem 1rem', borderTop: '1px solid var(--table-row-border)', paddingTop: '1rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: '0.75rem' }}>
                    <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-secondary)' }}>Análisis de Tarifas</span>
                    {u.tarifa_sostenible != null && (
                      <span style={{
                        padding: '2px 10px', borderRadius: 6, fontSize: '0.7rem', fontWeight: 700,
                        background: u.tarifa_sostenible ? '#dcfce7' : 'var(--danger-bg)',
                        color: u.tarifa_sostenible ? '#15803d' : '#dc2626',
                        display: 'inline-flex', alignItems: 'center', gap: 4
                      }}>
                        {u.tarifa_sostenible ? <ShieldCheck size={12} /> : <ShieldAlert size={12} />}
                        {u.tarifa_sostenible ? 'SOSTENIBLE' : 'INSUFICIENTE'}
                      </span>
                    )}
                    {u.cobertura_pct != null && (
                      <span style={{
                        padding: '2px 8px', borderRadius: 6, fontSize: '0.7rem', fontWeight: 600,
                        background: '#f0f9ff', color: 'var(--info-text)'
                      }}>
                        Cobertura: {u.cobertura_pct.toFixed(1)}%
                      </span>
                    )}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
                    <div style={{ background: 'var(--card-bg-hover)', borderRadius: 8, padding: '0.75rem' }}>
                      <div style={{ fontSize: '0.65rem', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 2 }}>Tarifa Actual (Promedio)</div>
                      <div style={{ fontSize: '1rem', fontWeight: 800, color: 'var(--text-heading)', fontFamily: "'JetBrains Mono', monospace" }}>
                        S/ {(u.tarifa_actual || 0).toFixed(4)}
                      </div>
                    </div>
                    <div style={{ background: u.tarifa_sostenible === false ? '#fef2f2' : 'var(--card-bg-hover)', borderRadius: 8, padding: '0.75rem' }}>
                      <div style={{ fontSize: '0.65rem', fontWeight: 600, color: u.tarifa_sostenible === false ? '#dc2626' : 'var(--muted)', textTransform: 'uppercase', marginBottom: 2 }}>Tarifa Mínima Sugerida</div>
                      <div style={{ fontSize: '1rem', fontWeight: 800, color: u.tarifa_sostenible === false ? '#dc2626' : 'var(--text-heading)', fontFamily: "'JetBrains Mono', monospace" }}>
                        S/ {(u.tarifa_minima || 0).toFixed(4)}
                      </div>
                    </div>
                  </div>

                  {/* Desglose de Gastos Contables */}
                  {u.gastos_detalle && u.gastos_detalle.length > 0 && (
                    <div style={{ marginTop: '0.75rem' }}>
                      <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', marginBottom: 6 }}>Desglose Gastos Contables</div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                        {u.gastos_detalle.map((d, i) => (
                          <div key={i} style={{
                            background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: 6, padding: '4px 10px',
                            fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: 6
                          }}>
                            <span style={{ color: 'var(--muted)' }}>{d.tipo_gasto || d.categoria_nombre || 'Otro'}</span>
                            <span style={{ fontWeight: 700, color: 'var(--danger-text)', fontFamily: "'JetBrains Mono', monospace" }}>
                              {formatCurrency(d.total)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
