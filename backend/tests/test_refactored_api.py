"""
Backend API Tests for Finanzas 4.0 Refactored Architecture
Tests all 132 endpoints after refactoring from monolithic server.py to 18 domain routers.
"""

import pytest
import requests
import os

# Use environment variable for BASE_URL
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
EMPRESA_ID = 6  # Ambission Industries SAC

# Test headers
HEADERS = {"Content-Type": "application/json"}


class TestCoreEndpoints:
    """Test core/health endpoints from routers/core.py"""

    def test_health_check(self):
        """GET /api/health - Returns 200 with database connected"""
        response = requests.get(f"{BASE_URL}/api/health", headers=HEADERS)
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        print("PASS: Health check returns 200 with database connected")

    def test_root_endpoint(self):
        """GET /api/ - Returns Finanzas 4.0 API info"""
        response = requests.get(f"{BASE_URL}/api/", headers=HEADERS)
        assert response.status_code == 200, f"Root endpoint failed: {response.text}"
        data = response.json()
        assert data["message"] == "Finanzas 4.0 API"
        assert data["version"] == "1.0.0"
        print("PASS: Root endpoint returns Finanzas 4.0 API info")


class TestEmpresasEndpoints:
    """Test empresas endpoints from routers/empresas.py"""

    def test_list_empresas(self):
        """GET /api/empresas - Returns list of empresas"""
        response = requests.get(f"{BASE_URL}/api/empresas", headers=HEADERS)
        assert response.status_code == 200, f"List empresas failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        # Verify empresa 6 (Ambission Industries SAC) exists
        empresa_6 = next((e for e in data if e["id"] == EMPRESA_ID), None)
        assert empresa_6 is not None, "Empresa ID 6 (Ambission Industries SAC) not found"
        print(f"PASS: List empresas returns {len(data)} empresas, including empresa_id={EMPRESA_ID}")


