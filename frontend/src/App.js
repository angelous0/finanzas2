import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Toaster } from 'sonner';
import { Menu } from 'lucide-react';
import './App.css';

// Context
import { EmpresaProvider, useEmpresa } from './context/EmpresaContext';
import { ThemeProvider } from './context/ThemeContext';

// Components
import Sidebar from './components/Sidebar';
import TopBar from './components/TopBar';

// === CORE Pages ===
import Dashboard from './pages/Dashboard';
import VentasPOS from './pages/VentasPOS';
import CxC from './pages/CxC';
import Gastos from './pages/Gastos';
import ProrrateoGastos from './pages/ProrrateoGastos';
import FacturasProveedor from './pages/FacturasProveedor';
import CxP from './pages/CxP';
import Tesoreria from './pages/Tesoreria';
import CuentasBancarias from './pages/CuentasBancarias';
import Pagos from './pages/Pagos';
import Proveedores from './pages/Proveedores';
import LibroAnalitico from './pages/LibroAnalitico';
import ReportesFinancieros from './pages/ReportesFinancieros';
import ValorizacionInventario from './pages/ValorizacionInventario';
import CategoriasGasto from './pages/CategoriasGasto';
import LineasNegocio from './pages/LineasNegocio';
import CentrosCosto from './pages/CentrosCosto';
import Marcas from './pages/Marcas';
import Empresas from './pages/Empresas';

// === REVISAR Pages (pendiente decisión Fase 2) ===
import OrdenesCompra from './pages/OrdenesCompra';
import Letras from './pages/Letras';
import ConciliacionBancaria from './pages/ConciliacionBancaria';
import { HistorialConciliaciones } from './pages/HistorialConciliaciones';

// === Planilla === eliminado en [planilla-reset], se rehace desde cero

// === Activos Fijos ===
import ActivosFijos from './pages/ActivosFijos';

// === Unidades Internas de Producción ===
import ProduccionInterna from './pages/ProduccionInterna';
import KardexCuentaInterna from './pages/KardexCuentaInterna';
import PnLUnidadInterna from './pages/PnLUnidadInterna';

function EmpresaGuard({ children }) {
  const { empresas, empresaActual, loading, reloadEmpresas } = useEmpresa();
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ nombre: '', ruc: '' });

  if (loading) {
    return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>Cargando...</div>;
  }

  if (!empresaActual && empresas.length === 0) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', background: 'var(--bg)' }}>
        <div style={{ textAlign: 'center', maxWidth: 420, padding: '2.5rem', background: 'var(--card)', borderRadius: '1rem', boxShadow: '0 4px 24px rgba(0,0,0,0.08)' }}>
          <div style={{ width: 64, height: 64, borderRadius: '50%', background: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.5rem', fontSize: '1.5rem', fontWeight: 700, color: '#fff' }}>F4</div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.5rem' }}>Bienvenido a Finanzas 4.0</h1>
          <p style={{ color: 'var(--muted)', marginBottom: '2rem' }}>Para comenzar, crea tu primera empresa</p>
          
          {!showCreate ? (
            <button className="btn btn-primary" style={{ width: '100%', padding: '0.75rem' }} onClick={() => setShowCreate(true)} data-testid="crear-primera-empresa-btn">
              Crear mi empresa
            </button>
          ) : (
            <form onSubmit={async (e) => {
              e.preventDefault();
              if (creating || !form.nombre) return;
              setCreating(true);
              try {
                const { createEmpresa } = await import('./services/api');
                await createEmpresa(form);
                await reloadEmpresas();
              } catch (err) {
                console.error(err);
              } finally {
                setCreating(false);
              }
            }}>
              <div style={{ textAlign: 'left', marginBottom: '1rem' }}>
                <label className="form-label required">Nombre de la empresa</label>
                <input className="form-input" required value={form.nombre} onChange={e => setForm(p => ({ ...p, nombre: e.target.value }))} placeholder="Mi Empresa S.A.C." data-testid="empresa-nombre-input" />
              </div>
              <div style={{ textAlign: 'left', marginBottom: '1.5rem' }}>
                <label className="form-label">RUC</label>
                <input className="form-input" value={form.ruc} onChange={e => setForm(p => ({ ...p, ruc: e.target.value }))} placeholder="20123456789" />
              </div>
              <button type="submit" className="btn btn-primary" style={{ width: '100%', padding: '0.75rem' }} disabled={creating} data-testid="submit-primera-empresa-btn">
                {creating ? 'Creando...' : 'Crear empresa'}
              </button>
            </form>
          )}
        </div>
      </div>
    );
  }

  return children;
}

