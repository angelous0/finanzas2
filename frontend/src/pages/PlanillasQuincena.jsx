import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Eye, Trash2, FileText, Calendar, Users } from 'lucide-react';
import { toast } from 'sonner';
import { getPlanillasQuincena, deletePlanillaQuincena } from '../services/api';
import { useEmpresa } from '../context/EmpresaContext';

const fmt = (v) => `S/ ${Number(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const MESES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'];

const ESTADOS = {
  borrador:  { label: 'Borrador',  color: 'bg-gray-500/10 text-gray-600' },
  aprobada:  { label: 'Aprobada',  color: 'bg-blue-500/10 text-blue-600' },
  pagada:    { label: 'Pagada',    color: 'bg-emerald-500/10 text-emerald-600' },
  anulada:   { label: 'Anulada',   color: 'bg-red-500/10 text-red-600' },
};

export default function PlanillasQuincena() {
  const { empresaActual } = useEmpresa();
  const navigate = useNavigate();
  const [planillas, setPlanillas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filtroEstado, setFiltroEstado] = useState('');
  const [filtroAnio, setFiltroAnio] = useState('');

  const load = useCallback(async () => {
    if (!empresaActual) return;
    setLoading(true);
    try {
      const params = {};
      if (filtroEstado) params.estado = filtroEstado;
      if (filtroAnio) params.anio = filtroAnio;
      const r = await getPlanillasQuincena(params);
      setPlanillas(r.data || []);
    } catch { toast.error('Error cargando planillas'); }
    finally { setLoading(false); }
  }, [empresaActual, filtroEstado, filtroAnio]);

  useEffect(() => { load(); }, [load]);

  const handleDelete = async (p) => {
    const periodo = `${p.anio}-${String(p.mes).padStart(2,'0')}-Q${p.quincena}`;
    const fmtMonto = (v) => `S/ ${Number(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    let mensaje;
    if (p.estado === 'pagada') {
      mensaje =
        `⚠️ ATENCIÓN — Planilla PAGADA\n\n` +
        `Se eliminará la planilla ${periodo}.\n\n` +
        `Esto ejecutará AUTOMÁTICAMENTE:\n` +
        `• Reversión de egresos por ${fmtMonto(p.total_neto)} (se generarán INGRESOS en las cuentas)\n` +
        `• Restauración de saldos de cuentas bancarias\n` +
        `• Los adelantos vinculados volverán a "Pendiente"\n` +
        `• Se borrará la planilla y todo su histórico\n\n` +
        `Esta acción NO se puede deshacer.\n\n` +
        `¿Continuar?`;
    } else if (p.estado === 'aprobada') {
      mensaje =
        `¿Eliminar planilla ${periodo} (APROBADA)?\n\n` +
        `• Los adelantos vinculados volverán a "Pendiente"\n` +
        `• Se borrará la planilla y todos sus detalles\n\n` +
        `Esta acción NO se puede deshacer.`;
    } else {
      mensaje = `¿Eliminar planilla ${periodo} (${p.estado})?\n\nLos adelantos vinculados volverán a "Pendiente".`;
    }

    if (!window.confirm(mensaje)) return;

    // Doble confirmación si está pagada
    if (p.estado === 'pagada') {
      const c2 = window.prompt('Escribe "ELIMINAR" (mayúsculas) para confirmar la eliminación de la planilla pagada:');
      if (c2 !== 'ELIMINAR') {
        toast.info('Eliminación cancelada');
        return;
      }
    }

    try {
      const r = await deletePlanillaQuincena(p.id);
      if (r.data?.se_revirtieron_egresos) {
        toast.success('Planilla eliminada y egresos revertidos');
      } else {
        toast.success('Planilla eliminada');
      }
      load();
    } catch (err) {
      toast.error(typeof err.response?.data?.detail === 'string' ? err.response.data.detail : 'Error al eliminar');
    }
  };

  return (
    <div className="max-w-[1200px] space-y-6" data-testid="planillas-quincena-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground tracking-tight flex items-center gap-2">
            <FileText size={22} /> Planillas Quincenales
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Gestión de planillas por quincena: calcular, aprobar y pagar con múltiples medios.
          </p>
        </div>
        <button onClick={() => navigate('/planillas-quincena/nueva')}
          className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-emerald-700 shadow-sm"
          data-testid="nueva-planilla-btn">
          <Plus size={16} /> Nueva planilla
        </button>
      </div>

      {/* Filtros */}
      <div className="flex gap-2 flex-wrap">
        <select value={filtroEstado} onChange={e => setFiltroEstado(e.target.value)}
          className="px-3 py-2 text-sm rounded-md border border-border bg-background">
          <option value="">Todos los estados</option>
          <option value="borrador">Borrador</option>
          <option value="aprobada">Aprobada</option>
          <option value="pagada">Pagada</option>
          <option value="anulada">Anulada</option>
        </select>
        <input type="number" placeholder="Año" value={filtroAnio}
          onChange={e => setFiltroAnio(e.target.value)}
          className="px-3 py-2 text-sm rounded-md border border-border bg-background w-28" />
      </div>

      {/* Tabla */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 border-b border-border">
            <tr>
              <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Período</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Fechas</th>
              <th className="text-center px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Trab.</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Bruto</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Descuentos</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Neto</th>
              <th className="text-center px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Estado</th>
              <th className="w-24"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {loading ? (
              <tr><td colSpan={8} className="py-10 text-center text-muted-foreground">Cargando…</td></tr>
            ) : planillas.length === 0 ? (
              <tr><td colSpan={8} className="py-10 text-center text-muted-foreground">
                Sin planillas. Crea la primera con el botón <strong>Nueva planilla</strong>.
              </td></tr>
            ) : planillas.map(p => {
              const desc = parseFloat(p.total_afp || 0) + parseFloat(p.total_tardanzas || 0) + parseFloat(p.total_adelantos || 0);
              const est = ESTADOS[p.estado] || ESTADOS.borrador;
              return (
                <tr key={p.id} className="hover:bg-muted/30 cursor-pointer"
                    onClick={() => navigate(`/planillas-quincena/${p.id}`)}
                    data-testid={`planilla-row-${p.id}`}>
                  <td className="px-4 py-3">
                    <div className="font-medium text-foreground">
                      {MESES[p.mes-1]} {p.anio} · Q{p.quincena}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {p.fecha_inicio} — {p.fecha_fin}
                  </td>
                  <td className="px-4 py-3 text-center text-xs">{p.num_trabajadores || 0}</td>
                  <td className="px-4 py-3 text-right font-mono text-xs text-emerald-700 dark:text-emerald-400">{fmt(p.total_bruto)}</td>
                  <td className="px-4 py-3 text-right font-mono text-xs text-red-600">{fmt(desc)}</td>
                  <td className="px-4 py-3 text-right font-mono text-sm font-bold">{fmt(p.total_neto)}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-medium ${est.color}`}>
                      {est.label}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-right" onClick={e => e.stopPropagation()}>
                    <div className="inline-flex gap-1">
                      <button onClick={() => navigate(`/planillas-quincena/${p.id}`)}
                        className="h-7 w-7 flex items-center justify-center rounded-md hover:bg-muted text-muted-foreground hover:text-foreground"
                        title="Ver">
                        <Eye size={14}/>
                      </button>
                      <button onClick={() => handleDelete(p)}
                        className={`h-7 w-7 flex items-center justify-center rounded-md hover:bg-red-500/10 text-red-600 ${p.estado === 'pagada' ? 'ring-1 ring-red-500/40' : ''}`}
                        title={p.estado === 'pagada' ? 'Eliminar (revierte egresos automáticamente)' : 'Eliminar'}
                        data-testid={`delete-planilla-${p.id}`}>
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
