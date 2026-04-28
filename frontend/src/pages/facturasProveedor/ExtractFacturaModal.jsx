import React, { useState, useRef } from 'react';
import { X, Camera, FileText, FileCode2, Loader2, Sparkles, AlertCircle, CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner';
import {
  extractFacturaFromImage,
  extractFacturaFromPDF,
  extractFacturaFromXML,
} from '../../services/api';

/**
 * Modal de extracción automática de factura.
 * El usuario sube foto / PDF / XML SUNAT y obtenemos los datos pre-llenados.
 *
 * Props:
 *   show, onClose, onExtracted(data)
 */
export default function ExtractFacturaModal({ show, onClose, onExtracted }) {
  const [tab, setTab] = useState('image'); // 'image' | 'pdf' | 'xml'
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [resultado, setResultado] = useState(null);
  const inputRef = useRef(null);

  if (!show) return null;

  const reset = () => {
    setFile(null);
    setResultado(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleFileChange = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setFile(f);
    setResultado(null);
  };

  const handleExtract = async () => {
    if (!file || loading) return;
    setLoading(true);
    setResultado(null);
    try {
      let r;
      if (tab === 'image') r = await extractFacturaFromImage(file);
      else if (tab === 'pdf') r = await extractFacturaFromPDF(file);
      else r = await extractFacturaFromXML(file);
      setResultado(r.data);
      const conf = r.data?.data?.confianza;
      const fuente = { image: 'imagen', pdf: 'PDF', xml: 'XML SUNAT' }[tab];
      toast.success(`Factura extraída desde ${fuente}${conf ? ` (confianza: ${(conf * 100).toFixed(0)}%)` : ''}`);
    } catch (e) {
      const msg = e.response?.data?.detail || 'Error al extraer';
      toast.error(typeof msg === 'string' ? msg : 'Error al extraer');
    } finally {
      setLoading(false);
    }
  };

  const handleApply = () => {
    if (!resultado?.data) return;
    onExtracted(resultado.data);
    handleClose();
  };

  const TABS = [
    { id: 'image', label: 'Foto', icon: Camera, accept: 'image/*', desc: 'JPG, PNG, HEIC. Toma una foto o sube de tu galería.' },
    { id: 'pdf', label: 'PDF', icon: FileText, accept: '.pdf', desc: 'Factura escaneada o nativa. Procesamos la primera página.' },
    { id: 'xml', label: 'XML SUNAT', icon: FileCode2, accept: '.xml', desc: 'Factura electrónica oficial (UBL 2.1). 100% precisa, gratis.' },
  ];
  const currentTab = TABS.find(t => t.id === tab);

  return (
    <div className="modal-overlay" onClick={handleClose} style={{ zIndex: 1100 }}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '700px' }}>
        <div className="modal-header">
          <h2 className="modal-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Sparkles size={20} /> Cargar factura automáticamente
          </h2>
          <button className="modal-close" onClick={handleClose}><X size={20} /></button>
        </div>
        <div className="modal-body">
          {/* Tabs */}
          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
            {TABS.map(t => {
              const Icon = t.icon;
              const active = tab === t.id;
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => { setTab(t.id); reset(); }}
                  style={{
                    flex: 1,
                    padding: '0.625rem 0.75rem',
                    border: 'none',
                    background: active ? 'var(--primary)' : 'transparent',
                    color: active ? 'white' : 'var(--muted)',
                    borderRadius: 6,
                    cursor: 'pointer',
                    fontWeight: 500,
                    fontSize: '0.875rem',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.375rem',
                    transition: 'all 0.15s',
                  }}
                >
                  <Icon size={16} /> {t.label}
                </button>
              );
            })}
          </div>

          {/* Descripción */}
          <p style={{ fontSize: '0.78rem', color: 'var(--muted)', marginBottom: '0.75rem' }}>
            {currentTab.desc}
          </p>

          {/* Input archivo */}
          <div style={{ background: 'var(--card-bg-hover)', border: '1px solid var(--border)', borderRadius: 8, padding: '1rem' }}>
            <input
              ref={inputRef}
              type="file"
              accept={currentTab.accept}
              capture={tab === 'image' ? 'environment' : undefined}
              onChange={handleFileChange}
              disabled={loading}
              style={{ width: '100%', padding: '0.5rem', border: '1px dashed var(--border)', borderRadius: 6, background: 'var(--bg)' }}
            />
            {file && (
              <div style={{ marginTop: '0.5rem', fontSize: '0.78rem', color: 'var(--muted)' }}>
                Archivo: <strong>{file.name}</strong> · {(file.size / 1024).toFixed(1)} KB
              </div>
            )}
          </div>

          {/* Loading */}
          {loading && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', padding: '1.5rem', color: 'var(--muted)' }}>
              <Loader2 size={20} className="animate-spin" />
              <span>Analizando factura{tab !== 'xml' ? ' con IA' : ''}…</span>
            </div>
          )}

          {/* Resultado */}
          {resultado?.data && (
            <div style={{ marginTop: '1rem', background: 'rgba(34,197,94,0.05)', border: '1px solid rgba(34,197,94,0.3)', borderRadius: 8, padding: '0.875rem 1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', color: '#15803d', fontWeight: 600, fontSize: '0.875rem', marginBottom: '0.625rem' }}>
                <CheckCircle2 size={16} /> Factura analizada
                {resultado.data.confianza < 0.7 && (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', color: '#d97706', fontSize: '0.7rem', marginLeft: '0.5rem' }}>
                    <AlertCircle size={12} /> Revisa los datos antes de guardar
                  </span>
                )}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem 1rem', fontSize: '0.78rem' }}>
                <div><span style={{ color: 'var(--muted)' }}>Tipo:</span> <strong>{resultado.data.tipo_documento || '—'}</strong></div>
                <div><span style={{ color: 'var(--muted)' }}>N° Doc:</span> <strong>{resultado.data.numero || '—'}</strong></div>
                <div><span style={{ color: 'var(--muted)' }}>Fecha:</span> <strong>{resultado.data.fecha_factura || '—'}</strong></div>
                <div><span style={{ color: 'var(--muted)' }}>Vencimiento:</span> <strong>{resultado.data.fecha_vencimiento || '—'}</strong></div>
                <div style={{ gridColumn: '1 / -1' }}>
                  <span style={{ color: 'var(--muted)' }}>Proveedor:</span> <strong>{resultado.data.proveedor?.nombre || '—'}</strong>
                  {resultado.data.proveedor?.ruc && <span style={{ color: 'var(--muted)' }}> · RUC {resultado.data.proveedor.ruc}</span>}
                  {resultado.data.proveedor?.match === 'no_encontrado' && (
                    <span style={{ marginLeft: '0.5rem', fontSize: '0.7rem', background: 'rgba(245,158,11,0.15)', color: '#b45309', padding: '2px 6px', borderRadius: 4 }}>
                      ⚠ proveedor nuevo — se creará al guardar
                    </span>
                  )}
                  {resultado.data.proveedor?.match === 'encontrado' && (
                    <span style={{ marginLeft: '0.5rem', fontSize: '0.7rem', background: 'rgba(34,197,94,0.15)', color: '#15803d', padding: '2px 6px', borderRadius: 4 }}>
                      ✓ encontrado en BD
                    </span>
                  )}
                </div>
                <div><span style={{ color: 'var(--muted)' }}>Subtotal:</span> <strong>S/ {(resultado.data.totales?.subtotal || 0).toFixed(2)}</strong></div>
                <div><span style={{ color: 'var(--muted)' }}>IGV:</span> <strong>S/ {(resultado.data.totales?.igv || 0).toFixed(2)}</strong></div>
                <div style={{ gridColumn: '1 / -1', fontSize: '0.95rem', marginTop: '0.25rem' }}>
                  <span style={{ color: 'var(--muted)' }}>Total:</span> <strong style={{ color: 'var(--primary)' }}>S/ {(resultado.data.totales?.total || 0).toFixed(2)}</strong>
                </div>
                <div style={{ gridColumn: '1 / -1', fontSize: '0.7rem', color: 'var(--muted)', marginTop: '0.25rem' }}>
                  {resultado.data.lineas?.length || 0} línea(s) detectada(s)
                </div>
              </div>
            </div>
          )}
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-outline" onClick={handleClose}>Cancelar</button>
          {!resultado?.data ? (
            <button type="button" className="btn btn-primary" onClick={handleExtract} disabled={!file || loading}>
              <Sparkles size={14} /> {loading ? 'Analizando…' : 'Analizar'}
            </button>
          ) : (
            <button type="button" className="btn btn-primary" onClick={handleApply}>
              <CheckCircle2 size={14} /> Aplicar al formulario
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
