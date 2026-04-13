"""
Test Ventas POS after dead code cleanup - iteration 16

This test verifies NOTHING BROKE after removing:
1. odoo_service.py file
2. _list_from_legacy() function  
3. POST /ventas-pos/sync deprecated endpoint
4. syncVentasPOS export from api.js
5. unused List import

Tests:
- POST /api/ventas-pos/sync should return 404 (endpoint removed)
- GET /api/ventas-pos still works with empresa_id=6
- GET /api/ventas-pos returns MISSING_ODOO_COMPANY_KEY for empresa_id=1
- Pagination works
- max_date_order field present
- GET /api/ventas-pos/{order_id}/lineas works
- POST /api/ventas-pos/refresh returns 503 (ODOO_MODULE_BASE_URL not configured)
- GET /api/ventas-pos/{order_id}/pagos works
- PUT /api/ventas-pos/{order_id}/confirmar works or returns appropriate error
- GET /api/config/odoo-company-map works
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestVentasPOSCleanup:
    """Tests to verify dead code cleanup didn't break anything"""

    # === TEST 1: Removed endpoint returns 404 ===
    def test_sync_endpoint_removed_returns_404(self):
        """POST /api/ventas-pos/sync should return 404 (endpoint was removed)"""
        response = requests.post(
            f"{BASE_URL}/api/ventas-pos/sync",
            headers={"x-empresa-id": "6"},
            json={}
        )
        assert response.status_code == 404, f"Expected 404 for removed /sync endpoint, got {response.status_code}"
        print("PASS: POST /api/ventas-pos/sync returns 404 (endpoint correctly removed)")

    # === TEST 2: GET /api/ventas-pos still works for empresa_id=6 ===
    def test_get_ventas_pos_empresa_6(self):
        """GET /api/ventas-pos returns paginated data for empresa_id=6"""
        response = requests.get(
            f"{BASE_URL}/api/ventas-pos",
            params={
                "empresa_id": 6,
                "fecha_desde": "2025-12-01",
                "fecha_hasta": "2026-03-10"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Verify response structure
        assert "data" in data, "Missing 'data' field"
        assert "total" in data, "Missing 'total' field"
        assert "page" in data, "Missing 'page' field"
        assert "page_size" in data, "Missing 'page_size' field"
        assert "total_pages" in data, "Missing 'total_pages' field"
        assert "max_date_order" in data, "Missing 'max_date_order' field"
        
        # Verify data has records
        assert data["total"] > 0, "Expected records for empresa_id=6 in date range"
        assert len(data["data"]) > 0, "Expected data array to have items"
        
        print(f"PASS: GET /api/ventas-pos returns {data['total']} records for empresa_id=6")

    # === TEST 3: GET /api/ventas-pos returns MISSING_ODOO_COMPANY_KEY for empresa_id=1 ===
    def test_get_ventas_pos_missing_company_key(self):
        """GET /api/ventas-pos returns MISSING_ODOO_COMPANY_KEY for empresa_id=1"""
        response = requests.get(
            f"{BASE_URL}/api/ventas-pos",
            params={"empresa_id": 1}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert data.get("error_code") == "MISSING_ODOO_COMPANY_KEY", \
            f"Expected error_code='MISSING_ODOO_COMPANY_KEY', got {data.get('error_code')}"
        assert data.get("data") == [], "Expected empty data array"
        assert data.get("total") == 0, "Expected total=0"
        
        print("PASS: GET /api/ventas-pos returns MISSING_ODOO_COMPANY_KEY for empresa_id=1")

    # === TEST 4: Pagination works ===
    def test_pagination_page_size(self):
        """GET /api/ventas-pos pagination: page=1&page_size=5 returns 5 items"""
        response = requests.get(
            f"{BASE_URL}/api/ventas-pos",
            params={
                "empresa_id": 6,
                "fecha_desde": "2025-12-01",
                "fecha_hasta": "2026-03-10",
                "page": 1,
                "page_size": 5
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["data"]) == 5, f"Expected 5 items with page_size=5, got {len(data['data'])}"
        assert data["page_size"] == 5, "Expected page_size=5 in response"
        
        print("PASS: Pagination returns correct number of items (5)")

    # === TEST 5: max_date_order field present ===
    def test_max_date_order_present(self):
        """GET /api/ventas-pos max_date_order field is present"""
        response = requests.get(
            f"{BASE_URL}/api/ventas-pos",
            params={
                "empresa_id": 6,
                "fecha_desde": "2025-12-01",
                "fecha_hasta": "2026-03-10"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "max_date_order" in data, "Missing max_date_order field"
        assert data["max_date_order"] is not None, "max_date_order should not be None"
        
        print(f"PASS: max_date_order present: {data['max_date_order']}")

    # === TEST 6: GET /api/ventas-pos/{order_id}/lineas returns product lines ===
    def test_get_lineas_venta_pos(self):
        """GET /api/ventas-pos/{order_id}/lineas returns product lines"""
        # First get a valid order_id from page 1
        response = requests.get(
            f"{BASE_URL}/api/ventas-pos",
            params={
                "empresa_id": 6,
                "fecha_desde": "2025-12-01",
                "fecha_hasta": "2026-03-10",
                "page": 1,
                "page_size": 1
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) > 0, "Need at least one order to test lineas"
        
        order_id = data["data"][0]["odoo_order_id"]
        
        # Get lineas for this order
        lineas_response = requests.get(
            f"{BASE_URL}/api/ventas-pos/{order_id}/lineas",
            params={"empresa_id": 6}
        )
        assert lineas_response.status_code == 200, f"Expected 200, got {lineas_response.status_code}"
        lineas = lineas_response.json()
        
        assert isinstance(lineas, list), "Expected list of product lines"
        print(f"PASS: GET /api/ventas-pos/{order_id}/lineas returns {len(lineas)} lines")

    # === TEST 7: POST /api/ventas-pos/refresh returns 503 ===
    def test_refresh_returns_503(self):
        """POST /api/ventas-pos/refresh returns 503 (ODOO_MODULE_BASE_URL not configured)"""
        response = requests.post(
            f"{BASE_URL}/api/ventas-pos/refresh",
            params={"empresa_id": 6},
            json={}
        )
        assert response.status_code == 503, f"Expected 503, got {response.status_code}"
        data = response.json()
        assert "ODOO_MODULE_BASE_URL" in str(data.get("detail", "")), \
            "Expected error message about ODOO_MODULE_BASE_URL"
        
        print("PASS: POST /api/ventas-pos/refresh returns 503 (expected - no Odoo URL configured)")

    # === TEST 8: GET /api/ventas-pos/{order_id}/pagos works ===
    def test_get_pagos_venta_pos(self):
        """GET /api/ventas-pos/{order_id}/pagos works"""
        # First get a valid order_id
        response = requests.get(
            f"{BASE_URL}/api/ventas-pos",
            params={
                "empresa_id": 6,
                "fecha_desde": "2025-12-01",
                "fecha_hasta": "2026-03-10",
                "page": 1,
                "page_size": 1
            }
        )
        assert response.status_code == 200
        data = response.json()
        order_id = data["data"][0]["odoo_order_id"]
        
        # Get pagos
        pagos_response = requests.get(
            f"{BASE_URL}/api/ventas-pos/{order_id}/pagos",
            params={"empresa_id": 6}
        )
        assert pagos_response.status_code == 200, f"Expected 200, got {pagos_response.status_code}"
        pagos = pagos_response.json()
        
        assert isinstance(pagos, list), "Expected list of pagos"
        print(f"PASS: GET /api/ventas-pos/{order_id}/pagos returns {len(pagos)} pagos")

    # === TEST 9: PUT /api/ventas-pos/{order_id}/confirmar works or returns appropriate error ===
    def test_confirmar_venta_pos(self):
        """PUT /api/ventas-pos/{order_id}/confirmar works or returns appropriate error"""
        # Get a pendiente order first
        response = requests.get(
            f"{BASE_URL}/api/ventas-pos",
            params={
                "empresa_id": 6,
                "estado": "pendiente",
                "fecha_desde": "2025-12-01",
                "fecha_hasta": "2026-03-10",
                "page": 1,
                "page_size": 1
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        if len(data["data"]) == 0:
            print("SKIP: No pendiente orders available to test confirmar")
            return
        
        order_id = data["data"][0]["odoo_order_id"]
        
        # Try to confirm - should fail if no pagos, or succeed if has pagos
        confirm_response = requests.post(
            f"{BASE_URL}/api/ventas-pos/{order_id}/confirmar",
            params={"empresa_id": 6}
        )
        
        # Accept either 200 (success) or 400 (already confirmed/no pagos)
        assert confirm_response.status_code in [200, 400], \
            f"Expected 200 or 400, got {confirm_response.status_code}"
        
        print(f"PASS: POST /api/ventas-pos/{order_id}/confirmar returned {confirm_response.status_code}")

    # === TEST 10: GET /api/config/odoo-company-map works ===
    def test_get_odoo_company_map(self):
        """GET /api/config/odoo-company-map works"""
        response = requests.get(
            f"{BASE_URL}/api/config/odoo-company-map",
            params={"empresa_id": 6}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        assert "empresa_id" in data, "Missing empresa_id in response"
        assert data["empresa_id"] == 6, f"Expected empresa_id=6, got {data['empresa_id']}"
        assert data.get("company_key") == "Ambission", f"Expected company_key='Ambission', got {data.get('company_key')}"
        
        print(f"PASS: GET /api/config/odoo-company-map returns {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
