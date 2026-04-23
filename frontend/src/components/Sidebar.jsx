import React, { useState, useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, ShoppingCart, Receipt, CreditCard,
  Building2, Users, Wallet,
  ChevronDown, ChevronLeft, DollarSign, Landmark, Clock,
  Tags, GitBranch, Target, X,
  Tag, Package, FileSpreadsheet,
  Vault, Layers, Link2, History, BookOpen, PieChart,
  Factory, ArrowRightLeft, FileText, BarChart3, ClipboardList,
  TrendingUp, Menu, ChevronsLeft, ChevronsRight, Settings
} from 'lucide-react';
import { useEmpresa } from '../context/EmpresaContext';

const navSections = [
  {
    key: 'principal',
    title: 'Principal',
    dot: 'bg-emerald-500',
    items: [
      { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
    ]
  },
  {
    key: 'ventas',
    title: 'Ventas',
    dot: 'bg-blue-500',
    items: [
      { icon: ShoppingCart, label: 'Ventas POS', path: '/ventas-pos' },
      { icon: CreditCard, label: 'CxC', path: '/cxc' },
    ]
  },
  {
    key: 'egresos',
    title: 'Egresos',
    dot: 'bg-red-500',
    items: [
      { icon: Wallet, label: 'Gastos', path: '/gastos' },
      { icon: Layers, label: 'Prorrateo', path: '/prorrateo' },
      { icon: Receipt, label: 'Factura Proveedor', path: '/facturas-proveedor' },
      { icon: ShoppingCart, label: 'Ordenes de Compra', path: '/ordenes-compra' },
      { icon: Clock, label: 'CxP', path: '/cxp' },
      { icon: FileSpreadsheet, label: 'Letras', path: '/letras' },
    ]
  },
  {
    key: 'tesoreria',
    title: 'Tesoreria',
    dot: 'bg-emerald-500',
    items: [
      { icon: Vault, label: 'Tesoreria', path: '/tesoreria' },
      { icon: Landmark, label: 'Cuentas Bancarias', path: '/cuentas-bancarias' },
      { icon: DollarSign, label: 'Movimientos/Pagos', path: '/pagos' },
      { icon: Link2, label: 'Conciliacion Bancaria', path: '/conciliacion' },
      { icon: History, label: 'Historial Conciliaciones', path: '/historial-conciliaciones' },
    ]
  },
  {
    key: 'reportes',
    title: 'Reportes',
    dot: 'bg-purple-500',
    items: [
      { icon: PieChart, label: 'Reportes Financieros', path: '/reportes-financieros' },
      { icon: BookOpen, label: 'Libro Analitico', path: '/libro-analitico' },
      { icon: Package, label: 'Valorizacion Inventario', path: '/valorizacion-inventario' },
    ]
  },
  {
    key: 'produccion-interna',
    title: 'Produccion Interna',
    dot: 'bg-amber-500',
    items: [
      { icon: Factory, label: 'Producción Interna', path: '/produccion-interna' },
    ]
  },
  {
    key: 'planilla',
    title: 'Planilla',
    dot: 'bg-cyan-500',
    items: [
      { icon: Users, label: 'Trabajadores', path: '/trabajadores' },
      { icon: FileSpreadsheet, label: 'Planillas Quincena', path: '/planillas-quincena' },
      { icon: Clock, label: 'Adelantos', path: '/adelantos' },
      { icon: Settings, label: 'Ajustes Planilla', path: '/ajustes-planilla' },
    ]
  },
  {
    key: 'activos',
    title: 'Activos',
    dot: 'bg-indigo-500',
    items: [
      { icon: Package, label: 'Activos Fijos', path: '/activos-fijos' },
    ]
  },
  {
    key: 'catalogos',
    title: 'Catalogos',
    dot: 'bg-gray-400',
    items: [
      { icon: GitBranch, label: 'Lineas de Negocio', path: '/lineas-negocio' },
      { icon: Tag, label: 'Marcas', path: '/marcas' },
      { icon: Target, label: 'Centros de Costo', path: '/centros-costo' },
      { icon: Tags, label: 'Categorias', path: '/categorias-gasto' },
      { icon: Users, label: 'Proveedores', path: '/proveedores' },
      { icon: Building2, label: 'Empresas', path: '/empresas' },
    ]
  },
];

function getInitials(name) {
  if (!name) return 'E';
  return name.split(/\s+/).map(w => w[0]).filter(Boolean).slice(0, 2).join('').toUpperCase();
}

export const Sidebar = ({ collapsed, setCollapsed, mobileOpen, setMobileOpen }) => {
  const location = useLocation();
  const { empresas, empresaActual, cambiarEmpresa } = useEmpresa();
  const [expandedSections, setExpandedSections] = useState(() => {
    try {
      const saved = localStorage.getItem('finanzas_sidebar_sections');
      return saved ? JSON.parse(saved) : navSections.reduce((acc, s) => ({ ...acc, [s.key]: true }), {});
    } catch {
      return navSections.reduce((acc, s) => ({ ...acc, [s.key]: true }), {});
    }
  });
  const [empresaDropdown, setEmpresaDropdown] = useState(false);

  useEffect(() => {
    localStorage.setItem('finanzas_sidebar_sections', JSON.stringify(expandedSections));
  }, [expandedSections]);

  const toggleSection = (key) => {
    setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const closeMobile = () => setMobileOpen && setMobileOpen(false);

  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 backdrop-blur-sm md:hidden"
          onClick={closeMobile}
        />
      )}

      <aside
        className={`
          fixed inset-y-0 left-0 z-40 flex flex-col
          border-r border-border bg-card
          transition-all duration-300 ease-in-out
          ${collapsed ? 'w-16' : 'w-60'}
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}
          md:translate-x-0 md:relative
        `}
        data-testid="sidebar"
      >
        {/* Logo header */}
        <div className="flex h-16 items-center justify-between border-b border-border px-3 flex-shrink-0">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-600 text-white font-bold text-sm flex-shrink-0 shadow-sm">
              F4
            </div>
            {!collapsed && (
              <span className="font-semibold text-foreground tracking-tight whitespace-nowrap text-sm">
                Finanzas 4.0
              </span>
            )}
          </div>
          <div className="flex items-center">
            <button
              className="hidden md:flex h-7 w-7 items-center justify-center rounded-md hover:bg-muted transition-colors text-muted-foreground"
              onClick={() => setCollapsed(!collapsed)}
              data-testid="sidebar-toggle"
            >
              {collapsed ? <ChevronsRight size={16} /> : <ChevronsLeft size={16} />}
            </button>
            <button
              className="flex md:hidden h-7 w-7 items-center justify-center rounded-md hover:bg-muted transition-colors text-muted-foreground"
              onClick={closeMobile}
              data-testid="mobile-close-btn"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Empresa selector */}
        {!collapsed && (
          <div className="px-3 py-2.5 border-b border-border">
            <div className="relative">
              <button
                className="w-full flex items-center gap-2.5 rounded-lg px-2.5 py-2 hover:bg-muted transition-colors text-left"
                onClick={() => setEmpresaDropdown(!empresaDropdown)}
                data-testid="empresa-selector-sidebar"
              >
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-600/10 text-emerald-600 font-semibold text-xs flex-shrink-0">
                  {getInitials(empresaActual?.nombre)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-foreground truncate">
                    {empresaActual?.nombre || 'Sin empresa'}
                  </div>
                  <div className="text-[0.6875rem] text-muted-foreground truncate">
                    {empresaActual?.ruc || 'Seleccionar empresa'}
                  </div>
                </div>
                <ChevronDown size={14} className={`text-muted-foreground transition-transform ${empresaDropdown ? 'rotate-180' : ''}`} />
              </button>

              {empresaDropdown && empresas.length > 1 && (
                <div className="absolute left-0 right-0 top-full mt-1 bg-popover border border-border rounded-lg shadow-lg z-50 py-1">
                  {empresas.map(emp => (
                    <button
                      key={emp.id}
                      className={`w-full flex items-center gap-2.5 px-3 py-2 text-sm transition-colors hover:bg-muted ${
                        emp.id === empresaActual?.id ? 'text-emerald-600 font-medium bg-emerald-600/5' : 'text-foreground'
                      }`}
                      onClick={() => { cambiarEmpresa(emp.id); setEmpresaDropdown(false); }}
                    >
                      <div className="flex h-6 w-6 items-center justify-center rounded bg-emerald-600/10 text-emerald-600 font-semibold text-[0.625rem] flex-shrink-0">
                        {getInitials(emp.nombre)}
                      </div>
                      <span className="truncate">{emp.nombre}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto overflow-x-hidden px-2.5 py-2 space-y-0.5 sidebar-scroll">
          {navSections.map((section) => (
            <div key={section.key}>
              {/* Section header */}
              {!collapsed ? (
                <button
                  className="w-full flex items-center justify-between px-2.5 py-1.5 mt-3 first:mt-1 mb-0.5 rounded-md hover:bg-muted/50 transition-colors group"
                  onClick={() => toggleSection(section.key)}
                >
                  <div className="flex items-center gap-2">
                    <div className={`w-1.5 h-1.5 rounded-full ${section.dot}`} />
                    <span className="text-[0.625rem] font-semibold uppercase tracking-[0.15em] text-muted-foreground/70">
                      {section.title}
                    </span>
                  </div>
                  <ChevronDown
                    size={12}
                    className={`text-muted-foreground/40 transition-transform duration-200 ${
                      expandedSections[section.key] ? '' : '-rotate-90'
                    }`}
                  />
                </button>
              ) : (
                <div className="flex justify-center my-2.5">
                  <div className={`w-1.5 h-1.5 rounded-full ${section.dot}`} />
                </div>
              )}

              {/* Section items */}
              <div
                className={`space-y-0.5 overflow-hidden transition-all duration-200 ease-in-out ${
                  collapsed
                    ? ''
                    : expandedSections[section.key]
                      ? 'max-h-[600px] opacity-100'
                      : 'max-h-0 opacity-0'
                }`}
              >
                {section.items.map((item) => (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    end={item.path === '/'}
                    className={({ isActive }) => {
                      return `sidebar-item flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-all duration-150
                        ${isActive
                          ? 'bg-emerald-600/10 text-emerald-600 font-medium shadow-sm'
                          : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                        }
                        ${collapsed ? 'justify-center px-0 py-2.5 mx-0.5' : ''}
                      `;
                    }}
                    title={collapsed ? item.label : undefined}
                    onClick={closeMobile}
                    data-testid={`nav-${item.path.replace('/', '') || 'dashboard'}`}
                  >
                    <item.icon className={`h-4 w-4 flex-shrink-0`} />
                    {!collapsed && <span className="truncate">{item.label}</span>}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* Collapsed empresa avatar */}
        {collapsed && (
          <div className="px-2 py-3 border-t border-border flex justify-center">
            <div
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-600/10 text-emerald-600 font-semibold text-xs cursor-pointer hover:bg-emerald-600/20 transition-colors"
              title={empresaActual?.nombre}
            >
              {getInitials(empresaActual?.nombre)}
            </div>
          </div>
        )}
      </aside>
    </>
  );
};

export default Sidebar;
