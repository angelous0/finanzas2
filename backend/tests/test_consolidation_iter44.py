"""
Test suite for Iteration 44: Report Consolidation
Tests the consolidated Reportes Financieros page with:
- Flujo de Caja tab with ComposedChart and agrupacion selector
- Rentabilidad tab with 5 sub-tabs
- Backend endpoints for all report data
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
EMPRESA_ID = 7


class TestFlujoCajaGerencial:
    """Tests for GET /api/flujo-caja-gerencial endpoint"""
    
    def test_endpoint_returns_200(self):
        """Flujo caja gerencial endpoint should return 200"""
        response = requests.get(
            f"{BASE_URL}/api/flujo-caja-gerencial",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2025-12-31",
                "agrupacion": "diario"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    def test_response_has_required_structure(self):
        """Response should have timeline, totales, agrupacion, fecha_desde, fecha_hasta"""
        response = requests.get(
            f"{BASE_URL}/api/flujo-caja-gerencial",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2025-12-31",
                "agrupacion": "diario"
            }
        )
        data = response.json()
        assert "timeline" in data, "Missing 'timeline' in response"
        assert "totales" in data, "Missing 'totales' in response"
        assert "agrupacion" in data, "Missing 'agrupacion' in response"
        assert "fecha_desde" in data, "Missing 'fecha_desde' in response"
        assert "fecha_hasta" in data, "Missing 'fecha_hasta' in response"
    
    def test_totales_has_required_fields(self):
        """Totales should have ingresos, egresos, flujo_neto"""
        response = requests.get(
            f"{BASE_URL}/api/flujo-caja-gerencial",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2025-12-31",
                "agrupacion": "diario"
            }
        )
        data = response.json()
        totales = data.get("totales", {})
        assert "ingresos" in totales, "Missing 'ingresos' in totales"
        assert "egresos" in totales, "Missing 'egresos' in totales"
        assert "flujo_neto" in totales, "Missing 'flujo_neto' in totales"
    
    def test_agrupacion_diario(self):
        """Agrupacion diario should work"""
        response = requests.get(
            f"{BASE_URL}/api/flujo-caja-gerencial",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2026-01-01",
                "fecha_hasta": "2026-04-10",
                "agrupacion": "diario"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["agrupacion"] == "diario"
    
    def test_agrupacion_semanal(self):
        """Agrupacion semanal should work"""
        response = requests.get(
            f"{BASE_URL}/api/flujo-caja-gerencial",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2026-01-01",
                "fecha_hasta": "2026-04-10",
                "agrupacion": "semanal"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["agrupacion"] == "semanal"
    
    def test_agrupacion_mensual(self):
        """Agrupacion mensual should work"""
        response = requests.get(
            f"{BASE_URL}/api/flujo-caja-gerencial",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2026-01-01",
                "fecha_hasta": "2026-04-10",
                "agrupacion": "mensual"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["agrupacion"] == "mensual"
    
    def test_timeline_item_has_required_fields(self):
        """Timeline items should have periodo, ingresos, egresos, saldo_acumulado"""
        response = requests.get(
            f"{BASE_URL}/api/flujo-caja-gerencial",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2026-01-01",
                "fecha_hasta": "2026-04-10",
                "agrupacion": "diario"
            }
        )
        data = response.json()
        timeline = data.get("timeline", [])
        if len(timeline) > 0:
            item = timeline[0]
            required_fields = ["periodo", "total_ingresos", "total_egresos", "flujo_neto", "saldo_acumulado"]
            for field in required_fields:
                assert field in item, f"Missing '{field}' in timeline item"


class TestDineroPorLinea:
    """Tests for GET /api/reportes/dinero-por-linea endpoint"""
    
    def test_endpoint_returns_200(self):
        """Dinero por linea endpoint should return 200"""
        response = requests.get(
            f"{BASE_URL}/api/reportes/dinero-por-linea",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2025-12-31"
            }
        )
        assert response.status_code == 200
    
    def test_response_has_data_and_totales(self):
        """Response should have data array and totales object"""
        response = requests.get(
            f"{BASE_URL}/api/reportes/dinero-por-linea",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2025-12-31"
            }
        )
        data = response.json()
        assert "data" in data, "Missing 'data' in response"
        assert "totales" in data, "Missing 'totales' in response"
        assert isinstance(data["data"], list), "'data' should be a list"
    
    def test_totales_has_required_fields(self):
        """Totales should have ventas, cobranzas, cxc_pendiente, gastos, saldo_neto"""
        response = requests.get(
            f"{BASE_URL}/api/reportes/dinero-por-linea",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2025-12-31"
            }
        )
        data = response.json()
        totales = data.get("totales", {})
        required = ["ventas", "cobranzas", "cxc_pendiente", "gastos", "saldo_neto"]
        for field in required:
            assert field in totales, f"Missing '{field}' in totales"


class TestVentasPorLinea:
    """Tests for GET /api/reportes/ventas-por-linea endpoint"""
    
    def test_endpoint_returns_200(self):
        """Ventas por linea endpoint should return 200"""
        response = requests.get(
            f"{BASE_URL}/api/reportes/ventas-por-linea",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2025-12-31"
            }
        )
        assert response.status_code == 200
    
    def test_response_has_data_and_totales(self):
        """Response should have data array and totales object"""
        response = requests.get(
            f"{BASE_URL}/api/reportes/ventas-por-linea",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2025-12-31"
            }
        )
        data = response.json()
        assert "data" in data
        assert "totales" in data
    
    def test_totales_has_required_fields(self):
        """Totales should have ventas, tickets, ticket_promedio"""
        response = requests.get(
            f"{BASE_URL}/api/reportes/ventas-por-linea",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2025-12-31"
            }
        )
        data = response.json()
        totales = data.get("totales", {})
        assert "ventas" in totales
        assert "tickets" in totales
        assert "ticket_promedio" in totales


class TestCobranzaPorLinea:
    """Tests for GET /api/reportes/cobranza-por-linea endpoint"""
    
    def test_endpoint_returns_200(self):
        """Cobranza por linea endpoint should return 200"""
        response = requests.get(
            f"{BASE_URL}/api/reportes/cobranza-por-linea",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2025-12-31"
            }
        )
        assert response.status_code == 200
    
    def test_response_has_data_and_totales(self):
        """Response should have data array and totales object"""
        response = requests.get(
            f"{BASE_URL}/api/reportes/cobranza-por-linea",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2025-12-31"
            }
        )
        data = response.json()
        assert "data" in data
        assert "totales" in data
    
    def test_totales_has_required_fields(self):
        """Totales should have vendido, cobrado, pendiente, pct_cobrado"""
        response = requests.get(
            f"{BASE_URL}/api/reportes/cobranza-por-linea",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2025-12-31"
            }
        )
        data = response.json()
        totales = data.get("totales", {})
        assert "vendido" in totales
        assert "cobrado" in totales
        assert "pendiente" in totales
        assert "pct_cobrado" in totales


class TestCruceLineaMarca:
    """Tests for GET /api/reportes/cruce-linea-marca endpoint"""
    
    def test_endpoint_returns_200(self):
        """Cruce linea marca endpoint should return 200"""
        response = requests.get(
            f"{BASE_URL}/api/reportes/cruce-linea-marca",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2025-12-31"
            }
        )
        assert response.status_code == 200
    
    def test_response_is_array(self):
        """Response should be an array of lineas"""
        response = requests.get(
            f"{BASE_URL}/api/reportes/cruce-linea-marca",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2025-12-31"
            }
        )
        data = response.json()
        assert isinstance(data, list), "Response should be a list"


class TestGastosDirectosPorLinea:
    """Tests for GET /api/reportes/gastos-directos-por-linea endpoint"""
    
    def test_endpoint_returns_200(self):
        """Gastos directos por linea endpoint should return 200"""
        response = requests.get(
            f"{BASE_URL}/api/reportes/gastos-directos-por-linea",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2025-12-31"
            }
        )
        assert response.status_code == 200
    
    def test_response_has_data_and_totales(self):
        """Response should have data array and totales object"""
        response = requests.get(
            f"{BASE_URL}/api/reportes/gastos-directos-por-linea",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2025-12-31"
            }
        )
        data = response.json()
        assert "data" in data
        assert "totales" in data
    
    def test_totales_has_required_fields(self):
        """Totales should have total_gastos, total_facturas, total_egresos"""
        response = requests.get(
            f"{BASE_URL}/api/reportes/gastos-directos-por-linea",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2025-12-31"
            }
        )
        data = response.json()
        totales = data.get("totales", {})
        assert "total_gastos" in totales
        assert "total_facturas" in totales
        assert "total_egresos" in totales


class TestDataIntegrity:
    """Tests for data integrity across endpoints"""
    
    def test_flujo_neto_equals_ingresos_minus_egresos(self):
        """Flujo neto should equal ingresos - egresos"""
        response = requests.get(
            f"{BASE_URL}/api/flujo-caja-gerencial",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2026-01-01",
                "fecha_hasta": "2026-04-10",
                "agrupacion": "diario"
            }
        )
        data = response.json()
        totales = data.get("totales", {})
        expected_flujo = totales.get("ingresos", 0) - totales.get("egresos", 0)
        actual_flujo = totales.get("flujo_neto", 0)
        assert abs(expected_flujo - actual_flujo) < 0.01, f"Flujo neto mismatch: {expected_flujo} vs {actual_flujo}"
    
    def test_dinero_saldo_neto_calculation(self):
        """Saldo neto should equal cobranzas - gastos"""
        response = requests.get(
            f"{BASE_URL}/api/reportes/dinero-por-linea",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2026-01-01",
                "fecha_hasta": "2026-04-10"
            }
        )
        data = response.json()
        totales = data.get("totales", {})
        expected_saldo = totales.get("cobranzas", 0) - totales.get("gastos", 0)
        actual_saldo = totales.get("saldo_neto", 0)
        assert abs(expected_saldo - actual_saldo) < 0.01, f"Saldo neto mismatch: {expected_saldo} vs {actual_saldo}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
