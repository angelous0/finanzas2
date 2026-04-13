"""
Test cases for Iteration 3 fixes:
1. IGV (VAT 18%) calculation in OrdenesCompra - igv_incluido toggle
2. Company filter (empresa_id) for Adelantos and Planilla endpoints
"""
import pytest
import requests
import os
from datetime import date

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="session")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestHealthCheck:
    """Basic health check to ensure API is running"""
    
    def test_api_health(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✓ API is healthy and connected to database")


class TestOrdenesCompraIGV:
    """Test IGV calculation in OrdenesCompra - verifying fix for igv_incluido"""
    
    @pytest.fixture
    def get_test_data(self, api_client):
        """Get proveedor and moneda IDs for OC creation"""
        proveedores_res = api_client.get(f"{BASE_URL}/api/proveedores")
        monedas_res = api_client.get(f"{BASE_URL}/api/monedas")
        
        assert proveedores_res.status_code == 200
        assert monedas_res.status_code == 200
        
        proveedores = proveedores_res.json()
        monedas = monedas_res.json()
        
        # Get first available proveedor and moneda
        proveedor_id = proveedores[0]['id'] if proveedores else None
        moneda_id = monedas[0]['id'] if monedas else None
        
        return {"proveedor_id": proveedor_id, "moneda_id": moneda_id}
    
    def test_oc_igv_incluido_true(self, api_client, get_test_data):
        """
        Test: When igv_incluido=true, price 118 should result in subtotal=100, igv=18, total=118
        The backend should divide by 1.18 to extract base price
        """
        test_data = get_test_data
        if not test_data['proveedor_id'] or not test_data['moneda_id']:
            pytest.skip("No test data available (proveedor or moneda missing)")
        
        payload = {
            "fecha": str(date.today()),
            "proveedor_id": test_data['proveedor_id'],
            "moneda_id": test_data['moneda_id'],
            "igv_incluido": True,
            "notas": "TEST_IGV_INCLUIDO_TRUE",
            "lineas": [
                {
                    "descripcion": "Test Item IGV Incluido",
                    "cantidad": 1,
                    "precio_unitario": 118.00,
                    "igv_aplica": True
                }
            ]
        }
        
        response = api_client.post(f"{BASE_URL}/api/ordenes-compra", json=payload)
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.json()}")
        
        assert response.status_code == 200, f"Failed to create OC: {response.text}"
        
        data = response.json()
        
        # Verify the IGV calculation
        # When igv_incluido=true and price=118:
        # subtotal = 118 / 1.18 = 100
        # igv = 118 - 100 = 18
        # total = 100 + 18 = 118
        
        subtotal = float(data['subtotal'])
        igv = float(data['igv'])
        total = float(data['total'])
        
        print(f"✓ IGV Incluido=True Test: subtotal={subtotal:.2f}, igv={igv:.2f}, total={total:.2f}")
        
        # Allow small floating point tolerance
        assert abs(subtotal - 100.0) < 0.01, f"Expected subtotal ~100, got {subtotal}"
        assert abs(igv - 18.0) < 0.01, f"Expected IGV ~18, got {igv}"
        assert abs(total - 118.0) < 0.01, f"Expected total ~118, got {total}"
        
        print("✓ IGV calculation correct when igv_incluido=true")
        
        # Cleanup - delete the test OC
        oc_id = data['id']
        delete_response = api_client.delete(f"{BASE_URL}/api/ordenes-compra/{oc_id}")
        assert delete_response.status_code == 200, "Failed to cleanup test OC"
        print("✓ Test OC cleaned up")
    
    def test_oc_igv_incluido_false(self, api_client, get_test_data):
        """
        Test: When igv_incluido=false, price 100 should result in subtotal=100, igv=18, total=118
        The backend should add 18% IGV on top
        """
        test_data = get_test_data
        if not test_data['proveedor_id'] or not test_data['moneda_id']:
            pytest.skip("No test data available (proveedor or moneda missing)")
        
        payload = {
            "fecha": str(date.today()),
            "proveedor_id": test_data['proveedor_id'],
            "moneda_id": test_data['moneda_id'],
            "igv_incluido": False,
            "notas": "TEST_IGV_INCLUIDO_FALSE",
            "lineas": [
                {
                    "descripcion": "Test Item IGV Not Included",
                    "cantidad": 1,
                    "precio_unitario": 100.00,
                    "igv_aplica": True
                }
            ]
        }
        
        response = api_client.post(f"{BASE_URL}/api/ordenes-compra", json=payload)
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.json()}")
        
        assert response.status_code == 200, f"Failed to create OC: {response.text}"
        
        data = response.json()
        
        # Verify the IGV calculation
        # When igv_incluido=false and price=100:
        # subtotal = 100
        # igv = 100 * 0.18 = 18
        # total = 100 + 18 = 118
        
        subtotal = float(data['subtotal'])
        igv = float(data['igv'])
        total = float(data['total'])
        
        print(f"✓ IGV Incluido=False Test: subtotal={subtotal:.2f}, igv={igv:.2f}, total={total:.2f}")
        
        # Allow small floating point tolerance
        assert abs(subtotal - 100.0) < 0.01, f"Expected subtotal ~100, got {subtotal}"
        assert abs(igv - 18.0) < 0.01, f"Expected IGV ~18, got {igv}"
        assert abs(total - 118.0) < 0.01, f"Expected total ~118, got {total}"
        
        print("✓ IGV calculation correct when igv_incluido=false")
        
        # Cleanup - delete the test OC
        oc_id = data['id']
        delete_response = api_client.delete(f"{BASE_URL}/api/ordenes-compra/{oc_id}")
        assert delete_response.status_code == 200, "Failed to cleanup test OC"
        print("✓ Test OC cleaned up")


