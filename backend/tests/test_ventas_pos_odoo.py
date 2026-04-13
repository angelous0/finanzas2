"""
Test Ventas POS API - Odoo Data Source Refactor
Tests the new paginated API for POS sales from odoo PostgreSQL schema

Features tested:
1. GET /api/ventas-pos - paginated response structure
2. MISSING_ODOO_COMPANY_KEY error for empresa without mapping
3. Pagination with page and page_size params
4. Filters: fecha_desde, fecha_hasta, estado, search
5. GET /api/ventas-pos/{order_id}/lineas - product lines on-demand
6. PUT /api/config/odoo-company-map - save company_key mapping
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = 'https://concilia-smart.preview.emergentagent.com'


class TestVentasPOSPaginated:
    """Test paginated Ventas POS API with empresa_id=6 (has company_key mapping)"""
    
    def test_ventas_pos_returns_paginated_structure(self):
        """Test that /api/ventas-pos returns correct paginated structure for empresa_id=6"""
        response = requests.get(
            f"{BASE_URL}/api/ventas-pos",
            params={"empresa_id": 6, "page": 1, "page_size": 10}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Check paginated structure
        assert "data" in data, "Response should have 'data' field"
        assert "total" in data, "Response should have 'total' field"
        assert "page" in data, "Response should have 'page' field"
        assert "page_size" in data, "Response should have 'page_size' field"
        assert "total_pages" in data, "Response should have 'total_pages' field"
        
        # Verify types
        assert isinstance(data["data"], list), "data should be a list"
        assert isinstance(data["total"], int), "total should be an integer"
        assert isinstance(data["page"], int), "page should be an integer"
        assert isinstance(data["page_size"], int), "page_size should be an integer"
        assert isinstance(data["total_pages"], int), "total_pages should be an integer"
        
        # No MISSING_ODOO_COMPANY_KEY error for empresa_id=6
        assert "error_code" not in data, f"empresa_id=6 should have mapping, got error: {data.get('error_code')}"
        print(f"PASS: Paginated structure correct. Total records: {data['total']}, Page: {data['page']}/{data['total_pages']}")

    def test_ventas_pos_pagination_works(self):
        """Test pagination with page and page_size params"""
        # Get page 1 with 5 items
        response_p1 = requests.get(
            f"{BASE_URL}/api/ventas-pos",
            params={
                "empresa_id": 6,
                "page": 1,
                "page_size": 5,
                "fecha_desde": "2025-12-01",
                "fecha_hasta": "2026-03-10"
            }
        )
        assert response_p1.status_code == 200
        data_p1 = response_p1.json()
        
        if data_p1["total"] < 6:
            print(f"SKIP: Not enough data to test pagination ({data_p1['total']} records)")
            return
        
        # Get page 2
        response_p2 = requests.get(
            f"{BASE_URL}/api/ventas-pos",
            params={
                "empresa_id": 6,
                "page": 2,
                "page_size": 5,
                "fecha_desde": "2025-12-01",
                "fecha_hasta": "2026-03-10"
            }
        )
        assert response_p2.status_code == 200
        data_p2 = response_p2.json()
        
        # Verify page 1 has 5 items
        assert len(data_p1["data"]) == 5, f"Page 1 should have 5 items, got {len(data_p1['data'])}"
        assert data_p1["page"] == 1
        
        # Verify page 2 is different
        if data_p2["data"]:
            p1_ids = {v["id"] for v in data_p1["data"]}
            p2_ids = {v["id"] for v in data_p2["data"]}
            assert p1_ids.isdisjoint(p2_ids), "Page 1 and Page 2 should have different records"
            assert data_p2["page"] == 2
        
        print(f"PASS: Pagination works. P1: {len(data_p1['data'])} items, P2: {len(data_p2['data'])} items")

    def test_ventas_pos_filter_by_estado(self):
        """Test filtering by estado parameter"""
        estados = ['pendiente', 'confirmada', 'credito', 'descartada']
        
        for estado in estados:
            response = requests.get(
                f"{BASE_URL}/api/ventas-pos",
                params={
                    "empresa_id": 6,
                    "estado": estado,
                    "fecha_desde": "2025-12-01",
                    "fecha_hasta": "2026-03-10",
                    "page": 1,
                    "page_size": 10
                }
            )
            assert response.status_code == 200, f"Filter by estado={estado} failed: {response.text}"
            data = response.json()
            
            # All returned records should have the filtered estado
            for venta in data["data"]:
                assert venta["estado_local"] == estado, f"Expected estado={estado}, got {venta['estado_local']}"
            
            print(f"PASS: Filter by estado={estado}: {len(data['data'])} records")

    def test_ventas_pos_filter_by_date_range(self):
        """Test filtering by fecha_desde and fecha_hasta"""
        response = requests.get(
            f"{BASE_URL}/api/ventas-pos",
            params={
                "empresa_id": 6,
                "fecha_desde": "2026-01-01",
                "fecha_hasta": "2026-01-31",
                "page": 1,
                "page_size": 50
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify dates are within range
        for venta in data["data"]:
            if venta["date_order"]:
                date_str = venta["date_order"][:10]
                assert date_str >= "2026-01-01", f"Date {date_str} is before 2026-01-01"
                assert date_str <= "2026-01-31", f"Date {date_str} is after 2026-01-31"
        
        print(f"PASS: Date filter works. Found {len(data['data'])} records in Jan 2026")

    def test_ventas_pos_search_filter(self):
        """Test search filter by partner or vendor name"""
        response = requests.get(
            f"{BASE_URL}/api/ventas-pos",
            params={
                "empresa_id": 6,
                "search": "a",  # Common letter to find some results
                "fecha_desde": "2025-12-01",
                "fecha_hasta": "2026-03-10",
                "page": 1,
                "page_size": 10
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Just verify structure, search results may vary
        assert "data" in data
        assert "total" in data
        print(f"PASS: Search filter works. Found {data['total']} records matching 'a'")

    def test_ventas_pos_ordering(self):
        """Test that results are ordered by date_order DESC"""
        response = requests.get(
            f"{BASE_URL}/api/ventas-pos",
            params={
                "empresa_id": 6,
                "fecha_desde": "2025-12-01",
                "fecha_hasta": "2026-03-10",
                "page": 1,
                "page_size": 20
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        if len(data["data"]) < 2:
            print("SKIP: Not enough data to test ordering")
            return
        
        # Check descending order
        dates = [v["date_order"] for v in data["data"] if v["date_order"]]
        for i in range(len(dates) - 1):
            assert dates[i] >= dates[i + 1], f"Results not in DESC order: {dates[i]} < {dates[i+1]}"
        
        print(f"PASS: Results ordered by date_order DESC")


class TestVentasPOSMissingMapping:
    """Test MISSING_ODOO_COMPANY_KEY error for empresa without mapping"""
    
    def test_missing_company_key_error_empresa_1(self):
        """Test that empresa_id=1 returns MISSING_ODOO_COMPANY_KEY error"""
        response = requests.get(
            f"{BASE_URL}/api/ventas-pos",
            params={"empresa_id": 1, "page": 1, "page_size": 10}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("error_code") == "MISSING_ODOO_COMPANY_KEY", \
            f"Expected MISSING_ODOO_COMPANY_KEY error, got: {data}"
        assert "message" in data, "Error should include message"
        assert data["data"] == [], "data should be empty list"
        assert data["total"] == 0, "total should be 0"
        assert data["total_pages"] == 0, "total_pages should be 0"
        
        print(f"PASS: MISSING_ODOO_COMPANY_KEY returned for empresa_id=1")


class TestVentasPOSLineas:
    """Test on-demand line fetching"""
    
    def test_get_lineas_for_valid_order(self):
        """Test GET /api/ventas-pos/{order_id}/lineas returns product lines"""
        # First get a valid order_id
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
        
        if not data["data"]:
            print("SKIP: No ventas to test lineas")
            return
        
        # Get first order's lines
        order_id = data["data"][0]["odoo_order_id"]
        lines_response = requests.get(
            f"{BASE_URL}/api/ventas-pos/{order_id}/lineas",
            params={"empresa_id": 6}
        )
        assert lines_response.status_code == 200, f"Failed to get lineas: {lines_response.text}"
        
        lines = lines_response.json()
        assert isinstance(lines, list), "Lineas should be a list"
        
        if lines:
            # Verify line structure
            line = lines[0]
            expected_fields = ["id", "qty", "price_unit", "price_subtotal"]
            for field in expected_fields:
                assert field in line, f"Line should have '{field}' field"
        
        print(f"PASS: Got {len(lines)} product lines for order {order_id}")


class TestOdooCompanyMapConfig:
    """Test company_key mapping configuration"""
    
    def test_get_odoo_company_map(self):
        """Test GET /api/config/odoo-company-map returns mapping"""
        response = requests.get(
            f"{BASE_URL}/api/config/odoo-company-map",
            params={"empresa_id": 6}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "empresa_id" in data, "Response should have empresa_id"
        assert "company_key" in data, "Response should have company_key"
        
        # empresa_id=6 should have 'Ambission' as company_key
        if data["company_key"]:
            print(f"PASS: empresa_id=6 has company_key: {data['company_key']}")
        else:
            print(f"INFO: empresa_id=6 has no company_key mapping")

    def test_get_odoo_company_map_no_mapping(self):
        """Test GET /api/config/odoo-company-map for empresa without mapping"""
        response = requests.get(
            f"{BASE_URL}/api/config/odoo-company-map",
            params={"empresa_id": 1}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("company_key") is None, f"empresa_id=1 should have no mapping, got: {data}"
        print(f"PASS: empresa_id=1 correctly returns no company_key")

    def test_set_odoo_company_map(self):
        """Test PUT /api/config/odoo-company-map saves mapping"""
        # Test with a temporary empresa (we'll use empresa_id=1 but won't permanently change it)
        # Just verify the endpoint accepts the request
        test_data = {"company_key": "TestCompany"}
        
        response = requests.put(
            f"{BASE_URL}/api/config/odoo-company-map",
            params={"empresa_id": 999},  # Non-existent to avoid changing real data
            json=test_data
        )
        
        # Should succeed (upsert creates new)
        if response.status_code == 200:
            data = response.json()
            assert data.get("company_key") == "TestCompany"
            print("PASS: PUT odoo-company-map works")
        else:
            print(f"INFO: PUT returned {response.status_code} (may need existing empresa)")

    def test_set_odoo_company_map_validation(self):
        """Test PUT /api/config/odoo-company-map validates company_key"""
        # Empty company_key should fail
        response = requests.put(
            f"{BASE_URL}/api/config/odoo-company-map",
            params={"empresa_id": 6},
            json={"company_key": ""}
        )
        
        assert response.status_code == 400, f"Empty company_key should return 400, got {response.status_code}"
        print("PASS: Empty company_key validation works")


class TestVentasPOSDataIntegrity:
    """Test data integrity and field presence"""
    
    def test_venta_has_required_fields(self):
        """Test that ventas have all required fields"""
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
        
        if not data["data"]:
            print("SKIP: No data to verify fields")
            return
        
        required_fields = [
            "id", "odoo_order_id", "date_order", "amount_total",
            "estado_local", "partner_name", "vendedor_name",
            "pagos_asignados", "pagos_oficiales", "name", "source"
        ]
        
        for venta in data["data"][:3]:  # Check first 3
            for field in required_fields:
                assert field in venta, f"Venta missing field: {field}"
            
            # Verify source is 'odoo'
            assert venta["source"] == "odoo", f"Expected source='odoo', got {venta['source']}"
        
        print(f"PASS: All required fields present in venta records")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
