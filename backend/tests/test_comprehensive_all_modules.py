"""
Comprehensive Backend API Tests - ALL Modules
Iteration 17 - Testing all endpoints for the Finanzas 4.0 Peruvian Finance App

Modules tested:
- Health check
- Dashboard KPIs
- Empresas (companies)
- Maestros (Categorias, Centros Costo, Lineas Negocio, Monedas)
- Terceros, Proveedores, Clientes, Empleados
- Articulos, Inventario
- Ordenes de Compra
- Facturas Proveedor
- Gastos
- Pagos
- Letras
- Cuentas Financieras (Bank Accounts)
- Conciliacion Bancaria
- Planillas
- Adelantos
- Presupuestos
- Contabilidad (Cuentas Contables, Asientos, Config Contable, Periodos)
- CxC, CxP
- Reportes (Balance General, Estado Resultados, Flujo Caja)
- Ventas POS
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
EMPRESA_ID = 6  # Ambission Industries SAC - empresa with data

# Header for empresa-scoped endpoints
HEADERS = {'Content-Type': 'application/json'}


class TestHealthAndCore:
    """Health and core endpoint tests"""
    
    def test_health_check(self):
        """GET /api/health returns OK"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get('status') in ['ok', 'healthy']
        print(f"Health check: {data}")


