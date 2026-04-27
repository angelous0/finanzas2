import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Eye, Trash2, Scissors, Calendar } from 'lucide-react';
import { toast } from 'sonner';
import { getPlanillasDestajo, deletePlanillaDestajo } from '../services/api';
import { useEmpresa } from '../context/EmpresaContext';

const fmt = (v) => `S/ ${Number(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtDate = (d) => d ? new Date(d + 'T00:00:00').toLocaleDateString('es-PE') : '—';

const ESTADOS = {
  borrador: { label: 'Borrador', color: 'bg-gray-500/10 text-gray-600' },
  aprobada: { label: 'Aprobada', color: 'bg-blue-500/10 text-blue-600' },
  pagada:   { label: 'Pagada',   color: 'bg-emerald-500/10 text-emerald-600' },
  anulada:  { label: 'Anulada',  color: 'bg-red-500/10 text-red-600' },
};

export default function PlanillasDestajo() {
  const { empresaActual } = useEmpresa();
  const navigate = useNavigate();
  const [planillas, setPlanillas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filtroEstado, setFiltroEstado] = useState('');

  const load = useCallback(async () => {
    if (!empresaActual) return;
    setLoading(true);
    try {
      const params = {};
      if (filtroEstado) params.estado = filtroEstado;
      const r = await getPlanillasDestajo(params);
      setPlanillas(r.data || []);
    } catch {
      toast.error('Error cargando planillas destajo');
    } finally { setLoading(false); }
  }, [empresaActual, filtroEstado]);

  useEffect(() => { load(); }, [load]);

  const handleDelete = async (p) => {
    const periodo = `${fmtDate(p.fecha_desde)} — ${fmtDate(p.fecha_hasta)}`;
    let mensaje;
    if (p.estado === 'pagada') {
      mensaje =
        `⚠️ ATENCIÓN — Planilla destajo PAGADA\n\n` +
        `Se eliminará la planilla ${periodo}.\n\n` +
        `Se revertirán automáticamente:\n` +
        `• Los egresos por ${fmt(p.total_neto)}\n` +
        `• El saldo de las cuentas\n` +
        `• Los adelantos vinculados volverán a "Pendiente"\n` +
        `• Los movimientos volverán a estar disponibles para otra planilla\n\n` +
        `Esta acción NO se puede deshacer.`;
    } else {
      mensaje = `¿Eliminar planilla destajo ${periodo} (${p.estado})?\n\n` +
               `Los movimientos incluidos volverán a estar disponibles.\n` +
               `Los adelantos vinculados volverán a "Pendiente".`;
    }
    if (!window.confirm(mensaje)) return;
    if (p.estado === 'pagada') {
      const c = window.prompt('Escribe "ELIMINAR" (mayúsculas) para confirmar:');
      if (c !== 'ELIMINAR') { toast.info('Eliminación cancelada'); return; }
    }
    try {
      await deletePlanillaDestajo(p.id);
      toast.success('Planilla eliminada');
      load();
    } catch (err) {
      toast.error(typeof err.response?.data?.detail === 'string'
        ? err.response.data.detail : 'Error al eliminar');
    }
  };

  return (
    <div className="max-w-[1200px] space-y-6" data-testid="planillas-destajo-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground tracking-tight flex items-center gap-2">
            <Scissors size={22}/> Planillas Destajo
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Pago a destajistas según los movimientos de producción del período.
          </p>
        </div>
        <button onClick={() => navigate('/planillas-destajo/nueva')}
          className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-emerald-700 shadow-sm"
          data-testid="nueva-planilla-destajo-btn">
          <Plus size={16}/> Nueva planilla
        </button>
      </div>

      <div className="flex gap-2 flex-wrap">
        <select value={filtroEstado} onChange={e => setFiltroEstado(e.target.value)}
          className="px-3 py-2 text-sm rounded-md border border-border bg-background">
          <option value="">Todos los estados</option>
          <option value="borrador">Borrador</option>
          <option value="aprobada">Aprobada</option>
          <option value="pagada">Pagada</option>
          <option value="anulada">Anulada</option>
        </select>
      </div>

      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 border-b border-border">
            <tr>
              <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Período</th>
              <th className="text-center px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Trab.</th>
              <th className="text-center px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Movs</th>
              <th className="text-center px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Prendas</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Bruto</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Adel.</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Neto</th>
              <th className="text-center px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Estado</th>
              <th className="w-24"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {loading ? (
              <tr><td colSpan={9} className="py-10 text-center text-muted-foreground">Cargando…</td></tr>
            ) : planillas.length === 0 ? (
              <tr><td colSpan={9} className="py-10 text-center text-muted-foreground">
                Sin planillas destajo. Crea la primera con <strong>Nueva planilla</strong>.
              </td></tr>
            ) : planillas.map(p => {
              const est = ESTADOS[p.estado] || ESTADOS.borrador;
              return (
                <tr key={p.id} className="hover:bg-muted/30 cursor-pointer"
                    onClick={() => navigate(`/planillas-destajo/${p.id}`)}
                    data-testid={`planilla-destajo-row-${p.id}`}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <Calendar size={14} className="text-muted-foreground"/>
                      <div>
                        <div className="font-medium text-foreground">{fmtDate(p.fecha_desde)} — {fmtDate(p.fecha_hasta)}</div>
                        {p.notas && <div className="text-[10px] text-muted-foreground mt-0.5 truncate max-w-[280px]">{p.notas}</div>}
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-center text-xs">{p.num_trabajadores || 0}</td>
                  <td className="px-4 py-3 text-center text-xs">{p.num_movimientos || 0}</td>
                  <td className="px-4 py-3 text-center text-xs">{(p.prendas || 0).toLocaleString('es-PE')}</td>
                  <td className="px-4 py-3 text-right font-mono text-xs text-emerald-700 dark:text-emerald-400">{fmt(p.total_bruto)}</td>
                  <td className="px-4 py-3 text-right font-mono text-xs text-red-600">{fmt(p.total_adelantos)}</td>
                  <td className="px-4 py-3 text-right font-mono text-sm font-bold">{fmt(p.total_neto)}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${est.color}`}>
                      {est.label}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-right" onClick={e => e.stopPropagation()}>
                    <div className="inline-flex gap-1">
                      <button onClick={() => navigate(`/planillas-destajo/${p.id}`)}
                        className="h-7 w-7 flex items-center justify-center rounded-md hover:bg-muted text-muted-foreground hover:text-foreground"
                        title="Ver">
                        <Eye size={14}/>
                      </button>
                      <button onClick={() => handleDelete(p)}
                        className={`h-7 w-7 flex items-center justify-center rounded-md hover:bg-red-500/10 text-red-600 ${p.estado === 'pagada' ? 'ring-1 ring-red-500/40' : ''}`}
                        title={p.estado === 'pagada' ? 'Eliminar (revierte pagos automáticamente)' : 'Eliminar'}
                        data-testid={`delete-planilla-destajo-${p.id}`}>
                        <Trash2 size={14}/>
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
