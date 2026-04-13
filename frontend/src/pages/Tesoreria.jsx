import React, { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { useEmpresa } from '../context/EmpresaContext';
import { getTesoreria, getTesoreriaResumen } from '../services/api';
import { ArrowUpCircle, ArrowDownCircle, Vault, Filter, Plus, RefreshCw } from 'lucide-react';

const ORIGEN_LABELS = {
  venta_pos_confirmada: 'Venta POS',
  cobranza_cxc: 'Cobranza CxC',
  pago_cxp: 'Pago CxP',
  gasto_directo: 'Gasto Directo',
  manual: 'Manual',
};

const formatCurrency = (val) => {
  const n = Number(val) || 0;
  return `S/ ${n.toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

export default function Tesoreria() {
  const { empresaActual } = useEmpresa();
  const [resumen, setResumen] = useState(null);
  const [movimientos, setMovimientos] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filtroTipo, setFiltroTipo] = useState('');
  const [filtroOrigen, setFiltroOrigen] = useState('');
  const [fechaDesde, setFechaDesde] = useState(() => {
    const d = new Date(); d.setDate(1);
    return d.toISOString().split('T')[0];
  });
  const [fechaHasta, setFechaHasta] = useState(() => new Date().toISOString().split('T')[0]);
  const [page, setPage] = useState(1);

  const eId = empresaActual?.id;

  const fetchData = useCallback(async () => {
    if (!eId) return;
    setLoading(true);
    try {
      const queryParams = { page, page_size: 50 };
      if (filtroTipo) queryParams.tipo = filtroTipo;
      if (filtroOrigen) queryParams.origen_tipo = filtroOrigen;
      if (fechaDesde) queryParams.fecha_desde = fechaDesde;
      if (fechaHasta) queryParams.fecha_hasta = fechaHasta;

      const resQueryParams = {};

      const [movRes, resumenRes] = await Promise.all([
        getTesoreria(queryParams),
        getTesoreriaResumen(resQueryParams),
      ]);
      setMovimientos(movRes.data?.data || []);
      setTotal(movRes.data?.total || 0);
      setResumen(resumenRes.data);
    } catch (e) {
      toast.error('Error al cargar tesorería');
    } finally {
      setLoading(false);
    }
  }, [eId, filtroTipo, filtroOrigen, fechaDesde, fechaHasta, page]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (!eId) return <div className="p-6">Seleccione una empresa</div>;

  return (
    <div className="p-4 md:p-6 space-y-6" data-testid="tesoreria-page">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Vault className="w-7 h-7 text-emerald-500" />
          <div>
            <h1 className="text-2xl font-bold">Tesoreria</h1>
            <p className="text-sm text-gray-500">Movimientos reales de caja y banco - Fuente unica de verdad</p>
          </div>
        </div>
        <button onClick={fetchData} className="btn btn-ghost" data-testid="refresh-tesoreria-btn">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* KPIs */}
      {resumen && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="tesoreria-kpis">
          <KpiCard label="Saldo Total" value={formatCurrency(resumen.saldo_total)} color="emerald" />
          <KpiCard label="Ingresos Periodo" value={formatCurrency(resumen.total_ingresos)} sub={`${resumen.count_ingresos} mov.`} color="green" />
          <KpiCard label="Egresos Periodo" value={formatCurrency(resumen.total_egresos)} sub={`${resumen.count_egresos} mov.`} color="red" />
          <KpiCard label="Flujo Neto" value={formatCurrency(resumen.flujo_neto)} color={resumen.flujo_neto >= 0 ? 'blue' : 'red'} />
        </div>
      )}

      {/* Cuentas */}
      {resumen?.cuentas?.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3" data-testid="tesoreria-cuentas">
          {resumen.cuentas.map(c => (
            <div key={c.id} className="card p-3 flex items-center justify-between">
              <div>
                <div className="text-xs text-gray-500 uppercase">{c.tipo}</div>
                <div className="font-medium text-sm">{c.nombre}</div>
              </div>
              <div className="font-bold text-sm">{formatCurrency(c.saldo)}</div>
            </div>
          ))}
        </div>
      )}

      {/* By origin breakdown */}
      {resumen?.por_origen?.length > 0 && (
        <div className="card p-4" data-testid="tesoreria-por-origen">
          <h3 className="text-sm font-semibold mb-3">Desglose por Origen</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {resumen.por_origen.map((o, i) => (
              <div key={i} className="flex items-center gap-2 p-2 rounded-lg bg-gray-50">
                {o.tipo === 'ingreso' ? <ArrowUpCircle className="w-4 h-4 text-green-500" /> : <ArrowDownCircle className="w-4 h-4 text-red-500" />}
                <div>
                  <div className="text-xs font-medium">{ORIGEN_LABELS[o.origen_tipo] || o.origen_tipo}</div>
                  <div className="text-xs text-gray-500">{o.count} mov. | {formatCurrency(o.total)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filtros */}
      <div className="card p-4 flex flex-wrap items-center gap-3" data-testid="tesoreria-filtros">
        <Filter className="w-4 h-4 text-gray-400" />
        <input type="date" value={fechaDesde} onChange={e => { setFechaDesde(e.target.value); setPage(1); }} className="input input-sm" data-testid="tesoreria-fecha-desde" />
        <input type="date" value={fechaHasta} onChange={e => { setFechaHasta(e.target.value); setPage(1); }} className="input input-sm" data-testid="tesoreria-fecha-hasta" />
        <select value={filtroTipo} onChange={e => { setFiltroTipo(e.target.value); setPage(1); }} className="input input-sm" data-testid="tesoreria-filtro-tipo">
          <option value="">Todos los tipos</option>
          <option value="ingreso">Ingresos</option>
          <option value="egreso">Egresos</option>
        </select>
        <select value={filtroOrigen} onChange={e => { setFiltroOrigen(e.target.value); setPage(1); }} className="input input-sm" data-testid="tesoreria-filtro-origen">
          <option value="">Todos los origenes</option>
          <option value="venta_pos_confirmada">Venta POS</option>
          <option value="cobranza_cxc">Cobranza CxC</option>
          <option value="pago_cxp">Pago CxP</option>
          <option value="gasto_directo">Gasto Directo</option>
          <option value="manual">Manual</option>
        </select>
      </div>

      {/* Table */}
      <div className="card overflow-x-auto" data-testid="tesoreria-table">
        <table className="table w-full">
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Tipo</th>
              <th>Monto</th>
              <th>Origen</th>
              <th>Concepto</th>
              <th>Cuenta</th>
              <th>Forma Pago</th>
              <th>Marca</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} className="text-center py-8">Cargando...</td></tr>
            ) : movimientos.length === 0 ? (
              <tr><td colSpan={8} className="text-center py-8 text-gray-400">Sin movimientos de tesoreria en el periodo</td></tr>
            ) : movimientos.map(m => (
              <tr key={m.id} data-testid={`tesoreria-row-${m.id}`}>
                <td className="text-sm">{m.fecha ? new Date(m.fecha).toLocaleDateString('es-PE') : '-'}</td>
                <td>
                  <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${m.tipo === 'ingreso' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                    {m.tipo === 'ingreso' ? <ArrowUpCircle className="w-3 h-3" /> : <ArrowDownCircle className="w-3 h-3" />}
                    {m.tipo}
                  </span>
                </td>
                <td className={`font-medium ${m.tipo === 'ingreso' ? 'text-green-600' : 'text-red-600'}`}>
                  {m.tipo === 'ingreso' ? '+' : '-'}{formatCurrency(m.monto)}
                </td>
                <td className="text-xs">{ORIGEN_LABELS[m.origen_tipo] || m.origen_tipo}</td>
                <td className="text-sm max-w-[200px] truncate">{m.concepto || '-'}</td>
                <td className="text-xs">{m.cuenta_nombre || '-'}</td>
                <td className="text-xs">{m.forma_pago || '-'}</td>
                <td className="text-xs">{m.marca_nombre || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {total > 50 && (
          <div className="flex justify-center gap-2 p-3 border-t">
            <button onClick={() => setPage(p => Math.max(1, p-1))} disabled={page <= 1} className="btn btn-sm">Anterior</button>
            <span className="text-sm self-center">Pagina {page} de {Math.ceil(total / 50)}</span>
            <button onClick={() => setPage(p => p+1)} disabled={page >= Math.ceil(total / 50)} className="btn btn-sm">Siguiente</button>
          </div>
        )}
      </div>
    </div>
  );
}

function KpiCard({ label, value, sub, color = 'gray' }) {
  const colorMap = {
    emerald: 'border-l-emerald-500', green: 'border-l-green-500',
    red: 'border-l-red-500', blue: 'border-l-blue-500', gray: 'border-l-gray-300',
  };
  return (
    <div className={`card p-4 border-l-4 ${colorMap[color]}`}>
      <div className="text-xs text-gray-500 font-medium">{label}</div>
      <div className="text-lg font-bold mt-1">{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
    </div>
  );
}
