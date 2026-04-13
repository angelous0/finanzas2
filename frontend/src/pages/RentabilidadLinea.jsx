import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Download, TrendingUp, CreditCard, Wallet, BarChart3, DollarSign } from 'lucide-react';
import {
  getReporteVentasPorLinea, getReporteCobranzaPorLinea2,
  getReporteCruceLineaMarca, getReporteGastosDirectosPorLinea,
  getReporteDineroPorLinea
} from '../services/api';
import { toast } from 'sonner';
import * as XLSX from 'xlsx';

const fmt = (v) => `S/ ${Number(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2 })}`;
const pct = (v) => `${Number(v || 0).toFixed(1)}%`;

const TABS = [
  { id: 'dinero', label: 'Dinero por Linea', icon: DollarSign },
  { id: 'ventas', label: 'Ventas por Linea', icon: TrendingUp },
  { id: 'cobranza', label: 'Cobranza por Linea', icon: CreditCard },
  { id: 'cruce', label: 'Linea x Marca', icon: BarChart3 },
  { id: 'gastos', label: 'Gastos por Linea', icon: Wallet },
];

export default function RentabilidadLinea() {
  const [tab, setTab] = useState('dinero');
  const [fechaDesde, setFechaDesde] = useState(() => {
    const d = new Date(); d.setDate(1); return d.toISOString().split('T')[0];
  });
  const [fechaHasta, setFechaHasta] = useState(() => new Date().toISOString().split('T')[0]);
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { fecha_desde: fechaDesde, fecha_hasta: fechaHasta };
      const [ventas, cobranza, cruce, gastos, dinero] = await Promise.all([
        getReporteVentasPorLinea(params),
        getReporteCobranzaPorLinea2(params),
        getReporteCruceLineaMarca(params),
        getReporteGastosDirectosPorLinea(params),
        getReporteDineroPorLinea(params),
      ]);
      setData({
        ventas: ventas.data,
        cobranza: cobranza.data,
        cruce: cruce.data,
        gastos: gastos.data,
        dinero: dinero.data,
      });
    } catch {
      toast.error('Error cargando reportes');
    } finally {
      setLoading(false);
    }
  }, [fechaDesde, fechaHasta]);

  useEffect(() => { load(); }, [load]);

  const exportExcel = () => {
    try {
      const wb = XLSX.utils.book_new();
      if (tab === 'ventas' && data.ventas?.data) {
        const ws = XLSX.utils.json_to_sheet(data.ventas.data.map(r => ({
          'Linea': r.linea, 'Ventas': r.ventas, 'Tickets': r.tickets, 'Ticket Promedio': r.ticket_promedio,
        })));
        XLSX.utils.book_append_sheet(wb, ws, 'Ventas por Linea');
      } else if (tab === 'cobranza' && data.cobranza?.data) {
        const ws = XLSX.utils.json_to_sheet(data.cobranza.data.map(r => ({
          'Linea': r.linea, 'Vendido': r.vendido, 'Cobrado': r.cobrado,
          'Pendiente': r.pendiente, '% Cobrado': r.pct_cobrado,
        })));
        XLSX.utils.book_append_sheet(wb, ws, 'Cobranza por Linea');
      } else if (tab === 'cruce' && data.cruce) {
        const rows = [];
        data.cruce.forEach(ln => ln.marcas.forEach(m => rows.push({
          'Linea': ln.linea, 'Marca': m.marca, 'Ventas': m.ventas, 'Tickets': m.tickets, '%': m.pct,
        })));
        const ws = XLSX.utils.json_to_sheet(rows);
        XLSX.utils.book_append_sheet(wb, ws, 'Linea x Marca');
      } else if (tab === 'gastos' && data.gastos?.data) {
        const ws = XLSX.utils.json_to_sheet(data.gastos.data.map(r => ({
          'Linea': r.linea, 'Gastos': r.total_gastos, 'Facturas Prov.': r.total_facturas, 'Total Egresos': r.total_egresos,
        })));
        XLSX.utils.book_append_sheet(wb, ws, 'Gastos por Linea');
      } else if (tab === 'dinero' && data.dinero?.data) {
        const ws = XLSX.utils.json_to_sheet(data.dinero.data.map(r => ({
          'Linea': r.linea, 'Ventas': r.ventas, 'Cobranzas': r.cobranzas,
          'CxC Pendiente': r.cxc_pendiente, 'Gastos': r.gastos, 'Saldo Neto': r.saldo_neto,
        })));
        XLSX.utils.book_append_sheet(wb, ws, 'Dinero por Linea');
      }
      XLSX.writeFile(wb, `reporte_${tab}_${fechaDesde}_${fechaHasta}.xlsx`);
      toast.success('Exportado a Excel');
    } catch { toast.error('Error al exportar'); }
  };

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1400px' }} data-testid="rentabilidad-linea-page">
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, color: 'var(--text-heading)' }}>Rentabilidad x Linea</h1>
          <p style={{ fontSize: '0.8rem', color: 'var(--muted)', margin: '0.25rem 0 0' }}>Control de dinero por linea de negocio</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <input type="date" className="form-input" value={fechaDesde} onChange={e => setFechaDesde(e.target.value)}
            style={{ fontSize: '0.8rem', padding: '4px 8px' }} data-testid="rl-fecha-desde" />
          <span style={{ color: 'var(--muted)', fontSize: '0.8rem' }}>a</span>
          <input type="date" className="form-input" value={fechaHasta} onChange={e => setFechaHasta(e.target.value)}
            style={{ fontSize: '0.8rem', padding: '4px 8px' }} data-testid="rl-fecha-hasta" />
          <button className="btn btn-primary btn-sm" onClick={load} data-testid="rl-refresh">
            <RefreshCw size={14} /> Aplicar
          </button>
          <button className="btn btn-outline btn-sm" onClick={exportExcel} data-testid="rl-export">
            <Download size={14} /> Excel
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0.25rem', marginBottom: '1rem', borderBottom: '2px solid var(--border)', paddingBottom: '0' }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            data-testid={`rl-tab-${t.id}`}
            style={{
              padding: '0.5rem 1rem',
              fontSize: '0.8125rem',
              fontWeight: tab === t.id ? 700 : 500,
              color: tab === t.id ? 'var(--text-heading)' : 'var(--muted)',
              background: 'none',
              border: 'none',
              borderBottom: tab === t.id ? '2px solid #0f172a' : '2px solid transparent',
              marginBottom: '-2px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.375rem',
              transition: 'all 0.15s',
            }}
          >
            <t.icon size={14} />
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <div className="loading"><div className="loading-spinner"></div></div>
      ) : (
        <>
          {tab === 'dinero' && <DineroPorLinea data={data.dinero} />}
          {tab === 'ventas' && <VentasPorLinea data={data.ventas} />}
          {tab === 'cobranza' && <CobranzaPorLinea data={data.cobranza} />}
          {tab === 'cruce' && <CruceLineaMarca data={data.cruce} />}
          {tab === 'gastos' && <GastosPorLinea data={data.gastos} />}
        </>
      )}
    </div>
  );
}


