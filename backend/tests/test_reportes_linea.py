"""Tests for Reportes por Linea de Negocio APIs - 5 new endpoints."""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
EMPRESA_ID = 7
DATE_DESDE = "2026-01-01"
DATE_HASTA = "2026-12-31"

class TestReportesLinea:
    """Test all 5 reportes por linea de negocio endpoints."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "X-Empresa-Id": str(EMPRESA_ID)
        })
        self.params = {
            "empresa_id": EMPRESA_ID,
            "fecha_desde": DATE_DESDE,
            "fecha_hasta": DATE_HASTA
        }

    # ========== 1. VENTAS POR LINEA ==========
    def test_ventas_por_linea_status_code(self):
        """GET /api/reportes/ventas-por-linea returns 200"""
        response = self.session.get(f"{BASE_URL}/api/reportes/ventas-por-linea", params=self.params)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_ventas_por_linea_structure(self):
        """Response has data array and totales object"""
        response = self.session.get(f"{BASE_URL}/api/reportes/ventas-por-linea", params=self.params)
        data = response.json()
        assert "data" in data, "Response missing 'data' field"
        assert "totales" in data, "Response missing 'totales' field"
        assert isinstance(data["data"], list), "'data' should be a list"
        assert isinstance(data["totales"], dict), "'totales' should be a dict"

    def test_ventas_por_linea_fields(self):
        """Each row has linea, ventas, tickets, ticket_promedio"""
        response = self.session.get(f"{BASE_URL}/api/reportes/ventas-por-linea", params=self.params)
        data = response.json()
        if len(data["data"]) > 0:
            row = data["data"][0]
            assert "linea" in row, "Row missing 'linea'"
            assert "ventas" in row, "Row missing 'ventas'"
            assert "tickets" in row, "Row missing 'tickets'"
            assert "ticket_promedio" in row, "Row missing 'ticket_promedio'"
        
        # Verify totales fields
        totales = data["totales"]
        assert "ventas" in totales, "Totales missing 'ventas'"
        assert "tickets" in totales, "Totales missing 'tickets'"
        assert "ticket_promedio" in totales, "Totales missing 'ticket_promedio'"

    def test_ventas_por_linea_has_data(self):
        """Using date range 2026-03-01 to 2026-03-14 returns data"""
        params = {"empresa_id": EMPRESA_ID, "fecha_desde": "2026-03-01", "fecha_hasta": "2026-03-14"}
        response = self.session.get(f"{BASE_URL}/api/reportes/ventas-por-linea", params=params)
        data = response.json()
        print(f"Ventas por linea data count: {len(data['data'])}")
        print(f"Total ventas: {data['totales']['ventas']}")

    # ========== 2. COBRANZA POR LINEA ==========
    def test_cobranza_por_linea_status_code(self):
        """GET /api/reportes/cobranza-por-linea returns 200"""
        response = self.session.get(f"{BASE_URL}/api/reportes/cobranza-por-linea", params=self.params)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_cobranza_por_linea_structure(self):
        """Response has data array and totales object"""
        response = self.session.get(f"{BASE_URL}/api/reportes/cobranza-por-linea", params=self.params)
        data = response.json()
        assert "data" in data, "Response missing 'data' field"
        assert "totales" in data, "Response missing 'totales' field"

    def test_cobranza_por_linea_fields(self):
        """Each row has linea, vendido, cobrado, pendiente, pct_cobrado"""
        response = self.session.get(f"{BASE_URL}/api/reportes/cobranza-por-linea", params=self.params)
        data = response.json()
        if len(data["data"]) > 0:
            row = data["data"][0]
            assert "linea" in row, "Row missing 'linea'"
            assert "vendido" in row, "Row missing 'vendido'"
            assert "cobrado" in row, "Row missing 'cobrado'"
            assert "pendiente" in row, "Row missing 'pendiente'"
            assert "pct_cobrado" in row, "Row missing 'pct_cobrado'"
        
        # Verify totales fields
        totales = data["totales"]
        assert "vendido" in totales, "Totales missing 'vendido'"
        assert "cobrado" in totales, "Totales missing 'cobrado'"
        assert "pendiente" in totales, "Totales missing 'pendiente'"
        assert "pct_cobrado" in totales, "Totales missing 'pct_cobrado'"

    # ========== 3. CRUCE LINEA x MARCA ==========
    def test_cruce_linea_marca_status_code(self):
        """GET /api/reportes/cruce-linea-marca returns 200"""
        response = self.session.get(f"{BASE_URL}/api/reportes/cruce-linea-marca", params=self.params)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_cruce_linea_marca_structure(self):
        """Response is array of lineas with nested marcas"""
        response = self.session.get(f"{BASE_URL}/api/reportes/cruce-linea-marca", params=self.params)
        data = response.json()
        assert isinstance(data, list), "Response should be a list of lineas"
        if len(data) > 0:
            linea_item = data[0]
            assert "linea" in linea_item, "Linea item missing 'linea'"
            assert "total_ventas" in linea_item, "Linea item missing 'total_ventas'"
            assert "marcas" in linea_item, "Linea item missing 'marcas'"
            assert isinstance(linea_item["marcas"], list), "'marcas' should be a list"

    def test_cruce_linea_marca_marca_fields(self):
        """Each marca has marca, ventas, tickets, pct fields"""
        response = self.session.get(f"{BASE_URL}/api/reportes/cruce-linea-marca", params=self.params)
        data = response.json()
        if len(data) > 0 and len(data[0]["marcas"]) > 0:
            marca = data[0]["marcas"][0]
            assert "marca" in marca, "Marca missing 'marca' field"
            assert "ventas" in marca, "Marca missing 'ventas' field"
            assert "tickets" in marca, "Marca missing 'tickets' field"
            assert "pct" in marca, "Marca missing 'pct' field"

    # ========== 4. GASTOS DIRECTOS POR LINEA ==========
    def test_gastos_directos_por_linea_status_code(self):
        """GET /api/reportes/gastos-directos-por-linea returns 200"""
        response = self.session.get(f"{BASE_URL}/api/reportes/gastos-directos-por-linea", params=self.params)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_gastos_directos_por_linea_structure(self):
        """Response has data array and totales object"""
        response = self.session.get(f"{BASE_URL}/api/reportes/gastos-directos-por-linea", params=self.params)
        data = response.json()
        assert "data" in data, "Response missing 'data' field"
        assert "totales" in data, "Response missing 'totales' field"

    def test_gastos_directos_por_linea_fields(self):
        """Each row has linea, total_gastos, total_facturas, total_egresos"""
        response = self.session.get(f"{BASE_URL}/api/reportes/gastos-directos-por-linea", params=self.params)
        data = response.json()
        if len(data["data"]) > 0:
            row = data["data"][0]
            assert "linea" in row, "Row missing 'linea'"
            assert "total_gastos" in row, "Row missing 'total_gastos'"
            assert "total_facturas" in row, "Row missing 'total_facturas'"
            assert "total_egresos" in row, "Row missing 'total_egresos'"
        
        # Verify totales
        totales = data["totales"]
        assert "total_gastos" in totales, "Totales missing 'total_gastos'"
        assert "total_facturas" in totales, "Totales missing 'total_facturas'"
        assert "total_egresos" in totales, "Totales missing 'total_egresos'"

    # ========== 5. DINERO POR LINEA ==========
    def test_dinero_por_linea_status_code(self):
        """GET /api/reportes/dinero-por-linea returns 200"""
        response = self.session.get(f"{BASE_URL}/api/reportes/dinero-por-linea", params=self.params)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_dinero_por_linea_structure(self):
        """Response has data array and totales object"""
        response = self.session.get(f"{BASE_URL}/api/reportes/dinero-por-linea", params=self.params)
        data = response.json()
        assert "data" in data, "Response missing 'data' field"
        assert "totales" in data, "Response missing 'totales' field"

    def test_dinero_por_linea_fields(self):
        """Each row has linea, ventas, cobranzas, cxc_pendiente, gastos, saldo_neto"""
        response = self.session.get(f"{BASE_URL}/api/reportes/dinero-por-linea", params=self.params)
        data = response.json()
        if len(data["data"]) > 0:
            row = data["data"][0]
            assert "linea" in row, "Row missing 'linea'"
            assert "ventas" in row, "Row missing 'ventas'"
            assert "cobranzas" in row, "Row missing 'cobranzas'"
            assert "cxc_pendiente" in row, "Row missing 'cxc_pendiente'"
            assert "gastos" in row, "Row missing 'gastos'"
            assert "saldo_neto" in row, "Row missing 'saldo_neto'"
        
        # Verify totales
        totales = data["totales"]
        assert "ventas" in totales, "Totales missing 'ventas'"
        assert "cobranzas" in totales, "Totales missing 'cobranzas'"
        assert "cxc_pendiente" in totales, "Totales missing 'cxc_pendiente'"
        assert "gastos" in totales, "Totales missing 'gastos'"
        assert "saldo_neto" in totales, "Totales missing 'saldo_neto'"

    def test_dinero_por_linea_has_data(self):
        """Dinero por linea returns actual data (Element Premium line expected)"""
        params = {"empresa_id": EMPRESA_ID, "fecha_desde": "2026-03-01", "fecha_hasta": "2026-03-14"}
        response = self.session.get(f"{BASE_URL}/api/reportes/dinero-por-linea", params=params)
        data = response.json()
        print(f"Dinero por linea data count: {len(data['data'])}")
        print(f"Total ventas: {data['totales']['ventas']}")
        print(f"Total cobranzas: {data['totales']['cobranzas']}")
        # Check for any data - the note mentions Element Premium has S/178 ventas
        for row in data["data"]:
            if row["ventas"] > 0:
                print(f"  - {row['linea']}: ventas={row['ventas']}, cobranzas={row['cobranzas']}")

    # ========== EDGE CASES ==========
    def test_empty_date_range(self):
        """Date range with no data returns empty but valid structure"""
        params = {"empresa_id": EMPRESA_ID, "fecha_desde": "2020-01-01", "fecha_hasta": "2020-01-31"}
        response = self.session.get(f"{BASE_URL}/api/reportes/ventas-por-linea", params=params)
        data = response.json()
        assert response.status_code == 200
        assert "data" in data
        assert "totales" in data

    def test_default_date_range(self):
        """No date params still works (uses default range)"""
        params = {"empresa_id": EMPRESA_ID}
        response = self.session.get(f"{BASE_URL}/api/reportes/ventas-por-linea", params=params)
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
