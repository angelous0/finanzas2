import React, { useState, useEffect, useCallback } from 'react';
import {
  Plus, Trash2, Eye, X, FileSpreadsheet, Users, DollarSign,
  Pencil, ChevronRight, ChevronLeft, Check, CreditCard,
  Download, Calculator, Clock, AlertCircle, Undo2
} from 'lucide-react';
import { toast } from 'sonner';
import {
  getPlanillas, createPlanilla, updatePlanilla, deletePlanilla,
  getTrabajadoresPlanilla, getLineasNegocio, getResumenPlanillas,
  getUnidadesInternas, calcularPlanilla, aprobarPlanilla, pagarPlanilla,
  anularPagoPlanilla,
} from '../services/api';
import { useEmpresa } from '../context/EmpresaContext';

const fmt = (v) => {
  const n = parseFloat(v) || 0;
  return `S/ ${n.toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};
const fmtDate = (d) => {
  if (!d) return '-';
  const dt = new Date(d + 'T00:00:00');
  return dt.toLocaleDateString('es-PE', { day: '2-digit', month: '2-digit', year: 'numeric' });
};

const TIPOS_PLANILLA = [
  { value: 'quincenal', label: 'Quincenal' },
  { value: 'mensual', label: 'Mensual' },
  { value: 'semanal', label: 'Semanal' },
  { value: 'gratificacion', label: 'Gratificacion' },
];

const ESTADO_BADGE = {
  borrador: 'bg-gray-500/10 text-gray-600',
  aprobado: 'bg-blue-500/10 text-blue-600',
  pagado: 'bg-emerald-500/10 text-emerald-600',
  pagada: 'bg-emerald-500/10 text-emerald-600',
  anulado: 'bg-red-500/10 text-red-600',
};

export default function Planilla() {
  const { empresaActual } = useEmpresa();
  const [view, setView] = useState('list'); // list | wizard | detail
  const [planillas, setPlanillas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [resumen, setResumen] = useState(null);
  const [filtroTipo, setFiltroTipo] = useState('');
  const [filtroEstado, setFiltroEstado] = useState('');

  // Wizard state
  const [wizardStep, setWizardStep] = useState(1);
  const [wizardForm, setWizardForm] = useState({ fecha_inicio: '', fecha_fin: '', tipo: 'quincenal' });
  const [preview, setPreview] = useState(null);
  const [calculating, setCalculating] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Detail state
  const [selectedPlanilla, setSelectedPlanilla] = useState(null);

  // Pago modal state
  const [showPagoModal, setShowPagoModal] = useState(false);
  const [pagoBreakdown, setPagoBreakdown] = useState([]);
  const [pagando, setPagando] = useState(false);
  const [pagoResult, setPagoResult] = useState(null); // success feedback

  // Master data
  const [trabajadores, setTrabajadores] = useState([]);
  const [lineasNegocio, setLineasNegocio] = useState([]);
  const [unidadesInternas, setUnidadesInternas] = useState([]);

  const loadData = useCallback(async () => {
    if (!empresaActual) return;
    setLoading(true);
    try {
      const params = {};
      if (filtroTipo) params.tipo = filtroTipo;
      if (filtroEstado) params.estado = filtroEstado;
      const [plRes, trRes, lnRes, resRes, uiRes] = await Promise.all([
        getPlanillas(params),
        getTrabajadoresPlanilla(),
        getLineasNegocio(),
        getResumenPlanillas({}),
        getUnidadesInternas(),
      ]);
      setPlanillas(plRes.data);
      setTrabajadores(trRes.data);
      setLineasNegocio(lnRes.data);
      setResumen(resRes.data);
      setUnidadesInternas(uiRes.data);
    } catch {
      toast.error('Error cargando planillas');
    } finally {
      setLoading(false);
    }
  }, [empresaActual, filtroTipo, filtroEstado]);

  useEffect(() => { loadData(); }, [loadData]);

  // ── WIZARD HANDLERS ──

  const startWizard = () => {
    setWizardStep(1);
    setWizardForm({ fecha_inicio: '', fecha_fin: '', tipo: 'quincenal' });
    setPreview(null);
    setView('wizard');
  };

  const handleCalculate = async () => {
    if (!wizardForm.fecha_inicio || !wizardForm.fecha_fin) {
      toast.error('Selecciona fecha inicio y fin');
      return;
    }
    setCalculating(true);
    try {
      const res = await calcularPlanilla({
        fecha_inicio: wizardForm.fecha_inicio,
        fecha_fin: wizardForm.fecha_fin,
        tipo: wizardForm.tipo,
      });
      setPreview(res.data);
      setWizardStep(2);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error calculando planilla');
    } finally {
      setCalculating(false);
    }
  };

  const updatePreviewLine = (idx, field, value) => {
    setPreview(prev => {
      const lineas = [...prev.lineas];
      lineas[idx] = { ...lineas[idx], [field]: parseFloat(value) || 0 };
      const l = lineas[idx];
      if (['salario_base', 'bonificaciones', 'adelantos', 'otros_descuentos'].includes(field)) {
        lineas[idx].neto_pagar = (l.salario_base || 0) + (l.bonificaciones || 0) - (l.adelantos || 0) - (l.otros_descuentos || 0);
      }
      return {
        ...prev,
        lineas,
        total_bruto: lineas.reduce((s, l) => s + (l.salario_base || 0) + (l.bonificaciones || 0), 0),
        total_adelantos: lineas.reduce((s, l) => s + (l.adelantos || 0), 0),
        total_neto: lineas.reduce((s, l) => s + (l.neto_pagar || 0), 0),
      };
    });
  };

  const handleCreateFromPreview = async () => {
    if (!preview) return;
    setSubmitting(true);
    try {
      const payload = {
        periodo: preview.periodo,
        tipo: preview.tipo,
        fecha_inicio: preview.fecha_inicio,
        fecha_fin: preview.fecha_fin,
        lineas: preview.lineas.map(l => ({
          trabajador_id: l.trabajador_id,
          trabajador_nombre: l.trabajador_nombre,
          tipo_trabajador: l.tipo_trabajador,
          unidad_interna_id: l.unidad_interna_id || null,
          salario_base: l.salario_base || 0,
          bonificaciones: l.bonificaciones || 0,
          adelantos: l.adelantos || 0,
          otros_descuentos: l.otros_descuentos || 0,
          neto_pagar: l.neto_pagar || 0,
        })),
      };
      await createPlanilla(payload);
      toast.success('Planilla creada exitosamente');
      setView('list');
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error creando planilla');
    } finally {
      setSubmitting(false);
    }
  };

  // ── DETAIL HANDLERS ──

  const openDetail = (p) => {
    setSelectedPlanilla(p);
    setView('detail');
  };

  const handleAprobar = async (id) => {
    try {
      await aprobarPlanilla(id);
      toast.success('Planilla aprobada');
      loadData();
      setView('list');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error aprobando');
    }
  };

  const openPagoModal = (planilla) => {
    // Build breakdown by unidad_interna from planilla lineas
    const byUnit = {};
    (planilla.lineas || []).forEach(l => {
      const uiId = l.unidad_interna_id || 'sin_unidad';
      if (!byUnit[uiId]) {
        byUnit[uiId] = { unidad_interna_id: l.unidad_interna_id, nombre: l.unidad_interna_nombre || 'Sin unidad', total: 0, trabajadores: [] };
      }
      byUnit[uiId].total += parseFloat(l.neto_pagar) || 0;
      byUnit[uiId].trabajadores.push(l.trabajador_nombre);
    });
    setPagoBreakdown(Object.values(byUnit));
    setPagoResult(null);
    setShowPagoModal(true);
  };

  const handlePagar = async (id) => {
    setPagando(true);
    try {
      const res = await pagarPlanilla(id);
      const data = res.data;
      setPagoResult(data);
      toast.success('Planilla pagada exitosamente');
      loadData();
      // Update selectedPlanilla to reflect new state
      setSelectedPlanilla(prev => prev ? { ...prev, estado: 'pagada', fecha_pago: new Date().toISOString().slice(0, 10) } : prev);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error pagando planilla');
      setShowPagoModal(false);
    } finally {
      setPagando(false);
    }
  };

  const handleAnularPago = async (id) => {
    if (!window.confirm('¿Está seguro de anular el pago? Se revertirán los movimientos EGRESO en las cuentas ficticias.')) return;
    try {
      const res = await anularPagoPlanilla(id);
      const data = res.data;
      toast.success('Pago anulado exitosamente');
      if (data.reversas?.length > 0) {
        const resumen = data.reversas.map(r => `${r.cuenta_nombre}: +${fmt(r.monto_revertido)} → Saldo: ${fmt(r.nuevo_saldo)}`).join('\n');
        toast.info(`Saldos restaurados:\n${resumen}`, { duration: 6000 });
      }
      loadData();
      setSelectedPlanilla(prev => prev ? { ...prev, estado: 'aprobado', fecha_pago: null } : prev);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error anulando pago');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Eliminar esta planilla?')) return;
    try {
      await deletePlanilla(id);
      toast.success('Planilla eliminada');
      loadData();
      setView('list');
    } catch {
      toast.error('Error eliminando');
    }
  };

  const exportExcel = (planilla) => {
    const headers = ['Trabajador', 'Tipo', 'Unidad', 'Salario Base', 'Bonificaciones', 'Adelantos', 'Otros Desc.', 'Neto'];
    const rows = (planilla.lineas || []).map(l => [
      l.trabajador_nombre, l.tipo_trabajador, l.unidad_interna_nombre || '',
      l.salario_base, l.bonificaciones, l.adelantos, l.otros_descuentos, l.neto_pagar,
    ]);
    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `planilla_${planilla.periodo || planilla.id}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!empresaActual) return null;

  // ══════════════════════════════════════
  // VIEW: WIZARD
  // ══════════════════════════════════════
  if (view === 'wizard') {
    return (
      <div className="max-w-[1100px] space-y-6" data-testid="planilla-wizard">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-foreground">Nueva Planilla</h1>
            <p className="text-sm text-muted-foreground mt-0.5">Paso {wizardStep} de 3</p>
          </div>
          <button
            className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-medium text-foreground hover:bg-muted transition-colors"
            onClick={() => setView('list')}
          >
            <X size={14} /> Cancelar
          </button>
        </div>

        {/* Steps indicator */}
        <div className="flex items-center gap-2">
          {[
            { n: 1, label: 'Periodo' },
            { n: 2, label: 'Preview' },
            { n: 3, label: 'Confirmar' },
          ].map((s, i) => (
            <React.Fragment key={s.n}>
              {i > 0 && <div className={`flex-1 h-0.5 ${wizardStep > i ? 'bg-emerald-600' : 'bg-border'}`} />}
              <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                wizardStep === s.n ? 'bg-emerald-600 text-white' :
                wizardStep > s.n ? 'bg-emerald-600/10 text-emerald-600' :
                'bg-muted text-muted-foreground'
              }`}>
                <span className="w-5 h-5 flex items-center justify-center rounded-full text-xs">
                  {wizardStep > s.n ? <Check size={12} /> : s.n}
                </span>
                <span className="hidden sm:inline">{s.label}</span>
              </div>
            </React.Fragment>
          ))}
        </div>

        {/* Step 1: Select period */}
        {wizardStep === 1 && (
          <div className="rounded-xl border border-border bg-card p-6 shadow-sm space-y-5">
            <h2 className="text-base font-semibold text-foreground">Seleccionar periodo y tipo</h2>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">Fecha Inicio *</label>
                <input
                  type="date"
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600"
                  value={wizardForm.fecha_inicio}
                  onChange={e => setWizardForm(f => ({ ...f, fecha_inicio: e.target.value }))}
                  data-testid="wizard-fecha-inicio"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">Fecha Fin *</label>
                <input
                  type="date"
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600"
                  value={wizardForm.fecha_fin}
                  onChange={e => setWizardForm(f => ({ ...f, fecha_fin: e.target.value }))}
                  data-testid="wizard-fecha-fin"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1.5">Tipo</label>
                <select
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600"
                  value={wizardForm.tipo}
                  onChange={e => setWizardForm(f => ({ ...f, tipo: e.target.value }))}
                  data-testid="wizard-tipo"
                >
                  {TIPOS_PLANILLA.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
            </div>

            <div className="flex justify-end">
              <button
                className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 transition-colors disabled:opacity-50"
                onClick={handleCalculate}
                disabled={calculating}
                data-testid="wizard-calcular-btn"
              >
                {calculating ? (
                  <>
                    <Calculator size={14} className="animate-spin" />
                    Calculando...
                  </>
                ) : (
                  <>
                    <Calculator size={14} />
                    Calcular Planilla
                    <ChevronRight size={14} />
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Preview */}
        {wizardStep === 2 && preview && (
          <div className="space-y-4">
            {/* Summary KPIs */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <MiniKpi label="Trabajadores" value={preview.num_trabajadores} icon={Users} color="blue" />
              <MiniKpi label="Total Bruto" value={fmt(preview.total_bruto)} icon={DollarSign} color="amber" />
              <MiniKpi label="Adelantos" value={fmt(preview.total_adelantos)} icon={AlertCircle} color="red" />
              <MiniKpi label="Total Neto" value={fmt(preview.total_neto)} icon={DollarSign} color="emerald" />
            </div>

            {/* Editable table */}
            <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
              <div className="px-5 py-3 border-b border-border bg-muted/30">
                <h2 className="text-sm font-semibold text-foreground">
                  Preview: {preview.periodo} ({TIPOS_PLANILLA.find(t => t.value === preview.tipo)?.label})
                </h2>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border bg-muted/20">
                      <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase">Trabajador</th>
                      <th className="text-left px-3 py-2.5 text-xs font-medium text-muted-foreground uppercase">Tipo</th>
                      <th className="text-left px-3 py-2.5 text-xs font-medium text-muted-foreground uppercase">Unidad</th>
                      <th className="text-center px-3 py-2.5 text-xs font-medium text-muted-foreground uppercase">Cant.</th>
                      <th className="text-right px-3 py-2.5 text-xs font-medium text-muted-foreground uppercase">Salario</th>
                      <th className="text-right px-3 py-2.5 text-xs font-medium text-muted-foreground uppercase">Bonif.</th>
                      <th className="text-right px-3 py-2.5 text-xs font-medium text-muted-foreground uppercase">Adelantos</th>
                      <th className="text-right px-3 py-2.5 text-xs font-medium text-muted-foreground uppercase">Otros</th>
                      <th className="text-right px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase">Neto</th>
                      <th className="text-center px-3 py-2.5 text-xs font-medium text-muted-foreground uppercase">Ult. Mov.</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {preview.lineas.map((l, idx) => (
                      <tr key={idx} className="hover:bg-muted/20 transition-colors">
                        <td className="px-4 py-2 font-medium text-foreground">{l.trabajador_nombre}</td>
                        <td className="px-3 py-2">
                          <span className="inline-flex rounded-full bg-blue-500/10 text-blue-600 px-2 py-0.5 text-xs font-medium">
                            {l.tipo_trabajador || '-'}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-muted-foreground text-xs">{l.unidad_interna_nombre || '-'}</td>
                        <td className="px-3 py-2 text-center text-muted-foreground">{l.cantidad_total || 0}</td>
                        <td className="px-3 py-2">
                          <input
                            type="number" step="0.01" min="0"
                            className="w-24 rounded border border-border bg-background px-2 py-1 text-sm text-right focus:outline-none focus:ring-1 focus:ring-emerald-600"
                            value={l.salario_base || 0}
                            onChange={e => updatePreviewLine(idx, 'salario_base', e.target.value)}
                          />
                        </td>
                        <td className="px-3 py-2">
                          <input
                            type="number" step="0.01" min="0"
                            className="w-20 rounded border border-border bg-background px-2 py-1 text-sm text-right focus:outline-none focus:ring-1 focus:ring-emerald-600"
                            value={l.bonificaciones || 0}
                            onChange={e => updatePreviewLine(idx, 'bonificaciones', e.target.value)}
                          />
                        </td>
                        <td className="px-3 py-2">
                          <input
                            type="number" step="0.01" min="0"
                            className="w-20 rounded border border-border bg-background px-2 py-1 text-sm text-right focus:outline-none focus:ring-1 focus:ring-emerald-600"
                            value={l.adelantos || 0}
                            onChange={e => updatePreviewLine(idx, 'adelantos', e.target.value)}
                          />
                        </td>
                        <td className="px-3 py-2">
                          <input
                            type="number" step="0.01" min="0"
                            className="w-20 rounded border border-border bg-background px-2 py-1 text-sm text-right focus:outline-none focus:ring-1 focus:ring-emerald-600"
                            value={l.otros_descuentos || 0}
                            onChange={e => updatePreviewLine(idx, 'otros_descuentos', e.target.value)}
                          />
                        </td>
                        <td className="px-4 py-2 text-right font-bold text-emerald-600">{fmt(l.neto_pagar)}</td>
                        <td className="px-3 py-2 text-center">
                          {l.ultimo_movimiento ? (
                            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                              <Clock size={10} />
                              {fmtDate(l.ultimo_movimiento)}
                            </span>
                          ) : (
                            <span className="text-xs text-muted-foreground/50">-</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {preview.lineas.length === 0 && (
                <div className="px-5 py-8 text-center text-muted-foreground text-sm">
                  No se encontraron movimientos de produccion en este periodo
                </div>
              )}
            </div>

            {/* Navigation */}
            <div className="flex items-center justify-between">
              <button
                className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-medium text-foreground hover:bg-muted transition-colors"
                onClick={() => setWizardStep(1)}
              >
                <ChevronLeft size={14} /> Atras
              </button>
              <button
                className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 transition-colors disabled:opacity-50"
                onClick={() => setWizardStep(3)}
                disabled={preview.lineas.length === 0}
              >
                Confirmar <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Confirm */}
        {wizardStep === 3 && preview && (
          <div className="rounded-xl border border-border bg-card p-6 shadow-sm space-y-5">
            <h2 className="text-base font-semibold text-foreground">Confirmar y crear planilla</h2>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">Periodo:</span>
                <div className="font-semibold">{preview.periodo}</div>
              </div>
              <div>
                <span className="text-muted-foreground">Tipo:</span>
                <div className="font-semibold">{TIPOS_PLANILLA.find(t => t.value === preview.tipo)?.label}</div>
              </div>
              <div>
                <span className="text-muted-foreground">Trabajadores:</span>
                <div className="font-semibold">{preview.num_trabajadores}</div>
              </div>
              <div>
                <span className="text-muted-foreground">Total Neto:</span>
                <div className="font-bold text-emerald-600 text-lg">{fmt(preview.total_neto)}</div>
              </div>
            </div>

            <div className="rounded-lg bg-amber-500/10 border border-amber-500/20 p-3 text-sm text-amber-700 dark:text-amber-400">
              <AlertCircle size={14} className="inline mr-1.5" />
              La planilla se creara en estado <strong>borrador</strong>. Podras revisarla y aprobarla despues.
            </div>

            <div className="flex items-center justify-between">
              <button
                className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-medium text-foreground hover:bg-muted transition-colors"
                onClick={() => setWizardStep(2)}
              >
                <ChevronLeft size={14} /> Atras
              </button>
              <button
                className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-emerald-700 transition-colors disabled:opacity-50"
                onClick={handleCreateFromPreview}
                disabled={submitting}
                data-testid="wizard-confirmar-btn"
              >
                {submitting ? 'Creando...' : (
                  <><Check size={14} /> Crear Planilla</>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ══════════════════════════════════════
  // VIEW: DETAIL
  // ══════════════════════════════════════
  if (view === 'detail' && selectedPlanilla) {
    const p = selectedPlanilla;
    return (
      <div className="max-w-[1100px] space-y-6" data-testid="planilla-detail">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-foreground">Planilla: {p.periodo}</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {fmtDate(p.fecha_inicio)} — {fmtDate(p.fecha_fin)}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-medium text-foreground hover:bg-muted transition-colors"
              onClick={() => exportExcel(p)}
            >
              <Download size={14} /> Exportar CSV
            </button>
            <button
              className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-medium text-foreground hover:bg-muted transition-colors"
              onClick={() => setView('list')}
            >
              <ChevronLeft size={14} /> Volver
            </button>
          </div>
        </div>

        {/* KPIs */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <MiniKpi label="Total Bruto" value={fmt(p.total_bruto)} icon={DollarSign} color="amber" />
          <MiniKpi label="Adelantos" value={fmt(p.total_adelantos)} icon={AlertCircle} color="red" />
          <MiniKpi label="Total Neto" value={fmt(p.total_neto)} icon={DollarSign} color="emerald" />
          <MiniKpi label="Estado" value={p.estado} icon={FileSpreadsheet} color={
            (p.estado === 'pagado' || p.estado === 'pagada') ? 'emerald' : p.estado === 'aprobado' ? 'blue' : 'gray'
          } />
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          {p.estado === 'borrador' && (
            <>
              <button
                className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
                onClick={() => handleAprobar(p.id)}
              >
                <Check size={14} /> Aprobar
              </button>
              <button
                className="inline-flex items-center gap-2 rounded-lg bg-red-600/10 text-red-600 border border-red-600/20 px-3 py-2 text-sm font-medium hover:bg-red-600/20 transition-colors"
                onClick={() => handleDelete(p.id)}
              >
                <Trash2 size={14} /> Eliminar
              </button>
            </>
          )}
          {p.estado === 'aprobado' && (
            <button
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 transition-colors"
              onClick={() => openPagoModal(p)}
            >
              <CreditCard size={14} /> Pagar Planilla
            </button>
          )}
          {p.estado === 'pagada' && (
            <button
              className="inline-flex items-center gap-2 rounded-lg bg-amber-600/10 text-amber-600 border border-amber-600/20 px-3 py-2 text-sm font-medium hover:bg-amber-600/20 transition-colors"
              onClick={() => handleAnularPago(p.id)}
            >
              <Undo2 size={14} /> Anular Pago
            </button>
          )}
        </div>

        {/* Fecha de pago info */}
        {p.estado === 'pagada' && p.fecha_pago && (
          <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/20 p-3 text-sm text-emerald-700 dark:text-emerald-400">
            <CreditCard size={14} className="inline mr-1.5" />
            Pagada el <strong>{fmtDate(p.fecha_pago)}</strong> — Los montos fueron descontados de las cuentas ficticias por unidad interna.
          </div>
        )}

        {/* Pago Confirmation Modal */}
        {showPagoModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => !pagando && !pagoResult && setShowPagoModal(false)}>
            <div className="bg-card border border-border rounded-xl shadow-lg w-full max-w-lg mx-4 p-6 space-y-4" onClick={e => e.stopPropagation()}>
              {!pagoResult ? (
                <>
                  <h3 className="text-lg font-bold text-foreground">Confirmar Pago de Planilla</h3>
                  <p className="text-sm text-muted-foreground">
                    Se crearán movimientos <strong>EGRESO</strong> en las cuentas ficticias de cada unidad interna:
                  </p>
                  <div className="rounded-lg border border-border overflow-hidden">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-muted/30 border-b border-border">
                          <th className="text-left px-4 py-2 text-xs font-medium text-muted-foreground uppercase">Unidad Interna</th>
                          <th className="text-center px-3 py-2 text-xs font-medium text-muted-foreground uppercase">Trab.</th>
                          <th className="text-right px-4 py-2 text-xs font-medium text-muted-foreground uppercase">Monto EGRESO</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border">
                        {pagoBreakdown.map((b, i) => (
                          <tr key={i}>
                            <td className="px-4 py-2 font-medium text-foreground">{b.nombre}</td>
                            <td className="px-3 py-2 text-center text-muted-foreground">{b.trabajadores.length}</td>
                            <td className="px-4 py-2 text-right font-semibold text-red-600">{fmt(b.total)}</td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr className="bg-muted/50 border-t-2 border-border font-bold">
                          <td colSpan={2} className="px-4 py-2 text-foreground">Total</td>
                          <td className="px-4 py-2 text-right text-red-600">
                            {fmt(pagoBreakdown.reduce((s, b) => s + b.total, 0))}
                          </td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                  <div className="rounded-lg bg-amber-500/10 border border-amber-500/20 p-3 text-sm text-amber-700 dark:text-amber-400">
                    <AlertCircle size={14} className="inline mr-1.5" />
                    Esta acción descontará los montos de las cuentas ficticias. Podrás anular el pago después si es necesario.
                  </div>
                  <div className="flex justify-end gap-2 pt-2">
                    <button
                      className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-muted transition-colors"
                      onClick={() => setShowPagoModal(false)}
                      disabled={pagando}
                    >
                      Cancelar
                    </button>
                    <button
                      className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 transition-colors disabled:opacity-50"
                      onClick={() => handlePagar(p.id)}
                      disabled={pagando}
                    >
                      {pagando ? 'Procesando...' : 'Confirmar Pago'}
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <h3 className="text-lg font-bold text-emerald-600 flex items-center gap-2">
                    <Check size={20} /> Planilla Pagada Exitosamente
                  </h3>
                  <p className="text-sm text-muted-foreground">Movimientos EGRESO creados en cuentas ficticias:</p>
                  <div className="rounded-lg border border-border overflow-hidden">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-muted/30 border-b border-border">
                          <th className="text-left px-4 py-2 text-xs font-medium text-muted-foreground uppercase">Cuenta</th>
                          <th className="text-right px-3 py-2 text-xs font-medium text-muted-foreground uppercase">Egreso</th>
                          <th className="text-right px-4 py-2 text-xs font-medium text-muted-foreground uppercase">Nuevo Saldo</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border">
                        {(pagoResult.movimientos_creados || []).map((m, i) => (
                          <tr key={i}>
                            <td className="px-4 py-2 font-medium text-foreground">{m.cuenta_nombre}</td>
                            <td className="px-3 py-2 text-right text-red-600">-{fmt(m.monto)}</td>
                            <td className="px-4 py-2 text-right font-semibold text-foreground">{fmt(m.nuevo_saldo)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {pagoResult.monto_sin_unidad > 0 && (
                    <div className="rounded-lg bg-amber-500/10 border border-amber-500/20 p-3 text-sm text-amber-700 dark:text-amber-400">
                      <AlertCircle size={14} className="inline mr-1.5" />
                      {fmt(pagoResult.monto_sin_unidad)} de trabajadores sin unidad interna no generó movimiento.
                    </div>
                  )}
                  <div className="flex justify-end pt-2">
                    <button
                      className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 transition-colors"
                      onClick={() => { setShowPagoModal(false); setPagoResult(null); }}
                    >
                      Cerrar
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* Detail table */}
        <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="text-left px-5 py-3 text-xs font-medium text-muted-foreground uppercase">Trabajador</th>
                  <th className="text-left px-3 py-3 text-xs font-medium text-muted-foreground uppercase">Tipo</th>
                  <th className="text-left px-3 py-3 text-xs font-medium text-muted-foreground uppercase">Unidad</th>
                  <th className="text-right px-3 py-3 text-xs font-medium text-muted-foreground uppercase">Salario</th>
                  <th className="text-right px-3 py-3 text-xs font-medium text-muted-foreground uppercase">Bonif.</th>
                  <th className="text-right px-3 py-3 text-xs font-medium text-muted-foreground uppercase">Adelantos</th>
                  <th className="text-right px-3 py-3 text-xs font-medium text-muted-foreground uppercase">Otros Desc.</th>
                  <th className="text-right px-5 py-3 text-xs font-medium text-muted-foreground uppercase">Neto</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(p.lineas || []).map((l, i) => (
                  <tr key={i} className="hover:bg-muted/20 transition-colors">
                    <td className="px-5 py-3 font-medium text-foreground">{l.trabajador_nombre || '-'}</td>
                    <td className="px-3 py-3">
                      <span className="inline-flex rounded-full bg-blue-500/10 text-blue-600 px-2 py-0.5 text-xs font-medium">
                        {l.tipo_trabajador || '-'}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-muted-foreground text-xs">{l.unidad_interna_nombre || '-'}</td>
                    <td className="px-3 py-3 text-right">{fmt(l.salario_base)}</td>
                    <td className="px-3 py-3 text-right">{fmt(l.bonificaciones)}</td>
                    <td className="px-3 py-3 text-right text-red-600">{fmt(l.adelantos)}</td>
                    <td className="px-3 py-3 text-right text-red-600">{fmt(l.otros_descuentos)}</td>
                    <td className="px-5 py-3 text-right font-bold text-emerald-600">{fmt(l.neto_pagar)}</td>
                  </tr>
                ))}
              </tbody>
              {(p.lineas || []).length > 0 && (
                <tfoot>
                  <tr className="bg-muted/50 font-semibold border-t-2 border-border">
                    <td colSpan={3} className="px-5 py-3 text-foreground">Total</td>
                    <td className="px-3 py-3 text-right">{fmt((p.lineas || []).reduce((s, l) => s + parseFloat(l.salario_base || 0), 0))}</td>
                    <td className="px-3 py-3 text-right">{fmt((p.lineas || []).reduce((s, l) => s + parseFloat(l.bonificaciones || 0), 0))}</td>
                    <td className="px-3 py-3 text-right text-red-600">{fmt((p.lineas || []).reduce((s, l) => s + parseFloat(l.adelantos || 0), 0))}</td>
                    <td className="px-3 py-3 text-right text-red-600">{fmt((p.lineas || []).reduce((s, l) => s + parseFloat(l.otros_descuentos || 0), 0))}</td>
                    <td className="px-5 py-3 text-right font-bold text-emerald-600">{fmt(p.total_neto)}</td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </div>
      </div>
    );
  }

  // ══════════════════════════════════════
  // VIEW: LIST
  // ══════════════════════════════════════
  return (
    <div className="max-w-[1100px] space-y-6" data-testid="planilla-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground tracking-tight">Planilla</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Gestiona el pago de trabajadores por periodo</p>
        </div>
        <button
          className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-emerald-700 transition-colors shadow-sm"
          onClick={startWizard}
          data-testid="create-planilla-btn"
        >
          <Plus size={16} /> Nueva Planilla
        </button>
      </div>

      {/* Summary Cards */}
      {resumen?.totales && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <MiniKpi label="Planillas" value={resumen.totales.num_planillas} icon={FileSpreadsheet} color="violet" />
          <MiniKpi label="Total Bruto" value={fmt(resumen.totales.total_bruto)} icon={DollarSign} color="amber" />
          <MiniKpi label="Total Neto" value={fmt(resumen.totales.total_neto)} icon={DollarSign} color="emerald" />
          <MiniKpi label="Trabajadores" value={trabajadores.length} icon={Users} color="blue" />
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <select
          className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20"
          value={filtroTipo}
          onChange={e => setFiltroTipo(e.target.value)}
          data-testid="filter-tipo"
        >
          <option value="">Todos los tipos</option>
          {TIPOS_PLANILLA.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
        <select
          className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20"
          value={filtroEstado}
          onChange={e => setFiltroEstado(e.target.value)}
          data-testid="filter-estado"
        >
          <option value="">Todos los estados</option>
          <option value="borrador">Borrador</option>
          <option value="aprobado">Aprobado</option>
          <option value="pagado">Pagado</option>
        </select>
      </div>

      {/* Table or empty state */}
      {loading ? (
        <div className="flex items-center justify-center py-12 text-muted-foreground text-sm">Cargando...</div>
      ) : planillas.length === 0 ? (
        <div className="rounded-xl border border-border bg-card p-8 text-center shadow-sm">
          <FileSpreadsheet size={40} className="mx-auto mb-3 text-muted-foreground/30" />
          <p className="text-muted-foreground text-sm mb-3">No hay planillas registradas</p>
          <button
            className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 transition-colors"
            onClick={startWizard}
          >
            <Plus size={14} /> Crear primera planilla
          </button>
        </div>
      ) : (
        <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="planillas-table">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="text-left px-5 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Periodo</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Tipo</th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Fecha</th>
                  <th className="text-center px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Trab.</th>
                  <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Total Neto</th>
                  <th className="text-center px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">Estado</th>
                  <th className="text-center px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider w-28">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {planillas.map(p => (
                  <tr key={p.id} className="hover:bg-muted/30 transition-colors group" data-testid={`planilla-row-${p.id}`}>
                    <td className="px-5 py-3 font-medium text-foreground">{p.periodo}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex rounded-full bg-violet-500/10 text-violet-600 px-2.5 py-0.5 text-xs font-medium">
                        {TIPOS_PLANILLA.find(t => t.value === p.tipo)?.label || p.tipo || '-'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground text-xs">
                      {fmtDate(p.fecha_inicio)} — {fmtDate(p.fecha_fin)}
                    </td>
                    <td className="px-4 py-3 text-center text-muted-foreground">{p.lineas?.length || 0}</td>
                    <td className="px-4 py-3 text-right font-semibold text-foreground">{fmt(p.total_neto)}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${ESTADO_BADGE[p.estado] || ESTADO_BADGE.borrador}`}>
                        {p.estado || 'borrador'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-1">
                        <button
                          className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                          onClick={() => openDetail(p)}
                          title="Ver detalle"
                        >
                          <Eye size={14} />
                        </button>
                        {p.estado === 'borrador' && (
                          <button
                            className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-red-500/10 text-muted-foreground hover:text-red-600 transition-colors"
                            onClick={() => handleDelete(p.id)}
                            title="Eliminar"
                          >
                            <Trash2 size={14} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function MiniKpi({ label, value, icon: Icon, color }) {
  const colorMap = {
    emerald: 'bg-emerald-500/10 text-emerald-600',
    blue: 'bg-blue-500/10 text-blue-600',
    amber: 'bg-amber-500/10 text-amber-600',
    red: 'bg-red-500/10 text-red-600',
    violet: 'bg-violet-500/10 text-violet-600',
    gray: 'bg-gray-500/10 text-gray-600',
  };
  const cls = colorMap[color] || colorMap.gray;

  return (
    <div className="rounded-xl border border-border bg-card px-4 py-3 shadow-sm">
      <div className="flex items-center gap-3">
        <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${cls}`}>
          <Icon size={18} />
        </div>
        <div>
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="text-base font-bold text-foreground">{value}</p>
        </div>
      </div>
    </div>
  );
}
