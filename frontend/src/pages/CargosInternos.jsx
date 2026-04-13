import React, { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { RefreshCw, Filter, Zap, ArrowRightLeft } from 'lucide-react';
import { getCargosInternos, generarCargosInternos, getUnidadesInternas } from '../services/api';

const formatCurrency = (v) => `S/ ${(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function CargosInternos() {
  const [cargos, setCargos] = useState([]);
  const [unidades, setUnidades] = useState([]);
  const [loading, setLoading] = useState(false);
  const [generando, setGenerando] = useState(false);
  const [filtroUnidad, setFiltroUnidad] = useState('');

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const params = {};
      if (filtroUnidad) params.unidad_interna_id = filtroUnidad;
      const [cRes, uRes] = await Promise.all([getCargosInternos(params), getUnidadesInternas()]);
      setCargos(cRes.data || []);
      setUnidades(uRes.data || []);
    } catch (e) {
      toast.error('Error al cargar cargos');
    } finally {
      setLoading(false);
    }
  }, [filtroUnidad]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleGenerar = async () => {
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

  const totalImporte = cargos.reduce((sum, c) => sum + (c.importe || 0), 0);
  const totalCantidad = cargos.reduce((sum, c) => sum + (c.cantidad || 0), 0);

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
        <select style={s.select} value={filtroUnidad} onChange={e => setFiltroUnidad(e.target.value)} data-testid="filtro-cargos-unidad">
          <option value="">Todas las unidades</option>
          {unidades.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}
        </select>
        <span style={{ color: 'var(--muted)', fontSize: '0.75rem' }}>
          Genera cargos desde movimientos de produccion de personas internas.
        </span>
      </div>

      {cargos.length > 0 && (
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
            <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase' }}>Cargos</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-secondary)' }}>{cargos.length}</div>
          </div>
        </div>
      )}

      <div style={s.card}>
        <table style={s.table}>
          <thead>
            <tr>
              <th style={s.th}>Fecha</th>
              <th style={s.th}>Unidad</th>
              <th style={s.th}>Servicio</th>
              <th style={s.th}>Persona</th>
              <th style={{ ...s.th, textAlign: 'right' }}>Cantidad</th>
              <th style={{ ...s.th, textAlign: 'right' }}>Tarifa</th>
              <th style={{ ...s.th, textAlign: 'right' }}>Importe</th>
              <th style={s.th}>Estado</th>
            </tr>
          </thead>
          <tbody>
            {cargos.length === 0 && (
              <tr><td colSpan={8} style={{ ...s.td, textAlign: 'center', color: 'var(--muted)', padding: 32 }}>
                No hay cargos internos. Presione "Generar Cargos" para crear desde movimientos de produccion.
              </td></tr>
            )}
            {cargos.map(c => (
              <tr key={c.id} data-testid={`cargo-row-${c.id}`}>
                <td style={s.td}>{c.fecha?.slice(0, 10)}</td>
                <td style={{ ...s.td, fontWeight: 600 }}>{c.unidad_nombre || '-'}</td>
                <td style={s.td}>{c.servicio_nombre || '-'}</td>
                <td style={s.td}>{c.persona_nombre || '-'}</td>
                <td style={{ ...s.td, textAlign: 'right', fontFamily: "'JetBrains Mono', monospace" }}>{(c.cantidad || 0).toLocaleString()}</td>
                <td style={{ ...s.td, textAlign: 'right', fontFamily: "'JetBrains Mono', monospace" }}>{(c.tarifa || 0).toFixed(4)}</td>
                <td style={{ ...s.td, textAlign: 'right', fontWeight: 700, color: '#16a34a', fontFamily: "'JetBrains Mono', monospace" }}>
                  {formatCurrency(c.importe)}
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
