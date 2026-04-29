import React, { useState, useEffect, useCallback } from 'react';
import { Plus, Pencil, Trash2, X, Users, Calculator, Check, ChevronDown, ChevronUp, CreditCard, Scissors, Search } from 'lucide-react';
import { toast } from 'sonner';
import {
  getTrabajadores, createTrabajador, updateTrabajador, deleteTrabajador,
  previewCalculosTrabajador, calcInversaTrabajador,
  getAfps, getUnidadesInternas, getAjustesPlanilla,
  getCuentasFinancieras, getMediosPagoTrabajador, setMediosPagoTrabajador,
  getTarifasDestajoTrabajador, setTarifasDestajoTrabajador,
  getPersonasProduccionDisponibles, getServiciosProduccion,
} from '../services/api';
import { useEmpresa } from '../context/EmpresaContext';

const AREAS = ['ADMINISTRACION', 'PRODUCCION', 'VENTAS', 'MARKETING'];

const TIPOS_PAGO = [
  { value: 'planilla', label: 'Planilla (jornal)', hint: 'Sueldo fijo por quincena basado en horas' },
  { value: 'destajo',  label: 'Destajo',            hint: 'Pago por prendas trabajadas (sin sueldo fijo)' },
  { value: 'mixto',    label: 'Mixto',              hint: 'Sueldo fijo + pago por prendas' },
];

