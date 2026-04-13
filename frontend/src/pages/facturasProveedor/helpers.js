/**
 * Helpers compartidos para el módulo de Facturas de Proveedor.
 */

export const formatCurrency = (value, symbol = 'S/') => {
  const s = symbol || 'S/';
  return `${s} ${Number(value || 0).toLocaleString('es-PE', { minimumFractionDigits: 2 })}`;
};

export const formatDate = (dateStr) => {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString('es-PE');
};

export const estadoBadge = (estado) => {
  const badges = {
    pendiente: 'badge badge-warning',
    parcial: 'badge badge-info',
    pagado: 'badge badge-success',
    canjeado: 'badge badge-canjeado',
    anulada: 'badge badge-error'
  };
  return badges[estado] || 'badge badge-neutral';
};

export const calcularImporteArticulo = (articulo) => {
  const cantidad = parseFloat(articulo.cantidad) || 0;
  const precio = parseFloat(articulo.precio) || 0;
  return cantidad * precio;
};

export const getEmptyLinea = () => ({
  categoria_id: '', descripcion: '', linea_negocio_id: '', centro_costo_id: '', unidad_interna_id: '', importe: 0, igv_aplica: true
});

export const getEmptyFormData = (monedaId = '') => ({
  proveedor_id: '',
  beneficiario_nombre: '',
  moneda_id: monedaId,
  tipo_cambio: '1',
  fecha_factura: new Date().toISOString().split('T')[0],
  fecha_contable: new Date().toISOString().split('T')[0],
  fecha_vencimiento: '',
  terminos_dias: 30,
  tipo_documento: 'factura',
  numero: '',
  impuestos_incluidos: true,
  tipo_comprobante_sunat: '01',
  base_gravada: 0,
  igv_sunat: 0,
  base_no_gravada: 0,
  isc: 0,
  notas: '',
  lineas: [getEmptyLinea()],
  articulos: []
});

export const calcularTotales = (formData) => {
  let subtotal = 0;
  let igv = 0;
  let base_gravada = 0;
  let igv_sunat = 0;
  let base_no_gravada = 0;

  formData.lineas.forEach(linea => {
    const importe = parseFloat(linea.importe) || 0;
    if (linea.igv_aplica) {
      if (formData.impuestos_incluidos) {
        const base = importe / 1.18;
        const lineaIgv = importe - base;
        subtotal += base;
        igv += lineaIgv;
        base_gravada += base;
        igv_sunat += lineaIgv;
      } else {
        subtotal += importe;
        igv += importe * 0.18;
        base_gravada += importe;
        igv_sunat += importe * 0.18;
      }
    } else {
      subtotal += importe;
      base_no_gravada += importe;
    }
  });

  formData.articulos.forEach(art => {
    const importe = calcularImporteArticulo(art);
    if (art.igv_aplica) {
      if (formData.impuestos_incluidos) {
        const base = importe / 1.18;
        const artIgv = importe - base;
        subtotal += base;
        igv += artIgv;
        base_gravada += base;
        igv_sunat += artIgv;
      } else {
        subtotal += importe;
        igv += importe * 0.18;
        base_gravada += importe;
        igv_sunat += importe * 0.18;
      }
    } else {
      subtotal += importe;
      base_no_gravada += importe;
    }
  });

  return {
    subtotal,
    igv,
    total: subtotal + igv,
    base_gravada: parseFloat(base_gravada.toFixed(2)),
    igv_sunat: parseFloat(igv_sunat.toFixed(2)),
    base_no_gravada: parseFloat(base_no_gravada.toFixed(2))
  };
};

