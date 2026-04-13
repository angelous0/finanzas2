import React, { useState, useEffect, useCallback } from 'react';
import {
  Plus, Search, X, Pencil, Trash2, Package, DollarSign,
  TrendingDown, Calculator, ChevronLeft, Calendar, Building2
} from 'lucide-react';
import { toast } from 'sonner';
import {
  getActivosFijos, createActivoFijo, updateActivoFijo, deleteActivoFijo,
  getResumenActivos, getDepreciacionActivo, calcularDepreciacion, getTerceros, getLineasNegocio,
} from '../services/api';
import { useEmpresa } from '../context/EmpresaContext';

const fmt = (v) => `S/ ${Number(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtDate = (d) => {
  if (!d) return '-';
  return new Date(d + 'T00:00:00').toLocaleDateString('es-PE', { day: '2-digit', month: '2-digit', year: 'numeric' });
};

const CATEGORIAS = ['Maquinaria', 'Equipo', 'Mueble', 'Vehiculo', 'Computadora', 'Herramienta', 'Otro'];

const ESTADO_BADGE = {
  activo: 'bg-emerald-500/10 text-emerald-600',
  baja: 'bg-red-500/10 text-red-600',
  vendido: 'bg-amber-500/10 text-amber-600',
};

const EMPTY_FORM = {
  nombre: '', codigo: '', descripcion: '', categoria: '',
  fecha_adquisicion: '', valor_adquisicion: '', vida_util_anios: '',
  valor_residual: '0', proveedor_id: '', factura_referencia: '',
  ubicacion: '', responsable: '', linea_negocio_id: '',
};

export default function ActivosFijos() {
  const { empresaActual } = useEmpresa();
  const [activos, setActivos] = useState([]);
  const [resumen, setResumen] = useState(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filtroCategoria, setFiltroCategoria] = useState('');
  const [filtroEstado, setFiltroEstado] = useState('');

  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  // Depreciation modal
  const [showDepModal, setShowDepModal] = useState(null);
  const [depData, setDepData] = useState([]);
  const [depLoading, setDepLoading] = useState(false);

  // Master data
  const [proveedores, setProveedores] = useState([]);
  const [lineasNegocio, setLineasNegocio] = useState([]);

  const load = useCallback(async () => {
    if (!empresaActual) return;
    setLoading(true);
    try {
      const params = {};
      if (search) params.search = search;
      if (filtroCategoria) params.categoria = filtroCategoria;
      if (filtroEstado) params.estado = filtroEstado;
      const [actRes, resRes, provRes, lnRes] = await Promise.all([
        getActivosFijos(params),
        getResumenActivos(),
        getTerceros({ es_proveedor: true }),
        getLineasNegocio(),
      ]);
      setActivos(actRes.data);
      setResumen(resRes.data);
      setProveedores(provRes.data);
      setLineasNegocio(lnRes.data);
    } catch {
      toast.error('Error cargando activos');
    } finally {
      setLoading(false);
    }
  }, [empresaActual, search, filtroCategoria, filtroEstado]);

  useEffect(() => { load(); }, [load]);

  const openNew = () => { setEditing(null); setForm(EMPTY_FORM); setShowModal(true); };
  const openEdit = (a) => {
    setEditing(a);
    setForm({
      nombre: a.nombre || '',
      codigo: a.codigo || '',
      descripcion: a.descripcion || '',
      categoria: a.categoria || '',
      fecha_adquisicion: a.fecha_adquisicion || '',
      valor_adquisicion: a.valor_adquisicion || '',
      vida_util_anios: a.vida_util_anios || '',
      valor_residual: a.valor_residual || '0',
      proveedor_id: a.proveedor_id || '',
      factura_referencia: a.factura_referencia || '',
      ubicacion: a.ubicacion || '',
      responsable: a.responsable || '',
      linea_negocio_id: a.linea_negocio_id || '',
    });
    setShowModal(true);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!form.nombre.trim()) { toast.error('Nombre es obligatorio'); return; }
    setSaving(true);
    try {
      const payload = {
        ...form,
        valor_adquisicion: parseFloat(form.valor_adquisicion) || null,
        vida_util_anios: parseInt(form.vida_util_anios) || null,
        valor_residual: parseFloat(form.valor_residual) || 0,
        proveedor_id: form.proveedor_id ? parseInt(form.proveedor_id) : null,
        linea_negocio_id: form.linea_negocio_id ? parseInt(form.linea_negocio_id) : null,
        fecha_adquisicion: form.fecha_adquisicion || null,
        codigo: form.codigo || null,
      };
      if (editing) {
        await updateActivoFijo(editing.id, payload);
        toast.success('Activo actualizado');
      } else {
        await createActivoFijo(payload);
        toast.success('Activo creado');
      }
      setShowModal(false);
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error guardando');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (a) => {
    if (!window.confirm(`Dar de baja "${a.nombre}"?`)) return;
    try {
      await deleteActivoFijo(a.id);
      toast.success('Activo dado de baja');
      load();
    } catch { toast.error('Error'); }
  };

  const openDepreciacion = async (a) => {
    setShowDepModal(a);
    setDepLoading(true);
    try {
      const res = await getDepreciacionActivo(a.id);
      setDepData(res.data);
    } catch { toast.error('Error cargando depreciacion'); }
    finally { setDepLoading(false); }
  };

  const handleCalcDep = async () => {
    try {
      const res = await calcularDepreciacion();
      toast.success(`Depreciacion calculada: ${res.data.activos_procesados} activos procesados`);
      load();
      if (showDepModal) openDepreciacion(showDepModal);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error calculando depreciacion');
    }
  };

  if (!empresaActual) return null;

  return (
    <div className="max-w-[1200px] space-y-6" data-testid="activos-fijos-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground tracking-tight">Activos Fijos</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Control de activos y depreciacion</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm font-medium text-foreground hover:bg-muted transition-colors"
            onClick={handleCalcDep}
          >
            <Calculator size={14} /> Calcular Depreciacion
          </button>
          <button
            className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-emerald-700 transition-colors shadow-sm"
            onClick={openNew}
            data-testid="nuevo-activo-btn"
          >
            <Plus size={16} /> Nuevo Activo
          </button>
        </div>
      </div>

      {/* KPIs */}
      {resumen && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <KpiCard label="Activos Activos" value={resumen.total_activos} icon={Package} color="emerald" />
          <KpiCard label="Valor Adquisicion" value={fmt(resumen.valor_total)} icon={DollarSign} color="blue" />
          <KpiCard label="Dep. Mes Actual" value={fmt(resumen.depreciacion_mes)} icon={TrendingDown} color="red" />
          <KpiCard label="Valor Libro" value={fmt(resumen.valor_libro_total)} icon={DollarSign} color="amber" />
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative max-w-xs">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            className="w-full rounded-lg border border-border bg-background pl-9 pr-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600"
            placeholder="Buscar por nombre o codigo..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            data-testid="activo-search"
          />
        </div>
        <select
          className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20"
          value={filtroCategoria}
          onChange={e => setFiltroCategoria(e.target.value)}
        >
          <option value="">Todas las categorias</option>
          {CATEGORIAS.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select
          className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20"
          value={filtroEstado}
          onChange={e => setFiltroEstado(e.target.value)}
        >
          <option value="">Todos los estados</option>
          <option value="activo">Activo</option>
          <option value="baja">Baja</option>
          <option value="vendido">Vendido</option>
        </select>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center py-12 text-muted-foreground text-sm">Cargando...</div>
      ) : activos.length === 0 ? (
        <div className="rounded-xl border border-border bg-card p-8 text-center shadow-sm">
          <Package size={40} className="mx-auto mb-3 text-muted-foreground/30" />
          <p className="text-muted-foreground text-sm mb-3">No hay activos registrados</p>
          <button
            className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 transition-colors"
            onClick={openNew}
          >
            <Plus size={14} /> Registrar primer activo
          </button>
        </div>
      ) : (
        <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="activos-table">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="sticky top-0 text-left px-5 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider bg-muted/30">Codigo</th>
                  <th className="sticky top-0 text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider bg-muted/30">Nombre</th>
                  <th className="sticky top-0 text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider bg-muted/30">Categoria</th>
                  <th className="sticky top-0 text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider bg-muted/30">Fecha Adq.</th>
                  <th className="sticky top-0 text-right px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider bg-muted/30">Valor Adq.</th>
                  <th className="sticky top-0 text-right px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider bg-muted/30">Dep. Mensual</th>
                  <th className="sticky top-0 text-right px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider bg-muted/30">Valor Libro</th>
                  <th className="sticky top-0 text-center px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider bg-muted/30">Estado</th>
                  <th className="sticky top-0 text-center px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider bg-muted/30 w-28">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {activos.map(a => (
                  <tr key={a.id} className="hover:bg-muted/30 transition-colors group">
                    <td className="px-5 py-3">
                      <span className="inline-flex rounded bg-muted px-2 py-0.5 text-xs font-mono font-medium">
                        {a.codigo || '-'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        className="font-medium text-foreground hover:text-emerald-600 transition-colors text-left"
                        onClick={() => openDepreciacion(a)}
                      >
                        {a.nombre}
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex rounded-full bg-blue-500/10 text-blue-600 px-2 py-0.5 text-xs font-medium">
                        {a.categoria || '-'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground text-xs">{fmtDate(a.fecha_adquisicion)}</td>
                    <td className="px-4 py-3 text-right font-medium">{fmt(a.valor_adquisicion)}</td>
                    <td className="px-4 py-3 text-right text-red-600">{fmt(a.dep_mensual)}</td>
                    <td className="px-4 py-3 text-right font-semibold">{fmt(a.valor_libro)}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${ESTADO_BADGE[a.estado] || ESTADO_BADGE.activo}`}>
                        {a.estado}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                          onClick={() => openEdit(a)}
                          title="Editar"
                        >
                          <Pencil size={14} />
                        </button>
                        <button
                          className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-emerald-500/10 text-muted-foreground hover:text-emerald-600 transition-colors"
                          onClick={() => openDepreciacion(a)}
                          title="Depreciacion"
                        >
                          <TrendingDown size={14} />
                        </button>
                        {a.estado === 'activo' && (
                          <button
                            className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-red-500/10 text-muted-foreground hover:text-red-600 transition-colors"
                            onClick={() => handleDelete(a)}
                            title="Dar de baja"
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

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setShowModal(false)} />
          <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-xl border border-border bg-card shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="sticky top-0 flex items-center justify-between px-6 py-4 border-b border-border bg-card z-10">
              <h2 className="text-base font-semibold text-foreground">
                {editing ? 'Editar Activo' : 'Nuevo Activo Fijo'}
              </h2>
              <button className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-muted text-muted-foreground" onClick={() => setShowModal(false)}>
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleSave}>
              <div className="px-6 py-4 space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div className="col-span-2 sm:col-span-1">
                    <label className="block text-sm font-medium text-foreground mb-1.5">Nombre *</label>
                    <input type="text" required autoFocus
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600"
                      value={form.nombre} onChange={e => setForm({ ...form, nombre: e.target.value })} data-testid="activo-nombre" />
                  </div>
                  <div className="col-span-2 sm:col-span-1">
                    <label className="block text-sm font-medium text-foreground mb-1.5">Codigo (auto si vacio)</label>
                    <input type="text"
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600"
                      value={form.codigo} onChange={e => setForm({ ...form, codigo: e.target.value })} placeholder="AF-0001" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-1.5">Categoria *</label>
                    <select
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600"
                      value={form.categoria} onChange={e => setForm({ ...form, categoria: e.target.value })}>
                      <option value="">Seleccionar</option>
                      {CATEGORIAS.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-1.5">Fecha Adquisicion *</label>
                    <input type="date"
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600"
                      value={form.fecha_adquisicion} onChange={e => setForm({ ...form, fecha_adquisicion: e.target.value })} />
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-1.5">Valor Adquisicion *</label>
                    <input type="number" step="0.01" min="0"
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600"
                      value={form.valor_adquisicion} onChange={e => setForm({ ...form, valor_adquisicion: e.target.value })} />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-1.5">Vida Util (anios) *</label>
                    <input type="number" min="1"
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600"
                      value={form.vida_util_anios} onChange={e => setForm({ ...form, vida_util_anios: e.target.value })} />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-1.5">Valor Residual</label>
                    <input type="number" step="0.01" min="0"
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600"
                      value={form.valor_residual} onChange={e => setForm({ ...form, valor_residual: e.target.value })} />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-1.5">Proveedor</label>
                    <select
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600"
                      value={form.proveedor_id} onChange={e => setForm({ ...form, proveedor_id: e.target.value })}>
                      <option value="">Sin proveedor</option>
                      {proveedores.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-1.5">Linea de Negocio</label>
                    <select
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600"
                      value={form.linea_negocio_id} onChange={e => setForm({ ...form, linea_negocio_id: e.target.value })}>
                      <option value="">Sin asignar</option>
                      {lineasNegocio.map(ln => <option key={ln.id} value={ln.id}>{ln.nombre}</option>)}
                    </select>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-1.5">Factura Referencia</label>
                    <input type="text"
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600"
                      value={form.factura_referencia} onChange={e => setForm({ ...form, factura_referencia: e.target.value })} placeholder="F001-00123" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-1.5">Ubicacion</label>
                    <input type="text"
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600"
                      value={form.ubicacion} onChange={e => setForm({ ...form, ubicacion: e.target.value })} placeholder="Almacen principal" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-1.5">Responsable</label>
                    <input type="text"
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600"
                      value={form.responsable} onChange={e => setForm({ ...form, responsable: e.target.value })} />
                  </div>
                  <div className="col-span-2 sm:col-span-1">
                    <label className="block text-sm font-medium text-foreground mb-1.5">Descripcion</label>
                    <input type="text"
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600"
                      value={form.descripcion} onChange={e => setForm({ ...form, descripcion: e.target.value })} />
                  </div>
                </div>
              </div>
              <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-border">
                <button type="button"
                  className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-muted transition-colors"
                  onClick={() => setShowModal(false)}>
                  Cancelar
                </button>
                <button type="submit"
                  className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 transition-colors disabled:opacity-50"
                  disabled={saving}>
                  {saving ? 'Guardando...' : (editing ? 'Guardar' : 'Crear Activo')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Depreciation Modal */}
      {showDepModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setShowDepModal(null)} />
          <div className="relative w-full max-w-2xl max-h-[80vh] overflow-y-auto rounded-xl border border-border bg-card shadow-2xl">
            <div className="sticky top-0 flex items-center justify-between px-6 py-4 border-b border-border bg-card z-10">
              <div>
                <h2 className="text-base font-semibold text-foreground">Tabla de Depreciacion</h2>
                <p className="text-sm text-muted-foreground">{showDepModal.nombre} ({showDepModal.codigo})</p>
              </div>
              <button className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-muted text-muted-foreground" onClick={() => setShowDepModal(null)}>
                <X size={18} />
              </button>
            </div>

            <div className="px-6 py-4">
              {/* Asset info */}
              <div className="grid grid-cols-3 gap-4 mb-4 text-sm">
                <div>
                  <span className="text-muted-foreground">Valor Adquisicion:</span>
                  <div className="font-semibold">{fmt(showDepModal.valor_adquisicion)}</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Vida Util:</span>
                  <div className="font-semibold">{showDepModal.vida_util_anios} anios</div>
                </div>
                <div>
                  <span className="text-muted-foreground">Dep. Mensual:</span>
                  <div className="font-semibold text-red-600">{fmt(showDepModal.dep_mensual)}</div>
                </div>
              </div>

              <button
                className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted transition-colors mb-4"
                onClick={handleCalcDep}
              >
                <Calculator size={14} /> Calcular mes actual
              </button>

              {depLoading ? (
                <div className="text-center py-8 text-muted-foreground text-sm">Cargando...</div>
              ) : depData.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground text-sm">
                  Sin depreciacion registrada. Usa el boton para calcular.
                </div>
              ) : (
                <div className="rounded-lg border border-border overflow-hidden">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border bg-muted/30">
                        <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase">Periodo</th>
                        <th className="text-right px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase">Dep. Mensual</th>
                        <th className="text-right px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase">Dep. Acumulada</th>
                        <th className="text-right px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase">Valor Libro</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {depData.map((d, i) => (
                        <tr key={i} className="hover:bg-muted/20">
                          <td className="px-4 py-2 font-medium">{d.periodo}</td>
                          <td className="px-4 py-2 text-right text-red-600">{fmt(d.valor_depreciacion)}</td>
                          <td className="px-4 py-2 text-right text-muted-foreground">{fmt(d.valor_acumulado)}</td>
                          <td className="px-4 py-2 text-right font-semibold">{fmt(d.valor_libro)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function KpiCard({ label, value, icon: Icon, color }) {
  const colorMap = {
    emerald: 'bg-emerald-500/10 text-emerald-600',
    blue: 'bg-blue-500/10 text-blue-600',
    amber: 'bg-amber-500/10 text-amber-600',
    red: 'bg-red-500/10 text-red-600',
  };
  const cls = colorMap[color] || colorMap.blue;
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{label}</p>
          <p className="text-xl font-bold text-foreground">{value}</p>
        </div>
        <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${cls}`}>
          <Icon size={20} />
        </div>
      </div>
    </div>
  );
}
