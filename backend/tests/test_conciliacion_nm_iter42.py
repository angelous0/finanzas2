"""
Test suite for Bank Reconciliation N:1 and 1:N auto-matching feature (Iteration 42)
Tests:
- GET /api/conciliacion/sugerencias returns suggestions with tipo 1:1, 3:1, and 1:2
- Suggestions use new array format: banco_mov_ids[] and sistema_mov_ids[]
- No duplicate IDs across suggestions
- POST /api/conciliacion/confirmar-sugerencias correctly processes array-based suggestions
- GET /api/articulos-oc returns enriched article data including linea_negocio_id
- GET /api/inventario includes linea_negocio_id in the response
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
EMPRESA_ID = 7
CUENTA_FINANCIERA_ID = 13  # Test account with N:1 and 1:N scenarios


class TestConciliacionSugerenciasEndpoint:
    """Test GET /api/conciliacion/sugerencias endpoint"""
    
    def test_endpoint_returns_200(self):
        """Endpoint should return 200 OK"""
        response = requests.get(
            f"{BASE_URL}/api/conciliacion/sugerencias",
            params={"cuenta_financiera_id": CUENTA_FINANCIERA_ID, "empresa_id": EMPRESA_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASSED: Endpoint returns 200")
    
    def test_response_structure(self):
        """Response should have sugerencias, total, pendientes_banco, pendientes_sistema"""
        response = requests.get(
            f"{BASE_URL}/api/conciliacion/sugerencias",
            params={"cuenta_financiera_id": CUENTA_FINANCIERA_ID, "empresa_id": EMPRESA_ID}
        )
        data = response.json()
        assert "sugerencias" in data, "Missing 'sugerencias' key"
        assert "total" in data, "Missing 'total' key"
        assert "pendientes_banco" in data, "Missing 'pendientes_banco' key"
        assert "pendientes_sistema" in data, "Missing 'pendientes_sistema' key"
        print(f"PASSED: Response structure correct. Total: {data['total']}, Pendientes banco: {data['pendientes_banco']}, Pendientes sistema: {data['pendientes_sistema']}")
    
    def test_suggestions_use_array_format(self):
        """All suggestions should use banco_mov_ids[] and sistema_mov_ids[] arrays"""
        response = requests.get(
            f"{BASE_URL}/api/conciliacion/sugerencias",
            params={"cuenta_financiera_id": CUENTA_FINANCIERA_ID, "empresa_id": EMPRESA_ID}
        )
        data = response.json()
        for i, sug in enumerate(data["sugerencias"]):
            assert "banco_mov_ids" in sug, f"Suggestion {i} missing 'banco_mov_ids'"
            assert "sistema_mov_ids" in sug, f"Suggestion {i} missing 'sistema_mov_ids'"
            assert isinstance(sug["banco_mov_ids"], list), f"Suggestion {i} banco_mov_ids should be a list"
            assert isinstance(sug["sistema_mov_ids"], list), f"Suggestion {i} sistema_mov_ids should be a list"
            assert len(sug["banco_mov_ids"]) > 0, f"Suggestion {i} banco_mov_ids should not be empty"
            assert len(sug["sistema_mov_ids"]) > 0, f"Suggestion {i} sistema_mov_ids should not be empty"
        print(f"PASSED: All {len(data['sugerencias'])} suggestions use array format")
    
    def test_suggestions_have_tipo_field(self):
        """All suggestions should have a 'tipo' field indicating match type"""
        response = requests.get(
            f"{BASE_URL}/api/conciliacion/sugerencias",
            params={"cuenta_financiera_id": CUENTA_FINANCIERA_ID, "empresa_id": EMPRESA_ID}
        )
        data = response.json()
        tipos_found = set()
        for sug in data["sugerencias"]:
            assert "tipo" in sug, f"Suggestion missing 'tipo' field"
            tipos_found.add(sug["tipo"])
        print(f"PASSED: All suggestions have 'tipo' field. Types found: {tipos_found}")
    
    def test_has_1_to_1_matches(self):
        """Should have at least one 1:1 match"""
        response = requests.get(
            f"{BASE_URL}/api/conciliacion/sugerencias",
            params={"cuenta_financiera_id": CUENTA_FINANCIERA_ID, "empresa_id": EMPRESA_ID}
        )
        data = response.json()
        one_to_one = [s for s in data["sugerencias"] if s["tipo"] == "1:1"]
        assert len(one_to_one) > 0, "No 1:1 matches found"
        print(f"PASSED: Found {len(one_to_one)} 1:1 matches")
    
    def test_has_n_to_1_match(self):
        """Should have at least one N:1 match (multiple sistema to one banco)"""
        response = requests.get(
            f"{BASE_URL}/api/conciliacion/sugerencias",
            params={"cuenta_financiera_id": CUENTA_FINANCIERA_ID, "empresa_id": EMPRESA_ID}
        )
        data = response.json()
        n_to_1 = [s for s in data["sugerencias"] if ":" in s["tipo"] and s["tipo"].split(":")[0] != "1"]
        assert len(n_to_1) > 0, "No N:1 matches found"
        for match in n_to_1:
            assert len(match["sistema_mov_ids"]) > 1, f"N:1 match should have multiple sistema_mov_ids"
            assert len(match["banco_mov_ids"]) == 1, f"N:1 match should have single banco_mov_id"
        print(f"PASSED: Found {len(n_to_1)} N:1 matches. First one: {n_to_1[0]['tipo']}")
    
    def test_has_1_to_n_match(self):
        """Should have at least one 1:N match (multiple banco to one sistema)"""
        response = requests.get(
            f"{BASE_URL}/api/conciliacion/sugerencias",
            params={"cuenta_financiera_id": CUENTA_FINANCIERA_ID, "empresa_id": EMPRESA_ID}
        )
        data = response.json()
        one_to_n = [s for s in data["sugerencias"] if ":" in s["tipo"] and s["tipo"].split(":")[1] != "1"]
        assert len(one_to_n) > 0, "No 1:N matches found"
        for match in one_to_n:
            assert len(match["banco_mov_ids"]) > 1, f"1:N match should have multiple banco_mov_ids"
            assert len(match["sistema_mov_ids"]) == 1, f"1:N match should have single sistema_mov_id"
        print(f"PASSED: Found {len(one_to_n)} 1:N matches. First one: {one_to_n[0]['tipo']}")
    
    def test_no_duplicate_banco_ids(self):
        """Each banco movement should appear in only one suggestion"""
        response = requests.get(
            f"{BASE_URL}/api/conciliacion/sugerencias",
            params={"cuenta_financiera_id": CUENTA_FINANCIERA_ID, "empresa_id": EMPRESA_ID}
        )
        data = response.json()
        all_banco_ids = []
        for sug in data["sugerencias"]:
            all_banco_ids.extend(sug["banco_mov_ids"])
        assert len(all_banco_ids) == len(set(all_banco_ids)), f"Duplicate banco IDs found: {all_banco_ids}"
        print(f"PASSED: No duplicate banco IDs. Total unique: {len(set(all_banco_ids))}")
    
    def test_no_duplicate_sistema_ids(self):
        """Each sistema movement should appear in only one suggestion"""
        response = requests.get(
            f"{BASE_URL}/api/conciliacion/sugerencias",
            params={"cuenta_financiera_id": CUENTA_FINANCIERA_ID, "empresa_id": EMPRESA_ID}
        )
        data = response.json()
        all_sistema_ids = []
        for sug in data["sugerencias"]:
            all_sistema_ids.extend(sug["sistema_mov_ids"])
        assert len(all_sistema_ids) == len(set(all_sistema_ids)), f"Duplicate sistema IDs found: {all_sistema_ids}"
        print(f"PASSED: No duplicate sistema IDs. Total unique: {len(set(all_sistema_ids))}")
    
    def test_suggestions_have_required_fields(self):
        """Each suggestion should have monto, regla, confianza, tipo"""
        response = requests.get(
            f"{BASE_URL}/api/conciliacion/sugerencias",
            params={"cuenta_financiera_id": CUENTA_FINANCIERA_ID, "empresa_id": EMPRESA_ID}
        )
        data = response.json()
        required_fields = ["banco_mov_ids", "sistema_mov_ids", "monto", "regla", "confianza", "tipo"]
        for i, sug in enumerate(data["sugerencias"]):
            for field in required_fields:
                assert field in sug, f"Suggestion {i} missing required field '{field}'"
        print(f"PASSED: All {len(data['sugerencias'])} suggestions have required fields")
    
    def test_3_to_1_match_details(self):
        """Verify the 3:1 match has correct structure (1 banco, 3 sistema)"""
        response = requests.get(
            f"{BASE_URL}/api/conciliacion/sugerencias",
            params={"cuenta_financiera_id": CUENTA_FINANCIERA_ID, "empresa_id": EMPRESA_ID}
        )
        data = response.json()
        three_to_one = [s for s in data["sugerencias"] if s["tipo"] == "3:1"]
        assert len(three_to_one) > 0, "No 3:1 match found"
        match = three_to_one[0]
        assert len(match["banco_mov_ids"]) == 1, f"3:1 match should have 1 banco_mov_id, got {len(match['banco_mov_ids'])}"
        assert len(match["sistema_mov_ids"]) == 3, f"3:1 match should have 3 sistema_mov_ids, got {len(match['sistema_mov_ids'])}"
        assert match["monto"] == 3000.0, f"3:1 match monto should be 3000.0, got {match['monto']}"
        print(f"PASSED: 3:1 match verified - banco_ids: {match['banco_mov_ids']}, sistema_ids: {match['sistema_mov_ids']}, monto: {match['monto']}")
    
    def test_1_to_2_match_details(self):
        """Verify the 1:2 match has correct structure (2 banco, 1 sistema)"""
        response = requests.get(
            f"{BASE_URL}/api/conciliacion/sugerencias",
            params={"cuenta_financiera_id": CUENTA_FINANCIERA_ID, "empresa_id": EMPRESA_ID}
        )
        data = response.json()
        one_to_two = [s for s in data["sugerencias"] if s["tipo"] == "1:2"]
        assert len(one_to_two) > 0, "No 1:2 match found"
        match = one_to_two[0]
        assert len(match["banco_mov_ids"]) == 2, f"1:2 match should have 2 banco_mov_ids, got {len(match['banco_mov_ids'])}"
        assert len(match["sistema_mov_ids"]) == 1, f"1:2 match should have 1 sistema_mov_id, got {len(match['sistema_mov_ids'])}"
        assert match["monto"] == -2500.0, f"1:2 match monto should be -2500.0, got {match['monto']}"
        print(f"PASSED: 1:2 match verified - banco_ids: {match['banco_mov_ids']}, sistema_ids: {match['sistema_mov_ids']}, monto: {match['monto']}")


class TestArticulosOCEndpoint:
    """Test GET /api/articulos-oc endpoint for linea_negocio_id"""
    
    def test_endpoint_returns_200(self):
        """Endpoint should return 200 OK"""
        response = requests.get(
            f"{BASE_URL}/api/articulos-oc",
            params={"empresa_id": EMPRESA_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASSED: articulos-oc endpoint returns 200")
    
    def test_returns_list(self):
        """Endpoint should return a list"""
        response = requests.get(
            f"{BASE_URL}/api/articulos-oc",
            params={"empresa_id": EMPRESA_ID}
        )
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"PASSED: articulos-oc returns list with {len(data)} items")
    
    def test_articles_have_linea_negocio_id(self):
        """All articles should have linea_negocio_id field"""
        response = requests.get(
            f"{BASE_URL}/api/articulos-oc",
            params={"empresa_id": EMPRESA_ID}
        )
        data = response.json()
        assert len(data) > 0, "No articles returned"
        for i, article in enumerate(data):
            assert "linea_negocio_id" in article, f"Article {i} missing 'linea_negocio_id'"
        articles_with_linea = [a for a in data if a.get("linea_negocio_id")]
        print(f"PASSED: All {len(data)} articles have linea_negocio_id field. {len(articles_with_linea)} have non-null values")
    
    def test_articles_have_linea_negocio_nombre(self):
        """Articles should have linea_negocio_nombre field"""
        response = requests.get(
            f"{BASE_URL}/api/articulos-oc",
            params={"empresa_id": EMPRESA_ID}
        )
        data = response.json()
        assert len(data) > 0, "No articles returned"
        for i, article in enumerate(data):
            assert "linea_negocio_nombre" in article, f"Article {i} missing 'linea_negocio_nombre'"
        articles_with_nombre = [a for a in data if a.get("linea_negocio_nombre")]
        print(f"PASSED: All {len(data)} articles have linea_negocio_nombre field. {len(articles_with_nombre)} have non-null values")


class TestInventarioEndpoint:
    """Test GET /api/inventario endpoint for linea_negocio_id"""
    
    def test_endpoint_returns_200(self):
        """Endpoint should return 200 OK"""
        response = requests.get(
            f"{BASE_URL}/api/inventario",
            params={"empresa_id": EMPRESA_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASSED: inventario endpoint returns 200")
    
    def test_returns_list(self):
        """Endpoint should return a list"""
        response = requests.get(
            f"{BASE_URL}/api/inventario",
            params={"empresa_id": EMPRESA_ID}
        )
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"PASSED: inventario returns list with {len(data)} items")
    
    def test_inventory_items_have_linea_negocio_id(self):
        """All inventory items should have linea_negocio_id field"""
        response = requests.get(
            f"{BASE_URL}/api/inventario",
            params={"empresa_id": EMPRESA_ID}
        )
        data = response.json()
        assert len(data) > 0, "No inventory items returned"
        for i, item in enumerate(data):
            assert "linea_negocio_id" in item, f"Inventory item {i} missing 'linea_negocio_id'"
        items_with_linea = [i for i in data if i.get("linea_negocio_id")]
        print(f"PASSED: All {len(data)} inventory items have linea_negocio_id field. {len(items_with_linea)} have non-null values")


class TestConfirmarSugerenciasEndpoint:
    """Test POST /api/conciliacion/confirmar-sugerencias endpoint"""
    
    def test_endpoint_accepts_array_format(self):
        """Endpoint should accept suggestions with array format"""
        # First get current suggestions
        response = requests.get(
            f"{BASE_URL}/api/conciliacion/sugerencias",
            params={"cuenta_financiera_id": CUENTA_FINANCIERA_ID, "empresa_id": EMPRESA_ID}
        )
        data = response.json()
        
        # Test with empty array (should return error but not 500)
        response = requests.post(
            f"{BASE_URL}/api/conciliacion/confirmar-sugerencias",
            params={"empresa_id": EMPRESA_ID},
            json={"sugerencias": []}
        )
        # Should return 400 (no suggestions) not 500 (server error)
        assert response.status_code in [200, 400], f"Expected 200 or 400, got {response.status_code}"
        print(f"PASSED: Endpoint handles empty array correctly (status: {response.status_code})")
    
    def test_endpoint_structure_validation(self):
        """Endpoint should validate suggestion structure"""
        # Test with malformed suggestion
        response = requests.post(
            f"{BASE_URL}/api/conciliacion/confirmar-sugerencias",
            params={"empresa_id": EMPRESA_ID},
            json={"sugerencias": [{"invalid": "data"}]}
        )
        # Should not crash (500), should handle gracefully
        assert response.status_code != 500, f"Server error on malformed data: {response.text}"
        print(f"PASSED: Endpoint handles malformed data gracefully (status: {response.status_code})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
