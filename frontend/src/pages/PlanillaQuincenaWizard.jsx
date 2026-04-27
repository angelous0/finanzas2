import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ChevronLeft, ChevronRight, Calculator, Clock, X, Check,
  AlertTriangle, Save, CreditCard, Plus, Trash2, ArrowLeft,
  RotateCcw, Printer,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  calcularPreviewPlanilla, createPlanillaQuincena, updatePlanillaQuincena,
  getPlanillaQuincena, aprobarPlanillaQuincena,
  pagarDetallePlanilla, anularPagoDetalle,
  getAdelantosPendientesTrabajador, getCuentasFinancieras,
  planillaPdfUrl,
} from '../services/api';

const fmt = (v) => `S/ ${Number(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtDate = (d) => d ? new Date(d + 'T00:00:00').toLocaleDateString('es-PE') : '';
const MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];

// Recalcula el neto de una línea en cliente.
// IMPORTANTE: NO redondeamos en los pasos intermedios. Solo redondeamos
// al final (subtotales y neto) a 2 decimales para persistencia.
function recalcularLinea(linea) {
  const hn = parseFloat(linea.horas_normales) || 0;
  const h25 = parseFloat(linea.horas_extra_25) || 0;
  const h35 = parseFloat(linea.horas_extra_35) || 0;
  const tardanzas = parseFloat(linea.descuento_tardanzas) || 0;
  const adelantos = parseFloat(linea.monto_adelantos) || 0;

  const monto_hn_raw = hn * (parseFloat(linea.hora_simple) || 0);
  const monto_h25_raw = h25 * (parseFloat(linea.hora_extra_25) || 0);
  const monto_h35_raw = h35 * (parseFloat(linea.hora_extra_35) || 0);
  const subtotal_horas_raw = monto_hn_raw + monto_h25_raw + monto_h35_raw;

  const asig = parseFloat(linea.asig_familiar_monto) || 0;
  const afp = parseFloat(linea.afp_total) || 0;
  const neto_raw = subtotal_horas_raw + asig - afp - tardanzas - adelantos;

  return {
    ...linea,
    monto_horas_normales: +monto_hn_raw.toFixed(2),
    monto_horas_25: +monto_h25_raw.toFixed(2),
    monto_horas_35: +monto_h35_raw.toFixed(2),
    subtotal_horas: +subtotal_horas_raw.toFixed(2),
    neto: +neto_raw.toFixed(2),
  };
}

export default function PlanillaQuincenaWizard() {
  const navigate = useNavigate();
  const { id } = useParams();
  const isEdit = !!id;

  const [step, setStep] = useState(1);
  const [anio, setAnio] = useState(2026);
  const [mes, setMes] = useState(4);
  const [quincena, setQuincena] = useState(2);
  const [fechas, setFechas] = useState({ inicio: '', fin: '' });
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [planillaId, setPlanillaId] = useState(isEdit ? parseInt(id) : null);
  const [estado, setEstado] = useState('borrador');
  const [warnings, setWarnings] = useState([]);
  const [lineas, setLineas] = useState([]);
  const [notas, setNotas] = useState('');

  // Cuentas financieras (para la modal de pago)
  const [cuentas, setCuentas] = useState([]);

  // Pagos ya registrados (para mostrar detalle al click en "Pagado")
  const [pagos, setPagos] = useState([]);

  // Popup de adelantos
  const [adelantosModal, setAdelantosModal] = useState(null); // {lineaIdx, adelantos}

  // Modal de pago por trabajador (nuevo pago)
  const [pagoModal, setPagoModal] = useState(null); // { linea }

  // Modal ver detalle de pagos ya hechos
  const [verPagosModal, setVerPagosModal] = useState(null); // { linea }

  const cargarCuentasIfNeeded = async () => {
    if (cuentas.length > 0) return;
    try {
      const c = await getCuentasFinancieras();
      // Cargamos TODAS las cuentas activas (incluyendo ficticias de unidades internas).
      // El filtrado final — qué cuentas ve cada trabajador — se hace en el modal de pago
      // según la unidad_interna_id del trabajador.
      setCuentas((c.data || []).filter(x => x.activo !== false));
    } catch { /* noop */ }
  };

  const reload = async (planillaIdArg) => {
    const pid = planillaIdArg || planillaId;
    if (!pid) return;
    const r = await getPlanillaQuincena(pid);
    const p = r.data;
    setPlanillaId(p.id);
    setAnio(p.anio); setMes(p.mes); setQuincena(p.quincena);
    setFechas({ inicio: p.fecha_inicio, fin: p.fecha_fin });
    setEstado(p.estado);
    setNotas(p.notas || '');

    const adelPorTrab = {};
    (p.adelantos_vinculados || []).forEach(a => {
      if (!adelPorTrab[a.trabajador_id]) adelPorTrab[a.trabajador_id] = [];
      adelPorTrab[a.trabajador_id].push(a);
    });

    const dets = (p.detalles || []).map(d => ({
      ...d,
      horas_normales: parseFloat(d.horas_normales) || 0,
      horas_extra_25: parseFloat(d.horas_extra_25) || 0,
      horas_extra_35: parseFloat(d.horas_extra_35) || 0,
      descuento_tardanzas: parseFloat(d.descuento_tardanzas) || 0,
      monto_adelantos: parseFloat(d.monto_adelantos) || 0,
      adelantos_ids: (adelPorTrab[d.trabajador_id] || []).map(a => a.id),
      _adelantos_vinculados: adelPorTrab[d.trabajador_id] || [],
      hora_simple: parseFloat(d.hora_simple) || 0,
      hora_extra_25: parseFloat(d.hora_extra_25) || 0,
      hora_extra_35: parseFloat(d.hora_extra_35) || 0,
      asig_familiar_monto: parseFloat(d.asig_familiar_monto) || 0,
      afp_total: parseFloat(d.afp_total) || 0,
    }));
    setLineas(dets);
    setPagos(p.pagos || []);
    setStep(2);
  };

  // Cargar si es edit
  useEffect(() => {
    if (!isEdit) return;
    (async () => {
      setLoading(true);
      try {
        await reload(parseInt(id));
        await cargarCuentasIfNeeded();
      } catch (e) {
        toast.error('Error cargando planilla');
      } finally { setLoading(false); }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEdit, id]);

  const handleCalcular = async () => {
    setLoading(true);
    try {
      const r = await calcularPreviewPlanilla({ anio: parseInt(anio), mes: parseInt(mes), quincena: parseInt(quincena) });
      if (r.data.planilla_existente_id) {
        toast.error('Ya existe una planilla para este período');
        return;
      }
      setFechas({ inicio: r.data.fecha_inicio, fin: r.data.fecha_fin });
      setWarnings(r.data.warnings || []);
      // El backend ya autoselecciona los adelantos pendientes del trabajador.
      // El usuario puede desmarcarlos desde el modal de adelantos para postergar.
      setLineas((r.data.trabajadores || []).map(t => ({
        ...t,
        adelantos_ids: t.adelantos_ids || [],
        _adelantos_vinculados: t.adelantos_pendientes || [],
      })));
      setStep(2);
    } catch (e) {
      toast.error(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Error al calcular');
    } finally { setLoading(false); }
  };

  const actualizarLinea = (idx, campo, valor) => {
    setLineas(prev => {
      const arr = [...prev];
      arr[idx] = recalcularLinea({ ...arr[idx], [campo]: valor });
      return arr;
    });
  };

  const handleGuardarBorrador = async () => {
    setSaving(true);
    try {
      const payload = {
        anio: parseInt(anio), mes: parseInt(mes), quincena: parseInt(quincena),
        fecha_inicio: fechas.inicio, fecha_fin: fechas.fin,
        detalles: lineas.map(l => ({
          trabajador_id: l.trabajador_id,
          horas_normales: parseFloat(l.horas_normales) || 0,
          horas_extra_25: parseFloat(l.horas_extra_25) || 0,
          horas_extra_35: parseFloat(l.horas_extra_35) || 0,
          descuento_tardanzas: parseFloat(l.descuento_tardanzas) || 0,
          adelantos_ids: l.adelantos_ids || [],
          notas: l.notas || null,
        })),
        notas: notas || null,
      };
      let r;
      if (planillaId) {
        r = await updatePlanillaQuincena(planillaId, { detalles: payload.detalles, notas });
      } else {
        r = await createPlanillaQuincena(payload);
        setPlanillaId(r.data.id);
      }
      toast.success('Planilla guardada en borrador');
      navigate(`/planillas-quincena/${r.data.id}`);
    } catch (e) {
      toast.error(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Error al guardar');
    } finally { setSaving(false); }
  };

  const handleAprobar = async () => {
    if (!planillaId) { await handleGuardarBorrador(); return; }
    if (!window.confirm('¿Aprobar la planilla? Después ya no se podrán editar las horas. Podrás registrar los pagos por trabajador desde la misma tabla.')) return;
    setSaving(true);
    try {
      await aprobarPlanillaQuincena(planillaId);
      toast.success('Planilla aprobada · ahora registra los pagos por trabajador');
      await reload();
      await cargarCuentasIfNeeded();
    } catch (e) {
      toast.error(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Error');
    } finally { setSaving(false); }
  };

  const handleAbrirAdelantos = async (lineaIdx) => {
    const l = lineas[lineaIdx];
    try {
      const r = await getAdelantosPendientesTrabajador(l.trabajador_id);
      setAdelantosModal({ lineaIdx, adelantos: r.data || [] });
    } catch { toast.error('Error cargando adelantos'); }
  };

  const handleToggleAdelanto = (adel) => {
    setAdelantosModal(m => {
      const l = lineas[m.lineaIdx];
      const ids = l.adelantos_ids || [];
      const yaEsta = ids.includes(adel.id);
      const newIds = yaEsta ? ids.filter(x => x !== adel.id) : [...ids, adel.id];
      const newAdels = yaEsta
        ? (l._adelantos_vinculados || []).filter(a => a.id !== adel.id)
        : [...(l._adelantos_vinculados || []), adel];
      const total = newAdels.reduce((s,a) => s + parseFloat(a.monto || 0), 0);

      setLineas(prev => {
        const arr = [...prev];
        arr[m.lineaIdx] = recalcularLinea({
          ...arr[m.lineaIdx],
          adelantos_ids: newIds,
          _adelantos_vinculados: newAdels,
          monto_adelantos: total,
        });
        return arr;
      });
      return m;
    });
  };

  const handleAbrirPagoModal = async (l) => {
    await cargarCuentasIfNeeded();
    setPagoModal({ linea: l });
  };

  const handleAnularPagoTrabajador = async (l) => {
    if (!window.confirm(`¿Anular el pago de ${l.nombre}?\n\nSe revertirán los egresos (se genera INGRESO en las cuentas) y sus adelantos volverán a pendientes.`)) return;
    try {
      await anularPagoDetalle(planillaId, l.id);
      toast.success('Pago anulado');
      await reload();
    } catch (e) {
      toast.error(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Error al anular');
    }
  };

  // === Totales ===
  const totales = lineas.reduce((acc, l) => {
    acc.bruto += parseFloat(l.subtotal_horas) || 0;
    acc.asig += parseFloat(l.asig_familiar_monto) || 0;
    acc.afp += parseFloat(l.afp_total) || 0;
    acc.tardanzas += parseFloat(l.descuento_tardanzas) || 0;
    acc.adelantos += parseFloat(l.monto_adelantos) || 0;
    acc.neto += parseFloat(l.neto) || 0;
    if (l.pagado_at) acc.pagadoNeto += parseFloat(l.neto) || 0;
    return acc;
  }, { bruto: 0, asig: 0, afp: 0, tardanzas: 0, adelantos: 0, neto: 0, pagadoNeto: 0 });

  const numPagados = lineas.filter(l => !!l.pagado_at).length;
  const totalPendienteDePago = totales.neto - totales.pagadoNeto;

  const mostrarColumnaPago = estado === 'aprobada' || estado === 'pagada';
  const editableHoras = estado === 'borrador';

  // ====================================================================
  // RENDER
  // ====================================================================

  if (loading) return <div className="p-10 text-muted-foreground">Cargando…</div>;

  return (
    <div className="max-w-[1500px] mx-auto space-y-5" data-testid="planilla-wizard">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/planillas-quincena')}
            className="h-8 w-8 flex items-center justify-center rounded-md hover:bg-muted">
            <ArrowLeft size={18}/>
          </button>
          <div>
            <h1 className="text-xl font-bold">{isEdit ? `Planilla ${MESES[mes-1]} ${anio} · Q${quincena}` : 'Nueva Planilla Quincenal'}</h1>
            {estado && <p className="text-xs text-muted-foreground mt-0.5">Estado: <strong>{estado}</strong>{estado === 'aprobada' && lineas.length > 0 && ` · ${numPagados} de ${lineas.length} pagados`}</p>}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {isEdit && (estado === 'aprobada' || estado === 'pagada') && (
            <button
              onClick={() => window.open(planillaPdfUrl(planillaId), '_blank')}
              className="inline-flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-md border border-border bg-card hover:bg-muted transition-colors"
              title="Abrir PDF consolidado para imprimir"
              data-testid="btn-imprimir-planilla">
              <Printer size={14}/> Imprimir planilla
            </button>
          )}
          <StepIndicator step={step}/>
        </div>
      </div>

      {/* PASO 1 — Período */}
      {step === 1 && !isEdit && (
        <div className="bg-card rounded-xl border border-border p-8 space-y-5 max-w-2xl mx-auto">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Clock size={18}/> Selecciona el período
          </h2>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1">Año</label>
              <input type="number" value={anio} onChange={e => setAnio(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background" />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1">Mes</label>
              <select value={mes} onChange={e => setMes(parseInt(e.target.value))}
                className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background">
                {MESES.map((n,i) => <option key={i} value={i+1}>{n}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground block mb-1">Quincena</label>
              <select value={quincena} onChange={e => setQuincena(parseInt(e.target.value))}
                className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background">
                <option value={1}>1ª (días 1 a 15)</option>
                <option value={2}>2ª (días 16 a fin de mes)</option>
              </select>
            </div>
          </div>
          <button onClick={handleCalcular} disabled={loading}
            className="w-full inline-flex items-center justify-center gap-2 bg-emerald-600 text-white px-4 py-3 text-sm font-medium rounded-md hover:bg-emerald-700 disabled:opacity-50"
            data-testid="btn-calcular">
            <Calculator size={16}/> Calcular planilla
          </button>
        </div>
      )}

      {/* PASO 2 — Tabla editable con columna PAGO al aprobar */}
      {step === 2 && (
        <div className="space-y-4">
          {/* Header del período con KPIs */}
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            <div className="bg-card rounded-lg border border-border p-3">
              <div className="text-[10px] uppercase text-muted-foreground tracking-wider">Período</div>
              <div className="text-sm font-semibold mt-0.5">{MESES[mes-1]} {anio} · Q{quincena}</div>
              <div className="text-[10px] text-muted-foreground mt-0.5">{fmtDate(fechas.inicio)} — {fmtDate(fechas.fin)}</div>
            </div>
            <div className="bg-card rounded-lg border border-border p-3">
              <div className="text-[10px] uppercase text-muted-foreground tracking-wider">Trabajadores</div>
              <div className="text-lg font-bold mt-0.5">{lineas.length}</div>
              {mostrarColumnaPago && (
                <div className="text-[10px] text-muted-foreground mt-0.5">{numPagados} pagados · {lineas.length - numPagados} pendientes</div>
              )}
            </div>
            <div className="bg-card rounded-lg border border-border p-3">
              <div className="text-[10px] uppercase text-muted-foreground tracking-wider">Bruto horas</div>
              <div className="text-lg font-bold text-emerald-700 dark:text-emerald-400 font-mono mt-0.5">{fmt(totales.bruto)}</div>
            </div>
            <div className="bg-card rounded-lg border border-border p-3">
              <div className="text-[10px] uppercase text-muted-foreground tracking-wider">Descuentos</div>
              <div className="text-lg font-bold text-red-600 font-mono mt-0.5">{fmt(totales.afp + totales.tardanzas + totales.adelantos)}</div>
            </div>
            <div className={`rounded-lg border p-3 ${mostrarColumnaPago ? 'bg-blue-500/5 border-blue-500/30' : 'bg-emerald-500/5 border-emerald-500/30'}`}>
              <div className={`text-[10px] uppercase tracking-wider font-semibold ${mostrarColumnaPago ? 'text-blue-700 dark:text-blue-400' : 'text-emerald-700 dark:text-emerald-400'}`}>
                {mostrarColumnaPago ? 'Pendiente de pago' : 'Total neto'}
              </div>
              <div className={`text-xl font-bold font-mono mt-0.5 ${mostrarColumnaPago ? 'text-blue-700 dark:text-blue-400' : 'text-emerald-700 dark:text-emerald-400'}`}>
                {mostrarColumnaPago ? fmt(totalPendienteDePago) : fmt(totales.neto)}
              </div>
              {mostrarColumnaPago && <div className="text-[10px] text-muted-foreground mt-0.5">de {fmt(totales.neto)} total</div>}
            </div>
          </div>

          {warnings.length > 0 && (
            <div className="bg-amber-500/5 border border-amber-500/20 rounded-md p-3 flex items-start gap-2">
              <AlertTriangle size={16} className="text-amber-600 mt-0.5 shrink-0"/>
              <div className="text-xs">
                <div className="font-medium mb-1">Advertencias:</div>
                <ul className="list-disc list-inside space-y-0.5">
                  {warnings.map((w,i) => <li key={i}>{w.trabajador_nombre}: {w.mensaje}</li>)}
                </ul>
              </div>
            </div>
          )}

          {!mostrarColumnaPago && (
            <div className="space-y-1">
              <div className="text-[11px] text-muted-foreground italic">
                💡 Los montos de <strong>Asig. Fam.</strong> y <strong>AFP</strong> ya están calculados como <strong>½ quincena</strong> (la mitad del mensual legal).
              </div>
              {lineas.some(l => (l.adelantos_ids?.length || 0) > 0) && (
                <div className="text-[11px] text-blue-700 dark:text-blue-400 italic">
                  💡 Los <strong>adelantos pendientes</strong> de cada trabajador se aplican automáticamente. Click en el botón <strong>+</strong> de la columna Adelantos para desmarcar y postergar a la siguiente quincena.
                </div>
              )}
            </div>
          )}
          {mostrarColumnaPago && (
            <div className="bg-blue-500/5 border border-blue-500/20 rounded-md p-3 flex items-start gap-2">
              <CreditCard size={16} className="text-blue-600 mt-0.5 shrink-0"/>
              <div className="text-xs">
                <div className="font-medium mb-0.5">Registro de pagos por trabajador</div>
                <div className="text-muted-foreground">
                  Usa el botón de la última columna <strong>PAGO</strong> para abrir el detalle y elegir medios de pago de cada trabajador individualmente.
                </div>
              </div>
            </div>
          )}

          <div className="rounded-xl border border-border bg-card overflow-x-auto shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/50 border-b-2 border-border">
                  <th className="text-left px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Trabajador</th>
                  <th className="text-right px-3 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Sueldo mes</th>
                  <th className="text-center px-2 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground w-20" title="Horas normales trabajadas en la quincena">
                    H. Normales
                  </th>
                  <th className="text-center px-2 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground w-20">
                    H. Extra 25%
                  </th>
                  <th className="text-center px-2 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground w-20">
                    H. Extra 35%
                  </th>
                  <th className="text-right px-3 py-3 text-[11px] font-semibold uppercase tracking-wider text-emerald-700 dark:text-emerald-400" title="Asignación familiar (½ quincena)">
                    Asig. Fam.
                  </th>
                  <th className="text-right px-3 py-3 text-[11px] font-semibold uppercase tracking-wider text-red-600" title="AFP aporte + prima (½ quincena)">
                    AFP
                  </th>
                  <th className="text-right px-2 py-3 text-[11px] font-semibold uppercase tracking-wider text-red-600 w-28">
                    Tardanzas
                  </th>
                  <th className="text-right px-2 py-3 text-[11px] font-semibold uppercase tracking-wider text-red-600 w-32">
                    Adelantos
                  </th>
                  <th className="text-right px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
                    NETO
                  </th>
                  {mostrarColumnaPago && (
                    <th className="text-center px-3 py-3 text-[11px] font-semibold uppercase tracking-wider text-blue-700 dark:text-blue-400 w-36">
                      PAGO
                    </th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {lineas.map((l, idx) => {
                  const pagado = !!l.pagado_at;
                  return (
                  <tr key={l.trabajador_id} className={`hover:bg-muted/20 transition-colors ${pagado ? 'bg-emerald-500/5' : ''}`}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <div className="h-8 w-8 rounded-full bg-gradient-to-br from-blue-500 to-emerald-500 flex items-center justify-center text-white text-[11px] font-semibold shrink-0">
                          {(l.nombre || '?').substring(0, 2).toUpperCase()}
                        </div>
                        <div className="min-w-0">
                          <div className="font-semibold text-sm truncate">{l.nombre}</div>
                          <div className="text-[10px] text-muted-foreground truncate">
                            {l.area}{l.unidad_interna_nombre ? ` · ${l.unidad_interna_nombre}` : ''}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-3 text-right">
                      <div className="font-mono text-sm font-semibold">{fmt(l.sueldo_basico_total)}</div>
                      <div className="text-[10px] text-muted-foreground font-mono">{fmt(l.hora_simple)}/h</div>
                    </td>
                    <td className="px-2 py-3">
                      {editableHoras ? (
                        <input type="number" step="0.5" value={l.horas_normales}
                          onChange={e => actualizarLinea(idx, 'horas_normales', e.target.value)}
                          className="w-full px-2 py-1.5 text-sm text-center rounded-md border border-border bg-background font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
                      ) : (
                        <div className="text-center font-mono text-sm">{l.horas_normales}</div>
                      )}
                    </td>
                    <td className="px-2 py-3">
                      {editableHoras ? (
                        <input type="number" step="0.5" value={l.horas_extra_25}
                          onChange={e => actualizarLinea(idx, 'horas_extra_25', e.target.value)}
                          className="w-full px-2 py-1.5 text-sm text-center rounded-md border border-border bg-background font-mono focus:outline-none focus:ring-2 focus:ring-blue-500" />
                      ) : <div className="text-center font-mono text-sm">{l.horas_extra_25}</div>}
                    </td>
                    <td className="px-2 py-3">
                      {editableHoras ? (
                        <input type="number" step="0.5" value={l.horas_extra_35}
                          onChange={e => actualizarLinea(idx, 'horas_extra_35', e.target.value)}
                          className="w-full px-2 py-1.5 text-sm text-center rounded-md border border-border bg-background font-mono focus:outline-none focus:ring-2 focus:ring-blue-500" />
                      ) : <div className="text-center font-mono text-sm">{l.horas_extra_35}</div>}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-sm text-emerald-700 dark:text-emerald-400">
                      {fmt(l.asig_familiar_monto)}
                    </td>
                    <td className="px-3 py-3 text-right font-mono text-sm text-red-600">
                      {fmt(l.afp_total)}
                    </td>
                    <td className="px-2 py-3">
                      {editableHoras ? (
                        <input type="number" step="0.01" min="0" value={l.descuento_tardanzas}
                          onChange={e => actualizarLinea(idx, 'descuento_tardanzas', e.target.value)}
                          className="w-full px-2 py-1.5 text-sm text-right rounded-md border border-border bg-background font-mono focus:outline-none focus:ring-2 focus:ring-red-400" />
                      ) : <div className="text-right font-mono text-sm">{fmt(l.descuento_tardanzas)}</div>}
                    </td>
                    <td className="px-2 py-3">
                      <div className="flex items-center gap-1">
                        <div className="flex-1 text-right">
                          <div className={`font-mono text-sm ${parseFloat(l.monto_adelantos) > 0 ? 'text-red-600 font-semibold' : 'text-muted-foreground'}`}>
                            {fmt(l.monto_adelantos)}
                          </div>
                          {(l.adelantos_ids?.length || 0) > 0 && (
                            <div className="text-[10px] text-blue-600 font-medium mt-0.5">
                              {l.adelantos_ids.length} adelanto{l.adelantos_ids.length !== 1 ? 's' : ''} aplicado{l.adelantos_ids.length !== 1 ? 's' : ''}
                            </div>
                          )}
                        </div>
                        {editableHoras && (
                          <button onClick={() => handleAbrirAdelantos(idx)}
                            className={`h-7 w-7 flex items-center justify-center rounded-md transition-colors ${(l.adelantos_ids?.length || 0) > 0 ? 'bg-blue-500/15 hover:bg-blue-500/25 text-blue-700' : 'bg-blue-500/10 hover:bg-blue-500/20 text-blue-600'}`}
                            title={(l.adelantos_ids?.length || 0) > 0 ? 'Editar adelantos aplicados (puedes desmarcar para postergar)' : 'Ver/incluir adelantos pendientes'}>
                            <Plus size={14}/>
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="font-mono text-base font-bold text-emerald-700 dark:text-emerald-400">
                        {fmt(l.neto)}
                      </div>
                    </td>
                    {mostrarColumnaPago && (
                      <td className="px-3 py-3 text-center">
                        {pagado ? (
                          <button onClick={() => setVerPagosModal({ linea: l })}
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 text-[11px] font-semibold transition-colors"
                            title="Ver detalle de medios de pago usados"
                            data-testid={`ver-pago-${l.id}`}>
                            <Check size={12}/> Pagado
                          </button>
                        ) : (
                          <button onClick={() => handleAbrirPagoModal(l)}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium rounded-md bg-blue-600 text-white hover:bg-blue-700 transition-colors shadow-sm"
                            data-testid={`pagar-trabajador-${l.id}`}
                            title="Registrar pago de este trabajador">
                            <CreditCard size={12}/> Pagar
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                  );
                })}
              </tbody>
              <tfoot className="bg-muted/40 border-t-2 border-border">
                <tr className="font-semibold text-xs">
                  <td colSpan={2} className="px-4 py-3 text-right uppercase tracking-wider text-muted-foreground">Totales →</td>
                  <td colSpan={3}></td>
                  <td className="px-3 py-3 text-right font-mono text-sm text-emerald-700 dark:text-emerald-400">{fmt(totales.asig)}</td>
                  <td className="px-3 py-3 text-right font-mono text-sm text-red-600">{fmt(totales.afp)}</td>
                  <td className="px-2 py-3 text-right font-mono text-sm text-red-600">{fmt(totales.tardanzas)}</td>
                  <td className="px-2 py-3 text-right font-mono text-sm text-red-600">{fmt(totales.adelantos)}</td>
                  <td className="px-4 py-3 text-right font-mono text-base font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-500/10">
                    {fmt(totales.neto)}
                  </td>
                  {mostrarColumnaPago && (
                    <td className="px-3 py-3 text-center text-[11px] text-muted-foreground">
                      {numPagados}/{lineas.length}
                    </td>
                  )}
                </tr>
              </tfoot>
            </table>
          </div>

          <div>
            <label className="text-xs font-medium text-muted-foreground block mb-1">Notas (opcional)</label>
            <textarea rows={2} value={notas} onChange={e => setNotas(e.target.value)}
              disabled={estado !== 'borrador'}
              className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background disabled:opacity-60" />
          </div>

          <div className="flex justify-between items-center gap-2 pt-2 border-t border-border">
            <button onClick={() => isEdit ? navigate('/planillas-quincena') : setStep(1)}
              className="inline-flex items-center gap-1.5 px-3 py-2 text-sm rounded-md border border-border hover:bg-muted">
              <ChevronLeft size={14}/> {isEdit ? 'Volver' : 'Atrás'}
            </button>
            <div className="flex gap-2">
              {estado === 'borrador' && (
                <>
                  <button onClick={handleGuardarBorrador} disabled={saving}
                    className="inline-flex items-center gap-1.5 px-3 py-2 text-sm rounded-md border border-border hover:bg-muted">
                    <Save size={14}/> {saving ? 'Guardando…' : 'Guardar borrador'}
                  </button>
                  <button onClick={handleAprobar} disabled={saving}
                    className="inline-flex items-center gap-1.5 bg-blue-600 text-white px-3 py-2 text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50"
                    data-testid="btn-aprobar">
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

      {/* Modal adelantos */}
      {adelantosModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
             onClick={() => setAdelantosModal(null)}>
          <div onClick={e => e.stopPropagation()} className="bg-card rounded-xl shadow-2xl w-full max-w-xl border border-border">
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
              <div>
                <h2 className="text-base font-semibold">Adelantos pendientes</h2>
                <p className="text-xs text-muted-foreground mt-0.5">{lineas[adelantosModal.lineaIdx].nombre}</p>
              </div>
              <button onClick={() => setAdelantosModal(null)}
                className="h-8 w-8 flex items-center justify-center rounded-md hover:bg-muted">
                <X size={18}/>
              </button>
            </div>
            {adelantosModal.adelantos.length > 0 && (
              <div className="px-5 py-2.5 bg-blue-500/5 border-b border-border text-xs text-blue-700 dark:text-blue-400">
                💡 Los adelantos pendientes se aplican automáticamente. Haz click en uno para <strong>desmarcarlo</strong> y postergarlo a otra quincena.
              </div>
            )}
            <div className="max-h-[400px] overflow-y-auto">
              {adelantosModal.adelantos.length === 0 ? (
                <div className="p-10 text-center text-muted-foreground text-sm">
                  No hay adelantos pendientes para este trabajador.
                </div>
              ) : adelantosModal.adelantos.map(a => {
                const yaEsta = (lineas[adelantosModal.lineaIdx].adelantos_ids || []).includes(a.id);
                return (
                  <div key={a.id} className={`flex items-center justify-between px-5 py-3 border-b border-border hover:bg-muted/30 cursor-pointer ${yaEsta ? 'bg-blue-500/5' : ''}`}
                       onClick={() => handleToggleAdelanto(a)}>
                    <div className="flex-1">
                      <div className="text-xs text-muted-foreground">{fmtDate(a.fecha)}{a.cuenta_nombre ? ` · ${a.cuenta_nombre}` : ''}</div>
                      <div className="font-medium">{a.motivo || 'Sin motivo'}</div>
                    </div>
                    <div className="text-right">
                      <div className="font-mono text-sm text-amber-700 dark:text-amber-400 font-semibold">{fmt(a.monto)}</div>
                    </div>
                    <div className="ml-3">
                      {yaEsta ? (
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] bg-blue-500/10 text-blue-700 dark:text-blue-400 font-medium">
                          <Check size={12}/> Aplicado
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] border border-amber-500/30 bg-amber-500/5 text-amber-700 dark:text-amber-400 font-medium">
                          ⏭ Postergado
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="flex justify-end px-5 py-3 border-t border-border">
              <button onClick={() => setAdelantosModal(null)}
                className="px-3 py-1.5 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700">
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal pago por trabajador */}
      {pagoModal && (
        <PagarTrabajadorModal
          linea={pagoModal.linea}
          cuentas={cuentas}
          planillaId={planillaId}
          periodoLabel={`${MESES[mes-1]} ${anio} · Q${quincena}`}
          onClose={() => setPagoModal(null)}
          onPaid={async () => {
            setPagoModal(null);
            await reload();
          }}
        />
      )}

      {/* Modal detalle de pago registrado */}
      {verPagosModal && (
        <VerPagosDetalleModal
          linea={verPagosModal.linea}
          pagos={pagos.filter(p => p.detalle_id === verPagosModal.linea.id)}
          periodoLabel={`${MESES[mes-1]} ${anio} · Q${quincena}`}
          onClose={() => setVerPagosModal(null)}
          onAnular={async () => {
            setVerPagosModal(null);
            await handleAnularPagoTrabajador(verPagosModal.linea);
          }}
        />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────
// Modal: Pagar UN trabajador
// ─────────────────────────────────────────────────
function PagarTrabajadorModal({ linea, cuentas, planillaId, periodoLabel, onClose, onPaid }) {
  const neto = parseFloat(linea.neto) || 0;
  const [medios, setMedios] = useState([]);
  const [saving, setSaving] = useState(false);

  // Filtro de cuentas visibles según la unidad interna del trabajador:
  //  - Cuentas reales (no ficticias): siempre visibles
  //  - Cuenta ficticia: solo si corresponde a la unidad interna del trabajador
  //    (un trabajador de Corte solo ve "Cuenta Corte Interno", no las otras unidades)
  const cuentasVisibles = (cuentas || []).filter(c => {
    if (!c.es_ficticia) return true;
    return linea.unidad_interna_id && c.unidad_interna_id === linea.unidad_interna_id;
  });
  const tieneUnidadInterna = !!linea.unidad_interna_id;
  const cuentaUnidadInterna = cuentasVisibles.find(c => c.es_ficticia);

  // Auto-poblar desde medios_pago_default; el último absorbe el resto
  useEffect(() => {
    const defaults = linea.medios_pago_default || [];
    if (defaults.length > 0) {
      let restante = neto;
      const arr = defaults.map((m, idx) => {
        const monto = idx === defaults.length - 1
          ? +restante.toFixed(2)
          : +(neto * (parseFloat(m.porcentaje) / 100)).toFixed(2);
        restante -= monto;
        return {
          cuenta_id: String(m.cuenta_id),
          cuenta_nombre: m.cuenta_nombre,
          porcentaje: m.porcentaje,
          monto: monto.toFixed(2),
          referencia: '',
        };
      });
      setMedios(arr);
    } else {
      setMedios([{ cuenta_id: '', monto: neto.toFixed(2), referencia: '' }]);
    }
  }, [linea.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const suma = medios.reduce((s, m) => s + (parseFloat(m.monto) || 0), 0);
  const diff = +(neto - suma).toFixed(2);
  const ok = Math.abs(neto - suma) < 0.01;

  const actualizar = (idx, campo, valor) => {
    setMedios(prev => {
      const arr = [...prev];
      arr[idx] = { ...arr[idx], [campo]: valor };
      return arr;
    });
  };
  const agregar = () => setMedios(prev => [...prev, { cuenta_id: '', monto: '', referencia: '' }]);
  const eliminar = (idx) => setMedios(prev => prev.length > 1 ? prev.filter((_, i) => i !== idx) : prev);

  const ajustarALNeto = () => {
    if (medios.length === 0) return;
    setMedios(prev => {
      const arr = prev.map(m => ({ ...m }));
      // Todos menos el último se mantienen; el último toma lo que falte
      let acumulado = 0;
      for (let i = 0; i < arr.length - 1; i++) {
        acumulado += parseFloat(arr[i].monto) || 0;
      }
      arr[arr.length - 1].monto = (+(neto - acumulado).toFixed(2)).toFixed(2);
      return arr;
    });
  };

  const handlePagar = async () => {
    if (!ok) {
      toast.error(`Suma (${fmt(suma)}) no coincide con neto (${fmt(neto)})`);
      return;
    }
    const mediosValidos = medios.filter(m => m.cuenta_id && parseFloat(m.monto) > 0);
    if (mediosValidos.length === 0) {
      toast.error('Agrega al menos un medio de pago');
      return;
    }
    setSaving(true);
    try {
      await pagarDetallePlanilla(planillaId, linea.id, {
        medios: mediosValidos.map(m => ({
          cuenta_id: parseInt(m.cuenta_id),
          monto: parseFloat(m.monto),
          referencia: m.referencia || null,
        })),
      });
      toast.success(`Pago de ${linea.nombre} registrado`);
      onPaid();
    } catch (e) {
      toast.error(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Error al pagar');
    } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
         onClick={onClose}>
      <div onClick={e => e.stopPropagation()} className="bg-card rounded-xl shadow-2xl w-full max-w-2xl border border-border">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-gradient-to-br from-blue-500 to-emerald-500 flex items-center justify-center text-white text-xs font-semibold">
              {(linea.nombre || '?').substring(0, 2).toUpperCase()}
            </div>
            <div>
              <h2 className="text-base font-semibold flex items-center gap-2">
                <CreditCard size={16}/> Pagar {linea.nombre}
              </h2>
              <p className="text-[11px] text-muted-foreground mt-0.5">{linea.area}{linea.unidad_interna_nombre ? ' · '+linea.unidad_interna_nombre : ''} · {periodoLabel}</p>
            </div>
          </div>
          <button onClick={onClose} className="h-8 w-8 flex items-center justify-center rounded-md hover:bg-muted">
            <X size={18}/>
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          <div className="flex items-center justify-between bg-emerald-500/5 border border-emerald-500/20 rounded-md px-3 py-2">
            <div className="text-xs text-muted-foreground">Neto a pagar</div>
            <div className="text-xl font-bold font-mono text-emerald-700 dark:text-emerald-400">{fmt(neto)}</div>
          </div>

          {(linea.medios_pago_default || []).length === 0 && (
            <div className="text-[11px] text-amber-700 bg-amber-500/10 border border-amber-500/20 rounded-md px-3 py-2 flex items-start gap-2">
              <AlertTriangle size={14} className="mt-0.5 shrink-0"/>
              <span>Este trabajador no tiene medios de pago por defecto. Agrégalos manualmente abajo o configúralos en la ficha del trabajador para auto-poblar próximas planillas.</span>
            </div>
          )}

          {tieneUnidadInterna && cuentaUnidadInterna && (
            <div className="text-[11px] text-blue-700 bg-blue-500/5 border border-blue-500/20 rounded-md px-3 py-2 flex items-start gap-2">
              <CreditCard size={14} className="mt-0.5 shrink-0"/>
              <span>
                Este trabajador pertenece a <strong>{linea.unidad_interna_nombre}</strong> · tienes disponible la cuenta interna{' '}
                <strong>{cuentaUnidadInterna.nombre}</strong> para imputar el costo a la unidad.
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
                  className="col-span-5 px-3 py-2 text-sm rounded-md border border-border bg-background"
                  data-testid={`pago-cuenta-${idx}`}>
                  <option value="">— Cuenta —</option>
                  {cuentasVisibles.map(c => (
                    <option key={c.id} value={c.id}>
                      {c.nombre}{c.es_ficticia ? ' (unidad interna)' : ''}
                    </option>
                  ))}
                </select>
                <input type="number" step="0.01" min="0" placeholder="0.00" value={m.monto}
                  onChange={e => actualizar(idx, 'monto', e.target.value)}
                  className="col-span-3 px-3 py-2 text-sm text-right rounded-md border border-border bg-background font-mono"
                  data-testid={`pago-monto-${idx}`}/>
                <input type="text" placeholder="Op., nota..." value={m.referencia}
                  onChange={e => actualizar(idx, 'referencia', e.target.value)}
                  className="col-span-3 px-3 py-2 text-sm rounded-md border border-border bg-background" />
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
                className="inline-flex items-center gap-1.5 px-3 py-1 text-xs rounded-md text-blue-600 hover:bg-blue-500/10"
                title="Ajusta el último medio para que la suma sea igual al neto">
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
              <span className={`font-mono font-semibold ${ok ? 'text-emerald-700 dark:text-emerald-400' : 'text-amber-700 dark:text-amber-400'}`}>
                {fmt(suma)}
              </span>
              {!ok && (
                <span className="text-[11px] text-amber-700 dark:text-amber-400">
                  Diferencia: <strong className="font-mono">{fmt(diff)}</strong>
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex justify-between items-center px-5 py-3 border-t border-border bg-muted/20">
          <button onClick={onClose} className="px-3 py-2 text-sm rounded-md border border-border hover:bg-muted">
            Cancelar
          </button>
          <button onClick={handlePagar} disabled={saving || !ok}
            className="inline-flex items-center gap-1.5 bg-emerald-600 text-white px-4 py-2 text-sm font-medium rounded-md hover:bg-emerald-700 disabled:opacity-50"
            data-testid="btn-confirmar-pago">
            <Check size={14}/> {saving ? 'Registrando…' : 'Registrar pago'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────
// Modal: Ver detalle del pago registrado
// ─────────────────────────────────────────────────
function VerPagosDetalleModal({ linea, pagos, periodoLabel, onClose, onAnular }) {
  const total = pagos.reduce((s, p) => s + parseFloat(p.monto || 0), 0);
  const fechaPago = linea.pagado_at ? new Date(linea.pagado_at).toLocaleString('es-PE') : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
         onClick={onClose}>
      <div onClick={e => e.stopPropagation()} className="bg-card rounded-xl shadow-2xl w-full max-w-xl border border-border">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-gradient-to-br from-emerald-500 to-blue-500 flex items-center justify-center text-white text-xs font-semibold">
              {(linea.nombre || '?').substring(0, 2).toUpperCase()}
            </div>
            <div>
              <h2 className="text-base font-semibold flex items-center gap-2">
                <Check size={16} className="text-emerald-600"/> Pago de {linea.nombre}
              </h2>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                {linea.area}{linea.unidad_interna_nombre ? ' · '+linea.unidad_interna_nombre : ''} · {periodoLabel}
              </p>
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
              {fechaPago && <div className="text-[10px] text-muted-foreground mt-0.5">{fechaPago}{linea.pagado_por ? ` · ${linea.pagado_por}` : ''}</div>}
            </div>
            <div className="text-xl font-bold font-mono text-emerald-700 dark:text-emerald-400">{fmt(total)}</div>
          </div>

          {pagos.length === 0 ? (
            <div className="text-xs text-muted-foreground italic py-4 text-center">
              No hay medios de pago registrados.
            </div>
          ) : (
            <div className="space-y-2">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground px-1">
                Medios de pago utilizados
              </div>
              {pagos.map((p, idx) => (
                <div key={p.id || idx} className="flex items-center justify-between bg-muted/30 rounded-md px-3 py-2.5 border border-border">
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm truncate">{p.cuenta_nombre || `Cuenta #${p.cuenta_id}`}</div>
                    {p.referencia && (
                      <div className="text-[11px] text-muted-foreground mt-0.5 truncate">
                        Ref: {p.referencia}
                      </div>
                    )}
                    {p.notas && (
                      <div className="text-[11px] text-muted-foreground italic mt-0.5 truncate">
                        {p.notas}
                      </div>
                    )}
                  </div>
                  <div className="font-mono text-sm font-semibold ml-3 shrink-0">{fmt(p.monto)}</div>
                </div>
              ))}
            </div>
          )}

          <div className="bg-blue-500/5 border border-blue-500/20 rounded-md px-3 py-2 text-[11px] text-blue-700 dark:text-blue-400">
            💡 Estos movimientos ya aparecen en <strong>Tesorería</strong> y <strong>Pagos</strong> como EGRESOs.
          </div>
        </div>

        <div className="flex justify-between items-center px-5 py-3 border-t border-border bg-muted/20">
          <button onClick={onClose} className="px-3 py-2 text-sm rounded-md border border-border hover:bg-muted">
            Cerrar
          </button>
          <button onClick={onAnular}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-sm rounded-md bg-red-600 text-white hover:bg-red-700"
            data-testid="btn-anular-pago-desde-detalle">
            <RotateCcw size={14}/> Anular pago
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────
// Step indicator (2 pasos)
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