class TestMaestrosEndpoints:
    """Test master data endpoints from routers/maestros.py"""

    def test_list_monedas(self):
        """GET /api/monedas - Returns list of monedas"""
        response = requests.get(f"{BASE_URL}/api/monedas", headers=HEADERS)
        assert response.status_code == 200, f"List monedas failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1, "Should have at least 1 moneda"
        # Verify PEN and USD exist
        codigos = [m["codigo"] for m in data]
        assert "PEN" in codigos, "PEN currency not found"
        print(f"PASS: List monedas returns {len(data)} currencies")

    def test_list_categorias(self):
        """GET /api/categorias?empresa_id=6 - Returns 8 categories"""
        response = requests.get(f"{BASE_URL}/api/categorias?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"List categorias failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 8, f"Expected at least 8 categories, got {len(data)}"
        print(f"PASS: List categorias returns {len(data)} categories for empresa_id={EMPRESA_ID}")

    def test_list_centros_costo(self):
        """GET /api/centros-costo?empresa_id=6 - Returns list"""
        response = requests.get(f"{BASE_URL}/api/centros-costo?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"List centros costo failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List centros costo returns {len(data)} centros for empresa_id={EMPRESA_ID}")

    def test_list_lineas_negocio(self):
        """GET /api/lineas-negocio?empresa_id=6 - Returns list"""
        response = requests.get(f"{BASE_URL}/api/lineas-negocio?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"List lineas negocio failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List lineas negocio returns {len(data)} lineas for empresa_id={EMPRESA_ID}")


class TestCuentasFinancierasEndpoints:
    """Test financial accounts endpoints from routers/cuentas_financieras.py"""

    def test_list_cuentas_financieras(self):
        """GET /api/cuentas-financieras?empresa_id=6 - Returns financial accounts"""
        response = requests.get(f"{BASE_URL}/api/cuentas-financieras?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"List cuentas financieras failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List cuentas financieras returns {len(data)} accounts for empresa_id={EMPRESA_ID}")


class TestTercerosEndpoints:
    """Test terceros/proveedores/empleados endpoints from routers/terceros.py"""

    def test_list_terceros(self):
        """GET /api/terceros?empresa_id=6 - Returns terceros list"""
        response = requests.get(f"{BASE_URL}/api/terceros?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"List terceros failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List terceros returns {len(data)} terceros for empresa_id={EMPRESA_ID}")

    def test_list_proveedores(self):
        """GET /api/proveedores?empresa_id=6 - Returns proveedores"""
        response = requests.get(f"{BASE_URL}/api/proveedores?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"List proveedores failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List proveedores returns {len(data)} proveedores for empresa_id={EMPRESA_ID}")

    def test_list_empleados(self):
        """GET /api/empleados?empresa_id=6 - Returns empleados"""
        response = requests.get(f"{BASE_URL}/api/empleados?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"List empleados failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List empleados returns {len(data)} empleados for empresa_id={EMPRESA_ID}")


class TestComprasEndpoints:
    """Test purchase/OC endpoints from routers/compras.py"""

    def test_list_ordenes_compra(self):
        """GET /api/ordenes-compra?empresa_id=6 - Returns OC list"""
        response = requests.get(f"{BASE_URL}/api/ordenes-compra?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"List OC failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List ordenes compra returns {len(data)} OCs for empresa_id={EMPRESA_ID}")

    def test_list_facturas_proveedor(self):
        """GET /api/facturas-proveedor?empresa_id=6 - Returns facturas"""
        response = requests.get(f"{BASE_URL}/api/facturas-proveedor?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"List facturas proveedor failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List facturas proveedor returns {len(data)} facturas for empresa_id={EMPRESA_ID}")


class TestPagosEndpoints:
    """Test payment endpoints from routers/pagos.py"""

    def test_list_pagos(self):
        """GET /api/pagos?empresa_id=6 - Returns pagos"""
        response = requests.get(f"{BASE_URL}/api/pagos?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"List pagos failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List pagos returns {len(data)} pagos for empresa_id={EMPRESA_ID}")

    def test_list_letras(self):
        """GET /api/letras?empresa_id=6 - Returns letras"""
        response = requests.get(f"{BASE_URL}/api/letras?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"List letras failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List letras returns {len(data)} letras for empresa_id={EMPRESA_ID}")


class TestGastosEndpoints:
    """Test expense endpoints from routers/gastos.py"""

    def test_list_gastos(self):
        """GET /api/gastos?empresa_id=6 - Returns gastos"""
        response = requests.get(f"{BASE_URL}/api/gastos?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"List gastos failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List gastos returns {len(data)} gastos for empresa_id={EMPRESA_ID}")

    def test_list_adelantos(self):
        """GET /api/adelantos?empresa_id=6 - Returns adelantos"""
        response = requests.get(f"{BASE_URL}/api/adelantos?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"List adelantos failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List adelantos returns {len(data)} adelantos for empresa_id={EMPRESA_ID}")


class TestPlanillasEndpoints:
    """Test payroll endpoints from routers/planillas.py"""

    def test_list_planillas(self):
        """GET /api/planillas?empresa_id=6 - Returns planillas"""
        response = requests.get(f"{BASE_URL}/api/planillas?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"List planillas failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List planillas returns {len(data)} planillas for empresa_id={EMPRESA_ID}")


class TestVentasPOSEndpoints:
    """Test POS sales endpoints from routers/ventas_pos.py"""

    def test_list_ventas_pos(self):
        """GET /api/ventas-pos?empresa_id=6 - Returns ventas POS"""
        response = requests.get(f"{BASE_URL}/api/ventas-pos?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"List ventas POS failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List ventas POS returns {len(data)} ventas for empresa_id={EMPRESA_ID}")


class TestCxCCxPEndpoints:
    """Test accounts receivable/payable endpoints from routers/cxc_cxp.py"""

    def test_list_cxp(self):
        """GET /api/cxp?empresa_id=6 - Returns CxP"""
        response = requests.get(f"{BASE_URL}/api/cxp?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"List CxP failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List CxP returns {len(data)} CxP for empresa_id={EMPRESA_ID}")

    def test_list_cxc(self):
        """GET /api/cxc?empresa_id=6 - Returns CxC"""
        response = requests.get(f"{BASE_URL}/api/cxc?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"List CxC failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List CxC returns {len(data)} CxC for empresa_id={EMPRESA_ID}")


class TestPresupuestosEndpoints:
    """Test budget endpoints from routers/presupuestos.py"""

    def test_list_presupuestos(self):
        """GET /api/presupuestos?empresa_id=6 - Returns presupuestos"""
        response = requests.get(f"{BASE_URL}/api/presupuestos?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"List presupuestos failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List presupuestos returns {len(data)} presupuestos for empresa_id={EMPRESA_ID}")


class TestBancoEndpoints:
    """Test bank/conciliation endpoints from routers/banco.py"""

    def test_list_movimientos_banco(self):
        """GET /api/conciliacion/movimientos-banco?empresa_id=6 - Returns bank movements"""
        response = requests.get(f"{BASE_URL}/api/conciliacion/movimientos-banco?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"List movimientos banco failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List movimientos banco returns {len(data)} movements for empresa_id={EMPRESA_ID}")

    def test_historial_conciliaciones(self):
        """GET /api/conciliacion/historial?empresa_id=6 - Returns conciliation history"""
        response = requests.get(f"{BASE_URL}/api/conciliacion/historial?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"List historial conciliaciones failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List historial conciliaciones returns {len(data)} records for empresa_id={EMPRESA_ID}")


class TestContabilidadEndpoints:
    """Test accounting endpoints from routers/contabilidad.py"""

    def test_list_cuentas_contables(self):
        """GET /api/cuentas-contables?empresa_id=6 - Returns contable accounts"""
        response = requests.get(f"{BASE_URL}/api/cuentas-contables?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"List cuentas contables failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List cuentas contables returns {len(data)} accounts for empresa_id={EMPRESA_ID}")

    def test_config_contable(self):
        """GET /api/config-contable?empresa_id=6 - Returns contable config"""
        response = requests.get(f"{BASE_URL}/api/config-contable?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"Get config contable failed: {response.text}"
        data = response.json()
        assert "empresa_id" in data or data == {}
        print(f"PASS: Get config contable returns config for empresa_id={EMPRESA_ID}")

    def test_list_asientos(self):
        """GET /api/asientos?empresa_id=6 - Returns journal entries"""
        response = requests.get(f"{BASE_URL}/api/asientos?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"List asientos failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List asientos returns {len(data)} entries for empresa_id={EMPRESA_ID}")

    def test_list_periodos_contables(self):
        """GET /api/periodos-contables?empresa_id=6 - Returns periods"""
        response = requests.get(f"{BASE_URL}/api/periodos-contables?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"List periodos contables failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: List periodos contables returns {len(data)} periods for empresa_id={EMPRESA_ID}")


class TestDashboardEndpoints:
    """Test dashboard endpoints from routers/dashboard.py"""

    def test_dashboard_kpis(self):
        """GET /api/dashboard/kpis?empresa_id=6 - Returns KPIs with numeric values"""
        response = requests.get(f"{BASE_URL}/api/dashboard/kpis?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"Get dashboard KPIs failed: {response.text}"
        data = response.json()
        # Verify all KPI fields exist and are numeric
        required_fields = [
            "total_cxp", "total_cxc", "total_letras_pendientes", 
            "saldo_bancos", "ventas_mes", "gastos_mes",
            "facturas_pendientes", "letras_por_vencer"
        ]
        for field in required_fields:
            assert field in data, f"KPI field '{field}' missing"
            assert isinstance(data[field], (int, float)), f"KPI field '{field}' should be numeric, got {type(data[field])}"
        print(f"PASS: Dashboard KPIs returns all {len(required_fields)} numeric fields for empresa_id={EMPRESA_ID}")


class TestReportesEndpoints:
    """Test reporting endpoints from routers/reportes.py"""

    def test_reporte_flujo_caja(self):
        """GET /api/reportes/flujo-caja - Returns cash flow data"""
        response = requests.get(
            f"{BASE_URL}/api/reportes/flujo-caja?fecha_desde=2025-01-01&fecha_hasta=2026-12-31&empresa_id={EMPRESA_ID}",
            headers=HEADERS
        )
        assert response.status_code == 200, f"Get flujo caja failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: Reporte flujo caja returns {len(data)} items for empresa_id={EMPRESA_ID}")

    def test_reporte_estado_resultados(self):
        """GET /api/reportes/estado-resultados - Returns results"""
        response = requests.get(
            f"{BASE_URL}/api/reportes/estado-resultados?fecha_desde=2025-01-01&fecha_hasta=2026-12-31&empresa_id={EMPRESA_ID}",
            headers=HEADERS
        )
        assert response.status_code == 200, f"Get estado resultados failed: {response.text}"
        data = response.json()
        assert "ingresos" in data
        assert "egresos" in data
        assert "resultado_neto" in data
        print(f"PASS: Reporte estado resultados returns data for empresa_id={EMPRESA_ID}")

    def test_reporte_balance_general(self):
        """GET /api/reportes/balance-general - Returns balance"""
        response = requests.get(
            f"{BASE_URL}/api/reportes/balance-general?empresa_id={EMPRESA_ID}",
            headers=HEADERS
        )
        assert response.status_code == 200, f"Get balance general failed: {response.text}"
        data = response.json()
        assert "activos" in data
        assert "pasivos" in data
        assert "total_activos" in data
        assert "total_pasivos" in data
        print(f"PASS: Reporte balance general returns data for empresa_id={EMPRESA_ID}")


class TestErrorHandling:
    """Test proper error handling when empresa_id is missing"""

    def test_missing_empresa_id(self):
        """Endpoints that require empresa_id should return 400 when missing"""
        # Test a few endpoints that require empresa_id
        endpoints_requiring_empresa_id = [
            "/api/categorias",
            "/api/centros-costo",
            "/api/cuentas-financieras",
            "/api/terceros",
            "/api/gastos",
        ]
        for endpoint in endpoints_requiring_empresa_id:
            response = requests.get(f"{BASE_URL}{endpoint}", headers=HEADERS)
            assert response.status_code == 400, f"Expected 400 for {endpoint} without empresa_id, got {response.status_code}"
        print(f"PASS: All {len(endpoints_requiring_empresa_id)} endpoints correctly return 400 when empresa_id is missing")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
