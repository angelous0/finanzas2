import React, { useState, useEffect, useCallback } from 'react';
import { Download, Search, ExternalLink, ArrowUpRight, ArrowDownRight, BookOpen } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import api from '../services/api';
import { getLineasNegocio, getMarcas, getCentrosCosto, getCategorias } from '../services/api';

const DIMENSIONS = [
  { value: 'linea_negocio', label: 'Linea de Negocio' },
  { value: 'marca', label: 'Marca' },
  { value: 'centro_costo', label: 'Centro de Costo' },
  { value: 'categoria', label: 'Categoria' },
];

const REF_ROUTES = {
  venta_pos: '/ventas-pos',
  pago: '/pagos',
  letra: '/letras',
  gasto: '/gastos',
  factura: '/facturas-proveedor',
};

const formatCurrency = (v) => {
  if (!v || v === 0) return '';
  return `S/ ${Number(v).toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const formatDate = (d) => {
  if (!d) return '';
  const parts = d.split('-');
  return `${parts[2]}/${parts[1]}/${parts[0]}`;
};

export default function LibroAnalitico() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const today = new Date().toISOString().split('T')[0];
  const firstOfMonth = `${today.substring(0, 8)}01`;

  const [dimension, setDimension] = useState(searchParams.get('dimension') || 'linea_negocio');
  const [dimensionId, setDimensionId] = useState(searchParams.get('dimension_id') || '');
  const [fechaDesde, setFechaDesde] = useState(searchParams.get('desde') || firstOfMonth);
  const [fechaHasta, setFechaHasta] = useState(searchParams.get('hasta') || today);
  const [options, setOptions] = useState([]);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);

  // Load dimension options when dimension type changes
  useEffect(() => {
    const loadOptions = async () => {
      try {
        let res;
        if (dimension === 'linea_negocio') {
          res = await getLineasNegocio();
          setOptions(res.data.map(o => ({ value: o.id, label: o.nombre })));
        } else if (dimension === 'marca') {
          res = await getMarcas();
          setOptions(res.data.map(o => ({ value: o.id, label: o.nombre })));
        } else if (dimension === 'centro_costo') {
          res = await getCentrosCosto();
          setOptions(res.data.map(o => ({ value: o.id, label: o.nombre })));
        } else if (dimension === 'categoria') {
          res = await getCategorias();
          setOptions(res.data.map(o => ({ value: o.id, label: o.nombre_completo || o.nombre })));
        }
      } catch (err) {
        console.error('Error loading options:', err);
        setOptions([]);
      }
    };
    loadOptions();
    setDimensionId('');
    setData(null);
  }, [dimension]);

  // Auto-select from URL params
  useEffect(() => {
    const urlDimId = searchParams.get('dimension_id');
    if (urlDimId && options.length > 0) {
      setDimensionId(urlDimId);
    }
  }, [options, searchParams]);

  const handleSearch = useCallback(async () => {
    if (!dimensionId) {
      toast.error('Selecciona un valor para buscar');
      return;
    }
    setLoading(true);
    try {
      const res = await api.get('/libro-analitico', {
        params: { dimension, dimension_id: dimensionId, fecha_desde: fechaDesde, fecha_hasta: fechaHasta },
      });
      setData(res.data);
      setSearchParams({ dimension, dimension_id: dimensionId, desde: fechaDesde, hasta: fechaHasta });
    } catch (err) {
      toast.error('Error al cargar el libro analítico');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [dimension, dimensionId, fechaDesde, fechaHasta, setSearchParams]);

  // Auto-search when dimensionId changes from URL
  useEffect(() => {
    if (dimensionId && options.length > 0 && searchParams.get('dimension_id')) {
      handleSearch();
    }
  }, [dimensionId, options.length]);

  const handleExport = async () => {
    if (!dimensionId) return;
    setExporting(true);
    try {
      const res = await api.get('/libro-analitico/export', {
        params: { dimension, dimension_id: dimensionId, fecha_desde: fechaDesde, fecha_hasta: fechaHasta },
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `libro_analitico_${fechaDesde}_${fechaHasta}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      toast.success('Archivo exportado');
    } catch (err) {
      toast.error('Error al exportar');
    } finally {
      setExporting(false);
    }
  };

  const navigateToRef = (refTipo, refId) => {
    const route = REF_ROUTES[refTipo];
    if (route) navigate(route);
  };

  return (
    <div className="page-container" data-testid="libro-analitico-page">
      <div className="page-header">
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <BookOpen size={28} />
            Libro Analitico
          </h1>
          <p className="page-subtitle">Historial de entradas y salidas por dimension</p>
        </div>
      </div>

      {/* Filters */}
      <div className="card" style={{ padding: '1.25rem', marginBottom: '1.5rem' }} data-testid="libro-filters">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', alignItems: 'end' }}>
          <div>
            <label className="form-label">Dimension</label>
            <select
              className="form-input"
              value={dimension}
              onChange={(e) => setDimension(e.target.value)}
              data-testid="dimension-select"
            >
              {DIMENSIONS.map(d => (
                <option key={d.value} value={d.value}>{d.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="form-label">Valor</label>
            <select
              className="form-input"
              value={dimensionId}
              onChange={(e) => setDimensionId(e.target.value)}
              data-testid="dimension-value-select"
            >
              <option value="">-- Seleccionar --</option>
              {options.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="form-label">Desde</label>
            <input
              type="date"
              className="form-input"
              value={fechaDesde}
              onChange={(e) => setFechaDesde(e.target.value)}
              data-testid="fecha-desde-input"
            />
          </div>

          <div>
            <label className="form-label">Hasta</label>
            <input
              type="date"
              className="form-input"
              value={fechaHasta}
              onChange={(e) => setFechaHasta(e.target.value)}
              data-testid="fecha-hasta-input"
            />
          </div>

          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              className="btn btn-primary"
              onClick={handleSearch}
              disabled={loading || !dimensionId}
              data-testid="buscar-btn"
              style={{ flex: 1 }}
            >
              <Search size={16} />
              {loading ? 'Buscando...' : 'Buscar'}
            </button>
            {data && data.movimientos.length > 0 && (
              <button
                className="btn btn-outline"
                onClick={handleExport}
                disabled={exporting}
                data-testid="exportar-csv-btn"
                title="Exportar CSV"
              >
                <Download size={16} />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      {data && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
          <div className="card" style={{ padding: '1.25rem', borderLeft: '4px solid var(--success)' }} data-testid="total-entradas-card">
            <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--muted)', fontWeight: 600, letterSpacing: '0.05em' }}>Total Entradas</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--success)', marginTop: '0.25rem' }}>
              {formatCurrency(data.total_entradas) || 'S/ 0.00'}
            </div>
          </div>
          <div className="card" style={{ padding: '1.25rem', borderLeft: '4px solid var(--danger)' }} data-testid="total-salidas-card">
            <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--muted)', fontWeight: 600, letterSpacing: '0.05em' }}>Total Salidas</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--danger)', marginTop: '0.25rem' }}>
              {formatCurrency(data.total_salidas) || 'S/ 0.00'}
            </div>
          </div>
          <div className="card" style={{ padding: '1.25rem', borderLeft: `4px solid ${data.saldo_final >= 0 ? 'var(--success)' : 'var(--danger)'}` }} data-testid="saldo-final-card">
            <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--muted)', fontWeight: 600, letterSpacing: '0.05em' }}>Saldo Final</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 700, color: data.saldo_final >= 0 ? 'var(--success)' : 'var(--danger)', marginTop: '0.25rem' }}>
              {formatCurrency(data.saldo_final) || 'S/ 0.00'}
            </div>
          </div>
        </div>
      )}

      {/* Movements Table */}
      {data && (
        <div className="card" data-testid="movimientos-table-container">
          <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>
              {data.dimension_nombre} - {data.movimientos.length} movimiento{data.movimientos.length !== 1 ? 's' : ''}
            </h3>
          </div>

          {data.movimientos.length === 0 ? (
            <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--muted)' }}>
              No hay movimientos en el periodo seleccionado
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table" data-testid="movimientos-table">
                <thead>
                  <tr>
                    <th style={{ width: '90px' }}>Fecha</th>
                    <th style={{ width: '130px' }}>Tipo</th>
                    <th>Descripcion</th>
                    <th style={{ width: '120px', textAlign: 'right' }}>Entrada</th>
                    <th style={{ width: '120px', textAlign: 'right' }}>Salida</th>
                    <th style={{ width: '130px', textAlign: 'right' }}>Saldo</th>
                    <th style={{ width: '50px' }}></th>
                  </tr>
                </thead>
                <tbody>
                  {data.movimientos.map((m, i) => (
                    <tr key={i} data-testid={`mov-row-${i}`}>
                      <td style={{ fontSize: '0.85rem', whiteSpace: 'nowrap' }}>{formatDate(m.fecha)}</td>
                      <td>
                        <span style={{
                          display: 'inline-flex', alignItems: 'center', gap: '4px',
                          fontSize: '0.8rem', fontWeight: 500,
                          color: m.entrada > 0 ? 'var(--success)' : 'var(--danger)',
                        }}>
                          {m.entrada > 0 ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
                          {m.tipo}
                        </span>
                      </td>
                      <td style={{ fontSize: '0.85rem' }}>
                        {m.descripcion}
                        {m.categoria && (
                          <span style={{ marginLeft: '0.5rem', fontSize: '0.75rem', color: 'var(--muted)', background: 'var(--bg)', padding: '2px 6px', borderRadius: '4px' }}>
                            {m.categoria}
                          </span>
                        )}
                      </td>
                      <td style={{ textAlign: 'right', color: 'var(--success)', fontWeight: m.entrada > 0 ? 600 : 400 }}>
                        {m.entrada > 0 ? formatCurrency(m.entrada) : ''}
                      </td>
                      <td style={{ textAlign: 'right', color: 'var(--danger)', fontWeight: m.salida > 0 ? 600 : 400 }}>
                        {m.salida > 0 ? formatCurrency(m.salida) : ''}
                      </td>
                      <td style={{ textAlign: 'right', fontWeight: 600, color: m.saldo >= 0 ? 'var(--success)' : 'var(--danger)' }}>
                        {formatCurrency(m.saldo)}
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        {m.ref_tipo && (
                          <button
                            className="btn-icon"
                            title="Abrir documento"
                            onClick={() => navigateToRef(m.ref_tipo, m.ref_id)}
                            data-testid={`open-ref-${i}`}
                            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--primary)', padding: '4px' }}
                          >
                            <ExternalLink size={15} />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr style={{ fontWeight: 700, borderTop: '2px solid var(--border)' }}>
                    <td colSpan={3} style={{ textAlign: 'right' }}>TOTALES</td>
                    <td style={{ textAlign: 'right', color: 'var(--success)' }}>{formatCurrency(data.total_entradas)}</td>
                    <td style={{ textAlign: 'right', color: 'var(--danger)' }}>{formatCurrency(data.total_salidas)}</td>
                    <td style={{ textAlign: 'right', color: data.saldo_final >= 0 ? 'var(--success)' : 'var(--danger)' }}>{formatCurrency(data.saldo_final)}</td>
                    <td></td>
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {!data && !loading && (
        <div className="card" style={{ padding: '4rem 2rem', textAlign: 'center' }}>
          <BookOpen size={48} style={{ color: 'var(--muted)', marginBottom: '1rem' }} />
          <h3 style={{ color: 'var(--muted)', marginBottom: '0.5rem' }}>Selecciona una dimension y busca</h3>
          <p style={{ color: 'var(--muted)', fontSize: '0.9rem' }}>
            Elige una linea de negocio, marca o centro de costo para ver su historial completo de entradas y salidas
          </p>
        </div>
      )}
    </div>
  );
}
