import React, { useState, useEffect } from 'react';
import { getPagosDeFactura, deletePago } from '../../services/api';
import { formatCurrency, formatDate } from './helpers';
import { X, Undo2 } from 'lucide-react';
import { toast } from 'sonner';

const VerPagosModal = ({ show, factura, onClose, onDataChanged }) => {
  const [pagos, setPagos] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (factura && show) {
      loadPagos();
    }
  }, [factura, show]);

  const loadPagos = async () => {
    setLoading(true);
    try {
      const response = await getPagosDeFactura(factura.id);
      setPagos(response.data);
    } catch (error) {
      console.error('Error loading pagos:', error);
      toast.error('Error al cargar pagos');
    } finally {
      setLoading(false);
    }
  };

  const handleAnular = async (pagoId) => {
    if (!window.confirm('Esta seguro de anular este pago? Se revertira el saldo de la factura.')) return;
    try {
      await deletePago(pagoId);
      toast.success('Pago anulado exitosamente');
      const response = await getPagosDeFactura(factura.id);
      setPagos(response.data);
      if (response.data.length === 0) {
        onClose();
      }
      onDataChanged();
    } catch (error) {
      console.error('Error anulando pago:', error);
      toast.error(error.response?.data?.detail || 'Error al anular pago');
    }
  };

  if (!show || !factura) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '700px' }}>
        <div className="modal-header">
          <h2 className="modal-title">Historial de Pagos</h2>
          <button className="modal-close" onClick={onClose}><X size={20} /></button>
        </div>
        <div className="modal-body">
          <div style={{ background: 'var(--card-bg-hover)', padding: '1rem', borderRadius: '8px', marginBottom: '1.5rem', border: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <span style={{ color: 'var(--muted)' }}>Documento:</span>
              <span style={{ fontWeight: 600, fontFamily: "'JetBrains Mono', monospace" }}>{factura.numero}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <span style={{ color: 'var(--muted)' }}>Proveedor:</span>
              <span style={{ fontWeight: 500 }}>{factura.proveedor_nombre || factura.beneficiario_nombre}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--muted)' }}>Total Factura:</span>
              <span style={{ fontWeight: 600, fontFamily: "'JetBrains Mono', monospace" }}>{formatCurrency(factura.total)}</span>
            </div>
          </div>

          {loading ? (
            <div className="loading"><div className="loading-spinner"></div></div>
          ) : pagos.length === 0 ? (
            <div className="empty-state" style={{ padding: '2rem' }}>
              <div className="empty-state-title">No hay pagos registrados</div>
            </div>
          ) : (
            <table className="data-table" style={{ fontSize: '0.875rem' }}>
              <thead>
                <tr>
                  <th>Fecha</th><th>N. Pago</th><th>Cuenta</th><th>Medio</th>
                  <th className="text-right">Monto</th><th>Referencia</th><th className="text-center">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {pagos.map((pago) => (
                  <tr key={pago.id}>
                    <td>{formatDate(pago.fecha)}</td>
                    <td style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 500 }}>{pago.numero}</td>
                    <td>{pago.cuenta_nombre}</td>
                    <td style={{ textTransform: 'capitalize' }}>{pago.medio_pago || '-'}</td>
                    <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace", color: '#22C55E', fontWeight: 500 }}>
                      {formatCurrency(pago.monto_aplicado, pago.moneda_simbolo)}
                    </td>
                    <td>{pago.referencia || '-'}</td>
                    <td className="text-center">
                      <button className="btn btn-outline btn-sm btn-icon btn-danger" onClick={() => handleAnular(pago.id)} title="Anular pago" data-testid={`anular-pago-${pago.id}`}>
                        <Undo2 size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr style={{ background: 'var(--card-bg-hover)', fontWeight: 600 }}>
                  <td colSpan={4}>Total Pagado</td>
                  <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace", color: '#22C55E' }}>
                    {formatCurrency(pagos.reduce((sum, p) => sum + parseFloat(p.monto_aplicado || 0), 0))}
                  </td>
                  <td colSpan={2}></td>
                </tr>
              </tfoot>
            </table>
          )}
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-outline" onClick={onClose}>Cerrar</button>
        </div>
      </div>
    </div>
  );
};

export default VerPagosModal;
