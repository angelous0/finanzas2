import React, { useState, useEffect, useCallback } from 'react';
import { getFlujoCajaGerencial } from '../services/api';
import { useEmpresa } from '../context/EmpresaContext';
import { toast } from 'sonner';
import { ArrowUpCircle, ArrowDownCircle, TrendingUp, RefreshCw } from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  Legend, Line, ComposedChart
} from 'recharts';

const fmt = (n) => `S/ ${Number(n || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtShort = (v) => `S/ ${(v / 1000).toFixed(1)}k`;
const fmtDate = (d) => {
  if (!d) return '';
  const dt = new Date(d + 'T00:00:00');
  return dt.toLocaleDateString('es-PE', { day: '2-digit', month: 'short' });
};

const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: 8, padding: '0.6rem 0.8rem', boxShadow: '0 4px 12px rgba(0,0,0,0.08)', fontSize: '0.78rem' }}>
      <div style={{ fontWeight: 600, marginBottom: '0.3rem' }}>{fmtDate(label)}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', color: p.color }}>
          <span>{p.name}</span>
          <span style={{ fontWeight: 600 }}>{fmt(p.value)}</span>
        </div>
      ))}
    </div>
  );
};

export default function FlujoCaja() {
  const { empresaActual } = useEmpresa();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const hoy = new Date();
  const inicio3m = new Date(hoy.getFullYear(), hoy.getMonth() - 2, 1);
  const [fechaDesde, setFechaDesde] = useState(inicio3m.toISOString().split('T')[0]);
  const [fechaHasta, setFechaHasta] = useState(hoy.toISOString().split('T')[0]);
  const [agrupacion, setAgrupacion] = useState('diario');

  const loadData = useCallback(async () => {
    if (!empresaActual || !fechaDesde || !fechaHasta) return;
    setLoading(true);
    try {
      const res = await getFlujoCajaGerencial({ fecha_desde: fechaDesde, fecha_hasta: fechaHasta, agrupacion });
      setData(res.data);
    } catch (err) {
      console.error(err);
      toast.error('Error al cargar flujo de caja');
    } finally {
      setLoading(false);
    }
  }, [empresaActual, fechaDesde, fechaHasta, agrupacion]);

  useEffect(() => { loadData(); }, [loadData]);

  const timeline = data?.timeline || [];
  const totales = data?.totales || {};

  return (
    <div data-testid="flujo-caja-page">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 className="page-title">Flujo de Caja</h1>
          <p className="page-subtitle">Movimientos reales de tesoreria - Fuente unica de verdad</p>
        </div>
        <button className="btn btn-primary" onClick={loadData} disabled={loading} data-testid="refresh-flujo-btn">
          <RefreshCw size={16} className={loading ? 'spin' : ''} /> Actualizar
        </button>
      </div>

      <div className="page-content">
        {/* Filters */}
        <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem', flexWrap: 'wrap', alignItems: 'end' }}>
          <div>
            <label className="form-label">Desde</label>
            <input type="date" className="form-input" value={fechaDesde}
              onChange={e => setFechaDesde(e.target.value)} data-testid="flujo-fecha-desde" />
          </div>
          <div>
            <label className="form-label">Hasta</label>
            <input type="date" className="form-input" value={fechaHasta}
              onChange={e => setFechaHasta(e.target.value)} data-testid="flujo-fecha-hasta" />
          </div>
          <div>
            <label className="form-label">Agrupacion</label>
            <select className="form-input" value={agrupacion}
              onChange={e => setAgrupacion(e.target.value)} data-testid="flujo-agrupacion">
              <option value="diario">Diario</option>
              <option value="semanal">Semanal</option>
              <option value="mensual">Mensual</option>
            </select>
          </div>
        </div>

        {/* KPI Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
          <div className="card" style={{ padding: '1.25rem' }} data-testid="kpi-ingresos">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--muted)', fontWeight: 600, letterSpacing: '0.05em' }}>Total Ingresos</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#22C55E', fontFamily: "'Manrope', sans-serif" }}>{fmt(totales.ingresos)}</div>
              </div>
              <ArrowUpCircle size={28} color="#22C55E" />
            </div>
          </div>
          <div className="card" style={{ padding: '1.25rem' }} data-testid="kpi-egresos">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--muted)', fontWeight: 600, letterSpacing: '0.05em' }}>Total Egresos</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#EF4444', fontFamily: "'Manrope', sans-serif" }}>{fmt(totales.egresos)}</div>
              </div>
              <ArrowDownCircle size={28} color="#EF4444" />
            </div>
          </div>
          <div className="card" style={{ padding: '1.25rem' }} data-testid="kpi-flujo-neto">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--muted)', fontWeight: 600, letterSpacing: '0.05em' }}>Flujo Neto</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 700, color: totales.flujo_neto >= 0 ? '#22C55E' : '#EF4444', fontFamily: "'Manrope', sans-serif" }}>{fmt(totales.flujo_neto)}</div>
              </div>
              <TrendingUp size={28} color={totales.flujo_neto >= 0 ? '#22C55E' : '#EF4444'} />
            </div>
          </div>
        </div>

        {/* Chart */}
        <div className="card" style={{ marginBottom: '1.5rem' }} data-testid="flujo-chart">
          <div className="card-header">
            <h3 className="card-title">Flujo de Caja - {agrupacion.charAt(0).toUpperCase() + agrupacion.slice(1)}</h3>
          </div>
          <div className="card-content" style={{ height: 340 }}>
            {loading ? (
              <div className="loading"><div className="loading-spinner"></div></div>
            ) : timeline.length === 0 ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--muted)' }}>
                Sin movimientos en el periodo
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={timeline} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="periodo" tick={{ fontSize: 11 }} tickFormatter={fmtDate} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={fmtShort} />
                  <Tooltip content={<ChartTooltip />} />
                  <Legend wrapperStyle={{ fontSize: '0.75rem' }} />
                  <Bar dataKey="total_ingresos" name="Ingresos" fill="#22C55E" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="total_egresos" name="Egresos" fill="#EF4444" radius={[4, 4, 0, 0]} />
                  <Line type="monotone" dataKey="saldo_acumulado" name="Saldo Acum." stroke="#3B82F6" strokeWidth={2} dot={false} />
                </ComposedChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Detail Table */}
        <div className="card" data-testid="flujo-table-card">
          <div className="card-header">
            <h3 className="card-title">Detalle por Periodo</h3>
          </div>
          <div className="data-table-wrapper">
            {loading ? (
              <div className="loading"><div className="loading-spinner"></div></div>
            ) : timeline.length === 0 ? (
              <div className="empty-state" style={{ padding: '2rem' }}>
                <TrendingUp size={40} style={{ color: '#d1d5db', marginBottom: '0.5rem' }} />
                <div className="empty-state-title">Sin movimientos</div>
              </div>
            ) : (
              <table className="data-table" data-testid="flujo-table">
                <thead>
                  <tr>
                    <th>Periodo</th>
                    <th className="text-right">Ventas</th>
                    <th className="text-right">Cobranzas</th>
                    <th className="text-right" style={{ color: '#22C55E' }}>Total Ingresos</th>
                    <th className="text-right">Gastos</th>
                    <th className="text-right">Pagos CxP</th>
                    <th className="text-right" style={{ color: '#EF4444' }}>Total Egresos</th>
                    <th className="text-right">Flujo Neto</th>
                    <th className="text-right">Saldo Acum.</th>
                  </tr>
                </thead>
                <tbody>
                  {timeline.map((r, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 500 }}>{fmtDate(r.periodo)}</td>
                      <td className="text-right">{fmt(r.ingresos_ventas)}</td>
                      <td className="text-right">{fmt(r.cobranzas_cxc)}</td>
                      <td className="text-right" style={{ fontWeight: 600, color: '#22C55E' }}>{fmt(r.total_ingresos)}</td>
                      <td className="text-right">{fmt(r.egresos_gastos)}</td>
                      <td className="text-right">{fmt(r.pagos_cxp)}</td>
                      <td className="text-right" style={{ fontWeight: 600, color: '#EF4444' }}>{fmt(r.total_egresos)}</td>
                      <td className="text-right" style={{ fontWeight: 600, color: r.flujo_neto >= 0 ? '#22C55E' : '#EF4444' }}>{fmt(r.flujo_neto)}</td>
                      <td className="text-right" style={{ fontWeight: 700, color: r.saldo_acumulado >= 0 ? 'var(--primary)' : '#EF4444' }}>{fmt(r.saldo_acumulado)}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr style={{ fontWeight: 700, borderTop: '2px solid var(--border)' }}>
                    <td>TOTAL</td>
                    <td className="text-right">{fmt(timeline.reduce((s, r) => s + r.ingresos_ventas, 0))}</td>
                    <td className="text-right">{fmt(timeline.reduce((s, r) => s + r.cobranzas_cxc, 0))}</td>
                    <td className="text-right" style={{ color: '#22C55E' }}>{fmt(totales.ingresos)}</td>
                    <td className="text-right">{fmt(timeline.reduce((s, r) => s + r.egresos_gastos, 0))}</td>
                    <td className="text-right">{fmt(timeline.reduce((s, r) => s + r.pagos_cxp, 0))}</td>
                    <td className="text-right" style={{ color: '#EF4444' }}>{fmt(totales.egresos)}</td>
                    <td className="text-right" style={{ color: totales.flujo_neto >= 0 ? '#22C55E' : '#EF4444' }}>{fmt(totales.flujo_neto)}</td>
                    <td className="text-right"></td>
                  </tr>
                </tfoot>
              </table>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