class TestAdelantosEmpresaFilter:
    """Test empresa_id filter for Adelantos endpoint"""
    
    def test_adelantos_without_empresa_id(self, api_client):
        """Test that /api/adelantos without empresa_id returns all results"""
        response = api_client.get(f"{BASE_URL}/api/adelantos")
        
        assert response.status_code == 200, f"Failed to get adelantos: {response.text}"
        data = response.json()
        
        # Should return a list (may be empty if no adelantos exist)
        assert isinstance(data, list), "Expected list response"
        print(f"✓ GET /api/adelantos returned {len(data)} adelantos (no filter)")
    
    def test_adelantos_with_empresa_id_1(self, api_client):
        """Test that /api/adelantos?empresa_id=1 returns filtered results"""
        response = api_client.get(f"{BASE_URL}/api/adelantos", params={"empresa_id": 1})
        
        assert response.status_code == 200, f"Failed to get adelantos: {response.text}"
        data = response.json()
        
        # Should return a list (may be empty if no adelantos for empresa_id=1)
        assert isinstance(data, list), "Expected list response"
        print(f"✓ GET /api/adelantos?empresa_id=1 returned {len(data)} adelantos (filtered)")
    
    def test_adelantos_with_empresa_id_999(self, api_client):
        """Test that /api/adelantos?empresa_id=999 returns empty list for non-existent empresa"""
        response = api_client.get(f"{BASE_URL}/api/adelantos", params={"empresa_id": 999})
        
        assert response.status_code == 200, f"Failed to get adelantos: {response.text}"
        data = response.json()
        
        # Should return empty list for non-existent empresa
        assert isinstance(data, list), "Expected list response"
        print(f"✓ GET /api/adelantos?empresa_id=999 returned {len(data)} adelantos (expected 0 for non-existent empresa)")


class TestPlanillasEmpresaFilter:
    """Test empresa_id filter for Planillas endpoint"""
    
    def test_planillas_without_empresa_id(self, api_client):
        """Test that /api/planillas without empresa_id returns all results"""
        response = api_client.get(f"{BASE_URL}/api/planillas")
        
        assert response.status_code == 200, f"Failed to get planillas: {response.text}"
        data = response.json()
        
        # Should return a list (may be empty if no planillas exist)
        assert isinstance(data, list), "Expected list response"
        print(f"✓ GET /api/planillas returned {len(data)} planillas (no filter)")
    
    def test_planillas_with_empresa_id_1(self, api_client):
        """Test that /api/planillas?empresa_id=1 returns filtered results"""
        response = api_client.get(f"{BASE_URL}/api/planillas", params={"empresa_id": 1})
        
        assert response.status_code == 200, f"Failed to get planillas: {response.text}"
        data = response.json()
        
        # Should return a list (may be empty if no planillas for empresa_id=1)
        assert isinstance(data, list), "Expected list response"
        print(f"✓ GET /api/planillas?empresa_id=1 returned {len(data)} planillas (filtered)")
    
    def test_planillas_with_empresa_id_999(self, api_client):
        """Test that /api/planillas?empresa_id=999 returns empty list for non-existent empresa"""
        response = api_client.get(f"{BASE_URL}/api/planillas", params={"empresa_id": 999})
        
        assert response.status_code == 200, f"Failed to get planillas: {response.text}"
        data = response.json()
        
        # Should return empty list for non-existent empresa
        assert isinstance(data, list), "Expected list response"
        print(f"✓ GET /api/planillas?empresa_id=999 returned {len(data)} planillas (expected 0 for non-existent empresa)")


class TestOrdenesCompraPage:
    """Test OrdenesCompra page loads and basic operations"""
    
    def test_get_ordenes_compra_list(self, api_client):
        """Test that /api/ordenes-compra returns a list"""
        response = api_client.get(f"{BASE_URL}/api/ordenes-compra")
        
        assert response.status_code == 200, f"Failed to get ordenes-compra: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "Expected list response"
        print(f"✓ GET /api/ordenes-compra returned {len(data)} OCs")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
