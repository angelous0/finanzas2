import React, { useState, useRef } from 'react';
import { X, Upload, Download, FileSpreadsheet, CheckCircle2, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';

/**
 * Modal genérico para carga masiva por Excel.
 *
 * Props:
 *  - show: boolean
 *  - title: string (ej. "Importar gastos desde Excel")
 *  - onClose: () => void
 *  - onImported: () => void   // se llama tras una importación exitosa
 *  - downloadTemplate: () => Promise<{data: Blob}>
 *  - importFile: (file: File) => Promise<{data: ImportResult}>
 *  - templateFilename: string
 *
 *  ImportResult: { creados, errores: [{fila,error}], creados_ids, total_filas }
 */
export default function ImportExcelModal({
  show, title, onClose, onImported,
  downloadTemplate, importFile, templateFilename = 'plantilla.xlsx'
}) {
  const [file, setFile] = useState(null);
  const [importing, setImporting] = useState(false);
  const [resultado, setResultado] = useState(null); // {creados, errores, total_filas}
  const fileInputRef = useRef(null);

  if (!show) return null;

  const reset = () => {
    setFile(null);
    setResultado(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleDownloadTemplate = async () => {
    try {
      const r = await downloadTemplate();
      const blob = r.data instanceof Blob ? r.data : new Blob([r.data]);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = templateFilename; a.click();
      URL.revokeObjectURL(url);
      toast.success('Plantilla descargada');
    } catch (e) {
      toast.error('Error al descargar plantilla');
    }
  };

  const handleFileChange = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (!f.name.match(/\.(xlsx|xlsm)$/i)) {
      toast.error('El archivo debe ser .xlsx');
      return;
    }
    setFile(f);
    setResultado(null);
  };

  const handleImport = async () => {
    if (!file || importing) return;
    setImporting(true);
    setResultado(null);
    try {
      const r = await importFile(file);
      setResultado(r.data);
      if (r.data.creados > 0) {
        toast.success(`${r.data.creados} registros creados`);
        onImported?.();
      }
      if (r.data.errores?.length) {
        toast.warning(`${r.data.errores.length} fila(s) con errores`);
      }
    } catch (e) {
      const msg = e.response?.data?.detail || 'Error al importar';
      toast.error(typeof msg === 'string' ? msg : 'Error al importar');
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={handleClose} style={{ zIndex: 1100 }}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '640px' }}>
        <div className="modal-header">
          <h2 className="modal-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <FileSpreadsheet size={20} /> {title}
          </h2>
          <button className="modal-close" onClick={handleClose}><X size={20} /></button>
        </div>
        <div className="modal-body">
          {/* Paso 1: descargar plantilla */}
          <div style={{ background: 'var(--card-bg-hover)', border: '1px solid var(--border)', borderRadius: 8, padding: '0.875rem 1rem', marginBottom: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: '0.875rem' }}>1. Descarga la plantilla</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--muted)', marginTop: '0.25rem' }}>
                  Excel con cabeceras + ejemplo + hoja de instrucciones.
                </div>
              </div>
              <button type="button" className="btn btn-outline" onClick={handleDownloadTemplate}>
                <Download size={14} /> Descargar
              </button>
            </div>
          </div>

          {/* Paso 2: subir archivo */}
          <div style={{ background: 'var(--card-bg-hover)', border: '1px solid var(--border)', borderRadius: 8, padding: '0.875rem 1rem' }}>
            <div style={{ fontWeight: 600, fontSize: '0.875rem', marginBottom: '0.5rem' }}>2. Llena la plantilla y súbela aquí</div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.xlsm"
              onChange={handleFileChange}
              disabled={importing}
              style={{ width: '100%', padding: '0.5rem', border: '1px dashed var(--border)', borderRadius: 6, background: 'var(--bg)' }}
            />
            {file && (
              <div style={{ marginTop: '0.5rem', fontSize: '0.78rem', color: 'var(--muted)' }}>
                Archivo: <strong>{file.name}</strong> · {(file.size / 1024).toFixed(1)} KB
              </div>
            )}
          </div>

          {/* Resultado */}
          {resultado && (
            <div style={{ marginTop: '1rem' }}>
              <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '0.75rem' }}>
                <div style={{ flex: 1, background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.3)', borderRadius: 8, padding: '0.625rem 0.875rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', color: '#15803d', fontWeight: 600, fontSize: '0.875rem' }}>
                    <CheckCircle2 size={16} /> Creados
                  </div>
                  <div style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: '0.25rem', color: '#166534' }}>{resultado.creados}</div>
                </div>
                <div style={{ flex: 1, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 8, padding: '0.625rem 0.875rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', color: '#b91c1c', fontWeight: 600, fontSize: '0.875rem' }}>
                    <AlertCircle size={16} /> Con errores
                  </div>
                  <div style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: '0.25rem', color: '#991b1b' }}>{resultado.errores?.length || 0}</div>
                </div>
                <div style={{ flex: 1, background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: 8, padding: '0.625rem 0.875rem' }}>
                  <div style={{ color: 'var(--muted)', fontSize: '0.875rem', fontWeight: 600 }}>Total filas</div>
                  <div style={{ fontSize: '1.25rem', fontWeight: 700, marginTop: '0.25rem' }}>{resultado.total_filas || 0}</div>
                </div>
              </div>

              {resultado.errores?.length > 0 && (
                <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: 8, padding: '0.625rem', maxHeight: '180px', overflowY: 'auto' }}>
                  <div style={{ fontSize: '0.78rem', fontWeight: 600, marginBottom: '0.375rem' }}>Detalle de errores:</div>
                  {resultado.errores.map((e, i) => (
                    <div key={i} style={{ fontSize: '0.75rem', padding: '0.25rem 0', borderBottom: '1px dashed var(--border)' }}>
                      <strong>Fila {e.fila}:</strong> <span style={{ color: '#b91c1c' }}>{e.error}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-outline" onClick={handleClose}>
            {resultado ? 'Cerrar' : 'Cancelar'}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleImport}
            disabled={!file || importing}
          >
            <Upload size={14} /> {importing ? 'Importando...' : 'Importar'}
          </button>
        </div>
      </div>
    </div>
  );
}
