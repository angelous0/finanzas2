import React, { useState, useEffect, useCallback } from 'react';
import { Plus, Pencil, Trash2, Search, X } from 'lucide-react';
import { getTerceros, createTercero, updateTercero, deleteTercero } from '../services/api';
import { toast } from 'sonner';

const EMPTY = { nombre: '', tipo_documento: 'RUC', numero_documento: '', telefono: '', email: '', direccion: '', notas: '' };

export default function Proveedores() {
  const [proveedores, setProveedores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getTerceros({ es_proveedor: true, search: search || undefined });
      setProveedores(res.data);
    } catch { toast.error('Error cargando proveedores'); }
    finally { setLoading(false); }
  }, [search]);

  useEffect(() => { load(); }, [load]);

  const openNew = () => { setEditing(null); setForm(EMPTY); setShowModal(true); };
  const openEdit = (p) => {
    setEditing(p);
    setForm({ nombre: p.nombre || '', tipo_documento: p.tipo_documento || 'RUC', numero_documento: p.numero_documento || '', telefono: p.telefono || '', email: p.email || '', direccion: p.direccion || '', notas: p.notas || '' });
    setShowModal(true);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!form.nombre.trim()) { toast.error('Nombre es obligatorio'); return; }
    setSaving(true);
    try {
      const payload = { ...form, es_proveedor: true, es_cliente: false, es_personal: false, activo: true };
      if (editing) {
        await updateTercero(editing.id, payload);
        toast.success('Proveedor actualizado');
      } else {
        await createTercero(payload);
        toast.success('Proveedor creado');
      }
      setShowModal(false);
      load();
    } catch { toast.error('Error guardando'); }
    finally { setSaving(false); }
  };

  const handleDelete = async (p) => {
    if (!window.confirm(`Desactivar "${p.nombre}"?`)) return;
    try { await deleteTercero(p.id); toast.success('Proveedor desactivado'); load(); }
    catch { toast.error('Error'); }
  };

  return (
    <div className="max-w-[1100px] space-y-4" data-testid="proveedores-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-foreground tracking-tight">Proveedores</h1>
        <button
          className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-emerald-700 transition-colors shadow-sm"
          onClick={openNew}
          data-testid="nuevo-proveedor-btn"
        >
          <Plus size={16} />
          Nuevo Proveedor
        </button>
      </div>

      {/* Search */}
      <div className="relative max-w-xs">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          className="w-full rounded-lg border border-border bg-background pl-9 pr-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600 transition-colors"
          placeholder="Buscar por nombre o RUC..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          data-testid="proveedor-search"
        />
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center py-12 text-muted-foreground text-sm">
          Cargando...
        </div>
      ) : proveedores.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
          <p className="text-sm">No hay proveedores registrados</p>
          <button
            className="mt-3 inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700 transition-colors"
            onClick={openNew}
          >
            <Plus size={14} />
            Registrar proveedor
          </button>
        </div>
      ) : (
        <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="proveedores-table">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="sticky top-0 text-left px-5 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider bg-muted/30">Nombre</th>
                  <th className="sticky top-0 text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider bg-muted/30">RUC / Doc.</th>
                  <th className="sticky top-0 text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider bg-muted/30">Telefono</th>
                  <th className="sticky top-0 text-left px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider bg-muted/30">Email</th>
                  <th className="sticky top-0 text-center px-4 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider bg-muted/30 w-20">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {proveedores.map(p => (
                  <tr key={p.id} className="hover:bg-muted/30 transition-colors group">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-600/10 text-emerald-600 text-xs font-semibold flex-shrink-0">
                          {(p.nombre || '?')[0].toUpperCase()}
                        </div>
                        <span className="font-medium text-foreground">{p.nombre}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {p.numero_documento ? (
                        <span className="inline-flex items-center gap-1.5">
                          <span className="inline-flex rounded bg-muted px-1.5 py-0.5 text-[0.625rem] font-medium uppercase">
                            {p.tipo_documento || 'RUC'}
                          </span>
                          {p.numero_documento}
                        </span>
                      ) : (
                        <span className="text-muted-foreground/50">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{p.telefono || <span className="text-muted-foreground/50">-</span>}</td>
                    <td className="px-4 py-3 text-muted-foreground">{p.email || <span className="text-muted-foreground/50">-</span>}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                          onClick={() => openEdit(p)}
                          title="Editar"
                        >
                          <Pencil size={14} />
                        </button>
                        <button
                          className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-red-500/10 text-muted-foreground hover:text-red-600 transition-colors"
                          onClick={() => handleDelete(p)}
                          title="Desactivar"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setShowModal(false)} />
          <div className="relative w-full max-w-lg rounded-xl border border-border bg-card shadow-2xl" onClick={e => e.stopPropagation()}>
            {/* Modal header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-border">
              <h2 className="text-base font-semibold text-foreground">
                {editing ? 'Editar Proveedor' : 'Nuevo Proveedor'}
              </h2>
              <button
                className="flex h-7 w-7 items-center justify-center rounded-md hover:bg-muted text-muted-foreground transition-colors"
                onClick={() => setShowModal(false)}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSave}>
              <div className="px-6 py-4 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">Nombre / Razon Social *</label>
                  <input
                    type="text"
                    className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600 transition-colors"
                    value={form.nombre}
                    autoFocus
                    onChange={e => setForm({ ...form, nombre: e.target.value })}
                    required
                    data-testid="prov-nombre"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-1.5">Tipo Doc.</label>
                    <select
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600 transition-colors"
                      value={form.tipo_documento}
                      onChange={e => setForm({ ...form, tipo_documento: e.target.value })}
                    >
                      <option value="RUC">RUC</option>
                      <option value="DNI">DNI</option>
                      <option value="CE">CE</option>
                      <option value="OTRO">Otro</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-1.5">N Documento</label>
                    <input
                      type="text"
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600 transition-colors"
                      value={form.numero_documento}
                      onChange={e => setForm({ ...form, numero_documento: e.target.value })}
                      placeholder="20123456789"
                      data-testid="prov-ruc"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-1.5">Telefono</label>
                    <input
                      type="text"
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600 transition-colors"
                      value={form.telefono}
                      onChange={e => setForm({ ...form, telefono: e.target.value })}
                      placeholder="987654321"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-foreground mb-1.5">Email</label>
                    <input
                      type="email"
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600 transition-colors"
                      value={form.email}
                      onChange={e => setForm({ ...form, email: e.target.value })}
                      placeholder="contacto@empresa.com"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">Direccion</label>
                  <input
                    type="text"
                    className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600 transition-colors"
                    value={form.direccion}
                    onChange={e => setForm({ ...form, direccion: e.target.value })}
                    placeholder="Opcional"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-foreground mb-1.5">Notas</label>
                  <textarea
                    className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600/20 focus:border-emerald-600 transition-colors resize-none"
                    rows={2}
                    value={form.notas}
                    onChange={e => setForm({ ...form, notas: e.target.value })}
                    placeholder="Opcional"
                  />
                </div>
              </div>

              {/* Modal footer */}
              <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-border">
                <button
                  type="button"
                  className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-muted transition-colors"
                  onClick={() => setShowModal(false)}
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 transition-colors disabled:opacity-50"
                  disabled={saving}
                >
                  {saving ? 'Guardando...' : (editing ? 'Guardar' : 'Crear Proveedor')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
