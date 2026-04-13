import React, { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { Wallet, Calendar, TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight, ChevronDown, ChevronUp } from 'lucide-react';
import { getResumenCuentasInternas, getKardexCuenta } from '../services/api';

const fmt = (v) => `S/ ${(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function CuentasInternas() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [mes, setMes] = useState(() => {
    const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  });
  const [expanded, setExpanded] = useState(null);
  const [kardex, setKardex] = useState(null);
  const [kardexLoading, setKardexLoading] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const res = await getResumenCuentasInternas({ mes });
      setData(res.data);
    } catch { toast.error('Error al cargar cuentas internas'); }
    finally { setLoading(false); }
  }, [mes]);

  useEffect(() => { load(); }, [load]);

  const toggleKardex = async (cuentaId) => {
    if (expanded === cuentaId) { setExpanded(null); setKardex(null); return; }
    setExpanded(cuentaId);
    setKardexLoading(true);
    try {
      const [y, m] = mes.split('-');
      const fecha_desde = `${y}-${m}-01`;
      const lastDay = new Date(parseInt(y), parseInt(m), 0).getDate();
      const fecha_hasta = `${y}-${m}-${lastDay}`;
      const res = await getKardexCuenta(cuentaId, { fecha_desde, fecha_hasta });
      setKardex(res.data);
    } catch { toast.error('Error al cargar kardex'); }
    finally { setKardexLoading(false); }
  };

  const s = {
    page: { padding: '1.5rem', maxWidth: 1200, margin: '0 auto' },
    header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: 12 },
    title: { fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-heading)', display: 'flex', alignItems: 'center', gap: 10 },
    cards: { display: 'flex', gap: 16, marginBottom: '1rem', flexWrap: 'wrap' },
    card: (bg, border) => ({ background: bg, borderRadius: 10, padding: '1rem 1.25rem', flex: 1, minWidth: 200, border: `1px solid ${border}` }),
    label: { fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', marginBottom: 4 },
    value: { fontSize: '1.25rem', fontWeight: 800, fontFamily: "'JetBrains Mono', monospace" },
    table: { width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' },
    th: { padding: '10px 14px', textAlign: 'left', fontWeight: 600, color: 'var(--muted)', borderBottom: '2px solid var(--border)', background: 'var(--card-bg-hover)', fontSize: '0.75rem', textTransform: 'uppercase' },
    td: { padding: '12px 14px', borderBottom: '1px solid var(--table-row-border)' },
    badge: (ok) => ({
      padding: '3px 10px', borderRadius: 6, fontSize: '0.7rem', fontWeight: 700,
      background: ok ? '#dcfce7' : 'var(--danger-bg)', color: ok ? '#15803d' : '#dc2626',
      display: 'inline-flex', alignItems: 'center', gap: 4
    }),
    input: { padding: '8px 12px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: '0.85rem' },
  };

  const cuentas = data?.cuentas || [];

  return (
    <div style={s.page}>
      <div style={s.header}>
        <div style={s.title}><Wallet size={22} /> Cuentas Internas</div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <Calendar size={16} color="#64748b" />
          <input type="month" style={s.input} value={mes} onChange={e => setMes(e.target.value)} />
        </div>
      </div>

      {/* Summary cards */}
      <div style={s.cards}>
        <div style={s.card('var(--card-bg-hover)', 'var(--border)')}>
          <div style={{ ...s.label, color: 'var(--muted)' }}>Total en Cuentas Internas</div>
          <div style={{ ...s.value, color: (data?.total_saldo || 0) >= 0 ? '#15803d' : '#dc2626' }}>{fmt(data?.total_saldo)}</div>
        </div>
        <div style={s.card('#f0fdf4', '#bbf7d0')}>
          <div style={{ ...s.label, color: 'var(--success-text)' }}>Mayor Saldo</div>
          <div style={{ ...s.value, color: 'var(--success-text)', fontSize: '1rem' }}>{data?.mayor_saldo?.nombre || '-'}</div>
          <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--success-text)', fontFamily: "'JetBrains Mono', monospace" }}>{fmt(data?.mayor_saldo?.saldo)}</div>
        </div>
        <div style={s.card('#fef2f2', '#fecaca')}>
          <div style={{ ...s.label, color: 'var(--danger-text)' }}>Menor Saldo</div>
          <div style={{ ...s.value, color: 'var(--danger-text)', fontSize: '1rem' }}>{data?.menor_saldo?.nombre || '-'}</div>
          <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--danger-text)', fontFamily: "'JetBrains Mono', monospace" }}>{fmt(data?.menor_saldo?.saldo)}</div>
        </div>
      </div>

      {/* Main table */}
      <div style={{ background: 'var(--card-bg)', borderRadius: 10, border: '1px solid var(--border)', overflow: 'hidden' }}>
        <table style={s.table}>
          <thead>
            <tr>
              <th style={s.th}>Unidad</th>
              <th style={{ ...s.th, textAlign: 'right' }}>Saldo Actual</th>
              <th style={{ ...s.th, textAlign: 'right' }}>Ingresos Mes</th>
              <th style={{ ...s.th, textAlign: 'right' }}>Gastos Mes</th>
              <th style={{ ...s.th, textAlign: 'right' }}>Resultado</th>
              <th style={{ ...s.th, textAlign: 'center' }}>Estado</th>
              <th style={{ ...s.th, width: 40 }}></th>
            </tr>
          </thead>
          <tbody>
            {cuentas.length === 0 && (
              <tr><td colSpan={7} style={{ ...s.td, textAlign: 'center', color: 'var(--muted)', padding: 32 }}>Sin cuentas internas</td></tr>
            )}
            {cuentas.map(c => {
              const ok = c.saldo_actual >= 0;
              const isExp = expanded === c.cuenta_id;
              return (
                <React.Fragment key={c.cuenta_id}>
                  <tr style={{ cursor: 'pointer', background: isExp ? 'var(--card-bg-hover)' : undefined }}
                      onClick={() => toggleKardex(c.cuenta_id)}>
                    <td style={{ ...s.td, fontWeight: 600 }}>{c.unidad_nombre}</td>
                    <td style={{ ...s.td, textAlign: 'right', fontWeight: 700, color: ok ? '#15803d' : '#dc2626', fontFamily: "'JetBrains Mono', monospace" }}>
                      {fmt(c.saldo_actual)}
                    </td>
                    <td style={{ ...s.td, textAlign: 'right', color: 'var(--success-text)', fontFamily: "'JetBrains Mono', monospace" }}>{fmt(c.ingresos_mes)}</td>
                    <td style={{ ...s.td, textAlign: 'right', color: 'var(--danger-text)', fontFamily: "'JetBrains Mono', monospace" }}>{fmt(c.gastos_mes)}</td>
                    <td style={{ ...s.td, textAlign: 'right', fontWeight: 700, color: c.resultado_mes >= 0 ? '#15803d' : '#dc2626', fontFamily: "'JetBrains Mono', monospace" }}>
                      {fmt(c.resultado_mes)}
                    </td>
                    <td style={{ ...s.td, textAlign: 'center' }}>
                      <span style={s.badge(ok)}>
                        {ok ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                        {ok ? 'Rentable' : 'Deficit'}
                      </span>
                    </td>
                    <td style={s.td}>{isExp ? <ChevronUp size={16} color="#64748b" /> : <ChevronDown size={16} color="#64748b" />}</td>
                  </tr>
                  {isExp && (
                    <tr>
                      <td colSpan={7} style={{ padding: 0 }}>
                        <div style={{ background: 'var(--card-bg-hover)', padding: '1rem', borderTop: '1px solid var(--border)' }}>
                          <div style={{ fontWeight: 700, fontSize: '0.85rem', marginBottom: 8, color: 'var(--text-secondary)' }}>
                            Kardex — {c.unidad_nombre} ({data?.periodo})
                          </div>
                          {kardexLoading ? (
                            <div style={{ textAlign: 'center', padding: 16, color: 'var(--muted)' }}>Cargando...</div>
                          ) : kardex && kardex.movimientos?.length > 0 ? (
                            <table style={{ ...s.table, fontSize: '0.75rem' }}>
                              <thead>
                                <tr>
                                  <th style={{ ...s.th, fontSize: '0.65rem' }}>Fecha</th>
                                  <th style={{ ...s.th, fontSize: '0.65rem' }}>Concepto</th>
                                  <th style={{ ...s.th, fontSize: '0.65rem' }}>Tipo</th>
                                  <th style={{ ...s.th, textAlign: 'right', fontSize: '0.65rem' }}>Ingreso</th>
                                  <th style={{ ...s.th, textAlign: 'right', fontSize: '0.65rem' }}>Egreso</th>
                                  <th style={{ ...s.th, textAlign: 'right', fontSize: '0.65rem' }}>Saldo</th>
                                </tr>
                              </thead>
                              <tbody>
                                {kardex.movimientos.map((m, i) => (
                                  <tr key={i}>
                                    <td style={s.td}>{m.fecha}</td>
                                    <td style={{ ...s.td, maxWidth: 250, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.concepto}</td>
                                    <td style={s.td}>
                                      <span style={{ padding: '2px 6px', borderRadius: 4, fontSize: '0.65rem', fontWeight: 600,
                                        background: m.tipo === 'ingreso' ? '#dcfce7' : 'var(--danger-bg)',
                                        color: m.tipo === 'ingreso' ? '#15803d' : '#dc2626' }}>
                                        {m.tipo === 'ingreso' ? 'INGRESO' : 'EGRESO'}
                                      </span>
                                    </td>
                                    <td style={{ ...s.td, textAlign: 'right', color: 'var(--success-text)', fontFamily: "'JetBrains Mono', monospace" }}>
                                      {m.ingreso > 0 ? fmt(m.ingreso) : ''}
                                    </td>
                                    <td style={{ ...s.td, textAlign: 'right', color: 'var(--danger-text)', fontFamily: "'JetBrains Mono', monospace" }}>
                                      {m.egreso > 0 ? fmt(m.egreso) : ''}
                                    </td>
                                    <td style={{ ...s.td, textAlign: 'right', fontWeight: 700, fontFamily: "'JetBrains Mono', monospace",
                                      color: m.saldo >= 0 ? '#15803d' : '#dc2626' }}>
                                      {fmt(m.saldo)}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                              <tfoot>
                                <tr style={{ background: 'var(--input-bg-readonly)' }}>
                                  <td colSpan={3} style={{ ...s.td, fontWeight: 700 }}>Totales</td>
                                  <td style={{ ...s.td, textAlign: 'right', fontWeight: 700, color: 'var(--success-text)', fontFamily: "'JetBrains Mono', monospace" }}>
                                    {fmt(kardex.total_ingresos)}
                                  </td>
                                  <td style={{ ...s.td, textAlign: 'right', fontWeight: 700, color: 'var(--danger-text)', fontFamily: "'JetBrains Mono', monospace" }}>
                                    {fmt(kardex.total_egresos)}
                                  </td>
                                  <td style={{ ...s.td, textAlign: 'right', fontWeight: 800, fontFamily: "'JetBrains Mono', monospace",
                                    color: kardex.saldo_final >= 0 ? '#15803d' : '#dc2626' }}>
                                    {fmt(kardex.saldo_final)}
                                  </td>
                                </tr>
                              </tfoot>
                            </table>
                          ) : (
                            <div style={{ textAlign: 'center', padding: 16, color: 'var(--muted)' }}>Sin movimientos en este periodo</div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
