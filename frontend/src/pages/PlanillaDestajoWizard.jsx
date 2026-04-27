import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ChevronLeft, ChevronRight, Calculator, Calendar, X, Check,
  AlertTriangle, Save, CreditCard, Plus, Trash2, ArrowLeft,
  RotateCcw, Scissors, ChevronDown, ChevronUp,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  calcularPreviewPlanillaDestajo, createPlanillaDestajo, updatePlanillaDestajo,
  getPlanillaDestajo, aprobarPlanillaDestajo,
  pagarDetalleDestajo, anularPagoDetalleDestajo,
  getCuentasFinancieras,
} from '../services/api';

const fmt = (v) => `S/ ${Number(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtDate = (d) => d ? new Date(d + (String(d).length <= 10 ? 'T00:00:00' : '')).toLocaleDateString('es-PE') : '—';
const firstOfMonthISO = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-01`; };
const lastOfMonthISO = () => {
  const d = new Date(); const last = new Date(d.getFullYear(), d.getMonth()+1, 0);
  return last.toISOString().slice(0, 10);
};

export default function PlanillaDestajoWizard() {
  const navigate = useNavigate();
  const { id } = useParams();
  const isEdit = !!id;

  const [step, setStep] = useState(1);
  const [fechaDesde, setFechaDesde] = useState(firstOfMonthISO());
  const [fechaHasta, setFechaHasta] = useState(lastOfMonthISO());
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [planillaId, setPlanillaId] = useState(isEdit ? parseInt(id) : null);
  const [estado, setEstado] = useState('borrador');
  const [notas, setNotas] = useState('');
  const [warnings, setWarnings] = useState([]);

  // Trabajadores con sus movimientos disponibles (preview) o ya persistidos (edit)
  // Estructura: [{ trabajador_id, nombre, unidad_interna_nombre, movimientos: [...], adelantos_pendientes: [...], adelantos_ids: [...], movimiento_ids: [...], detalle_id?, pagado_at?, monto_bruto, monto_adelantos, neto }]
  const [trabajadores, setTrabajadores] = useState([]);
  const [expandidos, setExpandidos] = useState({});   // {trabajador_id: true}

  // Cuentas + pagos (para modal)
  const [cuentas, setCuentas] = useState([]);
  const [pagos, setPagos] = useState([]);
  const [pagoModal, setPagoModal] = useState(null);       // { detalle }
  const [verPagosModal, setVerPagosModal] = useState(null); // { detalle }

  const cargarCuentasIfNeeded = async () => {
    if (cuentas.length > 0) return;
    try {
      const c = await getCuentasFinancieras();
      setCuentas((c.data || []).filter(x => x.activo !== false));
    } catch { /* */ }
  };

  const reload = async (pidArg) => {
    const pid = pidArg || planillaId;
    if (!pid) return;
    const r = await getPlanillaDestajo(pid);
    const p = r.data;
    setPlanillaId(p.id);
    setFechaDesde(String(p.fecha_desde).slice(0, 10));
    setFechaHasta(String(p.fecha_hasta).slice(0, 10));
    setEstado(p.estado);
    setNotas(p.notas || '');
    // Normalizar detalles → trabajadores, cada uno con sus movimientos ya vinculados
    const adelPorTrab = {};
    (p.adelantos_vinculados || []).forEach(a => {
      if (!adelPorTrab[a.trabajador_id]) adelPorTrab[a.trabajador_id] = [];
      adelPorTrab[a.trabajador_id].push(a);
    });
    const tr = (p.detalles || []).map(d => ({
      detalle_id: d.id,
      trabajador_id: d.trabajador_id,
      nombre: d.nombre,
      dni: d.dni,
      unidad_interna_id: d.unidad_interna_id,
      unidad_interna_nombre: d.unidad_interna_nombre,
      movimientos: (d.movimientos || []).map(m => ({
        movimiento_id: m.movimiento_id,
        n_corte: m.registro_n_corte,
        modelo_nombre: m.modelo_nombre,
        servicio_nombre: m.servicio_nombre,
        cantidad: parseInt(m.cantidad) || 0,
        tarifa_destajo: parseFloat(m.tarifa_destajo) || 0,
        // Al cargar desde DB no sabemos la tarifa default — usamos la persistida.
        // Si el user edita y vuelve a guardar, se re-persiste.
        tarifa_default: parseFloat(m.tarifa_destajo) || 0,
        importe: parseFloat(m.importe) || 0,
      })),
      movimiento_ids: (d.movimientos || []).map(m => m.movimiento_id),
      adelantos_pendientes: (adelPorTrab[d.trabajador_id] || []).map(a => ({
        id: a.id,
        fecha: a.fecha,
        monto: parseFloat(a.monto),
        motivo: a.motivo,
      })),
      adelantos_ids: (adelPorTrab[d.trabajador_id] || []).map(a => a.id),
      monto_bruto: parseFloat(d.monto_bruto) || 0,
      monto_adelantos: parseFloat(d.monto_adelantos) || 0,
      neto: parseFloat(d.neto) || 0,
      num_movimientos: parseInt(d.num_movimientos) || 0,
      prendas: parseInt(d.prendas) || 0,
      pagado_at: d.pagado_at,
      pagado_por: d.pagado_por,
      medios_pago_default: d.medios_pago_default || [],
    }));
    setTrabajadores(tr);
    setPagos(p.pagos || []);
    setWarnings([]);
    // Auto-expandir: en edit mostramos todo abierto
    const expandidosInit = {};
    tr.forEach(t => { expandidosInit[t.trabajador_id] = true; });
    setExpandidos(expandidosInit);
    setStep(2);
  };

  useEffect(() => {
    if (!isEdit) return;
    (async () => {
      setLoading(true);
      try {
        await reload(parseInt(id));
        await cargarCuentasIfNeeded();
      } catch { toast.error('Error cargando planilla'); }
      finally { setLoading(false); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEdit, id]);

  const handleCalcular = async () => {
    if (!fechaDesde || !fechaHasta) { toast.error('Elige el rango de fechas'); return; }
    if (fechaDesde > fechaHasta) { toast.error('fecha_desde > fecha_hasta'); return; }
    setLoading(true);
    try {
      const r = await calcularPreviewPlanillaDestajo({
        fecha_desde: fechaDesde, fecha_hasta: fechaHasta,
      });
      const data = r.data || {};
      setWarnings(data.warnings || []);
      // Pre-marcar SOLO los movimientos dentro del rango declarado.
      // Los de períodos anteriores (pendientes) aparecen pero desmarcados —
      // el usuario los marca si quiere incluirlos en esta planilla.
      const tr = (data.trabajadores || []).map(t => {
        const movsDentro = (t.movimientos || []).filter(m => m.dentro_rango);
        const movIdsPreSel = movsDentro.map(m => m.movimiento_id);
        const brutoInicial = movsDentro.reduce((s, m) => s + (m.importe || 0), 0);
        const prendasInicial = movsDentro.reduce((s, m) => s + (m.cantidad || 0), 0);
        return {
          trabajador_id: t.trabajador_id,
          nombre: t.nombre,
          dni: t.dni,
          unidad_interna_id: t.unidad_interna_id,
          unidad_interna_nombre: t.unidad_interna_nombre,
          tipo_pago: t.tipo_pago,
          movimientos: (t.movimientos || []).map(m => ({
            movimiento_id: m.movimiento_id,
            fecha: m.fecha,
            n_corte: m.n_corte,
            modelo_nombre: m.modelo_nombre,
            servicio_nombre: m.servicio_nombre,
            cantidad: m.cantidad,
            tarifa_destajo: m.tarifa_destajo,
            tarifa_default: m.tarifa_destajo,
            importe: m.importe,
            dentro_rango: !!m.dentro_rango,
          })),
          movimiento_ids: movIdsPreSel,
          movimientos_excluidos: t.movimientos_excluidos || [],
          num_pendientes_anteriores: t.num_pendientes_anteriores || 0,
          adelantos_pendientes: t.adelantos_pendientes || [],
          adelantos_ids: [],
          monto_bruto: +brutoInicial.toFixed(2),
          monto_adelantos: 0,
          neto: +brutoInicial.toFixed(2),
          num_movimientos: movIdsPreSel.length,
          prendas: prendasInicial,
        };
      });
      setTrabajadores(tr);
      // Auto-expandir a TODOS los trabajadores para que el usuario vea los movimientos de una
      const expandidosInit = {};
      tr.forEach(t => { expandidosInit[t.trabajador_id] = true; });
      setExpandidos(expandidosInit);
      setStep(2);
    } catch (e) {
      toast.error(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Error al calcular');
    } finally { setLoading(false); }
  };

  // Toggle movimiento incluido / excluido para un trabajador
  const toggleMov = (trabajador_id, movimiento_id) => {
    setTrabajadores(prev => prev.map(t => {
      if (t.trabajador_id !== trabajador_id) return t;
      const isOn = (t.movimiento_ids || []).includes(movimiento_id);
      const newIds = isOn
        ? t.movimiento_ids.filter(x => x !== movimiento_id)
        : [...t.movimiento_ids, movimiento_id];
      const bruto = t.movimientos
        .filter(m => newIds.includes(m.movimiento_id))
        .reduce((s, m) => s + (m.importe || 0), 0);
      const prendas = t.movimientos
        .filter(m => newIds.includes(m.movimiento_id))
        .reduce((s, m) => s + (m.cantidad || 0), 0);
      return {
        ...t,
        movimiento_ids: newIds,
        num_movimientos: newIds.length,
        prendas,
        monto_bruto: +bruto.toFixed(2),
        neto: +(bruto - (t.monto_adelantos || 0)).toFixed(2),
      };
    }));
  };

  // Editar tarifa destajo de un movimiento específico (override)
  const updateTarifaMov = (trabajador_id, movimiento_id, nueva_tarifa) => {
    setTrabajadores(prev => prev.map(t => {
      if (t.trabajador_id !== trabajador_id) return t;
      const tarifa = parseFloat(nueva_tarifa);
      const tarifaNum = isNaN(tarifa) || tarifa < 0 ? 0 : tarifa;
      const newMovs = t.movimientos.map(m => {
        if (m.movimiento_id !== movimiento_id) return m;
        return {
          ...m,
          tarifa_destajo: tarifaNum,
          importe: +((m.cantidad || 0) * tarifaNum).toFixed(2),
        };
      });
      const bruto = newMovs
        .filter(m => (t.movimiento_ids || []).includes(m.movimiento_id))
        .reduce((s, m) => s + (m.importe || 0), 0);
      return {
        ...t,
        movimientos: newMovs,
        monto_bruto: +bruto.toFixed(2),
        neto: +(bruto - (t.monto_adelantos || 0)).toFixed(2),
      };
    }));
  };

  // Restaurar tarifa al default del trabajador
  const resetTarifaMov = (trabajador_id, movimiento_id) => {
    setTrabajadores(prev => prev.map(t => {
      if (t.trabajador_id !== trabajador_id) return t;
      const newMovs = t.movimientos.map(m => {
        if (m.movimiento_id !== movimiento_id) return m;
        const tarifa = m.tarifa_default || 0;
        return {
          ...m,
          tarifa_destajo: tarifa,
          importe: +((m.cantidad || 0) * tarifa).toFixed(2),
        };
      });
      const bruto = newMovs
        .filter(m => (t.movimiento_ids || []).includes(m.movimiento_id))
        .reduce((s, m) => s + (m.importe || 0), 0);
      return { ...t, movimientos: newMovs, monto_bruto: +bruto.toFixed(2),
               neto: +(bruto - (t.monto_adelantos || 0)).toFixed(2) };
    }));
  };

  // Toggle adelanto (incluir/quitar)
  const toggleAdelanto = (trabajador_id, adelanto) => {
    setTrabajadores(prev => prev.map(t => {
      if (t.trabajador_id !== trabajador_id) return t;
      const isOn = (t.adelantos_ids || []).includes(adelanto.id);
      const newIds = isOn
        ? t.adelantos_ids.filter(x => x !== adelanto.id)
        : [...t.adelantos_ids, adelanto.id];
      const montoAdel = t.adelantos_pendientes
        .filter(a => newIds.includes(a.id))
        .reduce((s, a) => s + (parseFloat(a.monto) || 0), 0);
      return {
        ...t,
        adelantos_ids: newIds,
        monto_adelantos: +montoAdel.toFixed(2),
        neto: +((t.monto_bruto || 0) - montoAdel).toFixed(2),
      };
    }));
  };

  const handleGuardarBorrador = async () => {
    if (trabajadores.length === 0) { toast.error('Sin trabajadores'); return; }
    setSaving(true);
    try {
      const payload = {
        fecha_desde: fechaDesde, fecha_hasta: fechaHasta,
        detalles: trabajadores
          .filter(t => (t.movimiento_ids || []).length > 0)
          .map(t => {
            // Tarifas overrides: solo incluimos movimientos cuya tarifa editada
            // difiera del default de la ficha. Diferencia > 0.0001 (para evitar
            // ruido de floats).
            const tarifa_overrides = {};
            (t.movimientos || []).forEach(m => {
              if (!(t.movimiento_ids || []).includes(m.movimiento_id)) return;
              const diff = Math.abs((m.tarifa_destajo || 0) - (m.tarifa_default || 0));
              if (diff > 0.0001) {
                tarifa_overrides[m.movimiento_id] = Number(m.tarifa_destajo);
              }
            });
            return {
              trabajador_id: t.trabajador_id,
              movimiento_ids: t.movimiento_ids || [],
              tarifa_overrides,
              adelantos_ids: t.adelantos_ids || [],
              notas: null,
            };
          }),
        notas: notas || null,
      };
      if (payload.detalles.length === 0) {
        toast.error('Al menos un trabajador con movimientos');
        return;
      }
      let r;
      if (planillaId) {
        r = await updatePlanillaDestajo(planillaId, {
          detalles: payload.detalles,
          notas: payload.notas,
        });
      } else {
        r = await createPlanillaDestajo(payload);
        setPlanillaId(r.data.id);
      }
      toast.success('Planilla destajo guardada');
      navigate(`/planillas-destajo/${r.data.id}`);
    } catch (e) {
      toast.error(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Error al guardar');
    } finally { setSaving(false); }
  };

  const handleAprobar = async () => {
    if (!planillaId) { await handleGuardarBorrador(); return; }
    if (!window.confirm('¿Aprobar la planilla? Después ya no se podrán editar los movimientos. Podrás registrar los pagos por trabajador.')) return;
    setSaving(true);
    try {
      await aprobarPlanillaDestajo(planillaId);
      toast.success('Planilla aprobada');
      await reload();
      await cargarCuentasIfNeeded();
    } catch (e) {
      toast.error(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Error');
    } finally { setSaving(false); }
  };

  const handleAbrirPagoModal = async (detalle) => {
    await cargarCuentasIfNeeded();
    setPagoModal({ detalle });
  };

  const handleAnularPago = async (detalle) => {
    if (!window.confirm(`¿Anular el pago de ${detalle.nombre}?\n\nSe revertirán los egresos y sus adelantos volverán a pendientes.`)) return;
    try {
      await anularPagoDetalleDestajo(planillaId, detalle.detalle_id);
      toast.success('Pago anulado');
      await reload();
    } catch (e) {
      toast.error(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Error al anular');
    }
  };

  // Totales
  const totales = useMemo(() => trabajadores.reduce((acc, t) => {
    acc.num_trab += 1;
    acc.num_movs += t.num_movimientos || 0;
    acc.prendas += t.prendas || 0;
    acc.bruto += t.monto_bruto || 0;
    acc.adelantos += t.monto_adelantos || 0;
    acc.neto += t.neto || 0;
    if (t.pagado_at) acc.pagadoNeto += t.neto || 0;
    return acc;
  }, { num_trab: 0, num_movs: 0, prendas: 0, bruto: 0, adelantos: 0, neto: 0, pagadoNeto: 0 }), [trabajadores]);

  const numPagados = trabajadores.filter(t => !!t.pagado_at).length;
  const mostrarColumnaPago = estado === 'aprobada' || estado === 'pagada';
  const editableMovs = estado === 'borrador';

  if (loading) return <div className="p-10 text-muted-foreground">Cargando…</div>;

  return (
    <div className="max-w-[1500px] mx-auto space-y-5" data-testid="planilla-destajo-wizard">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/planillas-destajo')}
            className="h-8 w-8 flex items-center justify-center rounded-md hover:bg-muted">
            <ArrowLeft size={18}/>
          </button>
          <div>
            <h1 className="text-xl font-bold flex items-center gap-2">
              <Scissors size={18}/> {isEdit ? `Planilla Destajo ${fmtDate(fechaDesde)} — ${fmtDate(fechaHasta)}` : 'Nueva Planilla Destajo'}
            </h1>
            {estado && <p className="text-xs text-muted-foreground mt-0.5">Estado: <strong>{estado}</strong>{estado === 'aprobada' && trabajadores.length > 0 && ` · ${numPagados} de ${trabajadores.length} pagados`}</p>}
          </div>
        </div>
        <StepIndicator step={step}/>
      </div>

      {/* PASO 1 — Período */}
      {step === 1 && !isEdit && (
        <div className="bg-card rounded-xl border border-border p-8 space-y-5 max-w-2xl mx-auto">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Calendar size={18}/> Rango de fechas
          </h2>
          <p className="text-xs text-muted-foreground -mt-2">
            Los movimientos de producción de tus destajistas dentro de este rango se agregarán a la planilla.
            Un movimiento solo puede estar en una planilla destajo.
          </p>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1">Desde</label>
              <input type="date" value={fechaDesde} onChange={e => setFechaDesde(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background"/>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1">Hasta</label>
              <input type="date" value={fechaHasta} onChange={e => setFechaHasta(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background"/>
            </div>
          </div>
          <button onClick={handleCalcular} disabled={loading}
            className="w-full inline-flex items-center justify-center gap-2 bg-emerald-600 text-white px-4 py-3 text-sm font-medium rounded-md hover:bg-emerald-700 disabled:opacity-50"
            data-testid="btn-calcular-destajo">
            <Calculator size={16}/> Calcular planilla
          </button>
        </div>
      )}

      {/* PASO 2 — Lista editable */}
      {step === 2 && (
        <div className="space-y-4">
          {/* KPIs */}
          <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
            <KpiCard label="Período" main={`${fmtDate(fechaDesde).split('/').slice(0,2).join('/')} — ${fmtDate(fechaHasta).split('/').slice(0,2).join('/')}`} sub={`${trabajadores.length} destajistas`}/>
            <KpiCard label="Movimientos" main={totales.num_movs} sub="incluidos"/>
            <KpiCard label="Prendas" main={totales.prendas.toLocaleString('es-PE')} sub="total"/>
            <KpiCard label="Bruto" main={fmt(totales.bruto)} accent="emerald"/>
            <KpiCard label="Adelantos" main={fmt(totales.adelantos)} accent="red"/>
            <KpiCard label={mostrarColumnaPago ? "Pendiente pago" : "Total neto"}
              main={fmt(mostrarColumnaPago ? (totales.neto - totales.pagadoNeto) : totales.neto)}
              sub={mostrarColumnaPago ? `de ${fmt(totales.neto)}` : null} accent="emerald"/>
          </div>

          {warnings.length > 0 && (
            <div className="bg-amber-500/5 border border-amber-500/20 rounded-md p-3 flex items-start gap-2">
              <AlertTriangle size={16} className="text-amber-600 mt-0.5 shrink-0"/>
              <div className="text-xs">
                <div className="font-medium mb-1">Advertencias:</div>
                <ul className="list-disc list-inside space-y-0.5">
                  {warnings.map((w, i) => <li key={i}>{w.trabajador_nombre}: {w.mensaje}</li>)}
                </ul>
              </div>
            </div>
          )}

          {mostrarColumnaPago && (
            <div className="bg-blue-500/5 border border-blue-500/20 rounded-md p-3 flex items-start gap-2">
              <CreditCard size={16} className="text-blue-600 mt-0.5 shrink-0"/>
              <div className="text-xs">
                <div className="font-medium mb-0.5">Registro de pagos por trabajador</div>
                <div className="text-muted-foreground">
                  Usa el botón <strong>PAGO</strong> en cada fila para elegir la cuenta y registrar el egreso.
                </div>
              </div>
            </div>
          )}

          {trabajadores.length === 0 ? (
            <div className="bg-card rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
              No se encontraron movimientos de destajistas en este período.
              <div className="text-[11px] mt-2">
                Verifica que tus trabajadores tengan <strong>tipo_pago = destajo/mixto</strong> y estén vinculados a una persona de Producción.
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {trabajadores.map(t => (
                <TrabajadorCard key={t.trabajador_id}
                  trabajador={t}
                  expandido={!!expandidos[t.trabajador_id]}
                  onToggleExpand={() => setExpandidos(prev => ({ ...prev, [t.trabajador_id]: !prev[t.trabajador_id] }))}
                  editable={editableMovs}
                  mostrarColumnaPago={mostrarColumnaPago}
                  onToggleMov={(movId) => toggleMov(t.trabajador_id, movId)}
                  onToggleAdelanto={(adel) => toggleAdelanto(t.trabajador_id, adel)}
                  onUpdateTarifa={(movId, val) => updateTarifaMov(t.trabajador_id, movId, val)}
                  onResetTarifa={(movId) => resetTarifaMov(t.trabajador_id, movId)}
                  onAbrirPago={() => handleAbrirPagoModal(t)}
                  onAnularPago={() => handleAnularPago(t)}
                  onVerPagos={() => setVerPagosModal({ detalle: t })}
                />
              ))}
            </div>
          )}

          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">Notas (opcional)</label>
            <textarea rows={2} value={notas} onChange={e => setNotas(e.target.value)}
              disabled={!editableMovs}
              className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background disabled:opacity-60"/>
          </div>

          <div className="flex justify-between items-center gap-2 pt-2 border-t border-border">
            <button onClick={() => isEdit ? navigate('/planillas-destajo') : setStep(1)}
              className="inline-flex items-center gap-1.5 px-3 py-2 text-sm rounded-md border border-border hover:bg-muted">
              <ChevronLeft size={14}/> {isEdit ? 'Volver' : 'Atrás'}
            </button>
            <div className="flex gap-2">
              {estado === 'borrador' && (
                <>
                  <button onClick={handleGuardarBorrador} disabled={saving || trabajadores.length === 0}
                    className="inline-flex items-center gap-1.5 px-3 py-2 text-sm rounded-md border border-border hover:bg-muted disabled:opacity-50">
                    <Save size={14}/> {saving ? 'Guardando…' : 'Guardar borrador'}
                  </button>
                  <button onClick={handleAprobar} disabled={saving || trabajadores.length === 0}
                    className="inline-flex items-center gap-1.5 bg-blue-600 text-white px-3 py-2 text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50"
                    data-testid="btn-aprobar-destajo">
                    <Check size={14}/> Guardar y aprobar
                  </button>
                </>
              )}
              {estado === 'pagada' && (
                <div className="inline-flex items-center gap-2 px-3 py-2 rounded-md bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 text-xs font-medium">
                  <Check size={14}/> Planilla completamente pagada
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Modal PAGAR */}
      {pagoModal && (
        <PagarDestajoModal
          detalle={pagoModal.detalle}
          cuentas={cuentas}
          planillaId={planillaId}
          periodoLabel={`${fmtDate(fechaDesde)} — ${fmtDate(fechaHasta)}`}
          onClose={() => setPagoModal(null)}
          onPaid={async () => { setPagoModal(null); await reload(); }}
        />
      )}

      {/* Modal VER PAGOS */}
      {verPagosModal && (
        <VerPagosDestajoModal
          detalle={verPagosModal.detalle}
          pagos={pagos.filter(p => p.detalle_id === verPagosModal.detalle.detalle_id)}
          periodoLabel={`${fmtDate(fechaDesde)} — ${fmtDate(fechaHasta)}`}
          onClose={() => setVerPagosModal(null)}
          onAnular={async () => {
            setVerPagosModal(null);
            await handleAnularPago(verPagosModal.detalle);
          }}
        />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────
// Card de un trabajador (con sus movimientos colapsables)
// ─────────────────────────────────────────────────
function TrabajadorCard({ trabajador: t, expandido, onToggleExpand, editable,
                         mostrarColumnaPago, onToggleMov, onToggleAdelanto,
                         onUpdateTarifa, onResetTarifa,
                         onAbrirPago, onAnularPago, onVerPagos }) {
  const iniciales = (t.nombre || '?').substring(0, 2).toUpperCase();
  const pagado = !!t.pagado_at;
  const numExcluidos = (t.movimientos_excluidos || []).length;

  return (
    <div className={`bg-card rounded-xl border overflow-hidden transition-colors ${pagado ? 'border-emerald-500/40 bg-emerald-500/5' : 'border-border'}`}>
      {/* Header card — clickeable completo para expandir/colapsar */}
      <div
        className={`p-4 flex items-center gap-3 cursor-pointer transition-colors ${expandido ? 'bg-muted/10' : 'hover:bg-muted/20'}`}
        onClick={onToggleExpand}
        role="button"
        aria-expanded={expandido}
        title={expandido ? 'Colapsar movimientos' : 'Ver movimientos'}
      >
        <div className="h-8 w-8 flex items-center justify-center rounded-md bg-muted/50 text-muted-foreground shrink-0">
          {expandido ? <ChevronUp size={16}/> : <ChevronDown size={16}/>}
        </div>
        <div className="h-10 w-10 rounded-full bg-gradient-to-br from-blue-500 to-emerald-500 flex items-center justify-center text-white text-xs font-semibold shrink-0">
          {iniciales}
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-sm flex items-center gap-2">
            {t.nombre}
            <span className="text-[10px] font-normal text-blue-600 bg-blue-500/10 px-1.5 py-0.5 rounded">
              {expandido ? 'detalle abierto' : `ver ${t.num_movimientos || 0} movs`}
            </span>
          </div>
          <div className="text-[10px] text-muted-foreground">
            {t.unidad_interna_nombre || '(sin unidad)'} · {t.tipo_pago || 'destajo'}
            {numExcluidos > 0 && <span className="ml-2 text-amber-700">· {numExcluidos} movs excluidos</span>}
          </div>
        </div>
        {/* Resumen */}
        <div className="hidden md:grid grid-cols-4 gap-4 text-xs">
          <MiniStat label="Movs" value={t.num_movimientos || 0}/>
          <MiniStat label="Prendas" value={(t.prendas || 0).toLocaleString('es-PE')}/>
          <MiniStat label="Bruto" value={fmt(t.monto_bruto)} color="emerald"/>
          <MiniStat label="Adelantos" value={fmt(t.monto_adelantos)} color="red"/>
        </div>
        <div className="text-right shrink-0">
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Neto</div>
          <div className="text-lg font-bold font-mono text-emerald-700 dark:text-emerald-400">{fmt(t.neto)}</div>
        </div>
        {mostrarColumnaPago && (
          <div className="shrink-0 ml-2" onClick={e => e.stopPropagation()}>
            {pagado ? (
              <div className="flex items-center gap-1">
                <button onClick={onVerPagos}
                  className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 text-[11px] font-semibold hover:bg-emerald-500/20">
                  <Check size={12}/> Pagado
                </button>
              </div>
            ) : (
              <button onClick={onAbrirPago}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium rounded-md bg-blue-600 text-white hover:bg-blue-700 shadow-sm"
                data-testid={`pagar-destajo-${t.trabajador_id}`}>
                <CreditCard size={12}/> Pagar
              </button>
            )}
          </div>
        )}
      </div>

      {/* Expanded: movimientos + adelantos */}
      {expandido && (
        <div className="border-t border-border bg-muted/20 p-4 space-y-3">
          {/* Movimientos */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Movimientos de {t.nombre} ({t.num_movimientos} seleccionados / {(t.movimientos || []).length} disponibles)
              </div>
              {editable && (
                <a href={`/trabajadores`} target="_blank" rel="noopener noreferrer"
                  className="text-[10px] text-blue-600 hover:text-blue-700 hover:underline inline-flex items-center gap-1"
                  title="Abrir catálogo de trabajadores para editar tarifas de la ficha">
                  💡 Tarifas vienen de la ficha · editar catálogo
                </a>
              )}
            </div>
            {(t.num_pendientes_anteriores || 0) > 0 && editable && (
              <div className="mb-2 text-[11px] text-amber-800 bg-amber-500/5 border border-amber-500/30 rounded px-3 py-2 flex items-start gap-2">
                <AlertTriangle size={13} className="mt-0.5 shrink-0"/>
                <div>
                  <strong>{t.num_pendientes_anteriores} movimiento(s) de períodos anteriores</strong> pendientes de pago para {t.nombre}.
                  Están en la lista pero <strong>desmarcados</strong> — márcalos si quieres incluirlos en esta planilla.
                </div>
              </div>
            )}
            <div className="rounded-md border border-border bg-card overflow-hidden">
              <table className="w-full text-xs">
                <thead className="bg-muted/40">
                  <tr>
                    {editable && <th className="w-8 px-2 py-1.5"></th>}
                    <th className="text-left px-3 py-1.5 font-medium text-muted-foreground">Fecha</th>
                    <th className="text-left px-3 py-1.5 font-medium text-muted-foreground">N° Corte</th>
                    <th className="text-left px-3 py-1.5 font-medium text-muted-foreground">Modelo</th>
                    <th className="text-left px-3 py-1.5 font-medium text-muted-foreground">Servicio</th>
                    <th className="text-right px-3 py-1.5 font-medium text-muted-foreground">Cant.</th>
                    <th className="text-right px-3 py-1.5 font-medium text-muted-foreground"
                        title="Tarifa destajo. Viene de la ficha del trabajador. Editable por si un modelo paga distinto.">
                      Tarifa S/
                    </th>
                    <th className="text-right px-3 py-1.5 font-medium text-muted-foreground">Importe</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {(t.movimientos || []).map(m => {
                    const incluido = (t.movimiento_ids || []).includes(m.movimiento_id);
                    const diff = Math.abs((m.tarifa_destajo || 0) - (m.tarifa_default || 0));
                    const overrideada = diff > 0.0001;
                    const anterior = m.dentro_rango === false;
                    return (
                      <tr key={m.movimiento_id}
                          className={`hover:bg-muted/30 ${!incluido ? 'opacity-40' : ''} ${overrideada ? 'bg-amber-500/5' : ''} ${anterior ? 'border-l-2 border-amber-400' : ''}`}>
                        {editable && (
                          <td className="px-2 py-1.5 text-center">
                            <input type="checkbox" checked={incluido}
                              onChange={() => onToggleMov(m.movimiento_id)}
                              className="h-3.5 w-3.5"/>
                          </td>
                        )}
                        <td className="px-3 py-1.5 text-muted-foreground whitespace-nowrap">
                          {m.fecha ? fmtDate(m.fecha) : '—'}
                          {anterior && (
                            <span className="ml-1.5 inline-block px-1 py-0 rounded text-[9px] font-semibold bg-amber-500/20 text-amber-800"
                                  title="Este movimiento es anterior al rango seleccionado y sigue sin pagarse">
                              anterior
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-1.5 font-mono font-semibold">{m.n_corte || '—'}</td>
                        <td className="px-3 py-1.5">{m.modelo_nombre || '—'}</td>
                        <td className="px-3 py-1.5">{m.servicio_nombre || '—'}</td>
                        <td className="px-3 py-1.5 text-right font-mono">{m.cantidad}</td>
                        <td className="px-3 py-1.5 text-right">
                          {editable ? (
                            <div className="inline-flex items-center gap-1 justify-end">
                              <input type="number" step="0.0001" min="0"
                                value={m.tarifa_destajo}
                                onChange={e => onUpdateTarifa(m.movimiento_id, e.target.value)}
                                disabled={!incluido}
                                className={`w-24 px-2 py-1 text-right text-xs rounded border bg-background font-mono ${
                                  overrideada
                                    ? 'border-amber-500/60 text-amber-700 font-semibold focus:ring-2 focus:ring-amber-500'
                                    : 'border-border focus:ring-2 focus:ring-blue-500'
                                } disabled:opacity-40`}
                                title={overrideada
                                  ? `⚠️ Tarifa modificada. Default de ficha: S/ ${Number(m.tarifa_default).toFixed(4)}`
                                  : 'Tarifa desde la ficha del trabajador'}/>
                              {overrideada && (
                                <button type="button" onClick={() => onResetTarifa(m.movimiento_id)}
                                  className="h-5 w-5 flex items-center justify-center rounded hover:bg-amber-500/20 text-amber-700"
                                  title={`Restaurar a S/ ${Number(m.tarifa_default).toFixed(4)} (default)`}>
                                  <RotateCcw size={10}/>
                                </button>
                              )}
                            </div>
                          ) : (
                            <span className={`font-mono ${overrideada ? 'text-amber-700 font-semibold' : ''}`}
                                  title={overrideada ? `⚠️ Tarifa modificada (default: ${Number(m.tarifa_default).toFixed(4)})` : ''}>
                              {Number(m.tarifa_destajo).toFixed(4)}
                              {overrideada && ' *'}
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-1.5 text-right font-mono font-semibold">{fmt(m.importe)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {numExcluidos > 0 && editable && (
              <div className="mt-2 text-[10px] text-amber-700 bg-amber-500/5 border border-amber-500/20 rounded px-2 py-1.5">
                ⚠️ {numExcluidos} movimiento(s) no aparecen porque ya están en otra planilla destajo o porque no tienen tarifa configurada para su servicio.
              </div>
            )}
            {(t.movimientos || []).some(m => Math.abs((m.tarifa_destajo || 0) - (m.tarifa_default || 0)) > 0.0001) && (
              <div className="mt-2 text-[10px] text-amber-700 bg-amber-500/5 border border-amber-500/20 rounded px-2 py-1.5">
                ⚠️ Hay tarifas editadas manualmente en esta planilla (filas resaltadas en ámbar). Solo aplican para esta planilla; no cambian la ficha.
              </div>
            )}
          </div>

          {/* Adelantos */}
          {(t.adelantos_pendientes || []).length > 0 && (
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                Adelantos pendientes del trabajador
              </div>
              <div className="space-y-1">
                {t.adelantos_pendientes.map(a => {
                  const incluido = (t.adelantos_ids || []).includes(a.id);
                  return (
                    <label key={a.id}
                      className={`flex items-center gap-2 px-3 py-2 rounded-md border cursor-pointer text-xs ${
                        incluido ? 'bg-blue-500/5 border-blue-500/30' : 'bg-card border-border'
                      } ${!editable ? 'opacity-60 cursor-default' : ''}`}>
                      <input type="checkbox" checked={incluido}
                        disabled={!editable}
                        onChange={() => editable && onToggleAdelanto(a)}
                        className="h-3.5 w-3.5"/>
                      <span className="text-muted-foreground">{fmtDate(a.fecha)}</span>
                      <span className="flex-1 truncate">{a.motivo || '(sin motivo)'}</span>
                      <span className="font-mono font-semibold text-amber-700">{fmt(a.monto)}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          {pagado && mostrarColumnaPago && (
            <div className="flex justify-end">
              <button onClick={onAnularPago}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[11px] rounded-md hover:bg-red-500/10 text-red-600">
                <RotateCcw size={12}/> Anular pago
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function MiniStat({ label, value, color }) {
  const cls = color === 'emerald' ? 'text-emerald-700 dark:text-emerald-400'
            : color === 'red' ? 'text-red-600'
            : 'text-foreground';
  return (
    <div>
      <div className="text-[9px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className={`font-mono font-semibold ${cls}`}>{value}</div>
    </div>
  );
}

function KpiCard({ label, main, sub, accent = 'slate' }) {
  const accents = {
    slate:   'text-foreground',
    emerald: 'text-emerald-700 dark:text-emerald-400',
    red:     'text-red-600',
    blue:    'text-blue-700 dark:text-blue-400',
  };
  return (
    <div className="bg-card rounded-lg border border-border p-3">
      <div className="text-[10px] uppercase text-muted-foreground tracking-wider">{label}</div>
      <div className={`text-lg font-bold mt-0.5 font-mono ${accents[accent] || accents.slate}`}>{main}</div>
      {sub && <div className="text-[10px] text-muted-foreground mt-0.5">{sub}</div>}
    </div>
  );
}

// ─────────────────────────────────────────────────
// Modal Pagar destajo
// ─────────────────────────────────────────────────
function PagarDestajoModal({ detalle, cuentas, planillaId, periodoLabel, onClose, onPaid }) {
  const neto = parseFloat(detalle.neto) || 0;
  const [medios, setMedios] = useState([]);
  const [saving, setSaving] = useState(false);

  const cuentasVisibles = (cuentas || []).filter(c => {
    if (!c.es_ficticia) return true;
    return detalle.unidad_interna_id && c.unidad_interna_id === detalle.unidad_interna_id;
  });
  const cuentaUI = cuentasVisibles.find(c => c.es_ficticia);

  useEffect(() => {
    const defaults = detalle.medios_pago_default || [];
    if (defaults.length > 0) {
      let restante = neto;
      const arr = defaults.map((m, idx) => {
        const monto = idx === defaults.length - 1
          ? +restante.toFixed(2)
          : +(neto * (parseFloat(m.porcentaje) / 100)).toFixed(2);
        restante -= monto;
        return { cuenta_id: String(m.cuenta_id), monto: monto.toFixed(2), referencia: '' };
      });
      setMedios(arr);
    } else {
      setMedios([{ cuenta_id: '', monto: neto.toFixed(2), referencia: '' }]);
    }
  }, [detalle.detalle_id]); // eslint-disable-line

  const suma = medios.reduce((s, m) => s + (parseFloat(m.monto) || 0), 0);
  const diff = +(neto - suma).toFixed(2);
  const ok = Math.abs(neto - suma) < 0.01;

  const actualizar = (idx, campo, valor) => setMedios(prev => {
    const arr = [...prev]; arr[idx] = { ...arr[idx], [campo]: valor }; return arr;
  });
  const agregar = () => setMedios(prev => [...prev, { cuenta_id: '', monto: '', referencia: '' }]);
  const eliminar = (idx) => setMedios(prev => prev.length > 1 ? prev.filter((_, i) => i !== idx) : prev);
  const ajustarALNeto = () => setMedios(prev => {
    const arr = prev.map(x => ({ ...x }));
    let acc = 0;
    for (let i = 0; i < arr.length - 1; i++) acc += parseFloat(arr[i].monto) || 0;
    arr[arr.length - 1].monto = (+(neto - acc).toFixed(2)).toFixed(2);
    return arr;
  });

  const handlePagar = async () => {
    if (!ok) { toast.error(`Suma (${fmt(suma)}) ≠ neto (${fmt(neto)})`); return; }
    const validos = medios.filter(m => m.cuenta_id && parseFloat(m.monto) > 0);
    if (validos.length === 0) { toast.error('Agrega al menos un medio'); return; }
    setSaving(true);
    try {
      await pagarDetalleDestajo(planillaId, detalle.detalle_id, {
        medios: validos.map(m => ({
          cuenta_id: parseInt(m.cuenta_id),
          monto: parseFloat(m.monto),
          referencia: m.referencia || null,
        })),
      });
      toast.success(`Pago de ${detalle.nombre} registrado`);
      onPaid();
    } catch (e) {
      toast.error(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Error');
    } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
         onClick={onClose}>
      <div onClick={e => e.stopPropagation()} className="bg-card rounded-xl shadow-2xl w-full max-w-2xl border border-border">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-gradient-to-br from-blue-500 to-emerald-500 flex items-center justify-center text-white text-xs font-semibold">
              {(detalle.nombre || '?').substring(0, 2).toUpperCase()}
            </div>
            <div>
              <h2 className="text-base font-semibold flex items-center gap-2">
                <Scissors size={16}/> Pagar destajo · {detalle.nombre}
              </h2>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                {detalle.unidad_interna_nombre || '(sin unidad)'} · {periodoLabel}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="h-8 w-8 flex items-center justify-center rounded-md hover:bg-muted">
            <X size={18}/>
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          <div className="flex items-center justify-between bg-emerald-500/5 border border-emerald-500/20 rounded-md px-3 py-2">
            <div>
              <div className="text-xs text-muted-foreground">Neto a pagar</div>
              <div className="text-[10px] text-muted-foreground mt-0.5">
                {detalle.num_movimientos} movs · {(detalle.prendas || 0).toLocaleString('es-PE')} prendas
              </div>
            </div>
            <div className="text-xl font-bold font-mono text-emerald-700 dark:text-emerald-400">{fmt(neto)}</div>
          </div>

          {cuentaUI && (
            <div className="text-[11px] text-blue-700 bg-blue-500/5 border border-blue-500/20 rounded-md px-3 py-2 flex items-start gap-2">
              <CreditCard size={14} className="mt-0.5 shrink-0"/>
              <span>
                Pertenece a <strong>{detalle.unidad_interna_nombre}</strong> · disponible la cuenta interna{' '}
                <strong>{cuentaUI.nombre}</strong> para imputar el costo a la unidad.
              </span>
            </div>
          )}

          <div className="space-y-2">
            <div className="grid grid-cols-12 gap-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground px-1">
              <div className="col-span-5">Cuenta</div>
              <div className="col-span-3 text-right">Monto</div>
              <div className="col-span-3">Referencia</div>
              <div className="col-span-1"></div>
            </div>
            {medios.map((m, idx) => (
              <div key={idx} className="grid grid-cols-12 gap-2 items-center">
                <select value={m.cuenta_id} onChange={e => actualizar(idx, 'cuenta_id', e.target.value)}
                  className="col-span-5 px-3 py-2 text-sm rounded-md border border-border bg-background">
                  <option value="">— Cuenta —</option>
                  {cuentasVisibles.map(c => (
                    <option key={c.id} value={c.id}>
                      {c.nombre}{c.es_ficticia ? ' (unidad interna)' : ''}
                    </option>
                  ))}
                </select>
                <input type="number" step="0.01" min="0" placeholder="0.00" value={m.monto}
                  onChange={e => actualizar(idx, 'monto', e.target.value)}
                  className="col-span-3 px-3 py-2 text-sm text-right rounded-md border border-border bg-background font-mono"/>
                <input type="text" placeholder="Op., nota..." value={m.referencia}
                  onChange={e => actualizar(idx, 'referencia', e.target.value)}
                  className="col-span-3 px-3 py-2 text-sm rounded-md border border-border bg-background"/>
                <button onClick={() => eliminar(idx)} disabled={medios.length === 1}
                  className="col-span-1 h-9 flex items-center justify-center rounded-md hover:bg-red-500/10 text-red-600 disabled:opacity-30">
                  <Trash2 size={14}/>
                </button>
              </div>
            ))}
            <div className="flex items-center justify-between">
              <button onClick={agregar} type="button"
                className="inline-flex items-center gap-1.5 px-3 py-1 text-xs rounded-md border border-dashed border-border hover:bg-muted">
                <Plus size={12}/> Agregar medio
              </button>
              <button onClick={ajustarALNeto} type="button"
                className="inline-flex items-center gap-1.5 px-3 py-1 text-xs rounded-md text-blue-600 hover:bg-blue-500/10">
                Ajustar al neto
              </button>
            </div>
          </div>

          <div className={`rounded-md px-3 py-2 flex items-center justify-between text-sm ${ok ? 'bg-emerald-500/10 border border-emerald-500/20' : 'bg-amber-500/10 border border-amber-500/20'}`}>
            <div className="flex items-center gap-1.5 text-xs">
              {ok ? <Check size={14} className="text-emerald-600"/> : <AlertTriangle size={14} className="text-amber-600"/>}
              <span>Suma medios</span>
            </div>
            <div className="flex items-center gap-4">
              <span className={`font-mono font-semibold ${ok ? 'text-emerald-700 dark:text-emerald-400' : 'text-amber-700 dark:text-amber-400'}`}>{fmt(suma)}</span>
              {!ok && <span className="text-[11px] text-amber-700 dark:text-amber-400">Diferencia: <strong className="font-mono">{fmt(diff)}</strong></span>}
            </div>
          </div>
        </div>

        <div className="flex justify-between items-center px-5 py-3 border-t border-border bg-muted/20">
          <button onClick={onClose} className="px-3 py-2 text-sm rounded-md border border-border hover:bg-muted">
            Cancelar
          </button>
          <button onClick={handlePagar} disabled={saving || !ok}
            className="inline-flex items-center gap-1.5 bg-emerald-600 text-white px-4 py-2 text-sm font-medium rounded-md hover:bg-emerald-700 disabled:opacity-50"
            data-testid="btn-confirmar-pago-destajo">
            <Check size={14}/> {saving ? 'Registrando…' : 'Registrar pago'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────
// Modal ver pagos
// ─────────────────────────────────────────────────
function VerPagosDestajoModal({ detalle, pagos, periodoLabel, onClose, onAnular }) {
  const total = pagos.reduce((s, p) => s + parseFloat(p.monto || 0), 0);
  const fechaPago = detalle.pagado_at ? new Date(detalle.pagado_at).toLocaleString('es-PE') : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
         onClick={onClose}>
      <div onClick={e => e.stopPropagation()} className="bg-card rounded-xl shadow-2xl w-full max-w-xl border border-border">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-gradient-to-br from-emerald-500 to-blue-500 flex items-center justify-center text-white text-xs font-semibold">
              {(detalle.nombre || '?').substring(0, 2).toUpperCase()}
            </div>
            <div>
              <h2 className="text-base font-semibold flex items-center gap-2">
                <Check size={16} className="text-emerald-600"/> Pago destajo · {detalle.nombre}
              </h2>
              <p className="text-[11px] text-muted-foreground mt-0.5">{periodoLabel}</p>
            </div>
          </div>
          <button onClick={onClose} className="h-8 w-8 flex items-center justify-center rounded-md hover:bg-muted">
            <X size={18}/>
          </button>
        </div>

        <div className="px-5 py-4 space-y-3">
          <div className="flex items-center justify-between bg-emerald-500/5 border border-emerald-500/20 rounded-md px-3 py-2">
            <div>
              <div className="text-xs text-muted-foreground">Total pagado</div>
              {fechaPago && <div className="text-[10px] text-muted-foreground mt-0.5">{fechaPago}{detalle.pagado_por ? ` · ${detalle.pagado_por}` : ''}</div>}
            </div>
            <div className="text-xl font-bold font-mono text-emerald-700 dark:text-emerald-400">{fmt(total)}</div>
          </div>
          {pagos.length === 0 ? (
            <div className="text-xs text-muted-foreground italic py-4 text-center">Sin medios registrados.</div>
          ) : (
            <div className="space-y-2">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground px-1">
                Medios usados
              </div>
              {pagos.map((p, idx) => (
                <div key={p.id || idx} className="flex items-center justify-between bg-muted/30 rounded-md px-3 py-2.5 border border-border">
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm truncate">{p.cuenta_nombre || `Cuenta #${p.cuenta_id}`}</div>
                    {p.referencia && <div className="text-[11px] text-muted-foreground mt-0.5 truncate">Ref: {p.referencia}</div>}
                  </div>
                  <div className="font-mono text-sm font-semibold ml-3 shrink-0">{fmt(p.monto)}</div>
                </div>
              ))}
            </div>
          )}
          <div className="bg-blue-500/5 border border-blue-500/20 rounded-md px-3 py-2 text-[11px] text-blue-700 dark:text-blue-400">
            💡 Estos movimientos ya aparecen en <strong>Tesorería</strong> como EGRESOs de destajo.
          </div>
        </div>

        <div className="flex justify-between items-center px-5 py-3 border-t border-border bg-muted/20">
          <button onClick={onClose} className="px-3 py-2 text-sm rounded-md border border-border hover:bg-muted">
            Cerrar
          </button>
          <button onClick={onAnular}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-sm rounded-md bg-red-600 text-white hover:bg-red-700">
            <RotateCcw size={14}/> Anular pago
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────
// Step indicator
// ─────────────────────────────────────────────────
function StepIndicator({ step }) {
  const steps = [
    { n: 1, label: 'Período' },
    { n: 2, label: 'Cálculo y pago' },
  ];
  return (
    <div className="flex items-center gap-2 text-xs">
      {steps.map((s, i) => (
        <React.Fragment key={s.n}>
          <div className={`flex items-center gap-1.5 ${step >= s.n ? 'text-foreground font-medium' : 'text-muted-foreground'}`}>
            <span className={`h-5 w-5 rounded-full flex items-center justify-center text-[10px] font-semibold ${step >= s.n ? 'bg-emerald-600 text-white' : 'bg-muted'}`}>
              {s.n}
            </span>
            {s.label}
          </div>
          {i < steps.length - 1 && <ChevronRight size={12} className="text-muted-foreground"/>}
        </React.Fragment>
      ))}
    </div>
  );
}