const fmt = (v) => `S/ ${Number(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const emptyForm = {
  dni: '', nombre: '', area: 'ADMINISTRACION',
  unidad_interna_id: '',
  sueldo_planilla: 0, sueldo_basico: 0,
  bono: 0,
  horas_quincenales: 120,
  horas_extras_25_default: 0,
  horas_extras_35_default: 0,
  asignacion_familiar: false,
  porcentaje_planilla: 100,
  afp_id: '',
  fecha_ingreso: '',
  activo: true,
  notas: '',
  tipo_pago: 'planilla',
  prod_persona_id: '',
};

export default function Trabajadores() {
  const { empresaActual } = useEmpresa();
  const [trabajadores, setTrabajadores] = useState([]);
  const [afps, setAfps] = useState([]);
  const [unidades, setUnidades] = useState([]);
  const [cuentas, setCuentas] = useState([]);
  const [ajustes, setAjustes] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filtroArea, setFiltroArea] = useState('');
  const [filtroActivo, setFiltroActivo] = useState(true);
  const [busqueda, setBusqueda] = useState('');

  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [showSueldoDetalle, setShowSueldoDetalle] = useState(false);
  // Calculadora inversa: ingresa sueldo objetivo + horas → calcula básico
  const [sueldoObjetivo, setSueldoObjetivo] = useState('');
  const [calculandoInversa, setCalculandoInversa] = useState(false);

  const handleAutoCalcularBasico = async () => {
    const obj = parseFloat(sueldoObjetivo);
    if (!obj || obj <= 0) { toast.error('Ingresa el sueldo objetivo'); return; }
    setCalculandoInversa(true);
    try {
      // Asignación familiar: si está marcada, usar el monto del preview o calcular como (sueldo_minimo × asig_fam_pct)
      const asig_fam_monto = form.asignacion_familiar
        ? (calculos?.asignacion_familiar_monto || (ajustes ? (parseFloat(ajustes.sueldo_minimo) || 0) * (parseFloat(ajustes.asignacion_familiar_pct) || 0) / 100 : 0))
        : 0;
      const r = await calcInversaTrabajador({
        sueldo_objetivo: obj,
        horas_quincenales: parseInt(form.horas_quincenales) || 120,
        horas_extras_25: parseFloat(form.horas_extras_25_default) || 0,
        horas_extras_35: parseFloat(form.horas_extras_35_default) || 0,
        bono: parseFloat(form.bono) || 0,
        asignacion_familiar_monto: asig_fam_monto,
      });
      // Si tiene desglose abierto, lo pone todo en sueldo_basico (complemento) y deja planilla en 0
      setForm(prev => ({
        ...prev,
        sueldo_planilla: 0,
        sueldo_basico: r.data.sueldo_basico_total,
      }));
      toast.success(`Sueldo básico = S/ ${r.data.sueldo_basico_total.toFixed(2)} (total mensual S/ ${r.data.sueldo_total_calculado.toFixed(2)})`);
    } catch (e) {
      toast.error('Error en el cálculo');
    } finally { setCalculandoInversa(false); }
  };
  const [calculos, setCalculos] = useState(null);
  const [saving, setSaving] = useState(false);
  const [medios, setMedios] = useState([]);  // Medios de pago default del trabajador
  const [tarifasDestajo, setTarifasDestajo] = useState([]);  // Tarifas destajo del trabajador
  const [personasProd, setPersonasProd] = useState([]);  // Para linkear
  const [serviciosProd, setServiciosProd] = useState([]);  // Catálogo

  const load = useCallback(async () => {
    if (!empresaActual) return;
    setLoading(true);
    try {
      const params = {};
      if (filtroArea) params.area = filtroArea;
      if (filtroActivo !== null) params.activo = filtroActivo;
      // Cada endpoint con su propio catch para que un fallo no tumbe la página entera
      const [t, a, u, aj, c, sp, pp] = await Promise.all([
        getTrabajadores(params).catch(() => ({ data: [] })),
        getAfps({ activo: true }).catch(() => ({ data: [] })),
        getUnidadesInternas().catch(() => ({ data: [] })),
        getAjustesPlanilla().catch(() => ({ data: null })),
        getCuentasFinancieras().catch(() => ({ data: [] })),
        getServiciosProduccion().catch(() => ({ data: [] })),
        getPersonasProduccionDisponibles().catch(() => ({ data: [] })),
      ]);
      setTrabajadores(t.data || []);
      setAfps(a.data || []);
      setUnidades(u.data || []);
      setAjustes(aj.data);
      setCuentas((c.data || []).filter(ct => ct.activo !== false));
      setServiciosProd(sp.data || []);
      setPersonasProd(pp.data || []);
    } catch (e) {
      console.error('Error cargando trabajadores', e);
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
          bono: parseFloat(form.bono) || 0,
          horas_quincenales: parseInt(form.horas_quincenales) || 120,
          horas_extras_25_default: parseFloat(form.horas_extras_25_default) || 0,
          horas_extras_35_default: parseFloat(form.horas_extras_35_default) || 0,
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
    setMedios([]);
    setTarifasDestajo([]);
    setShowForm(true);
  };

  const openEdit = async (t) => {
    setEditing(t);
    setForm({
      dni: t.dni || '',
      nombre: t.nombre || '',
      area: t.area || 'ADMINISTRACION',
      unidad_interna_id: t.unidad_interna_id ? String(t.unidad_interna_id) : '',
      sueldo_planilla: t.sueldo_planilla || 0,
      sueldo_basico: t.sueldo_basico || 0,
      bono: t.bono || 0,
      horas_quincenales: t.horas_quincenales || 120,
      horas_extras_25_default: t.horas_extras_25_default || 0,
      horas_extras_35_default: t.horas_extras_35_default || 0,
      asignacion_familiar: !!t.asignacion_familiar,
      porcentaje_planilla: t.porcentaje_planilla || 100,
      afp_id: t.afp_id ? String(t.afp_id) : '',
      fecha_ingreso: t.fecha_ingreso ? String(t.fecha_ingreso).split('T')[0] : '',
      activo: t.activo !== false,
      notas: t.notas || '',
      tipo_pago: t.tipo_pago || 'planilla',
      prod_persona_id: t.prod_persona_id || '',
    });
    setShowSueldoDetalle(
      (parseFloat(t.sueldo_planilla) || 0) !== 0 && (parseFloat(t.sueldo_basico) || 0) !== 0
    );
    // Cargar medios de pago + tarifas destajo
    try {
      const [rm, rt] = await Promise.all([
        getMediosPagoTrabajador(t.id),
        getTarifasDestajoTrabajador(t.id).catch(() => ({ data: [] })),
      ]);
      setMedios((rm.data || []).map(m => ({ cuenta_id: m.cuenta_id, porcentaje: m.porcentaje })));
      setTarifasDestajo((rt.data || []).map(x => ({
        servicio_nombre: x.servicio_nombre,
        tarifa: x.tarifa,
      })));
    } catch {
      setMedios([]);
      setTarifasDestajo([]);
    }
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
      bono: parseFloat(form.bono) || 0,
      horas_quincenales: parseInt(form.horas_quincenales) || 120,
      horas_extras_25_default: parseFloat(form.horas_extras_25_default) || 0,
      horas_extras_35_default: parseFloat(form.horas_extras_35_default) || 0,
      porcentaje_planilla: parseFloat(form.porcentaje_planilla) || 100,
      unidad_interna_id: form.unidad_interna_id ? parseInt(form.unidad_interna_id) : null,
      afp_id: form.afp_id ? parseInt(form.afp_id) : null,
      fecha_ingreso: form.fecha_ingreso || null,
      notas: form.notas || null,
      tipo_pago: form.tipo_pago || 'planilla',
      prod_persona_id: form.prod_persona_id || null,
    };
    // Validar medios de pago default
    const mediosValidos = medios.filter(m => m.cuenta_id && parseFloat(m.porcentaje) > 0);
    const sumaPct = mediosValidos.reduce((s, m) => s + (parseFloat(m.porcentaje) || 0), 0);
    if (mediosValidos.length > 0 && Math.abs(sumaPct - 100) > 0.01) {
      toast.error(`La suma de porcentajes de medios de pago debe ser 100% (actual: ${sumaPct.toFixed(2)}%)`);
      return;
    }
    // Validar tarifas destajo: si tipo_pago incluye destajo, debe tener al menos una tarifa
    const requiereDestajo = payload.tipo_pago === 'destajo' || payload.tipo_pago === 'mixto';
    const tarifasValidas = tarifasDestajo.filter(
      x => x.servicio_nombre && parseFloat(x.tarifa) >= 0
    );
    if (requiereDestajo && tarifasValidas.length === 0) {
      toast.error(`Un trabajador "${payload.tipo_pago}" debe tener al menos una tarifa de destajo configurada`);
      return;
    }

    setSaving(true);
    try {
      let trabajadorId;
      if (editing) {
        await updateTrabajador(editing.id, payload);
        trabajadorId = editing.id;
        toast.success('Trabajador actualizado');
      } else {
        const r = await createTrabajador(payload);
        trabajadorId = r.data.id;
        toast.success('Trabajador creado');
      }
      // Guardar medios de pago + tarifas destajo en paralelo
      await Promise.all([
        setMediosPagoTrabajador(trabajadorId, mediosValidos.map(m => ({
          cuenta_id: parseInt(m.cuenta_id),
          porcentaje: parseFloat(m.porcentaje),
        }))),
        setTarifasDestajoTrabajador(trabajadorId, tarifasValidas.map(x => ({
          servicio_nombre: x.servicio_nombre,
          tarifa: parseFloat(x.tarifa),
        }))),
      ]);
      setShowForm(false);
      load();
    } catch (err) {
      const msg = typeof err.response?.data?.detail === 'string' ? err.response.data.detail : 'Error al guardar';
      toast.error(msg);
    } finally { setSaving(false); }
  };

  // Helpers para editar tarifas destajo
  const agregarTarifaDestajo = () => setTarifasDestajo(prev => [...prev, { servicio_nombre: '', tarifa: '' }]);
  const actualizarTarifaDestajo = (idx, campo, valor) => setTarifasDestajo(prev => {
    const arr = [...prev]; arr[idx] = { ...arr[idx], [campo]: valor }; return arr;
  });
  const eliminarTarifaDestajo = (idx) => setTarifasDestajo(prev => prev.filter((_, i) => i !== idx));

  const agregarMedio = () => setMedios(prev => [...prev, { cuenta_id: '', porcentaje: '' }]);
  const actualizarMedio = (idx, campo, valor) => setMedios(prev => {
    const arr = [...prev]; arr[idx] = { ...arr[idx], [campo]: valor }; return arr;
  });
  const eliminarMedio = (idx) => setMedios(prev => prev.filter((_, i) => i !== idx));

  const sumaPctMedios = medios.reduce((s, m) => s + (parseFloat(m.porcentaje) || 0), 0);
  const pctOk = medios.length === 0 || Math.abs(sumaPctMedios - 100) < 0.01;

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

  // Búsqueda local — quita acentos, ignora mayúsculas y matchea contra varios campos
  const norm = (s) => (s || '')
    .toString()
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase().trim();
  const q = norm(busqueda);
  const trabajadoresFiltrados = !q ? trabajadores : trabajadores.filter(t => {
    const haystack = [
      t.nombre, t.dni, t.area,
      t.unidad_interna_nombre, t.afp_nombre, t.afp_codigo,
      t.tipo_pago,
    ].map(norm).join(' ');
    return haystack.includes(q);
  });

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
      <div className="flex gap-2 flex-wrap items-center">
        <div className="relative flex-1 min-w-[260px] max-w-md">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none"/>
          <input
            type="text"
            value={busqueda}
            onChange={e => setBusqueda(e.target.value)}
            placeholder="Buscar por nombre, DNI, AFP, unidad…"
            className="w-full pl-9 pr-9 py-2 text-sm rounded-md border border-border bg-background focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500"
            data-testid="trabajadores-search"
          />
          {busqueda && (
            <button
              type="button"
              onClick={() => setBusqueda('')}
              className="absolute right-2 top-1/2 -translate-y-1/2 h-5 w-5 flex items-center justify-center rounded text-muted-foreground hover:bg-muted"
              title="Limpiar"
            >
              <X size={12}/>
            </button>
          )}
        </div>
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
        {busqueda && (
          <span className="text-xs text-muted-foreground" title="Resultados que coinciden con la búsqueda">
            {trabajadoresFiltrados.length} de {trabajadores.length}
          </span>
        )}
      </div>

      {/* Tabla */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 border-b border-border">
            <tr>
              <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase">DNI / Nombre</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Área</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Unidad</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-emerald-700 dark:text-emerald-400 uppercase" title="Sueldo total mensual esperado (básico + HE25 default + HE35 default × tarifas × 2)">Sueldo total</th>
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
            ) : trabajadoresFiltrados.length === 0 ? (
              <tr><td colSpan={8} className="py-10 text-center text-muted-foreground">
                No hay coincidencias para <strong>"{busqueda}"</strong>.
                <button onClick={() => setBusqueda('')} className="ml-2 text-emerald-600 hover:underline">Limpiar búsqueda</button>
              </td></tr>
            ) : trabajadoresFiltrados.map(t => (
              <tr key={t.id} className="hover:bg-muted/30" data-testid={`trabajador-row-${t.id}`}>
                <td className="px-4 py-3">
                  <div className="font-medium text-foreground">{t.nombre}</div>
                  {t.dni && <div className="text-[11px] text-muted-foreground font-mono">DNI {t.dni}</div>}
                </td>
                <td className="px-4 py-3 text-xs text-muted-foreground">{t.area}</td>
                <td className="px-4 py-3 text-xs">{t.unidad_interna_nombre || <span className="text-muted-foreground">—</span>}</td>
                <td className="px-4 py-3 text-right font-mono text-sm font-semibold text-emerald-700 dark:text-emerald-400" title={`Básico ${fmt(t.sueldo_basico_total)} + HE25 (${t.horas_extras_25_default || 0}h) + HE35 (${t.horas_extras_35_default || 0}h)`}>
                  {fmt(t.calculos?.sueldo_total_mensual_esperado ?? t.sueldo_basico_total)}
                </td>
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

                  {/* Calculadora inversa: sueldo objetivo → básico automático */}
                  <div className="mb-3 p-3 rounded-md border border-blue-200 dark:border-blue-900 bg-blue-50/60 dark:bg-blue-950/30">
                    <div className="text-[11px] font-semibold text-blue-700 dark:text-blue-400 mb-1.5">
                      💡 Auto-calcular básico desde sueldo objetivo
                    </div>
                    <div className="flex items-end gap-2">
                      <div className="flex-1">
                        <label className="text-[10px] text-muted-foreground block mb-0.5">Sueldo total mensual deseado</label>
                        <input type="number" step="0.01" min="0"
                          value={sueldoObjetivo}
                          onChange={e => setSueldoObjetivo(e.target.value)}
                          onWheel={(e) => e.currentTarget.blur()}
                          placeholder="Ej: 1500"
                          className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background font-mono" />
                      </div>
                      <button type="button"
                        onClick={handleAutoCalcularBasico}
                        disabled={calculandoInversa || !sueldoObjetivo}
                        className="px-3 py-2 rounded-md bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium disabled:opacity-50 whitespace-nowrap">
                        {calculandoInversa ? 'Calculando...' : 'Calcular básico'}
                      </button>
                    </div>
                    <p className="text-[10px] text-muted-foreground mt-1.5 leading-snug">
                      Usa <strong>{form.horas_quincenales || 120}h</strong> quincenales,
                      <strong> {form.horas_extras_25_default || 0}h</strong> extra 25% y
                      <strong> {form.horas_extras_35_default || 0}h</strong> extra 35%.
                      El sistema calculará el básico para que el total mensual sea ~el objetivo.
                    </p>
                  </div>

                  <div>
                    <label className="text-xs font-medium text-muted-foreground block mb-1">Sueldo básico total (S/)</label>
                    <div className="flex gap-2">
                      <input type="number" step="0.01" min="0"
                        value={sueldoBasicoTotal}
                        onChange={e => {
                          // Editar el total → todo va a "Sueldo básico" por defecto, planilla en 0.
                          // Si el usuario después abre el desglose y mete algo en planilla,
                          // se descontará de básico para mantener este total fijo.
                          const v = parseFloat(e.target.value) || 0;
                          setForm({...form, sueldo_planilla: 0, sueldo_basico: v});
                        }}
                        className="flex-1 px-3 py-2 text-sm rounded-md border border-border bg-background font-mono"
                        data-testid="form-sueldo-total" />
                      <button type="button" onClick={() => setShowSueldoDetalle(!showSueldoDetalle)}
                        className="inline-flex items-center gap-1 px-3 py-2 text-xs rounded-md border border-border hover:bg-muted"
                        data-testid="toggle-sueldo-detalle">
                        {showSueldoDetalle ? <><ChevronUp size={14}/> Ocultar desglose</> : <><ChevronDown size={14}/> Desglosar</>}
                      </button>
                    </div>
                    <p className="text-[10px] text-muted-foreground mt-1">
                      Por defecto todo va a <strong>Sueldo básico</strong>. Si añadís algo a <strong>Sueldo planilla</strong> (en el desglose), se resta automáticamente del básico para mantener este total fijo.
                    </p>
                  </div>
                  {showSueldoDetalle && (
                    <div className="grid grid-cols-2 gap-3 mt-3 bg-muted/30 p-3 rounded-md border border-border">
                      <div>
                        <label className="text-xs font-medium text-muted-foreground block mb-1">Sueldo planilla</label>
                        <input type="number" step="0.01" min="0"
                          value={form.sueldo_planilla}
                          onChange={e => {
                            // Auto-ajuste: básico = total fijo - nuevo planilla
                            const nuevoP = parseFloat(e.target.value) || 0;
                            const total = sueldoBasicoTotal;
                            const nuevoB = Math.max(0, +(total - nuevoP).toFixed(2));
                            setForm({...form, sueldo_planilla: e.target.value, sueldo_basico: nuevoB});
                          }}
                          className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background font-mono"
                          data-testid="form-sueldo-planilla" />
                        <p className="text-[10px] text-muted-foreground mt-1">Monto que aparece en boleta (base AFP). El básico se ajusta solo.</p>
                      </div>
                      <div>
                        <label className="text-xs font-medium text-muted-foreground block mb-1">Sueldo básico (auto)</label>
                        <input type="number" step="0.01" min="0"
                          value={form.sueldo_basico}
                          onChange={e => {
                            // Si editás básico manualmente, el sistema ajusta planilla
                            const nuevoB = parseFloat(e.target.value) || 0;
                            const total = sueldoBasicoTotal;
                            const nuevoP = Math.max(0, +(total - nuevoB).toFixed(2));
                            setForm({...form, sueldo_basico: e.target.value, sueldo_planilla: nuevoP});
                          }}
                          className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background font-mono"
                          data-testid="form-sueldo-basico" />
                        <p className="text-[10px] text-muted-foreground mt-1">Complemento fuera de planilla. Se ajusta solo cuando cambiás planilla.</p>
                      </div>
                      <div className="col-span-2 text-[11px] text-emerald-700 dark:text-emerald-400 font-medium">
                        Total fijo = Planilla + Básico = <span className="font-mono">{fmt(sueldoBasicoTotal)}</span>
                      </div>
                    </div>
                  )}

                  {/* Bono mensual: NO afecta horas extras ni AFP, sólo suma al total mensual esperado */}
                  <div className="mt-3">
                    <label className="text-xs font-medium text-muted-foreground block mb-1">
                      Bono mensual (S/)
                      <span className="ml-1 text-[10px] font-normal text-muted-foreground/70">— monto fijo extra que se suma al sueldo total esperado</span>
                    </label>
                    <input type="number" step="0.01" min="0"
                      value={form.bono}
                      onChange={e => setForm({...form, bono: e.target.value})}
                      className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background font-mono"
                      placeholder="0.00"
                      data-testid="form-bono" />
                    <p className="text-[10px] text-muted-foreground mt-1">
                      No interviene en hora simple, horas extras, AFP ni en planilla. Sólo se suma al total mensual del trabajador.
                    </p>
                  </div>
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
                      <p className="text-[10px] text-muted-foreground mt-1">Hora simple = sueldo / (horas × 2)</p>
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
                      <label className="text-xs font-medium text-muted-foreground block mb-1">H. Extras 25% (default)</label>
                      <input type="number" min="0" step="0.5"
                        value={form.horas_extras_25_default}
                        onChange={e => setForm({...form, horas_extras_25_default: e.target.value})}
                        onWheel={(e) => e.currentTarget.blur()}
                        className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background font-mono" />
                      <p className="text-[10px] text-muted-foreground mt-1">Se pre-carga al armar la planilla quincenal.</p>
                    </div>
                    <div>
                      <label className="text-xs font-medium text-muted-foreground block mb-1">H. Extras 35% (default)</label>
                      <input type="number" min="0" step="0.5"
                        value={form.horas_extras_35_default}
                        onChange={e => setForm({...form, horas_extras_35_default: e.target.value})}
                        onWheel={(e) => e.currentTarget.blur()}
                        className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background font-mono" />
                      <p className="text-[10px] text-muted-foreground mt-1">Editable luego en cada planilla.</p>
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

                {/* Tipo de pago + link con Producción */}
                <section>
                  <h3 className="text-xs font-semibold uppercase text-muted-foreground mb-2 flex items-center gap-1.5">
                    <Scissors size={13}/> Tipo de pago
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                    {TIPOS_PAGO.map(tp => (
                      <label key={tp.value}
                        className={`border rounded-md p-2 cursor-pointer transition-colors ${
                          form.tipo_pago === tp.value
                            ? 'border-emerald-500 bg-emerald-500/5'
                            : 'border-border hover:bg-muted/50'
                        }`}>
                        <input type="radio" name="tipo_pago" value={tp.value}
                          checked={form.tipo_pago === tp.value}
                          onChange={e => setForm({ ...form, tipo_pago: e.target.value })}
                          className="hidden"/>
                        <div className="flex items-center gap-1.5">
                          <div className={`h-3 w-3 rounded-full border-2 ${
                            form.tipo_pago === tp.value
                              ? 'border-emerald-600 bg-emerald-600'
                              : 'border-muted-foreground'
                          }`}/>
                          <div className="text-xs font-medium">{tp.label}</div>
                        </div>
                        <div className="text-[10px] text-muted-foreground mt-0.5 ml-4.5">{tp.hint}</div>
                      </label>
                    ))}
                  </div>

                  {/* Link con Producción (solo si destajo/mixto) */}
                  {(form.tipo_pago === 'destajo' || form.tipo_pago === 'mixto') && (
                    <div className="mt-3 space-y-2">
                      <label className="text-xs font-medium text-muted-foreground block">
                        Persona en Producción <span className="text-[10px] text-muted-foreground/70">(para cruzar los movimientos y calcular el pago)</span>
                      </label>
                      <select value={form.prod_persona_id || ''}
                        onChange={e => setForm({ ...form, prod_persona_id: e.target.value })}
                        className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background"
                        data-testid="form-prod-persona">
                        <option value="">— Sin vincular —</option>
                        {personasProd.map(p => {
                          const ocupada = p.trabajador_id && p.trabajador_id !== editing?.id;
                          return (
                            <option key={p.id} value={p.id} disabled={ocupada}>
                              {p.nombre}
                              {p.unidad_interna_nombre ? ` · ${p.unidad_interna_nombre}` : ''}
                              {p.tipo_persona ? ` [${p.tipo_persona}]` : ''}
                              {ocupada ? ` — ya vinculada a ${p.trabajador_nombre}` : ''}
                            </option>
                          );
                        })}
                      </select>
                    </div>
                  )}
                </section>

                {/* Tarifas destajo (solo si destajo/mixto) */}
                {(form.tipo_pago === 'destajo' || form.tipo_pago === 'mixto') && (
                  <section>
                    <h3 className="text-xs font-semibold uppercase text-muted-foreground mb-2 flex items-center gap-1.5">
                      <Scissors size={13}/> Tarifas destajo
                      <span className="text-[10px] text-muted-foreground/70 normal-case font-normal">
                        (lo que se paga al trabajador por cada prenda de cada servicio)
                      </span>
                    </h3>
                    <div className="space-y-2">
                      {tarifasDestajo.length === 0 && (
                        <div className="text-[11px] text-amber-700 bg-amber-500/10 border border-amber-500/20 rounded-md px-3 py-2">
                          Agrega al menos una tarifa. Ejemplo: Corte S/ 0.20 · Remalle S/ 0.20 · Cerrado S/ 0.15
                        </div>
                      )}
                      {tarifasDestajo.map((x, idx) => (
                        <div key={idx} className="grid grid-cols-12 gap-2 items-center">
                          <select value={x.servicio_nombre}
                            onChange={e => actualizarTarifaDestajo(idx, 'servicio_nombre', e.target.value)}
                            className="col-span-7 px-3 py-2 text-sm rounded-md border border-border bg-background"
                            data-testid={`form-destajo-servicio-${idx}`}>
                            <option value="">— Servicio —</option>
                            {serviciosProd.map(s => (
                              <option key={s.id || s.nombre} value={s.nombre}>{s.nombre}</option>
                            ))}
                          </select>
                          <div className="col-span-4 relative">
                            <span className="absolute left-2 top-1/2 -translate-y-1/2 text-[11px] text-muted-foreground">S/</span>
                            <input type="number" step="0.0001" min="0" placeholder="0.00"
                              value={x.tarifa}
                              onChange={e => actualizarTarifaDestajo(idx, 'tarifa', e.target.value)}
                              className="w-full pl-7 pr-2 py-2 text-sm rounded-md border border-border bg-background font-mono"
                              data-testid={`form-destajo-tarifa-${idx}`}/>
                            <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-muted-foreground">/prenda</span>
                          </div>
                          <button type="button" onClick={() => eliminarTarifaDestajo(idx)}
                            className="col-span-1 h-9 flex items-center justify-center rounded-md hover:bg-red-500/10 text-red-600">
                            <Trash2 size={14}/>
                          </button>
                        </div>
                      ))}
                      <button type="button" onClick={agregarTarifaDestajo}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md border border-dashed border-border hover:bg-muted">
                        <Plus size={12}/> Agregar servicio
                      </button>
                    </div>
                  </section>
                )}

                {/* Medios de pago por defecto */}
                <section>
                  <h3 className="text-xs font-semibold uppercase text-muted-foreground mb-2 flex items-center gap-1.5">
                    <CreditCard size={13}/> Medios de pago por defecto <span className="text-[10px] text-muted-foreground/70 normal-case font-normal">(opcional, auto-cuadre en planilla)</span>
                  </h3>
                  {(() => {
                    // Filtrado: cuentas reales siempre + cuenta ficticia solo si corresponde a la unidad interna del trabajador
                    const uiId = form.unidad_interna_id ? parseInt(form.unidad_interna_id) : null;
                    const cuentasVisibles = cuentas.filter(c => {
                      if (!c.es_ficticia) return true;
                      return uiId && c.unidad_interna_id === uiId;
                    });
                    const cuentaUI = cuentasVisibles.find(c => c.es_ficticia);
                    return (
                  <div className="space-y-2">
                    {uiId && cuentaUI && (
                      <div className="text-[11px] text-blue-700 bg-blue-500/5 border border-blue-500/20 rounded-md px-3 py-2 flex items-start gap-2">
                        <CreditCard size={12} className="mt-0.5 shrink-0"/>
                        <span>
                          Como este trabajador pertenece a una unidad interna, también puedes asignar la cuenta interna{' '}
                          <strong>{cuentaUI.nombre}</strong> para imputar el sueldo al P&amp;L de la unidad.
                        </span>
                      </div>
                    )}
                    {medios.map((m, idx) => (
                      <div key={idx} className="grid grid-cols-12 gap-2 items-center">
                        <select value={m.cuenta_id}
                          onChange={e => actualizarMedio(idx, 'cuenta_id', e.target.value)}
                          className="col-span-8 px-3 py-2 text-sm rounded-md border border-border bg-background">
                          <option value="">— Cuenta —</option>
                          {cuentasVisibles.map(c => (
                            <option key={c.id} value={c.id}>
                              {c.nombre}{c.es_ficticia ? ' (unidad interna)' : ''}
                            </option>
                          ))}
                        </select>
                        <div className="col-span-3 relative">
                          <input type="number" step="0.01" min="0" max="100" placeholder="0"
                            value={m.porcentaje}
                            onChange={e => actualizarMedio(idx, 'porcentaje', e.target.value)}
                            className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background font-mono pr-7" />
                          <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">%</span>
                        </div>
                        <button type="button" onClick={() => eliminarMedio(idx)}
                          className="col-span-1 h-9 flex items-center justify-center rounded-md hover:bg-red-500/10 text-red-600">
                          <Trash2 size={14}/>
                        </button>
                      </div>
                    ))}
                    <button type="button" onClick={agregarMedio}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md border border-dashed border-border hover:bg-muted">
                      <Plus size={12}/> Agregar medio
                    </button>
                    {medios.length > 0 && (
                      <div className={`text-xs px-3 py-2 rounded-md border ${pctOk ? 'bg-emerald-500/5 border-emerald-500/20 text-emerald-700' : 'bg-amber-500/5 border-amber-500/20 text-amber-700'}`}>
                        Total: <strong>{sumaPctMedios.toFixed(2)}%</strong>
                        {pctOk ? ' ✓ correcto' : ` · faltan ${(100 - sumaPctMedios).toFixed(2)}% para llegar a 100`}
                      </div>
                    )}
                  </div>
                    );
                  })()}
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
                        <Row label="Hora simple" value={fmt(calculos.hora_simple)} hint={`sueldo / (horas × 2) = ${sueldoBasicoTotal.toFixed(2)} / ${(parseFloat(form.horas_quincenales || 120) * 2)}`} />
                        <Row label="Hora extra 25%" value={fmt(calculos.hora_extra_25)} hint="hora simple × 1.25" />
                        <Row label="Hora extra 35%" value={fmt(calculos.hora_extra_35)} hint="hora simple × 1.35" />
                      </div>
                    </div>
                    {/* Sueldo total mensual esperado: lo calcula el backend exacto */}
                    {(() => {
                      const he25 = parseFloat(form.horas_extras_25_default) || 0;
                      const he35 = parseFloat(form.horas_extras_35_default) || 0;
                      const bonoVal = parseFloat(form.bono) || 0;
                      const afMonto = form.asignacion_familiar ? (calculos.asignacion_familiar_monto || 0) : 0;
                      // Mostrar el cuadro si hay AL MENOS uno de: HE, Bono, AF
                      if (he25 + he35 + bonoVal + afMonto === 0) return null;
                      const totalEsperado = calculos.sueldo_total_mensual_esperado || 0;
                      const aporteHE25 = calculos.aporte_he25_mensual || 0;
                      const aporteHE35 = calculos.aporte_he35_mensual || 0;
                      // Quincenal = total / 2
                      const totalQuincenal = totalEsperado / 2;
                      return (
                        <div>
                          <div className="text-[11px] uppercase tracking-wider text-muted-foreground mb-1">Sueldo total esperado (mensual)</div>
                          <div className="bg-emerald-50 dark:bg-emerald-950/30 rounded-md border border-emerald-200 dark:border-emerald-900 p-3">
                            <div className="text-2xl font-bold text-emerald-700 dark:text-emerald-400 font-mono">
                              S/ {totalEsperado.toFixed(2)}
                            </div>
                            <div className="text-[10px] text-muted-foreground mt-1.5 leading-snug">
                              Sueldo {fmt(sueldoBasicoTotal)}
                              {he25 > 0 && <> + ({he25}h × {fmt(calculos.hora_extra_25)} × 2 = <strong>{fmt(aporteHE25)}</strong>)</>}
                              {he35 > 0 && <> + ({he35}h × {fmt(calculos.hora_extra_35)} × 2 = <strong>{fmt(aporteHE35)}</strong>)</>}
                              {afMonto > 0 && <> + AF <strong>{fmt(afMonto)}</strong></>}
                              {bonoVal > 0 && <> + Bono <strong>{fmt(bonoVal)}</strong></>}
                            </div>
                            <div className="text-[10px] text-muted-foreground mt-1 pt-1 border-t border-emerald-200/60 dark:border-emerald-900/60">
                              Quincenal: <strong className="font-mono text-emerald-700 dark:text-emerald-400">S/ {totalQuincenal.toFixed(2)}</strong> (mensual / 2)
                            </div>
                          </div>
                        </div>
                      );
                    })()}
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
