/**
 * FacturasProveedor — Orquestador.
 *
 * La lógica está distribuida en sub-módulos:
 *   helpers.js           → Formatters, cálculos, PDF
 *   FacturasTable.jsx    → Tabla con filtros y acciones
 *   FacturaFormModal.jsx → Modal crear/editar factura
 *   PagoModal.jsx        → Modal registrar pago
 *   LetrasModal.jsx      → Modal canjear por letras
 *   VerPagosModal.jsx    → Modal ver historial de pagos
 *   VerLetrasModal.jsx   → Modal ver letras vinculadas
 *   ExportModal.jsx      → Modal exportar CompraAPP
 *   ProveedorModal.jsx   → Modal crear proveedor
 */
import React, { useState, useEffect } from 'react';
import {
  getFacturasProveedor, deleteFacturaProveedor,
  getProveedores, getMonedas, getCategorias, getLineasNegocio, getCentrosCosto,
  getInventario, getModelosCortes, getCuentasFinancieras,
  getServiciosProduccion, getValorizacionInventario, getUnidadesInternas
} from '../services/api';
import { useEmpresa } from '../context/EmpresaContext';
import { Plus, FileSpreadsheet } from 'lucide-react';
import { toast } from 'sonner';

import { formatCurrency, generatePDFAndPrint } from './facturasProveedor/helpers';
import FacturasTable from './facturasProveedor/FacturasTable';
import FacturaFormModal from './facturasProveedor/FacturaFormModal';
import PagoModal from './facturasProveedor/PagoModal';
import LetrasModal from './facturasProveedor/LetrasModal';
import VerPagosModal from './facturasProveedor/VerPagosModal';
import VerLetrasModal from './facturasProveedor/VerLetrasModal';
import ExportModal from './facturasProveedor/ExportModal';
import ProveedorModal from './facturasProveedor/ProveedorModal';
import VincularIngresosModal from './facturasProveedor/VincularIngresosModal';

