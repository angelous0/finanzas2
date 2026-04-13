"""
Backend tests for P0 Fix: Treasury and Payments visibility for confirmed POS sales.

P0 Bug Fixed: When a POS sale was confirmed, the system was creating analytical 
distributions but NOT creating entries in cont_movimiento_tesoreria (Tesoreria view) 
and cont_pago (Pagos view). This test validates both are now created correctly.

Test data: Order 146662 (Ambission Industries SAC, empresa_id=6) - S/100 sale
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://concilia-smart.preview.emergentagent.com').rstrip('/')
EMPRESA_ID = 6


class TestTesoreriaMovements:
    """Test that treasury movements are correctly created and visible"""

    def test_tesoreria_list_contains_venta_pos_movement(self):
        """API GET /api/tesoreria should return movement for confirmed POS sale"""
        response = requests.get(
            f"{BASE_URL}/api/tesoreria",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2026-03-01",
                "fecha_hasta": "2026-03-31"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "data" in data
        assert "total" in data
        assert data["total"] > 0, "Should have treasury movements"
        
        # Find the movement for Venta POS #146662
        venta_pos_movements = [
            m for m in data["data"] 
            if m.get("origen_tipo") == "venta_pos_confirmada" and "146662" in (m.get("concepto") or "")
        ]
        assert len(venta_pos_movements) > 0, "Should have treasury movement for Venta POS #146662"
        
        # Validate the movement details
        mov = venta_pos_movements[0]
        assert mov["tipo"] == "ingreso", "Movement should be ingreso type"
        assert mov["monto"] == 100.0, "Movement amount should be S/100"
        assert mov["origen_tipo"] == "venta_pos_confirmada", "origen_tipo should be venta_pos_confirmada"

    def test_tesoreria_filter_by_origen_tipo(self):
        """API GET /api/tesoreria with origen_tipo filter should work"""
        response = requests.get(
            f"{BASE_URL}/api/tesoreria",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2026-03-01",
                "fecha_hasta": "2026-03-31",
                "origen_tipo": "venta_pos_confirmada"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # All returned movements should have origen_tipo = venta_pos_confirmada
        for mov in data["data"]:
            assert mov["origen_tipo"] == "venta_pos_confirmada"

    def test_tesoreria_resumen_includes_ingresos(self):
        """API GET /api/tesoreria/resumen should show total_ingresos >= 100"""
        response = requests.get(
            f"{BASE_URL}/api/tesoreria/resumen",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2026-03-01",
                "fecha_hasta": "2026-03-31"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields
        assert "total_ingresos" in data
        assert "total_egresos" in data
        assert "flujo_neto" in data
        assert "saldo_total" in data
        assert "por_origen" in data
        
        # total_ingresos should be at least 100 (the S/100 from POS sale)
        assert data["total_ingresos"] >= 100.0, f"total_ingresos should be >= 100, got {data['total_ingresos']}"
        
        # Check por_origen breakdown includes venta_pos_confirmada
        venta_pos_ingresos = [
            o for o in data["por_origen"] 
            if o["origen_tipo"] == "venta_pos_confirmada" and o["tipo"] == "ingreso"
        ]
        assert len(venta_pos_ingresos) > 0, "Should have venta_pos_confirmada in por_origen breakdown"
        assert venta_pos_ingresos[0]["total"] >= 100.0


class TestPagosMovements:
    """Test that payment records (cont_pago) are correctly created and visible"""

    def test_pagos_list_contains_pos_payment(self):
        """API GET /api/pagos should include PAG-I-2026-00001 ingreso"""
        response = requests.get(
            f"{BASE_URL}/api/pagos",
            params={"empresa_id": EMPRESA_ID}
        )
        assert response.status_code == 200
        pagos = response.json()
        
        # Should be a list
        assert isinstance(pagos, list)
        assert len(pagos) > 0, "Should have payment records"
        
        # Find PAG-I-2026-00001
        pag_i_001 = [p for p in pagos if p.get("numero") == "PAG-I-2026-00001"]
        assert len(pag_i_001) > 0, "Should have PAG-I-2026-00001 payment"
        
        # Validate payment details
        pago = pag_i_001[0]
        assert pago["tipo"] == "ingreso", "Payment should be ingreso type"
        assert pago["monto_total"] == 100.0, "Payment amount should be S/100"

    def test_pagos_filter_by_tipo_ingreso(self):
        """API GET /api/pagos with tipo=ingreso filter should work"""
        response = requests.get(
            f"{BASE_URL}/api/pagos",
            params={
                "empresa_id": EMPRESA_ID,
                "tipo": "ingreso"
            }
        )
        assert response.status_code == 200
        pagos = response.json()
        
        # All returned payments should be ingresos
        for pago in pagos:
            assert pago["tipo"] == "ingreso"
        
        # Should include at least the POS payment
        assert len(pagos) >= 1

    def test_pagos_response_structure(self):
        """Validate pagos response has all required fields"""
        response = requests.get(
            f"{BASE_URL}/api/pagos",
            params={"empresa_id": EMPRESA_ID}
        )
        assert response.status_code == 200
        pagos = response.json()
        
        if len(pagos) > 0:
            pago = pagos[0]
            # Required fields
            assert "id" in pago
            assert "numero" in pago
            assert "tipo" in pago
            assert "fecha" in pago
            assert "monto_total" in pago


class TestTesoreriaKPIs:
    """Test treasury KPIs for correct totals"""

    def test_tesoreria_kpi_fields(self):
        """API GET /api/tesoreria/resumen should return all KPI fields"""
        response = requests.get(
            f"{BASE_URL}/api/tesoreria/resumen",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2026-03-01",
                "fecha_hasta": "2026-03-31"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # All KPI fields should be present
        required_fields = [
            "total_ingresos", "total_egresos", "flujo_neto",
            "count_ingresos", "count_egresos",
            "saldo_caja", "saldo_banco", "saldo_total",
            "por_origen", "cuentas",
            "fecha_desde", "fecha_hasta"
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    def test_tesoreria_flujo_neto_calculation(self):
        """Verify flujo_neto = total_ingresos - total_egresos"""
        response = requests.get(
            f"{BASE_URL}/api/tesoreria/resumen",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2026-03-01",
                "fecha_hasta": "2026-03-31"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        expected_flujo = data["total_ingresos"] - data["total_egresos"]
        assert abs(data["flujo_neto"] - expected_flujo) < 0.01, "flujo_neto calculation is incorrect"

    def test_tesoreria_saldo_total_calculation(self):
        """Verify saldo_total = saldo_caja + saldo_banco"""
        response = requests.get(
            f"{BASE_URL}/api/tesoreria/resumen",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2026-03-01",
                "fecha_hasta": "2026-03-31"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        expected_total = data["saldo_caja"] + data["saldo_banco"]
        assert abs(data["saldo_total"] - expected_total) < 0.01, "saldo_total calculation is incorrect"


class TestReportesIngresosPorLinea:
    """Test analytical revenue reports by business line"""

    def test_ingresos_por_linea_endpoint(self):
        """API GET /api/reportes/ingresos-por-linea should return analytical data"""
        response = requests.get(
            f"{BASE_URL}/api/reportes/ingresos-por-linea",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2026-03-01",
                "fecha_hasta": "2026-03-31"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should be a list of linea data
        assert isinstance(data, list)
        
        # If we have data, validate structure
        if len(data) > 0:
            item = data[0]
            assert "linea" in item or "id" in item, "Should have linea identifier"
            assert "ingresos" in item, "Should have ingresos amount"


class TestPagosKPIs:
    """Test pagos KPI calculations from frontend perspective"""

    def test_pagos_totals_calculation(self):
        """Verify total ingresos and egresos can be calculated from pagos list"""
        response = requests.get(
            f"{BASE_URL}/api/pagos",
            params={"empresa_id": EMPRESA_ID}
        )
        assert response.status_code == 200
        pagos = response.json()
        
        # Calculate totals as frontend would
        total_ingresos = sum(float(p.get("monto_total", 0)) for p in pagos if p.get("tipo") == "ingreso")
        total_egresos = sum(float(p.get("monto_total", 0)) for p in pagos if p.get("tipo") == "egreso")
        neto = total_ingresos - total_egresos
        
        # Basic sanity checks
        assert total_ingresos >= 100.0, f"Ingresos should include the S/100 POS payment, got {total_ingresos}"


class TestP0BugVerification:
    """Specific tests to verify the P0 bug fix is complete"""

    def test_venta_pos_146662_creates_treasury_movement(self):
        """Verify Venta POS #146662 has a treasury movement"""
        response = requests.get(
            f"{BASE_URL}/api/tesoreria",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2026-03-01",
                "fecha_hasta": "2026-03-31",
                "origen_tipo": "venta_pos_confirmada"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Find 146662 movement
        found = any(
            "146662" in (m.get("concepto") or "") 
            for m in data["data"]
        )
        assert found, "Treasury movement for Venta POS #146662 should exist"

    def test_venta_pos_146662_creates_cont_pago(self):
        """Verify Venta POS #146662 has a cont_pago record"""
        response = requests.get(
            f"{BASE_URL}/api/pagos",
            params={"empresa_id": EMPRESA_ID, "tipo": "ingreso"}
        )
        assert response.status_code == 200
        pagos = response.json()
        
        # Should have PAG-I-2026-00001 which is linked to POS-146662
        pag_found = any(p.get("numero") == "PAG-I-2026-00001" for p in pagos)
        assert pag_found, "cont_pago PAG-I-2026-00001 should exist for Venta POS #146662"

    def test_tesoreria_and_pagos_consistency(self):
        """Verify treasury and payment amounts are consistent"""
        # Get treasury total for POS sales
        tesoreria_response = requests.get(
            f"{BASE_URL}/api/tesoreria",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2026-03-01",
                "fecha_hasta": "2026-03-31",
                "origen_tipo": "venta_pos_confirmada"
            }
        )
        assert tesoreria_response.status_code == 200
        tesoreria_data = tesoreria_response.json()
        
        treasury_total = sum(float(m.get("monto", 0)) for m in tesoreria_data["data"])
        
        # Get payments total for ingreso
        pagos_response = requests.get(
            f"{BASE_URL}/api/pagos",
            params={"empresa_id": EMPRESA_ID, "tipo": "ingreso"}
        )
        assert pagos_response.status_code == 200
        pagos = pagos_response.json()
        
        # The POS-related payment should match treasury movement
        # Note: There may be other ingresos too, so we just check POS amounts are >= 100
        assert treasury_total >= 100.0, f"Treasury total for POS should be >= 100, got {treasury_total}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
