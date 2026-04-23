import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Factory, ArrowRightLeft, Wallet,
  FileText, BarChart3,
} from 'lucide-react';

// Reutilizamos las páginas existentes como componentes internos
import CuentasInternas from './CuentasInternas';
import UnidadesInternas from './UnidadesInternas';
import CargosInternos from './CargosInternos';
import GastosUnidadInterna from './GastosUnidadInterna';
import MovimientosProduccion from './MovimientosProduccion';
import ReporteUnidadesInternas from './ReporteUnidadesInternas';

const TABS = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, component: CuentasInternas,
    desc: 'Saldos por unidad, CxC virtual y potencial' },
  { id: 'unidades', label: 'Unidades', icon: Factory, component: UnidadesInternas,
    desc: 'Catálogo de unidades y personas de producción' },
  { id: 'cargos', label: 'Cargos Internos', icon: ArrowRightLeft, component: CargosInternos,
    desc: 'Ingresos por servicios internos' },
  { id: 'gastos', label: 'Gastos', icon: Wallet, component: GastosUnidadInterna,
    desc: 'Gastos por unidad (planilla, destajo)' },
  { id: 'movimientos', label: 'Movimientos', icon: FileText, component: MovimientosProduccion,
    desc: 'Movimientos físicos desde producción' },
  { id: 'reporte', label: 'Reporte Gerencial', icon: BarChart3, component: ReporteUnidadesInternas,
    desc: 'Resumen agregado de todas las unidades' },
];

// Mapeo de rutas legacy → id de tab, para mantener retrocompatibilidad
const LEGACY_ROUTE_TO_TAB = {
  '/cuentas-internas': 'dashboard',
  '/unidades-internas': 'unidades',
  '/cargos-internos': 'cargos',
  '/gastos-unidad-interna': 'gastos',
  '/movimientos-produccion': 'movimientos',
  '/reporte-unidades-internas': 'reporte',
};

function resolveTab(pathname) {
  // 1) Ruta nueva: /produccion-interna/:tab
  const match = pathname.match(/^\/produccion-interna\/?(.*)$/);
  if (match) {
    const slug = match[1];
    if (TABS.find(t => t.id === slug)) return slug;
    return 'dashboard';
  }
  // 2) Rutas legacy
  if (LEGACY_ROUTE_TO_TAB[pathname]) return LEGACY_ROUTE_TO_TAB[pathname];
  return 'dashboard';
}

export default function ProduccionInterna() {
  const location = useLocation();
  const navigate = useNavigate();
  const [tab, setTab] = useState(() => resolveTab(location.pathname));

  useEffect(() => {
    setTab(resolveTab(location.pathname));
  }, [location.pathname]);

  const changeTab = (id) => {
    setTab(id);
    navigate(`/produccion-interna/${id}`, { replace: false });
  };

  const ActiveComponent = TABS.find(t => t.id === tab)?.component || CuentasInternas;
  const activeMeta = TABS.find(t => t.id === tab);

  return (
    <div data-testid="produccion-interna-page">
      {/* Header con tabs */}
      <div style={{
        padding: '1rem 1.5rem 0',
        borderBottom: '1px solid var(--border)',
        background: 'var(--card-bg)',
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <div style={{ marginBottom: '0.5rem' }}>
          <h1 style={{ fontSize: '1.15rem', fontWeight: 700, margin: 0, color: 'var(--text-heading)' }}>
            Producción Interna
          </h1>
          <p style={{ fontSize: '0.75rem', color: 'var(--muted)', margin: '0.15rem 0 0' }}>
            {activeMeta?.desc}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.25rem', overflowX: 'auto' }}>
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => changeTab(t.id)}
              data-testid={`pi-tab-${t.id}`}
              style={{
                padding: '0.5rem 0.9rem',
                fontSize: '0.8125rem',
                fontWeight: tab === t.id ? 700 : 500,
                color: tab === t.id ? 'var(--text-heading)' : 'var(--muted)',
                background: 'none',
                border: 'none',
                borderBottom: tab === t.id ? '2px solid #f59e0b' : '2px solid transparent',
                marginBottom: '-1px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.375rem',
                transition: 'all 0.15s',
                whiteSpace: 'nowrap',
              }}
            >
              <t.icon size={14} />
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Contenido: la página seleccionada renderizada como componente */}
      <div key={tab}>
        <ActiveComponent />
      </div>
    </div>
  );
}
