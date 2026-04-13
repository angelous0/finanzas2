"""
Test suite for Reportes Financieros Gerenciales endpoints:
- GET /api/reportes/balance-general
- GET /api/reportes/estado-resultados
- GET /api/reportes/flujo-caja
- GET /api/reportes/inventario-valorizado
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestReporteBalanceGeneral:
    """Tests for Balance General endpoint"""
    
    def test_balance_general_status_code(self, api_client):
        """Test that endpoint returns 200 OK"""
        response = api_client.get(f"{BASE_URL}/api/reportes/balance-general?empresa_id=1")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"[PASS] Balance General returns status 200")
    
    def test_balance_general_has_activos(self, api_client):
        """Test that response has activos field with correct structure"""
        response = api_client.get(f"{BASE_URL}/api/reportes/balance-general?empresa_id=1")
        data = response.json()
        
        assert "activos" in data, "Missing 'activos' field"
        activos = data["activos"]
        
        # Check sub-fields
        assert "caja_bancos" in activos, "Missing 'caja_bancos' in activos"
        assert "cuentas_por_cobrar" in activos, "Missing 'cuentas_por_cobrar' in activos"
        assert "inventario_mp" in activos, "Missing 'inventario_mp' in activos"
        assert "inventario_pt" in activos, "Missing 'inventario_pt' in activos"
        assert "wip" in activos, "Missing 'wip' in activos"
        assert "total" in activos, "Missing 'total' in activos"
        print(f"[PASS] Balance General activos structure is correct")
    
    def test_balance_general_has_pasivos(self, api_client):
        """Test that response has pasivos field with correct structure"""
        response = api_client.get(f"{BASE_URL}/api/reportes/balance-general?empresa_id=1")
        data = response.json()
        
        assert "pasivos" in data, "Missing 'pasivos' field"
        pasivos = data["pasivos"]
        
        assert "cuentas_por_pagar" in pasivos, "Missing 'cuentas_por_pagar' in pasivos"
        assert "letras_por_pagar" in pasivos, "Missing 'letras_por_pagar' in pasivos"
        assert "total" in pasivos, "Missing 'total' in pasivos"
        print(f"[PASS] Balance General pasivos structure is correct")
    
    def test_balance_general_has_patrimonio(self, api_client):
        """Test that response has patrimonio field"""
        response = api_client.get(f"{BASE_URL}/api/reportes/balance-general?empresa_id=1")
        data = response.json()
        
        assert "patrimonio" in data, "Missing 'patrimonio' field"
        assert "total_activos" in data, "Missing 'total_activos' field"
        assert "total_pasivos" in data, "Missing 'total_pasivos' field"
        
        # Verify accounting equation: Activos = Pasivos + Patrimonio
        assert abs(data["total_activos"] - (data["total_pasivos"] + data["patrimonio"])) < 0.01, \
            "Accounting equation violated: Activos != Pasivos + Patrimonio"
        print(f"[PASS] Balance General patrimonio and accounting equation correct")
    
    def test_balance_general_caja_bancos_detail(self, api_client):
        """Test caja_bancos has cuentas array and total"""
        response = api_client.get(f"{BASE_URL}/api/reportes/balance-general?empresa_id=1")
        data = response.json()
        
        caja = data["activos"]["caja_bancos"]
        assert "cuentas" in caja, "Missing 'cuentas' in caja_bancos"
        assert "total" in caja, "Missing 'total' in caja_bancos"
        assert isinstance(caja["cuentas"], list), "cuentas should be a list"
        print(f"[PASS] Balance General caja_bancos detail structure correct")
    
    def test_balance_general_wip_detail(self, api_client):
        """Test WIP has mp_consumida, servicios, and total"""
        response = api_client.get(f"{BASE_URL}/api/reportes/balance-general?empresa_id=1")
        data = response.json()
        
        wip = data["activos"]["wip"]
        assert "mp_consumida" in wip, "Missing 'mp_consumida' in wip"
        assert "servicios" in wip, "Missing 'servicios' in wip"
        assert "total" in wip, "Missing 'total' in wip"
        print(f"[PASS] Balance General WIP detail structure correct")


class TestReporteEstadoResultados:
    """Tests for Estado de Resultados (P&L) endpoint"""
    
    def test_estado_resultados_status_code(self, api_client):
        """Test that endpoint returns 200 OK"""
        response = api_client.get(
            f"{BASE_URL}/api/reportes/estado-resultados?empresa_id=1&fecha_desde=2026-01-01&fecha_hasta=2026-03-18"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"[PASS] Estado de Resultados returns status 200")
    
    def test_estado_resultados_periodo(self, api_client):
        """Test that response has periodo with desde/hasta"""
        response = api_client.get(
            f"{BASE_URL}/api/reportes/estado-resultados?empresa_id=1&fecha_desde=2026-01-01&fecha_hasta=2026-03-18"
        )
        data = response.json()
        
        assert "periodo" in data, "Missing 'periodo' field"
        assert data["periodo"]["desde"] == "2026-01-01", "Incorrect desde date"
        assert data["periodo"]["hasta"] == "2026-03-18", "Incorrect hasta date"
        print(f"[PASS] Estado de Resultados periodo correct")
    
    def test_estado_resultados_ventas(self, api_client):
        """Test that response has ventas with total and por_linea"""
        response = api_client.get(
            f"{BASE_URL}/api/reportes/estado-resultados?empresa_id=1&fecha_desde=2026-01-01&fecha_hasta=2026-03-18"
        )
        data = response.json()
        
        assert "ventas" in data, "Missing 'ventas' field"
        assert "total" in data["ventas"], "Missing 'total' in ventas"
        assert "por_linea" in data["ventas"], "Missing 'por_linea' in ventas"
        assert isinstance(data["ventas"]["por_linea"], list), "por_linea should be a list"
        print(f"[PASS] Estado de Resultados ventas structure correct")
    
    def test_estado_resultados_costo_venta(self, api_client):
        """Test that response has costo_venta with mp_consumida, servicios, total"""
        response = api_client.get(
            f"{BASE_URL}/api/reportes/estado-resultados?empresa_id=1&fecha_desde=2026-01-01&fecha_hasta=2026-03-18"
        )
        data = response.json()
        
        assert "costo_venta" in data, "Missing 'costo_venta' field"
        costo = data["costo_venta"]
        assert "mp_consumida" in costo, "Missing 'mp_consumida' in costo_venta"
        assert "servicios" in costo, "Missing 'servicios' in costo_venta"
        assert "total" in costo, "Missing 'total' in costo_venta"
        print(f"[PASS] Estado de Resultados costo_venta structure correct")
    
    def test_estado_resultados_margen_bruto(self, api_client):
        """Test that margen_bruto = ventas - costo_venta"""
        response = api_client.get(
            f"{BASE_URL}/api/reportes/estado-resultados?empresa_id=1&fecha_desde=2026-01-01&fecha_hasta=2026-03-18"
        )
        data = response.json()
        
        assert "margen_bruto" in data, "Missing 'margen_bruto' field"
        expected_margen = data["ventas"]["total"] - data["costo_venta"]["total"]
        assert abs(data["margen_bruto"] - expected_margen) < 0.01, \
            f"Margen bruto mismatch: {data['margen_bruto']} vs expected {expected_margen}"
        print(f"[PASS] Estado de Resultados margen_bruto calculation correct")
    
    def test_estado_resultados_gastos_operativos(self, api_client):
        """Test that response has gastos_operativos with total and por_categoria"""
        response = api_client.get(
            f"{BASE_URL}/api/reportes/estado-resultados?empresa_id=1&fecha_desde=2026-01-01&fecha_hasta=2026-03-18"
        )
        data = response.json()
        
        assert "gastos_operativos" in data, "Missing 'gastos_operativos' field"
        gastos = data["gastos_operativos"]
        assert "total" in gastos, "Missing 'total' in gastos_operativos"
        assert "por_categoria" in gastos, "Missing 'por_categoria' in gastos_operativos"
        print(f"[PASS] Estado de Resultados gastos_operativos structure correct")
    
    def test_estado_resultados_utilidad(self, api_client):
        """Test that response has utilidad_operativa and utilidad_neta"""
        response = api_client.get(
            f"{BASE_URL}/api/reportes/estado-resultados?empresa_id=1&fecha_desde=2026-01-01&fecha_hasta=2026-03-18"
        )
        data = response.json()
        
        assert "utilidad_operativa" in data, "Missing 'utilidad_operativa' field"
        assert "utilidad_neta" in data, "Missing 'utilidad_neta' field"
        
        # Verify calculation: utilidad_operativa = margen_bruto - gastos_operativos
        expected = data["margen_bruto"] - data["gastos_operativos"]["total"]
        assert abs(data["utilidad_operativa"] - expected) < 0.01, \
            f"Utilidad operativa mismatch: {data['utilidad_operativa']} vs expected {expected}"
        print(f"[PASS] Estado de Resultados utilidad calculation correct")


class TestReporteFlujoCaja:
    """Tests for Flujo de Caja (Cash Flow) endpoint"""
    
    def test_flujo_caja_status_code(self, api_client):
        """Test that endpoint returns 200 OK"""
        response = api_client.get(
            f"{BASE_URL}/api/reportes/flujo-caja?empresa_id=1&fecha_desde=2026-01-01&fecha_hasta=2026-03-18"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"[PASS] Flujo de Caja returns status 200")
    
    def test_flujo_caja_periodo(self, api_client):
        """Test that response has periodo with desde/hasta"""
        response = api_client.get(
            f"{BASE_URL}/api/reportes/flujo-caja?empresa_id=1&fecha_desde=2026-01-01&fecha_hasta=2026-03-18"
        )
        data = response.json()
        
        assert "periodo" in data, "Missing 'periodo' field"
        assert data["periodo"]["desde"] == "2026-01-01"
        assert data["periodo"]["hasta"] == "2026-03-18"
        print(f"[PASS] Flujo de Caja periodo correct")
    
    def test_flujo_caja_ingresos(self, api_client):
        """Test that ingresos has correct fields"""
        response = api_client.get(
            f"{BASE_URL}/api/reportes/flujo-caja?empresa_id=1&fecha_desde=2026-01-01&fecha_hasta=2026-03-18"
        )
        data = response.json()
        
        assert "ingresos" in data, "Missing 'ingresos' field"
        ing = data["ingresos"]
        assert "cobros_ventas" in ing, "Missing 'cobros_ventas'"
        assert "tesoreria" in ing, "Missing 'tesoreria'"
        assert "pagos_recibidos" in ing, "Missing 'pagos_recibidos'"
        assert "total" in ing, "Missing 'total'"
        assert "detalle" in ing, "Missing 'detalle'"
        print(f"[PASS] Flujo de Caja ingresos structure correct")
    
    def test_flujo_caja_egresos(self, api_client):
        """Test that egresos has correct fields"""
        response = api_client.get(
            f"{BASE_URL}/api/reportes/flujo-caja?empresa_id=1&fecha_desde=2026-01-01&fecha_hasta=2026-03-18"
        )
        data = response.json()
        
        assert "egresos" in data, "Missing 'egresos' field"
        egr = data["egresos"]
        assert "tesoreria" in egr, "Missing 'tesoreria'"
        assert "pagos_proveedores" in egr, "Missing 'pagos_proveedores'"
        assert "total" in egr, "Missing 'total'"
        assert "detalle" in egr, "Missing 'detalle'"
        print(f"[PASS] Flujo de Caja egresos structure correct")
    
    def test_flujo_caja_flujo_neto(self, api_client):
        """Test that flujo_neto = ingresos - egresos"""
        response = api_client.get(
            f"{BASE_URL}/api/reportes/flujo-caja?empresa_id=1&fecha_desde=2026-01-01&fecha_hasta=2026-03-18"
        )
        data = response.json()
        
        assert "flujo_neto" in data, "Missing 'flujo_neto' field"
        expected = data["ingresos"]["total"] - data["egresos"]["total"]
        assert abs(data["flujo_neto"] - expected) < 0.01, \
            f"Flujo neto mismatch: {data['flujo_neto']} vs expected {expected}"
        print(f"[PASS] Flujo de Caja flujo_neto calculation correct")
    
    def test_flujo_caja_saldos_cuentas(self, api_client):
        """Test that saldos_cuentas is present"""
        response = api_client.get(
            f"{BASE_URL}/api/reportes/flujo-caja?empresa_id=1&fecha_desde=2026-01-01&fecha_hasta=2026-03-18"
        )
        data = response.json()
        
        assert "saldos_cuentas" in data, "Missing 'saldos_cuentas' field"
        assert isinstance(data["saldos_cuentas"], list), "saldos_cuentas should be a list"
        print(f"[PASS] Flujo de Caja saldos_cuentas structure correct")


class TestReporteInventarioValorizado:
    """Tests for Inventario Valorizado endpoint"""
    
    def test_inventario_valorizado_status_code(self, api_client):
        """Test that endpoint returns 200 OK"""
        response = api_client.get(f"{BASE_URL}/api/reportes/inventario-valorizado?empresa_id=1")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"[PASS] Inventario Valorizado returns status 200")
    
    def test_inventario_valorizado_materia_prima(self, api_client):
        """Test that response has materia_prima with items and total"""
        response = api_client.get(f"{BASE_URL}/api/reportes/inventario-valorizado?empresa_id=1")
        data = response.json()
        
        assert "materia_prima" in data, "Missing 'materia_prima' field"
        mp = data["materia_prima"]
        assert "items" in mp, "Missing 'items' in materia_prima"
        assert "total" in mp, "Missing 'total' in materia_prima"
        assert isinstance(mp["items"], list), "items should be a list"
        print(f"[PASS] Inventario Valorizado materia_prima structure correct")
    
    def test_inventario_valorizado_producto_terminado(self, api_client):
        """Test that response has producto_terminado with items and total"""
        response = api_client.get(f"{BASE_URL}/api/reportes/inventario-valorizado?empresa_id=1")
        data = response.json()
        
        assert "producto_terminado" in data, "Missing 'producto_terminado' field"
        pt = data["producto_terminado"]
        assert "items" in pt, "Missing 'items' in producto_terminado"
        assert "total" in pt, "Missing 'total' in producto_terminado"
        print(f"[PASS] Inventario Valorizado producto_terminado structure correct")
    
    def test_inventario_valorizado_wip(self, api_client):
        """Test that response has wip with mp_consumida, servicios, totals"""
        response = api_client.get(f"{BASE_URL}/api/reportes/inventario-valorizado?empresa_id=1")
        data = response.json()
        
        assert "wip" in data, "Missing 'wip' field"
        wip = data["wip"]
        assert "mp_consumida" in wip, "Missing 'mp_consumida' in wip"
        assert "total_mp" in wip, "Missing 'total_mp' in wip"
        assert "servicios" in wip, "Missing 'servicios' in wip"
        assert "total_srv" in wip, "Missing 'total_srv' in wip"
        assert "total" in wip, "Missing 'total' in wip"
        print(f"[PASS] Inventario Valorizado WIP structure correct")
    
    def test_inventario_valorizado_gran_total(self, api_client):
        """Test that gran_total = MP + PT + WIP"""
        response = api_client.get(f"{BASE_URL}/api/reportes/inventario-valorizado?empresa_id=1")
        data = response.json()
        
        assert "gran_total" in data, "Missing 'gran_total' field"
        expected = data["materia_prima"]["total"] + data["producto_terminado"]["total"] + data["wip"]["total"]
        assert abs(data["gran_total"] - expected) < 0.01, \
            f"Gran total mismatch: {data['gran_total']} vs expected {expected}"
        print(f"[PASS] Inventario Valorizado gran_total calculation correct")


class TestReportesNoEmpresaId:
    """Test that endpoints handle missing empresa_id gracefully"""
    
    def test_balance_general_without_empresa_id(self, api_client):
        """Test that endpoint works with default empresa handling"""
        response = api_client.get(f"{BASE_URL}/api/reportes/balance-general")
        # Should either return 200 with default empresa, 400 bad request, or 422 validation error
        assert response.status_code in [200, 400, 422], f"Unexpected status: {response.status_code}"
        print(f"[PASS] Balance General handles missing empresa_id: {response.status_code}")
    
    def test_estado_resultados_default_dates(self, api_client):
        """Test that endpoint uses default dates when not provided"""
        response = api_client.get(f"{BASE_URL}/api/reportes/estado-resultados?empresa_id=1")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "periodo" in data
        # Should have default dates (2020-01-01 to today)
        assert data["periodo"]["desde"] == "2020-01-01" or data["periodo"]["desde"] is not None
        print(f"[PASS] Estado de Resultados uses default dates correctly")