/* ========== DINERO POR LINEA ========== */
function DineroPorLinea({ data }) {
  if (!data) return <Empty />;
  const { data: rows, totales } = data;

  return (
    <div data-testid="dinero-por-linea">
      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '0.75rem', marginBottom: '1rem' }}>
        <KPI label="Ventas Confirmadas" value={fmt(totales.ventas)} color="#22c55e" />
        <KPI label="Cobranzas Reales" value={fmt(totales.cobranzas)} color="#059669" />
        <KPI label="CxC Pendiente" value={fmt(totales.cxc_pendiente)} color="#f59e0b" />
        <KPI label="Gastos Directos" value={fmt(totales.gastos)} color="#ef4444" />
        <KPI label="Saldo Neto" value={fmt(totales.saldo_neto)} color={totales.saldo_neto >= 0 ? '#166534' : '#991b1b'} bold />
      </div>
      {rows.length === 0 ? <Empty /> : (
        <Table
          testId="dinero-table"
          headers={['Linea de Negocio', 'Ventas', 'Cobranzas', 'CxC Pend.', 'Gastos', 'Saldo Neto']}
          rows={rows.map(r => [
            r.linea,
            { v: fmt(r.ventas), color: '#22c55e' },
            { v: fmt(r.cobranzas), color: '#059669' },
            { v: fmt(r.cxc_pendiente), color: '#f59e0b' },
            { v: fmt(r.gastos), color: '#ef4444' },
            { v: fmt(r.saldo_neto), color: r.saldo_neto >= 0 ? '#166534' : '#991b1b', bold: true },
          ])}
          footer={[
            'TOTAL',
            { v: fmt(totales.ventas), color: '#22c55e', bold: true },
            { v: fmt(totales.cobranzas), color: '#059669', bold: true },
            { v: fmt(totales.cxc_pendiente), color: '#f59e0b', bold: true },
            { v: fmt(totales.gastos), color: '#ef4444', bold: true },
            { v: fmt(totales.saldo_neto), color: totales.saldo_neto >= 0 ? '#166534' : '#991b1b', bold: true },
          ]}
        />
      )}
    </div>
  );
}


