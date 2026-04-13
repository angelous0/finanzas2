import React, { useState, useEffect, useCallback } from 'react';
import { useEmpresa } from '../context/EmpresaContext';
import { getValorizacionInventario } from '../services/api';
import { Package, Search, Filter, ChevronDown, ChevronRight, RefreshCw, Eye, EyeOff, Layers } from 'lucide-react';

const fmt = (val) => {
  const n = Number(val) || 0;
  return `S/ ${n.toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const fmtQty = (val) => {
  const n = Number(val) || 0;
  return n.toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const CAT_COLORS = {
  'Jean': { bg: '#dbeafe', text: '#1e40af', border: '#93c5fd' },
  'Polo': { bg: '#fce7f3', text: '#9d174d', border: '#f9a8d4' },
  'Drill': { bg: '#fef3c7', text: '#92400e', border: '#fcd34d' },
  'Otros': { bg: 'var(--card-bg-alt)', text: 'var(--text-label)', border: 'var(--input-border)' },
  'Telas': { bg: '#d1fae5', text: '#065f46', border: '#6ee7b7' },
  'Punto': { bg: '#ede9fe', text: '#5b21b6', border: '#c4b5fd' },
  'Avios': { bg: '#fff7ed', text: '#c2410c', border: '#fdba74' },
  'Franela': { bg: '#fdf2f8', text: '#831843', border: '#f9a8d4' },
  'Rigido': { bg: 'var(--success-bg)', text: '#166534', border: '#86efac' },
  'PT': { bg: '#f0f9ff', text: '#0369a1', border: '#7dd3fc' },
};

const getCatColor = (cat) => CAT_COLORS[cat] || { bg: 'var(--card-bg-hover)', text: 'var(--muted)', border: 'var(--border)' };

export default function ValorizacionInventario() {
  const { empresaActual } = useEmpresa();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [categoria, setCategoria] = useState('');
  const [expandedItem, setExpandedItem] = useState(null);
  const [showZeroStock, setShowZeroStock] = useState(false);
  const [collapsedCats, setCollapsedCats] = useState({});

  const eId = empresaActual?.id;

  const fetchData = useCallback(async () => {
    if (!eId) return;
    setLoading(true);
    try {
      const params = {};
      if (search) params.search = search;
      if (categoria) params.categoria = categoria;
      const res = await getValorizacionInventario(params);
      setData(res.data);
    } catch (e) {
      console.error('Error:', e);
    } finally {
      setLoading(false);
    }
  }, [eId, search, categoria]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (!eId) return <div style={{ padding: '2rem', color: 'var(--muted)' }}>Seleccione una empresa</div>;

  // Group items by categoria
  const items = data?.data || [];
  const filtered = showZeroStock ? items : items.filter(i => i.stock_actual > 0 || i.stock_fifo > 0);
  const grouped = {};
  filtered.forEach(item => {
    const cat = item.categoria || 'Sin Categoria';
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(item);
  });

  // Category totals
  const catTotals = {};
  Object.entries(grouped).forEach(([cat, items]) => {
    catTotals[cat] = {
      items: items.length,
      stockTotal: items.reduce((s, i) => s + (i.stock_actual || 0), 0),
      valorFifo: items.reduce((s, i) => s + (i.valor_fifo || 0), 0),
      valorProm: items.reduce((s, i) => s + (i.valor_promedio || 0), 0),
    };
  });

  // Sort categories by valor_fifo desc
  const sortedCats = Object.keys(grouped).sort((a, b) => (catTotals[b]?.valorFifo || 0) - (catTotals[a]?.valorFifo || 0));

  const toggleCat = (cat) => setCollapsedCats(prev => ({ ...prev, [cat]: !prev[cat] }));

  const totalConStock = items.filter(i => i.stock_actual > 0 || i.stock_fifo > 0).length;

  const s = {
    page: { padding: '1.5rem', maxWidth: 1400, margin: '0 auto' },
    header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: 12 },
    title: { fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-heading)', display: 'flex', alignItems: 'center', gap: 10 },
    subtitle: { fontSize: '0.8rem', color: 'var(--muted)', marginTop: 2 },
    kpiRow: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12, marginBottom: '1rem' },
    kpiCard: (borderColor) => ({
      background: 'var(--card-bg)', borderRadius: 10, padding: '0.85rem 1rem', border: '1px solid var(--border)',
      borderLeft: `4px solid ${borderColor}`
    }),
    kpiLabel: { fontSize: '0.7rem', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.5px' },
    kpiValue: (color) => ({ fontSize: '1.3rem', fontWeight: 800, color, marginTop: 2, fontFamily: "'JetBrains Mono', monospace" }),
    filterBar: {
      display: 'flex', gap: 12, alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap',
      background: 'var(--card-bg)', borderRadius: 10, padding: '0.75rem 1rem', border: '1px solid var(--border)'
    },
    input: { padding: '7px 12px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: '0.8rem', minWidth: 180 },
    select: { padding: '7px 12px', borderRadius: 6, border: '1px solid #d1d5db', fontSize: '0.8rem', background: 'var(--card-bg)' },
    btn: { padding: '6px 12px', borderRadius: 6, border: '1px solid var(--border)', cursor: 'pointer', fontSize: '0.75rem', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 6, background: 'var(--card-bg)', color: 'var(--muted)' },
    btnActive: { background: 'var(--success-bg)', color: '#16a34a', borderColor: '#bbf7d0' },
    catHeader: (color) => ({
      display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.6rem 1rem',
      background: color.bg, borderBottom: `1px solid ${color.border}`, cursor: 'pointer', userSelect: 'none'
    }),
    catTitle: (color) => ({ fontWeight: 700, fontSize: '0.85rem', color: color.text, display: 'flex', alignItems: 'center', gap: 8 }),
    catStats: { display: 'flex', gap: 20, fontSize: '0.75rem', fontWeight: 600 },
    card: { background: 'var(--card-bg)', borderRadius: 10, border: '1px solid var(--border)', overflow: 'hidden', marginBottom: '0.75rem' },
    table: { width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' },
    th: { padding: '8px 12px', textAlign: 'left', fontWeight: 600, color: 'var(--muted)', borderBottom: '1px solid var(--border)', fontSize: '0.7rem', textTransform: 'uppercase' },
    td: { padding: '7px 12px', borderBottom: '1px solid #f8fafc' },
    lotePanel: { background: '#f0f9ff', padding: '0.75rem 1rem', margin: '0 12px 8px 40px', borderRadius: 8, border: '1px solid #bae6fd' },
    badge: (color) => ({
      padding: '2px 8px', borderRadius: 4, fontSize: '0.65rem', fontWeight: 700,
      background: color.bg, color: color.text, border: `1px solid ${color.border}`
    }),
    footerRow: { background: 'var(--card-bg-hover)', fontWeight: 800, borderTop: '2px solid var(--border)' },
  };

  return (
    <div style={s.page} data-testid="valorizacion-page">
      <div style={s.header}>
        <div>
          <div style={s.title}><Package size={22} color="#3b82f6" /> Valorizacion de Inventario</div>
          <div style={s.subtitle}>Costeo FIFO - Materia prima desde Produccion</div>
        </div>
        <button onClick={fetchData} style={s.btn} data-testid="refresh-val-btn">
          <RefreshCw size={14} /> Actualizar
        </button>
      </div>

      {/* KPIs */}
      {data && (
        <div style={s.kpiRow} data-testid="valorizacion-kpis">
          <div style={s.kpiCard('#3b82f6')}>
            <div style={s.kpiLabel}>Total Articulos</div>
            <div style={s.kpiValue('#0f172a')}>{data.total_articulos}</div>
            <div style={{ fontSize: '0.7rem', color: 'var(--muted)', marginTop: 2 }}>{totalConStock} con stock</div>
          </div>
          <div style={s.kpiCard('#16a34a')}>
            <div style={s.kpiLabel}>Valor Total FIFO</div>
            <div style={s.kpiValue('#16a34a')}>{fmt(data.total_valor_fifo)}</div>
          </div>
          <div style={s.kpiCard('#d97706')}>
            <div style={s.kpiLabel}>Valor Total Promedio</div>
            <div style={s.kpiValue('#d97706')}>{fmt(data.total_valor_promedio)}</div>
          </div>
          <div style={s.kpiCard('#7c3aed')}>
            <div style={s.kpiLabel}>Categorias</div>
            <div style={s.kpiValue('#7c3aed')}>{data.categorias?.length || 0}</div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div style={s.filterBar} data-testid="valorizacion-filtros">
        <Filter size={16} color="#94a3b8" />
        <div style={{ position: 'relative' }}>
          <Search size={14} style={{ position: 'absolute', left: 8, top: 9, color: 'var(--muted)' }} />
          <input
            type="text" placeholder="Buscar articulo..."
            value={search} onChange={e => setSearch(e.target.value)}
            style={{ ...s.input, paddingLeft: 28 }} data-testid="valorizacion-search"
          />
        </div>
        <select value={categoria} onChange={e => setCategoria(e.target.value)}
          style={s.select} data-testid="valorizacion-cat-filter">
          <option value="">Todas las categorias</option>
          {data?.categorias?.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <button
          style={{ ...s.btn, ...(showZeroStock ? {} : s.btnActive) }}
          onClick={() => setShowZeroStock(!showZeroStock)}
          data-testid="toggle-zero-stock"
        >
          {showZeroStock ? <Eye size={14} /> : <EyeOff size={14} />}
          {showZeroStock ? 'Mostrando todos' : 'Solo con stock'}
        </button>
        <span style={{ color: 'var(--muted)', fontSize: '0.75rem', marginLeft: 'auto' }}>
          {filtered.length} articulos mostrados
        </span>
      </div>

      {/* Grouped by category */}
      {loading ? (
        <div style={{ ...s.card, padding: 40, textAlign: 'center', color: 'var(--muted)' }}>Cargando...</div>
      ) : sortedCats.length === 0 ? (
        <div style={{ ...s.card, padding: 40, textAlign: 'center', color: 'var(--muted)' }}>
          Sin articulos{!showZeroStock ? ' con stock. Active "Mostrando todos" para ver items sin stock.' : '.'}
        </div>
      ) : (
        sortedCats.map(cat => {
          const color = getCatColor(cat);
          const totals = catTotals[cat];
          const isCollapsed = collapsedCats[cat];
          const catItems = grouped[cat];

          return (
            <div key={cat} style={s.card} data-testid={`cat-group-${cat}`}>
              {/* Category Header */}
              <div style={s.catHeader(color)} onClick={() => toggleCat(cat)}>
                <div style={s.catTitle(color)}>
                  {isCollapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
                  <Layers size={16} />
                  {cat}
                  <span style={{ fontWeight: 400, fontSize: '0.75rem', color: color.text, opacity: 0.7 }}>
                    ({totals.items} articulo{totals.items !== 1 ? 's' : ''})
                  </span>
                </div>
                <div style={s.catStats}>
                  <span style={{ color: 'var(--muted)' }}>Stock: <strong>{fmtQty(totals.stockTotal)}</strong></span>
                  <span style={{ color: '#16a34a' }}>FIFO: <strong>{fmt(totals.valorFifo)}</strong></span>
                  <span style={{ color: '#d97706' }}>Prom: <strong>{fmt(totals.valorProm)}</strong></span>
                </div>
              </div>

              {/* Items table */}
              {!isCollapsed && (
                <table style={s.table}>
                  <thead>
                    <tr>
                      <th style={{ ...s.th, width: 30 }}></th>
                      <th style={s.th}>Codigo</th>
                      <th style={s.th}>Nombre</th>
                      <th style={s.th}>Unidad</th>
                      <th style={{ ...s.th, textAlign: 'right' }}>Stock</th>
                      <th style={{ ...s.th, textAlign: 'right' }}>Costo FIFO Unit.</th>
                      <th style={{ ...s.th, textAlign: 'right' }}>Valor FIFO</th>
                      <th style={{ ...s.th, textAlign: 'right' }}>Costo Prom.</th>
                      <th style={{ ...s.th, textAlign: 'right' }}>Valor Prom.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {catItems.map(item => (
                      <React.Fragment key={item.id}>
                        <tr
                          style={{ cursor: item.lotes_fifo?.length > 0 ? 'pointer' : 'default', transition: 'background 0.1s' }}
                          onClick={() => item.lotes_fifo?.length > 0 && setExpandedItem(expandedItem === item.id ? null : item.id)}
                          onMouseEnter={e => e.currentTarget.style.background = 'var(--card-bg-hover)'}
                          onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                          data-testid={`val-row-${item.codigo}`}
                        >
                          <td style={s.td}>
                            {item.lotes_fifo?.length > 0 ? (
                              expandedItem === item.id
                                ? <ChevronDown size={14} color="#94a3b8" />
                                : <ChevronRight size={14} color="#94a3b8" />
                            ) : null}
                          </td>
                          <td style={{ ...s.td, fontFamily: "'JetBrains Mono', monospace", fontSize: '0.75rem', color: 'var(--muted)' }}>{item.codigo}</td>
                          <td style={{ ...s.td, fontWeight: 600, color: 'var(--text-heading)' }}>{item.nombre}</td>
                          <td style={{ ...s.td, color: 'var(--muted)' }}>{item.unidad}</td>
                          <td style={{
                            ...s.td, textAlign: 'right', fontWeight: 700,
                            fontFamily: "'JetBrains Mono', monospace",
                            color: item.stock_actual < 0 ? '#dc2626' : item.stock_actual > 0 ? 'var(--text-heading)' : '#cbd5e1'
                          }}>
                            {fmtQty(item.stock_actual)}
                          </td>
                          <td style={{ ...s.td, textAlign: 'right', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.75rem' }}>
                            {fmt(item.costo_fifo_unitario)}
                          </td>
                          <td style={{ ...s.td, textAlign: 'right', fontWeight: 700, color: '#16a34a', fontFamily: "'JetBrains Mono', monospace" }}>
                            {fmt(item.valor_fifo)}
                          </td>
                          <td style={{ ...s.td, textAlign: 'right', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.75rem' }}>
                            {fmt(item.costo_promedio)}
                          </td>
                          <td style={{ ...s.td, textAlign: 'right', fontFamily: "'JetBrains Mono', monospace" }}>
                            {fmt(item.valor_promedio)}
                          </td>
                        </tr>
                        {/* Expanded FIFO lots */}
                        {expandedItem === item.id && item.lotes_fifo?.length > 0 && (
                          <tr>
                            <td colSpan={9} style={{ padding: 0 }}>
                              <div style={s.lotePanel}>
                                <div style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--info-text)', marginBottom: 6, textTransform: 'uppercase' }}>
                                  Lotes FIFO disponibles (mas antiguo primero)
                                </div>
                                <table style={{ ...s.table, fontSize: '0.72rem' }}>
                                  <thead>
                                    <tr>
                                      <th style={{ ...s.th, fontSize: '0.65rem', borderColor: '#bae6fd' }}>Fecha Ingreso</th>
                                      <th style={{ ...s.th, fontSize: '0.65rem', borderColor: '#bae6fd' }}>Documento</th>
                                      <th style={{ ...s.th, fontSize: '0.65rem', borderColor: '#bae6fd', textAlign: 'right' }}>Disponible</th>
                                      <th style={{ ...s.th, fontSize: '0.65rem', borderColor: '#bae6fd', textAlign: 'right' }}>Costo Unit.</th>
                                      <th style={{ ...s.th, fontSize: '0.65rem', borderColor: '#bae6fd', textAlign: 'right' }}>Valor Lote</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {item.lotes_fifo.map((lote, i) => (
                                      <tr key={lote.id || i}>
                                        <td style={{ ...s.td, borderColor: '#e0f2fe' }}>{lote.fecha?.split('T')[0] || '-'}</td>
                                        <td style={{ ...s.td, borderColor: '#e0f2fe' }}>{lote.documento || '-'}</td>
                                        <td style={{ ...s.td, borderColor: '#e0f2fe', textAlign: 'right', fontFamily: "'JetBrains Mono', monospace" }}>
                                          {fmtQty(lote.cantidad_disponible)}
                                        </td>
                                        <td style={{ ...s.td, borderColor: '#e0f2fe', textAlign: 'right', fontFamily: "'JetBrains Mono', monospace" }}>
                                          {fmt(lote.costo_unitario)}
                                        </td>
                                        <td style={{ ...s.td, borderColor: '#e0f2fe', textAlign: 'right', fontWeight: 700, fontFamily: "'JetBrains Mono', monospace", color: 'var(--info-text)' }}>
                                          {fmt(lote.cantidad_disponible * lote.costo_unitario)}
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                    {/* Category subtotal row */}
                    <tr style={s.footerRow}>
                      <td colSpan={4} style={{ ...s.td, textAlign: 'right', fontWeight: 800, fontSize: '0.75rem' }}>
                        Subtotal {cat}
                      </td>
                      <td style={{ ...s.td, textAlign: 'right', fontWeight: 800, fontFamily: "'JetBrains Mono', monospace" }}>
                        {fmtQty(totals.stockTotal)}
                      </td>
                      <td style={s.td}></td>
                      <td style={{ ...s.td, textAlign: 'right', fontWeight: 800, color: '#16a34a', fontFamily: "'JetBrains Mono', monospace" }}>
                        {fmt(totals.valorFifo)}
                      </td>
                      <td style={s.td}></td>
                      <td style={{ ...s.td, textAlign: 'right', fontWeight: 800, color: '#d97706', fontFamily: "'JetBrains Mono', monospace" }}>
                        {fmt(totals.valorProm)}
                      </td>
                    </tr>
                  </tbody>
                </table>
              )}
            </div>
          );
        })
      )}

      {/* Grand total */}
      {data && sortedCats.length > 0 && (
        <div style={{
          ...s.card, padding: '0.85rem 1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          background: 'var(--text-heading)', color: 'var(--card-bg)', border: 'none'
        }} data-testid="grand-total-bar">
          <span style={{ fontWeight: 800, fontSize: '0.85rem' }}>TOTAL INVENTARIO VALORIZADO</span>
          <div style={{ display: 'flex', gap: 32 }}>
            <div>
              <span style={{ fontSize: '0.65rem', color: 'var(--muted)', textTransform: 'uppercase', fontWeight: 600 }}>FIFO</span>
              <div style={{ fontWeight: 800, fontSize: '1.1rem', fontFamily: "'JetBrains Mono', monospace", color: '#4ade80' }}>
                {fmt(data.total_valor_fifo)}
              </div>
            </div>
            <div>
              <span style={{ fontSize: '0.65rem', color: 'var(--muted)', textTransform: 'uppercase', fontWeight: 600 }}>Promedio</span>
              <div style={{ fontWeight: 800, fontSize: '1.1rem', fontFamily: "'JetBrains Mono', monospace", color: '#fbbf24' }}>
                {fmt(data.total_valor_promedio)}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
