import React, { useState, useEffect, useCallback } from 'react';
import { Plus, Pencil, Trash2, X, Users, Calculator, Check, ChevronDown, ChevronUp } from 'lucide-react';
import { toast } from 'sonner';
import {
  getTrabajadores, createTrabajador, updateTrabajador, deleteTrabajador,
  previewCalculosTrabajador, getAfps, getUnidadesInternas, getAjustesPlanilla,
} from '../services/api';
import { useEmpresa } from '../context/EmpresaContext';

const AREAS = ['ADMINISTRACION', 'PRODUCCION', 'VENTAS', 'MARKETING'];

const fmt = (v) => `S/ ${Number(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const emptyForm = {
  dni: '', nombre: '', area: 'ADMINISTRACION',
  unidad_interna_id: '',
  sueldo_planilla: 0, sueldo_basico: 0,
  horas_quincenales: 120,
  asignacion_familiar: false,
  porcentaje_planilla: 100,
  afp_id: '',
  fecha_ingreso: '',
  activo: true,
  notas: '',
};

export default function Trabajadores() {
  const { empresaActual } = useEmpresa();
  const [trabajadores, setTrabajadores] = useState([]);
  const [afps, setAfps] = useState([]);
  const [unidades, setUnidades] = useState([]);
  const [ajustes, setAjustes] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filtroArea, setFiltroArea] = useState('');
  const [filtroActivo, setFiltroActivo] = useState(true);

  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [showSueldoDetalle, setShowSueldoDetalle] = useState(false);
  const [calculos, setCalculos] = useState(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    if (!empresaActual) return;
    setLoading(true);
    try {
      const params = {};
      if (filtroArea) params.area = filtroArea;
      if (filtroActivo !== null) params.activo = filtroActivo;
      const [t, a, u, aj] = await Promise.all([
        getTrabajadores(params),
        getAfps({ activo: true }),
        getUnidadesInternas(),
        getAjustesPlanilla(),
      ]);
      setTrabajadores(t.data || []);
      setAfps(a.data || []);
      setUnidades(u.data || []);
      setAjustes(aj.data);
    } catch (e) {
      toast.error('Error cargando trabajadores');
    } finally { setLoading(false); }
  }, [empresaActual, filtroArea, filtroActivo]);

  useEffect(() => { load(); }, [load]);

  // Recalcular preview cuando cambian campos relevantes del form
  useEffect(() => {
    if (!showForm) { setCalculos(null); return; }
    const t = setTimeout(async () => {
      try {
        const payload = {
          ...form,
          sueldo_planilla: parseFloat(form.sueldo_planilla) || 0,
          sueldo_basico: parseFloat(form.sueldo_basico) || 0,
          horas_quincenales: parseInt(form.horas_quincenales) || 120,
          porcentaje_planilla: parseFloat(form.porcentaje_planilla) || 100,
          unidad_interna_id: form.unidad_interna_id ? parseInt(form.unidad_interna_id) : null,
          afp_id: form.afp_id ? parseInt(form.afp_id) : null,
          fecha_ingreso: form.fecha_ingreso || null,
        };
        const r = await previewCalculosTrabajador(payload);
        setCalculos(r.data);
      } catch { /* silencio — el form aún puede estar incompleto */ }
    }, 250);
    return () => clearTimeout(t);
  }, [form, showForm]);

  const openNew = () => {
    setEditing(null);
    setForm({ ...emptyForm, horas_quincenales: ajustes?.horas_quincena_default || 120 });
    setShowSueldoDetalle(false);
    setShowForm(true);
  };

  const openEdit = (t) => {
    setEditing(t);
    setForm({
      dni: t.dni || '',
      nombre: t.nombre || '',
      area: t.area || 'ADMINISTRACION',
      unidad_interna_id: t.unidad_interna_id ? String(t.unidad_interna_id) : '',
      sueldo_planilla: t.sueldo_planilla || 0,
      sueldo_basico: t.sueldo_basico || 0,
      horas_quincenales: t.horas_quincenales || 120,
      asignacion_familiar: !!t.asignacion_familiar,
      porcentaje_planilla: t.porcentaje_planilla || 100,
      afp_id: t.afp_id ? String(t.afp_id) : '',
      fecha_ingreso: t.fecha_ingreso ? String(t.fecha_ingreso).split('T')[0] : '',
      activo: t.activo !== false,
      notas: t.notas || '',
    });
    setShowSueldoDetalle(
      (parseFloat(t.sueldo_planilla) || 0) !== 0 && (parseFloat(t.sueldo_basico) || 0) !== 0
    );
    setShowForm(true);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (saving) return;
    if (!form.nombre.trim()) { toast.error('Nombre requerido'); return; }
    const payload = {
      ...form,
      dni: form.dni || null,
      sueldo_planilla: parseFloat(form.sueldo_planilla) || 0,
      sueldo_basico: parseFloat(form.sueldo_basico) || 0,
      horas_quincenales: parseInt(form.horas_quincenales) || 120,
      porcentaje_planilla: parseFloat(form.porcentaje_planilla) || 100,
      unidad_interna_id: form.unidad_interna_id ? parseInt(form.unidad_interna_id) : null,
      afp_id: form.afp_id ? parseInt(form.afp_id) : null,
      fecha_ingreso: form.fecha_ingreso || null,
      notas: form.notas || null,
    };
    setSaving(true);
    try {
      if (editing) {
        await updateTrabajador(editing.id, payload);
        toast.success('Trabajador actualizado');
      } else {
        await createTrabajador(payload);
        toast.success('Trabajador creado');
      }
      setShowForm(false);
      load();
    } catch (err) {
      const msg = typeof err.response?.data?.detail === 'string' ? err.response.data.detail : 'Error al guardar';
      toast.error(msg);
    } finally { setSaving(false); }
  };

  const handleDelete = async (t) => {
    if (!window.confirm(`¿Eliminar a "${t.nombre}"?`)) return;
    try {
      await deleteTrabajador(t.id);
      toast.success('Trabajador eliminado');
      load();
    } catch (err) {
      toast.error('Error al eliminar');
    }
  };

  const sueldoBasicoTotal = (parseFloat(form.sueldo_planilla) || 0) + (parseFloat(form.sueldo_basico) || 0);

  return (
    <div className="max-w-[1200px] space-y-6" data-testid="trabajadores-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground tracking-tight flex items-center gap-2">
            <Users size={22} /> Trabajadores
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Empleados en planilla. Cada uno con su configuración de sueldo, horas, asignación familiar y AFP.
          </p>
        </div>
        <button onClick={openNew}
          className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-emerald-700 shadow-sm"
          data-testid="nuevo-trabajador-btn">
          <Plus size={16} /> Nuevo Trabajador
        </button>
      </div>

      {/* Filtros */}
      <div className="flex gap-2 flex-wrap">
        <select value={filtroArea} onChange={e => setFiltroArea(e.target.value)}
          className="px-3 py-2 text-sm rounded-md border border-border bg-background">
          <option value="">Todas las áreas</option>
          {AREAS.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
        <select value={filtroActivo === null ? 'all' : filtroActivo ? 'true' : 'false'}
          onChange={e => { const v = e.target.value; setFiltroActivo(v === 'all' ? null : v === 'true'); }}
          className="px-3 py-2 text-sm rounded-md border border-border bg-background">
          <option value="true">Solo activos</option>
          <option value="false">Solo inactivos</option>
          <option value="all">Todos</option>
        </select>
      </div>

      {/* Tabla */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 border-b border-border">
            <tr>
              <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase">DNI / Nombre</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Área</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Unidad</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Sueldo total</th>
              <th className="text-center px-4 py-3 text-xs font-medium text-muted-foreground uppercase">%</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase">AFP</th>
              <th className="text-center px-4 py-3 text-xs font-medium text-muted-foreground uppercase">AF</th>
              <th className="w-24"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {loading ? (
              <tr><td colSpan={8} className="py-10 text-center text-muted-foreground">Cargando…</td></tr>
            ) : trabajadores.length === 0 ? (
              <tr><td colSpan={8} className="py-10 text-center text-muted-foreground">
                Sin trabajadores. Crea el primero con el botón <strong>Nuevo Trabajador</strong>.
              </td></tr>
            ) : trabajadores.map(t => (
              <tr key={t.id} className="hover:bg-muted/30" data-testid={`trabajador-row-${t.id}`}>
                <td className="px-4 py-3">
                  <div className="font-medium text-foreground">{t.nombre}</div>
                  {t.dni && <div className="text-[11px] text-muted-foreground font-mono">DNI {t.dni}</div>}
                </td>
                <td className="px-4 py-3 text-xs text-muted-foreground">{t.area}</td>
                <td className="px-4 py-3 text-xs">{t.unidad_interna_nombre || <span className="text-muted-foreground">—</span>}</td>
                <td className="px-4 py-3 text-right font-mono text-sm">{fmt(t.sueldo_basico_total)}</td>
                <td className="px-4 py-3 text-center text-xs">{t.porcentaje_planilla}%</td>
                <td className="px-4 py-3 text-xs">{t.afp_nombre || <span className="text-muted-foreground">—</span>}</td>
                <td className="px-4 py-3 text-center">
                  {t.asignacion_familiar ? <Check size={14} className="inline text-emerald-600"/> : <span className="text-muted-foreground">—</span>}
                </td>
                <td className="px-3 py-3 text-right">
                  <div className="inline-flex gap-1">
                    <button onClick={() => openEdit(t)}
                      className="h-7 w-7 flex items-center justify-center rounded-md hover:bg-muted text-muted-foreground hover:text-foreground"
                      title="Editar" data-testid={`edit-${t.id}`}>
                      <Pencil size={14} />
                    </button>
                    <button onClick={() => handleDelete(t)}
                      className="h-7 w-7 flex items-center justify-center rounded-md hover:bg-red-500/10 text-red-600"
                      title="Eliminar">
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal form */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
             onClick={() => !saving && setShowForm(false)}>
          <form onSubmit={handleSave} onClick={e => e.stopPropagation()}
                className="bg-card text-foreground rounded-xl shadow-2xl w-full max-w-4xl max-h-[92vh] flex flex-col border border-border">
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
              <h2 className="text-base font-semibold">{editing ? `Editar: ${editing.nombre}` : 'Nuevo Trabajador'}</h2>
              <button type="button" onClick={() => setShowForm(false)}
                className="h-8 w-8 flex items-center justify-center rounded-md hover:bg-muted">
                <X size={18} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto grid grid-cols-1 lg:grid-cols-5 gap-0">
              {/* Form (3 columnas) */}
              <div className="lg:col-span-3 p-5 space-y-5 border-r border-border">
                <section>
                  <h3 className="text-xs font-semibold uppercase text-muted-foreground mb-2">Datos básicos</h3>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-medium text-muted-foreground block mb-1">DNI</label>
                      <input type="text" maxLength={15} value={form.dni}
                        onChange={e => setForm({...form, dni: e.target.value})}
                        className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background font-mono"
                        data-testid="form-dni" />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-muted-foreground block mb-1">Nombre *</label>
                      <input type="text" required value={form.nombre}
                        onChange={e => setForm({...form, nombre: e.target.value})}
                        className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background"
                        data-testid="form-nombre" />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-muted-foreground block mb-1">Área *</label>
                      <select required value={form.area}
                        onChange={e => setForm({...form, area: e.target.value})}
                        className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background"
                        data-testid="form-area">
                        {AREAS.map(a => <option key={a} value={a}>{a}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="text-xs font-medium text-muted-foreground block mb-1">Unidad interna</label>
                      <select value={form.unidad_interna_id}
                        onChange={e => setForm({...form, unidad_interna_id: e.target.value})}
                        className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background"
                        data-testid="form-unidad">
                        <option value="">— Sin unidad —</option>
                        {unidades.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}
                      </select>
                    </div>
                  </div>
                </section>

                <section>
                  <h3 className="text-xs font-semibold uppercase text-muted-foreground mb-2">Sueldo</h3>
                  <div>
                    <label className="text-xs font-medium text-muted-foreground block mb-1">Sueldo básico total (S/)</label>
                    <div className="flex gap-2">
                      <input type="number" step="0.01" min="0"
                        value={sueldoBasicoTotal}
                        readOnly={showSueldoDetalle}
                        onChange={e => {
                          const v = parseFloat(e.target.value) || 0;
                          setForm({...form, sueldo_planilla: v, sueldo_basico: 0});
                          setShowSueldoDetalle(false);
                        }}
                        className="flex-1 px-3 py-2 text-sm rounded-md border border-border bg-background font-mono"
                        data-testid="form-sueldo-total" />
                      <button type="button" onClick={() => setShowSueldoDetalle(!showSueldoDetalle)}
                        className="inline-flex items-center gap-1 px-3 py-2 text-xs rounded-md border border-border hover:bg-muted"
                        data-testid="toggle-sueldo-detalle">
                        {showSueldoDetalle ? <><ChevronUp size={14}/> Ocultar desglose</> : <><ChevronDown size={14}/> Desglosar</>}
                      </button>
                    </div>
                  </div>
                  {showSueldoDetalle && (
                    <div className="grid grid-cols-2 gap-3 mt-3 bg-muted/30 p-3 rounded-md border border-border">
                      <div>
                        <label className="text-xs font-medium text-muted-foreground block mb-1">Sueldo planilla</label>
                        <input type="number" step="0.01" min="0"
                          value={form.sueldo_planilla}
                          onChange={e => setForm({...form, sueldo_planilla: e.target.value})}
                          className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background font-mono"
                          data-testid="form-sueldo-planilla" />
                        <p className="text-[10px] text-muted-foreground mt-1">Monto que aparece en boleta (base AFP).</p>
                      </div>
                      <div>
                        <label className="text-xs font-medium text-muted-foreground block mb-1">Sueldo básico</label>
                        <input type="number" step="0.01" min="0"
                          value={form.sueldo_basico}
                          onChange={e => setForm({...form, sueldo_basico: e.target.value})}
                          className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background font-mono"
                          data-testid="form-sueldo-basico" />
                        <p className="text-[10px] text-muted-foreground mt-1">Complemento fuera de planilla.</p>
                      </div>
                      <div className="col-span-2 text-[11px] text-emerald-700 dark:text-emerald-400 font-medium">
                        Total = Planilla + Básico = <span className="font-mono">{fmt(sueldoBasicoTotal)}</span>
                      </div>
                    </div>
                  )}
                </section>

                <section>
                  <h3 className="text-xs font-semibold uppercase text-muted-foreground mb-2">Configuración</h3>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-medium text-muted-foreground block mb-1">Horas quincenales *</label>
                      <input type="number" required min="1"
                        value={form.horas_quincenales}
                        onChange={e => setForm({...form, horas_quincenales: e.target.value})}
                        className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background font-mono"
                        data-testid="form-horas" />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-muted-foreground block mb-1">% Planilla *</label>
                      <select value={form.porcentaje_planilla}
                        onChange={e => setForm({...form, porcentaje_planilla: e.target.value})}
                        className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background"
                        data-testid="form-pct">
                        <option value={100}>100%</option>
                        <option value={50}>50%</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs font-medium text-muted-foreground block mb-1">AFP</label>
                      <select value={form.afp_id}
                        onChange={e => setForm({...form, afp_id: e.target.value})}
                        className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background"
                        data-testid="form-afp">
                        <option value="">— Sin AFP —</option>
                        {afps.map(a => <option key={a.id} value={a.id}>{a.nombre}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="text-xs font-medium text-muted-foreground block mb-1">Fecha ingreso</label>
                      <input type="date" value={form.fecha_ingreso}
                        onChange={e => setForm({...form, fecha_ingreso: e.target.value})}
                        className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background" />
                    </div>
                    <div className="col-span-2 flex items-center gap-2 pt-1">
                      <input type="checkbox" id="af" checked={form.asignacion_familiar}
                        onChange={e => setForm({...form, asignacion_familiar: e.target.checked})}
                        className="h-4 w-4" data-testid="form-asig-fam" />
                      <label htmlFor="af" className="text-sm">Recibe asignación familiar ({ajustes?.asignacion_familiar_pct}% del sueldo mínimo)</label>
                    </div>
                    <div className="col-span-2 flex items-center gap-2">
                      <input type="checkbox" id="activo-chk" checked={form.activo}
                        onChange={e => setForm({...form, activo: e.target.checked})}
                        className="h-4 w-4" />
                      <label htmlFor="activo-chk" className="text-sm">Activo</label>
                    </div>
                  </div>
                </section>

                <section>
                  <label className="text-xs font-medium text-muted-foreground block mb-1">Notas</label>
                  <textarea rows={2} value={form.notas}
                    onChange={e => setForm({...form, notas: e.target.value})}
                    className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background" />
                </section>
              </div>

              {/* Cuadro de cálculos (2 columnas) */}
              <div className="lg:col-span-2 p-5 bg-muted/20">
                <h3 className="text-xs font-semibold uppercase text-muted-foreground mb-3 flex items-center gap-1.5">
                  <Calculator size={14} /> Cálculos derivados
                </h3>
                {!calculos ? (
                  <p className="text-sm text-muted-foreground">Completa el formulario para ver los cálculos en vivo.</p>
                ) : (
                  <div className="space-y-4 text-sm">
                    <div>
                      <div className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1">Horas</div>
                      <div className="bg-card rounded-md border border-border divide-y divide-border">
                        <Row label="Hora simple" value={fmt(calculos.hora_simple)} hint="sueldo_total / 30 / 8" />
                        <Row label="Hora extra 25%" value={fmt(calculos.hora_extra_25)} hint="hora simple × 1.25" />
                        <Row label="Hora extra 35%" value={fmt(calculos.hora_extra_35)} hint="hora simple × 1.35" />
                      </div>
                    </div>
                    <div>
                      <div className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1">Beneficios / Aportes</div>
                      <div className="bg-card rounded-md border border-border divide-y divide-border">
                        <Row label="Asignación familiar"
                             value={fmt(calculos.asignacion_familiar_monto)}
                             hint={`${calculos.meta.asig_fam_pct}% × S/ ${calculos.meta.sueldo_minimo}`}
                             active={form.asignacion_familiar} />
                        <Row label="Base aporte AFP"
                             value={fmt(calculos.base_afp)}
                             hint="sueldo_planilla + asignación familiar" />
                        <Row label="Aporte obligatorio AFP"
                             value={fmt(calculos.aporte_afp)}
                             hint={`${calculos.meta.afp_aporte_pct}% × base`}
                             active={!!form.afp_id} />
                        <Row label="Prima de seguros"
                             value={fmt(calculos.prima_seguros)}
                             hint={`${calculos.meta.afp_prima_pct}% × base`}
                             active={!!form.afp_id} />
                      </div>
                    </div>
                    {calculos.meta.afp_nombre && (
                      <div className="text-[10px] text-muted-foreground">
                        AFP: <span className="font-medium text-foreground">{calculos.meta.afp_nombre}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            <div className="flex justify-end gap-2 px-5 py-3 border-t border-border bg-muted/20">
              <button type="button" onClick={() => setShowForm(false)}
                className="px-3 py-1.5 text-sm rounded-md border border-border hover:bg-muted">
                Cancelar
              </button>
              <button type="submit" disabled={saving}
                className="inline-flex items-center gap-1.5 bg-emerald-600 text-white px-4 py-1.5 text-sm font-medium rounded-md hover:bg-emerald-700 disabled:opacity-50"
                data-testid="form-guardar">
                <Check size={14} /> {saving ? 'Guardando…' : 'Guardar trabajador'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

function Row({ label, value, hint, active = true }) {
  return (
    <div className={`flex items-center justify-between px-3 py-2 ${active ? '' : 'opacity-40'}`}>
      <div className="min-w-0 flex-1">
        <div className="text-xs font-medium text-foreground truncate">{label}</div>
        {hint && <div className="text-[10px] text-muted-foreground truncate">{hint}</div>}
      </div>
      <div className="text-sm font-mono font-semibold text-emerald-700 dark:text-emerald-400 ml-2 whitespace-nowrap">{value}</div>
    </div>
  );
}
