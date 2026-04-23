import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import { toast } from 'sonner';
import {
  Factory, ArrowLeft, Download, Calendar, RefreshCw, TrendingUp, TrendingDown,
  Package, Users, DollarSign, FileText, AlertTriangle, CheckCircle2,
  ChevronDown, ChevronUp, Printer,
} from 'lucide-react';
import { getReportePnLUnidad, getUnidadesInternas } from '../services/api';

const fmt = (v, d = 2) => `S/ ${Number(v || 0).toLocaleString('es-PE', { minimumFractionDigits: d, maximumFractionDigits: d })}`;
const pct = (v) => `${Number(v || 0).toFixed(2)}%`;

const firstOfMonthISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
};
const lastOfMonthISO = () => {
  const d = new Date();
  const last = new Date(d.getFullYear(), d.getMonth() + 1, 0);
  return last.toISOString().slice(0, 10);
};

export default function PnLUnidadInterna() {
  const { id: unidadId } = useParams();
  const [searchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [unidades, setUnidades] = useState([]);
  const [desde, setDesde] = useState(searchParams.get('desde') || firstOfMonthISO());
  const [hasta, setHasta] = useState(searchParams.get('hasta') || lastOfMonthISO());
  const [expIng, setExpIng] = useState(true);
  const [expCxC, setExpCxC] = useState(true);
  const [expGas, setExpGas] = useState(true);
  const [gastoVista, setGastoVista] = useState('agrupado'); // 'agrupado' | 'detalle'

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const [pnlRes, uniRes] = await Promise.all([
        getReportePnLUnidad(unidadId, { fecha_desde: desde, fecha_hasta: hasta }),
        getUnidadesInternas(),
      ]);
      setData(pnlRes.data);
      setUnidades(uniRes.data || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error al cargar reporte');
    } finally {
      setLoading(false);
    }
  }, [unidadId, desde, hasta]);

  useEffect(() => { load(); }, [load]);

  const exportarCSV = () => {
    if (!data) return;
    const lines = [];
    lines.push(`P&L - ${data.unidad.nombre}`);
    lines.push(`Período: ${desde} a ${hasta}`);
    lines.push('');
    lines.push('INGRESOS');
    lines.push('N° Corte,Modelo,Persona,Servicio,Cantidad,Tarifa,Total,Factura');
    for (const i of data.ingresos.items) {
      lines.push([i.n_corte, i.modelo, i.persona, i.servicio, i.cantidad, i.tarifa, i.importe, i.factura_numero || ''].join(','));
    }
    lines.push(`TOTAL INGRESOS,,,,,,${data.ingresos.total}`);
    lines.push('');
    lines.push('CxC VIRTUAL (pendiente de procesar)');
    lines.push('N° Corte,Modelo,Persona,Servicio,Cantidad,Tarifa,Total,Factura');
    for (const i of data.cxc_virtual.items) {
      lines.push([i.n_corte, i.modelo, i.persona, i.servicio, i.cantidad, i.tarifa, i.importe, i.factura_numero || ''].join(','));
    }
    lines.push(`TOTAL CxC,,,,,,${data.cxc_virtual.total}`);
    lines.push('');
    lines.push('GASTOS');
    lines.push('Fecha,Categoría,Concepto,Monto,Origen');
    for (const g of data.gastos.items) {
      lines.push([g.fecha, g.categoria, g.concepto, g.monto, g.origen].join(','));
    }
    lines.push(`TOTAL GASTOS,,,${data.gastos.total}`);
    lines.push('');
    lines.push(`UTILIDAD,,,${data.utilidad.total}`);
    lines.push(`MARGEN %,,,${data.utilidad.margen_pct}`);
    const csv = lines.join('\n');
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `pnl_${data.unidad.nombre}_${desde}_${hasta}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const s = {
    page: { padding: '1.5rem', maxWidth: 1400, margin: '0 auto' },
    header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.25rem', flexWrap: 'wrap', gap: 12 },
    title: { fontSize: '1.6rem', fontWeight: 700, color: 'var(--text-heading)', display: 'flex', alignItems: 'center', gap: 10 },
    subtitle: { fontSize: '0.85rem', color: 'var(--muted)', marginTop: 4 },
    btn: { padding: '7px 14px', borderRadius: 6, border: '1px solid var(--border)', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 6, background: 'var(--card-bg)' },
    filters: { display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', background: 'var(--card-bg)', padding: '0.75rem 1rem', borderRadius: 8, border: '1px solid var(--border)', marginBottom: '1rem' },
    input: { padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border)', fontSize: '0.85rem', background: 'var(--card-bg)' },
    section: { background: 'var(--card-bg)', borderRadius: 10, border: '1px solid var(--border)', overflow: 'hidden', marginBottom: '1rem' },
    sectionHeader: (bg, color) => ({
      padding: '12px 18px', background: bg, color,
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      cursor: 'pointer', fontSize: '1rem', fontWeight: 700, letterSpacing: '0.02em',
    }),
    table: { width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' },
    th: { padding: '8px 14px', textAlign: 'left', fontWeight: 600, color: 'var(--muted)', borderBottom: '1px solid var(--border)', background: 'var(--card-bg-hover)', fontSize: '0.7rem', textTransform: 'uppercase' },
    td: { padding: '9px 14px', borderBottom: '1px solid var(--table-row-border)' },
    total: { padding: '10px 18px', background: 'var(--card-bg-hover)', fontWeight: 700, display: 'flex', justifyContent: 'space-between', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.95rem', borderTop: '2px solid var(--border)' },
    kpiRow: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginBottom: '1rem' },
    kpiCard: (bg, border, color) => ({ background: bg, borderRadius: 10, padding: '0.9rem 1rem', border: `1px solid ${border}`, color }),
    kpiLabel: { fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', marginBottom: 4, opacity: 0.85 },
    kpiValue: { fontSize: '1.2rem', fontWeight: 800, fontFamily: "'JetBrains Mono', monospace" },
    utilidadBox: (positive) => ({
      background: positive ? 'linear-gradient(135deg, #dcfce7, #bbf7d0)' : 'linear-gradient(135deg, #fef2f2, #fecaca)',
      border: `2px solid ${positive ? '#86efac' : '#fca5a5'}`,
      borderRadius: 12, padding: '1.25rem 1.5rem', marginBottom: '1rem',
      color: positive ? '#15803d' : '#dc2626',
    }),
  };

  if (loading && !data) {
    return <div style={s.page}><div style={{ textAlign: 'center', padding: 64, color: 'var(--muted)' }}>Cargando...</div></div>;
  }
  if (!data) return null;

  const hasIng = data.ingresos.items.length > 0;
  const hasCxC = data.cxc_virtual.items.length > 0;
  const hasGas = data.gastos.items.length > 0;
  const positive = data.utilidad.es_rentable;

  return (
    <div style={s.page} data-testid="pnl-unidad-page">
      <div style={s.header}>
        <div>
          <Link to="/cuentas-internas" style={{ color: 'var(--muted)', textDecoration: 'none', fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: 4, marginBottom: 4 }}>
            <ArrowLeft size={12} /> Volver a Cuentas Internas
          </Link>
          <div style={s.title}>
            <Factory size={24} color="#b45309" />
            P&L — {data.unidad.nombre}
          </div>
          <div style={s.subtitle}>
            Estado de resultados del período seleccionado. Muestra ingresos efectivos (NI procesadas),
            CxC virtual pendiente, gastos reales y utilidad.
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button style={s.btn} onClick={load} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'spin' : ''} /> Actualizar
          </button>
          <button style={s.btn} onClick={() => window.print()}>
            <Printer size={14} /> Imprimir
          </button>
          <button style={s.btn} onClick={exportarCSV}>
            <Download size={14} /> CSV
          </button>
        </div>
      </div>

      {/* Filtros */}
      <div style={s.filters}>
        <Calendar size={16} color="#64748b" />
        <label style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>Desde</label>
        <input type="date" style={s.input} value={desde} onChange={e => setDesde(e.target.value)} />
        <label style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>Hasta</label>
        <input type="date" style={s.input} value={hasta} onChange={e => setHasta(e.target.value)} />
        <span style={{ color: 'var(--muted)', fontSize: '0.75rem', marginLeft: 'auto' }}>Cambiar unidad:</span>
        <select
          style={s.input}
          value={unidadId}
          onChange={e => { if (e.target.value) window.location.href = `/reporte-pnl-unidad/${e.target.value}?desde=${desde}&hasta=${hasta}`; }}
        >
          {unidades.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}
        </select>
      </div>

      {/* UTILIDAD - hero */}
      <div style={s.utilidadBox(positive)}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <div style={{ fontSize: '0.75rem', fontWeight: 700, opacity: 0.8, marginBottom: 4, letterSpacing: '0.05em' }}>
              UTILIDAD DEL PERÍODO
            </div>
            <div style={{ fontSize: '2.5rem', fontWeight: 900, fontFamily: "'JetBrains Mono', monospace", letterSpacing: '-0.02em' }}>
              {fmt(data.utilidad.total)}
            </div>
            <div style={{ fontSize: '0.85rem', marginTop: 4, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              {positive ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
              Margen: <b>{pct(data.utilidad.margen_pct)}</b>
              {data.utilidad.margen_pct >= 20 && ' · Muy rentable'}
              {data.utilidad.margen_pct >= 0 && data.utilidad.margen_pct < 20 && ' · Rentable'}
              {data.utilidad.margen_pct < 0 && ' · En déficit'}
            </div>
          </div>
          <div style={{ textAlign: 'right', fontSize: '0.85rem' }}>
            <div>Ingresos: <b>{fmt(data.ingresos.total)}</b></div>
            <div>Gastos: <b>{fmt(data.gastos.total)}</b></div>
            <div style={{ marginTop: 8, paddingTop: 8, borderTop: `1px dashed ${positive ? '#86efac' : '#fca5a5'}` }}>
              + CxC pendiente: {fmt(data.cxc_virtual.total)}<br />
              = Utilidad potencial: <b>{fmt(data.kpis.utilidad_potencial)}</b>
            </div>
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div style={s.kpiRow}>
        <div style={s.kpiCard('#f0fdf4', '#bbf7d0', '#15803d')}>
          <div style={s.kpiLabel}>Ingresos (NI procesadas)</div>
          <div style={s.kpiValue}>{fmt(data.ingresos.total)}</div>
          <div style={{ fontSize: '0.7rem', marginTop: 2 }}>{data.ingresos.count} cargos · {data.ingresos.prendas} prendas</div>
        </div>
        <div style={s.kpiCard('#fef3c7', '#fde68a', '#b45309')}>
          <div style={s.kpiLabel}>📋 CxC Virtual</div>
          <div style={s.kpiValue}>{fmt(data.cxc_virtual.total)}</div>
          <div style={{ fontSize: '0.7rem', marginTop: 2 }}>{data.cxc_virtual.count} cargos pendientes</div>
        </div>
        <div style={s.kpiCard('#fef2f2', '#fecaca', '#dc2626')}>
          <div style={s.kpiLabel}>Gastos</div>
          <div style={s.kpiValue}>{fmt(data.gastos.total)}</div>
          <div style={{ fontSize: '0.7rem', marginTop: 2 }}>{data.gastos.count} movimientos</div>
        </div>
        <div style={s.kpiCard('#eff6ff', '#bfdbfe', '#1d4ed8')}>
          <div style={s.kpiLabel}>Prendas procesadas</div>
          <div style={s.kpiValue}>{data.kpis.prendas_total.toLocaleString('es-PE')}</div>
          <div style={{ fontSize: '0.7rem', marginTop: 2 }}>En el período</div>
        </div>
        <div style={s.kpiCard('#f5f3ff', '#ddd6fe', '#6d28d9')}>
          <div style={s.kpiLabel}>Costo real / prenda</div>
          <div style={s.kpiValue}>S/ {data.kpis.costo_real_por_prenda.toFixed(4)}</div>
          <div style={{ fontSize: '0.7rem', marginTop: 2 }}>Tarifa mercado: S/ {data.kpis.tarifa_mercado_promedio.toFixed(4)}</div>
        </div>
      </div>

      {/* INGRESOS */}
      <div style={s.section}>
        <div style={s.sectionHeader('#dcfce7', '#15803d')} onClick={() => setExpIng(!expIng)}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <DollarSign size={20} />
            INGRESOS
            <span style={{ fontSize: '0.75rem', opacity: 0.75, fontWeight: 500 }}>
              · NIs procesadas · {data.ingresos.count} cargos
            </span>
          </div>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '1.1rem', fontWeight: 800 }}>
              {fmt(data.ingresos.total)}
            </span>
            {expIng ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </div>
        </div>
        {expIng && hasIng && (
          <>
            <table style={s.table}>
              <thead>
                <tr>
                  <th style={s.th}>Fecha</th>
                  <th style={s.th}>N° Corte</th>
                  <th style={s.th}>Modelo</th>
                  <th style={s.th}>Persona</th>
                  <th style={s.th}>Servicio</th>
                  <th style={{ ...s.th, textAlign: 'right' }}>Cantidad</th>
                  <th style={{ ...s.th, textAlign: 'right' }}>Tarifa</th>
                  <th style={{ ...s.th, textAlign: 'right' }}>Total</th>
                  <th style={s.th}>Factura</th>
                </tr>
              </thead>
              <tbody>
                {data.ingresos.items.map((i, k) => (
                  <tr key={k}>
                    <td style={{ ...s.td, fontSize: '0.75rem' }}>{i.fecha}</td>
                    <td style={{ ...s.td, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>{i.n_corte || '—'}</td>
                    <td style={s.td}>{i.modelo}</td>
                    <td style={s.td}>{i.persona}</td>
                    <td style={s.td}>{i.servicio}</td>
                    <td style={{ ...s.td, textAlign: 'right', fontFamily: "'JetBrains Mono', monospace" }}>{i.cantidad.toLocaleString('es-PE')}</td>
                    <td style={{ ...s.td, textAlign: 'right', fontFamily: "'JetBrains Mono', monospace" }}>{i.tarifa.toFixed(4)}</td>
                    <td style={{ ...s.td, textAlign: 'right', fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", color: '#15803d' }}>{fmt(i.importe)}</td>
                    <td style={{ ...s.td, fontSize: '0.7rem', fontFamily: "'JetBrains Mono', monospace", color: '#b45309' }}>{i.factura_numero || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={s.total}>
              <span>Total ingresos ({data.ingresos.prendas} prendas)</span>
              <span style={{ color: '#15803d' }}>{fmt(data.ingresos.total)}</span>
            </div>
          </>
        )}
        {expIng && !hasIng && (
          <div style={{ padding: 32, textAlign: 'center', color: 'var(--muted)', fontSize: '0.85rem' }}>
            Sin ingresos procesados en este período. Cuando proceses NIs pendientes, aparecerán acá.
          </div>
        )}
      </div>

      {/* CxC VIRTUAL */}
      {hasCxC && (
        <div style={s.section}>
          <div style={s.sectionHeader('#fef3c7', '#b45309')} onClick={() => setExpCxC(!expCxC)}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <FileText size={18} />
              📋 CxC VIRTUAL
              <span style={{ fontSize: '0.75rem', opacity: 0.8, fontWeight: 500 }}>
                · NIs pendientes de procesar · no computado en utilidad
              </span>
            </div>
            <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '1rem', fontWeight: 700 }}>
                {fmt(data.cxc_virtual.total)}
              </span>
              {expCxC ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
            </div>
          </div>
          {expCxC && (
            <>
              <table style={s.table}>
                <thead>
                  <tr>
                    <th style={s.th}>Fecha</th>
                    <th style={s.th}>N° Corte</th>
                    <th style={s.th}>Modelo</th>
                    <th style={s.th}>Persona</th>
                    <th style={{ ...s.th, textAlign: 'right' }}>Cantidad</th>
                    <th style={{ ...s.th, textAlign: 'right' }}>Total</th>
                    <th style={s.th}>NI</th>
                  </tr>
                </thead>
                <tbody>
                  {data.cxc_virtual.items.map((i, k) => (
                    <tr key={k}>
                      <td style={{ ...s.td, fontSize: '0.75rem' }}>{i.fecha}</td>
                      <td style={{ ...s.td, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>{i.n_corte || '—'}</td>
                      <td style={s.td}>{i.modelo}</td>
                      <td style={s.td}>{i.persona}</td>
                      <td style={{ ...s.td, textAlign: 'right', fontFamily: "'JetBrains Mono', monospace" }}>{i.cantidad}</td>
                      <td style={{ ...s.td, textAlign: 'right', fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", color: '#b45309' }}>{fmt(i.importe)}</td>
                      <td style={{ ...s.td, fontSize: '0.7rem', fontFamily: "'JetBrains Mono', monospace" }}>{i.factura_numero || 'sin NI'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={s.total}>
                <span>Total CxC virtual ({data.cxc_virtual.prendas} prendas)</span>
                <span style={{ color: '#b45309' }}>{fmt(data.cxc_virtual.total)}</span>
              </div>
            </>
          )}
        </div>
      )}

      {/* GASTOS */}
      <div style={s.section}>
        <div style={s.sectionHeader('#fef2f2', '#dc2626')} onClick={() => setExpGas(!expGas)}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <TrendingDown size={20} />
            GASTOS
            <span style={{ fontSize: '0.75rem', opacity: 0.8, fontWeight: 500 }}>
              · {data.gastos.count} movimientos
            </span>
          </div>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '1.1rem', fontWeight: 800 }}>
              {fmt(data.gastos.total)}
            </span>
            {expGas ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </div>
        </div>
        {expGas && hasGas && (
          <>
            {/* Toggle vista agrupada / detalle */}
            <div style={{ padding: '8px 14px', display: 'flex', gap: 8, background: 'var(--card-bg-hover)', borderBottom: '1px solid var(--border)' }}>
              <button
                style={{ ...s.btn, fontSize: '0.7rem', padding: '4px 10px', background: gastoVista === 'agrupado' ? '#dc2626' : 'transparent', color: gastoVista === 'agrupado' ? '#fff' : 'var(--muted)' }}
                onClick={() => setGastoVista('agrupado')}
              >
                Por categoría
              </button>
              <button
                style={{ ...s.btn, fontSize: '0.7rem', padding: '4px 10px', background: gastoVista === 'detalle' ? '#dc2626' : 'transparent', color: gastoVista === 'detalle' ? '#fff' : 'var(--muted)' }}
                onClick={() => setGastoVista('detalle')}
              >
                Detalle completo
              </button>
            </div>
            <table style={s.table}>
              {gastoVista === 'agrupado' ? (
                <>
                  <thead>
                    <tr>
                      <th style={s.th}>Categoría</th>
                      <th style={{ ...s.th, textAlign: 'right' }}>Monto</th>
                      <th style={{ ...s.th, textAlign: 'right' }}>% del total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.gastos.agrupado_categoria.map((g, k) => {
                      const pctG = (g.monto / data.gastos.total * 100);
                      return (
                        <tr key={k}>
                          <td style={{ ...s.td, fontWeight: 600 }}>{g.categoria}</td>
                          <td style={{ ...s.td, textAlign: 'right', fontFamily: "'JetBrains Mono', monospace", color: '#dc2626', fontWeight: 700 }}>{fmt(g.monto)}</td>
                          <td style={{ ...s.td, textAlign: 'right' }}>
                            <span style={{ display: 'inline-block', minWidth: 50, textAlign: 'right' }}>{pct(pctG)}</span>
                            <span style={{ display: 'inline-block', marginLeft: 6, width: 60, height: 6, background: '#fecaca', borderRadius: 3, overflow: 'hidden', verticalAlign: 'middle' }}>
                              <span style={{ display: 'block', width: `${Math.min(pctG, 100)}%`, height: '100%', background: '#dc2626' }} />
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </>
              ) : (
                <>
                  <thead>
                    <tr>
                      <th style={s.th}>Fecha</th>
                      <th style={s.th}>Categoría</th>
                      <th style={s.th}>Concepto</th>
                      <th style={s.th}>Origen</th>
                      <th style={{ ...s.th, textAlign: 'right' }}>Monto</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.gastos.items.map((g, k) => (
                      <tr key={k}>
                        <td style={{ ...s.td, fontSize: '0.75rem' }}>{g.fecha}</td>
                        <td style={{ ...s.td, fontWeight: 600 }}>{g.categoria}</td>
                        <td style={{ ...s.td, color: 'var(--muted)' }}>{g.concepto}</td>
                        <td style={s.td}>
                          <span style={{ padding: '2px 6px', borderRadius: 4, fontSize: '0.65rem', fontWeight: 600, background: g.origen === 'factura' ? '#dbeafe' : '#fef3c7', color: g.origen === 'factura' ? '#1d4ed8' : '#b45309' }}>
                            {g.origen}
                          </span>
                        </td>
                        <td style={{ ...s.td, textAlign: 'right', fontFamily: "'JetBrains Mono', monospace", color: '#dc2626', fontWeight: 700 }}>{fmt(g.monto)}</td>
                      </tr>
                    ))}
                  </tbody>
                </>
              )}
            </table>
            <div style={s.total}>
              <span>Total gastos</span>
              <span style={{ color: '#dc2626' }}>{fmt(data.gastos.total)}</span>
            </div>
          </>
        )}
        {expGas && !hasGas && (
          <div style={{ padding: 32, textAlign: 'center', color: 'var(--muted)', fontSize: '0.85rem' }}>
            Sin gastos registrados en este período.
          </div>
        )}
      </div>

      {/* Análisis de rentabilidad */}
      <div style={s.section}>
        <div style={{ padding: '14px 18px', fontWeight: 700, fontSize: '0.95rem', background: 'var(--card-bg-hover)', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
          {positive ? <CheckCircle2 size={18} color="#15803d" /> : <AlertTriangle size={18} color="#dc2626" />}
          Análisis de Rentabilidad
        </div>
        <div style={{ padding: '1rem 1.25rem', fontSize: '0.85rem', lineHeight: 1.7 }}>
          {data.kpis.tarifa_mercado_promedio > 0 && data.kpis.costo_real_por_prenda > 0 ? (
            <>
              El <b>costo real por prenda</b> es <b>S/ {data.kpis.costo_real_por_prenda.toFixed(4)}</b> (= gastos totales / prendas procesadas).<br />
              El <b>precio de mercado</b> que estás pagando (tarifa) es <b>S/ {data.kpis.tarifa_mercado_promedio.toFixed(4)}</b> por prenda.<br />
              {data.kpis.costo_real_por_prenda <= data.kpis.tarifa_mercado_promedio ? (
                <span style={{ color: '#15803d', fontWeight: 600 }}>
                  ✅ Producir internamente es <b>{pct((1 - data.kpis.costo_real_por_prenda / data.kpis.tarifa_mercado_promedio) * 100)}</b> más barato que tercerizar.
                </span>
              ) : (
                <span style={{ color: '#dc2626', fontWeight: 600 }}>
                  ⚠️ Producir internamente cuesta <b>{pct((data.kpis.costo_real_por_prenda / data.kpis.tarifa_mercado_promedio - 1) * 100)}</b> MÁS que tercerizar. Revisar tarifa o reducir gastos.
                </span>
              )}
            </>
          ) : (
            <span style={{ color: 'var(--muted)' }}>
              Se necesita tener ingresos procesados y gastos cargados para calcular el análisis de rentabilidad.
            </span>
          )}
          {data.cxc_virtual.total > 0 && (
            <>
              <br /><br />
              📋 <b>Atención</b>: tenés <b>{fmt(data.cxc_virtual.total)}</b> en CxC virtual pendiente ({data.cxc_virtual.count} cargos).
              Si los procesás (desde Finanzas → Facturas → Procesar NI), la utilidad subiría a <b>{fmt(data.kpis.utilidad_potencial)}</b>.
            </>
          )}
        </div>
      </div>
    </div>
  );
}
