import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Scale, TrendingUp, Banknote, Package, ArrowUpRight, ArrowDownRight, Minus, ChevronRight, ChevronDown, BarChart3, Clock, Users, Download, DollarSign, CreditCard, Wallet, Layout, Tag, Target, TrendingDown } from 'lucide-react';
import {
  getReporteBalanceGeneral, getReporteEstadoResultados,
  getReporteInventarioValorizado,
  getReporteCxpAging, getReporteCxcAging,
  getFlujoCajaGerencial,
  getReporteVentasPorLinea, getReporteCobranzaPorLinea2,
  getReporteCruceLineaMarca, getReporteGastosDirectosPorLinea,
  getReporteDineroPorLinea,
  getReporteVentasPendientes, getReporteIngresosPorMarca,
  getReportePendienteCobrar, getReporteGastosPorCategoria,
  getReporteGastosPorCentro, getReporteUtilidadPorLinea
} from '../services/api';
import { toast } from 'sonner';
import * as XLSX from 'xlsx';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  Legend, Line, ComposedChart
} from 'recharts';

const fmt = (v) => `S/ ${Number(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtNum = (v) => Number(v || 0).toFixed(2);

function exportRentabilidadDetallado(data, subTab) {
  if (!data) return;
  const wb = XLSX.utils.book_new();
  const sdata = data[subTab];
  if (!sdata?.data?.length && !Array.isArray(sdata)) { toast.info('Sin datos para exportar'); return; }
  const label = SUB_TABS_RENT.find(t => t.id === subTab)?.label || subTab;

  if (subTab === 'cruce' && Array.isArray(sdata)) {
    sdata.forEach(linea => {
      const rows = linea.marcas.map(m => ({ 'Marca': m.marca, 'Ventas': +fmtNum(m.ventas), 'Tickets': m.tickets, '%': m.pct }));
      const ws = XLSX.utils.json_to_sheet(rows);
      XLSX.utils.book_append_sheet(wb, ws, linea.linea.substring(0, 28));
    });
  } else if (sdata?.data) {
    const rows = sdata.data.map(r => {
      const row = { 'Linea': r.linea };
      Object.keys(r).filter(k => k !== 'linea').forEach(k => { row[k] = typeof r[k] === 'number' ? +fmtNum(r[k]) : r[k]; });
      return row;
    });
    const ws = XLSX.utils.json_to_sheet(rows);
    XLSX.utils.book_append_sheet(wb, ws, label.substring(0, 31));
  }
  XLSX.writeFile(wb, `rentabilidad_${subTab}.xlsx`);
  toast.success('Excel exportado');
}

function exportFlujoCaja(data) {
  if (!data?.timeline?.length) { toast.info('Sin datos para exportar'); return; }
  const wb = XLSX.utils.book_new();
  const rows = data.timeline.map(r => ({
    'Periodo': r.periodo,
    'Ingresos Ventas': +fmtNum(r.ingresos_ventas),
    'Cobranzas CxC': +fmtNum(r.cobranzas_cxc),
    'Total Ingresos': +fmtNum(r.total_ingresos),
    'Egresos Gastos': +fmtNum(r.egresos_gastos),
    'Pagos CxP': +fmtNum(r.pagos_cxp),
    'Total Egresos': +fmtNum(r.total_egresos),
    'Flujo Neto': +fmtNum(r.flujo_neto),
    'Saldo Acumulado': +fmtNum(r.saldo_acumulado),
  }));
  const ws = XLSX.utils.json_to_sheet(rows);
  ws['!cols'] = Array(9).fill({ wch: 16 });
  XLSX.utils.book_append_sheet(wb, ws, 'Flujo de Caja');
  XLSX.writeFile(wb, `flujo_caja.xlsx`);
  toast.success('Excel exportado');
}

function exportCxpAging(data) {
  if (!data?.detalle) return;
  const wb = XLSX.utils.book_new();
  // Resumen por proveedor
  if (data.resumen_proveedor?.length) {
    const resProv = data.resumen_proveedor.map(p => ({
      'Proveedor': p.nombre,
      'Vigente': +fmtNum(p.vigente),
      '1-30 dias': +fmtNum(p['1_30']),
      '31-60 dias': +fmtNum(p['31_60']),
      '61-90 dias': +fmtNum(p['61_90']),
      '90+ dias': +fmtNum(p['90_plus']),
      'Total': +fmtNum(p.total),
    }));
    const ws1 = XLSX.utils.json_to_sheet(resProv);
    ws1['!cols'] = [{ wch: 30 }, { wch: 14 }, { wch: 14 }, { wch: 14 }, { wch: 14 }, { wch: 14 }, { wch: 14 }];
    XLSX.utils.book_append_sheet(wb, ws1, 'Resumen Proveedor');
  }
  // Detalle
  const det = data.detalle.map(d => ({
    'Proveedor': d.proveedor,
    'Documento': d.documento,
    'Monto Original': +fmtNum(d.monto_original),
    'Saldo': +fmtNum(d.saldo),
    'Fecha Vencimiento': d.fecha_vencimiento || '',
    'Dias Vencido': d.dias_vencido,
    'Estado': d.bucket === 'vigente' ? 'Vigente' : d.bucket === '1_30' ? '1-30' : d.bucket === '31_60' ? '31-60' : d.bucket === '61_90' ? '61-90' : '90+',
    'Linea Negocio': d.linea_negocio || '',
  }));
  const ws2 = XLSX.utils.json_to_sheet(det);
  ws2['!cols'] = [{ wch: 30 }, { wch: 18 }, { wch: 14 }, { wch: 14 }, { wch: 16 }, { wch: 12 }, { wch: 10 }, { wch: 25 }];
  XLSX.utils.book_append_sheet(wb, ws2, 'Detalle CxP');
  XLSX.writeFile(wb, `cxp_aging_${data.fecha_corte}.xlsx`);
  toast.success('Excel exportado');
}

function exportCxcAging(data) {
  if (!data?.detalle?.length) { toast.info('Sin datos para exportar'); return; }
  const wb = XLSX.utils.book_new();
  const det = data.detalle.map(d => ({
    'Cliente/Documento': d.cliente,
    'Monto Original': +fmtNum(d.monto_original),
    'Saldo': +fmtNum(d.saldo),
    'Fecha Vencimiento': d.fecha_vencimiento || '',
    'Dias Vencido': d.dias_vencido,
    'Estado': d.bucket === 'vigente' ? 'Vigente' : d.bucket === '1_30' ? '1-30' : d.bucket === '31_60' ? '31-60' : d.bucket === '61_90' ? '61-90' : '90+',
    'Linea Negocio': d.linea_negocio || '',
  }));
  const ws = XLSX.utils.json_to_sheet(det);
  ws['!cols'] = [{ wch: 30 }, { wch: 14 }, { wch: 14 }, { wch: 16 }, { wch: 12 }, { wch: 10 }, { wch: 25 }];
  XLSX.utils.book_append_sheet(wb, ws, 'Detalle CxC');
  XLSX.writeFile(wb, `cxc_aging_${data.fecha_corte}.xlsx`);
  toast.success('Excel exportado');
}
const TABS = [
  { id: 'resumen', label: 'Resumen', icon: Layout },
  { id: 'balance', label: 'Balance General', icon: Scale },
  { id: 'egyp', label: 'Estado de Resultados', icon: TrendingUp },
  { id: 'flujo', label: 'Flujo de Caja', icon: Banknote },
  { id: 'inventario', label: 'Inventario Valorizado', icon: Package },
  { id: 'rentabilidad', label: 'Rentabilidad x Linea', icon: BarChart3 },
  { id: 'cxp_aging', label: 'CxP Aging', icon: Clock },
  { id: 'cxc_aging', label: 'CxC Aging', icon: Users },
];

const SUB_TABS_RENT = [
  { id: 'dinero', label: 'Dinero por Linea', icon: DollarSign },
  { id: 'ventas', label: 'Ventas por Linea', icon: TrendingUp },
  { id: 'cobranza', label: 'Cobranza por Linea', icon: CreditCard },
  { id: 'cruce', label: 'Linea x Marca', icon: BarChart3 },
  { id: 'gastos', label: 'Gastos por Linea', icon: Wallet },
];

export default function ReportesFinancieros() {
  const [tab, setTab] = useState('resumen');
  const [rentSubTab, setRentSubTab] = useState('dinero');
  const [agrupacion, setAgrupacion] = useState('diario');
  const [fechaDesde, setFechaDesde] = useState(() => {
    const d = new Date(); d.setMonth(0, 1); return d.toISOString().split('T')[0];
  });
  const [fechaHasta, setFechaHasta] = useState(() => new Date().toISOString().split('T')[0]);
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState({});

  const needsDates = tab === 'egyp' || tab === 'flujo' || tab === 'rentabilidad' || tab === 'resumen';
  const needsCorte = tab === 'balance' || tab === 'cxp_aging' || tab === 'cxc_aging';

  const load = useCallback(async () => {
    setLoading(true);
    try {
      let params = {};
      if (needsDates) params = { fecha_desde: fechaDesde, fecha_hasta: fechaHasta };
      if (needsCorte) params = { fecha_corte: fechaHasta };
      let result;
      switch (tab) {
        case 'resumen': {
          const [vp, im, pc, gc, gcc, ul] = await Promise.all([
            getReporteVentasPendientes(),
            getReporteIngresosPorMarca(params),
            getReportePendienteCobrar(),
            getReporteGastosPorCategoria(params),
            getReporteGastosPorCentro(params),
            getReporteUtilidadPorLinea(params),
          ]);
          result = { data: {
            ventasPend: vp.data, ingresoMarca: im.data, pendienteCobrar: pc.data,
            gastoCategoria: gc.data, gastoCentro: gcc.data, utilidadLinea: ul.data,
          } };
          break;
        }
        case 'balance':
          result = await getReporteBalanceGeneral(params);
          break;
        case 'egyp':
          result = await getReporteEstadoResultados(params);
          break;
        case 'flujo':
          result = await getFlujoCajaGerencial({ fecha_desde: fechaDesde, fecha_hasta: fechaHasta, agrupacion });
          break;
        case 'inventario':
          result = await getReporteInventarioValorizado();
          break;
        case 'rentabilidad': {
          const [ventas, cobranza, cruce, gastos, dinero] = await Promise.all([
            getReporteVentasPorLinea(params),
            getReporteCobranzaPorLinea2(params),
            getReporteCruceLineaMarca(params),
            getReporteGastosDirectosPorLinea(params),
            getReporteDineroPorLinea(params),
          ]);
          result = { data: { ventas: ventas.data, cobranza: cobranza.data, cruce: cruce.data, gastos: gastos.data, dinero: dinero.data } };
          break;
        }
        case 'cxp_aging':
          result = await getReporteCxpAging(params);
          break;
        case 'cxc_aging':
          result = await getReporteCxcAging(params);
          break;
        default: break;
      }
      setData(prev => ({ ...prev, [tab]: result?.data }));
    } catch {
      toast.error('Error cargando reporte');
    } finally {
      setLoading(false);
    }
  }, [tab, fechaDesde, fechaHasta, needsDates, needsCorte, agrupacion]);

  useEffect(() => { load(); }, [load]);

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1400px' }} data-testid="reportes-financieros-page">
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0, color: 'var(--text-heading)' }}>Reportes Financieros</h1>
          <p style={{ fontSize: '0.8rem', color: 'var(--muted)', margin: '0.25rem 0 0' }}>Estados financieros gerenciales consolidados</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          {needsCorte && (
            <>
              <span style={{ color: 'var(--muted)', fontSize: '0.8rem', fontWeight: 500 }}>Corte al:</span>
              <input type="date" className="form-input" value={fechaHasta} onChange={e => setFechaHasta(e.target.value)}
                style={{ fontSize: '0.8rem', padding: '4px 8px' }} data-testid="rf-fecha-corte" />
            </>
          )}
          {needsDates && (
            <>
              <input type="date" className="form-input" value={fechaDesde} onChange={e => setFechaDesde(e.target.value)}
                style={{ fontSize: '0.8rem', padding: '4px 8px' }} data-testid="rf-fecha-desde" />
              <span style={{ color: 'var(--muted)', fontSize: '0.8rem' }}>a</span>
              <input type="date" className="form-input" value={fechaHasta} onChange={e => setFechaHasta(e.target.value)}
                style={{ fontSize: '0.8rem', padding: '4px 8px' }} data-testid="rf-fecha-hasta" />
              {tab === 'flujo' && (
                <select className="form-input" value={agrupacion} onChange={e => setAgrupacion(e.target.value)}
                  style={{ fontSize: '0.8rem', padding: '4px 8px', width: 'auto' }} data-testid="rf-agrupacion">
                  <option value="diario">Diario</option>
                  <option value="semanal">Semanal</option>
                  <option value="mensual">Mensual</option>
                </select>
              )}
            </>
          )}
          <button className="btn btn-primary btn-sm" onClick={load} data-testid="rf-refresh">
            <RefreshCw size={14} /> Actualizar
          </button>
          {(tab === 'rentabilidad' || tab === 'cxp_aging' || tab === 'cxc_aging' || tab === 'flujo') && data[tab] && (
            <button
              className="btn btn-outline btn-sm"
              data-testid="rf-export-excel"
              onClick={() => {
                if (tab === 'rentabilidad') exportRentabilidadDetallado(data.rentabilidad, rentSubTab);
                else if (tab === 'cxp_aging') exportCxpAging(data.cxp_aging);
                else if (tab === 'cxc_aging') exportCxcAging(data.cxc_aging);
                else if (tab === 'flujo') exportFlujoCaja(data.flujo);
              }}
              style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              <Download size={14} /> Excel
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0.25rem', marginBottom: '1rem', borderBottom: '2px solid var(--border)', paddingBottom: '0' }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            data-testid={`rf-tab-${t.id}`}
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
          {tab === 'resumen' && <ResumenEjecutivo data={data.resumen} />}
          {tab === 'balance' && <BalanceGeneral data={data.balance} />}
          {tab === 'egyp' && <EstadoResultados data={data.egyp} />}
          {tab === 'flujo' && <FlujoCajaChart data={data.flujo} agrupacion={agrupacion} />}
          {tab === 'inventario' && <InventarioValorizado data={data.inventario} />}
          {tab === 'rentabilidad' && <RentabilidadDetallada data={data.rentabilidad} subTab={rentSubTab} setSubTab={setRentSubTab} />}
          {tab === 'cxp_aging' && <CxpAging data={data.cxp_aging} />}
          {tab === 'cxc_aging' && <CxcAging data={data.cxc_aging} />}
        </>
      )}
    </div>
  );
}


/* ========== BALANCE GENERAL ========== */
function BalanceGeneral({ data }) {
  const [open, setOpen] = useState({});
  if (!data) return <Empty />;
  const { activos, pasivos, patrimonio } = data;

  const toggle = (key) => setOpen(prev => ({ ...prev, [key]: !prev[key] }));

  return (
    <div data-testid="balance-general-content">
      {/* KPI Summary */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem', marginBottom: '1.25rem' }}>
        <KPI label="Total Activos" value={fmt(activos.total)} color="#22c55e" icon={ArrowUpRight} />
        <KPI label="Total Pasivos" value={fmt(pasivos.total)} color="#ef4444" icon={ArrowDownRight} />
        <KPI label="Patrimonio" value={fmt(patrimonio)} color={patrimonio >= 0 ? '#166534' : '#991b1b'} icon={Scale} bold />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        {/* ACTIVOS */}
        <div>
          <SectionCard title="ACTIVOS" total={activos.total} color="#22c55e">
            <CollapsibleRow label="Caja y Bancos" total={activos.caja_bancos.total} isOpen={open.caja} onToggle={() => toggle('caja')} testId="bg-caja">
              <SimpleTable
                headers={['Cuenta', 'Tipo', 'Saldo']}
                rows={activos.caja_bancos.cuentas.map(c => [
                  c.nombre, c.tipo, { v: fmt(c.saldo_actual), color: '#22c55e', bold: true }
                ])}
                testId="balance-cuentas-table"
              />
            </CollapsibleRow>

            <CollapsibleRow label="Cuentas por Cobrar" total={activos.cuentas_por_cobrar} isOpen={false} simple />

            <CollapsibleRow label="Inventario Materia Prima" total={activos.inventario_mp.total} isOpen={open.invmp} onToggle={() => toggle('invmp')} hasDetail={activos.inventario_mp.detalle.length > 0} testId="bg-invmp">
              <SimpleTable
                headers={['Categoria', 'Cantidad', 'Valor']}
                rows={activos.inventario_mp.detalle.map(r => [
                  r.categoria, Number(r.cantidad || 0).toFixed(2), { v: fmt(r.valor), color: '#22c55e' }
                ])}
                testId="balance-inv-mp-table"
              />
            </CollapsibleRow>

            <CollapsibleRow label="Inventario Producto Terminado" total={activos.inventario_pt} isOpen={false} simple />

            <CollapsibleRow label="Trabajo en Proceso (WIP)" total={activos.wip.total} isOpen={open.wip} onToggle={() => toggle('wip')} hasDetail testId="bg-wip">
              <div style={{ padding: '0.4rem 0.75rem 0.4rem 1.5rem', fontSize: '0.775rem', color: 'var(--muted)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.2rem 0' }}>
                  <span>MP Consumida</span><span style={{ fontWeight: 600 }}>{fmt(activos.wip.mp_consumida)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.2rem 0' }}>
                  <span>Servicios</span><span style={{ fontWeight: 600 }}>{fmt(activos.wip.servicios)}</span>
                </div>
              </div>
            </CollapsibleRow>
          </SectionCard>
        </div>

        {/* PASIVOS + PATRIMONIO */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <SectionCard title="PASIVOS" total={pasivos.total} color="#ef4444">
            <CollapsibleRow label="Cuentas por Pagar" total={pasivos.cuentas_por_pagar} isOpen={false} simple />
            <CollapsibleRow label="Letras por Pagar" total={pasivos.letras_por_pagar} isOpen={false} simple />
          </SectionCard>

          <SectionCard title="PATRIMONIO" total={patrimonio} color={patrimonio >= 0 ? '#166534' : '#991b1b'}>
            <div style={{ padding: '1rem', textAlign: 'center' }}>
              <div style={{ fontSize: '1.5rem', fontWeight: 700, color: patrimonio >= 0 ? '#166534' : '#991b1b' }}>{fmt(patrimonio)}</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--muted)', marginTop: '0.25rem' }}>Activos - Pasivos</div>
            </div>
          </SectionCard>

          {/* Ecuacion Contable */}
          <div style={{ background: 'var(--card-bg-hover)', border: '1px solid var(--border)', borderRadius: '8px', padding: '1rem' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-label)', marginBottom: '0.5rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Ecuacion Contable</div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.75rem', fontSize: '0.875rem' }}>
              <span style={{ fontWeight: 600 }}>{fmt(activos.total)}</span>
              <span style={{ color: 'var(--muted)' }}>=</span>
              <span style={{ fontWeight: 600, color: '#ef4444' }}>{fmt(pasivos.total)}</span>
              <span style={{ color: 'var(--muted)' }}>+</span>
              <span style={{ fontWeight: 600, color: patrimonio >= 0 ? '#166534' : '#991b1b' }}>{fmt(patrimonio)}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}


/* ========== ESTADO DE RESULTADOS ========== */
function EstadoResultados({ data }) {
  if (!data) return <Empty />;

  const lines = [
    { label: 'Ventas', value: data.ventas.total, color: '#22c55e', bold: true, indent: 0 },
    { label: '(-) Costo MP Consumida', value: -data.costo_venta.mp_consumida, color: '#ef4444', indent: 1 },
    { label: '(-) Costo Servicios', value: -data.costo_venta.servicios, color: '#ef4444', indent: 1 },
    { label: 'Costo de Venta Total', value: -data.costo_venta.total, color: '#ef4444', bold: true, indent: 0, separator: true },
    { label: 'MARGEN BRUTO', value: data.margen_bruto, color: data.margen_bruto >= 0 ? '#166534' : '#991b1b', bold: true, indent: 0, highlight: true, negative: data.margen_bruto < 0 },
    { label: '(-) Gastos Operativos', value: -data.gastos_operativos.total, color: '#ef4444', bold: true, indent: 0 },
    { label: 'UTILIDAD OPERATIVA', value: data.utilidad_operativa, color: data.utilidad_operativa >= 0 ? '#166534' : '#991b1b', bold: true, indent: 0, highlight: true, negative: data.utilidad_operativa < 0 },
  ];

  const pctMargen = data.ventas.total > 0 ? ((data.margen_bruto / data.ventas.total) * 100).toFixed(1) : '0.0';
  const pctUtilidad = data.ventas.total > 0 ? ((data.utilidad_operativa / data.ventas.total) * 100).toFixed(1) : '0.0';

  return (
    <div data-testid="estado-resultados-content">
      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.75rem', marginBottom: '1.25rem' }}>
        <KPI label="Ventas" value={fmt(data.ventas.total)} color="#22c55e" icon={ArrowUpRight} />
        <KPI label="Costo de Venta" value={fmt(data.costo_venta.total)} color="#ef4444" icon={ArrowDownRight} />
        <KPI label="Margen Bruto" value={fmt(data.margen_bruto)} subtitle={`${pctMargen}%`} color={data.margen_bruto >= 0 ? '#166534' : '#991b1b'} icon={TrendingUp} bold />
        <KPI label="Utilidad Neta" value={fmt(data.utilidad_neta)} subtitle={`${pctUtilidad}%`} color={data.utilidad_neta >= 0 ? '#166534' : '#991b1b'} icon={Scale} bold />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: '1rem' }}>
        {/* Waterfall */}
        <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden' }}>
          <div style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--table-row-border)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <TrendingUp size={16} color="#64748b" />
            <h3 style={{ fontSize: '0.8125rem', fontWeight: 600, margin: 0, color: 'var(--text-secondary)' }}>Estado de Ganancias y Perdidas</h3>
            <span style={{ marginLeft: 'auto', fontSize: '0.7rem', color: 'var(--muted)' }}>{data.periodo.desde} - {data.periodo.hasta}</span>
          </div>
          <div style={{ padding: '0.25rem 0' }}>
            {lines.map((l, i) => (
              <div key={i} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: `0.4rem ${1 + l.indent * 0.75}rem 0.4rem 1rem`,
                background: l.highlight ? (l.negative ? '#fef2f2' : '#f0fdf4') : 'transparent',
                borderTop: l.separator ? '1px solid #e2e8f0' : 'none',
                borderBottom: l.highlight ? (l.negative ? '1px solid #fecaca' : '1px solid #dcfce7') : 'none',
              }}>
                <span style={{ fontSize: '0.8rem', fontWeight: l.bold ? 700 : 400, color: l.indent ? 'var(--muted)' : 'var(--text-primary)' }}>{l.label}</span>
                <span style={{ fontSize: '0.8rem', fontWeight: l.bold ? 700 : 500, color: l.color }}>{l.negative ? '-' : ''}{fmt(Math.abs(l.value))}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Sidebar: Desglose */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* Ventas por Linea */}
          {data.ventas.por_linea?.length > 0 && (
            <Card title="Ventas por Linea" icon={TrendingUp} testId="egyp-ventas-linea">
              <SimpleTable
                headers={['Linea', 'Monto']}
                rows={data.ventas.por_linea.map(r => [r.linea || 'Sin clasificar', { v: fmt(r.total), color: '#22c55e', bold: true }])}
                testId="egyp-ventas-linea-table"
              />
            </Card>
          )}

          {/* Gastos por Categoria */}
          {data.gastos_operativos.por_categoria?.length > 0 && (
            <Card title="Gastos por Categoria" icon={ArrowDownRight} testId="egyp-gastos-cat">
              <SimpleTable
                headers={['Categoria', 'Monto']}
                rows={data.gastos_operativos.por_categoria.map(r => [r.categoria, { v: fmt(r.monto), color: '#ef4444', bold: true }])}
                testId="egyp-gastos-cat-table"
              />
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}


/* ========== FLUJO DE CAJA ========== */
/* ========== FLUJO CAJA CON GRAFICOS ========== */
const fmtDate = (d) => {
  if (!d) return '';
  const dt = new Date(d + 'T00:00:00');
  return dt.toLocaleDateString('es-PE', { day: '2-digit', month: 'short' });
};
const fmtShort = (v) => `S/ ${(v / 1000).toFixed(1)}k`;
const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: 8, padding: '0.5rem 0.75rem', boxShadow: '0 4px 12px rgba(0,0,0,0.08)', fontSize: '0.75rem' }}>
      <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>{fmtDate(label)}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', color: p.color }}>
          <span>{p.name}</span><span style={{ fontWeight: 600 }}>{fmt(p.value)}</span>
        </div>
      ))}
    </div>
  );
};

function FlujoCajaChart({ data, agrupacion }) {
  if (!data) return <Empty />;
  const timeline = data.timeline || [];
  const totales = data.totales || {};

  return (
    <div data-testid="flujo-caja-content">
      {/* KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem', marginBottom: '1.25rem' }}>
        <KPI label="Total Ingresos" value={fmt(totales.ingresos)} color="#22c55e" icon={ArrowUpRight} />
        <KPI label="Total Egresos" value={fmt(totales.egresos)} color="#ef4444" icon={ArrowDownRight} />
        <KPI label="Flujo Neto" value={fmt(totales.flujo_neto)} color={totales.flujo_neto >= 0 ? '#166534' : '#991b1b'} icon={Banknote} bold />
      </div>

      {/* Chart */}
      {timeline.length > 0 && (
        <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: '8px', marginBottom: '1rem', overflow: 'hidden' }}>
          <div style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--table-row-border)' }}>
            <h3 style={{ fontSize: '0.8125rem', fontWeight: 600, margin: 0, color: 'var(--text-secondary)' }}>Flujo de Caja - {agrupacion?.charAt(0).toUpperCase() + agrupacion?.slice(1)}</h3>
          </div>
          <div style={{ padding: '0.5rem', height: 300 }}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={timeline} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="periodo" tick={{ fontSize: 10 }} tickFormatter={fmtDate} />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={fmtShort} />
                <Tooltip content={<ChartTooltip />} />
                <Legend wrapperStyle={{ fontSize: '0.7rem' }} />
                <Bar dataKey="total_ingresos" name="Ingresos" fill="#22C55E" radius={[4, 4, 0, 0]} />
                <Bar dataKey="total_egresos" name="Egresos" fill="#EF4444" radius={[4, 4, 0, 0]} />
                <Line type="monotone" dataKey="saldo_acumulado" name="Saldo Acum." stroke="#3B82F6" strokeWidth={2} dot={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Detail Table */}
      {timeline.length > 0 ? (
        <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden' }}>
          <div style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--table-row-border)' }}>
            <h3 style={{ fontSize: '0.8125rem', fontWeight: 600, margin: 0, color: 'var(--text-secondary)' }}>Detalle por Periodo</h3>
          </div>
          <div style={{ maxHeight: '350px', overflow: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.775rem' }} data-testid="flujo-chart-table">
              <thead style={{ position: 'sticky', top: 0, background: 'var(--card-bg-hover)' }}>
                <tr>
                  {['Periodo', 'Ventas', 'Cobranzas', 'Total Ing.', 'Gastos', 'Pagos CxP', 'Total Egr.', 'Flujo Neto', 'Saldo Acum.'].map((h, i) => (
                    <th key={i} style={{ padding: '6px 10px', textAlign: i === 0 ? 'left' : 'right', color: 'var(--muted)', fontWeight: 600, borderBottom: '2px solid var(--border)', fontSize: '0.72rem' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {timeline.map((r, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--table-row-border)' }}>
                    <td style={{ padding: '6px 10px', fontWeight: 500 }}>{fmtDate(r.periodo)}</td>
                    <td style={{ padding: '6px 10px', textAlign: 'right' }}>{fmt(r.ingresos_ventas)}</td>
                    <td style={{ padding: '6px 10px', textAlign: 'right' }}>{fmt(r.cobranzas_cxc)}</td>
                    <td style={{ padding: '6px 10px', textAlign: 'right', fontWeight: 600, color: '#22c55e' }}>{fmt(r.total_ingresos)}</td>
                    <td style={{ padding: '6px 10px', textAlign: 'right' }}>{fmt(r.egresos_gastos)}</td>
                    <td style={{ padding: '6px 10px', textAlign: 'right' }}>{fmt(r.pagos_cxp)}</td>
                    <td style={{ padding: '6px 10px', textAlign: 'right', fontWeight: 600, color: '#ef4444' }}>{fmt(r.total_egresos)}</td>
                    <td style={{ padding: '6px 10px', textAlign: 'right', fontWeight: 600, color: r.flujo_neto >= 0 ? '#22c55e' : '#ef4444' }}>{fmt(r.flujo_neto)}</td>
                    <td style={{ padding: '6px 10px', textAlign: 'right', fontWeight: 700, color: r.saldo_acumulado >= 0 ? '#166534' : '#ef4444' }}>{fmt(r.saldo_acumulado)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--muted)' }}>
          <Banknote size={36} style={{ margin: '0 auto 0.5rem', opacity: 0.3 }} />
          <p style={{ fontSize: '0.875rem' }}>Sin movimientos en el periodo</p>
        </div>
      )}
    </div>
  );
}


/* ========== INVENTARIO VALORIZADO ========== */
function InventarioValorizado({ data }) {
  if (!data) return <Empty />;

  return (
    <div data-testid="inventario-valorizado-content">
      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.75rem', marginBottom: '1.25rem' }}>
        <KPI label="Materia Prima" value={fmt(data.materia_prima.total)} color="#3b82f6" icon={Package} />
        <KPI label="Producto Terminado" value={fmt(data.producto_terminado.total)} color="#8b5cf6" icon={Package} />
        <KPI label="Trabajo en Proceso" value={fmt(data.wip.total)} color="#f59e0b" icon={Package} />
        <KPI label="Gran Total" value={fmt(data.gran_total)} color="#0f172a" icon={Scale} bold />
      </div>

      {/* MP Table */}
      {data.materia_prima.items.length > 0 && (
        <div style={{ marginBottom: '1rem' }}>
          <Card title={`Materia Prima (${data.materia_prima.items.length} items)`} icon={Package} testId="inv-mp-card">
            <SimpleTable
              headers={['Articulo', 'Codigo', 'Categoria', 'UM', 'Stock', 'Costo Prom.', 'Valor Total']}
              rows={data.materia_prima.items.map(r => [
                r.nombre, r.codigo || '-', r.categoria, r.unidad_medida || '-',
                Number(r.stock || 0).toFixed(2),
                { v: fmt(r.costo_promedio), color: 'var(--muted)' },
                { v: fmt(r.valor_total), color: '#3b82f6', bold: true }
              ])}
              testId="inv-mp-table"
            />
            <TotalRow label="Total Materia Prima" value={data.materia_prima.total} color="#3b82f6" />
          </Card>
        </div>
      )}

      {/* PT Table */}
      {data.producto_terminado.items.length > 0 && (
        <div style={{ marginBottom: '1rem' }}>
          <Card title={`Producto Terminado (${data.producto_terminado.items.length} items)`} icon={Package} testId="inv-pt-card">
            <SimpleTable
              headers={['Articulo', 'Codigo', 'UM', 'Stock', 'Costo Prom.', 'Valor Total']}
              rows={data.producto_terminado.items.map(r => [
                r.nombre, r.codigo || '-', r.unidad_medida || '-',
                Number(r.stock || 0).toFixed(2),
                { v: fmt(r.costo_promedio), color: 'var(--muted)' },
                { v: fmt(r.valor_total), color: '#8b5cf6', bold: true }
              ])}
              testId="inv-pt-table"
            />
            <TotalRow label="Total Producto Terminado" value={data.producto_terminado.total} color="#8b5cf6" />
          </Card>
        </div>
      )}

      {/* WIP */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        {data.wip.mp_consumida.length > 0 && (
          <Card title="WIP - MP Consumida" icon={Package} testId="inv-wip-mp-card">
            <SimpleTable
              headers={['Articulo', 'Tipo', 'Consumido', 'Valor']}
              rows={data.wip.mp_consumida.map(r => [
                r.inventario_nombre, r.tipo_componente || '-',
                Number(r.consumido || 0).toFixed(2),
                { v: fmt(r.valor), color: '#f59e0b', bold: true }
              ])}
              testId="inv-wip-mp-table"
            />
            <TotalRow label="Total MP Consumida" value={data.wip.total_mp} color="#f59e0b" />
          </Card>
        )}

        {data.wip.servicios.length > 0 && (
          <Card title="WIP - Servicios" icon={Package} testId="inv-wip-srv-card">
            <SimpleTable
              headers={['Descripcion', 'Monto']}
              rows={data.wip.servicios.map(r => [
                r.descripcion || 'Sin descripcion', { v: fmt(r.monto), color: '#f59e0b', bold: true }
              ])}
              testId="inv-wip-srv-table"
            />
            <TotalRow label="Total Servicios" value={data.wip.total_srv} color="#f59e0b" />
          </Card>
        )}
      </div>
    </div>
  );
}


const pctFmt = (v) => `${Number(v || 0).toFixed(1)}%`;

/* ========== RENTABILIDAD DETALLADA (5 SUB-TABS) ========== */
function RentabilidadDetallada({ data, subTab, setSubTab }) {
  if (!data) return <Empty />;

  return (
    <div data-testid="rentabilidad-linea-content">
      {/* Sub-tabs */}
      <div style={{ display: 'flex', gap: '0.25rem', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0' }}>
        {SUB_TABS_RENT.map(t => (
          <button
            key={t.id}
            onClick={() => setSubTab(t.id)}
            data-testid={`rent-sub-${t.id}`}
            style={{
              padding: '0.4rem 0.75rem', fontSize: '0.75rem', fontWeight: subTab === t.id ? 700 : 500,
              color: subTab === t.id ? 'var(--text-heading)' : 'var(--muted)', background: 'none', border: 'none',
              borderBottom: subTab === t.id ? '2px solid #0f172a' : '2px solid transparent',
              marginBottom: '-1px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.3rem',
            }}
          >
            <t.icon size={13} />{t.label}
          </button>
        ))}
      </div>

      {subTab === 'dinero' && <RentDinero data={data.dinero} />}
      {subTab === 'ventas' && <RentVentas data={data.ventas} />}
      {subTab === 'cobranza' && <RentCobranza data={data.cobranza} />}
      {subTab === 'cruce' && <RentCruce data={data.cruce} />}
      {subTab === 'gastos' && <RentGastos data={data.gastos} />}
    </div>
  );
}

function RentDinero({ data }) {
  if (!data?.data) return <RentEmpty />;
  const { data: rows, totales } = data;
  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '0.5rem', marginBottom: '1rem' }}>
        <KPI label="Ventas Confirmadas" value={fmt(totales.ventas)} color="#22c55e" icon={ArrowUpRight} />
        <KPI label="Cobranzas Reales" value={fmt(totales.cobranzas)} color="#059669" icon={CreditCard} />
        <KPI label="CxC Pendiente" value={fmt(totales.cxc_pendiente)} color="#f59e0b" icon={Clock} />
        <KPI label="Gastos Directos" value={fmt(totales.gastos)} color="#ef4444" icon={ArrowDownRight} />
        <KPI label="Saldo Neto" value={fmt(totales.saldo_neto)} color={totales.saldo_neto >= 0 ? '#166534' : '#991b1b'} icon={DollarSign} bold />
      </div>
      <RentTable testId="dinero-table" headers={['Linea de Negocio', 'Ventas', 'Cobranzas', 'CxC Pend.', 'Gastos', 'Saldo Neto']}
        rows={rows.map(r => [r.linea, {v: fmt(r.ventas), c:'#22c55e'}, {v: fmt(r.cobranzas), c:'#059669'}, {v: fmt(r.cxc_pendiente), c:'#f59e0b'}, {v: fmt(r.gastos), c:'#ef4444'}, {v: fmt(r.saldo_neto), c: r.saldo_neto>=0?'#166534':'#991b1b', b:true}])}
        footer={['TOTAL', {v: fmt(totales.ventas), c:'#22c55e', b:true}, {v: fmt(totales.cobranzas), c:'#059669', b:true}, {v: fmt(totales.cxc_pendiente), c:'#f59e0b', b:true}, {v: fmt(totales.gastos), c:'#ef4444', b:true}, {v: fmt(totales.saldo_neto), c: totales.saldo_neto>=0?'#166534':'#991b1b', b:true}]} />
    </div>
  );
}

function RentVentas({ data }) {
  if (!data?.data) return <RentEmpty />;
  const { data: rows, totales } = data;
  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem', marginBottom: '1rem' }}>
        <KPI label="Total Ventas" value={fmt(totales.ventas)} color="#22c55e" icon={ArrowUpRight} />
        <KPI label="Total Tickets" value={String(totales.tickets)} color="#3b82f6" icon={BarChart3} />
        <KPI label="Ticket Promedio" value={fmt(totales.ticket_promedio)} color="#8b5cf6" icon={TrendingUp} />
      </div>
      <RentTable testId="ventas-linea-table" headers={['Linea de Negocio', 'Ventas Confirmadas', 'Tickets', 'Ticket Promedio']}
        rows={rows.map(r => [r.linea, {v: fmt(r.ventas), c:'#22c55e', b:true}, String(r.tickets), {v: fmt(r.ticket_promedio), c:'#8b5cf6'}])}
        footer={['TOTAL', {v: fmt(totales.ventas), c:'#22c55e', b:true}, {v: String(totales.tickets), b:true}, {v: fmt(totales.ticket_promedio), c:'#8b5cf6', b:true}]} />
    </div>
  );
}

function RentCobranza({ data }) {
  if (!data?.data) return <RentEmpty />;
  const { data: rows, totales } = data;
  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.5rem', marginBottom: '1rem' }}>
        <KPI label="Total Vendido" value={fmt(totales.vendido)} color="#22c55e" icon={ArrowUpRight} />
        <KPI label="Total Cobrado" value={fmt(totales.cobrado)} color="#059669" icon={CreditCard} />
        <KPI label="Pendiente Cobrar" value={fmt(totales.pendiente)} color="#ef4444" icon={Clock} />
        <KPI label="% Cobrado" value={pctFmt(totales.pct_cobrado)} color="#3b82f6" icon={TrendingUp} />
      </div>
      <RentTable testId="cobranza-linea-table" headers={['Linea de Negocio', 'Vendido', 'Cobrado', 'Pendiente', '% Cobrado']}
        rows={rows.map(r => [r.linea, {v: fmt(r.vendido), c:'#22c55e'}, {v: fmt(r.cobrado), c:'#059669', b:true}, {v: fmt(r.pendiente), c:'#ef4444'}, {v: pctFmt(r.pct_cobrado), c: r.pct_cobrado>=80?'#059669':r.pct_cobrado>=50?'#f59e0b':'#ef4444', b:true}])}
        footer={['TOTAL', {v: fmt(totales.vendido), c:'#22c55e', b:true}, {v: fmt(totales.cobrado), c:'#059669', b:true}, {v: fmt(totales.pendiente), c:'#ef4444', b:true}, {v: pctFmt(totales.pct_cobrado), c:'#3b82f6', b:true}]} />
    </div>
  );
}

function RentCruce({ data }) {
  if (!data || data.length === 0) return <RentEmpty />;
  return (
    <div>
      {data.map((linea) => (
        <div key={linea.linea} style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: '8px', marginBottom: '0.75rem', overflow: 'hidden' }}>
          <div style={{ padding: '0.5rem 1rem', borderBottom: '1px solid var(--table-row-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--card-bg-hover)' }}>
            <span style={{ fontWeight: 700, fontSize: '0.8125rem', color: 'var(--text-heading)' }}>{linea.linea}</span>
            <span style={{ fontWeight: 600, fontSize: '0.8125rem', color: '#059669' }}>{fmt(linea.total_ventas)}</span>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.775rem' }}>
            <thead><tr>
              {['Marca', 'Ventas', 'Tickets', '%'].map((h, i) => (
                <th key={i} style={{ padding: '4px 12px', textAlign: i === 0 ? 'left' : 'right', color: 'var(--muted)', fontWeight: 500, fontSize: '0.72rem' }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {linea.marcas.map((m) => (
                <tr key={m.marca} style={{ borderTop: '1px solid var(--table-row-border)' }}>
                  <td style={{ padding: '5px 12px', fontWeight: 500 }}>{m.marca}</td>
                  <td style={{ padding: '5px 12px', textAlign: 'right', color: '#22c55e', fontWeight: 600 }}>{fmt(m.ventas)}</td>
                  <td style={{ padding: '5px 12px', textAlign: 'right', color: 'var(--muted)' }}>{m.tickets}</td>
                  <td style={{ padding: '5px 12px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '0.5rem' }}>
                      <div style={{ width: '50px', height: '5px', background: 'var(--border)', borderRadius: '3px', overflow: 'hidden' }}>
                        <div style={{ width: `${m.pct}%`, height: '100%', background: '#22c55e', borderRadius: '3px' }} />
                      </div>
                      <span style={{ fontSize: '0.7rem', color: 'var(--muted)', minWidth: '32px', textAlign: 'right' }}>{pctFmt(m.pct)}</span>
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

function RentGastos({ data }) {
  if (!data?.data) return <RentEmpty />;
  const { data: rows, totales } = data;
  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem', marginBottom: '1rem' }}>
        <KPI label="Total Gastos" value={fmt(totales.total_gastos)} color="#ef4444" icon={ArrowDownRight} />
        <KPI label="Total Facturas Prov." value={fmt(totales.total_facturas)} color="#f97316" icon={Wallet} />
        <KPI label="Total Egresos" value={fmt(totales.total_egresos)} color="#991b1b" icon={Banknote} bold />
      </div>
      <RentTable testId="gastos-linea-table" headers={['Linea de Negocio', 'Gastos', 'Facturas Prov.', 'Total Egresos']}
        rows={rows.map(r => [r.linea, {v: fmt(r.total_gastos), c:'#ef4444'}, {v: fmt(r.total_facturas), c:'#f97316'}, {v: fmt(r.total_egresos), c:'#991b1b', b:true}])}
        footer={['TOTAL', {v: fmt(totales.total_gastos), c:'#ef4444', b:true}, {v: fmt(totales.total_facturas), c:'#f97316', b:true}, {v: fmt(totales.total_egresos), c:'#991b1b', b:true}]} />
    </div>
  );
}

function RentTable({ headers, rows, footer, testId }) {
  return (
    <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }} data-testid={testId}>
        <thead><tr style={{ background: 'var(--card-bg-hover)' }}>
          {headers.map((h, i) => (
            <th key={i} style={{ padding: '0.4rem 0.75rem', textAlign: i === 0 ? 'left' : 'right', color: 'var(--text-label)', fontWeight: 600, borderBottom: '2px solid var(--border)', fontSize: '0.72rem' }}>{h}</th>
          ))}
        </tr></thead>
        <tbody>{rows.map((row, i) => (
          <tr key={i} style={{ borderBottom: '1px solid var(--table-row-border)' }}>
            {row.map((cell, j) => {
              const isObj = typeof cell === 'object' && cell !== null;
              return (<td key={j} style={{ padding: '0.4rem 0.75rem', textAlign: j === 0 ? 'left' : 'right', fontWeight: (j === 0 || (isObj && cell.b)) ? 600 : 400, color: isObj ? cell.c : 'var(--text-primary)' }}>{isObj ? cell.v : cell}</td>);
            })}
          </tr>
        ))}</tbody>
        {footer && (
          <tfoot><tr style={{ background: 'var(--card-bg-hover)', borderTop: '2px solid var(--border)' }}>
            {footer.map((cell, j) => {
              const isObj = typeof cell === 'object' && cell !== null;
              return (<td key={j} style={{ padding: '0.4rem 0.75rem', textAlign: j === 0 ? 'left' : 'right', fontWeight: 700, color: isObj ? cell.c : 'var(--text-heading)' }}>{isObj ? cell.v : cell}</td>);
            })}
          </tr></tfoot>
        )}
      </table>
    </div>
  );
}

function RentEmpty() {
  return <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--muted)', fontSize: '0.8rem' }}>Sin datos para el periodo seleccionado</div>;
}


/* ========== CXP AGING ========== */
function CxpAging({ data }) {
  if (!data) return <Empty />;
  const { buckets, total, detalle, resumen_proveedor } = data;
  const bucketLabels = { vigente: 'Vigente', '1_30': '1-30 dias', '31_60': '31-60 dias', '61_90': '61-90 dias', '90_plus': '90+ dias' };
  const bucketColors = { vigente: '#22c55e', '1_30': '#3b82f6', '31_60': '#f59e0b', '61_90': '#f97316', '90_plus': '#ef4444' };

  return (
    <div data-testid="cxp-aging-content">
      {/* Aging KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '0.5rem', marginBottom: '1.25rem' }}>
        <KPI label="Total CxP" value={fmt(total)} color="#0f172a" icon={Scale} bold />
        {Object.entries(bucketLabels).map(([key, label]) => (
          <KPI key={key} label={label} value={fmt(buckets[key])} color={bucketColors[key]} icon={Clock} />
        ))}
      </div>

      {/* Aging bar */}
      {total > 0 && (
        <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: '8px', padding: '1rem', marginBottom: '1rem' }}>
          <h3 style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>Distribucion de Antiguedad</h3>
          <div style={{ display: 'flex', height: '32px', borderRadius: '6px', overflow: 'hidden' }}>
            {Object.entries(buckets).map(([key, val]) => val > 0 && (
              <div key={key} style={{ width: `${(val / total) * 100}%`, background: bucketColors[key], minWidth: '2px', position: 'relative' }}
                title={`${bucketLabels[key]}: ${fmt(val)} (${((val / total) * 100).toFixed(1)}%)`}>
                {val / total > 0.08 && (
                  <span style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.65rem', fontWeight: 700, color: 'var(--card-bg)' }}>
                    {((val / total) * 100).toFixed(0)}%
                  </span>
                )}
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem', fontSize: '0.65rem', color: 'var(--muted)', flexWrap: 'wrap' }}>
            {Object.entries(bucketLabels).map(([key, label]) => (
              <span key={key}><span style={{ display: 'inline-block', width: 10, height: 10, background: bucketColors[key], borderRadius: 2, marginRight: 4 }}></span>{label}</span>
            ))}
          </div>
        </div>
      )}

      {/* Resumen por proveedor */}
      {resumen_proveedor?.length > 0 && (
        <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden', marginBottom: '1rem' }}>
          <div style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--table-row-border)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Users size={16} color="#64748b" />
            <h3 style={{ fontSize: '0.8125rem', fontWeight: 600, margin: 0, color: 'var(--text-secondary)' }}>Por Proveedor</h3>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.775rem' }} data-testid="cxp-proveedor-table">
            <thead>
              <tr style={{ background: 'var(--card-bg-hover)' }}>
                {['Proveedor', 'Vigente', '1-30', '31-60', '61-90', '90+', 'Total'].map((h, i) => (
                  <th key={i} style={{ padding: '6px 10px', textAlign: i === 0 ? 'left' : 'right', color: 'var(--muted)', fontWeight: 600, borderBottom: '2px solid var(--border)', fontSize: '0.72rem' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {resumen_proveedor.map((p, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--table-row-border)' }}>
                  <td style={{ padding: '6px 10px', fontWeight: 600, color: 'var(--text-primary)' }}>{p.nombre}</td>
                  {['vigente', '1_30', '31_60', '61_90', '90_plus'].map(b => (
                    <td key={b} style={{ padding: '6px 10px', textAlign: 'right', color: p[b] > 0 ? bucketColors[b] : '#cbd5e1', fontWeight: p[b] > 0 ? 600 : 400 }}>
                      {p[b] > 0 ? fmt(p[b]) : '-'}
                    </td>
                  ))}
                  <td style={{ padding: '6px 10px', textAlign: 'right', fontWeight: 700, color: 'var(--text-heading)' }}>{fmt(p.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Detalle */}
      {detalle.length > 0 && (
        <AgingDetailTable data={detalle} entityField="proveedor" bucketLabels={bucketLabels} bucketColors={bucketColors} testId="cxp-detalle-table" />
      )}

      {detalle.length === 0 && (
        <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--muted)' }}>
          <Clock size={36} style={{ margin: '0 auto 0.5rem', opacity: 0.3 }} />
          <p style={{ fontSize: '0.875rem' }}>No hay cuentas por pagar pendientes</p>
        </div>
      )}
    </div>
  );
}


/* ========== CXC AGING ========== */
function CxcAging({ data }) {
  if (!data) return <Empty />;
  const { buckets, total, detalle } = data;
  const bucketLabels = { vigente: 'Vigente', '1_30': '1-30 dias', '31_60': '31-60 dias', '61_90': '61-90 dias', '90_plus': '90+ dias' };
  const bucketColors = { vigente: '#22c55e', '1_30': '#3b82f6', '31_60': '#f59e0b', '61_90': '#f97316', '90_plus': '#ef4444' };

  return (
    <div data-testid="cxc-aging-content">
      {/* Aging KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: '0.5rem', marginBottom: '1.25rem' }}>
        <KPI label="Total CxC" value={fmt(total)} color="#0f172a" icon={Scale} bold />
        {Object.entries(bucketLabels).map(([key, label]) => (
          <KPI key={key} label={label} value={fmt(buckets[key])} color={bucketColors[key]} icon={Clock} />
        ))}
      </div>

      {/* Aging bar */}
      {total > 0 && (
        <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: '8px', padding: '1rem', marginBottom: '1rem' }}>
          <h3 style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>Distribucion de Antiguedad</h3>
          <div style={{ display: 'flex', height: '32px', borderRadius: '6px', overflow: 'hidden' }}>
            {Object.entries(buckets).map(([key, val]) => val > 0 && (
              <div key={key} style={{ width: `${(val / total) * 100}%`, background: bucketColors[key], minWidth: '2px', position: 'relative' }}
                title={`${bucketLabels[key]}: ${fmt(val)} (${((val / total) * 100).toFixed(1)}%)`}>
                {val / total > 0.08 && (
                  <span style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.65rem', fontWeight: 700, color: 'var(--card-bg)' }}>
                    {((val / total) * 100).toFixed(0)}%
                  </span>
                )}
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem', fontSize: '0.65rem', color: 'var(--muted)', flexWrap: 'wrap' }}>
            {Object.entries(bucketLabels).map(([key, label]) => (
              <span key={key}><span style={{ display: 'inline-block', width: 10, height: 10, background: bucketColors[key], borderRadius: 2, marginRight: 4 }}></span>{label}</span>
            ))}
          </div>
        </div>
      )}

      {/* Detalle */}
      {detalle.length > 0 && (
        <AgingDetailTable data={detalle} entityField="cliente" bucketLabels={bucketLabels} bucketColors={bucketColors} testId="cxc-detalle-table" />
      )}

      {detalle.length === 0 && (
        <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--muted)' }}>
          <Clock size={36} style={{ margin: '0 auto 0.5rem', opacity: 0.3 }} />
          <p style={{ fontSize: '0.875rem' }}>No hay cuentas por cobrar pendientes</p>
        </div>
      )}
    </div>
  );
}


/* ========== AGING DETAIL TABLE (shared) ========== */
function AgingDetailTable({ data, entityField, bucketLabels, bucketColors, testId }) {
  return (
    <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden' }}>
      <div style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--table-row-border)' }}>
        <h3 style={{ fontSize: '0.8125rem', fontWeight: 600, margin: 0, color: 'var(--text-secondary)' }}>Detalle</h3>
      </div>
      <div style={{ maxHeight: '400px', overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.775rem' }} data-testid={testId}>
          <thead style={{ position: 'sticky', top: 0, background: 'var(--card-bg-hover)' }}>
            <tr>
              {[entityField === 'proveedor' ? 'Proveedor' : 'Cliente/Documento', 'Documento', 'Monto Orig.', 'Saldo', 'Vencimiento', 'Dias', 'Estado'].map((h, i) => (
                <th key={i} style={{ padding: '6px 10px', textAlign: i <= 1 ? 'left' : 'right', color: 'var(--muted)', fontWeight: 600, borderBottom: '2px solid var(--border)', fontSize: '0.72rem' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((d, i) => (
              <tr key={i} style={{ borderBottom: '1px solid var(--table-row-border)' }}>
                <td style={{ padding: '6px 10px', fontWeight: 600, color: 'var(--text-primary)' }}>{d[entityField]}</td>
                <td style={{ padding: '6px 10px', color: 'var(--muted)' }}>{d.documento || d.cliente}</td>
                <td style={{ padding: '6px 10px', textAlign: 'right', color: 'var(--muted)' }}>{fmt(d.monto_original)}</td>
                <td style={{ padding: '6px 10px', textAlign: 'right', fontWeight: 600, color: bucketColors[d.bucket] }}>{fmt(d.saldo)}</td>
                <td style={{ padding: '6px 10px', textAlign: 'right', color: 'var(--muted)' }}>{d.fecha_vencimiento ? new Date(d.fecha_vencimiento).toLocaleDateString('es-PE') : '-'}</td>
                <td style={{ padding: '6px 10px', textAlign: 'right' }}>
                  <span style={{
                    padding: '1px 6px', borderRadius: '4px', fontSize: '0.7rem', fontWeight: 600,
                    background: d.dias_vencido > 60 ? '#fef2f2' : d.dias_vencido > 30 ? '#fffbeb' : d.dias_vencido > 0 ? '#eff6ff' : 'var(--success-bg)',
                    color: d.dias_vencido > 60 ? '#dc2626' : d.dias_vencido > 30 ? '#d97706' : d.dias_vencido > 0 ? '#2563eb' : '#16a34a'
                  }}>
                    {d.dias_vencido > 0 ? `${d.dias_vencido}d` : 'Vigente'}
                  </span>
                </td>
                <td style={{ padding: '6px 10px', textAlign: 'right' }}>
                  <span style={{ padding: '1px 6px', borderRadius: '4px', fontSize: '0.65rem', fontWeight: 600, background: bucketColors[d.bucket] + '18', color: bucketColors[d.bucket] }}>
                    {bucketLabels[d.bucket]}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}


/* ========== SHARED COMPONENTS ========== */

function CollapsibleRow({ label, total, isOpen, onToggle, children, simple, hasDetail = true, testId }) {
  const canExpand = !simple && hasDetail && children;
  return (
    <div data-testid={testId}>
      <div
        onClick={canExpand ? onToggle : undefined}
        style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '0.5rem 0.75rem',
          borderBottom: '1px solid var(--table-row-border)',
          cursor: canExpand ? 'pointer' : 'default',
          background: isOpen ? 'var(--card-bg-hover)' : 'transparent',
          transition: 'background 0.15s',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
          {canExpand && (
            isOpen ? <ChevronDown size={14} color="#94a3b8" /> : <ChevronRight size={14} color="#94a3b8" />
          )}
          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-label)' }}>{label}</span>
        </div>
        <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>{fmt(total)}</span>
      </div>
      {canExpand && isOpen && (
        <div style={{ borderBottom: '1px solid var(--table-row-border)', background: '#fafbfc' }}>
          {children}
        </div>
      )}
    </div>
  );
}

function KPI({ label, value, subtitle, color, icon: Icon, bold }) {
  return (
    <div style={{
      background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: '8px',
      padding: '0.75rem 1rem', display: 'flex', alignItems: 'center', gap: '0.75rem'
    }}>
      {Icon && (
        <div style={{ width: 36, height: 36, borderRadius: '8px', background: `${color}12`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <Icon size={18} color={color} />
        </div>
      )}
      <div>
        <div style={{ fontSize: '0.7rem', color: 'var(--muted)', fontWeight: 500 }}>{label}</div>
        <div style={{ fontSize: bold ? '1.125rem' : '1rem', fontWeight: 700, color }}>{value}</div>
        {subtitle && <div style={{ fontSize: '0.7rem', color: 'var(--muted)' }}>{subtitle}</div>}
      </div>
    </div>
  );
}

function SectionCard({ title, total, color, children }) {
  return (
    <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: '8px', overflow: 'hidden' }}>
      <div style={{ padding: '0.75rem 1rem', borderBottom: '1px solid var(--table-row-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ fontSize: '0.8125rem', fontWeight: 700, margin: 0, color: 'var(--text-secondary)', letterSpacing: '0.05em' }}>{title}</h3>
        <span style={{ fontSize: '0.9375rem', fontWeight: 700, color }}>{fmt(total)}</span>
      </div>
      <div>{children}</div>
    </div>
  );
}

function GroupHeader({ label, total }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.4rem 0.75rem', borderBottom: '1px solid #f8fafc', background: '#fafbfc' }}>
      <span style={{ fontSize: '0.775rem', fontWeight: 600, color: 'var(--text-label)' }}>{label}</span>
      <span style={{ fontSize: '0.775rem', fontWeight: 600, color: 'var(--text-primary)' }}>{fmt(total)}</span>
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

function SimpleTable({ headers, rows, testId }) {
  if (!rows || !rows.length) return <p style={{ textAlign: 'center', color: 'var(--muted)', fontSize: '0.8rem', padding: '1rem' }}>Sin datos</p>;
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }} data-testid={testId}>
      <thead>
        <tr>
          {headers.map((h, i) => (
            <th key={i} style={{ padding: '4px 8px', textAlign: i === 0 ? 'left' : 'right', color: 'var(--muted)', fontWeight: 500, borderBottom: '1px solid var(--border)', fontSize: '0.72rem' }}>{h}</th>
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
                  padding: '4px 8px',
                  textAlign: j === 0 ? 'left' : 'right',
                  fontWeight: (j === 0 || (isObj && cell.bold)) ? 600 : 400,
                  color: isObj ? cell.color : 'var(--text-primary)',
                  fontSize: '0.775rem',
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

function TotalRow({ label, value, color }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.5rem 0.75rem', borderTop: '2px solid var(--border)', background: '#fafbfc' }}>
      <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-secondary)' }}>{label}</span>
      <span style={{ fontSize: '0.8rem', fontWeight: 700, color }}>{fmt(value)}</span>
    </div>
  );
}

function Empty() {
  return (
    <div style={{ textAlign: 'center', padding: '3rem 1rem', color: 'var(--muted)' }}>
      <Minus size={40} style={{ margin: '0 auto 0.5rem', opacity: 0.3 }} />
      <p style={{ fontSize: '0.875rem' }}>Sin datos disponibles</p>
    </div>
  );
}

/* ========== RESUMEN EJECUTIVO (reemplaza ReportesSimplificados) ========== */
function ResumenEjecutivo({ data }) {
  if (!data) return <Empty />;
  return (
    <div data-testid="resumen-ejecutivo-content">
      {/* Row 1: Ventas Pendientes + Utilidad por Linea */}
      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: '1rem', marginBottom: '1rem' }}>
        <ResumenCard title="Ventas Pendientes" icon={BarChart3} testId="rep-ventas-pend">
          <div style={{ textAlign: 'center', padding: '0.75rem 0' }}>
            <div style={{ fontSize: '2rem', fontWeight: 700, color: '#f59e0b' }}>{data.ventasPend?.cantidad || 0}</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>por revisar</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 600, marginTop: '0.25rem' }}>{fmt(data.ventasPend?.monto)}</div>
          </div>
        </ResumenCard>
        <ResumenCard title="Utilidad por Linea de Negocio" icon={TrendingUp} testId="rep-utilidad">
          <SimpleTable
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
        </ResumenCard>
      </div>

      {/* Row 2: Ingresos por Marca + Pendiente Cobrar */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
        <ResumenCard title="Ingresos por Marca" icon={Tag} testId="rep-ing-marca">
          <SimpleTable
            headers={['Marca', 'Ingresos']}
            rows={data.ingresoMarca?.map(r => [r.marca, { v: fmt(r.ingresos), color: '#22c55e', bold: true }]) || []}
            testId="ing-marca-table"
          />
        </ResumenCard>
        <ResumenCard title="Pendiente por Cobrar" icon={TrendingDown} testId="rep-pend-cobrar">
          <SimpleTable
            headers={['Linea', 'Pendiente']}
            rows={data.pendienteCobrar?.map(r => [r.linea || 'Sin clasificar', { v: fmt(r.pendiente), color: '#ef4444', bold: true }]) || []}
            testId="pend-cobrar-table"
          />
        </ResumenCard>
      </div>

      {/* Row 3: Gastos por Categoria + Gastos por Centro */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
        <ResumenCard title="Gastos por Categoria" icon={Wallet} testId="rep-gasto-cat">
          <SimpleTable
            headers={['Categoria', 'Cant.', 'Monto']}
            rows={data.gastoCategoria?.map(r => [r.categoria, r.cantidad, { v: fmt(r.monto), color: '#ef4444', bold: true }]) || []}
            testId="gasto-cat-table"
          />
        </ResumenCard>
        <ResumenCard title="Gastos por Centro de Costo" icon={Target} testId="rep-gasto-cc">
          <SimpleTable
            headers={['Centro', 'Cant.', 'Monto']}
            rows={data.gastoCentro?.map(r => [r.centro_costo, r.cantidad, { v: fmt(r.monto), color: '#ef4444', bold: true }]) || []}
            testId="gasto-cc-table"
          />
        </ResumenCard>
      </div>
    </div>
  );
}

function ResumenCard({ title, icon: Icon, children, testId }) {
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
