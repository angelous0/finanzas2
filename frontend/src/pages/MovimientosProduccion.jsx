import React, { useState, useEffect, useMemo } from 'react';
import { toast } from 'sonner';
import { useEmpresa } from '../context/EmpresaContext';
import { getMovimientosProduccion, getMovimientosProduccionFinanzas } from '../services/api';
import {
  Factory, ArrowDownCircle, ArrowUpCircle, Package,
  RefreshCw, Download, Filter, Search, FileText,
} from 'lucide-react';

const formatCurrency = (val) => {
  const n = Number(val) || 0;
  return `S/ ${n.toLocaleString('es-PE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const formatDate = (d) => {
  if (!d) return '-';
  return new Date(d).toLocaleDateString('es-PE');
};

const TIPO_CONFIG = {
  servicio:    { icon: ArrowDownCircle, label: 'Servicio Externo', impacto: 'Egreso',  cls: 'bg-red-100 text-red-700',    dotCls: 'bg-red-500' },
  ingreso_mp:  { icon: Package,         label: 'Ingreso MP',       impacto: 'Costo',   cls: 'bg-amber-100 text-amber-700', dotCls: 'bg-amber-500' },
  entrega_pt:  { icon: ArrowUpCircle,   label: 'Entrega PT',       impacto: 'Ingreso', cls: 'bg-emerald-100 text-emerald-700', dotCls: 'bg-emerald-500' },
  movimiento:  { icon: ArrowDownCircle, label: 'Mov. Producción',  impacto: 'Egreso',  cls: 'bg-red-100 text-red-700',    dotCls: 'bg-red-500' },
};

const FacturaBadge = ({ facturado, numero }) => (
  <span style={{
    padding: '2px 8px', borderRadius: '999px', fontSize: '0.65rem', fontWeight: 700,
    background: facturado ? '#d1fae5' : '#fee2e2',
    color: facturado ? '#065f46' : '#991b1b',
    whiteSpace: 'nowrap',
  }}>
    {facturado ? `✓ ${numero}` : 'SIN FACTURA'}
  </span>
);

const KpiCard = ({ label, count, monto, icon: Icon, color }) => (
  <div className="card" style={{ padding: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
    <div style={{
      width: 40, height: 40, borderRadius: '0.5rem', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: color || 'var(--card-bg-alt)',
    }}>
      <Icon size={18} />
    </div>
    <div>
      <p style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--muted)', fontWeight: 500 }}>{label}</p>
      <p style={{ fontSize: '1.25rem', fontWeight: 700 }}>{count}</p>
      <p style={{ fontSize: '0.7rem', color: 'var(--muted)', fontFamily: "'JetBrains Mono', monospace" }}>{formatCurrency(monto)}</p>
    </div>
  </div>
);

const DetallePanel = ({ item, onClose }) => {
  if (!item) return null;
  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 1000,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }} onClick={onClose}>
      <div className="card" style={{ width: 440, padding: '1.5rem', position: 'relative' }} onClick={e => e.stopPropagation()}>
        <button onClick={onClose} style={{ position: 'absolute', top: '1rem', right: '1rem', background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.25rem', color: 'var(--muted)' }}>✕</button>
        <h3 style={{ fontWeight: 700, marginBottom: '1rem', fontSize: '1rem' }}>Detalle del movimiento</h3>
        <table style={{ width: '100%', fontSize: '0.8125rem', borderCollapse: 'collapse' }}>
          <tbody>
            {[
              ['Descripción', item.descripcion],
              ['Proveedor / Persona', item.detalle || item.persona_nombre],
              ['Servicio', item.servicio_nombre || item.tipo_label],
              ['Corte / Registro', item.registro_n_corte ? `#${item.registro_n_corte}` : null],
              ['Fecha', formatDate(item.fecha || item.fecha_inicio)],
              ['Cantidad', item.cantidad != null ? Number(item.cantidad).toLocaleString() : null],
              ['Monto', formatCurrency(item.monto)],
              ['Estado', item.estado],
            ].filter(([, v]) => v != null && v !== '').map(([label, val]) => (
              <tr key={label} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: '0.4rem 0', color: 'var(--muted)', width: '140px' }}>{label}</td>
                <td style={{ padding: '0.4rem 0', fontWeight: 500 }}>{val}</td>
              </tr>
            ))}
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              <td style={{ padding: '0.4rem 0', color: 'var(--muted)' }}>Factura</td>
              <td style={{ padding: '0.4rem 0' }}>
                {item.facturado != null
                  ? <FacturaBadge facturado={item.facturado} numero={item.factura_numero} />
                  : <span style={{ color: 'var(--muted)', fontSize: '0.75rem' }}>—</span>}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default function MovimientosProduccion() {
  const { empresaActual } = useEmpresa();
  const [data, setData] = useState(null);
  const [dataMovimientos, setDataMovimientos] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filtroTipo, setFiltroTipo] = useState('');
  const [busqueda, setBusqueda] = useState('');
  const [fechaDesde, setFechaDesde] = useState('');
  const [fechaHasta, setFechaHasta] = useState('');
  const [itemDetalle, setItemDetalle] = useState(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const params = {};
      if (filtroTipo && filtroTipo !== 'movimiento') params.tipo = filtroTipo;
      if (fechaDesde) params.fecha_desde = fechaDesde;
      if (fechaHasta) params.fecha_hasta = fechaHasta;

      if (filtroTipo === 'movimiento') {
        // Servicios (movimientos individuales) desde produccion backend via Finanzas
        const res = await getMovimientosProduccionFinanzas(params);
        setDataMovimientos(res.data);
        setData(null);
      } else {
        const res = await getMovimientosProduccion(params);
        setData(res.data);
        setDataMovimientos(null);
      }
    } catch {
      toast.error('Error al cargar movimientos de producción');
    }
    setLoading(false);
  };

  useEffect(() => { if (empresaActual) fetchData(); }, [empresaActual]);

  const filtered = useMemo(() => {
    const source = filtroTipo === 'movimiento' ? (dataMovimientos?.items || []) : (data?.items || []);
    if (!busqueda.trim()) return source;
    const q = busqueda.toLowerCase();
    return source.filter(i =>
      (i.descripcion || '').toLowerCase().includes(q) ||
      (i.detalle || '').toLowerCase().includes(q) ||
      (i.persona_nombre || '').toLowerCase().includes(q)
    );
  }, [data, dataMovimientos, busqueda, filtroTipo]);

  const resumen = data?.resumen || {};

  const handleExportExcel = async () => {
    if (!filtered.length) return;
    const XLSX = (await import('xlsx')).default || await import('xlsx');
    const wsData = [
      ['Fecha', 'Tipo', 'Descripción', 'Detalle', 'Cantidad', 'Monto', 'Factura'],
      ...filtered.map(r => [
        r.fecha || r.fecha_inicio || '',
        r.tipo_label || r.servicio_nombre || '',
        r.descripcion,
        r.detalle || r.persona_nombre || '',
        r.cantidad,
        r.monto,
        r.factura_numero || (r.facturado === false ? 'SIN FACTURA' : r.estado || ''),
      ]),
    ];
    const ws = XLSX.utils.aoa_to_sheet(wsData);
    ws['!cols'] = [{ wch: 12 }, { wch: 18 }, { wch: 35 }, { wch: 25 }, { wch: 10 }, { wch: 14 }, { wch: 20 }];
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Mov.Producción');
    XLSX.writeFile(wb, `movimientos_produccion_${new Date().toISOString().slice(0, 10)}.xlsx`);
    toast.success('Excel exportado');
  };

  const FILTROS = [
    { key: '', label: 'Todos' },
    { key: 'servicio', label: 'Servicios (órdenes)' },
    { key: 'movimiento', label: 'Servicios (movimientos)' },
    { key: 'ingreso_mp', label: 'Ingresos MP' },
    { key: 'entrega_pt', label: 'Entregas PT' },
  ];

  const showFacturaCol = filtroTipo === 'movimiento';

  return (
    <div className="space-y-4" data-testid="movimientos-produccion-page">
      {itemDetalle && <DetallePanel item={itemDetalle} onClose={() => setItemDetalle(null)} />}

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Factory size={20} style={{ color: 'var(--primary)' }} /> Movimientos desde Producción
          </h2>
          <p style={{ fontSize: '0.8125rem', color: 'var(--muted)' }}>
            Eventos productivos con impacto financiero
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-outline btn-sm" onClick={handleExportExcel} disabled={!filtered.length}>
            <Download size={14} /> Excel
          </button>
          <button className="btn btn-outline btn-sm" onClick={fetchData} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Actualizar
          </button>
        </div>
      </div>

      {/* KPIs — solo cuando no estamos en movimientos */}
      {!showFacturaCol && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.75rem' }}>
          <KpiCard label="Servicios Externos" count={resumen.total_servicios || 0} monto={resumen.monto_servicios || 0} icon={ArrowDownCircle} color="#fee2e2" />
          <KpiCard label="Ingresos de MP" count={resumen.total_ingresos_mp || 0} monto={resumen.monto_ingresos_mp || 0} icon={Package} color="#fef3c7" />
          <KpiCard label="Entregas de PT" count={resumen.total_entregas_pt || 0} monto={resumen.monto_entregas_pt || 0} icon={ArrowUpCircle} color="#d1fae5" />
        </div>
      )}

      {/* Filtros */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: '1', maxWidth: '280px' }}>
          <Search size={14} style={{ position: 'absolute', left: '0.625rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--muted)' }} />
          <input
            className="form-input"
            placeholder="Buscar descripción, proveedor..."
            value={busqueda}
            onChange={e => setBusqueda(e.target.value)}
            style={{ paddingLeft: '2rem', height: '2rem', fontSize: '0.75rem' }}
          />
        </div>
        <input type="date" className="form-input" value={fechaDesde} onChange={e => setFechaDesde(e.target.value)} style={{ height: '2rem', width: '140px', fontSize: '0.75rem' }} />
        <span style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>a</span>
        <input type="date" className="form-input" value={fechaHasta} onChange={e => setFechaHasta(e.target.value)} style={{ height: '2rem', width: '140px', fontSize: '0.75rem' }} />
        <button className="btn btn-primary btn-sm" onClick={fetchData} disabled={loading} style={{ height: '2rem', fontSize: '0.75rem' }}>
          Aplicar
        </button>
        {(fechaDesde || fechaHasta || filtroTipo) && (
          <button className="btn btn-outline btn-sm" onClick={() => { setFechaDesde(''); setFechaHasta(''); setFiltroTipo(''); setTimeout(fetchData, 0); }} style={{ height: '2rem', fontSize: '0.75rem' }}>
            Limpiar
          </button>
        )}
      </div>

      {/* Tipo filter pills */}
      <div style={{ display: 'flex', gap: '0.375rem', flexWrap: 'wrap' }}>
        {FILTROS.map(f => (
          <button
            key={f.key}
            onClick={() => { setFiltroTipo(f.key); setTimeout(fetchData, 0); }}
            style={{
              padding: '0.375rem 0.75rem', borderRadius: '0.375rem', fontSize: '0.75rem', fontWeight: 500, border: '1px solid',
              borderColor: filtroTipo === f.key ? 'var(--primary)' : 'var(--border)',
              background: filtroTipo === f.key ? 'var(--primary)' : 'var(--card)',
              color: filtroTipo === f.key ? '#fff' : 'var(--text)', cursor: 'pointer',
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Table */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--muted)' }}>Cargando...</div>
      ) : filtered.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '3rem', color: 'var(--muted)' }}>
          <Factory size={32} style={{ margin: '0 auto 0.75rem', opacity: 0.3 }} />
          <p style={{ fontSize: '0.875rem' }}>Sin movimientos de producción</p>
        </div>
      ) : (
        <div className="card" style={{ overflow: 'auto' }}>
          <table className="data-table" style={{ fontSize: '0.8125rem' }}>
            <thead>
              <tr>
                <th style={{ width: '85px' }}>Fecha</th>
                <th>Tipo / Servicio</th>
                {!showFacturaCol && <th>Impacto</th>}
                <th>Descripción</th>
                <th>Detalle / Proveedor</th>
                <th className="text-right">Cantidad</th>
                <th className="text-right">Monto</th>
                {showFacturaCol
                  ? <th style={{ width: '160px' }}>Factura</th>
                  : <th>Estado</th>
                }
              </tr>
            </thead>
            <tbody>
              {filtered.map((item, idx) => {
                const cfg = TIPO_CONFIG[item.tipo] || TIPO_CONFIG.servicio;
                const Icon = cfg.icon;
                return (
                  <tr
                    key={`${item.tipo || 'mov'}-${item.referencia_id || item.id}-${idx}`}
                    onClick={() => setItemDetalle(item)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td style={{ whiteSpace: 'nowrap', fontSize: '0.75rem' }}>{formatDate(item.fecha || item.fecha_inicio)}</td>
                    <td>
                      <span style={{
                        display: 'inline-flex', alignItems: 'center', gap: '0.25rem',
                        padding: '2px 8px', borderRadius: '999px', fontSize: '0.6875rem', fontWeight: 600,
                      }} className={cfg.cls}>
                        <Icon size={12} /> {item.tipo_label || item.servicio_nombre}
                      </span>
                    </td>
                    {!showFacturaCol && (
                      <td>
                        <span style={{
                          fontSize: '0.6875rem', fontWeight: 600,
                          color: item.impacto === 'egreso' ? '#dc2626' : item.impacto === 'ingreso' ? '#16a34a' : '#d97706',
                        }}>
                          {item.impacto === 'egreso' ? '- ' : item.impacto === 'ingreso' ? '+ ' : ''}{item.impacto?.toUpperCase()}
                        </span>
                      </td>
                    )}
                    <td style={{ maxWidth: '250px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {item.descripcion}
                    </td>
                    <td style={{ color: 'var(--muted)', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {item.detalle || item.persona_nombre}
                    </td>
                    <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {Number(item.cantidad || 0).toLocaleString()}
                    </td>
                    <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>
                      {formatCurrency(item.monto)}
                    </td>
                    {showFacturaCol ? (
                      <td>
                        <FacturaBadge facturado={item.facturado} numero={item.factura_numero} />
                      </td>
                    ) : (
                      <td>
                        <span style={{
                          padding: '1px 6px', borderRadius: '4px', fontSize: '0.65rem', fontWeight: 600,
                          background: item.estado === 'COMPLETADO' || item.estado === 'CERRADO' || item.estado === 'ENTREGADO' ? '#d1fae5' :
                                      item.estado === 'PENDIENTE' ? '#fef3c7' : 'var(--card-bg-alt)',
                          color: item.estado === 'COMPLETADO' || item.estado === 'CERRADO' || item.estado === 'ENTREGADO' ? '#065f46' :
                                 item.estado === 'PENDIENTE' ? '#92400e' : 'var(--muted)',
                        }}>
                          {item.estado}
                        </span>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
