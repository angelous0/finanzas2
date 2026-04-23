import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import {
  Wallet, Calendar, ArrowLeft, RefreshCw, Download, Search,
  TrendingUp, TrendingDown, Minus, Factory, Receipt, FileText,
} from 'lucide-react';
import { getKardexCuenta } from '../services/api';

const fmt = (v) => `S/ ${(v || 0).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const todayISO = () => new Date().toISOString().slice(0, 10);
const firstOfMonthISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
};

export default function KardexCuentaInterna() {
  const { id: cuentaId } = useParams();
  const [searchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [desde, setDesde] = useState(searchParams.get('desde') || firstOfMonthISO());
  const [hasta, setHasta] = useState(searchParams.get('hasta') || todayISO());
  const [tipoFiltro, setTipoFiltro] = useState(''); // '' | 'ingreso' | 'egreso'
  const [busqueda, setBusqueda] = useState('');

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const res = await getKardexCuenta(cuentaId, { fecha_desde: desde, fecha_hasta: hasta });
      setData(res.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error al cargar kardex');
    } finally {
      setLoading(false);
    }
  }, [cuentaId, desde, hasta]);

  useEffect(() => { load(); }, [load]);

  const movimientosFiltrados = useMemo(() => {
    const movs = data?.movimientos || [];
    return movs.filter(m => {
      if (tipoFiltro && m.tipo !== tipoFiltro) return false;
      if (busqueda.trim()) {
        const q = busqueda.toLowerCase();
        return (
          (m.concepto || '').toLowerCase().includes(q) ||
          (m.referencia_tipo || '').toLowerCase().includes(q) ||
          (m.medio_pago || '').toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [data, tipoFiltro, busqueda]);

  const cuenta = data?.cuenta || {};

  // Calculamos totales sobre lo filtrado (pueden diferir de los totales del backend cuando hay filtro)
  const totalesFiltrados = useMemo(() => {
    let ing = 0, egr = 0;
    for (const m of movimientosFiltrados) {
      ing += Number(m.ingreso || 0);
      egr += Number(m.egreso || 0);
    }
    return { ing, egr };
  }, [movimientosFiltrados]);

  const exportarCSV = () => {
    if (!movimientosFiltrados.length) return;
    const headers = ['Fecha', 'Tipo', 'Concepto', 'Referencia', 'Ingreso', 'Egreso', 'Saldo'];
    const rows = movimientosFiltrados.map(m => [
      m.fecha || '',
      m.tipo || '',
      m.concepto || '',
      m.referencia_tipo ? `${m.referencia_tipo}:${m.referencia_id || ''}` : (m.medio_pago || ''),
      Number(m.ingreso || 0).toFixed(2),
      Number(m.egreso || 0).toFixed(2),
      Number(m.saldo || 0).toFixed(2),
    ]);
    const csv = [headers, ...rows]
      .map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(','))
      .join('\n');
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `kardex_${cuenta.nombre || cuentaId}_${desde}_${hasta}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const iconoReferencia = (tipo) => {
    if (tipo === 'CARGO_INTERNO') return <Factory size={13} style={{ color: '#b45309' }} />;
    if (tipo === 'GASTO_UNIDAD') return <FileText size={13} style={{ color: '#dc2626' }} />;
    if (tipo === 'FACTURA') return <Receipt size={13} style={{ color: '#2563eb' }} />;
    return null;
  };

  const s = {
    page: { padding: '1.5rem', maxWidth: 1400, margin: '0 auto' },
    header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.25rem', flexWrap: 'wrap', gap: 12 },
    titleBlock: { display: 'flex', flexDirection: 'column', gap: 4 },
    title: { fontSize: '1.5rem', fontWeight: 700, color: 'var(--text-heading)', display: 'flex', alignItems: 'center', gap: 10 },
    subtitle: { fontSize: '0.85rem', color: 'var(--muted)' },
    backBtn: { background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', fontSize: '0.75rem', display: 'inline-flex', alignItems: 'center', gap: 4, padding: 0, marginBottom: 6 },
    cards: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12, marginBottom: '1rem' },
    card: (bg, border) => ({ background: bg, borderRadius: 10, padding: '0.9rem 1rem', border: `1px solid ${border}` }),
    label: { fontSize: '0.7rem', fontWeight: 600, textTransform: 'uppercase', marginBottom: 4 },
    value: { fontSize: '1.2rem', fontWeight: 800, fontFamily: "'JetBrains Mono', monospace" },
    filters: { display: 'flex', gap: 12, alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', background: 'var(--card-bg)', padding: '0.75rem 1rem', borderRadius: 8, border: '1px solid var(--border)' },
    input: { padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border)', fontSize: '0.85rem', background: 'var(--card-bg)' },
    btn: { padding: '6px 12px', borderRadius: 6, border: '1px solid var(--border)', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 6, background: 'var(--card-bg)' },
    table: { width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' },
    th: { padding: '10px 14px', textAlign: 'left', fontWeight: 600, color: 'var(--muted)', borderBottom: '2px solid var(--border)', background: 'var(--card-bg-hover)', fontSize: '0.7rem', textTransform: 'uppercase', position: 'sticky', top: 0 },
    td: { padding: '10px 14px', borderBottom: '1px solid var(--table-row-border)' },
    badge: (color) => ({
      padding: '2px 8px', borderRadius: 4, fontSize: '0.65rem', fontWeight: 700,
      background: color === 'green' ? '#dcfce7' : color === 'red' ? 'var(--danger-bg)' : 'var(--card-bg-alt)',
      color: color === 'green' ? '#15803d' : color === 'red' ? '#dc2626' : 'var(--muted)',
      display: 'inline-flex', alignItems: 'center', gap: 3,
    }),
  };

  const isFicticia = cuenta.es_ficticia;
  const saldoInicial = Number(data?.saldo_inicial || 0);
  const saldoFinal = Number(data?.saldo_final || 0);
  const totalIng = Number(data?.total_ingresos || 0);
  const totalEgr = Number(data?.total_egresos || 0);

  return (
    <div style={s.page} data-testid="kardex-cuenta-interna">
      <div style={s.header}>
        <div style={s.titleBlock}>
          <button style={s.backBtn} onClick={() => window.history.back()}>
            <ArrowLeft size={12} /> Volver
          </button>
          <div style={s.title}>
            {isFicticia ? <Factory size={22} /> : <Wallet size={22} />}
            Kardex — {cuenta.nombre || 'Cuenta'}
          </div>
          <div style={s.subtitle}>
            {isFicticia
              ? <>Cuenta ficticia de la unidad interna. Los movimientos representan ingresos virtuales (cargos) y egresos (gastos imputados).</>
              : <>Cuenta financiera real.</>}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button style={s.btn} onClick={load} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'spin' : ''} /> Actualizar
          </button>
          <button style={s.btn} onClick={exportarCSV} disabled={!movimientosFiltrados.length}>
            <Download size={14} /> CSV
          </button>
        </div>
      </div>

      {/* KPIs */}
      <div style={s.cards}>
        <div style={s.card('var(--card-bg-hover)', 'var(--border)')}>
          <div style={{ ...s.label, color: 'var(--muted)' }}>Saldo Inicial</div>
          <div style={{ ...s.value, color: saldoInicial >= 0 ? '#15803d' : '#dc2626' }}>{fmt(saldoInicial)}</div>
        </div>
        <div style={s.card('#f0fdf4', '#bbf7d0')}>
          <div style={{ ...s.label, color: '#15803d' }}>Ingresos período</div>
          <div style={{ ...s.value, color: '#15803d' }}>{fmt(totalIng)}</div>
        </div>
        <div style={s.card('#fef2f2', '#fecaca')}>
          <div style={{ ...s.label, color: '#dc2626' }}>Egresos período</div>
          <div style={{ ...s.value, color: '#dc2626' }}>{fmt(totalEgr)}</div>
        </div>
        <div style={s.card(saldoFinal >= 0 ? '#ecfdf5' : '#fef2f2', saldoFinal >= 0 ? '#86efac' : '#fca5a5')}>
          <div style={{ ...s.label, color: saldoFinal >= 0 ? '#15803d' : '#dc2626' }}>Saldo Final</div>
          <div style={{ ...s.value, color: saldoFinal >= 0 ? '#15803d' : '#dc2626' }}>{fmt(saldoFinal)}</div>
        </div>
        <div style={s.card('#eff6ff', '#bfdbfe')}>
          <div style={{ ...s.label, color: '#1d4ed8' }}>Resultado</div>
          <div style={{ ...s.value, color: (totalIng - totalEgr) >= 0 ? '#15803d' : '#dc2626', display: 'flex', alignItems: 'center', gap: 4 }}>
            {(totalIng - totalEgr) > 0 ? <TrendingUp size={18} /> : (totalIng - totalEgr) < 0 ? <TrendingDown size={18} /> : <Minus size={18} />}
            {fmt(totalIng - totalEgr)}
          </div>
        </div>
      </div>

      {/* Filtros */}
      <div style={s.filters}>
        <Calendar size={16} color="#64748b" />
        <label style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>Desde</label>
        <input type="date" style={s.input} value={desde} onChange={e => setDesde(e.target.value)} />
        <label style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>Hasta</label>
        <input type="date" style={s.input} value={hasta} onChange={e => setHasta(e.target.value)} />
        <select style={s.input} value={tipoFiltro} onChange={e => setTipoFiltro(e.target.value)}>
          <option value="">Todos los tipos</option>
          <option value="ingreso">Solo ingresos</option>
          <option value="egreso">Solo egresos</option>
        </select>
        <div style={{ position: 'relative', flex: 1, minWidth: 200 }}>
          <Search size={14} style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--muted)' }} />
          <input
            type="text"
            placeholder="Buscar concepto o referencia..."
            value={busqueda}
            onChange={e => setBusqueda(e.target.value)}
            style={{ ...s.input, paddingLeft: 28, width: '100%' }}
          />
        </div>
        {(tipoFiltro || busqueda) && (
          <div style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>
            Filtrado: {movimientosFiltrados.length} / {(data?.movimientos || []).length} movimientos ·
            Ingresos {fmt(totalesFiltrados.ing)} · Egresos {fmt(totalesFiltrados.egr)}
          </div>
        )}
      </div>

      {/* Tabla */}
      <div style={{ background: 'var(--card-bg)', borderRadius: 10, border: '1px solid var(--border)', overflow: 'hidden' }}>
        <div style={{ maxHeight: '60vh', overflow: 'auto' }}>
          <table style={s.table}>
            <thead>
              <tr>
                <th style={s.th}>Fecha</th>
                <th style={s.th}>Tipo</th>
                <th style={s.th}>Concepto</th>
                <th style={s.th}>Referencia</th>
                <th style={{ ...s.th, textAlign: 'right' }}>Ingreso</th>
                <th style={{ ...s.th, textAlign: 'right' }}>Egreso</th>
                <th style={{ ...s.th, textAlign: 'right' }}>Saldo</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} style={{ ...s.td, textAlign: 'center', color: 'var(--muted)', padding: 32 }}>Cargando...</td></tr>
              ) : movimientosFiltrados.length === 0 ? (
                <tr><td colSpan={7} style={{ ...s.td, textAlign: 'center', color: 'var(--muted)', padding: 32 }}>
                  {(data?.movimientos || []).length === 0 ? 'Sin movimientos en este período' : 'Sin resultados con los filtros actuales'}
                </td></tr>
              ) : (
                <>
                  {/* Fila saldo inicial */}
                  <tr style={{ background: 'var(--card-bg-hover)' }}>
                    <td style={s.td} colSpan={6}><b>Saldo inicial al {desde}</b></td>
                    <td style={{ ...s.td, textAlign: 'right', fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", color: saldoInicial >= 0 ? '#15803d' : '#dc2626' }}>
                      {fmt(saldoInicial)}
                    </td>
                  </tr>
                  {movimientosFiltrados.map((m, i) => (
                    <tr key={i}>
                      <td style={{ ...s.td, fontFamily: "'JetBrains Mono', monospace", fontSize: '0.75rem' }}>{m.fecha}</td>
                      <td style={s.td}>
                        <span style={s.badge(m.tipo === 'ingreso' ? 'green' : 'red')}>
                          {m.tipo === 'ingreso' ? '↑ Ingreso' : '↓ Egreso'}
                        </span>
                      </td>
                      <td style={{ ...s.td, maxWidth: 420 }}>{m.concepto || '-'}</td>
                      <td style={s.td}>
                        {m.referencia_tipo ? (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: '0.7rem', color: 'var(--muted)', fontFamily: "'JetBrains Mono', monospace" }}>
                            {iconoReferencia(m.referencia_tipo)}
                            {m.referencia_tipo}#{m.referencia_id}
                          </span>
                        ) : m.medio_pago ? (
                          <span style={{ fontSize: '0.7rem', color: 'var(--muted)' }}>{m.medio_pago}</span>
                        ) : (
                          <span style={{ color: 'var(--muted)' }}>-</span>
                        )}
                      </td>
                      <td style={{ ...s.td, textAlign: 'right', color: '#15803d', fontFamily: "'JetBrains Mono', monospace" }}>
                        {m.ingreso > 0 ? fmt(m.ingreso) : ''}
                      </td>
                      <td style={{ ...s.td, textAlign: 'right', color: '#dc2626', fontFamily: "'JetBrains Mono', monospace" }}>
                        {m.egreso > 0 ? fmt(m.egreso) : ''}
                      </td>
                      <td style={{ ...s.td, textAlign: 'right', fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", color: m.saldo >= 0 ? '#15803d' : '#dc2626' }}>
                        {fmt(m.saldo)}
                      </td>
                    </tr>
                  ))}
                </>
              )}
            </tbody>
            {movimientosFiltrados.length > 0 && (
              <tfoot>
                <tr style={{ background: 'var(--card-bg-hover)', position: 'sticky', bottom: 0 }}>
                  <td style={{ ...s.td, fontWeight: 800 }} colSpan={4}>Total período ({movimientosFiltrados.length} movimientos)</td>
                  <td style={{ ...s.td, textAlign: 'right', fontWeight: 800, color: '#15803d', fontFamily: "'JetBrains Mono', monospace" }}>
                    {fmt(totalesFiltrados.ing)}
                  </td>
                  <td style={{ ...s.td, textAlign: 'right', fontWeight: 800, color: '#dc2626', fontFamily: "'JetBrains Mono', monospace" }}>
                    {fmt(totalesFiltrados.egr)}
                  </td>
                  <td style={{ ...s.td, textAlign: 'right', fontWeight: 800, fontFamily: "'JetBrains Mono', monospace", color: saldoFinal >= 0 ? '#15803d' : '#dc2626' }}>
                    {fmt(saldoFinal)}
                  </td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </div>
    </div>
  );
}
