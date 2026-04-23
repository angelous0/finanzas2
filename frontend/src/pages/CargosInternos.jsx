import React, { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { RefreshCw, Filter, Zap, ArrowRightLeft, Calendar, X } from 'lucide-react';
import { getCargosInternos, generarCargosInternos, getUnidadesInternas } from '../services/api';

const firstOfMonthISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
};
const lastOfMonthISO = () => {
  const d = new Date();
  const last = new Date(d.getFullYear(), d.getMonth() + 1, 0);
  return last.toISOString().slice(0, 10);
};

const formatCurrency = (v) => `S/ ${(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function CargosInternos() {
  const [cargos, setCargos] = useState([]);
  const [unidades, setUnidades] = useState([]);
  const [loading, setLoading] = useState(false);
  const [generando, setGenerando] = useState(false);
  const [filtroUnidad, setFiltroUnidad] = useState('');
  const [filtroNota, setFiltroNota] = useState(''); // '' | 'si' | 'no'
  const [busqueda, setBusqueda] = useState('');
  // Por defecto: mes actual para no traer años de histórico de golpe
  const [fechaDesde, setFechaDesde] = useState(firstOfMonthISO());
  const [fechaHasta, setFechaHasta] = useState(lastOfMonthISO());

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const params = {};
      if (filtroUnidad) params.unidad_interna_id = filtroUnidad;
      if (filtroNota) params.con_nota = filtroNota;
      if (fechaDesde) params.fecha_desde = fechaDesde;
      if (fechaHasta) params.fecha_hasta = fechaHasta;
      const [cRes, uRes] = await Promise.all([getCargosInternos(params), getUnidadesInternas()]);
      setCargos(cRes.data || []);
      setUnidades(uRes.data || []);
    } catch (e) {
      toast.error('Error al cargar cargos');
    } finally {
      setLoading(false);
    }
  }, [filtroUnidad, filtroNota, fechaDesde, fechaHasta]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleGenerar = async () => {
    const confirm = window.confirm(
      '¿Escanear movimientos internos sin cargo?\n\n' +
      '⚠️ Los cargos se crearán como CxC VIRTUAL (no tocan el saldo de la cuenta ficticia).\n\n' +
      'Para materializar el ingreso, generá una Nota Interna desde el reporte de Producción y procesala.'
    );
    if (!confirm) return;
    try {
      setGenerando(true);
      const res = await generarCargosInternos();
      toast.success(res.data.message);
      loadData();
    } catch (e) {
      toast.error('Error al generar cargos');
    } finally {
      setGenerando(false);
    }
  };

  // Filtro local por búsqueda
  const cargosFiltrados = cargos.filter(c => {
    if (!busqueda.trim()) return true;
    const q = busqueda.toLowerCase();
    return (
      (c.persona_nombre || '').toLowerCase().includes(q) ||
      (c.servicio_nombre || '').toLowerCase().includes(q) ||
      (c.unidad_nombre || '').toLowerCase().includes(q) ||
      (c.n_corte || '').toString().toLowerCase().includes(q) ||
      (c.modelo_nombre || '').toLowerCase().includes(q) ||
      (c.factura_numero || '').toLowerCase().includes(q)
    );
  });

  const totalImporte = cargosFiltrados.reduce((sum, c) => sum + (c.importe || 0), 0);
  const totalCantidad = cargosFiltrados.reduce((sum, c) => sum + (c.cantidad || 0), 0);
  const conNota = cargosFiltrados.filter(c => c.tiene_nota_interna).length;
  const sinNota = cargosFiltrados.length - conNota;

  const s = {
    page: { padding: '1.5rem', maxWidth: 1200, margin: '0 auto' },
    header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' },
    title: { fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-heading)', display: 'flex', alignItems: 'center', gap: 10 },
    card: { background: 'var(--card-bg)', borderRadius: 10, border: '1px solid var(--border)', overflow: 'hidden' },
    table: { width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' },
    th: { padding: '10px 14px', textAlign: 'left', fontWeight: 600, color: 'var(--muted)', borderBottom: '2px solid var(--border)', background: 'var(--card-bg-hover)', fontSize: '0.75rem', textTransform: 'uppercase' },
    td: { padding: '10px 14px', borderBottom: '1px solid var(--table-row-border)' },
    btn: { padding: '6px 14px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 6 },
    btnPrimary: { background: '#3b82f6', color: 'var(--card-bg)' },
    select: { padding: '8px 12px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: '0.85rem', background: 'var(--card-bg)' },
    badge: (color) => ({
      padding: '2px 8px', borderRadius: 4, fontSize: '0.7rem', fontWeight: 700,
      background: color === 'green' ? '#dcfce7' : color === 'blue' ? '#dbeafe' : 'var(--card-bg-alt)',
      color: color === 'green' ? '#15803d' : color === 'blue' ? '#1d4ed8' : 'var(--muted)'
    }),
    filterBar: { display: 'flex', gap: 12, alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap' },
    summaryRow: { display: 'flex', gap: 16, marginBottom: '0.75rem', flexWrap: 'wrap' },
    summaryCard: (bg) => ({ background: bg, borderRadius: 8, padding: '0.75rem 1rem', flex: 1, minWidth: 200 }),
  };

  return (
    <div style={s.page} data-testid="cargos-internos-page">
      <div style={s.header}>
        <div style={s.title}><ArrowRightLeft size={22} /> Cargos Internos</div>
        <button style={{ ...s.btn, ...s.btnPrimary }} onClick={handleGenerar} disabled={generando} data-testid="generar-cargos-btn">
          {generando ? <><RefreshCw size={16} className="spin" /> Generando...</> : <><Zap size={16} /> Generar Cargos</>}
        </button>
      </div>

      <div style={s.filterBar}>
        <Filter size={16} color="#64748b" />
        <Calendar size={14} color="#64748b" />
        <input
          type="date"
          style={s.select}
          value={fechaDesde}
          onChange={e => setFechaDesde(e.target.value)}
          title="Desde"
        />
        <input
          type="date"
          style={s.select}
          value={fechaHasta}
          onChange={e => setFechaHasta(e.target.value)}
          title="Hasta"
        />
        <button
          onClick={() => { setFechaDesde(''); setFechaHasta(''); }}
          style={{ ...s.select, cursor: 'pointer', color: 'var(--muted)', border: '1px dashed var(--border)' }}
          title="Limpiar fechas (ver todo el histórico)"
        >
          <X size={12} style={{ display: 'inline' }} /> sin fecha
        </button>
        <select style={s.select} value={filtroUnidad} onChange={e => setFiltroUnidad(e.target.value)} data-testid="filtro-cargos-unidad">
          <option value="">Todas las unidades</option>
          {unidades.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}
        </select>
        <select style={s.select} value={filtroNota} onChange={e => setFiltroNota(e.target.value)} data-testid="filtro-cargos-nota">
          <option value="">Todos los cargos</option>
          <option value="si">Solo con Nota Interna</option>
          <option value="no">Solo legacy (sin nota)</option>
        </select>
        <input
          type="text"
          placeholder="Buscar corte, modelo, persona, factura..."
          value={busqueda}
          onChange={e => setBusqueda(e.target.value)}
          style={{ ...s.select, minWidth: 200, flex: 1 }}
        />
      </div>
      <div style={{ color: 'var(--muted)', fontSize: '0.7rem', marginBottom: '0.75rem', fontStyle: 'italic' }}>
        Por defecto se muestra el mes actual. Los cargos con <b>🏭 Nota Interna</b> pueden ser <b>pagados</b> (contabilizados en la cuenta ficticia) o <b>generados</b> (CxC virtual pendiente de procesar). Los <b>legacy</b> son cargos sin NI — son CxC virtuales que no impactan el saldo hasta vincularlos a una Nota Interna.
      </div>

      {cargosFiltrados.length > 0 && (
        <div style={s.summaryRow}>
          <div style={s.summaryCard('#f0fdf4')}>
            <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--success-text)', textTransform: 'uppercase' }}>Total Importe</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--success-text)', fontFamily: "'JetBrains Mono', monospace" }}>{formatCurrency(totalImporte)}</div>
          </div>
          <div style={s.summaryCard('#eff6ff')}>
            <div style={{ fontSize: '0.7rem', fontWeight: 600, color: '#1d4ed8', textTransform: 'uppercase' }}>Total Cantidad</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#1d4ed8', fontFamily: "'JetBrains Mono', monospace" }}>{totalCantidad.toLocaleString()}</div>
          </div>
          <div style={s.summaryCard('var(--card-bg-hover)')}>
            <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase' }}>Total Cargos</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-secondary)' }}>{cargosFiltrados.length}</div>
          </div>
          <div style={s.summaryCard('#fef3c7')}>
            <div style={{ fontSize: '0.7rem', fontWeight: 600, color: '#b45309', textTransform: 'uppercase' }}>Con NI / Legacy</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#b45309', fontFamily: "'JetBrains Mono', monospace" }}>
              {conNota} / {sinNota}
            </div>
          </div>
        </div>
      )}

      <div style={s.card}>
        <table style={s.table}>
          <thead>
            <tr>
              <th style={s.th}>Fecha</th>
              <th style={s.th}>N° Corte</th>
              <th style={s.th}>Modelo</th>
              <th style={s.th}>Unidad</th>
              <th style={s.th}>Servicio</th>
              <th style={s.th}>Persona</th>
              <th style={{ ...s.th, textAlign: 'right' }}>Cantidad</th>
              <th style={{ ...s.th, textAlign: 'right' }}>Tarifa</th>
              <th style={{ ...s.th, textAlign: 'right' }}>Importe</th>
              <th style={s.th}>Nota Interna</th>
              <th style={s.th}>Estado</th>
            </tr>
          </thead>
          <tbody>
            {cargosFiltrados.length === 0 && (
              <tr><td colSpan={11} style={{ ...s.td, textAlign: 'center', color: 'var(--muted)', padding: 32 }}>
                {cargos.length === 0
                  ? 'No hay cargos internos. Presioná "Generar Cargos" para crear desde movimientos de produccion.'
                  : 'Sin resultados con los filtros actuales'}
              </td></tr>
            )}
            {cargosFiltrados.map(c => (
              <tr key={c.id} data-testid={`cargo-row-${c.id}`}>
                <td style={s.td}>{c.fecha?.slice(0, 10)}</td>
                <td style={{ ...s.td, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>{c.n_corte || '-'}</td>
                <td style={s.td}>{c.modelo_nombre || <span style={{ color: 'var(--muted)', fontStyle: 'italic' }}>—</span>}</td>
                <td style={{ ...s.td, fontWeight: 600 }}>{c.unidad_nombre || '-'}</td>
                <td style={s.td}>{c.servicio_nombre || '-'}</td>
                <td style={s.td}>{c.persona_nombre || '-'}</td>
                <td style={{ ...s.td, textAlign: 'right', fontFamily: "'JetBrains Mono', monospace" }}>{(c.cantidad || 0).toLocaleString()}</td>
                <td style={{ ...s.td, textAlign: 'right', fontFamily: "'JetBrains Mono', monospace" }}>{(c.tarifa || 0).toFixed(4)}</td>
                <td style={{ ...s.td, textAlign: 'right', fontWeight: 700, color: '#16a34a', fontFamily: "'JetBrains Mono', monospace" }}>
                  {formatCurrency(c.importe)}
                </td>
                <td style={s.td}>
                  {c.tiene_nota_interna ? (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: '#fef3c7', color: '#b45309', padding: '2px 8px', borderRadius: 4, fontSize: '0.7rem', fontWeight: 600, fontFamily: "'JetBrains Mono', monospace" }}>
                      🏭 {c.factura_numero}
                    </span>
                  ) : (
                    <span style={{ color: 'var(--muted)', fontSize: '0.7rem', fontStyle: 'italic' }}>legacy</span>
                  )}
                </td>
                <td style={s.td}><span style={s.badge('green')}>{c.estado}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
