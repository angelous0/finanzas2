import React, { useState } from 'react';
import { createPago, getPagosDeFactura } from '../../services/api';
import { formatCurrency } from './helpers';
import { X, DollarSign } from 'lucide-react';
import { toast } from 'sonner';

const PagoModal = ({ show, factura, cuentasFinancieras, onClose, onPagoRegistrado }) => {
  const [registrando, setRegistrando] = useState(false);
  const [pagoData, setPagoData] = useState({
    cuenta_id: '',
    medio_pago: 'transferencia',
    monto: 0,
    referencia: ''
  });

  // Initialize pagoData when factura changes
  React.useEffect(() => {
    if (factura && show) {
      const initPago = async () => {
        let referencia = factura.numero || '';
        try {
          const pagosRes = await getPagosDeFactura(factura.id);
          const numPagos = pagosRes.data?.length || 0;
          if (numPagos > 0) {
            referencia = `${factura.numero} - PAGO ${numPagos + 1}`;
          }
        } catch (e) { /* use document number */ }

        setPagoData({
          cuenta_id: cuentasFinancieras[0]?.id || '',
          medio_pago: 'transferencia',
          monto: parseFloat(factura.saldo_pendiente) || 0,
          referencia
        });
      };
      initPago();
    }
  }, [factura, show, cuentasFinancieras]);

  if (!show || !factura) return null;

  const handleRegistrar = async () => {
    if (registrando) return;
    if (!pagoData.cuenta_id) { toast.error('Seleccione una cuenta'); return; }
    if (pagoData.monto <= 0) { toast.error('El monto debe ser mayor a 0'); return; }

    const saldoPendiente = parseFloat(factura.saldo_pendiente) || 0;
    if (parseFloat(pagoData.monto) > saldoPendiente) {
      toast.error(`El monto no puede ser mayor al saldo pendiente (${formatCurrency(saldoPendiente)})`);
      return;
    }

    setRegistrando(true);
    try {
      await createPago({
        tipo: 'egreso',
        fecha: new Date().toISOString().split('T')[0],
        cuenta_financiera_id: parseInt(pagoData.cuenta_id),
        moneda_id: factura.moneda_id || (cuentasFinancieras.find(c => c.id === parseInt(pagoData.cuenta_id))?.moneda_id) || null,
        monto_total: parseFloat(pagoData.monto),
        referencia: pagoData.referencia,
        detalles: [{
          cuenta_financiera_id: parseInt(pagoData.cuenta_id),
          medio_pago: pagoData.medio_pago,
          monto: parseFloat(pagoData.monto),
          referencia: pagoData.referencia
        }],
        aplicaciones: [{
          tipo_documento: 'factura',
          documento_id: factura.id,
          monto_aplicado: parseFloat(pagoData.monto)
        }]
      });
      toast.success('Pago registrado exitosamente');
      onPagoRegistrado();
    } catch (error) {
      console.error('Error registrando pago:', error);
      toast.error(error.response?.data?.detail || 'Error al registrar pago');
    } finally {
      setRegistrando(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '500px' }}>
        <div className="modal-header">
          <h2 className="modal-title">Agregar Pago</h2>
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
              <span style={{ color: 'var(--muted)' }}>Saldo Pendiente:</span>
              <span style={{ fontWeight: 600, color: '#EF4444', fontFamily: "'JetBrains Mono', monospace" }}>{formatCurrency(factura.saldo_pendiente)}</span>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label required">Cuenta</label>
            <select className="form-input form-select" value={pagoData.cuenta_id} onChange={(e) => setPagoData(prev => ({ ...prev, cuenta_id: e.target.value }))} data-testid="pago-cuenta-select">
              <option value="">Seleccionar cuenta...</option>
              {cuentasFinancieras.filter(c => !c.es_ficticia).map(c => (<option key={c.id} value={c.id}>{c.nombre}</option>))}
              {cuentasFinancieras.some(c => c.es_ficticia) && <option disabled>── Unidades Internas ──</option>}
              {cuentasFinancieras.filter(c => c.es_ficticia).map(c => (<option key={c.id} value={c.id}>⚡ {c.nombre} (S/ {(c.saldo_actual||0).toFixed(2)})</option>))}
            </select>
            {pagoData.cuenta_id && cuentasFinancieras.find(c => c.id == pagoData.cuenta_id && c.es_ficticia) && (
              <div style={{ padding: '6px 10px', background: 'var(--warning-bg)', border: '1px solid var(--warning-border)', borderRadius: 6, marginTop: 6, fontSize: '0.75rem', color: 'var(--warning-text)' }}>
                Este pago sale de la cuenta de una <strong>unidad interna</strong>, no de la caja de la empresa.
              </div>
            )}
          </div>
          <div className="form-group">
            <label className="form-label required">Medio de Pago</label>
            <select className="form-input form-select" value={pagoData.medio_pago} onChange={(e) => setPagoData(prev => ({ ...prev, medio_pago: e.target.value }))} data-testid="pago-medio-select">
              <option value="transferencia">Transferencia</option>
              <option value="efectivo">Efectivo</option>
              <option value="cheque">Cheque</option>
              <option value="tarjeta">Tarjeta</option>
            </select>
          </div>
          <div className="form-group">
            <label className="form-label required">Monto</label>
            <input type="number" step="0.01" className="form-input" value={pagoData.monto} onChange={(e) => setPagoData(prev => ({ ...prev, monto: e.target.value }))} style={{ fontFamily: "'JetBrains Mono', monospace" }} data-testid="pago-monto-input" />
          </div>
          <div className="form-group">
            <label className="form-label">Referencia / N. Operacion</label>
            <input type="text" className="form-input" placeholder="Ej: OP-12345678" value={pagoData.referencia} onChange={(e) => setPagoData(prev => ({ ...prev, referencia: e.target.value }))} data-testid="pago-referencia-input" />
          </div>
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-outline" onClick={onClose}>Cancelar</button>
          <button type="button" className="btn btn-success" onClick={handleRegistrar} disabled={registrando} data-testid="registrar-pago-btn">
            <DollarSign size={16} />
            {registrando ? 'Registrando...' : 'Registrar Pago'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default PagoModal;
