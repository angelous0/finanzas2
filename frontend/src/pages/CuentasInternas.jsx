import React, { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { Wallet, Calendar, TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight, ExternalLink, BarChart3 } from 'lucide-react';
import { getResumenCuentasInternas } from '../services/api';

const fmt = (v) => `S/ ${(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function CuentasInternas() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [mes, setMes] = useState(() => {
    const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  });

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const res = await getResumenCuentasInternas({ mes });
      setData(res.data);
    } catch { toast.error('Error al cargar cuentas internas'); }
    finally { setLoading(false); }
  }, [mes]);

  useEffect(() => { load(); }, [load]);

  const openKardex = (cuentaId) => {
    // Abrir el kardex en una pestaña nueva con el rango del mes filtrado
    const [y, m] = mes.split('-');
    const fecha_desde = `${y}-${m}-01`;
    const lastDay = new Date(parseInt(y), parseInt(m), 0).getDate();
    const fecha_hasta = `${y}-${m}-${String(lastDay).padStart(2, '0')}`;
    const url = `/cuentas-internas/${cuentaId}/kardex?desde=${fecha_desde}&hasta=${fecha_hasta}`;
    window.open(url, '_blank');
  };

  const openPnL = (unidadId) => {
    const [y, m] = mes.split('-');
    const fecha_desde = `${y}-${m}-01`;
    const lastDay = new Date(parseInt(y), parseInt(m), 0).getDate();
    const fecha_hasta = `${y}-${m}-${String(lastDay).padStart(2, '0')}`;
    const url = `/reporte-pnl-unidad/${unidadId}?desde=${fecha_desde}&hasta=${fecha_hasta}`;
    window.open(url, '_blank');
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
          <div style={{ ...s.label, color: 'var(--muted)' }}>💰 Saldo Caja Total</div>
          <div style={{ ...s.value, color: (data?.total_saldo || 0) >= 0 ? '#15803d' : '#dc2626' }}>{fmt(data?.total_saldo)}</div>
          <div style={{ fontSize: '0.65rem', color: 'var(--muted)', marginTop: 2 }}>NIs procesadas + gastos</div>
        </div>
        <div style={s.card('#fef3c7', '#fde68a')}>
          <div style={{ ...s.label, color: '#b45309' }}>📋 CxC Virtual Pendiente</div>
          <div style={{ ...s.value, color: '#b45309' }}>{fmt(data?.total_cxc_virtual)}</div>
          <div style={{ fontSize: '0.65rem', color: '#b45309', marginTop: 2 }}>NIs pendientes de procesar</div>
        </div>
        <div style={s.card('#eff6ff', '#bfdbfe')}>
          <div style={{ ...s.label, color: '#1d4ed8' }}>📊 Potencial Total</div>
          <div style={{ ...s.value, color: '#1d4ed8' }}>{fmt(data?.total_potencial)}</div>
          <div style={{ fontSize: '0.65rem', color: '#1d4ed8', marginTop: 2 }}>Si se procesa todo lo pendiente</div>
        </div>
      </div>

      {/* Main table */}
      <div style={{ background: 'var(--card-bg)', borderRadius: 10, border: '1px solid var(--border)', overflow: 'hidden' }}>
        <table style={s.table}>
          <thead>
            <tr>
              <th style={s.th}>Unidad</th>
              <th style={{ ...s.th, textAlign: 'right' }} title="Saldo acumulado en la cuenta ficticia de la unidad">💰 Saldo Caja</th>
              <th style={{ ...s.th, textAlign: 'right' }} title="Notas Internas pendientes de procesar (CxC virtual)">📋 CxC Virtual</th>
              <th style={{ ...s.th, textAlign: 'right' }} title="Saldo + CxC virtual: lo que tendrás si procesas todas las NIs">📊 Potencial</th>
              <th style={{ ...s.th, textAlign: 'right' }} title="Ingresos del mes: cargos internos procesados via NI">Ingresos Mes</th>
              <th style={{ ...s.th, textAlign: 'right' }} title="Egresos del mes de la cuenta ficticia (gastos + salidas)">Gastos Mes</th>
              <th style={{ ...s.th, textAlign: 'right' }} title="Ingresos − Gastos del mes">Resultado</th>
              <th style={{ ...s.th, textAlign: 'center' }} title="Rentable si Resultado ≥ 0 (este mes)">Estado</th>
              <th style={{ ...s.th, textAlign: 'center', width: 200 }}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {cuentas.length === 0 && (
              <tr><td colSpan={9} style={{ ...s.td, textAlign: 'center', color: 'var(--muted)', padding: 32 }}>Sin cuentas internas</td></tr>
            )}
            {cuentas.map(c => {
              // "Rentable/Déficit" refleja el resultado del período, no el saldo acumulado
              const ok = (c.resultado_mes || 0) >= 0;
              const saldoPositivo = c.saldo_actual >= 0;
              const hasPendiente = (c.cxc_virtual || 0) > 0;
              return (
                <tr key={c.cuenta_id}>
                  <td style={{ ...s.td, fontWeight: 600 }}>{c.unidad_nombre}</td>
                  <td style={{ ...s.td, textAlign: 'right', fontWeight: 700, color: saldoPositivo ? '#15803d' : '#dc2626', fontFamily: "'JetBrains Mono', monospace" }}>
                    {fmt(c.saldo_actual)}
                  </td>
                  <td style={{ ...s.td, textAlign: 'right', color: hasPendiente ? '#b45309' : 'var(--muted)', fontFamily: "'JetBrains Mono', monospace" }}>
                    {hasPendiente ? (
                      <span title={`${c.cxc_cargos_pendientes} cargo(s) en ${c.cxc_nis_pendientes} NI pendiente(s)`}>
                        {fmt(c.cxc_virtual)}
                        <div style={{ fontSize: '0.6rem', color: '#b45309', fontFamily: 'inherit' }}>
                          {c.cxc_nis_pendientes} NI · {c.cxc_cargos_pendientes} cargos
                        </div>
                      </span>
                    ) : '—'}
                  </td>
                  <td style={{ ...s.td, textAlign: 'right', fontWeight: 700, color: '#1d4ed8', fontFamily: "'JetBrains Mono', monospace" }}>
                    {fmt(c.potencial)}
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
                  <td style={{ ...s.td, textAlign: 'center' }}>
                    <div style={{ display: 'inline-flex', gap: 4 }}>
                      <button
                        onClick={() => openPnL(c.unidad_id)}
                        style={{
                          background: '#b45309', color: '#fff', border: 'none',
                          borderRadius: 6, padding: '6px 10px', fontSize: '0.75rem',
                          fontWeight: 600, cursor: 'pointer',
                          display: 'inline-flex', alignItems: 'center', gap: 4,
                        }}
                        title="Abrir P&L detallado en nueva pestaña"
                      >
                        <BarChart3 size={12} /> P&L
                      </button>
                      <button
                        onClick={() => openKardex(c.cuenta_id)}
                        style={{
                          background: '#3b82f6', color: '#fff', border: 'none',
                          borderRadius: 6, padding: '6px 10px', fontSize: '0.75rem',
                          fontWeight: 600, cursor: 'pointer',
                          display: 'inline-flex', alignItems: 'center', gap: 4,
                        }}
                        title="Abrir kardex en nueva pestaña"
                      >
                        <ExternalLink size={12} /> Kardex
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
