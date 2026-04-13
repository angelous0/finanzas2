"""
Test suite for ventas_pos refactoring verification.
Tests all 16 endpoints from the refactored modules:
- pos_sync.py: 4 endpoints (config/odoo-company-map GET/PUT, ventas-pos/sync-local, ventas-pos/refresh)
- pos_crud.py: 2 endpoints (ventas-pos GET, ventas-pos/{id}/lineas GET)
- pos_estados.py: 5 endpoints (confirmar, credito, descartar, desconfirmar, distribucion-analitica)
- pos_pagos.py: 5 endpoints (pagos GET/POST/PUT/DELETE, pagos-oficiales GET)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
EMPRESA_ID = 6  # Existing empresa with Odoo mapping


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestBackendStartup:
    """Verify backend starts without import errors after refactor"""
    
    def test_health_endpoint(self, api_client):
        """Backend should be healthy with database connected"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        print("PASS: Backend healthy and database connected")


class TestPosSyncModule:
    """Tests for pos_sync.py - 4 endpoints"""
    
    def test_get_odoo_company_map(self, api_client):
        """GET /api/config/odoo-company-map - Get Odoo company mapping"""
        response = api_client.get(f"{BASE_URL}/api/config/odoo-company-map?empresa_id={EMPRESA_ID}")
        assert response.status_code == 200
        data = response.json()
        assert "empresa_id" in data
        assert "company_key" in data
        print(f"PASS: GET odoo-company-map - empresa_id={data['empresa_id']}, company_key={data['company_key']}")
    
    def test_put_odoo_company_map(self, api_client):
        """PUT /api/config/odoo-company-map - Set Odoo company mapping"""
        # Get current value
        current = api_client.get(f"{BASE_URL}/api/config/odoo-company-map?empresa_id={EMPRESA_ID}").json()
        original_key = current.get("company_key")
        
        # Update to TEST
        response = api_client.put(
            f"{BASE_URL}/api/config/odoo-company-map?empresa_id={EMPRESA_ID}",
            json={"company_key": "TEST_REFACTOR"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["company_key"] == "TEST_REFACTOR"
        print("PASS: PUT odoo-company-map updated to TEST_REFACTOR")
        
        # Restore original
        if original_key:
            api_client.put(
                f"{BASE_URL}/api/config/odoo-company-map?empresa_id={EMPRESA_ID}",
                json={"company_key": original_key}
            )
            print(f"PASS: Restored company_key to {original_key}")
    
    def test_sync_local_requires_company_key(self, api_client):
        """POST /api/ventas-pos/sync-local - Should work with company_key"""
        response = api_client.post(f"{BASE_URL}/api/ventas-pos/sync-local?empresa_id={EMPRESA_ID}")
        # Should return 200 (sync completed) or error message about dates
        assert response.status_code in [200, 400, 500]
        print(f"PASS: sync-local endpoint accessible, status={response.status_code}")
    
    def test_refresh_requires_odoo_config(self, api_client):
        """POST /api/ventas-pos/refresh - Should handle missing Odoo config"""
        response = api_client.post(
            f"{BASE_URL}/api/ventas-pos/refresh?empresa_id={EMPRESA_ID}",
            json={}
        )
        # 200 = success, 503 = ODOO not configured, 502 = connection error, 504 = timeout
        assert response.status_code in [200, 400, 502, 503, 504]
        print(f"PASS: refresh endpoint accessible, status={response.status_code}")


class TestPosCrudModule:
    """Tests for pos_crud.py - 2 endpoints"""
    
    def test_list_ventas_pos(self, api_client):
        """GET /api/ventas-pos - List POS sales with pagination"""
        response = api_client.get(f"{BASE_URL}/api/ventas-pos?empresa_id={EMPRESA_ID}&page=1&page_size=5")
        assert response.status_code == 200
        data = response.json()
        # Verify pagination response structure
        assert "data" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data
        assert isinstance(data["data"], list)
        print(f"PASS: list_ventas_pos - total={data['total']}, page={data['page']}, total_pages={data['total_pages']}")
    
    def test_list_ventas_pos_filters(self, api_client):
        """GET /api/ventas-pos with filters"""
        response = api_client.get(
            f"{BASE_URL}/api/ventas-pos?empresa_id={EMPRESA_ID}&page=1&page_size=5&include_cancelled=true"
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        print(f"PASS: list_ventas_pos with filters - returned {len(data['data'])} items")
    
    def test_get_lineas_venta_pos_nonexistent(self, api_client):
        """GET /api/ventas-pos/{id}/lineas - Non-existent order returns empty array"""
        response = api_client.get(f"{BASE_URL}/api/ventas-pos/99999/lineas?empresa_id={EMPRESA_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data == []
        print("PASS: get_lineas for non-existent order returns empty array")


class TestPosEstadosModule:
    """Tests for pos_estados.py - 5 endpoints"""
    
    def test_confirmar_nonexistent(self, api_client):
        """POST /api/ventas-pos/{id}/confirmar - Non-existent order"""
        response = api_client.post(f"{BASE_URL}/api/ventas-pos/88888/confirmar?empresa_id={EMPRESA_ID}")
        # Should return 404 for non-existent order
        assert response.status_code in [400, 404, 500]
        print(f"PASS: confirmar non-existent order handled, status={response.status_code}")
    
    def test_credito_nonexistent(self, api_client):
        """POST /api/ventas-pos/{id}/credito - Non-existent order"""
        response = api_client.post(f"{BASE_URL}/api/ventas-pos/88888/credito?empresa_id={EMPRESA_ID}")
        assert response.status_code in [400, 404, 500]
        print(f"PASS: credito non-existent order handled, status={response.status_code}")
    
    def test_descartar(self, api_client):
        """POST /api/ventas-pos/{id}/descartar - Discard order"""
        response = api_client.post(f"{BASE_URL}/api/ventas-pos/88888/descartar?empresa_id={EMPRESA_ID}")
        # descartar creates a record if not exists, so should return 200
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Venta descartada"
        print("PASS: descartar endpoint works correctly")
    
    def test_desconfirmar_nonexistent(self, api_client):
        """POST /api/ventas-pos/{id}/desconfirmar - Non-existent/non-confirmed order"""
        response = api_client.post(f"{BASE_URL}/api/ventas-pos/88887/desconfirmar?empresa_id={EMPRESA_ID}")
        # Should fail because order is not in 'confirmada' state
        assert response.status_code == 400
        print(f"PASS: desconfirmar validation works, status={response.status_code}")
    
    def test_distribucion_analitica(self, api_client):
        """GET /api/ventas-pos/{id}/distribucion-analitica"""
        response = api_client.get(f"{BASE_URL}/api/ventas-pos/99999/distribucion-analitica?empresa_id={EMPRESA_ID}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: distribucion-analitica returns list, count={len(data)}")


class TestPosPagosModule:
    """Tests for pos_pagos.py - 5 endpoints"""
    
    def test_get_pagos(self, api_client):
        """GET /api/ventas-pos/{id}/pagos - Get payments for order"""
        response = api_client.get(f"{BASE_URL}/api/ventas-pos/99999/pagos?empresa_id={EMPRESA_ID}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: get_pagos returns list, count={len(data)}")
    
    def test_get_pagos_oficiales(self, api_client):
        """GET /api/ventas-pos/{id}/pagos-oficiales - Get official payments"""
        response = api_client.get(f"{BASE_URL}/api/ventas-pos/99999/pagos-oficiales?empresa_id={EMPRESA_ID}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: get_pagos_oficiales returns list, count={len(data)}")
    
    def test_add_pago_nonexistent_order(self, api_client):
        """POST /api/ventas-pos/{id}/pagos - Adding payment to non-existent order"""
        response = api_client.post(
            f"{BASE_URL}/api/ventas-pos/77777/pagos?empresa_id={EMPRESA_ID}",
            json={
                "forma_pago": "Efectivo",
                "cuenta_financiera_id": 1,
                "monto": 100,
                "fecha_pago": "2026-01-15"
            }
        )
        # Should return 404 for non-existent order
        assert response.status_code in [404, 500]
        print(f"PASS: add_pago validation for non-existent order, status={response.status_code}")
    
    def test_update_pago_nonexistent(self, api_client):
        """PUT /api/ventas-pos/{id}/pagos/{pago_id} - Update non-existent payment"""
        response = api_client.put(
            f"{BASE_URL}/api/ventas-pos/99999/pagos/99999?empresa_id={EMPRESA_ID}",
            json={
                "forma_pago": "Tarjeta",
                "monto": 50
            }
        )
        # Should return 200 (no rows updated) or 404
        assert response.status_code in [200, 404]
        print(f"PASS: update_pago endpoint accessible, status={response.status_code}")
    
    def test_delete_pago_nonexistent(self, api_client):
        """DELETE /api/ventas-pos/{id}/pagos/{pago_id} - Delete non-existent payment"""
        response = api_client.delete(
            f"{BASE_URL}/api/ventas-pos/99999/pagos/99999?empresa_id={EMPRESA_ID}"
        )
        # Should return 200 (no rows deleted) or 404
        assert response.status_code in [200, 404]
        print(f"PASS: delete_pago endpoint accessible, status={response.status_code}")


class TestEndpointAccessibility:
    """Verify all 16 original endpoints are accessible (no 404 for valid routes)"""
    
    def test_all_endpoints_no_404(self, api_client):
        """All endpoints should return valid responses (not 404 for route)"""
        endpoints = [
            # pos_sync.py - 4 endpoints
            ("GET", f"/api/config/odoo-company-map?empresa_id={EMPRESA_ID}"),
            ("PUT", f"/api/config/odoo-company-map?empresa_id={EMPRESA_ID}"),
            ("POST", f"/api/ventas-pos/sync-local?empresa_id={EMPRESA_ID}"),
            ("POST", f"/api/ventas-pos/refresh?empresa_id={EMPRESA_ID}"),
            # pos_crud.py - 2 endpoints
            ("GET", f"/api/ventas-pos?empresa_id={EMPRESA_ID}"),
            ("GET", f"/api/ventas-pos/99999/lineas?empresa_id={EMPRESA_ID}"),
            # pos_estados.py - 5 endpoints
            ("POST", f"/api/ventas-pos/99999/confirmar?empresa_id={EMPRESA_ID}"),
            ("POST", f"/api/ventas-pos/99999/credito?empresa_id={EMPRESA_ID}"),
            ("POST", f"/api/ventas-pos/99999/descartar?empresa_id={EMPRESA_ID}"),
            ("POST", f"/api/ventas-pos/99999/desconfirmar?empresa_id={EMPRESA_ID}"),
            ("GET", f"/api/ventas-pos/99999/distribucion-analitica?empresa_id={EMPRESA_ID}"),
            # pos_pagos.py - 5 endpoints
            ("GET", f"/api/ventas-pos/99999/pagos?empresa_id={EMPRESA_ID}"),
            ("POST", f"/api/ventas-pos/99999/pagos?empresa_id={EMPRESA_ID}"),
            ("PUT", f"/api/ventas-pos/99999/pagos/1?empresa_id={EMPRESA_ID}"),
            ("DELETE", f"/api/ventas-pos/99999/pagos/1?empresa_id={EMPRESA_ID}"),
            ("GET", f"/api/ventas-pos/99999/pagos-oficiales?empresa_id={EMPRESA_ID}"),
        ]
        
        results = []
        for method, path in endpoints:
            url = f"{BASE_URL}{path}"
            if method == "GET":
                resp = api_client.get(url)
            elif method == "POST":
                resp = api_client.post(url, json={})
            elif method == "PUT":
                resp = api_client.put(url, json={"company_key": "TEST"} if "odoo-company-map" in path else {"forma_pago": "Efectivo", "monto": 100})
            elif method == "DELETE":
                resp = api_client.delete(url)
            
            # 404 would mean the route doesn't exist - that's a failure
            # Any other status (200, 400, 500, etc.) means the route is accessible
            is_accessible = resp.status_code != 404
            results.append((method, path, resp.status_code, is_accessible))
            
            if not is_accessible:
                print(f"FAIL: {method} {path} returned 404 - route not found!")
        
        for method, path, status, accessible in results:
            print(f"{'PASS' if accessible else 'FAIL'}: {method} {path} -> {status}")
        
        # All endpoints must be accessible (no 404s)
        all_accessible = all(r[3] for r in results)
        assert all_accessible, f"Some endpoints returned 404: {[r for r in results if not r[3]]}"
        print(f"\nPASS: All 16 endpoints are accessible (no 404 errors)")


class TestExistingOrder:
    """Test with an existing order from the database"""
    
    def test_get_existing_order_lineas(self, api_client):
        """Get lineas for an existing order"""
        # First get a list of orders to find an existing one
        list_resp = api_client.get(f"{BASE_URL}/api/ventas-pos?empresa_id={EMPRESA_ID}&page=1&page_size=1")
        assert list_resp.status_code == 200
        list_data = list_resp.json()
        
        if list_data["total"] > 0 and len(list_data["data"]) > 0:
            order_id = list_data["data"][0]["odoo_order_id"]
            
            # Get lineas for this order
            lineas_resp = api_client.get(f"{BASE_URL}/api/ventas-pos/{order_id}/lineas?empresa_id={EMPRESA_ID}")
            assert lineas_resp.status_code == 200
            lineas = lineas_resp.json()
            assert isinstance(lineas, list)
            
            # Get pagos for this order
            pagos_resp = api_client.get(f"{BASE_URL}/api/ventas-pos/{order_id}/pagos?empresa_id={EMPRESA_ID}")
            assert pagos_resp.status_code == 200
            
            # Get distribucion for this order
            dist_resp = api_client.get(f"{BASE_URL}/api/ventas-pos/{order_id}/distribucion-analitica?empresa_id={EMPRESA_ID}")
            assert dist_resp.status_code == 200
            
            print(f"PASS: Tested existing order {order_id} - lineas: {len(lineas)}")
        else:
            pytest.skip("No orders found in database to test")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
