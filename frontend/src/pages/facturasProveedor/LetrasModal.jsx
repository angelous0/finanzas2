import React, { useState, useEffect } from 'react';
import { generarLetras } from '../../services/api';
import { formatCurrency } from './helpers';
import { X, FileSpreadsheet } from 'lucide-react';
import { toast } from 'sonner';

const LetrasModal = ({ show, factura, cuentasFinancieras, onClose, onLetrasCreadas }) => {
  const [letrasConfig, setLetrasConfig] = useState({
    prefijo: 'LT',
    cantidad: 3,
    intervalo_dias: 30,
    fecha_giro: new Date().toISOString().split('T')[0],
    banco_id: ''
  });
  const [letrasPreview, setLetrasPreview] = useState([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (factura && show) {
      const cfg = {
        prefijo: 'LT',
        cantidad: 3,
        intervalo_dias: 30,
        fecha_giro: new Date().toISOString().split('T')[0],
        banco_id: cuentasFinancieras.find(c => c.tipo === 'banco')?.id || cuentasFinancieras[0]?.id || ''
      };
      setLetrasConfig(cfg);
      generatePreview(factura, cfg.cantidad, cfg.intervalo_dias, cfg.fecha_giro);
    }
  }, [factura, show, cuentasFinancieras]);

  const generatePreview = (fac, cantidad, intervalo, fechaGiro) => {
    const saldo = parseFloat(fac?.saldo_pendiente || 0);
    const montoLetra = saldo / cantidad;
    const letras = [];
    for (let i = 0; i < cantidad; i++) {
      const fechaVenc = new Date(fechaGiro);
      fechaVenc.setDate(fechaVenc.getDate() + (intervalo * (i + 1)));
      letras.push({
        numero: i + 1,
        fecha_vencimiento: fechaVenc.toISOString().split('T')[0],
        monto: montoLetra
      });
    }
    setLetrasPreview(letras);
  };

  const handleConfigChange = (field, value) => {
    const newConfig = { ...letrasConfig, [field]: value };
    setLetrasConfig(newConfig);
    if (factura) {
      generatePreview(
        factura,
        field === 'cantidad' ? parseInt(value) : parseInt(newConfig.cantidad),
        field === 'intervalo_dias' ? parseInt(value) : parseInt(newConfig.intervalo_dias),
        field === 'fecha_giro' ? value : newConfig.fecha_giro
      );
    }
  };

  const handleLetraChange = (index, field, value) => {
    setLetrasPreview(prev => prev.map((letra, i) =>
      i === index ? { ...letra, [field]: field === 'monto' ? parseFloat(value) || 0 : value } : letra
    ));
  };

  const handleCrear = async () => {
    if (saving) return;  // Anti-doble-click
    const totalLetras = letrasPreview.reduce((sum, l) => sum + l.monto, 0);
    const totalFactura = parseFloat(factura.total) || 0;
    if (Math.abs(totalLetras - totalFactura) > 0.01) {
      toast.error(`El total de las letras (${formatCurrency(totalLetras)}) debe ser igual al total de la factura (${formatCurrency(totalFactura)})`);
      return;
    }
    setSaving(true);
    try {
      await generarLetras({
        factura_id: factura.id,
        cantidad_letras: letrasPreview.length,
        dias_entre_letras: parseInt(letrasConfig.intervalo_dias),
        letras_personalizadas: letrasPreview.map(l => ({
          fecha_vencimiento: l.fecha_vencimiento,
          monto: l.monto
        }))
      });
      toast.success(`${letrasPreview.length} letras creadas exitosamente`);
      onLetrasCreadas();
    } catch (error) {
      console.error('Error creando letras:', error);
      toast.error(typeof error.response?.data?.detail === 'string' ? error.response?.data?.detail : 'Error al crear letras');
    } finally {
      setSaving(false);
    }
  };

  if (!show || !factura) return null;

  const totalLetras = letrasPreview.reduce((sum, l) => sum + l.monto, 0);
  const totalFactura = parseFloat(factura.total || 0);
  const mismatch = Math.abs(totalLetras - totalFactura) > 0.01;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '600px' }}>
        <div className="modal-header">
          <h2 className="modal-title">Canjear por Letras</h2>
          <button className="modal-close" onClick={onClose}><X size={20} /></button>
        </div>
        <div className="modal-body">
          {/* Info doc */}
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
              <span style={{ color: 'var(--muted)' }}>Saldo a canjear:</span>
              <span style={{ fontWeight: 600, color: 'var(--primary)', fontFamily: "'JetBrains Mono', monospace" }}>{formatCurrency(factura.saldo_pendiente)}</span>
            </div>
          </div>

          {/* Quick generation */}
          <div style={{ background: 'var(--success-bg)', padding: '1rem', borderRadius: '8px', marginBottom: '1.5rem', border: '1px solid var(--success-border)' }}>
            <h4 style={{ margin: '0 0 1rem', fontSize: '0.875rem', fontWeight: 600, color: 'var(--success-text)' }}>Generacion Rapida</h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem' }}>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Prefijo</label>
                <input type="text" className="form-input" value={letrasConfig.prefijo} onChange={(e) => handleConfigChange('prefijo', e.target.value)} style={{ fontFamily: "'JetBrains Mono', monospace" }} />
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Cantidad Letras</label>
                <input type="number" min="1" max="12" className="form-input" value={letrasConfig.cantidad} onChange={(e) => handleConfigChange('cantidad', e.target.value)} data-testid="letras-cantidad-input" />
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <label className="form-label">Intervalo (dias)</label>
                <input type="number" min="1" className="form-input" value={letrasConfig.intervalo_dias} onChange={(e) => handleConfigChange('intervalo_dias', e.target.value)} />
              </div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label required">Fecha de Giro</label>
              <input type="date" className="form-input" value={letrasConfig.fecha_giro} onChange={(e) => handleConfigChange('fecha_giro', e.target.value)} />
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label required">Banco para pago</label>
              <select className="form-input form-select" value={letrasConfig.banco_id} onChange={(e) => setLetrasConfig(prev => ({ ...prev, banco_id: e.target.value }))} data-testid="letras-banco-select">
                <option value="">Seleccionar banco...</option>
                {cuentasFinancieras.map(c => (<option key={c.id} value={c.id}>{c.nombre}</option>))}
              </select>
            </div>
          </div>

          {/* Preview */}
          <div style={{ marginBottom: '1rem' }}>
            <h4 style={{ margin: '0 0 0.75rem', fontSize: '0.875rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              Letras a crear ({letrasPreview.length})
              <span style={{ fontWeight: 400, fontSize: '0.75rem', color: 'var(--muted)' }}>- Puedes editar montos y fechas antes de crear</span>
            </h4>
            <table className="data-table" style={{ fontSize: '0.8125rem' }}>
              <thead>
                <tr><th>N. Letra</th><th>Fecha Venc.</th><th className="text-right">Monto</th></tr>
              </thead>
              <tbody>
                {letrasPreview.map((letra, index) => (
                  <tr key={index}>
                    <td style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                      {letrasConfig.prefijo}-{factura.numero}-{String(letra.numero).padStart(2, '0')}
                    </td>
                    <td style={{ padding: 0 }}>
                      <input type="date" value={letra.fecha_vencimiento} onChange={(e) => handleLetraChange(index, 'fecha_vencimiento', e.target.value)} style={{ width: '100%', padding: '0.5rem', border: 'none', background: 'transparent', fontFamily: 'inherit', fontSize: 'inherit' }} data-testid={`letra-fecha-${index}`} />
                    </td>
                    <td style={{ padding: 0 }}>
                      <input type="number" step="0.01" value={letra.monto} onChange={(e) => handleLetraChange(index, 'monto', e.target.value)} style={{ width: '100%', padding: '0.5rem', border: 'none', background: 'transparent', fontFamily: "'JetBrains Mono', monospace", fontSize: 'inherit', textAlign: 'right' }} data-testid={`letra-monto-${index}`} />
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr style={{ background: 'var(--card-bg-hover)', fontWeight: 600 }}>
                  <td colSpan={2}>Total Letras</td>
                  <td className="text-right" style={{ fontFamily: "'JetBrains Mono', monospace", color: mismatch ? '#EF4444' : 'var(--primary)' }}>
                    {formatCurrency(totalLetras)}
                    {mismatch && (<span style={{ display: 'block', fontSize: '0.7rem', fontWeight: 400 }}>Debe ser: {formatCurrency(factura.total)}</span>)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-outline" onClick={onClose} disabled={saving}>Cancelar</button>
          <button type="button" className="btn btn-primary" onClick={handleCrear} disabled={saving} data-testid="crear-letras-btn">
            <FileSpreadsheet size={16} />
            {saving ? 'Creando...' : `Crear ${letrasPreview.length} Letras`}
          </button>
        </div>
      </div>
    </div>
  );
};

export default LetrasModal;
