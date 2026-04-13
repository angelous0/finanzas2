import React, { useState, useEffect } from 'react';
import { getConciliacionesDetalladas, desconciliarMovimientos } from '../services/api';
import { useEmpresa } from '../context/EmpresaContext';
import { History, Trash2, Search, Download, RefreshCw, Calendar } from 'lucide-react';
import { toast } from 'sonner';

const formatCurrency = (value, symbol = 'S/') => {
  return `${symbol} ${Number(value || 0).toLocaleString('es-PE', { minimumFractionDigits: 2 })}`;
};

const formatDate = (dateStr) => {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleDateString('es-PE');
};

export const HistorialConciliaciones = () => {
  const { empresaActual } = useEmpresa();

  const [conciliaciones, setConciliaciones] = useState([]);
  const [conciliacionesFiltradas, setConciliacionesFiltradas] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [fechaDesde, setFechaDesde] = useState('');
  const [fechaHasta, setFechaHasta] = useState('');

  useEffect(() => {
    loadConciliaciones();
  }, [empresaActual]);

  useEffect(() => {
    filtrarConciliaciones();
  }, [conciliaciones, searchTerm, fechaDesde, fechaHasta]);

  const loadConciliaciones = async () => {
    try {
      setLoading(true);
      const response = await getConciliacionesDetalladas();
      setConciliaciones(response.data || []);
    } catch (error) {
      console.error('Error loading conciliaciones:', error);
      toast.error('Error al cargar historial de conciliaciones');
    } finally {
      setLoading(false);
    }
  };

  const filtrarConciliaciones = () => {
    let filtered = [...conciliaciones];

    // Filter by search term
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      filtered = filtered.filter(c =>
        (c.descripcion_banco || '').toLowerCase().includes(term) ||
        (c.descripcion_sistema || '').toLowerCase().includes(term) ||
        (c.ref_banco || '').toLowerCase().includes(term) ||
        (c.numero_sistema || '').toLowerCase().includes(term)
      );
    }

    // Filter by date range
    if (fechaDesde) {
      filtered = filtered.filter(c => {
        const fecha = c.fecha_banco || c.fecha_sistema;
        return fecha >= fechaDesde;
      });
    }
    if (fechaHasta) {
      filtered = filtered.filter(c => {
        const fecha = c.fecha_banco || c.fecha_sistema;
        return fecha <= fechaHasta;
      });
    }

    setConciliacionesFiltradas(filtered);
  };

  const handleDesconciliar = async (bancoId, pagoId) => {
    if (!window.confirm('¿Está seguro de desconciliar estos movimientos?')) {
      return;
    }

    try {
      await desconciliarMovimientos(bancoId, pagoId);
      toast.success('Movimientos desconciliados exitosamente');
      loadConciliaciones();
    } catch (error) {
      console.error('Error al desconciliar:', error);
      toast.error('Error al desconciliar movimientos');
    }
  };

  const totalMontoBanco = conciliacionesFiltradas.reduce((sum, c) => sum + (c.monto || 0), 0);
  const totalMontoSistema = conciliacionesFiltradas.reduce((sum, c) => sum + (c.monto_sistema || 0), 0);
  const diferencia = totalMontoBanco - totalMontoSistema;

  const exportToExcel = () => {
    toast.info('Función de exportar a Excel en desarrollo');
  };

  const exportToPDF = () => {
    toast.info('Función de exportar a PDF en desarrollo');
  };

  return (
    <div className="page">
      {/* Page Header */}
      <div className="page-header" style={{ marginBottom: '1.5rem' }}>
        <div>
          <h1 className="page-title">
            <History size={28} style={{ display: 'inline', marginRight: '0.5rem', verticalAlign: 'middle' }} />
            Historial Conciliación
          </h1>
          <p className="page-subtitle">Vista general de todas las conciliaciones realizadas</p>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto auto auto auto auto', gap: '1rem', alignItems: 'end' }}>
          {/* Search */}
          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.875rem', fontWeight: 500 }}>
              Buscar
            </label>
            <div style={{ position: 'relative' }}>
              <Search size={18} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--muted)' }} />
              <input
                type="text"
                className="form-input"
                placeholder="Descripción, proveedor, nro doc..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{ paddingLeft: '2.5rem' }}
              />
            </div>
          </div>

          {/* Date From */}
          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.875rem', fontWeight: 500 }}>
              Desde
            </label>
            <input
              type="date"
              className="form-input"
              value={fechaDesde}
              onChange={(e) => setFechaDesde(e.target.value)}
            />
          </div>

          {/* Date To */}
          <div>
            <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.875rem', fontWeight: 500 }}>
              Hasta
            </label>
            <input
              type="date"
              className="form-input"
              value={fechaHasta}
              onChange={(e) => setFechaHasta(e.target.value)}
            />
          </div>

          {/* Export Excel */}
          <button className="btn btn-outline" onClick={exportToExcel} style={{ height: 'fit-content' }}>
            <Download size={16} /> Excel
          </button>

          {/* Export PDF */}
          <button className="btn btn-outline" onClick={exportToPDF} style={{ height: 'fit-content' }}>
            <Download size={16} /> PDF
          </button>

          {/* Refresh */}
          <button className="btn btn-outline" onClick={loadConciliaciones} style={{ height: 'fit-content' }}>
            <RefreshCw size={16} /> Actualizar
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(4, 1fr)', 
        gap: '1rem',
        marginBottom: '1.5rem'
      }}>
        <div className="summary-card" style={{ 
          background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
          color: 'white'
        }}>
          <div style={{ fontSize: '0.875rem', opacity: 0.9, marginBottom: '0.5rem' }}>
            Total Conciliaciones
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 700 }}>{conciliacionesFiltradas.length}</div>
        </div>

        <div className="summary-card" style={{ 
          background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
          color: 'white'
        }}>
          <div style={{ fontSize: '0.875rem', opacity: 0.9, marginBottom: '0.5rem' }}>
            Total Monto Banco
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 700 }}>{formatCurrency(totalMontoBanco)}</div>
        </div>

        <div className="summary-card" style={{ 
          background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
          color: 'white'
        }}>
          <div style={{ fontSize: '0.875rem', opacity: 0.9, marginBottom: '0.5rem' }}>
            Total Monto Sistema
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 700 }}>{formatCurrency(totalMontoSistema)}</div>
        </div>

        <div className="summary-card" style={{ 
          background: 'linear-gradient(135deg, #a855f7 0%, #9333ea 100%)',
          color: 'white'
        }}>
          <div style={{ fontSize: '0.875rem', opacity: 0.9, marginBottom: '0.5rem' }}>
            Diferencia
          </div>
          <div style={{ fontSize: '2rem', fontWeight: 700 }}>{formatCurrency(diferencia)}</div>
        </div>
      </div>

      {/* Conciliaciones Table */}
      <div className="card">
        <div style={{ marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0, fontSize: '1.125rem', fontWeight: 600 }}>Detalle de Conciliaciones</h3>
          <span style={{ fontSize: '0.8125rem', color: 'var(--muted)' }}>
            Click en columna para ordenar • Arrastre borde para redimensionar
          </span>
        </div>

        <div className="data-table-wrapper">
          {loading ? (
            <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--muted)' }}>
              <RefreshCw size={40} className="spin" style={{ marginBottom: '1rem', opacity: 0.5 }} />
              <div>Cargando...</div>
            </div>
          ) : conciliacionesFiltradas.length === 0 ? (
            <div className="empty-state">
              <History className="empty-state-icon" />
              <div className="empty-state-title">No hay conciliaciones que mostrar</div>
              <div className="empty-state-description">
                {conciliaciones.length === 0 
                  ? 'Las conciliaciones aparecerán aquí una vez que vincule movimientos'
                  : 'No se encontraron conciliaciones con los filtros aplicados'}
              </div>
            </div>
          ) : (
            <table className="data-table" style={{ fontSize: '0.8125rem' }}>
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th style={{ background: 'var(--info-bg)', color: 'var(--info-text)' }}>Banco</th>
                  <th style={{ background: 'var(--info-bg)', color: 'var(--info-text)' }}>Nro Operación</th>
                  <th style={{ background: 'var(--info-bg)', color: 'var(--info-text)' }}>Descripción Banco</th>
                  <th style={{ background: 'var(--info-bg)', color: 'var(--info-text)' }}>Monto Banco</th>
                  <th style={{ background: 'var(--success-bg)', color: 'var(--success-text)' }}>Nro Doc Sistema</th>
                  <th style={{ background: 'var(--success-bg)', color: 'var(--success-text)' }}>Tipo</th>
                  <th style={{ background: 'var(--success-bg)', color: 'var(--success-text)' }}>Descripción Sistema</th>
                  <th className="text-right" style={{ background: 'var(--success-bg)', color: 'var(--success-text)' }}>Monto Sistema</th>
                  <th className="text-center">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {conciliacionesFiltradas.map((conc, idx) => (
                  <tr key={idx}>
                    <td>{formatDate(conc.fecha_banco || conc.fecha_sistema)}</td>
                    <td style={{ background: '#f8faff' }}>{conc.banco}</td>
                    <td style={{ background: '#f8faff', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.75rem' }}>
                      {conc.ref_banco || '-'}
                    </td>
                    <td style={{ background: '#f8faff', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {conc.descripcion_banco || '-'}
                    </td>
                    <td className="text-right currency-display" style={{ 
                      background: '#f8faff',
                      color: conc.monto < 0 ? '#dc2626' : '#16a34a',
                      fontWeight: 500
                    }}>
                      {formatCurrency(conc.monto, conc.monto < 0 ? '-S/' : 'S/')}
                    </td>
                    <td style={{ background: '#f7fef9', fontFamily: "'JetBrains Mono', monospace", fontSize: '0.75rem' }}>
                      {conc.numero_sistema || '-'}
                    </td>
                    <td style={{ background: '#f7fef9' }}>
                      <span className={`badge ${conc.tipo_sistema === 'ingreso' ? 'badge-success' : 'badge-danger'}`} style={{ fontSize: '0.6875rem' }}>
                        {conc.tipo_sistema === 'ingreso' ? 'INGRESO' : 'EGRESO'}
                      </span>
                    </td>
                    <td style={{ background: '#f7fef9', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {conc.descripcion_sistema || '-'}
                    </td>
                    <td className="text-right currency-display" style={{ 
                      background: '#f7fef9',
                      fontWeight: 500,
                      color: conc.tipo_sistema === 'ingreso' ? '#16a34a' : '#dc2626'
                    }}>
                      {conc.tipo_sistema === 'ingreso' ? '' : '-'}{formatCurrency(Math.abs(conc.monto))}
                    </td>
                    <td className="text-center">
                      <button
                        className="btn btn-sm btn-danger"
                        onClick={() => handleDesconciliar(conc.banco_id, conc.sistema_id)}
                        style={{ 
                          padding: '0.375rem 0.75rem',
                          fontSize: '0.75rem',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.375rem'
                        }}
                      >
                        <Trash2 size={14} />
                        Desconciliar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};
