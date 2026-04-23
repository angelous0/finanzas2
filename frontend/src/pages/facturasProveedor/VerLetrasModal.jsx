import React, { useState, useEffect } from 'react';
import { getLetrasDeFactura, deshacerCanjeLetras } from '../../services/api';
import { formatCurrency, formatDate, estadoBadge } from './helpers';
import { X, Undo2 } from 'lucide-react';
import { toast } from 'sonner';

const VerLetrasModal = ({ show, factura, onClose, onDataChanged }) => {
  const [letras, setLetras] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (factura && show) {
      loadLetras();
    }
  }, [factura, show]);

  const loadLetras = async () => {
    setLoading(true);
    try {
      const response = await getLetrasDeFactura(factura.id);
      setLetras(response.data);
    } catch (error) {
      console.error('Error loading letras:', error);
      toast.error('Error al cargar letras');
    } finally {
      setLoading(false);
    }
  };

  const handleDeshacer = async () => {
    if (!window.confirm('Esta seguro de deshacer el canje? Se eliminaran todas las letras y la factura volvera a estado pendiente.')) return;
    try {
      await deshacerCanjeLetras(factura.id);
      toast.success('Canje deshecho exitosamente');
      onClose();
      onDataChanged();
    } catch (error) {
      console.error('Error deshaciendo canje:', error);
      toast.error(typeof error.response?.data?.detail === 'string' ? error.response?.data?.detail : 'Error al deshacer canje');
    }
  };

  if (!show || !factura) return null;

  const hayLetrasPagadas = letras.some(l => parseFloat(l.saldo_pendiente) < parseFloat(l.monto));

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '700px' }}>
        <div className="modal-header">
          <h2 className="modal-title">Letras Vinculadas</h2>
          <button className="modal-close" onClick={onClose}><X size={20} /></button>
        </div>
        <div className="modal-body">
          <div style={{ background: 'var(--warning-bg)', padding: '1rem', borderRadius: '8px', marginBottom: '1.5rem', border: '1px solid var(--warning-border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <span style={{ color: 'var(--warning-text)' }}>Documento Canjeado:</span>
              <span style={{ fontWeight: 600, fontFamily: "'JetBrains Mono', monospace", color: 'var(--warning-text)' }}>{factura.numero}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <span style={{ color: 'var(--warning-text)' }}>Proveedor:</span>
              <span style={{ fontWeight: 500 }}>{factura.proveedor_nombre || factura.beneficiario_nombre}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--warning-text)' }}>Monto Canjeado:</span>
              <span style={{ fontWeight: 600, fontFamily: "'JetBrains Mono', monospace", color: 'var(--warning-text)' }}>{formatCurrency(factura.total)}</span>
            </div>
          </div>

          {loading ? (
            <div className="loading"><div className="loading-spinner"></div></div>
          ) : letras.length === 0 ? (
            <div className="empty-state" style={{ padding: '2rem' }}>
              <div className="empty-state-title">No hay letras vinculadas</div>
            </div>
          ) : (
            <table className="data-table" style={{ fontSize: '0.875rem' }}>
              <thead>
                <tr>
                  <th>N. Letra</th><th>Fecha Emision</th><th>Fecha Venc.</th>
                  <th className="text-right">Monto</th><th className="text-right">Saldo</th><th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {letras.map((letra) => (
                  <tr key={letra.id}>
                    <td style={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 500 }}>{letra.numero}</td>
                    <td>{formatDate(letra.fecha_emision)}</td>
                    <td>{formatDate(letra.fecha_vencimiento)}</td>
                    <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {formatCurrency(letra.monto, letra.moneda_simbolo)}
                    </td>
                    <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace", color: parseFloat(letra.saldo_pendiente) > 0 ? '#EF4444' : '#22C55E', fontWeight: 500 }}>
                      {formatCurrency(parseFloat(letra.saldo_pendiente ?? letra.monto), letra.moneda_simbolo)}
                    </td>
                    <td><span className={estadoBadge(letra.estado)}>{letra.estado}</span></td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr style={{ background: 'var(--card-bg-hover)', fontWeight: 600 }}>
                  <td colSpan={3}>Total Letras</td>
                  <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                    {formatCurrency(letras.reduce((sum, l) => sum + parseFloat(l.monto || 0), 0))}
                  </td>
                  <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace", color: '#EF4444' }}>
                    {formatCurrency(letras.reduce((sum, l) => sum + parseFloat(l.saldo_pendiente ?? l.monto ?? 0), 0))}
                  </td>
                  <td></td>
                </tr>
              </tfoot>
            </table>
          )}
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-outline btn-danger" onClick={handleDeshacer} disabled={hayLetrasPagadas} title={hayLetrasPagadas ? 'No se puede deshacer - hay letras con pagos' : 'Deshacer canje'}>
            <Undo2 size={16} />
            Deshacer Canje
          </button>
          <button type="button" className="btn btn-outline" onClick={onClose}>Cerrar</button>
        </div>
      </div>
    </div>
  );
};

export default VerLetrasModal;
