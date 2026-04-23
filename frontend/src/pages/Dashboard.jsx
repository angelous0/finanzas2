import React, { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { getDashboardResumen, getCifProduccion } from '../services/api';
import { useEmpresa } from '../context/EmpresaContext';
import { useNavigate } from 'react-router-dom';
import {
  TrendingUp, TrendingDown, Wallet, CreditCard,
  AlertTriangle, Layers, ArrowRight, RefreshCw,
  DollarSign, ShoppingCart
} from 'lucide-react';

const fmt = (v) => `S/ ${Number(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [cifData, setCifData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showAllLineas, setShowAllLineas] = useState(false);
  const { empresaActual } = useEmpresa();
  const navigate = useNavigate();

  const load = async () => {
    setLoading(true);
    try {
      const [res, cifRes] = await Promise.all([
        getDashboardResumen(),
        getCifProduccion().catch(() => ({ data: null }))
      ]);
      setData(res.data);
      setCifData(cifRes.data);
    } catch (err) {
      toast.error('Error al cargar dashboard');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (empresaActual?.id) load(); }, [empresaActual?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex items-center gap-3 text-muted-foreground">
          <RefreshCw size={20} className="animate-spin" />
          <span className="text-sm">Cargando dashboard...</span>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground text-sm">
        Sin datos disponibles
      </div>
    );
  }

  const hasAlerts = data.ventas_pendientes_cantidad > 0 || data.gastos_prorrateo_cantidad > 0 || data.cobranza_pendiente_total > 0;

  return (
    <div className="max-w-[1400px] space-y-6" data-testid="dashboard-ejecutivo">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground tracking-tight">Panel de Control</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Resumen ejecutivo del mes actual</p>
        </div>
        <button
          className="inline-flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium text-foreground hover:bg-muted transition-colors"
          onClick={load}
          data-testid="refresh-dashboard"
        >
          <RefreshCw size={14} />
          Actualizar
        </button>
      </div>

      {/* Alerts */}
      {hasAlerts && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3" data-testid="alerts-section">
          {data.ventas_pendientes_cantidad > 0 && (
            <AlertCard
              icon={ShoppingCart}
              color="amber"
              text={`${data.ventas_pendientes_cantidad} ventas pendientes`}
              sub={fmt(data.ventas_pendientes_monto)}
              onClick={() => navigate('/ventas-pos')}
              testId="alert-ventas-pendientes"
            />
          )}
          {data.gastos_prorrateo_cantidad > 0 && (
            <AlertCard
              icon={Layers}
              color="violet"
              text={`${data.gastos_prorrateo_cantidad} gastos sin prorratear`}
              sub={fmt(data.gastos_prorrateo_monto)}
              onClick={() => navigate('/prorrateo')}
              testId="alert-gastos-prorrateo"
            />
          )}
          {data.cobranza_pendiente_total > 0 && (
            <AlertCard
              icon={CreditCard}
              color="red"
              text="Cobranza pendiente"
              sub={fmt(data.cobranza_pendiente_total)}
              onClick={() => navigate('/cxc')}
              testId="alert-cobranza"
            />
          )}
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4" data-testid="kpi-cards">
        <KpiCard
          label="Ingresos del Mes"
          value={fmt(data.ingresos_mes)}
          icon={TrendingUp}
          iconBg="bg-emerald-500/10"
          iconColor="text-emerald-600"
          testId="kpi-ingresos"
          note={data.ingresos_mes === 0 ? 'Sin ventas registradas en el período' : null}
        />
        <KpiCard
          label="Costos Proveedores"
          value={fmt(data.egresos_proveedores_mes || 0)}
          icon={Wallet}
          iconBg="bg-orange-500/10"
          iconColor="text-orange-600"
          testId="kpi-costos-prov"
        />
        <KpiCard
          label="Gastos del Mes"
          value={fmt(data.gastos_mes)}
          icon={DollarSign}
          iconBg="bg-red-500/10"
          iconColor="text-red-600"
          testId="kpi-gastos"
        />
        <KpiCard
          label="Resultado Neto"
          value={fmt(data.resultado_neto)}
          icon={data.resultado_neto >= 0 ? TrendingUp : TrendingDown}
          iconBg={data.resultado_neto >= 0 ? 'bg-emerald-500/10' : 'bg-red-500/10'}
          iconColor={data.resultado_neto >= 0 ? 'text-emerald-600' : 'text-red-600'}
          badge={data.resultado_neto >= 0 ? 'positive' : 'negative'}
          testId="kpi-resultado"
        />
      </div>

      {/* CIF Produccion Card */}
      {cifData && cifData.total_cif > 0 && (
        <div className="rounded-xl border border-border bg-card shadow-sm p-5" data-testid="cif-card">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-foreground">CIF Producci&oacute;n ({cifData.periodo})</h2>
            <button
              className="text-xs text-blue-600 hover:underline"
              onClick={() => navigate('/gastos')}
            >
              Ver gastos CIF
            </button>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-xs text-muted-foreground">Gastos CIF</p>
              <p className="text-lg font-bold text-foreground">{fmt(cifData.total_gastos_cif)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Depreciaci&oacute;n</p>
              <p className="text-lg font-bold text-foreground">{fmt(cifData.depreciacion_mes)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Total CIF</p>
              <p className="text-lg font-bold text-emerald-600">{fmt(cifData.total_cif)}</p>
            </div>
          </div>
        </div>
      )}

      {/* Utilidad por Linea */}
      <div className="rounded-xl border border-border bg-card shadow-sm">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="text-sm font-semibold text-foreground">Utilidad por Linea de Negocio</h2>
          <div className="flex items-center gap-2">
            {data.utilidad_linea?.some(l =>
              (l.ingresos || 0) === 0 && (l.egresos_proveedores || 0) === 0 &&
              (l.gastos_directos || 0) === 0 && (l.gastos_prorrateados || 0) === 0
            ) && (
              <button
                onClick={() => setShowAllLineas(v => !v)}
                className="text-xs text-blue-600 hover:underline"
                data-testid="toggle-lineas-vacias"
              >
                {showAllLineas ? 'Ocultar líneas sin movimientos' : 'Mostrar todas'}
              </button>
            )}
            <span className="text-xs text-muted-foreground px-2 py-1 rounded-md bg-muted">Mes actual</span>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="utilidad-linea-table">
            <thead>
              <tr className="border-b border-border bg-muted/30">
                <th className="text-left px-5 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Linea de Negocio</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Ingresos</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Costos Prov.</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Gastos Dir.</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Utilidad (antes)</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Prorrateo</th>
                <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Utilidad (despues)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {(() => {
                const lineasFiltradas = showAllLineas
                  ? (data.utilidad_linea || [])
                  : (data.utilidad_linea || []).filter(l =>
                      (l.ingresos || 0) !== 0 || (l.egresos_proveedores || 0) !== 0 ||
                      (l.gastos_directos || 0) !== 0 || (l.gastos_prorrateados || 0) !== 0
                    );
                return lineasFiltradas.length > 0 ? lineasFiltradas.map((l, i) => (
                <tr key={i} className="hover:bg-muted/30 transition-colors">
                  <td className="px-5 py-3 font-medium text-foreground">{l.linea_nombre}</td>
                  <td className="px-4 py-3 text-right text-emerald-600">{fmt(l.ingresos)}</td>
                  <td className="px-4 py-3 text-right text-orange-600">{fmt(l.egresos_proveedores || 0)}</td>
                  <td className="px-4 py-3 text-right text-red-600">{fmt(l.gastos_directos)}</td>
                  <td className="px-4 py-3 text-right">
                    <UtilityBadge value={l.utilidad_antes_prorrateo} />
                  </td>
                  <td className="px-4 py-3 text-right text-violet-600">{fmt(l.gastos_prorrateados)}</td>
                  <td className="px-4 py-3 text-right">
                    <UtilityBadge value={l.utilidad_despues_prorrateo} bold />
                  </td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={7} className="px-5 py-8 text-center text-muted-foreground">
                    Sin movimientos este mes
                  </td>
                </tr>
              );
              })()}
            </tbody>
            {data.utilidad_linea?.length > 0 && (
              <tfoot>
                <tr className="bg-muted/50 font-semibold border-t-2 border-border">
                  <td className="px-5 py-3 text-foreground">Total</td>
                  <td className="px-4 py-3 text-right text-emerald-600">
                    {fmt(data.utilidad_linea.reduce((s, l) => s + l.ingresos, 0))}
                  </td>
                  <td className="px-4 py-3 text-right text-orange-600">
                    {fmt(data.utilidad_linea.reduce((s, l) => s + (l.egresos_proveedores || 0), 0))}
                  </td>
                  <td className="px-4 py-3 text-right text-red-600">
                    {fmt(data.utilidad_linea.reduce((s, l) => s + l.gastos_directos, 0))}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <UtilityBadge value={data.utilidad_linea.reduce((s, l) => s + l.utilidad_antes_prorrateo, 0)} />
                  </td>
                  <td className="px-4 py-3 text-right text-violet-600">
                    {fmt(data.utilidad_linea.reduce((s, l) => s + l.gastos_prorrateados, 0))}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <UtilityBadge value={data.utilidad_linea.reduce((s, l) => s + l.utilidad_despues_prorrateo, 0)} bold />
                  </td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </div>

      {/* Cobranza por linea */}
      {data.cobranza_pendiente_linea?.length > 0 && (
        <div className="rounded-xl border border-border bg-card shadow-sm">
          <div className="px-5 py-4 border-b border-border">
            <h2 className="text-sm font-semibold text-foreground">Cobranza Pendiente por Linea</h2>
          </div>
          <div className="px-5 py-3 divide-y divide-border">
            {data.cobranza_pendiente_linea.map((c, i) => (
              <div key={i} className="flex items-center justify-between py-3" data-testid={`cobranza-linea-${i}`}>
                <span className="text-sm font-medium text-foreground">{c.linea_nombre || 'Sin clasificar'}</span>
                <span className="text-sm font-semibold text-red-600">{fmt(c.saldo_pendiente)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function KpiCard({ label, value, icon: Icon, iconBg, iconColor, badge, note, testId }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm" data-testid={testId}>
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{label}</p>
          <p className="text-xl font-bold text-foreground">{value}</p>
        </div>
        <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${iconBg}`}>
          <Icon size={20} className={iconColor} />
        </div>
      </div>
      {note && (
        <p className="mt-2 text-xs text-muted-foreground/70 italic">{note}</p>
      )}
      {badge && (
        <div className="mt-3">
          <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
            badge === 'positive'
              ? 'bg-emerald-500/10 text-emerald-600'
              : 'bg-red-500/10 text-red-600'
          }`}>
            {badge === 'positive' ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
            {badge === 'positive' ? 'Positivo' : 'Negativo'}
          </span>
        </div>
      )}
    </div>
  );
}

function AlertCard({ icon: Icon, color, text, sub, onClick, testId }) {
  const colorMap = {
    amber: 'bg-amber-500/10 border-amber-500/20 text-amber-600',
    violet: 'bg-violet-500/10 border-violet-500/20 text-violet-600',
    red: 'bg-red-500/10 border-red-500/20 text-red-600',
  };
  const classes = colorMap[color] || colorMap.amber;

  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-3 rounded-xl border p-4 text-left transition-all hover:shadow-md ${classes}`}
      data-testid={testId}
    >
      <AlertTriangle size={18} />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold">{text}</div>
        <div className="text-base font-bold text-foreground">{sub}</div>
      </div>
      <ArrowRight size={16} className="text-muted-foreground" />
    </button>
  );
}

function UtilityBadge({ value, bold }) {
  const positive = value >= 0;
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs ${bold ? 'font-bold' : 'font-semibold'} ${
      positive
        ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
        : 'bg-red-500/10 text-red-700 dark:text-red-400'
    }`}>
      {fmt(value)}
    </span>
  );
}