function AppRoutes() {
  const { empresaActual } = useEmpresa();
  return (
    <div key={empresaActual?.id}>
      <Routes>
        {/* === CORE === */}
        <Route path="/" element={<Dashboard />} />
        <Route path="/ventas-pos" element={<VentasPOS />} />
        <Route path="/cxc" element={<CxC />} />
        <Route path="/gastos" element={<Gastos />} />
        <Route path="/proveedores" element={<Proveedores />} />
        <Route path="/prorrateo" element={<ProrrateoGastos />} />
        <Route path="/facturas-proveedor" element={<FacturasProveedor />} />
        <Route path="/cxp" element={<CxP />} />
        <Route path="/tesoreria" element={<Tesoreria />} />
        <Route path="/cuentas-bancarias" element={<CuentasBancarias />} />
        <Route path="/pagos" element={<Pagos />} />
        <Route path="/reportes-financieros" element={<ReportesFinancieros />} />
        <Route path="/libro-analitico" element={<LibroAnalitico />} />
        <Route path="/valorizacion-inventario" element={<ValorizacionInventario />} />
        <Route path="/lineas-negocio" element={<LineasNegocio />} />
        <Route path="/marcas" element={<Marcas />} />
        <Route path="/centros-costo" element={<CentrosCosto />} />
        <Route path="/categorias-gasto" element={<CategoriasGasto />} />
        <Route path="/empresas" element={<Empresas />} />

        {/* === REVISAR — pendiente decisión Fase 2 === */}
        <Route path="/ordenes-compra" element={<OrdenesCompra />} />
        <Route path="/letras" element={<Letras />} />
        <Route path="/conciliacion" element={<ConciliacionBancaria />} />
        <Route path="/historial-conciliaciones" element={<HistorialConciliaciones />} />
        {/* Hub unificado (tabs) + rutas individuales legacy que redirigen al hub */}
        <Route path="/produccion-interna" element={<ProduccionInterna />} />
        <Route path="/produccion-interna/:tab" element={<ProduccionInterna />} />
        <Route path="/unidades-internas" element={<ProduccionInterna />} />
        <Route path="/gastos-unidad-interna" element={<ProduccionInterna />} />
        <Route path="/cargos-internos" element={<ProduccionInterna />} />
        <Route path="/reporte-unidades-internas" element={<ProduccionInterna />} />
        <Route path="/cuentas-internas" element={<ProduccionInterna />} />
        <Route path="/movimientos-produccion" element={<ProduccionInterna />} />
        {/* Detalle: kardex y P&L siguen como páginas independientes */}
        <Route path="/cuentas-internas/:id/kardex" element={<KardexCuentaInterna />} />
        <Route path="/reporte-pnl-unidad/:id" element={<PnLUnidadInterna />} />
        {/* /planilla y /trabajadores: eliminados en [planilla-reset] */}
        <Route path="/activos-fijos" element={<ActivosFijos />} />
      </Routes>
    </div>
  );
}

function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth > 768) {
        setMobileMenuOpen(false);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <Router>
      <ThemeProvider>
      <EmpresaProvider>
        <EmpresaGuard>
        <div className="flex h-screen bg-background overflow-hidden">
          <Sidebar
            collapsed={sidebarCollapsed}
            setCollapsed={setSidebarCollapsed}
            mobileOpen={mobileMenuOpen}
            setMobileOpen={setMobileMenuOpen}
          />

          <div className="flex-1 flex flex-col min-h-0 min-w-0 overflow-hidden">
            <TopBar />

            {/* Mobile menu button */}
            <button
              className="fixed top-4 left-4 z-50 flex md:hidden h-10 w-10 items-center justify-center rounded-lg bg-background border border-border shadow-md"
              onClick={() => setMobileMenuOpen(true)}
              data-testid="mobile-menu-btn"
            >
              <Menu size={20} />
            </button>

            <main className="flex-1 overflow-y-auto overflow-x-hidden p-4 md:p-6">
              <AppRoutes />
            </main>
          </div>
        </div>
        <Toaster position="top-right" richColors />
        </EmpresaGuard>
      </EmpresaProvider>
      </ThemeProvider>
    </Router>
  );
}

export default App;
