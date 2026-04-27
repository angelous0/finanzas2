import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { toast } from 'sonner';
import {
  Factory, RefreshCw, Download, Filter, Search, Zap, ExternalLink,
  Package, Users, Briefcase, ArrowUpRight, CheckCircle2, AlertCircle,
} from 'lucide-react';
import {
  getMovimientosProduccionFinanzas, getUnidadesInternas,
  generarCargosInternos, PRODUCCION_APP_URL,
} from '../services/api';

const fmt = (v) => `S/ ${Number(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtNum = (v) => Number(v || 0).toLocaleString('es-PE');
const fmtDate = (d) => d ? new Date(d + (String(d).length <= 10 ? 'T00:00:00' : '')).toLocaleDateString('es-PE') : '—';
const firstOfMonthISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
};
const todayISO = () => new Date().toISOString().slice(0, 10);

// Mapeo de estado → {label, color, bg}
const ESTADO_LABELS = {
  facturado:       { label: 'Facturado',      color: '#065f46', bg: '#d1fae5', icon: CheckCircle2 },
  sin_factura:     { label: 'Sin factura',    color: '#991b1b', bg: '#fee2e2', icon: AlertCircle },
  cargo_pagado:    { label: 'NI procesada',   color: '#065f46', bg: '#d1fae5', icon: CheckCircle2 },
  cargo_pendiente: { label: 'Cargo pendiente', color: '#b45309', bg: '#fef3c7', icon: AlertCircle },
  sin_cargo:       { label: 'Sin cargo',      color: '#991b1b', bg: '#fee2e2', icon: AlertCircle },
};

export default function MovimientosProduccionFinanzas() {
  const [loading, setLoading] = useState(false);
  const [generando, setGenerando] = useState(false);
  const [data, setData] = useState({ items: [], kpis: {}, por_unidad_interna: [] });
  const [unidades, setUnidades] = useState([]);

  // Filtros
  const [fechaDesde, setFechaDesde] = useState(firstOfMonthISO());
  const [fechaHasta, setFechaHasta] = useState(todayISO());
  const [persona, setPersona] = useState('');
  const [servicio, setServicio] = useState('');
  const [tipoPersona, setTipoPersona] = useState(''); // '' | 'INTERNO' | 'EXTERNO'
  const [unidadId, setUnidadId] = useState('');
  const [estado, setEstado] = useState('');
  const [q, setQ] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (fechaDesde) params.fecha_desde = fechaDesde;
      if (fechaHasta) params.fecha_hasta = fechaHasta;
      if (persona) params.persona_nombre = persona;
      if (servicio) params.servicio = servicio;
      if (tipoPersona) params.tipo_persona = tipoPersona;
      if (unidadId) params.unidad_interna_id = unidadId;
      if (estado) params.estado = estado;
      if (q) params.q = q;
      const r = await getMovimientosProduccionFinanzas(params);
      setData(r.data || { items: [], kpis: {}, por_unidad_interna: [] });
    } catch (e) {
      toast.error('Error al cargar movimientos');
    } finally { setLoading(false); }
  }, [fechaDesde, fechaHasta, persona, servicio, tipoPersona, unidadId, estado, q]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    getUnidadesInternas().then(r => setUnidades(r.data || [])).catch(() => {});
  }, []);

  const handleGenerar = async () => {
    if (!window.confirm('¿Generar cargos para los movimientos internos que aún no los tengan?\n\nEsto crea registros en "Cargos Internos" como CxC virtual (estado: generado).\nDespués hay que procesar la Nota Interna desde Facturas para materializar el ingreso.')) return;
    setGenerando(true);
    try {
      const r = await generarCargosInternos();
      toast.success(r.data.message || 'Cargos generados');
      await load();
    } catch (e) {
      toast.error('Error al generar cargos');
    } finally { setGenerando(false); }
  };

  const exportCSV = () => {
    const rows = data.items || [];
    if (rows.length === 0) { toast.info('No hay filas para exportar'); return; }
    const headers = [
      'N° Corte','Fecha','Persona','Tipo','Servicio','Modelo','Marca','Unidad Interna',
      'Cantidad','Tarifa','Costo','Factura','Cargo','Estado',
    ];
    const csv = [
      headers.join(','),
      ...rows.map(r => [
        r.registro_n_corte || '', r.fecha_inicio || '',
        r.persona_nombre || '', r.tipo_persona || '',
        r.servicio_nombre || '', r.modelo_nombre || '', r.marca_nombre || '',
        r.unidad_interna_nombre || '',
        r.cantidad || 0, r.tarifa || 0, r.monto || 0,
        r.factura_numero || '', r.cargo_estado || '',
        ESTADO_LABELS[r.estado_financiero]?.label || r.estado_financiero,
      ].map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')),
    ].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `movimientos-produccion-${fechaDesde}-${fechaHasta}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const k = data.kpis || {};
  const items = data.items || [];

  const totalCargosPend = (k.cargos_pendientes?.count || 0);

  return (
    <div className="max-w-[1400px] mx-auto p-6 space-y-4" data-testid="movimientos-produccion-finanzas">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Factory size={20} className="text-amber-600"/>
          <div>
            <h2 className="text-lg font-bold">Movimientos de Producción</h2>
            <p className="text-[11px] text-muted-foreground">Eventos productivos con estado financiero</p>
          </div>
        </div>
        <div className="flex gap-2">
          {totalCargosPend > 0 && (
            <button onClick={handleGenerar} disabled={generando}
              className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
              data-testid="btn-generar-cargos">
              {generando ? <><RefreshCw size={14} className="animate-spin"/> Generando…</> : <><Zap size={14}/> Generar cargos faltantes ({totalCargosPend})</>}
            </button>
          )}
          <a href={`${PRODUCCION_APP_URL}/reportes/movimientos-costos`} target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-md border border-border hover:bg-muted"
            title="Abrir en el sistema de Producción">
            <ExternalLink size={14}/> Abrir en Producción
          </a>
          <button onClick={exportCSV}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-md border border-border hover:bg-muted">
            <Download size={14}/> CSV
          </button>
          <button onClick={load} disabled={loading}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-md border border-border hover:bg-muted disabled:opacity-50">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''}/> Actualizar
          </button>
        </div>
      </div>

      {/* KPIs en cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
        <KpiCard icon={Package} label="Movimientos" main={fmtNum(k.movimientos)}
          sub={fmt(k.costo_total)} accent="slate"/>
        <KpiCard icon={Factory} label="Prendas" main={fmtNum(k.prendas)} sub="total" accent="slate"/>
        <KpiCard icon={Users} label="Externo" main={fmtNum(k.externo?.count)}
          sub={fmt(k.externo?.monto)} accent="purple"/>
        <KpiCard icon={Briefcase} label="Interno" main={fmtNum(k.interno?.count)}
          sub={fmt(k.interno?.monto)} accent="emerald"/>
        <KpiCard icon={CheckCircle2} label="Facturados" main={`${k.facturados?.count || 0}/${(k.facturados?.count || 0) + (k.sin_factura?.count || 0)}`}
          sub={fmt(k.facturados?.monto)} accent="emerald"/>
        <KpiCard icon={ArrowUpRight} label="Cargos NI" main={`${k.cargos_pagados?.count || 0}/${(k.cargos_pagados?.count || 0) + (k.cargos_pendientes?.count || 0)}`}
          sub={`${fmt(k.cargos_pagados?.monto)} pag.`} accent="amber"/>
      </div>

      {/* Breakdown por unidad interna */}
      {(data.por_unidad_interna || []).length > 0 && (
        <div className="bg-card rounded-lg border border-border overflow-hidden">
          <div className="px-4 py-2 bg-muted/40 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Resumen por unidad interna
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] uppercase text-muted-foreground border-b border-border">
                <th className="text-left px-4 py-2 font-medium">Unidad</th>
                <th className="text-right px-4 py-2 font-medium">Movimientos</th>
                <th className="text-right px-4 py-2 font-medium">Costo total</th>
                <th className="text-right px-4 py-2 font-medium">Con cargo</th>
                <th className="text-right px-4 py-2 font-medium">Sin cargo</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.por_unidad_interna.map(u => (
                <tr key={u.unidad} className="hover:bg-muted/30">
                  <td className="px-4 py-2 font-medium">{u.unidad}</td>
                  <td className="px-4 py-2 text-right font-mono">{u.count}</td>
                  <td className="px-4 py-2 text-right font-mono">{fmt(u.monto)}</td>
                  <td className="px-4 py-2 text-right font-mono text-emerald-700">{u.con_cargo}</td>
                  <td className="px-4 py-2 text-right font-mono text-amber-700">{u.sin_cargo}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Filtros */}
      <div className="bg-card rounded-lg border border-border p-3 space-y-2">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Filter size={13}/> <span>Filtros</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2">
          <input type="date" value={fechaDesde} onChange={e => setFechaDesde(e.target.value)}
            className="px-2 py-1.5 text-xs rounded-md border border-border bg-background" title="Desde"/>
          <input type="date" value={fechaHasta} onChange={e => setFechaHasta(e.target.value)}
            className="px-2 py-1.5 text-xs rounded-md border border-border bg-background" title="Hasta"/>
          <input type="text" placeholder="Servicio..." value={servicio} onChange={e => setServicio(e.target.value)}
            className="px-2 py-1.5 text-xs rounded-md border border-border bg-background" />
          <input type="text" placeholder="Persona..." value={persona} onChange={e => setPersona(e.target.value)}
            className="px-2 py-1.5 text-xs rounded-md border border-border bg-background" />
          <select value={tipoPersona} onChange={e => setTipoPersona(e.target.value)}
            className="px-2 py-1.5 text-xs rounded-md border border-border bg-background">
            <option value="">Tipo persona…</option>
            <option value="EXTERNO">Externo</option>
            <option value="INTERNO">Interno</option>
          </select>
          <select value={unidadId} onChange={e => setUnidadId(e.target.value)}
            className="px-2 py-1.5 text-xs rounded-md border border-border bg-background">
            <option value="">Unidad interna…</option>
            {unidades.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}
          </select>
          <select value={estado} onChange={e => setEstado(e.target.value)}
            className="px-2 py-1.5 text-xs rounded-md border border-border bg-background">
            <option value="">Estado…</option>
            <option value="facturado">Facturado</option>
            <option value="sin_factura">Sin factura</option>
            <option value="con_cargo">NI procesada</option>
            <option value="sin_cargo">Cargo pendiente / sin cargo</option>
          </select>
        </div>
        <div className="relative">
          <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground"/>
          <input type="text" placeholder="Buscar corte, modelo, persona, factura…"
            value={q} onChange={e => setQ(e.target.value)}
            className="w-full pl-7 pr-2 py-1.5 text-xs rounded-md border border-border bg-background"/>
        </div>
      </div>

      {/* Tabla */}
      <div className="bg-card rounded-lg border border-border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-muted/50 border-b-2 border-border">
                <th className="text-left px-3 py-2 font-semibold uppercase tracking-wider text-muted-foreground">N°</th>
                <th className="text-left px-3 py-2 font-semibold uppercase tracking-wider text-muted-foreground">Fecha</th>
                <th className="text-left px-3 py-2 font-semibold uppercase tracking-wider text-muted-foreground">Persona</th>
                <th className="text-center px-3 py-2 font-semibold uppercase tracking-wider text-muted-foreground">Tipo</th>
                <th className="text-left px-3 py-2 font-semibold uppercase tracking-wider text-muted-foreground">Servicio</th>
                <th className="text-left px-3 py-2 font-semibold uppercase tracking-wider text-muted-foreground">Modelo / Marca</th>
                <th className="text-right px-3 py-2 font-semibold uppercase tracking-wider text-muted-foreground">Prendas</th>
                <th className="text-right px-3 py-2 font-semibold uppercase tracking-wider text-muted-foreground">Tarifa</th>
                <th className="text-right px-3 py-2 font-semibold uppercase tracking-wider text-muted-foreground">Costo</th>
                <th className="text-left px-3 py-2 font-semibold uppercase tracking-wider text-muted-foreground">Factura</th>
                <th className="text-center px-3 py-2 font-semibold uppercase tracking-wider text-muted-foreground">Estado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {loading ? (
                <tr><td colSpan={11} className="py-10 text-center text-muted-foreground">Cargando…</td></tr>
              ) : items.length === 0 ? (
                <tr><td colSpan={11} className="py-10 text-center text-muted-foreground">
                  Sin movimientos para los filtros aplicados.
                </td></tr>
              ) : items.map(it => {
                const est = ESTADO_LABELS[it.estado_financiero] || ESTADO_LABELS.sin_factura;
                const EstIcon = est.icon;
                return (
                  <tr key={it.id} className="hover:bg-muted/30">
                    <td className="px-3 py-2 font-mono font-semibold">{it.registro_n_corte || '—'}</td>
                    <td className="px-3 py-2 text-muted-foreground">{fmtDate(it.fecha_inicio)}</td>
                    <td className="px-3 py-2 font-medium">{it.persona_nombre || '—'}</td>
                    <td className="px-3 py-2 text-center">
                      {it.tipo_persona === 'INTERNO' ? (
                        <span className="inline-block px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 text-[9px] font-bold"
                              title={it.unidad_interna_nombre || ''}>INT</span>
                      ) : (
                        <span className="inline-block px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 text-[9px] font-bold">EXT</span>
                      )}
                    </td>
                    <td className="px-3 py-2">{it.servicio_nombre || '—'}</td>
                    <td className="px-3 py-2">
                      <div className="font-medium truncate max-w-[180px]">{it.modelo_nombre || '—'}</div>
                      {it.marca_nombre && <div className="text-[10px] text-muted-foreground">{it.marca_nombre}</div>}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">{fmtNum(it.cantidad)}</td>
                    <td className="px-3 py-2 text-right font-mono">{Number(it.tarifa || 0).toFixed(4)}</td>
                    <td className="px-3 py-2 text-right font-mono font-semibold">{fmt(it.monto)}</td>
                    <td className="px-3 py-2">
                      {it.factura_numero ? (
                        <span className="text-emerald-700 font-mono text-[10px]">{it.factura_numero}</span>
                      ) : (
                        <span className="text-muted-foreground text-[10px]">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-center">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold"
                            style={{ background: est.bg, color: est.color }}>
                        <EstIcon size={10}/> {est.label}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
            {!loading && items.length > 0 && (
              <tfoot className="bg-muted/40 border-t-2 border-border">
                <tr>
                  <td colSpan={8} className="px-3 py-2 text-right font-semibold text-muted-foreground uppercase text-[10px]">Total →</td>
                  <td className="px-3 py-2 text-right font-mono font-bold text-sm">{fmt(k.costo_total)}</td>
                  <td colSpan={2}></td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </div>
    </div>
  );
}

function KpiCard({ icon: Icon, label, main, sub, accent = 'slate' }) {
  const tones = {
    slate:   { bg: 'bg-slate-500/5',    text: 'text-slate-700 dark:text-slate-300' },
    emerald: { bg: 'bg-emerald-500/5',  text: 'text-emerald-700 dark:text-emerald-400' },
    purple:  { bg: 'bg-purple-500/5',   text: 'text-purple-700 dark:text-purple-400' },
    amber:   { bg: 'bg-amber-500/5',    text: 'text-amber-700 dark:text-amber-400' },
  };
  const t = tones[accent] || tones.slate;
  return (
    <div className={`rounded-lg border border-border p-3 ${t.bg}`}>
      <div className="flex items-center gap-1.5 mb-1">
        <Icon size={12} className={t.text}/>
        <span className="text-[9px] uppercase tracking-wider text-muted-foreground font-medium">{label}</span>
      </div>
      <div className={`text-lg font-bold ${t.text} font-mono leading-tight`}>{main}</div>
      {sub && <div className="text-[10px] text-muted-foreground font-mono mt-0.5">{sub}</div>}
    </div>
  );
}
