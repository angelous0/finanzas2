import React, { useState } from 'react';
import { exportCompraAPP } from '../../services/api';
import { X, FileSpreadsheet } from 'lucide-react';
import { toast } from 'sonner';

const ExportModal = ({ show, onClose }) => {
  const [exportDesde, setExportDesde] = useState('');
  const [exportHasta, setExportHasta] = useState('');
  const [exporting, setExporting] = useState(false);

  if (!show) return null;

  const handleExport = async () => {
    setExporting(true);
    try {
      const params = {};
      if (exportDesde) params.desde = exportDesde;
      if (exportHasta) params.hasta = exportHasta;
      const response = await exportCompraAPP(params);
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `CompraAPP_${exportDesde || 'all'}_${exportHasta || 'all'}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Archivo CompraAPP exportado exitosamente');
      onClose();
    } catch (error) {
      console.error('Export error:', error);
      const detail = error.response?.data;
      if (detail && detail instanceof Blob) {
        const text = await detail.text();
        try {
          const parsed = JSON.parse(text);
          if (parsed.detail?.errors) {
            toast.error(`${parsed.detail.message}:\n${parsed.detail.errors.slice(0, 3).join('\n')}`);
          } else {
            toast.error(parsed.detail?.message || (typeof parsed.detail === 'string' ? parsed.detail : 'Error al exportar'));
          }
        } catch { toast.error('Error al exportar CompraAPP'); }
      } else {
        toast.error(detail?.detail?.message || (typeof detail?.detail === 'string' ? detail?.detail : 'Error al exportar CompraAPP'));
      }
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: '420px' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">Exportar CompraAPP</h2>
          <button className="modal-close" onClick={onClose}><X size={20} /></button>
        </div>
        <div className="modal-body">
          <p style={{ fontSize: '0.875rem', color: 'var(--muted)', marginBottom: '1rem' }}>
            Exporta facturas de proveedor y gastos en formato Excel para contabilidad SUNAT.
          </p>
          <div className="form-grid form-grid-2">
            <div className="form-group">
              <label className="form-label">Desde</label>
              <input type="date" className="form-input" value={exportDesde} onChange={(e) => setExportDesde(e.target.value)} data-testid="export-desde" />
            </div>
            <div className="form-group">
              <label className="form-label">Hasta</label>
              <input type="date" className="form-input" value={exportHasta} onChange={(e) => setExportHasta(e.target.value)} data-testid="export-hasta" />
            </div>
          </div>
        </div>
        <div className="modal-footer">
          <button type="button" className="btn btn-outline" onClick={onClose}>Cancelar</button>
          <button type="button" className="btn btn-primary" onClick={handleExport} disabled={exporting} data-testid="export-confirm-btn">
            <FileSpreadsheet size={16} />
            {exporting ? 'Exportando...' : 'Exportar Excel'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ExportModal;
