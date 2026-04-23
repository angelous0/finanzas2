import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ChevronLeft, ChevronRight, Calculator, Clock, X, Check,
  AlertTriangle, Save, CreditCard, Plus, Trash2, Edit3, ArrowLeft,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  calcularPreviewPlanilla, createPlanillaQuincena, updatePlanillaQuincena,
  getPlanillaQuincena, aprobarPlanillaQuincena, pagarPlanillaQuincena,
  anularPagoPlanillaQuincena,
  getAdelantosPendientesTrabajador, getCuentasFinancieras,
} from '../services/api';
import { useEmpresa } from '../context/EmpresaContext';

const fmt = (v) => `S/ ${Number(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtDate = (d) => d ? new Date(d + 'T00:00:00').toLocaleDateString('es-PE') : '';
const MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];

// Recalcula el neto de una línea en cliente (mismo algoritmo del backend)
function recalcularLinea(linea) {
  const hn = parseFloat(linea.horas_normales) || 0;
  const h25 = parseFloat(linea.horas_extra_25) || 0;
  const h35 = parseFloat(linea.horas_extra_35) || 0;
  const tardanzas = parseFloat(linea.descuento_tardanzas) || 0;
  const adelantos = parseFloat(linea.monto_adelantos) || 0;

  const monto_hn = +(hn * (linea.hora_simple || 0)).toFixed(2);
  const monto_h25 = +(h25 * (linea.hora_extra_25 || 0)).toFixed(2);
  const monto_h35 = +(h35 * (linea.hora_extra_35 || 0)).toFixed(2);
  const subtotal_horas = +(monto_hn + monto_h25 + monto_h35).toFixed(2);

  const asig = +(linea.asig_familiar_monto || 0);
  const afp = +(linea.afp_total || 0);
  const neto = +(subtotal_horas + asig - afp - tardanzas - adelantos).toFixed(2);

  return { ...linea, monto_horas_normales: monto_hn, monto_horas_25: monto_h25, monto_horas_35: monto_h35, subtotal_horas, neto };
}

export default function PlanillaQuincenaWizard() {
  const { empresaActual } = useEmpresa();
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

  // Paso 3
  const [cuentas, setCuentas] = useState([]);
  const [pagosPlan, setPagosPlan] = useState([]);
  const [existingPagos, setExistingPagos] = useState([]);

  // Popup de adelantos
  const [adelantosModal, setAdelantosModal] = useState(null); // {lineaIdx, adelantos}

  // Cargar si es edit
  useEffect(() => {
    if (!isEdit) return;
    (async () => {
      setLoading(true);
      try {
        const r = await getPlanillaQuincena(id);
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
        setExistingPagos(p.pagos || []);
        setStep(2);
      } catch (e) {
        toast.error('Error cargando planilla');
      } finally { setLoading(false); }
    })();
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
      setLineas((r.data.trabajadores || []).map(t => ({
        ...t,
        adelantos_ids: [],
        _adelantos_vinculados: [],
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
    if (!window.confirm('¿Aprobar la planilla? Después ya no se podrá editar.')) return;
    setSaving(true);
    try {
      await aprobarPlanillaQuincena(planillaId);
      toast.success('Planilla aprobada');
      const r = await getPlanillaQuincena(planillaId);
      setEstado(r.data.estado);
      setStep(3);
      // cargar cuentas
      const c = await getCuentasFinancieras();
      setCuentas((c.data || []).filter(x => !x.es_ficticia && x.activo !== false));
    } catch (e) {
      toast.error(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Error');
    } finally { setSaving(false); }
  };

  const handleAbrirAdelantos = async (lineaIdx) => {
    const l = lineas[lineaIdx];
    try {
      const r = await getAdelantosPendientesTrabajador(l.trabajador_id);
      // Incluir también los ya vinculados (aunque estén "descontado=false" mientras esta planilla siga en borrador)
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

  // === Totales ===
  const totales = lineas.reduce((acc, l) => {
    acc.bruto += parseFloat(l.subtotal_horas) || 0;
    acc.asig += parseFloat(l.asig_familiar_monto) || 0;
    acc.afp += parseFloat(l.afp_total) || 0;
    acc.tardanzas += parseFloat(l.descuento_tardanzas) || 0;
    acc.adelantos += parseFloat(l.monto_adelantos) || 0;
    acc.neto += parseFloat(l.neto) || 0;
    return acc;
  }, { bruto: 0, asig: 0, afp: 0, tardanzas: 0, adelantos: 0, neto: 0 });

  // ====================================================================
  // RENDER
  // ====================================================================

  if (loading) return <div className="p-10 text-muted-foreground">Cargando…</div>;

  return (
    <div className="max-w-[1400px] mx-auto space-y-5" data-testid="planilla-wizard">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/planillas-quincena')}
            className="h-8 w-8 flex items-center justify-center rounded-md hover:bg-muted">
            <ArrowLeft size={18}/>
          </button>
          <div>
            <h1 className="text-xl font-bold">{isEdit ? `Planilla ${MESES[mes-1]} ${anio} · Q${quincena}` : 'Nueva Planilla Quincenal'}</h1>
            {estado && <p className="text-xs text-muted-foreground mt-0.5">Estado: <strong>{estado}</strong></p>}
          </div>
        </div>
        <StepIndicator step={step}/>
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

      {/* PASO 2 — Tabla editable */}
      {step === 2 && (
        <div className="space-y-4">
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

          <div className="rounded-xl border border-border bg-card overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-muted/40 border-b border-border">
                <tr>
                  <th className="text-left px-2 py-2 font-medium uppercase text-[10px]">Trabajador</th>
                  <th className="text-right px-2 py-2 font-medium uppercase text-[10px]">Sueldo</th>
                  <th className="text-center px-1 py-2 font-medium uppercase text-[10px] w-16">H.Norm</th>
                  <th className="text-center px-1 py-2 font-medium uppercase text-[10px] w-16">H.25%</th>
                  <th className="text-center px-1 py-2 font-medium uppercase text-[10px] w-16">H.35%</th>
                  <th className="text-right px-2 py-2 font-medium uppercase text-[10px]">Asig.Fam</th>
                  <th className="text-right px-2 py-2 font-medium uppercase text-[10px]">AFP</th>
                  <th className="text-right px-1 py-2 font-medium uppercase text-[10px] w-20">Tardanzas</th>
                  <th className="text-right px-1 py-2 font-medium uppercase text-[10px] w-24">Adelantos</th>
                  <th className="text-right px-2 py-2 font-medium uppercase text-[10px]">NETO</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {lineas.map((l, idx) => (
                  <tr key={l.trabajador_id} className="hover:bg-muted/20">
                    <td className="px-2 py-2">
                      <div className="font-medium">{l.nombre}</div>
                      <div className="text-[10px] text-muted-foreground">{l.area}{l.unidad_interna_nombre ? ` · ${l.unidad_interna_nombre}` : ''}</div>
                    </td>
                    <td className="px-2 py-2 text-right font-mono">{fmt(l.sueldo_basico_total)}</td>
                    <td className="px-1 py-2">
                      {estado === 'borrador' ? (
                        <input type="number" step="0.5" value={l.horas_normales}
                          onChange={e => actualizarLinea(idx, 'horas_normales', e.target.value)}
                          className="w-full px-1 py-1 text-xs text-center rounded border border-border bg-background font-mono" />
                      ) : (
                        <div className="text-center font-mono">{l.horas_normales}</div>
                      )}
                      <div className="text-[9px] text-muted-foreground text-center mt-0.5 font-mono">{fmt(l.hora_simple)}/h</div>
                    </td>
                    <td className="px-1 py-2">
                      {estado === 'borrador' ? (
                        <input type="number" step="0.5" value={l.horas_extra_25}
                          onChange={e => actualizarLinea(idx, 'horas_extra_25', e.target.value)}
                          className="w-full px-1 py-1 text-xs text-center rounded border border-border bg-background font-mono" />
                      ) : <div className="text-center font-mono">{l.horas_extra_25}</div>}
                    </td>
                    <td className="px-1 py-2">
                      {estado === 'borrador' ? (
                        <input type="number" step="0.5" value={l.horas_extra_35}
                          onChange={e => actualizarLinea(idx, 'horas_extra_35', e.target.value)}
                          className="w-full px-1 py-1 text-xs text-center rounded border border-border bg-background font-mono" />
                      ) : <div className="text-center font-mono">{l.horas_extra_35}</div>}
                    </td>
                    <td className="px-2 py-2 text-right font-mono text-emerald-700">{fmt(l.asig_familiar_monto)}</td>
                    <td className="px-2 py-2 text-right font-mono text-red-600">{fmt(l.afp_total)}</td>
                    <td className="px-1 py-2">
                      {estado === 'borrador' ? (
                        <input type="number" step="0.01" min="0" value={l.descuento_tardanzas}
                          onChange={e => actualizarLinea(idx, 'descuento_tardanzas', e.target.value)}
                          className="w-full px-1 py-1 text-xs text-right rounded border border-border bg-background font-mono" />
                      ) : <div className="text-right font-mono">{fmt(l.descuento_tardanzas)}</div>}
                    </td>
                    <td className="px-1 py-2">
                      <div className="flex items-center gap-1">
                        <div className="flex-1 text-right font-mono text-red-600">{fmt(l.monto_adelantos)}</div>
                        {estado === 'borrador' && (
                          <button onClick={() => handleAbrirAdelantos(idx)}
                            className="h-6 w-6 flex items-center justify-center rounded hover:bg-muted text-blue-600"
                            title="Adelantos pendientes">
                            <Plus size={12}/>
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="px-2 py-2 text-right font-mono text-sm font-bold text-emerald-700 dark:text-emerald-400">
                      {fmt(l.neto)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="bg-muted/30 border-t-2 border-border">
                <tr className="font-semibold text-[11px]">
                  <td colSpan={5} className="px-2 py-2 text-right">TOTALES →</td>
                  <td className="px-2 py-2 text-right font-mono text-emerald-700">{fmt(totales.asig)}</td>
                  <td className="px-2 py-2 text-right font-mono text-red-600">{fmt(totales.afp)}</td>
                  <td className="px-1 py-2 text-right font-mono text-red-600">{fmt(totales.tardanzas)}</td>
                  <td className="px-1 py-2 text-right font-mono text-red-600">{fmt(totales.adelantos)}</td>
                  <td className="px-2 py-2 text-right font-mono text-base font-bold text-emerald-700 dark:text-emerald-400">{fmt(totales.neto)}</td>
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
              {estado === 'aprobada' && (
                <button onClick={() => setStep(3)}
                  className="inline-flex items-center gap-1.5 bg-emerald-600 text-white px-3 py-2 text-sm font-medium rounded-md hover:bg-emerald-700">
                  <CreditCard size={14}/> Registrar pago
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* PASO 3 — Medios de pago */}
      {step === 3 && planillaId && (
        <PasoPagos
          planillaId={planillaId}
          totalNeto={totales.neto || 0}
          cuentas={cuentas}
          estado={estado}
          existingPagos={existingPagos}
          onPagada={() => navigate(`/planillas-quincena/${planillaId}`)}
          onBack={() => setStep(2)}
        />
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
                      <div className="text-xs text-muted-foreground">{fmtDate(a.fecha)} · {a.cuenta_nombre}</div>
                      <div className="font-medium">{a.motivo || 'Sin motivo'}</div>
                    </div>
                    <div className="text-right">
                      <div className="font-mono text-sm text-amber-700 dark:text-amber-400 font-semibold">{fmt(a.monto)}</div>
                    </div>
                    <div className="ml-3">
                      {yaEsta ? (
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] bg-blue-500/10 text-blue-700 dark:text-blue-400 font-medium">
                          <Check size={12}/> Incluido
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] border border-border text-muted-foreground">
                          <Plus size={12}/> Incluir
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
    </div>
  );
}

// ─────────────────────────────────────────────────
// Paso 3 — Medios de pago
// ─────────────────────────────────────────────────
function PasoPagos({ planillaId, totalNeto, cuentas, estado, existingPagos, onPagada, onBack }) {
  const [pagos, setPagos] = useState([{ cuenta_id: '', monto: '', referencia: '' }]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (pagos.length === 1 && !pagos[0].cuenta_id && cuentas.length > 0) {
      setPagos([{ cuenta_id: cuentas[0].id, monto: totalNeto.toFixed(2), referencia: '' }]);
    }
  }, [cuentas, totalNeto]); // eslint-disable-line

  const suma = pagos.reduce((s, p) => s + (parseFloat(p.monto) || 0), 0);
  const diferencia = +(totalNeto - suma).toFixed(2);
  const coincide = Math.abs(diferencia) < 0.01;

  const actualizar = (i, campo, valor) => {
    setPagos(prev => { const arr = [...prev]; arr[i] = {...arr[i], [campo]: valor}; return arr; });
  };
  const agregar = () => setPagos(prev => [...prev, { cuenta_id: '', monto: '', referencia: '' }]);
  const eliminar = (i) => setPagos(prev => prev.filter((_,k) => k !== i));

  const handlePagar = async () => {
    if (!coincide) { toast.error(`La suma de pagos no coincide con el total. Diferencia: ${fmt(diferencia)}`); return; }
    if (!window.confirm(`¿Pagar ${fmt(totalNeto)} con ${pagos.length} medio(s)?\n\nSe generarán egresos reales en las cuentas seleccionadas.`)) return;
    setSaving(true);
    try {
      await pagarPlanillaQuincena(planillaId, {
        pagos: pagos.map(p => ({
          cuenta_id: parseInt(p.cuenta_id),
          monto: parseFloat(p.monto),
          referencia: p.referencia || null,
        })),
      });
      toast.success('Planilla pagada exitosamente');
      onPagada();
    } catch (e) {
      toast.error(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Error al pagar');
    } finally { setSaving(false); }
  };

  const handleAnular = async () => {
    if (!window.confirm('¿Anular el pago? Se revertirán los egresos en las cuentas y los adelantos volverán a pendientes.')) return;
    setSaving(true);
    try {
      await anularPagoPlanillaQuincena(planillaId);
      toast.success('Pago anulado. Planilla vuelve a aprobada.');
      onPagada();
    } catch (e) {
      toast.error(typeof e.response?.data?.detail === 'string' ? e.response.data.detail : 'Error');
    } finally { setSaving(false); }
  };

  if (estado === 'pagada') {
    return (
      <div className="bg-card rounded-xl border border-border p-6 space-y-4">
        <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-md p-4 flex items-center gap-3">
          <Check size={20} className="text-emerald-600"/>
          <div>
            <div className="font-semibold text-emerald-700">Planilla pagada</div>
            <div className="text-xs text-muted-foreground mt-0.5">Los egresos ya se generaron en las cuentas.</div>
          </div>
        </div>
        <div>
          <h3 className="text-sm font-semibold mb-2">Medios de pago aplicados:</h3>
          <table className="w-full text-sm border border-border rounded">
            <thead className="bg-muted/40">
              <tr>
                <th className="text-left px-3 py-2 text-xs font-medium">Cuenta</th>
                <th className="text-left px-3 py-2 text-xs font-medium">Referencia</th>
                <th className="text-right px-3 py-2 text-xs font-medium">Monto</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {existingPagos.map(p => (
                <tr key={p.id}>
                  <td className="px-3 py-2">{p.cuenta_nombre}</td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">{p.referencia || '—'}</td>
                  <td className="px-3 py-2 text-right font-mono">{fmt(p.monto)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex justify-between pt-2 border-t border-border">
          <button onClick={onBack} className="inline-flex items-center gap-1.5 px-3 py-2 text-sm rounded-md border border-border hover:bg-muted">
            <ChevronLeft size={14}/> Ver tabla
          </button>
          <button onClick={handleAnular} disabled={saving}
            className="inline-flex items-center gap-1.5 bg-red-600 text-white px-3 py-2 text-sm font-medium rounded-md hover:bg-red-700 disabled:opacity-50">
            {saving ? 'Anulando…' : 'Anular pago'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-card rounded-xl border border-border p-6 space-y-5">
      <h2 className="text-lg font-semibold flex items-center gap-2"><CreditCard size={18}/> Medios de pago</h2>
      <div className="bg-muted/30 rounded-md p-3 flex items-center justify-between">
        <span className="text-sm">Total a pagar:</span>
        <span className="text-lg font-bold font-mono">{fmt(totalNeto)}</span>
      </div>
      <div className="space-y-2">
        {pagos.map((p, i) => (
          <div key={i} className="grid grid-cols-12 gap-2 items-center">
            <select value={p.cuenta_id} onChange={e => actualizar(i, 'cuenta_id', e.target.value)}
              className="col-span-5 px-3 py-2 text-sm rounded-md border border-border bg-background">
              <option value="">— Cuenta —</option>
              {cuentas.map(c => <option key={c.id} value={c.id}>{c.nombre} ({fmt(c.saldo_actual)})</option>)}
            </select>
            <input type="number" step="0.01" min="0" placeholder="Monto" value={p.monto}
              onChange={e => actualizar(i, 'monto', e.target.value)}
              className="col-span-3 px-3 py-2 text-sm rounded-md border border-border bg-background font-mono" />
            <input type="text" placeholder="Referencia (N° op, cheque)" value={p.referencia}
              onChange={e => actualizar(i, 'referencia', e.target.value)}
              className="col-span-3 px-3 py-2 text-sm rounded-md border border-border bg-background" />
            <button onClick={() => eliminar(i)} disabled={pagos.length === 1}
              className="col-span-1 h-9 flex items-center justify-center rounded-md hover:bg-red-500/10 text-red-600 disabled:opacity-30">
              <Trash2 size={14}/>
            </button>
          </div>
        ))}
        <button onClick={agregar} type="button"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md border border-dashed border-border hover:bg-muted">
          <Plus size={12}/> Agregar otro medio
        </button>
      </div>
      <div className={`rounded-md p-3 text-sm ${coincide ? 'bg-emerald-500/5 border border-emerald-500/20' : 'bg-amber-500/5 border border-amber-500/20'}`}>
        Suma de medios: <strong className="font-mono">{fmt(suma)}</strong>
        {!coincide && <span className="ml-2 text-amber-700">· Diferencia: <strong>{fmt(diferencia)}</strong></span>}
        {coincide && <span className="ml-2 text-emerald-700">✓ coincide con total</span>}
      </div>
      <div className="flex justify-between pt-2 border-t border-border">
        <button onClick={onBack} className="inline-flex items-center gap-1.5 px-3 py-2 text-sm rounded-md border border-border hover:bg-muted">
          <ChevronLeft size={14}/> Volver
        </button>
        <button onClick={handlePagar} disabled={saving || !coincide}
          className="inline-flex items-center gap-1.5 bg-emerald-600 text-white px-4 py-2 text-sm font-medium rounded-md hover:bg-emerald-700 disabled:opacity-50"
          data-testid="btn-pagar-planilla">
          <Check size={14}/> {saving ? 'Pagando…' : 'Aprobar y pagar'}
        </button>
      </div>
    </div>
  );
}

function StepIndicator({ step }) {
  const steps = [
    { n: 1, label: 'Período' },
    { n: 2, label: 'Cálculo' },
    { n: 3, label: 'Pago' },
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