export const generatePDFAndPrint = (factura, proveedores, monedas) => {
  const moneda = monedas.find(m => m.id === factura.moneda_id);
  const fmt = (v) => formatCurrency(v, moneda?.simbolo || 'S/');
  const pdfContent = `
    <html>
    <head>
      <title>Factura-${factura.numero}</title>
      <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        html, body { font-family: 'Inter', sans-serif; padding: 40px; color: #1e293b; background-color: #ffffff !important; color-scheme: light; -webkit-print-color-adjust: exact; }
        @media print { body { background-color: #ffffff !important; } }
        .header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 2px solid #1B4D3E; }
        .doc-title { font-size: 1.5rem; font-weight: 700; color: #1B4D3E; }
        .doc-number { font-family: 'JetBrains Mono', monospace; font-size: 1.125rem; font-weight: 600; margin-top: 4px; }
        .doc-date { font-size: 0.875rem; color: #64748b; margin-top: 4px; }
        .section { margin-bottom: 24px; }
        .section-title { font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b; margin-bottom: 8px; }
        .info-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
        .info-item label { font-size: 0.75rem; color: #64748b; display: block; }
        .info-item p { font-size: 0.9375rem; font-weight: 500; }
        table { width: 100%; border-collapse: collapse; margin-top: 16px; }
        th { background: #f1f5f9; padding: 10px 12px; text-align: left; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em; color: #64748b; border-bottom: 2px solid #e2e8f0; }
        td { padding: 10px 12px; border-bottom: 1px solid #e2e8f0; font-size: 0.875rem; }
        .text-right { text-align: right; }
        .currency { font-family: 'JetBrains Mono', monospace; font-weight: 500; }
        .totals { margin-top: 24px; display: flex; justify-content: flex-end; }
        .totals-box { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px 24px; min-width: 280px; }
        .totals-row { display: flex; justify-content: space-between; padding: 6px 0; font-size: 0.9375rem; }
        .totals-row.total { border-top: 2px solid #1B4D3E; margin-top: 8px; padding-top: 12px; font-weight: 700; font-size: 1.125rem; }
        .badge { display: inline-block; padding: 0.25rem 0.75rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
        .badge-pendiente { background: #fef3c7; color: #92400e; }
        .badge-parcial { background: #dbeafe; color: #1d4ed8; }
        .badge-pagado { background: #dcfce7; color: #15803d; }
        .footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid #e2e8f0; text-align: center; color: #64748b; font-size: 0.75rem; }
      </style>
    </head>
    <body>
      <div class="header">
        <div>
          <div class="doc-title">FACTURA DE PROVEEDOR</div>
          <div class="doc-number">${factura.tipo_documento?.toUpperCase() || 'FAC'} ${factura.numero}</div>
        </div>
        <div style="text-align: right;">
          <div class="doc-date">Emision: ${formatDate(factura.fecha_factura)}</div>
          <div class="doc-date">Vencimiento: ${formatDate(factura.fecha_vencimiento)}</div>
          <span class="badge badge-${factura.estado}">${factura.estado?.toUpperCase()}</span>
        </div>
      </div>
      <div class="section">
        <div class="section-title">Datos del Proveedor</div>
        <div class="info-grid">
          <div class="info-item"><label>Proveedor</label><p>${factura.proveedor_nombre || factura.beneficiario_nombre || '-'}</p></div>
          <div class="info-item"><label>Terminos</label><p>${factura.terminos_dias || 0} dias</p></div>
          <div class="info-item"><label>Moneda</label><p>${factura.moneda_codigo || moneda?.codigo || 'PEN'}</p></div>
        </div>
      </div>
      <div class="section">
        <div class="section-title">Detalle</div>
        <table>
          <thead><tr><th>#</th><th>Categoria</th><th>Descripcion</th><th class="text-right">Importe</th></tr></thead>
          <tbody>
            ${(factura.lineas || []).map((linea, i) => `
            <tr>
              <td>${i + 1}</td>
              <td>${linea.categoria_padre_nombre ? `${linea.categoria_padre_nombre} > ${linea.categoria_nombre}` : (linea.categoria_nombre || '-')}</td>
              <td>${linea.descripcion || '-'}</td>
              <td class="text-right currency">${fmt(linea.importe)}</td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
      <div class="totals">
        <div class="totals-box">
          <div class="totals-row"><span>Subtotal:</span><span class="currency">${fmt(factura.subtotal)}</span></div>
          <div class="totals-row"><span>IGV (18%):</span><span class="currency">${fmt(factura.igv)}</span></div>
          <div class="totals-row total"><span>TOTAL:</span><span class="currency">${fmt(factura.total)}</span></div>
          ${factura.saldo_pendiente !== factura.total ? `
          <div class="totals-row" style="color: #dc2626;"><span>Saldo Pendiente:</span><span class="currency">${fmt(factura.saldo_pendiente)}</span></div>` : ''}
        </div>
      </div>
      ${factura.notas ? `<div class="section" style="margin-top: 24px;"><div class="section-title">Observaciones</div><p style="font-size: 0.875rem; color: #64748b;">${factura.notas}</p></div>` : ''}
      <div class="footer"><p>Documento generado el ${new Date().toLocaleDateString('es-PE')} | Finanzas 4.0</p></div>
    </body>
    </html>
  `;
  const printWindow = window.open('', '_blank');
  printWindow.document.write(pdfContent);
  printWindow.document.close();
  printWindow.focus();
  printWindow.onload = () => printWindow.print();
};
