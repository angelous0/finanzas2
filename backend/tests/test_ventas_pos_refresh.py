"""
Test suite for Ventas POS refresh endpoint and existing functionality
Iteration 15: Tests the NEW /ventas-pos/refresh endpoint behavior with ODOO_MODULE_BASE_URL empty
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Headers for different empresas
HEADERS_EMPRESA_6 = {'Content-Type': 'application/json', 'x-empresa-id': '6'}  # Has Ambission mapping
HEADERS_EMPRESA_1 = {'Content-Type': 'application/json', 'x-empresa-id': '1'}  # No mapping


class TestRefreshEndpoint:
    """POST /ventas-pos/refresh endpoint tests - ODOO_MODULE_BASE_URL is empty"""

    def test_refresh_returns_503_empresa_6_odoo_url_not_configured(self):
        """POST /ventas-pos/refresh returns 503 when ODOO_MODULE_BASE_URL is empty (empresa_id=6)"""
        response = requests.post(
            f"{BASE_URL}/api/ventas-pos/refresh",
            json={},
            headers=HEADERS_EMPRESA_6,
            params={'empresa_id': 6}
        )
        assert response.status_code == 503, f"Expected 503, got {response.status_code}: {response.text}"
        data = response.json()
        assert 'detail' in data, "Response should have detail field"
        assert 'ODOO_MODULE_BASE_URL' in data['detail'], f"Expected ODOO_MODULE_BASE_URL message, got: {data['detail']}"
        print(f"PASS: refresh returns 503 with message: {data['detail']}")

    def test_refresh_returns_503_before_checking_company_key(self):
        """POST /ventas-pos/refresh returns 503 before checking company_key when URL is missing (empresa_id=1)"""
        response = requests.post(
            f"{BASE_URL}/api/ventas-pos/refresh",
            json={},
            headers=HEADERS_EMPRESA_1,
            params={'empresa_id': 1}
        )
        # Should return 503 for missing ODOO_MODULE_BASE_URL, NOT 400 for missing company_key
        # Because ODOO_MODULE_BASE_URL check happens BEFORE company_key check
        assert response.status_code == 503, f"Expected 503, got {response.status_code}: {response.text}"
        data = response.json()
        assert 'ODOO_MODULE_BASE_URL' in data.get('detail', ''), f"Expected ODOO_MODULE_BASE_URL error first, got: {data}"
        print(f"PASS: refresh returns 503 before checking company_key: {data['detail']}")

    def test_refresh_with_date_params(self):
        """POST /ventas-pos/refresh accepts desde/hasta params but still returns 503"""
        response = requests.post(
            f"{BASE_URL}/api/ventas-pos/refresh",
            json={'desde': '2025-12-01', 'hasta': '2026-03-10'},
            headers=HEADERS_EMPRESA_6,
            params={'empresa_id': 6}
        )
        assert response.status_code == 503, f"Expected 503 even with date params"
        print("PASS: refresh with date params still returns 503 when URL not configured")


class TestVentasPOSListExisting:
    """GET /ventas-pos existing functionality - should still work"""

    def test_list_ventas_pos_paginated_empresa_6(self):
        """GET /ventas-pos returns paginated data for empresa_id=6"""
        response = requests.get(
            f"{BASE_URL}/api/ventas-pos",
            headers=HEADERS_EMPRESA_6,
            params={
                'empresa_id': 6,
                'fecha_desde': '2025-12-01',
                'fecha_hasta': '2026-03-10',
                'page': 1,
                'page_size': 50
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Check paginated response structure
        assert 'data' in data, "Response should have 'data' field"
        assert 'total' in data, "Response should have 'total' field"
        assert 'page' in data, "Response should have 'page' field"
        assert 'page_size' in data, "Response should have 'page_size' field"
        assert 'total_pages' in data, "Response should have 'total_pages' field"
        assert 'max_date_order' in data, "Response should have 'max_date_order' field"
        
        # Check we get data
        assert data['total'] > 0, "Should have records in date range"
        assert len(data['data']) > 0, "Should have data array with items"
        print(f"PASS: GET /ventas-pos returns {data['total']} total records, {len(data['data'])} on page 1")

    def test_list_ventas_pos_missing_company_key_empresa_1(self):
        """GET /ventas-pos returns MISSING_ODOO_COMPANY_KEY for empresa_id=1"""
        response = requests.get(
            f"{BASE_URL}/api/ventas-pos",
            headers=HEADERS_EMPRESA_1,
            params={'empresa_id': 1}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Check error_code structure
        assert data.get('error_code') == 'MISSING_ODOO_COMPANY_KEY', f"Expected error_code, got: {data}"
        assert 'message' in data, "Should have message field"
        assert data['data'] == [], "data should be empty array"
        assert data['total'] == 0, "total should be 0"
        print(f"PASS: empresa_id=1 returns MISSING_ODOO_COMPANY_KEY: {data['message']}")

    def test_pagination_page_1_vs_page_2(self):
        """GET /ventas-pos pagination - page 1 and page 2 return different data"""
        params_page1 = {
            'empresa_id': 6,
            'fecha_desde': '2025-12-01',
            'fecha_hasta': '2026-03-10',
            'page': 1,
            'page_size': 10
        }
        params_page2 = {
            **params_page1,
            'page': 2
        }
        
        response1 = requests.get(f"{BASE_URL}/api/ventas-pos", headers=HEADERS_EMPRESA_6, params=params_page1)
        response2 = requests.get(f"{BASE_URL}/api/ventas-pos", headers=HEADERS_EMPRESA_6, params=params_page2)
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        data1 = response1.json()
        data2 = response2.json()
        
        if data1['total_pages'] > 1:
            # Get first IDs from each page
            ids_page1 = [v['id'] for v in data1['data']]
            ids_page2 = [v['id'] for v in data2['data']]
            assert ids_page1 != ids_page2, "Page 1 and Page 2 should have different data"
            print(f"PASS: Pagination works - Page 1 IDs: {ids_page1[:3]}... Page 2 IDs: {ids_page2[:3]}...")
        else:
            print("PASS: Only 1 page of data, pagination not needed")

    def test_max_date_order_field_present(self):
        """GET /ventas-pos response includes max_date_order field"""
        response = requests.get(
            f"{BASE_URL}/api/ventas-pos",
            headers=HEADERS_EMPRESA_6,
            params={
                'empresa_id': 6,
                'fecha_desde': '2025-12-01',
                'fecha_hasta': '2026-03-10'
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert 'max_date_order' in data, "Response should include max_date_order"
        assert data['max_date_order'] is not None, "max_date_order should have a value"
        print(f"PASS: max_date_order = {data['max_date_order']}")


class TestVentasPOSLineas:
    """GET /ventas-pos/{order_id}/lineas - product lines endpoint"""

    def test_get_lineas_for_order(self):
        """GET /ventas-pos/{order_id}/lineas returns product lines"""
        # First get an order
        response = requests.get(
            f"{BASE_URL}/api/ventas-pos",
            headers=HEADERS_EMPRESA_6,
            params={
                'empresa_id': 6,
                'fecha_desde': '2025-12-01',
                'fecha_hasta': '2026-03-10',
                'page': 1,
                'page_size': 1
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        if len(data['data']) > 0:
            order_id = data['data'][0]['id']
            
            # Get lineas for this order
            lineas_response = requests.get(
                f"{BASE_URL}/api/ventas-pos/{order_id}/lineas",
                headers=HEADERS_EMPRESA_6,
                params={'empresa_id': 6}
            )
            assert lineas_response.status_code == 200, f"Expected 200, got {lineas_response.status_code}"
            lineas = lineas_response.json()
            assert isinstance(lineas, list), "Response should be a list"
            print(f"PASS: GET /ventas-pos/{order_id}/lineas returned {len(lineas)} product lines")
        else:
            pytest.skip("No orders found to test lineas endpoint")


class TestVentasPOSPagos:
    """GET /ventas-pos/{order_id}/pagos endpoint"""

    def test_get_pagos_for_order(self):
        """GET /ventas-pos/{order_id}/pagos returns pagos array"""
        # First get an order
        response = requests.get(
            f"{BASE_URL}/api/ventas-pos",
            headers=HEADERS_EMPRESA_6,
            params={
                'empresa_id': 6,
                'fecha_desde': '2025-12-01',
                'fecha_hasta': '2026-03-10',
                'page': 1,
                'page_size': 1
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        if len(data['data']) > 0:
            order_id = data['data'][0]['id']
            
            # Get pagos for this order
            pagos_response = requests.get(
                f"{BASE_URL}/api/ventas-pos/{order_id}/pagos",
                headers=HEADERS_EMPRESA_6,
                params={'empresa_id': 6}
            )
            assert pagos_response.status_code == 200, f"Expected 200, got {pagos_response.status_code}"
            pagos = pagos_response.json()
            assert isinstance(pagos, list), "Response should be a list"
            print(f"PASS: GET /ventas-pos/{order_id}/pagos returned {len(pagos)} pagos")
        else:
            pytest.skip("No orders found to test pagos endpoint")


class TestOdooCompanyMapConfig:
    """PUT /config/odoo-company-map endpoint"""

    def test_config_odoo_company_map_still_works(self):
        """PUT /config/odoo-company-map updates mapping (test read then restore)"""
        # First read current
        get_response = requests.get(
            f"{BASE_URL}/api/config/odoo-company-map",
            headers=HEADERS_EMPRESA_6,
            params={'empresa_id': 6}
        )
        assert get_response.status_code == 200
        original = get_response.json()
        print(f"Current mapping: {original}")
        
        # Update to same value (safe operation)
        if original.get('company_key'):
            put_response = requests.put(
                f"{BASE_URL}/api/config/odoo-company-map",
                json={'company_key': original['company_key']},
                headers=HEADERS_EMPRESA_6,
                params={'empresa_id': 6}
            )
            assert put_response.status_code == 200
            print(f"PASS: PUT /config/odoo-company-map works, company_key={original['company_key']}")
        else:
            pytest.skip("No company_key configured for empresa_id=6")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
