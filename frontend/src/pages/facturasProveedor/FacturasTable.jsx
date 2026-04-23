import React from 'react';
import { formatCurrency, formatDate, estadoBadge } from './helpers';
import { Plus, Trash2, Search, X, FileText, Edit2, Eye, DollarSign, FileSpreadsheet, History, Download, Link2, MoreVertical, CheckCircle2, RotateCcw, Factory } from 'lucide-react';
import { toast } from 'sonner';
import SearchableSelect from '../../components/SearchableSelect';
import { procesarNotaInterna, anularProcesamientoNotaInterna } from '../../services/api';

const FacturasTable = ({
  facturas, loading, proveedores,
  filtroNumero, setFiltroNumero, filtroProveedorId, setFiltroProveedorId,
  filtroFecha, setFiltroFecha, filtroEstado, setFiltroEstado,
  onOpenPago, onOpenLetras, onVerPagos, onVerLetras, onView, onEdit, onDelete, onDownloadPDF,
  onNewFactura, onVincularIngresos, onRefresh,
}) => {
  const [openMenu, setOpenMenu] = React.useState(null);

  const facturasFiltradas = filtroNumero
    ? facturas.filter(f => f.numero?.toLowerCase().includes(filtroNumero.toLowerCase()))
    : facturas;

  const totalPendiente = facturasFiltradas.filter(f => f.estado === 'pendiente' || f.estado === 'parcial')
    .reduce((sum, f) => sum + parseFloat(f.saldo_pendiente || 0), 0);

  const clearFilters = () => { setFiltroNumero(''); setFiltroProveedorId(''); setFiltroFecha(''); setFiltroEstado(''); };
  const hasFilters = filtroNumero || filtroProveedorId || filtroFecha || filtroEstado;

  // Close menu on outside click
  React.useEffect(() => {
    if (openMenu === null) return;
    const handler = () => setOpenMenu(null);
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [openMenu]);

  return (
    <>
      {/* Filtros */}
      <div className="filters-bar">
        <div className="filter-group">
          <label className="filter-label">N. Doc</label>
          <input type="text" className="form-input" placeholder="Buscar..." value={filtroNumero} onChange={(e) => setFiltroNumero(e.target.value)} data-testid="filtro-numero" style={{ width: '140px' }} />
        </div>
        <div className="filter-group">
          <label className="filter-label">Proveedor</label>
          <SearchableSelect
            options={[{ id: '', nombre: 'Todos' }, ...proveedores]}
            value={filtroProveedorId}
            onChange={(value) => setFiltroProveedorId(value || '')}
            placeholder="Todos"
            searchPlaceholder="Buscar proveedor..."
            displayKey="nombre"
            valueKey="id"
            data-testid="filtro-proveedor"
            style={{ width: '200px' }}
          />
        </div>
        <div className="filter-group">
          <label className="filter-label">Fecha emision</label>
          <input type="date" className="form-input" value={filtroFecha} onChange={(e) => setFiltroFecha(e.target.value)} data-testid="filtro-fecha" style={{ width: '150px' }} />
        </div>
        <div className="filter-group">
          <label className="filter-label">Estado</label>
          <select className="form-input form-select" value={filtroEstado} onChange={(e) => setFiltroEstado(e.target.value)} data-testid="filtro-estado" style={{ width: '140px' }}>
            <option value="">Todos</option>
            <option value="pendiente">Pendiente</option>
            <option value="parcial">Parcial</option>
            <option value="pagado">Pagado</option>
            <option value="canjeado">Canjeado</option>
            <option value="anulada">Anulada</option>
          </select>
        </div>
        {hasFilters && (
          <button className="btn btn-ghost btn-sm" onClick={clearFilters} title="Limpiar filtros"><X size={16} /></button>
        )}
      </div>

      {/* Tabla */}
      <div className="card">
        <div className="data-table-wrapper">
          {loading ? (
            <div className="loading"><div className="loading-spinner"></div></div>
          ) : facturasFiltradas.length === 0 ? (
            <div className="empty-state">
              <FileText className="empty-state-icon" />
              <div className="empty-state-title">{facturas.length === 0 ? 'No hay facturas registradas' : 'No se encontraron facturas con los filtros aplicados'}</div>
              <div className="empty-state-description">{facturas.length === 0 ? 'Crea tu primera factura de proveedor' : 'Intenta cambiar los criterios de busqueda'}</div>
              {facturas.length === 0 && (
                <button className="btn btn-primary" onClick={onNewFactura}><Plus size={18} /> Crear primera factura</button>
              )}
            </div>
          ) : (
            <table className="data-table" data-testid="facturas-table">
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Nro. Doc</th>
                  <th>Proveedor / Beneficiario</th>
                  <th className="text-right">Total</th>
                  <th className="text-right">Pagado</th>
                  <th>Estado</th>
                  <th className="text-center">Ingresos</th>
                  <th className="text-right">Saldo CxP</th>
                  <th className="text-center" style={{ minWidth: '120px' }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {facturasFiltradas.map((factura) => {
                  const saldo = parseFloat(factura.saldo_pendiente) || 0;
                  const total = parseFloat(factura.total) || 0;
                  const pagado = total - saldo;
                  const puedeGenerarLetras = factura.estado === 'pendiente' && saldo > 0;
                  const puedePagar = (factura.estado === 'pendiente' || factura.estado === 'parcial') && saldo > 0;
                  const tienePagos = pagado > 0;
                  const estaCanjeado = factura.estado === 'canjeado';
                  const isMenuOpen = openMenu === factura.id;

                  const esNotaInterna = factura.tipo_documento === 'nota_interna';
                  const niPendiente = esNotaInterna && factura.estado === 'pendiente';
                  const niProcesada = esNotaInterna && factura.estado === 'pagado';

                  const handleProcesarNI = async () => {
                    try {
                      const res = await procesarNotaInterna(factura.id);
                      toast.success(res.data?.message || 'Procesada');
                      onRefresh?.();
                    } catch (e) {
                      toast.error(e.response?.data?.detail || 'Error al procesar');
                    }
                  };
                  const handleAnularProcesamiento = async () => {
                    if (!window.confirm('¿Revertir el procesamiento de esta Nota Interna?')) return;
                    try {
                      const res = await anularProcesamientoNotaInterna(factura.id);
                      toast.success(res.data?.message || 'Revertida');
                      onRefresh?.();
                    } catch (e) {
                      toast.error(e.response?.data?.detail || 'Error al anular');
                    }
                  };

                  // Build menu items dynamically
                  const menuItems = [];
                  if (niPendiente) menuItems.push({ label: '✓ Procesar NI', icon: CheckCircle2, color: '#059669', action: handleProcesarNI, testId: `procesar-ni-${factura.id}` });
                  if (niProcesada) menuItems.push({ label: '↻ Anular procesamiento', icon: RotateCcw, color: '#d97706', action: handleAnularProcesamiento, testId: `anular-ni-${factura.id}` });
                  if (puedePagar && !estaCanjeado && !esNotaInterna) menuItems.push({ label: 'Registrar Pago', icon: DollarSign, color: '#059669', action: () => onOpenPago(factura), testId: `pagar-factura-${factura.id}` });
                  if (puedeGenerarLetras && !esNotaInterna) menuItems.push({ label: 'Canjear por Letras', icon: FileSpreadsheet, color: '#2563eb', action: () => onOpenLetras(factura), testId: `letras-factura-${factura.id}` });
                  if (estaCanjeado) menuItems.push({ label: 'Ver Letras', icon: FileSpreadsheet, color: 'var(--muted)', action: () => onVerLetras(factura), testId: `ver-letras-${factura.id}` });
                  if (tienePagos && !estaCanjeado && !esNotaInterna) menuItems.push({ label: 'Ver Pagos', icon: History, color: 'var(--muted)', action: () => onVerPagos(factura), testId: `ver-pagos-${factura.id}` });
                  if (!esNotaInterna) menuItems.push({ label: 'Vincular Ingresos', icon: Link2, color: 'var(--muted)', action: () => onVincularIngresos(factura), testId: `vincular-ingresos-${factura.id}` });
                  if (factura.estado === 'pendiente' || niProcesada) menuItems.push({ label: 'Eliminar', icon: Trash2, color: 'var(--danger-text)', action: () => onDelete(factura.id), testId: `delete-factura-${factura.id}` });

                  return (
                    <tr key={factura.id} data-testid={`factura-row-${factura.id}`}>
                      <td>{formatDate(factura.fecha_factura)}</td>
                      <td style={{ fontWeight: 500, fontFamily: "'JetBrains Mono', monospace" }}>
                        {factura.numero}
                        {factura.tipo_documento === 'nota_interna' && (
                          <span style={{ display: 'inline-block', marginLeft: '6px', background: '#fef3c7', color: '#b45309', padding: '1px 6px', borderRadius: '4px', fontSize: '0.65rem', fontWeight: 600, verticalAlign: 'middle' }} title="Nota Interna (producción propia)">
                            🏭 Interna
                          </span>
                        )}
                      </td>
                      <td>
                        {factura.tipo_documento === 'nota_interna'
                          ? (factura.unidad_interna_nombre
                              ? <span style={{ color: '#b45309', fontWeight: 500 }}>{factura.unidad_interna_nombre}</span>
                              : <span style={{ color: 'var(--muted)', fontStyle: 'italic' }}>— sin unidad —</span>)
                          : (factura.proveedor_nombre || factura.beneficiario_nombre || '-')}
                      </td>
                      <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                        {formatCurrency(total, factura.moneda_simbolo)}
                      </td>
                      <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace", color: pagado > 0 ? '#22C55E' : 'var(--muted)' }}>
                        {pagado > 0 ? (
                          <button className="btn-link" onClick={() => onVerPagos(factura)} style={{ color: '#22C55E', fontFamily: "'JetBrains Mono', monospace", fontWeight: 500 }} title="Ver pagos">
                            {formatCurrency(pagado, factura.moneda_simbolo)}
                          </button>
                        ) : formatCurrency(pagado, factura.moneda_simbolo)}
                      </td>
                      <td>
                        {esNotaInterna ? (
                          niProcesada ? (
                            <span style={{ background: '#dcfce7', color: '#15803d', padding: '3px 8px', borderRadius: 6, fontSize: '0.7rem', fontWeight: 700 }}>
                              ✓ Procesada
                            </span>
                          ) : (
                            <span style={{ background: '#fef3c7', color: '#b45309', padding: '3px 8px', borderRadius: 6, fontSize: '0.7rem', fontWeight: 700 }}>
                              📋 CxC Virtual
                            </span>
                          )
                        ) : (
                          <span className={estadoBadge(factura.estado)} style={{ cursor: estaCanjeado ? 'pointer' : 'default' }} onClick={() => estaCanjeado && onVerLetras(factura)} title={estaCanjeado ? 'Ver letras vinculadas' : ''}>
                            {factura.estado}
                          </span>
                        )}
                      </td>
                      <td className="text-center">
                        {(() => {
                          const v = factura.vinculacion_resumen;
                          if (!v || v.estado === 'na') return <span style={{ color: '#cbd5e1', fontSize: '0.75rem' }}>-</span>;
                          if (v.estado === 'completo') return <span style={{ background: '#dcfce7', color: '#16a34a', padding: '2px 8px', borderRadius: '10px', fontSize: '0.75rem', fontWeight: 600 }} title={`${v.total_vinculado}/${v.total_cantidad}`}>Completo</span>;
                          if (v.estado === 'parcial') return <span style={{ background: 'var(--warning-bg)', color: 'var(--warning-text)', padding: '2px 8px', borderRadius: '10px', fontSize: '0.75rem', fontWeight: 600 }} title={`${v.total_vinculado}/${v.total_cantidad}`}>{v.total_vinculado}/{v.total_cantidad}</span>;
                          return <span style={{ background: 'var(--danger-bg)', color: 'var(--danger-text)', padding: '2px 8px', borderRadius: '10px', fontSize: '0.75rem', fontWeight: 600 }}>Pendiente</span>;
                        })()}
                      </td>
                      <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace", color: saldo > 0 ? '#EF4444' : '#22C55E', fontWeight: 500 }}>
                        {formatCurrency(saldo, factura.moneda_simbolo)}
                      </td>
                      <td>
                        <div className="actions-row" style={{ gap: '2px' }}>
                          <button className="action-btn" onClick={() => onView(factura)} title="Ver" data-testid={`ver-factura-${factura.id}`}><Eye size={15} /></button>
                          {factura.estado !== 'anulada' && (
                            <button className="action-btn" onClick={() => onEdit(factura)} title="Editar" data-testid={`editar-factura-${factura.id}`}><Edit2 size={15} /></button>
                          )}
                          <button className="action-btn" onClick={() => onDownloadPDF(factura)} title="PDF" data-testid={`pdf-factura-${factura.id}`}><Download size={15} /></button>
                          {menuItems.length > 0 && (
                            <div style={{ position: 'relative' }}>
                              <button
                                className="action-btn"
                                onClick={(e) => { e.stopPropagation(); setOpenMenu(isMenuOpen ? null : factura.id); }}
                                title="Mas acciones"
                                data-testid={`menu-factura-${factura.id}`}
                                style={{ background: isMenuOpen ? 'var(--card-bg-alt)' : undefined }}
                              >
                                <MoreVertical size={15} />
                              </button>
                              {isMenuOpen && (
                                <div
                                  data-testid={`dropdown-factura-${factura.id}`}
                                  style={{
                                    position: 'absolute', right: 0, top: '100%', zIndex: 50,
                                    background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: '8px',
                                    boxShadow: '0 8px 24px rgba(0,0,0,0.12)', minWidth: '180px',
                                    padding: '4px 0', marginTop: '2px'
                                  }}
                                >
                                  {menuItems.map((item, i) => (
                                    <button
                                      key={i}
                                      onClick={(e) => { e.stopPropagation(); setOpenMenu(null); item.action(); }}
                                      data-testid={item.testId}
                                      style={{
                                        display: 'flex', alignItems: 'center', gap: '8px', width: '100%',
                                        padding: '7px 12px', border: 'none', background: 'none', cursor: 'pointer',
                                        fontSize: '0.8rem', color: item.color, fontWeight: 500,
                                        transition: 'background 0.1s'
                                      }}
                                      onMouseEnter={e => e.currentTarget.style.background = 'var(--card-bg-hover)'}
                                      onMouseLeave={e => e.currentTarget.style.background = 'none'}
                                    >
                                      <item.icon size={14} />{item.label}
                                    </button>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
};

export default FacturasTable;
