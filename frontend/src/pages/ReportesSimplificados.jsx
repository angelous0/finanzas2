import React, { useState, useEffect, useCallback } from 'react';
import { BarChart3, RefreshCw, TrendingUp, TrendingDown, CreditCard, Wallet, Tag, Target } from 'lucide-react';
import {
  getReporteVentasPendientes, getReporteIngresosPorLinea, getReporteIngresosPorMarca,
  getReporteCobranzasPorLinea, getReportePendienteCobrar, getReporteGastosPorCategoria,
  getReporteGastosPorCentro, getReporteUtilidadPorLinea
} from '../services/api';
import { toast } from 'sonner';

const fmt = (v) => `S/ ${Number(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2 })}`;

export default function ReportesSimplificados() {
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
      const [vp, il, im, cl, pc, gc, gcc, ul] = await Promise.all([
        getReporteVentasPendientes(),
        getReporteIngresosPorLinea(params),
        getReporteIngresosPorMarca(params),
        getReporteCobranzasPorLinea(params),
        getReportePendienteCobrar(),
        getReporteGastosPorCategoria(params),
        getReporteGastosPorCentro(params),
        getReporteUtilidadPorLinea(params),
      ]);
      setData({
        ventasPend: vp.data,
        ingresoLinea: il.data,
        ingresoMarca: im.data,
        cobranzaLinea: cl.data,
        pendienteCobrar: pc.data,
        gastoCategoria: gc.data,
        gastoCentro: gcc.data,
        utilidadLinea: ul.data,
      });
    } catch { toast.error('Error cargando reportes'); }
    finally { setLoading(false); }
  }, [fechaDesde, fechaHasta]);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="loading"><div className="loading-spinner"></div></div>;

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1400px' }} data-testid="reportes-page">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <h1 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0 }}>Reportes Simplificados</h1>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <input type="date" className="form-input" value={fechaDesde} onChange={e => setFechaDesde(e.target.value)}
            style={{ fontSize: '0.8rem', padding: '4px 8px' }} data-testid="rep-fecha-desde" />
          <span style={{ color: 'var(--muted)', fontSize: '0.8rem' }}>a</span>
          <input type="date" className="form-input" value={fechaHasta} onChange={e => setFechaHasta(e.target.value)}
            style={{ fontSize: '0.8rem', padding: '4px 8px' }} data-testid="rep-fecha-hasta" />
          <button className="btn btn-primary btn-sm" onClick={load} data-testid="rep-refresh">
            <RefreshCw size={14} /> Aplicar
          </button>
        </div>
      </div>

      {/* Row 1: Ventas Pendientes + Utilidad */}
      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: '1rem', marginBottom: '1rem' }}>
        <Card title="Ventas Pendientes" icon={BarChart3} testId="rep-ventas-pend">
          <div style={{ textAlign: 'center', padding: '0.75rem 0' }}>
            <div style={{ fontSize: '2rem', fontWeight: 700, color: '#f59e0b' }}>{data.ventasPend?.cantidad || 0}</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>por revisar</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 600, marginTop: '0.25rem' }}>{fmt(data.ventasPend?.monto)}</div>
          </div>
        </Card>
        <Card title="Utilidad por Linea de Negocio" icon={TrendingUp} testId="rep-utilidad">
          <ReportTable
            headers={['Linea', 'Ingresos', 'Costos Prov.', 'G. Directos', 'Util. (antes)', 'Prorrateo', 'Util. (despues)']}
            rows={data.utilidadLinea?.map(r => [
              r.linea,
              { v: fmt(r.ingresos), color: '#22c55e' },
              { v: fmt(r.egresos_proveedores || 0), color: '#f97316' },
              { v: fmt(r.gastos_directos), color: '#ef4444' },
              { v: fmt(r.utilidad_antes), color: r.utilidad_antes >= 0 ? '#166534' : '#991b1b', bold: true },
              { v: fmt(r.gastos_prorrateados), color: '#8b5cf6' },
              { v: fmt(r.utilidad_despues), color: r.utilidad_despues >= 0 ? '#166534' : '#991b1b', bold: true },
            ]) || []}
            testId="utilidad-table"
          />
        </Card>
      </div>

      {/* Row 2: Ingresos por Linea + Ingresos por Marca */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
        <Card title="Ingresos por Linea" icon={TrendingUp} testId="rep-ing-linea">
          <ReportTable
            headers={['Linea', 'Ingresos']}
            rows={data.ingresoLinea?.map(r => [r.linea, { v: fmt(r.ingresos), color: '#22c55e', bold: true }]) || []}
            testId="ing-linea-table"
          />
        </Card>
        <Card title="Ingresos por Marca" icon={Tag} testId="rep-ing-marca">
          <ReportTable
            headers={['Marca', 'Ingresos']}
            rows={data.ingresoMarca?.map(r => [r.marca, { v: fmt(r.ingresos), color: '#22c55e', bold: true }]) || []}
            testId="ing-marca-table"
          />
        </Card>
      </div>

      {/* Row 3: Cobranzas + Pendiente Cobrar */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
        <Card title="Cobranzas por Linea" icon={CreditCard} testId="rep-cob-linea">
          <ReportTable
            headers={['Linea', 'Cobrado']}
            rows={data.cobranzaLinea?.map(r => [r.linea, { v: fmt(r.cobrado), color: '#059669', bold: true }]) || []}
            testId="cob-linea-table"
          />
        </Card>
        <Card title="Pendiente por Cobrar" icon={TrendingDown} testId="rep-pend-cobrar">
          <ReportTable
            headers={['Linea', 'Pendiente']}
            rows={data.pendienteCobrar?.map(r => [r.linea || 'Sin clasificar', { v: fmt(r.pendiente), color: '#ef4444', bold: true }]) || []}
            testId="pend-cobrar-table"
          />
        </Card>
      </div>

      {/* Row 4: Gastos por Categoría + Gastos por Centro */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <Card title="Gastos por Categoria" icon={Wallet} testId="rep-gasto-cat">
          <ReportTable
            headers={['Categoria', 'Cant.', 'Monto']}
            rows={data.gastoCategoria?.map(r => [r.categoria, r.cantidad, { v: fmt(r.monto), color: '#ef4444', bold: true }]) || []}
            testId="gasto-cat-table"
          />
        </Card>
        <Card title="Gastos por Centro de Costo" icon={Target} testId="rep-gasto-cc">
          <ReportTable
            headers={['Centro', 'Cant.', 'Monto']}
            rows={data.gastoCentro?.map(r => [r.centro_costo, r.cantidad, { v: fmt(r.monto), color: '#ef4444', bold: true }]) || []}
            testId="gasto-cc-table"
          />
        </Card>
      </div>
    </div>
  );
}

function Card({ title, icon: Icon, children, testId }) {
  return (
    <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden' }} data-testid={testId}>
      <div style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--table-row-border)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Icon size={16} color="#64748b" />
        <h3 style={{ fontSize: '0.8125rem', fontWeight: 600, margin: 0, color: 'var(--text-secondary)' }}>{title}</h3>
      </div>
      <div style={{ padding: '0.5rem' }}>{children}</div>
    </div>
  );
}

function ReportTable({ headers, rows, testId }) {
  if (!rows.length) return <p style={{ textAlign: 'center', color: 'var(--muted)', fontSize: '0.8rem', padding: '1rem' }}>Sin datos</p>;
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }} data-testid={testId}>
      <thead>
        <tr>
          {headers.map((h, i) => (
            <th key={i} style={{ padding: '4px 8px', textAlign: i === 0 ? 'left' : 'right', color: 'var(--muted)', fontWeight: 500, borderBottom: '1px solid var(--border)', fontSize: '0.75rem' }}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i} style={{ borderBottom: '1px solid #f8fafc' }}>
            {row.map((cell, j) => {
              const isObj = typeof cell === 'object' && cell !== null;
              return (
                <td key={j} style={{
                  padding: '5px 8px',
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
    </table>
  );
}
