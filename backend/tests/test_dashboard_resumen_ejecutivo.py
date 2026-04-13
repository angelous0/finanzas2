"""
Test Dashboard Resumen Ejecutivo - Iteration 29
Tests for the executive dashboard with KPIs, alerts, and profit-by-line data
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestDashboardResumenEjecutivo:
    """Tests for GET /api/dashboard/resumen-ejecutivo endpoint"""
    
    @pytest.fixture
    def empresa_id(self):
        return 6
    
    def test_resumen_ejecutivo_returns_200(self, empresa_id):
        """Test that the endpoint returns 200 status"""
        response = requests.get(f"{BASE_URL}/api/dashboard/resumen-ejecutivo", params={"empresa_id": empresa_id})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_resumen_ejecutivo_has_ventas_pendientes_fields(self, empresa_id):
        """Test ventas_pendientes_cantidad and ventas_pendientes_monto fields"""
        response = requests.get(f"{BASE_URL}/api/dashboard/resumen-ejecutivo", params={"empresa_id": empresa_id})
        assert response.status_code == 200
        data = response.json()
        
        assert "ventas_pendientes_cantidad" in data, "Missing ventas_pendientes_cantidad"
        assert "ventas_pendientes_monto" in data, "Missing ventas_pendientes_monto"
        assert isinstance(data["ventas_pendientes_cantidad"], int), "ventas_pendientes_cantidad should be int"
        assert isinstance(data["ventas_pendientes_monto"], (int, float)), "ventas_pendientes_monto should be numeric"
    
    def test_resumen_ejecutivo_has_gastos_prorrateo_fields(self, empresa_id):
        """Test gastos_prorrateo_cantidad and gastos_prorrateo_monto fields"""
        response = requests.get(f"{BASE_URL}/api/dashboard/resumen-ejecutivo", params={"empresa_id": empresa_id})
        assert response.status_code == 200
        data = response.json()
        
        assert "gastos_prorrateo_cantidad" in data, "Missing gastos_prorrateo_cantidad"
        assert "gastos_prorrateo_monto" in data, "Missing gastos_prorrateo_monto"
        assert isinstance(data["gastos_prorrateo_cantidad"], int), "gastos_prorrateo_cantidad should be int"
        assert isinstance(data["gastos_prorrateo_monto"], (int, float)), "gastos_prorrateo_monto should be numeric"
    
    def test_resumen_ejecutivo_has_cobranza_pendiente(self, empresa_id):
        """Test cobranza_pendiente_total and cobranza_pendiente_linea fields"""
        response = requests.get(f"{BASE_URL}/api/dashboard/resumen-ejecutivo", params={"empresa_id": empresa_id})
        assert response.status_code == 200
        data = response.json()
        
        assert "cobranza_pendiente_total" in data, "Missing cobranza_pendiente_total"
        assert "cobranza_pendiente_linea" in data, "Missing cobranza_pendiente_linea"
        assert isinstance(data["cobranza_pendiente_total"], (int, float)), "cobranza_pendiente_total should be numeric"
        assert isinstance(data["cobranza_pendiente_linea"], list), "cobranza_pendiente_linea should be array"
    
    def test_resumen_ejecutivo_cobranza_linea_structure(self, empresa_id):
        """Test cobranza_pendiente_linea array has correct structure"""
        response = requests.get(f"{BASE_URL}/api/dashboard/resumen-ejecutivo", params={"empresa_id": empresa_id})
        assert response.status_code == 200
        data = response.json()
        
        cobranza_linea = data["cobranza_pendiente_linea"]
        if len(cobranza_linea) > 0:
            first = cobranza_linea[0]
            assert "linea_id" in first or first.get("linea_id") is None, "Should have linea_id (can be null)"
            assert "linea_nombre" in first or first.get("linea_nombre") is None, "Should have linea_nombre (can be null)"
            assert "saldo_pendiente" in first, "Should have saldo_pendiente"
    
    def test_resumen_ejecutivo_has_ingresos_gastos_mes(self, empresa_id):
        """Test ingresos_mes and gastos_mes fields"""
        response = requests.get(f"{BASE_URL}/api/dashboard/resumen-ejecutivo", params={"empresa_id": empresa_id})
        assert response.status_code == 200
        data = response.json()
        
        assert "ingresos_mes" in data, "Missing ingresos_mes"
        assert "gastos_mes" in data, "Missing gastos_mes"
        assert "resultado_neto" in data, "Missing resultado_neto"
        assert isinstance(data["ingresos_mes"], (int, float)), "ingresos_mes should be numeric"
        assert isinstance(data["gastos_mes"], (int, float)), "gastos_mes should be numeric"
        assert isinstance(data["resultado_neto"], (int, float)), "resultado_neto should be numeric"
    
    def test_resumen_ejecutivo_resultado_neto_calculation(self, empresa_id):
        """Test resultado_neto = ingresos_mes - gastos_mes"""
        response = requests.get(f"{BASE_URL}/api/dashboard/resumen-ejecutivo", params={"empresa_id": empresa_id})
        assert response.status_code == 200
        data = response.json()
        
        expected_resultado = data["ingresos_mes"] - data["gastos_mes"]
        assert abs(data["resultado_neto"] - expected_resultado) < 0.01, f"resultado_neto should be ingresos_mes - gastos_mes"
    
    def test_resumen_ejecutivo_has_utilidad_linea(self, empresa_id):
        """Test utilidad_linea array exists and has correct structure"""
        response = requests.get(f"{BASE_URL}/api/dashboard/resumen-ejecutivo", params={"empresa_id": empresa_id})
        assert response.status_code == 200
        data = response.json()
        
        assert "utilidad_linea" in data, "Missing utilidad_linea"
        assert isinstance(data["utilidad_linea"], list), "utilidad_linea should be array"
    
    def test_resumen_ejecutivo_utilidad_linea_structure(self, empresa_id):
        """Test each item in utilidad_linea has required fields"""
        response = requests.get(f"{BASE_URL}/api/dashboard/resumen-ejecutivo", params={"empresa_id": empresa_id})
        assert response.status_code == 200
        data = response.json()
        
        utilidad_linea = data["utilidad_linea"]
        required_fields = [
            "linea_id", "linea_nombre", "ingresos", "gastos_directos", 
            "gastos_prorrateados", "utilidad_antes_prorrateo", "utilidad_despues_prorrateo"
        ]
        
        if len(utilidad_linea) > 0:
            for linea in utilidad_linea:
                for field in required_fields:
                    assert field in linea, f"Missing field {field} in utilidad_linea item"
    
    def test_resumen_ejecutivo_utilidad_calculation(self, empresa_id):
        """Test utilidad calculations in utilidad_linea"""
        response = requests.get(f"{BASE_URL}/api/dashboard/resumen-ejecutivo", params={"empresa_id": empresa_id})
        assert response.status_code == 200
        data = response.json()
        
        for linea in data["utilidad_linea"]:
            # utilidad_antes = ingresos - gastos_directos
            expected_antes = linea["ingresos"] - linea["gastos_directos"]
            assert abs(linea["utilidad_antes_prorrateo"] - expected_antes) < 0.01, \
                f"utilidad_antes_prorrateo should be ingresos - gastos_directos for {linea['linea_nombre']}"
            
            # utilidad_despues = ingresos - gastos_directos - gastos_prorrateados
            expected_despues = linea["ingresos"] - linea["gastos_directos"] - linea["gastos_prorrateados"]
            assert abs(linea["utilidad_despues_prorrateo"] - expected_despues) < 0.01, \
                f"utilidad_despues_prorrateo should be ingresos - gastos_directos - gastos_prorrateados for {linea['linea_nombre']}"


class TestDashboardKPIsLegacy:
    """Tests for GET /api/dashboard/kpis endpoint (legacy)"""
    
    @pytest.fixture
    def empresa_id(self):
        return 6
    
    def test_kpis_returns_200(self, empresa_id):
        """Test legacy KPIs endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/dashboard/kpis", params={"empresa_id": empresa_id})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_kpis_has_required_fields(self, empresa_id):
        """Test legacy KPIs endpoint returns all required fields"""
        response = requests.get(f"{BASE_URL}/api/dashboard/kpis", params={"empresa_id": empresa_id})
        assert response.status_code == 200
        data = response.json()
        
        required_fields = [
            "total_cxp", "total_cxc", "total_letras_pendientes", "saldo_bancos",
            "ventas_mes", "gastos_mes", "facturas_pendientes", "letras_por_vencer"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing field {field} in KPIs response"


class TestDashboardDataConsistency:
    """Test data consistency between endpoints"""
    
    @pytest.fixture
    def empresa_id(self):
        return 6
    
    def test_cobranza_total_matches_kpis_cxc(self, empresa_id):
        """Test cobranza_pendiente_total in resumen matches total_cxc in kpis"""
        resumen_resp = requests.get(f"{BASE_URL}/api/dashboard/resumen-ejecutivo", params={"empresa_id": empresa_id})
        kpis_resp = requests.get(f"{BASE_URL}/api/dashboard/kpis", params={"empresa_id": empresa_id})
        
        assert resumen_resp.status_code == 200
        assert kpis_resp.status_code == 200
        
        resumen = resumen_resp.json()
        kpis = kpis_resp.json()
        
        assert abs(resumen["cobranza_pendiente_total"] - kpis["total_cxc"]) < 0.01, \
            "cobranza_pendiente_total should match total_cxc"
    
    def test_gastos_mes_consistent(self, empresa_id):
        """Test gastos_mes is consistent between both endpoints"""
        resumen_resp = requests.get(f"{BASE_URL}/api/dashboard/resumen-ejecutivo", params={"empresa_id": empresa_id})
        kpis_resp = requests.get(f"{BASE_URL}/api/dashboard/kpis", params={"empresa_id": empresa_id})
        
        assert resumen_resp.status_code == 200
        assert kpis_resp.status_code == 200
        
        resumen = resumen_resp.json()
        kpis = kpis_resp.json()
        
        assert abs(resumen["gastos_mes"] - kpis["gastos_mes"]) < 0.01, \
            "gastos_mes should be consistent between endpoints"