/* ========== VENTAS POR LINEA ========== */
function VentasPorLinea({ data }) {
  if (!data) return <Empty />;
  const { data: rows, totales } = data;

  return (
    <div data-testid="ventas-por-linea">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem', marginBottom: '1rem' }}>
        <KPI label="Total Ventas" value={fmt(totales.ventas)} color="#22c55e" />
        <KPI label="Total Tickets" value={totales.tickets} color="#3b82f6" />
        <KPI label="Ticket Promedio" value={fmt(totales.ticket_promedio)} color="#8b5cf6" />
      </div>
      {rows.length === 0 ? <Empty /> : (
        <Table
          testId="ventas-linea-table"
          headers={['Linea de Negocio', 'Ventas Confirmadas', 'Tickets', 'Ticket Promedio']}
          rows={rows.map(r => [
            r.linea,
            { v: fmt(r.ventas), color: '#22c55e', bold: true },
            r.tickets,
            { v: fmt(r.ticket_promedio), color: '#8b5cf6' },
          ])}
          footer={[
            'TOTAL',
            { v: fmt(totales.ventas), color: '#22c55e', bold: true },
            { v: totales.tickets, bold: true },
            { v: fmt(totales.ticket_promedio), color: '#8b5cf6', bold: true },
          ]}
        />
      )}
    </div>
  );
}


/* ========== COBRANZA POR LINEA ========== */
function CobranzaPorLinea({ data }) {
  if (!data) return <Empty />;
  const { data: rows, totales } = data;

  return (
    <div data-testid="cobranza-por-linea">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.75rem', marginBottom: '1rem' }}>
        <KPI label="Total Vendido" value={fmt(totales.vendido)} color="#22c55e" />
        <KPI label="Total Cobrado" value={fmt(totales.cobrado)} color="#059669" />
        <KPI label="Pendiente Cobrar" value={fmt(totales.pendiente)} color="#ef4444" />
        <KPI label="% Cobrado" value={pct(totales.pct_cobrado)} color="#3b82f6" />
      </div>
      {rows.length === 0 ? <Empty /> : (
        <Table
          testId="cobranza-linea-table"
          headers={['Linea de Negocio', 'Vendido', 'Cobrado', 'Pendiente', '% Cobrado']}
          rows={rows.map(r => [
            r.linea,
            { v: fmt(r.vendido), color: '#22c55e' },
            { v: fmt(r.cobrado), color: '#059669', bold: true },
            { v: fmt(r.pendiente), color: '#ef4444' },
            { v: pct(r.pct_cobrado), color: r.pct_cobrado >= 80 ? '#059669' : r.pct_cobrado >= 50 ? '#f59e0b' : '#ef4444', bold: true },
          ])}
          footer={[
            'TOTAL',
            { v: fmt(totales.vendido), color: '#22c55e', bold: true },
            { v: fmt(totales.cobrado), color: '#059669', bold: true },
            { v: fmt(totales.pendiente), color: '#ef4444', bold: true },
            { v: pct(totales.pct_cobrado), color: '#3b82f6', bold: true },
          ]}
        />
      )}
    </div>
  );
}


