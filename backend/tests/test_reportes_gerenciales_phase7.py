"""
Phase 7 Tests: Reportes Gerenciales
- GET /api/reportes/resumen-ejecutivo - CFO Executive Summary
- GET /api/reportes/exportar/cxc - CSV export for CxC
- GET /api/reportes/exportar/cxp - CSV export for CxP
- GET /api/reportes/exportar/flujo-caja - CSV export for Flujo de Caja
- GET /api/reportes/exportar/rentabilidad - CSV export for Rentabilidad
- GET /api/reportes/exportar/gastos - CSV export for Gastos
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
EMPRESA_ID = 6


class TestResumenEjecutivo:
    """Tests for /api/reportes/resumen-ejecutivo endpoint"""

    def test_resumen_ejecutivo_returns_200(self):
        """Test that resumen-ejecutivo endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/reportes/resumen-ejecutivo", params={"empresa_id": EMPRESA_ID})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_resumen_ejecutivo_has_tesoreria(self):
        """Test that resumen-ejecutivo includes tesoreria data"""
        response = requests.get(f"{BASE_URL}/api/reportes/resumen-ejecutivo", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        assert "tesoreria" in data, "Response should include tesoreria"
        assert "caja" in data["tesoreria"], "Tesoreria should have caja"
        assert "banco" in data["tesoreria"], "Tesoreria should have banco"
        assert "total" in data["tesoreria"], "Tesoreria should have total"
        assert isinstance(data["tesoreria"]["total"], (int, float)), "Total should be numeric"

    def test_resumen_ejecutivo_has_cxc(self):
        """Test that resumen-ejecutivo includes CxC data"""
        response = requests.get(f"{BASE_URL}/api/reportes/resumen-ejecutivo", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        assert "cxc" in data, "Response should include cxc"
        assert "documentos" in data["cxc"], "CxC should have documentos count"
        assert "total" in data["cxc"], "CxC should have total"
        assert "vencido" in data["cxc"], "CxC should have vencido"

    def test_resumen_ejecutivo_has_cxp(self):
        """Test that resumen-ejecutivo includes CxP data"""
        response = requests.get(f"{BASE_URL}/api/reportes/resumen-ejecutivo", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        assert "cxp" in data, "Response should include cxp"
        assert "documentos" in data["cxp"], "CxP should have documentos count"
        assert "total" in data["cxp"], "CxP should have total"
        assert "vencido" in data["cxp"], "CxP should have vencido"

    def test_resumen_ejecutivo_has_ventas_mtd(self):
        """Test that resumen-ejecutivo includes ventas_mtd data"""
        response = requests.get(f"{BASE_URL}/api/reportes/resumen-ejecutivo", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        assert "ventas_mtd" in data, "Response should include ventas_mtd"
        assert "cantidad" in data["ventas_mtd"], "ventas_mtd should have cantidad"
        assert "total" in data["ventas_mtd"], "ventas_mtd should have total"

    def test_resumen_ejecutivo_has_gastos_mtd(self):
        """Test that resumen-ejecutivo includes gastos_mtd"""
        response = requests.get(f"{BASE_URL}/api/reportes/resumen-ejecutivo", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        assert "gastos_mtd" in data, "Response should include gastos_mtd"
        assert isinstance(data["gastos_mtd"], (int, float)), "gastos_mtd should be numeric"

    def test_resumen_ejecutivo_has_utilidad_mtd(self):
        """Test that resumen-ejecutivo includes utilidad_mtd"""
        response = requests.get(f"{BASE_URL}/api/reportes/resumen-ejecutivo", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        assert "utilidad_mtd" in data, "Response should include utilidad_mtd"
        # Verify calculation: utilidad_mtd = ventas_mtd.total - gastos_mtd
        expected_utilidad = data["ventas_mtd"]["total"] - data["gastos_mtd"]
        assert abs(data["utilidad_mtd"] - expected_utilidad) < 0.01, f"utilidad_mtd should equal ventas - gastos"

    def test_resumen_ejecutivo_has_pendientes_confirmar(self):
        """Test that resumen-ejecutivo includes pendientes_confirmar"""
        response = requests.get(f"{BASE_URL}/api/reportes/resumen-ejecutivo", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        assert "pendientes_confirmar" in data, "Response should include pendientes_confirmar"
        assert isinstance(data["pendientes_confirmar"], int), "pendientes_confirmar should be integer"

    def test_resumen_ejecutivo_has_liquidez_neta(self):
        """Test that resumen-ejecutivo includes liquidez_neta and calculates correctly"""
        response = requests.get(f"{BASE_URL}/api/reportes/resumen-ejecutivo", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        assert "liquidez_neta" in data, "Response should include liquidez_neta"
        # Verify calculation: liquidez_neta = disponible_total + cxc_total - cxp_total
        expected_liquidez = data["tesoreria"]["total"] + data["cxc"]["total"] - data["cxp"]["total"]
        assert abs(data["liquidez_neta"] - expected_liquidez) < 0.01, f"liquidez_neta should equal disponible + cxc - cxp"

    def test_resumen_ejecutivo_missing_empresa_id(self):
        """Test that resumen-ejecutivo returns 400 without empresa_id"""
        response = requests.get(f"{BASE_URL}/api/reportes/resumen-ejecutivo")
        assert response.status_code == 400, f"Expected 400 without empresa_id, got {response.status_code}"


class TestExportarCxC:
    """Tests for /api/reportes/exportar/cxc CSV export endpoint"""

    def test_exportar_cxc_returns_200(self):
        """Test that exportar CxC endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/cxc", params={"empresa_id": EMPRESA_ID})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_exportar_cxc_content_type_csv(self):
        """Test that exportar CxC returns CSV content type"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/cxc", params={"empresa_id": EMPRESA_ID})
        content_type = response.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got {content_type}"

    def test_exportar_cxc_content_disposition(self):
        """Test that exportar CxC has correct Content-Disposition header"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/cxc", params={"empresa_id": EMPRESA_ID})
        content_disposition = response.headers.get("content-disposition", "")
        assert "attachment" in content_disposition, f"Expected attachment in content-disposition"
        assert "filename=" in content_disposition, f"Expected filename in content-disposition"
        assert ".csv" in content_disposition, f"Expected .csv in filename"

    def test_exportar_cxc_csv_headers(self):
        """Test that exportar CxC CSV has correct headers"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/cxc", params={"empresa_id": EMPRESA_ID})
        lines = response.text.strip().split('\n')
        assert len(lines) >= 1, "CSV should have at least header row"
        headers = lines[0].split(',')
        # Required headers: ID, Cliente, Monto Original, Saldo Pendiente, Estado, Vencimiento, Dias Atraso
        assert "ID" in headers, "CSV should have ID header"
        assert "Cliente" in headers, "CSV should have Cliente header"
        assert "Monto Original" in headers, "CSV should have Monto Original header"
        assert "Saldo Pendiente" in headers, "CSV should have Saldo Pendiente header"
        assert "Estado" in headers, "CSV should have Estado header"
        assert "Vencimiento" in headers, "CSV should have Vencimiento header"
        assert "Dias Atraso" in headers, "CSV should have Dias Atraso header"

    def test_exportar_cxc_missing_empresa_id(self):
        """Test that exportar CxC returns 400 without empresa_id"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/cxc")
        assert response.status_code == 400, f"Expected 400 without empresa_id, got {response.status_code}"


class TestExportarCxP:
    """Tests for /api/reportes/exportar/cxp CSV export endpoint"""

    def test_exportar_cxp_returns_200(self):
        """Test that exportar CxP endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/cxp", params={"empresa_id": EMPRESA_ID})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_exportar_cxp_content_type_csv(self):
        """Test that exportar CxP returns CSV content type"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/cxp", params={"empresa_id": EMPRESA_ID})
        content_type = response.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got {content_type}"

    def test_exportar_cxp_content_disposition(self):
        """Test that exportar CxP has correct Content-Disposition header"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/cxp", params={"empresa_id": EMPRESA_ID})
        content_disposition = response.headers.get("content-disposition", "")
        assert "attachment" in content_disposition, f"Expected attachment in content-disposition"
        assert "filename=" in content_disposition, f"Expected filename in content-disposition"
        assert ".csv" in content_disposition, f"Expected .csv in filename"

    def test_exportar_cxp_csv_headers(self):
        """Test that exportar CxP CSV has correct headers"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/cxp", params={"empresa_id": EMPRESA_ID})
        lines = response.text.strip().split('\n')
        assert len(lines) >= 1, "CSV should have at least header row"
        headers = lines[0].split(',')
        # Required headers for CxP
        assert "ID" in headers, "CSV should have ID header"
        assert "Proveedor" in headers, "CSV should have Proveedor header"
        assert "Monto Original" in headers, "CSV should have Monto Original header"
        assert "Saldo Pendiente" in headers, "CSV should have Saldo Pendiente header"
        assert "Estado" in headers, "CSV should have Estado header"
        assert "Vencimiento" in headers, "CSV should have Vencimiento header"


class TestExportarFlujoCaja:
    """Tests for /api/reportes/exportar/flujo-caja CSV export endpoint"""

    def test_exportar_flujo_caja_returns_200(self):
        """Test that exportar flujo-caja endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/flujo-caja", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": "2025-01-01",
            "fecha_hasta": "2026-12-31"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_exportar_flujo_caja_content_type_csv(self):
        """Test that exportar flujo-caja returns CSV content type"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/flujo-caja", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": "2025-01-01",
            "fecha_hasta": "2026-12-31"
        })
        content_type = response.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got {content_type}"

    def test_exportar_flujo_caja_content_disposition(self):
        """Test that exportar flujo-caja has correct Content-Disposition header"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/flujo-caja", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": "2025-01-01",
            "fecha_hasta": "2026-12-31"
        })
        content_disposition = response.headers.get("content-disposition", "")
        assert "attachment" in content_disposition, f"Expected attachment in content-disposition"
        assert "filename=" in content_disposition, f"Expected filename in content-disposition"
        assert ".csv" in content_disposition, f"Expected .csv in filename"

    def test_exportar_flujo_caja_csv_headers(self):
        """Test that exportar flujo-caja CSV has correct headers"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/flujo-caja", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": "2025-01-01",
            "fecha_hasta": "2026-12-31"
        })
        lines = response.text.strip().split('\n')
        assert len(lines) >= 1, "CSV should have at least header row"
        headers = lines[0].split(',')
        assert "Fecha" in headers, "CSV should have Fecha header"
        assert "Ingresos" in headers, "CSV should have Ingresos header"
        assert "Egresos" in headers, "CSV should have Egresos header"
        assert "Flujo Neto" in headers, "CSV should have Flujo Neto header"
        assert "Saldo Acumulado" in headers, "CSV should have Saldo Acumulado header"

    def test_exportar_flujo_caja_missing_fecha_desde(self):
        """Test that exportar flujo-caja returns 422 without fecha_desde"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/flujo-caja", params={
            "empresa_id": EMPRESA_ID,
            "fecha_hasta": "2026-12-31"
        })
        assert response.status_code == 422, f"Expected 422 without fecha_desde, got {response.status_code}"

    def test_exportar_flujo_caja_missing_fecha_hasta(self):
        """Test that exportar flujo-caja returns 422 without fecha_hasta"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/flujo-caja", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": "2025-01-01"
        })
        assert response.status_code == 422, f"Expected 422 without fecha_hasta, got {response.status_code}"


class TestExportarRentabilidad:
    """Tests for /api/reportes/exportar/rentabilidad CSV export endpoint"""

    def test_exportar_rentabilidad_returns_200(self):
        """Test that exportar rentabilidad endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/rentabilidad", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": "2025-01-01",
            "fecha_hasta": "2026-12-31",
            "dimension": "marca"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_exportar_rentabilidad_content_type_csv(self):
        """Test that exportar rentabilidad returns CSV content type"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/rentabilidad", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": "2025-01-01",
            "fecha_hasta": "2026-12-31",
            "dimension": "marca"
        })
        content_type = response.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got {content_type}"

    def test_exportar_rentabilidad_content_disposition(self):
        """Test that exportar rentabilidad has correct Content-Disposition header"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/rentabilidad", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": "2025-01-01",
            "fecha_hasta": "2026-12-31",
            "dimension": "marca"
        })
        content_disposition = response.headers.get("content-disposition", "")
        assert "attachment" in content_disposition, f"Expected attachment in content-disposition"
        assert "filename=" in content_disposition, f"Expected filename in content-disposition"
        assert ".csv" in content_disposition, f"Expected .csv in filename"

    def test_exportar_rentabilidad_csv_headers(self):
        """Test that exportar rentabilidad CSV has correct headers"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/rentabilidad", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": "2025-01-01",
            "fecha_hasta": "2026-12-31",
            "dimension": "marca"
        })
        lines = response.text.strip().split('\n')
        assert len(lines) >= 1, "CSV should have at least header row"
        # Strip carriage returns from headers
        headers = [h.strip() for h in lines[0].split(',')]
        # Expected headers: dimension (Marca), Ingreso, Gasto, Utilidad, Margen %
        assert "Marca" in headers, "CSV should have Marca header (dimension)"
        assert "Ingreso" in headers, "CSV should have Ingreso header"
        assert "Gasto" in headers, "CSV should have Gasto header"
        assert "Utilidad" in headers, "CSV should have Utilidad header"
        assert "Margen %" in headers, "CSV should have Margen % header"


class TestExportarGastos:
    """Tests for /api/reportes/exportar/gastos CSV export endpoint"""

    def test_exportar_gastos_returns_200(self):
        """Test that exportar gastos endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/gastos", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": "2025-01-01",
            "fecha_hasta": "2026-12-31"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_exportar_gastos_content_type_csv(self):
        """Test that exportar gastos returns CSV content type"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/gastos", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": "2025-01-01",
            "fecha_hasta": "2026-12-31"
        })
        content_type = response.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got {content_type}"

    def test_exportar_gastos_content_disposition(self):
        """Test that exportar gastos has correct Content-Disposition header"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/gastos", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": "2025-01-01",
            "fecha_hasta": "2026-12-31"
        })
        content_disposition = response.headers.get("content-disposition", "")
        assert "attachment" in content_disposition, f"Expected attachment in content-disposition"
        assert "filename=" in content_disposition, f"Expected filename in content-disposition"
        assert ".csv" in content_disposition, f"Expected .csv in filename"

    def test_exportar_gastos_csv_headers(self):
        """Test that exportar gastos CSV has correct headers"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/gastos", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": "2025-01-01",
            "fecha_hasta": "2026-12-31"
        })
        lines = response.text.strip().split('\n')
        assert len(lines) >= 1, "CSV should have at least header row"
        # Strip carriage returns from headers
        headers = [h.strip() for h in lines[0].split(',')]
        # Expected headers: ID, Fecha, Nro Doc, Descripcion, Proveedor, Categoria, Subtotal, IGV, Total, Marca, Centro Costo
        assert "ID" in headers, "CSV should have ID header"
        assert "Fecha" in headers, "CSV should have Fecha header"
        assert "Descripcion" in headers, "CSV should have Descripcion header"
        assert "Proveedor" in headers, "CSV should have Proveedor header"
        assert "Categoria" in headers, "CSV should have Categoria header"
        assert "Subtotal" in headers, "CSV should have Subtotal header"
        assert "IGV" in headers, "CSV should have IGV header"
        assert "Total" in headers, "CSV should have Total header"

    def test_exportar_gastos_missing_fecha_desde(self):
        """Test that exportar gastos returns 422 without fecha_desde"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/gastos", params={
            "empresa_id": EMPRESA_ID,
            "fecha_hasta": "2026-12-31"
        })
        assert response.status_code == 422, f"Expected 422 without fecha_desde, got {response.status_code}"

    def test_exportar_gastos_missing_fecha_hasta(self):
        """Test that exportar gastos returns 422 without fecha_hasta"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/gastos", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": "2025-01-01"
        })
        assert response.status_code == 422, f"Expected 422 without fecha_hasta, got {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
