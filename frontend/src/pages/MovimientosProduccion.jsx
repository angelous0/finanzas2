import React, { useState, useEffect, useMemo } from 'react';
import { toast } from 'sonner';
import { useEmpresa } from '../context/EmpresaContext';
import { getMovimientosProduccion } from '../services/api';
import {
  Factory, ArrowDownCircle, ArrowUpCircle, Package,
  RefreshCw, Download, Filter, Search,
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
};

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

export default function MovimientosProduccion() {
  const { empresaActual } = useEmpresa();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filtroTipo, setFiltroTipo] = useState('');
  const [busqueda, setBusqueda] = useState('');
  const [fechaDesde, setFechaDesde] = useState('');
  const [fechaHasta, setFechaHasta] = useState('');

  const fetchData = async () => {
    setLoading(true);
    try {
      const params = {};
      if (filtroTipo) params.tipo = filtroTipo;
      if (fechaDesde) params.fecha_desde = fechaDesde;
      if (fechaHasta) params.fecha_hasta = fechaHasta;
      const res = await getMovimientosProduccion(params);
      setData(res.data);
    } catch {
      toast.error('Error al cargar movimientos de producción');
    }
    setLoading(false);
  };

  useEffect(() => { if (empresaActual) fetchData(); }, [empresaActual]);

  const filtered = useMemo(() => {
    if (!data?.items) return [];
    if (!busqueda.trim()) return data.items;
    const q = busqueda.toLowerCase();
    return data.items.filter(i =>
      (i.descripcion || '').toLowerCase().includes(q) ||
      (i.detalle || '').toLowerCase().includes(q)
    );
  }, [data, busqueda]);

  const resumen = data?.resumen || {};

  const handleExportExcel = async () => {
    if (!filtered.length) return;
    const XLSX = (await import('xlsx')).default || await import('xlsx');
    const wsData = [
      ['Fecha', 'Tipo', 'Impacto', 'Descripción', 'Detalle', 'Cantidad', 'Monto', 'Estado'],
      ...filtered.map(r => [
        r.fecha || '',
        r.tipo_label,
        r.impacto,
        r.descripcion,
        r.detalle,
        r.cantidad,
        r.monto,
        r.estado,
      ]),
    ];
    const ws = XLSX.utils.aoa_to_sheet(wsData);
    ws['!cols'] = [{ wch: 12 }, { wch: 18 }, { wch: 10 }, { wch: 35 }, { wch: 25 }, { wch: 10 }, { wch: 14 }, { wch: 12 }];
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Mov.Producción');
    XLSX.writeFile(wb, `movimientos_produccion_${new Date().toISOString().slice(0, 10)}.xlsx`);
    toast.success('Excel exportado');
  };

  const FILTROS = [
    { key: '', label: 'Todos' },
    { key: 'servicio', label: 'Servicios' },
    { key: 'ingreso_mp', label: 'Ingresos MP' },
    { key: 'entrega_pt', label: 'Entregas PT' },
  ];

  return (
    <div className="space-y-4" data-testid="movimientos-produccion-page">
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

      {/* KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.75rem' }}>
        <KpiCard
          label="Servicios Externos"
          count={resumen.total_servicios || 0}
          monto={resumen.monto_servicios || 0}
          icon={ArrowDownCircle}
          color="#fee2e2"
        />
        <KpiCard
          label="Ingresos de MP"
          count={resumen.total_ingresos_mp || 0}
          monto={resumen.monto_ingresos_mp || 0}
          icon={Package}
          color="#fef3c7"
        />
        <KpiCard
          label="Entregas de PT"
          count={resumen.total_entregas_pt || 0}
          monto={resumen.monto_entregas_pt || 0}
          icon={ArrowUpCircle}
          color="#d1fae5"
        />
      </div>

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
              padding: '0.375rem 0.75rem',
              borderRadius: '0.375rem',
              fontSize: '0.75rem',
              fontWeight: 500,
              border: '1px solid',
              borderColor: filtroTipo === f.key ? 'var(--primary)' : 'var(--border)',
              background: filtroTipo === f.key ? 'var(--primary)' : 'var(--card)',
              color: filtroTipo === f.key ? '#fff' : 'var(--text)',
              cursor: 'pointer',
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
                <th>Tipo</th>
                <th>Impacto</th>
                <th>Descripción</th>
                <th>Detalle / Proveedor</th>
                <th className="text-right">Cantidad</th>
                <th className="text-right">Monto</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item, idx) => {
                const cfg = TIPO_CONFIG[item.tipo] || TIPO_CONFIG.servicio;
                const Icon = cfg.icon;
                return (
                  <tr key={`${item.tipo}-${item.referencia_id}-${idx}`}>
                    <td style={{ whiteSpace: 'nowrap', fontSize: '0.75rem' }}>{formatDate(item.fecha)}</td>
                    <td>
                      <span style={{
                        display: 'inline-flex', alignItems: 'center', gap: '0.25rem',
                        padding: '2px 8px', borderRadius: '999px', fontSize: '0.6875rem', fontWeight: 600,
                      }} className={cfg.cls}>
                        <Icon size={12} /> {item.tipo_label}
                      </span>
                    </td>
                    <td>
                      <span style={{
                        fontSize: '0.6875rem', fontWeight: 600,
                        color: item.impacto === 'egreso' ? '#dc2626' : item.impacto === 'ingreso' ? '#16a34a' : '#d97706',
                      }}>
                        {item.impacto === 'egreso' ? '- ' : item.impacto === 'ingreso' ? '+ ' : ''}{item.impacto?.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ maxWidth: '250px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {item.descripcion}
                    </td>
                    <td style={{ color: 'var(--muted)', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {item.detalle}
                    </td>
                    <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {Number(item.cantidad || 0).toLocaleString()}
                    </td>
                    <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>
                      {formatCurrency(item.monto)}
                    </td>
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
