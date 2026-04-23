import React, { useState, useEffect, useCallback } from 'react';
import { Plus, Trash2, X, Clock, Check, AlertCircle, Users } from 'lucide-react';
import { toast } from 'sonner';
import {
  getAdelantos, createAdelanto, deleteAdelanto,
  getTrabajadores, getCuentasFinancieras,
} from '../services/api';
import { useEmpresa } from '../context/EmpresaContext';

const fmt = (v) => `S/ ${Number(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const fmtDate = (d) => {
  if (!d) return '';
  const dt = new Date(d + (typeof d === 'string' && d.length === 10 ? 'T00:00:00' : ''));
  return dt.toLocaleDateString('es-PE');
};

const today = () => new Date().toISOString().split('T')[0];

export default function Adelantos() {
  const { empresaActual } = useEmpresa();
  const [adelantos, setAdelantos] = useState([]);
  const [trabajadores, setTrabajadores] = useState([]);
  const [cuentas, setCuentas] = useState([]);
  const [filtro, setFiltro] = useState('pendientes'); // 'pendientes' | 'descontados' | 'todos'
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    trabajador_id: '',
    fecha: today(),
    monto: '',
    motivo: '',
    cuenta_pago_id: '',
  });

  const load = useCallback(async () => {
    if (!empresaActual) return;
    setLoading(true);
    try {
      const params = {};
      if (filtro === 'pendientes') params.pendientes = true;
      if (filtro === 'descontados') params.pendientes = false;
      const [a, t, c] = await Promise.all([
        getAdelantos(params),
        getTrabajadores({ activo: true }),
        getCuentasFinancieras(),
      ]);
      setAdelantos(a.data || []);
      setTrabajadores(t.data || []);
      setCuentas(c.data || []);
    } catch (e) {
      toast.error('Error cargando adelantos');
    } finally { setLoading(false); }
  }, [empresaActual, filtro]);

  useEffect(() => { load(); }, [load]);

  const openNew = () => {
    setForm({
      trabajador_id: '',
      fecha: today(),
      monto: '',
      motivo: '',
      cuenta_pago_id: cuentas.find(c => !c.es_ficticia)?.id || '',
    });
    setShowForm(true);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (saving) return;
    if (!form.trabajador_id) { toast.error('Selecciona un trabajador'); return; }
    if (!form.cuenta_pago_id) { toast.error('Selecciona la cuenta de pago'); return; }
    const monto = parseFloat(form.monto);
    if (!monto || monto <= 0) { toast.error('Monto inválido'); return; }

    setSaving(true);
    try {
      await createAdelanto({
        trabajador_id: parseInt(form.trabajador_id),
        fecha: form.fecha,
        monto,
        motivo: form.motivo || null,
        cuenta_pago_id: parseInt(form.cuenta_pago_id),
      });
      toast.success('Adelanto registrado y egreso generado');
      setShowForm(false);
      load();
    } catch (err) {
      const msg = typeof err.response?.data?.detail === 'string' ? err.response.data.detail : 'Error';
      toast.error(msg);
    } finally { setSaving(false); }
  };

  const handleDelete = async (a) => {
    if (!window.confirm(`¿Eliminar adelanto de ${a.trabajador_nombre} por ${fmt(a.monto)}?\n(Se revertirá el egreso de ${a.cuenta_nombre})`)) return;
    try {
      await deleteAdelanto(a.id);
      toast.success('Adelanto eliminado y egreso revertido');
      load();
    } catch (err) {
      const msg = typeof err.response?.data?.detail === 'string' ? err.response.data.detail : 'Error';
      toast.error(msg);
    }
  };

  const totalPendiente = adelantos
    .filter(a => !a.descontado)
    .reduce((s, a) => s + parseFloat(a.monto || 0), 0);

  return (
    <div className="max-w-[1100px] space-y-6" data-testid="adelantos-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground tracking-tight flex items-center gap-2">
            <Clock size={22} /> Adelantos a Trabajadores
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Al crear un adelanto se genera un egreso real de la cuenta elegida. Se descuenta en la planilla quincenal.
          </p>
        </div>
        <button onClick={openNew}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-blue-700 shadow-sm"
          data-testid="nuevo-adelanto-btn">
          <Plus size={16} /> Nuevo adelanto
        </button>
      </div>

      {/* Filtros y KPI */}
      <div className="flex items-center gap-2 flex-wrap">
        <button onClick={() => setFiltro('pendientes')}
          className={`px-3 py-1.5 text-xs rounded-md font-medium ${filtro === 'pendientes' ? 'bg-blue-600 text-white' : 'bg-card border border-border text-muted-foreground hover:text-foreground'}`}>
          Pendientes
        </button>
        <button onClick={() => setFiltro('descontados')}
          className={`px-3 py-1.5 text-xs rounded-md font-medium ${filtro === 'descontados' ? 'bg-blue-600 text-white' : 'bg-card border border-border text-muted-foreground hover:text-foreground'}`}>
          Descontados
        </button>
        <button onClick={() => setFiltro('todos')}
          className={`px-3 py-1.5 text-xs rounded-md font-medium ${filtro === 'todos' ? 'bg-blue-600 text-white' : 'bg-card border border-border text-muted-foreground hover:text-foreground'}`}>
          Todos
        </button>
        {filtro === 'pendientes' && (
          <span className="ml-2 text-xs text-amber-700 font-medium">
            Total pendiente: {fmt(totalPendiente)}
          </span>
        )}
      </div>

      {/* Tabla */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 border-b border-border">
            <tr>
              <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Fecha</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Trabajador</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Motivo</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Cuenta origen</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Monto</th>
              <th className="text-center px-4 py-3 text-xs font-medium text-muted-foreground uppercase">Estado</th>
              <th className="w-16"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {loading ? (
              <tr><td colSpan={7} className="py-10 text-center text-muted-foreground">Cargando…</td></tr>
            ) : adelantos.length === 0 ? (
              <tr><td colSpan={7} className="py-10 text-center text-muted-foreground">
                <AlertCircle size={28} className="mx-auto mb-2 opacity-40" />
                Sin adelantos en este filtro.
              </td></tr>
            ) : adelantos.map(a => (
              <tr key={a.id} className="hover:bg-muted/30" data-testid={`adelanto-row-${a.id}`}>
                <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">{fmtDate(a.fecha)}</td>
                <td className="px-4 py-3">
                  <div className="font-medium text-foreground text-sm">{a.trabajador_nombre}</div>
                  {a.trabajador_dni && <div className="text-[10px] text-muted-foreground font-mono">DNI {a.trabajador_dni}</div>}
                </td>
                <td className="px-4 py-3 text-xs text-muted-foreground max-w-[280px] truncate" title={a.motivo}>{a.motivo || '—'}</td>
                <td className="px-4 py-3 text-xs">{a.cuenta_nombre || '—'}</td>
                <td className="px-4 py-3 text-right font-mono text-sm font-semibold text-amber-700 dark:text-amber-400">{fmt(a.monto)}</td>
                <td className="px-4 py-3 text-center">
                  {a.descontado ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/10 text-emerald-700 dark:text-emerald-400">
                      <Check size={10} /> Descontado
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/10 text-amber-700 dark:text-amber-400">
                      <Clock size={10} /> Pendiente
                    </span>
                  )}
                </td>
                <td className="px-3 py-3 text-right">
                  {!a.descontado && (
                    <button onClick={() => handleDelete(a)}
                      className="h-7 w-7 flex items-center justify-center rounded-md hover:bg-red-500/10 text-red-600"
                      title="Eliminar y revertir egreso">
                      <Trash2 size={14} />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal nuevo */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
             onClick={() => !saving && setShowForm(false)}>
          <form onSubmit={handleSave} onClick={e => e.stopPropagation()}
                className="bg-card rounded-xl shadow-2xl w-full max-w-lg border border-border">
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
              <h2 className="text-base font-semibold flex items-center gap-2">
                <Plus size={18} className="text-blue-600"/> Nuevo Adelanto
              </h2>
              <button type="button" onClick={() => setShowForm(false)}
                className="h-8 w-8 flex items-center justify-center rounded-md hover:bg-muted">
                <X size={18} />
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1">Trabajador *</label>
                <select required value={form.trabajador_id}
                  onChange={e => setForm({...form, trabajador_id: e.target.value})}
                  className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background"
                  data-testid="form-adel-trabajador">
                  <option value="">— Selecciona —</option>
                  {trabajadores.map(t => (
                    <option key={t.id} value={t.id}>
                      {t.nombre}{t.dni ? ` · DNI ${t.dni}` : ''}{t.area ? ` · ${t.area}` : ''}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-muted-foreground block mb-1">Fecha *</label>
                  <input type="date" required value={form.fecha}
                    onChange={e => setForm({...form, fecha: e.target.value})}
                    className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background" />
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground block mb-1">Monto (S/) *</label>
                  <input type="number" step="0.01" min="0" required value={form.monto}
                    onChange={e => setForm({...form, monto: e.target.value})}
                    className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background font-mono"
                    data-testid="form-adel-monto" />
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1">
                  Cuenta de pago *
                  <span className="text-[10px] text-muted-foreground ml-1">(de aquí sale el dinero)</span>
                </label>
                <select required value={form.cuenta_pago_id}
                  onChange={e => setForm({...form, cuenta_pago_id: e.target.value})}
                  className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background"
                  data-testid="form-adel-cuenta">
                  <option value="">— Selecciona —</option>
                  {cuentas.filter(c => !c.es_ficticia && c.activo !== false).map(c => (
                    <option key={c.id} value={c.id}>
                      {c.nombre} ({fmt(c.saldo_actual)})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground block mb-1">Motivo</label>
                <input type="text" placeholder="Opcional — emergencia familiar, compra, etc."
                  value={form.motivo}
                  onChange={e => setForm({...form, motivo: e.target.value})}
                  className="w-full px-3 py-2 text-sm rounded-md border border-border bg-background" />
              </div>
              <div className="bg-blue-500/5 border border-blue-500/20 rounded-md p-3 text-[12px] flex gap-2">
                <AlertCircle size={14} className="text-blue-600 mt-0.5 shrink-0"/>
                <div>Al guardar se registrará el adelanto y se generará un <strong>EGRESO</strong> por {form.monto ? fmt(form.monto) : 'el monto'} en la cuenta seleccionada.</div>
              </div>
            </div>
            <div className="flex justify-end gap-2 px-5 py-3 border-t border-border bg-muted/20">
              <button type="button" onClick={() => setShowForm(false)}
                className="px-3 py-1.5 text-sm rounded-md border border-border hover:bg-muted">Cancelar</button>
              <button type="submit" disabled={saving}
                className="inline-flex items-center gap-1.5 bg-blue-600 text-white px-4 py-1.5 text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50"
                data-testid="form-adel-guardar">
                <Check size={14} /> {saving ? 'Guardando…' : 'Guardar y pagar'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