export const FacturasProveedor = () => {
  const { empresaActual } = useEmpresa();

  // Data
  const [facturas, setFacturas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [proveedores, setProveedores] = useState([]);
  const [monedas, setMonedas] = useState([]);
  const [categorias, setCategorias] = useState([]);
  const [lineasNegocio, setLineasNegocio] = useState([]);
  const [centrosCosto, setCentrosCosto] = useState([]);
  const [inventario, setInventario] = useState([]);
  const [modelosCortes, setModelosCortes] = useState([]);
  const [cuentasFinancieras, setCuentasFinancieras] = useState([]);
  const [serviciosProduccion, setServiciosProduccion] = useState([]);
  const [unidadesInternas, setUnidadesInternas] = useState([]);
  const [valorizacionMap, setValorizacionMap] = useState({});

  // Filters
  const [filtroEstado, setFiltroEstado] = useState('');
  const [filtroNumero, setFiltroNumero] = useState('');
  const [filtroProveedorId, setFiltroProveedorId] = useState('');
  const [filtroFecha, setFiltroFecha] = useState('');

  // Modal states
  const [showFormModal, setShowFormModal] = useState(false);
  const [editingFactura, setEditingFactura] = useState(null);
  const [viewOnlyMode, setViewOnlyMode] = useState(false);
  const [showPagoModal, setShowPagoModal] = useState(false);
  const [facturaParaPago, setFacturaParaPago] = useState(null);
  const [showLetrasModal, setShowLetrasModal] = useState(false);
  const [facturaParaLetras, setFacturaParaLetras] = useState(null);
  const [showVerPagosModal, setShowVerPagosModal] = useState(false);
  const [facturaParaVerPagos, setFacturaParaVerPagos] = useState(null);
  const [showVerLetrasModal, setShowVerLetrasModal] = useState(false);
  const [facturaParaVerLetras, setFacturaParaVerLetras] = useState(null);
  const [showExportModal, setShowExportModal] = useState(false);
  const [showProveedorModal, setShowProveedorModal] = useState(false);
  const [showVincularModal, setShowVincularModal] = useState(false);
  const [facturaParaVincular, setFacturaParaVincular] = useState(null);

  useEffect(() => { loadData(); }, [filtroEstado, filtroProveedorId, filtroFecha, empresaActual]);

  const loadData = async () => {
    try {
      setLoading(true);
      const params = {};
      if (filtroEstado) params.estado = filtroEstado;
      if (filtroProveedorId) params.proveedor_id = filtroProveedorId;
      if (filtroFecha) params.fecha_desde = filtroFecha;

      const [facturasRes, proveedoresRes, monedasRes, categoriasRes, lineasRes, centrosRes, inventarioRes, modelosRes, cuentasRes, serviciosRes, unidadesRes] = await Promise.all([
        getFacturasProveedor(params),
        getProveedores(),
        getMonedas(),
        getCategorias('egreso'),
        getLineasNegocio(),
        getCentrosCosto(),
        getInventario(),
        getModelosCortes(),
        getCuentasFinancieras(),
        getServiciosProduccion(),
        getUnidadesInternas()
      ]);

      setFacturas(facturasRes.data);
      setProveedores(proveedoresRes.data);
      setMonedas(monedasRes.data);
      setCategorias(categoriasRes.data);
      setLineasNegocio(lineasRes.data);
      setCentrosCosto(centrosRes.data);
      setInventario(inventarioRes.data.filter(a => a.categoria !== 'PT'));
      setModelosCortes(modelosRes.data);
      setCuentasFinancieras(cuentasRes.data);
      setServiciosProduccion(serviciosRes.data);
      setUnidadesInternas(unidadesRes.data);

      // Fetch FIFO valuation
      try {
        const valRes = await getValorizacionInventario();
        const map = {};
        (valRes.data?.data || []).forEach(item => { map[item.id] = item; });
        setValorizacionMap(map);
      } catch (e) { console.warn('Could not load FIFO data:', e); }
    } catch (error) {
      console.error('Error loading data:', error);
      toast.error('Error al cargar datos');
    } finally {
      setLoading(false);
    }
  };

  // Handlers
  const handleDelete = async (id) => {
    if (!window.confirm('Esta seguro de eliminar esta factura?')) return;
    try {
      await deleteFacturaProveedor(id);
      toast.success('Factura eliminada');
      loadData();
    } catch (error) {
      console.error('Error deleting factura:', error);
      toast.error(error.response?.data?.detail || 'Error al eliminar factura');
    }
  };

  const handleEdit = (factura) => {
    if (factura.estado === 'anulada') {
      toast.error('No se puede editar una factura anulada');
      return;
    }
    setEditingFactura(factura);
    setViewOnlyMode(false);
    setShowFormModal(true);
  };

  const handleView = (factura) => {
    setEditingFactura(factura);
    setViewOnlyMode(true);
    setShowFormModal(true);
  };

  const handleNewFactura = () => { setEditingFactura(null); setViewOnlyMode(false); setShowFormModal(true); };

  // Calculate totals for header
  const facturasFiltradas = filtroNumero
    ? facturas.filter(f => f.numero?.toLowerCase().includes(filtroNumero.toLowerCase()))
    : facturas;
  const totalPendiente = facturasFiltradas.filter(f => f.estado === 'pendiente' || f.estado === 'parcial')
    .reduce((sum, f) => sum + parseFloat(f.saldo_pendiente || 0), 0);

  return (
    <div data-testid="facturas-proveedor-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Facturas de Proveedor</h1>
          <p className="page-subtitle">Pendiente: {formatCurrency(totalPendiente)}</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-outline" onClick={() => setShowExportModal(true)} data-testid="export-compraapp-btn" title="Exportar CompraAPP">
            <FileSpreadsheet size={18} /> CompraAPP
          </button>
          <button className="btn btn-primary" onClick={handleNewFactura} data-testid="nueva-factura-btn">
            <Plus size={18} /> Nueva Factura
          </button>
        </div>
      </div>

      <div className="page-content">
        <FacturasTable
          facturas={facturas}
          loading={loading}
          proveedores={proveedores}
          filtroNumero={filtroNumero} setFiltroNumero={setFiltroNumero}
          filtroProveedorId={filtroProveedorId} setFiltroProveedorId={setFiltroProveedorId}
          filtroFecha={filtroFecha} setFiltroFecha={setFiltroFecha}
          filtroEstado={filtroEstado} setFiltroEstado={setFiltroEstado}
          onOpenPago={(f) => { setFacturaParaPago(f); setShowPagoModal(true); }}
          onOpenLetras={(f) => { setFacturaParaLetras(f); setShowLetrasModal(true); }}
          onVerPagos={(f) => { setFacturaParaVerPagos(f); setShowVerPagosModal(true); }}
          onVerLetras={(f) => { setFacturaParaVerLetras(f); setShowVerLetrasModal(true); }}
          onView={handleView}
          onEdit={handleEdit}
          onDelete={handleDelete}
          onDownloadPDF={(f) => generatePDFAndPrint(f, proveedores, monedas)}
          onNewFactura={handleNewFactura}
          onVincularIngresos={(f) => { setFacturaParaVincular(f); setShowVincularModal(true); }}
        />
      </div>

      {/* Modals */}
      <FacturaFormModal
        show={showFormModal}
        editingFactura={editingFactura}
        readOnly={viewOnlyMode}
        proveedores={proveedores}
        monedas={monedas}
        categorias={categorias}
        lineasNegocio={lineasNegocio}
        centrosCosto={centrosCosto}
        inventario={inventario}
        modelosCortes={modelosCortes}
        serviciosProduccion={serviciosProduccion}
        unidadesInternas={unidadesInternas}
        valorizacionMap={valorizacionMap}
        onClose={() => { setShowFormModal(false); setEditingFactura(null); setViewOnlyMode(false); }}
        onSaved={loadData}
        onProveedorCreated={(newProv) => setProveedores(prev => [...prev, newProv])}
        onOpenPago={(f) => { setFacturaParaPago(f); setShowPagoModal(true); }}
        onDownloadPDF={(f) => generatePDFAndPrint(f, proveedores, monedas)}
        onVincularIngresos={(f) => { setFacturaParaVincular(f); setShowVincularModal(true); }}
        onVerPagos={(f) => { setFacturaParaVerPagos(f); setShowVerPagosModal(true); }}
        onOpenLetras={(f) => { setFacturaParaLetras(f); setShowLetrasModal(true); }}
        onVerLetras={(f) => { setFacturaParaVerLetras(f); setShowVerLetrasModal(true); }}
      />

      <PagoModal
        show={showPagoModal}
        factura={facturaParaPago}
        cuentasFinancieras={cuentasFinancieras}
        onClose={() => setShowPagoModal(false)}
        onPagoRegistrado={() => { setShowPagoModal(false); loadData(); }}
      />

      <LetrasModal
        show={showLetrasModal}
        factura={facturaParaLetras}
        cuentasFinancieras={cuentasFinancieras}
        onClose={() => setShowLetrasModal(false)}
        onLetrasCreadas={() => { setShowLetrasModal(false); loadData(); }}
      />

      <VerPagosModal
        show={showVerPagosModal}
        factura={facturaParaVerPagos}
        onClose={() => setShowVerPagosModal(false)}
        onDataChanged={loadData}
      />

      <VerLetrasModal
        show={showVerLetrasModal}
        factura={facturaParaVerLetras}
        onClose={() => setShowVerLetrasModal(false)}
        onDataChanged={loadData}
      />

      <ExportModal show={showExportModal} onClose={() => setShowExportModal(false)} />

      <ProveedorModal
        show={showProveedorModal}
        onClose={() => setShowProveedorModal(false)}
        onCreated={(newProv) => { setProveedores(prev => [...prev, newProv]); setShowProveedorModal(false); }}
      />

      <VincularIngresosModal
        show={showVincularModal}
        factura={facturaParaVincular}
        onClose={() => { setShowVincularModal(false); setFacturaParaVincular(null); }}
        onDataChanged={loadData}
      />
    </div>
  );
};

export default FacturasProveedor;