class TestDashboard:
    """Dashboard KPIs tests"""
    
    def test_dashboard_kpis(self):
        """GET /api/dashboard/kpis returns dashboard data"""
        response = requests.get(f"{BASE_URL}/api/dashboard/kpis", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        # Should have KPI structure
        assert isinstance(data, dict)
        print(f"Dashboard KPIs keys: {list(data.keys())}")


class TestEmpresas:
    """Empresas (companies) tests"""
    
    def test_get_empresas(self):
        """GET /api/empresas returns list of companies"""
        response = requests.get(f"{BASE_URL}/api/empresas")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Empresas count: {len(data)}")
        # Check empresa 6 exists
        empresa_6 = next((e for e in data if e.get('id') == 6), None)
        if empresa_6:
            print(f"Empresa 6: {empresa_6.get('nombre')}")


class TestMaestros:
    """Maestros (master data) tests - Categorias, Centros Costo, Lineas Negocio, Monedas"""
    
    def test_get_categorias(self):
        """GET /api/categorias returns categories"""
        response = requests.get(f"{BASE_URL}/api/categorias", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Categorias count: {len(data)}")
    
    def test_get_centros_costo(self):
        """GET /api/centros-costo returns cost centers"""
        response = requests.get(f"{BASE_URL}/api/centros-costo", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Centros Costo count: {len(data)}")
    
    def test_get_lineas_negocio(self):
        """GET /api/lineas-negocio returns business lines"""
        response = requests.get(f"{BASE_URL}/api/lineas-negocio", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Lineas Negocio count: {len(data)}")
    
    def test_get_monedas(self):
        """GET /api/monedas returns currencies"""
        response = requests.get(f"{BASE_URL}/api/monedas")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Monedas count: {len(data)}")
        # Should have PEN and USD at minimum
        codigos = [m.get('codigo') for m in data]
        assert 'PEN' in codigos or len(data) > 0


class TestTerceros:
    """Terceros, Proveedores, Clientes, Empleados tests"""
    
    def test_get_terceros(self):
        """GET /api/terceros returns list of terceros"""
        response = requests.get(f"{BASE_URL}/api/terceros", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Terceros count: {len(data)}")
    
    def test_get_proveedores(self):
        """GET /api/proveedores returns list of proveedores"""
        response = requests.get(f"{BASE_URL}/api/proveedores", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Proveedores count: {len(data)}")
    
    def test_get_clientes(self):
        """GET /api/clientes returns list of clients"""
        response = requests.get(f"{BASE_URL}/api/clientes", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Clientes count: {len(data)}")
    
    def test_get_empleados(self):
        """GET /api/empleados returns list of employees"""
        response = requests.get(f"{BASE_URL}/api/empleados", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Empleados count: {len(data)}")


class TestArticulos:
    """Articulos and Inventario tests"""
    
    def test_get_articulos(self):
        """GET /api/articulos returns articles/products"""
        response = requests.get(f"{BASE_URL}/api/articulos", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Articulos count: {len(data)}")
    
    def test_get_inventario(self):
        """GET /api/inventario returns inventory"""
        response = requests.get(f"{BASE_URL}/api/inventario", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Inventario count: {len(data)}")


class TestOrdenesCompra:
    """Ordenes de Compra (Purchase Orders) tests"""
    
    def test_get_ordenes_compra(self):
        """GET /api/ordenes-compra returns purchase orders"""
        response = requests.get(f"{BASE_URL}/api/ordenes-compra", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Ordenes Compra count: {len(data)}")


class TestFacturasProveedor:
    """Facturas Proveedor (Supplier Invoices) tests"""
    
    def test_get_facturas_proveedor(self):
        """GET /api/facturas-proveedor returns supplier invoices"""
        response = requests.get(f"{BASE_URL}/api/facturas-proveedor", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Facturas Proveedor count: {len(data)}")


class TestGastos:
    """Gastos (Expenses) tests"""
    
    def test_get_gastos(self):
        """GET /api/gastos returns expenses"""
        response = requests.get(f"{BASE_URL}/api/gastos", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Gastos count: {len(data)}")


class TestPagos:
    """Pagos (Payments) tests"""
    
    def test_get_pagos(self):
        """GET /api/pagos returns payments"""
        response = requests.get(f"{BASE_URL}/api/pagos", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Pagos count: {len(data)}")


class TestLetras:
    """Letras (Bills of Exchange) tests"""
    
    def test_get_letras(self):
        """GET /api/letras returns bills of exchange"""
        response = requests.get(f"{BASE_URL}/api/letras", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Letras count: {len(data)}")


class TestCuentasFinancieras:
    """Cuentas Financieras (Financial/Bank Accounts) tests"""
    
    def test_get_cuentas_financieras(self):
        """GET /api/cuentas-financieras returns financial accounts"""
        response = requests.get(f"{BASE_URL}/api/cuentas-financieras", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Cuentas Financieras count: {len(data)}")
        return data
    
    def test_get_kardex_cuenta(self):
        """GET /api/cuentas-financieras/{id}/kardex returns kardex for an account"""
        # First get an account
        cuentas_response = requests.get(f"{BASE_URL}/api/cuentas-financieras", params={'empresa_id': EMPRESA_ID})
        cuentas = cuentas_response.json()
        if cuentas:
            cuenta_id = cuentas[0].get('id')
            response = requests.get(f"{BASE_URL}/api/cuentas-financieras/{cuenta_id}/kardex", params={'empresa_id': EMPRESA_ID})
            assert response.status_code == 200
            data = response.json()
            # Kardex returns object with 'movimientos' key or list
            if isinstance(data, dict):
                assert 'movimientos' in data
                print(f"Kardex for cuenta {cuenta_id}: {len(data.get('movimientos', []))} movements")
            else:
                assert isinstance(data, list)
                print(f"Kardex for cuenta {cuenta_id}: {len(data)} movements")
        else:
            print("No cuentas financieras found, skipping kardex test")


class TestConciliacion:
    """Conciliacion Bancaria (Bank Reconciliation) tests"""
    
    def test_get_conciliaciones(self):
        """GET /api/conciliaciones returns bank reconciliations"""
        response = requests.get(f"{BASE_URL}/api/conciliaciones", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Conciliaciones count: {len(data)}")
    
    def test_get_movimientos_banco(self):
        """GET /api/conciliacion/movimientos-banco returns bank movements"""
        response = requests.get(f"{BASE_URL}/api/conciliacion/movimientos-banco", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Movimientos Banco count: {len(data)}")
    
    def test_get_historial_conciliacion(self):
        """GET /api/conciliacion/historial returns reconciliation history"""
        response = requests.get(f"{BASE_URL}/api/conciliacion/historial", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Historial Conciliacion count: {len(data)}")


class TestPlanillas:
    """Planillas (Payroll) tests"""
    
    def test_get_planillas(self):
        """GET /api/planillas returns payroll list"""
        response = requests.get(f"{BASE_URL}/api/planillas", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Planillas count: {len(data)}")


class TestAdelantos:
    """Adelantos (Advances) tests"""
    
    def test_get_adelantos(self):
        """GET /api/adelantos returns advances"""
        response = requests.get(f"{BASE_URL}/api/adelantos", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Adelantos count: {len(data)}")


class TestPresupuestos:
    """Presupuestos (Budgets) tests"""
    
    def test_get_presupuestos(self):
        """GET /api/presupuestos returns budgets"""
        response = requests.get(f"{BASE_URL}/api/presupuestos", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Presupuestos count: {len(data)}")


class TestContabilidad:
    """Contabilidad (Accounting) tests - Cuentas Contables, Asientos, Config, Periodos"""
    
    def test_get_cuentas_contables(self):
        """GET /api/cuentas-contables returns chart of accounts"""
        response = requests.get(f"{BASE_URL}/api/cuentas-contables", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Cuentas Contables count: {len(data)}")
    
    def test_get_asientos(self):
        """GET /api/asientos returns journal entries"""
        response = requests.get(f"{BASE_URL}/api/asientos", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Asientos count: {len(data)}")
    
    def test_get_periodos_contables(self):
        """GET /api/periodos-contables returns accounting periods"""
        response = requests.get(f"{BASE_URL}/api/periodos-contables", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Periodos Contables count: {len(data)}")
    
    def test_get_config_contable(self):
        """GET /api/config-contable returns accounting config"""
        response = requests.get(f"{BASE_URL}/api/config-contable", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        # Can be dict or empty
        print(f"Config Contable: {type(data)}")


class TestCxCCxP:
    """CxC (Accounts Receivable) and CxP (Accounts Payable) tests"""
    
    def test_get_cxc(self):
        """GET /api/cxc returns accounts receivable"""
        response = requests.get(f"{BASE_URL}/api/cxc", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"CxC count: {len(data)}")
    
    def test_get_cxp(self):
        """GET /api/cxp returns accounts payable"""
        response = requests.get(f"{BASE_URL}/api/cxp", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"CxP count: {len(data)}")


class TestReportes:
    """Reportes (Reports) tests - Balance General, Estado Resultados, Flujo Caja"""
    
    def test_get_balance_general(self):
        """GET /api/reportes/balance-general returns balance sheet"""
        response = requests.get(f"{BASE_URL}/api/reportes/balance-general", params={'empresa_id': EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        print(f"Balance General keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")
    
    def test_get_estado_resultados(self):
        """GET /api/reportes/estado-resultados returns income statement"""
        response = requests.get(
            f"{BASE_URL}/api/reportes/estado-resultados",
            params={'empresa_id': EMPRESA_ID, 'fecha_desde': '2025-01-01', 'fecha_hasta': '2026-12-31'}
        )
        assert response.status_code == 200
        data = response.json()
        print(f"Estado Resultados keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")
    
    def test_get_flujo_caja(self):
        """GET /api/reportes/flujo-caja returns cash flow report"""
        response = requests.get(
            f"{BASE_URL}/api/reportes/flujo-caja",
            params={'empresa_id': EMPRESA_ID, 'fecha_desde': '2025-01-01', 'fecha_hasta': '2026-12-31'}
        )
        assert response.status_code == 200
        data = response.json()
        print(f"Flujo Caja type: {type(data)}")


class TestVentasPOS:
    """Ventas POS tests"""
    
    def test_get_ventas_pos(self):
        """GET /api/ventas-pos returns paginated POS sales"""
        response = requests.get(
            f"{BASE_URL}/api/ventas-pos",
            params={'empresa_id': EMPRESA_ID, 'fecha_desde': '2025-12-01', 'fecha_hasta': '2026-03-10'}
        )
        assert response.status_code == 200
        data = response.json()
        # API returns 'data' key for paginated results
        assert 'data' in data or 'items' in data or isinstance(data, list)
        if 'data' in data:
            print(f"Ventas POS total: {data.get('total', len(data.get('data', [])))}")
        elif 'items' in data:
            print(f"Ventas POS total: {data.get('total', len(data.get('items', [])))}")
        else:
            print(f"Ventas POS count: {len(data)}")
    
    def test_get_ventas_pos_lineas(self):
        """GET /api/ventas-pos/{order_id}/lineas returns order lines"""
        # First get a POS sale
        response = requests.get(
            f"{BASE_URL}/api/ventas-pos",
            params={'empresa_id': EMPRESA_ID, 'fecha_desde': '2025-12-01', 'fecha_hasta': '2026-03-10', 'page_size': 1}
        )
        data = response.json()
        # API returns 'data' key for paginated results
        items = data.get('data', data.get('items', data)) if isinstance(data, dict) else data
        if items and len(items) > 0:
            order_id = items[0].get('id')
            lineas_response = requests.get(
                f"{BASE_URL}/api/ventas-pos/{order_id}/lineas",
                params={'empresa_id': EMPRESA_ID}
            )
            assert lineas_response.status_code == 200
            lineas = lineas_response.json()
            print(f"Lineas for order {order_id}: {len(lineas)}")
        else:
            print("No ventas POS found, skipping lineas test")
    
    def test_ventas_pos_refresh(self):
        """POST /api/ventas-pos/refresh triggers Odoo sync"""
        response = requests.post(
            f"{BASE_URL}/api/ventas-pos/refresh",
            params={'empresa_id': EMPRESA_ID},
            json={}
        )
        # May return 503 if ODOO_MODULE_BASE_URL not configured, or 200 if it works
        assert response.status_code in [200, 503]
        print(f"Ventas POS refresh status: {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
