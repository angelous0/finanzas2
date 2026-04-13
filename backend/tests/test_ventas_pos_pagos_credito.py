"""
Test Ventas POS Pagos Credito (CxC Abonos) Feature - Iteration 36

Tests the fix for P0 bug: Credit sales now correctly show 'Pago Asociado' amounts
and provide payment history visibility via new /pagos-credito endpoint.

Modules tested:
- pos_crud.py: pagos_cxc/num_pagos_cxc subqueries in ventas list
- pos_crud.py: GET /api/ventas-pos/{order_id}/pagos-credito endpoint
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
HEADERS = {
    "Content-Type": "application/json",
    "X-Empresa-Id": "7"
}


class TestVentasPOSPagosCreditoAPI:
    """Tests for Ventas POS Credit Payment (CxC Abonos) functionality"""

    def test_credit_sales_list_includes_pagos_cxc(self):
        """GET /api/ventas-pos?estado=credito should include pagos_cxc fields"""
        response = requests.get(
            f"{BASE_URL}/api/ventas-pos",
            params={"estado": "credito", "page": 1, "page_size": 10},
            headers=HEADERS
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "data" in data, "Response should contain 'data' key"
        assert len(data["data"]) > 0, "Should have at least one credit sale"
        
        # Verify order 146699 is in the list with correct pagos_cxc
        order_146699 = next((v for v in data["data"] if v["id"] == 146699), None)
        assert order_146699 is not None, "Order 146699 should be in credit sales list"
        
        # Verify pagos_cxc fields
        assert "pagos_cxc" in order_146699, "Order should have pagos_cxc field"
        assert "num_pagos_cxc" in order_146699, "Order should have num_pagos_cxc field"
        assert order_146699["pagos_cxc"] == 50.0, f"Expected pagos_cxc=50.0, got {order_146699['pagos_cxc']}"
        assert order_146699["num_pagos_cxc"] == 1, f"Expected num_pagos_cxc=1, got {order_146699['num_pagos_cxc']}"
        
        # Verify other fields for completeness
        assert order_146699["amount_total"] == 78.0, "Order amount_total should be 78"
        assert order_146699["estado_local"] == "credito", "Order estado_local should be credito"

    def test_get_pagos_credito_existing_order(self):
        """GET /api/ventas-pos/146699/pagos-credito should return CxC abonos"""
        response = requests.get(
            f"{BASE_URL}/api/ventas-pos/146699/pagos-credito",
            headers=HEADERS
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify response structure
        assert "abonos" in data, "Response should contain 'abonos' key"
        assert "cxc" in data, "Response should contain 'cxc' key"
        
        # Verify CxC info
        cxc = data["cxc"]
        assert cxc is not None, "CxC info should not be null"
        assert cxc["monto_original"] == 78.0, f"Expected monto_original=78, got {cxc['monto_original']}"
        assert cxc["saldo_pendiente"] == 28.0, f"Expected saldo_pendiente=28, got {cxc['saldo_pendiente']}"
        assert cxc["estado"] == "parcial", f"Expected estado=parcial, got {cxc['estado']}"
        
        # Verify abonos
        abonos = data["abonos"]
        assert len(abonos) == 1, f"Expected 1 abono, got {len(abonos)}"
        
        abono = abonos[0]
        assert abono["monto"] == 50.0, f"Expected abono monto=50, got {abono['monto']}"
        assert abono["forma_pago"] == "transferencia", f"Expected forma_pago=transferencia, got {abono['forma_pago']}"
        assert "cuenta_nombre" in abono, "Abono should have cuenta_nombre field"

    def test_get_pagos_credito_nonexistent_order(self):
        """GET /api/ventas-pos/999999/pagos-credito should return empty for non-existent order"""
        response = requests.get(
            f"{BASE_URL}/api/ventas-pos/999999/pagos-credito",
            headers=HEADERS
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify empty response
        assert data["abonos"] == [], "Abonos should be empty for non-existent order"
        assert data["cxc"] is None, "CxC should be null for non-existent order"

    def test_credit_sale_cxc_id_populated(self):
        """Credit sales should have cxc_id populated"""
        response = requests.get(
            f"{BASE_URL}/api/ventas-pos",
            params={"estado": "credito", "page": 1, "page_size": 10},
            headers=HEADERS
        )
        assert response.status_code == 200
        
        data = response.json()
        order_146699 = next((v for v in data["data"] if v["id"] == 146699), None)
        assert order_146699 is not None
        
        # Verify cxc_id is populated
        assert "cxc_id" in order_146699, "Order should have cxc_id field"
        assert order_146699["cxc_id"] is not None, "cxc_id should not be null for credit sale with CxC"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
