import React from 'react';
import { useLocation } from 'react-router-dom';
import { Sun, Moon, User } from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

const PAGE_TITLES = {
  '/': 'Dashboard',
  '/ventas-pos': 'Ventas POS',
  '/cxc': 'Cuentas por Cobrar',
  '/gastos': 'Gastos',
  '/prorrateo': 'Prorrateo de Gastos',
  '/facturas-proveedor': 'Facturas de Proveedor',
  '/ordenes-compra': 'Ordenes de Compra',
  '/cxp': 'Cuentas por Pagar',
  '/letras': 'Letras',
  '/tesoreria': 'Tesoreria',
  '/cuentas-bancarias': 'Cuentas Bancarias',
  '/pagos': 'Movimientos / Pagos',
  '/conciliacion': 'Conciliacion Bancaria',
  '/historial-conciliaciones': 'Historial de Conciliaciones',
  '/reportes-financieros': 'Reportes Financieros',
  '/libro-analitico': 'Libro Analitico',
  '/valorizacion-inventario': 'Valorizacion de Inventario',
  '/trabajadores': 'Trabajadores',
  '/ajustes-planilla': 'Ajustes de Planilla',
  '/adelantos': 'Adelantos a Trabajadores',
  '/planillas-quincena': 'Planillas Quincenales',
  '/produccion-interna': 'Producción Interna',
  '/unidades-internas': 'Producción Interna',
  '/cargos-internos': 'Producción Interna',
  '/gastos-unidad-interna': 'Producción Interna',
  '/reporte-unidades-internas': 'Producción Interna',
  '/cuentas-internas': 'Producción Interna',
  '/movimientos-produccion': 'Producción Interna',
  '/lineas-negocio': 'Lineas de Negocio',
  '/marcas': 'Marcas',
  '/centros-costo': 'Centros de Costo',
  '/categorias-gasto': 'Categorias de Gasto',
  '/proveedores': 'Proveedores',
  '/empresas': 'Empresas',
  '/activos-fijos': 'Activos Fijos',
};

export default function TopBar() {
  const { theme, toggleTheme } = useTheme();
  const location = useLocation();
  const pageTitle = PAGE_TITLES[location.pathname] || '';

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-background/80 backdrop-blur-md px-4 md:px-6">
      {/* Page title */}
      <h1 className="text-lg font-semibold text-foreground tracking-tight hidden md:block">
        {pageTitle}
      </h1>

      {/* Right side actions */}
      <div className="ml-auto flex items-center gap-2">
        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          className="flex h-9 w-9 items-center justify-center rounded-lg hover:bg-muted transition-colors text-muted-foreground"
          title={theme === 'dark' ? 'Modo claro' : 'Modo oscuro'}
          data-testid="theme-toggle"
        >
          {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
        </button>

        {/* User avatar placeholder */}
        <div
          className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted text-muted-foreground cursor-pointer hover:bg-muted/80 transition-colors"
          title="Usuario"
          data-testid="user-avatar"
        >
          <User size={18} />
        </div>
      </div>
    </header>
  );
}
