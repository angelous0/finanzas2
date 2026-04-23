import React, { useState, useEffect } from 'react';
import { Settings, Save, RefreshCw, Info } from 'lucide-react';
import { toast } from 'sonner';
import { getAjustesPlanilla, updateAjustesPlanilla, getAfps } from '../services/api';
import { useEmpresa } from '../context/EmpresaContext';

const fmt = (v) => `S/ ${Number(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function AjustesPlanilla() {
  const { empresaActual } = useEmpresa();
  const [form, setForm] = useState({
    sueldo_minimo: '',
    horas_quincena_default: '',
    asignacion_familiar_pct: '',
  });
  const [afps, setAfps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    if (!empresaActual) return;
    setLoading(true);
    try {
      const [a, f] = await Promise.all([
        getAjustesPlanilla(),
        getAfps({ activo: true }),
      ]);
      setForm({
        sueldo_minimo: a.data.sueldo_minimo,
        horas_quincena_default: a.data.horas_quincena_default,
        asignacion_familiar_pct: a.data.asignacion_familiar_pct,
      });
      setAfps(f.data || []);
    } catch (e) {
      toast.error('Error cargando ajustes');
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [empresaActual]); // eslint-disable-line

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await updateAjustesPlanilla({
        sueldo_minimo: parseFloat(form.sueldo_minimo),
        horas_quincena_default: parseInt(form.horas_quincena_default),
        asignacion_familiar_pct: parseFloat(form.asignacion_familiar_pct),
      });
      toast.success('Ajustes guardados');
      load();
    } catch (e) {
      toast.error(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Error');
    } finally { setSaving(false); }
  };

  if (loading) return <div className="p-8 text-muted-foreground">Cargando ajustes…</div>;

  const asigFamMonto = (parseFloat(form.sueldo_minimo) || 0) * (parseFloat(form.asignacion_familiar_pct) || 0) / 100;

  return (
    <div className="max-w-[900px] space-y-6" data-testid="ajustes-planilla-page">
      <div>
        <h1 className="text-xl font-bold text-foreground tracking-tight flex items-center gap-2">
          <Settings size={22} /> Ajustes de Planilla
        </h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Parámetros globales que se usan en los cálculos de sueldo, horas extras, asignación familiar y aportes AFP.
        </p>
      </div>

      <form onSubmit={handleSave} className="bg-card rounded-xl border border-border p-6 space-y-5">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">Sueldo mínimo (S/) *</label>
            <input type="number" step="0.01" required
              value={form.sueldo_minimo}
              onChange={e => setForm({...form, sueldo_minimo: e.target.value})}
              className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500"
              data-testid="input-sueldo-minimo" />
            <p className="text-[11px] text-muted-foreground mt-1">Base para la asignación familiar.</p>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">Horas quincena default *</label>
            <input type="number" required
              value={form.horas_quincena_default}
              onChange={e => setForm({...form, horas_quincena_default: e.target.value})}
              className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500"
              data-testid="input-horas-default" />
            <p className="text-[11px] text-muted-foreground mt-1">Sugerido: 120 (15 días × 8 h). Editable por trabajador.</p>
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">% Asignación familiar *</label>
            <input type="number" step="0.01" required
              value={form.asignacion_familiar_pct}
              onChange={e => setForm({...form, asignacion_familiar_pct: e.target.value})}
              className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background font-mono focus:outline-none focus:ring-2 focus:ring-emerald-500"
              data-testid="input-asig-fam-pct" />
            <p className="text-[11px] text-muted-foreground mt-1">Ley peruana: 10% del sueldo mínimo.</p>
          </div>
        </div>

        <div className="bg-blue-500/5 border border-blue-500/20 rounded-md p-3 flex items-start gap-2">
          <Info size={16} className="text-blue-600 mt-0.5 shrink-0" />
          <div className="text-[12px] text-foreground">
            <div className="font-medium mb-1">Con los valores actuales:</div>
            <div>Asignación familiar por trabajador = <strong>{fmt(asigFamMonto)}</strong></div>
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-2 border-t border-border">
          <button type="button" onClick={load}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-sm rounded-md border border-border hover:bg-muted">
            <RefreshCw size={14} /> Recargar
          </button>
          <button type="submit" disabled={saving}
            className="inline-flex items-center gap-1.5 bg-emerald-600 text-white px-4 py-2 text-sm font-medium rounded-md hover:bg-emerald-700 disabled:opacity-50"
            data-testid="save-ajustes">
            <Save size={14} /> {saving ? 'Guardando…' : 'Guardar ajustes'}
          </button>
        </div>
      </form>

      {/* Tabla de AFP vigentes (solo lectura por ahora) */}
      <div className="bg-card rounded-xl border border-border overflow-hidden">
        <div className="px-5 py-3 border-b border-border flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-foreground">AFPs vigentes</h2>
            <p className="text-[11px] text-muted-foreground">Tasas publicadas por la SBS. Se actualizan mensualmente.</p>
          </div>
          <span className="text-[11px] text-muted-foreground">Fuente: sbs.gob.pe</span>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-[11px] uppercase tracking-wider text-muted-foreground">
            <tr>
              <th className="text-left px-4 py-2">AFP</th>
              <th className="text-right px-4 py-2">Aporte oblig.</th>
              <th className="text-right px-4 py-2">Prima seguro</th>
              <th className="text-right px-4 py-2">Comisión flujo</th>
              <th className="text-right px-4 py-2">Comisión saldo</th>
              <th className="text-right px-4 py-2">RMA</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {afps.map(a => (
              <tr key={a.id}>
                <td className="px-4 py-2 font-medium">{a.nombre}</td>
                <td className="px-4 py-2 text-right font-mono text-xs">{a.aporte_obligatorio_pct}%</td>
                <td className="px-4 py-2 text-right font-mono text-xs">{a.prima_seguro_pct}%</td>
                <td className="px-4 py-2 text-right font-mono text-xs">{a.comision_flujo_pct}%</td>
                <td className="px-4 py-2 text-right font-mono text-xs">{a.comision_saldo_pct}%</td>
                <td className="px-4 py-2 text-right font-mono text-xs">{fmt(a.remuneracion_maxima_asegurable)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