/* ========== CRUCE LINEA x MARCA ========== */
function CruceLineaMarca({ data }) {
  if (!data || data.length === 0) return <Empty />;

  return (
    <div data-testid="cruce-linea-marca">
      {data.map((linea) => (
        <div key={linea.linea} style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: '8px', marginBottom: '0.75rem', overflow: 'hidden' }}>
          <div style={{ padding: '0.625rem 1rem', borderBottom: '1px solid var(--table-row-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--card-bg-hover)' }}>
            <span style={{ fontWeight: 700, fontSize: '0.875rem', color: 'var(--text-heading)' }}>{linea.linea}</span>
            <span style={{ fontWeight: 600, fontSize: '0.875rem', color: '#059669' }}>{fmt(linea.total_ventas)}</span>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }} data-testid={`cruce-table-${linea.linea}`}>
            <thead>
              <tr>
                <th style={{ padding: '4px 12px', textAlign: 'left', color: 'var(--muted)', fontWeight: 500, fontSize: '0.75rem' }}>Marca</th>
                <th style={{ padding: '4px 12px', textAlign: 'right', color: 'var(--muted)', fontWeight: 500, fontSize: '0.75rem' }}>Ventas</th>
                <th style={{ padding: '4px 12px', textAlign: 'right', color: 'var(--muted)', fontWeight: 500, fontSize: '0.75rem' }}>Tickets</th>
                <th style={{ padding: '4px 12px', textAlign: 'right', color: 'var(--muted)', fontWeight: 500, fontSize: '0.75rem' }}>%</th>
              </tr>
            </thead>
            <tbody>
              {linea.marcas.map((m) => (
                <tr key={m.marca} style={{ borderTop: '1px solid var(--table-row-border)' }}>
                  <td style={{ padding: '5px 12px', fontWeight: 500 }}>{m.marca}</td>
                  <td style={{ padding: '5px 12px', textAlign: 'right', color: '#22c55e', fontWeight: 600 }}>{fmt(m.ventas)}</td>
                  <td style={{ padding: '5px 12px', textAlign: 'right', color: 'var(--muted)' }}>{m.tickets}</td>
                  <td style={{ padding: '5px 12px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '0.5rem' }}>
                      <div style={{ width: '60px', height: '6px', background: 'var(--border)', borderRadius: '3px', overflow: 'hidden' }}>
                        <div style={{ width: `${m.pct}%`, height: '100%', background: '#22c55e', borderRadius: '3px' }} />
                      </div>
                      <span style={{ fontSize: '0.75rem', color: 'var(--muted)', minWidth: '36px', textAlign: 'right' }}>{pct(m.pct)}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}


/* ========== GASTOS POR LINEA ========== */
function GastosPorLinea({ data }) {
  if (!data) return <Empty />;
  const { data: rows, totales } = data;

  return (
    <div data-testid="gastos-por-linea">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem', marginBottom: '1rem' }}>
        <KPI label="Total Gastos" value={fmt(totales.total_gastos)} color="#ef4444" />
        <KPI label="Total Facturas Prov." value={fmt(totales.total_facturas)} color="#f97316" />
        <KPI label="Total Egresos" value={fmt(totales.total_egresos)} color="#991b1b" bold />
      </div>
      {rows.length === 0 ? <Empty /> : (
        <Table
          testId="gastos-linea-table"
          headers={['Linea de Negocio', 'Gastos', 'Facturas Prov.', 'Total Egresos']}
          rows={rows.map(r => [
            r.linea,
            { v: fmt(r.total_gastos), color: '#ef4444' },
            { v: fmt(r.total_facturas), color: '#f97316' },
            { v: fmt(r.total_egresos), color: 'var(--danger-text)', bold: true },
          ])}
          footer={[
            'TOTAL',
            { v: fmt(totales.total_gastos), color: '#ef4444', bold: true },
            { v: fmt(totales.total_facturas), color: '#f97316', bold: true },
            { v: fmt(totales.total_egresos), color: 'var(--danger-text)', bold: true },
          ]}
        />
      )}
    </div>
  );
}


/* ========== SHARED COMPONENTS ========== */
function KPI({ label, value, color, bold }) {
  return (
    <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: '8px', padding: '0.75rem 1rem' }}>
      <div style={{ fontSize: '0.7rem', color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '0.25rem' }}>{label}</div>
      <div style={{ fontSize: '1.125rem', fontWeight: bold ? 800 : 700, color }}>{value}</div>
    </div>
  );
}

function Table({ headers, rows, footer, testId }) {
  return (
    <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem' }} data-testid={testId}>
        <thead>
          <tr style={{ background: 'var(--card-bg-hover)' }}>
            {headers.map((h, i) => (
              <th key={i} style={{ padding: '0.5rem 0.75rem', textAlign: i === 0 ? 'left' : 'right', color: 'var(--text-label)', fontWeight: 600, borderBottom: '2px solid var(--border)', fontSize: '0.75rem' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} style={{ borderBottom: '1px solid var(--table-row-border)' }}>
              {row.map((cell, j) => {
                const isObj = typeof cell === 'object' && cell !== null;
                return (
                  <td key={j} style={{
                    padding: '0.5rem 0.75rem',
                    textAlign: j === 0 ? 'left' : 'right',
                    fontWeight: (j === 0 || (isObj && cell.bold)) ? 600 : 400,
                    color: isObj ? cell.color : 'var(--text-primary)',
                  }}>
                    {isObj ? cell.v : cell}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
        {footer && (
          <tfoot>
            <tr style={{ background: 'var(--card-bg-hover)', borderTop: '2px solid var(--border)' }}>
              {footer.map((cell, j) => {
                const isObj = typeof cell === 'object' && cell !== null;
                return (
                  <td key={j} style={{
                    padding: '0.5rem 0.75rem',
                    textAlign: j === 0 ? 'left' : 'right',
                    fontWeight: 700,
                    fontSize: '0.8125rem',
                    color: isObj ? cell.color : 'var(--text-heading)',
                  }}>
                    {isObj ? cell.v : cell}
                  </td>
                );
              })}
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  );
}

function Empty() {
  return (
    <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--muted)', fontSize: '0.875rem' }}>
      Sin datos para el periodo seleccionado
    </div>
  );
}
