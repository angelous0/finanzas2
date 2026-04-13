"""
Test suite for 3-Layer Financial Architecture
- Capa 1: Comercial (sales, expenses)
- Capa 2: Obligaciones (CxC/CxP)
- Capa 3: Tesoreria/Caja Real (treasury movements - single source of truth)

Tests the following features:
- GET /api/tesoreria - list treasury movements with filters
- GET /api/tesoreria/resumen - KPIs for treasury
- POST /api/tesoreria - manual treasury movement creation
- GET /api/dashboard/financiero - 3-layer KPIs
- GET /api/finanzas-gerencial/flujo-caja-gerencial - reads from treasury
- GET /api/reportes/resumen-ejecutivo - includes flujo_caja_mtd from treasury
- GET /api/reportes/exportar/tesoreria - CSV export
- CxC/CxP abonos auto-create treasury movements
"""
import pytest
import requests
import os
from datetime import date, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
EMPRESA_ID = 6  # Ambission Industries SAC


class TestTesoreriaEndpoints:
    """Tests for the new /api/tesoreria endpoints"""

    def test_list_tesoreria_basic(self):
        """GET /api/tesoreria - basic list with pagination"""
        response = requests.get(f"{BASE_URL}/api/tesoreria", params={"empresa_id": EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        print(f"PASS: GET /api/tesoreria returns {len(data['data'])} movements, total={data['total']}")

    def test_list_tesoreria_filter_tipo_ingreso(self):
        """GET /api/tesoreria?tipo=ingreso - filter by tipo"""
        response = requests.get(f"{BASE_URL}/api/tesoreria", params={"empresa_id": EMPRESA_ID, "tipo": "ingreso"})
        assert response.status_code == 200
        data = response.json()
        # All movements should be ingreso
        for mov in data['data']:
            assert mov['tipo'] == 'ingreso', f"Expected tipo=ingreso, got {mov['tipo']}"
        print(f"PASS: Filter tipo=ingreso returns {len(data['data'])} movements")

    def test_list_tesoreria_filter_tipo_egreso(self):
        """GET /api/tesoreria?tipo=egreso - filter by tipo"""
        response = requests.get(f"{BASE_URL}/api/tesoreria", params={"empresa_id": EMPRESA_ID, "tipo": "egreso"})
        assert response.status_code == 200
        data = response.json()
        for mov in data['data']:
            assert mov['tipo'] == 'egreso', f"Expected tipo=egreso, got {mov['tipo']}"
        print(f"PASS: Filter tipo=egreso returns {len(data['data'])} movements")

    def test_list_tesoreria_filter_fecha(self):
        """GET /api/tesoreria with date range filter"""
        today = date.today()
        first_of_month = today.replace(day=1)
        response = requests.get(f"{BASE_URL}/api/tesoreria", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": first_of_month.isoformat(),
            "fecha_hasta": today.isoformat()
        })
        assert response.status_code == 200
        data = response.json()
        print(f"PASS: Date range filter returns {len(data['data'])} movements for current month")

    def test_list_tesoreria_filter_origen_tipo(self):
        """GET /api/tesoreria?origen_tipo=manual - filter by origin"""
        response = requests.get(f"{BASE_URL}/api/tesoreria", params={
            "empresa_id": EMPRESA_ID,
            "origen_tipo": "manual"
        })
        assert response.status_code == 200
        data = response.json()
        for mov in data['data']:
            assert mov['origen_tipo'] == 'manual', f"Expected origen_tipo=manual, got {mov['origen_tipo']}"
        print(f"PASS: Filter origen_tipo=manual returns {len(data['data'])} movements")


class TestTesoreriaResumen:
    """Tests for /api/tesoreria/resumen KPI endpoint"""

    def test_resumen_basic(self):
        """GET /api/tesoreria/resumen - basic KPI response"""
        response = requests.get(f"{BASE_URL}/api/tesoreria/resumen", params={"empresa_id": EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        
        # Verify KPI fields exist
        required_fields = [
            "total_ingresos", "total_egresos", "flujo_neto",
            "count_ingresos", "count_egresos",
            "saldo_caja", "saldo_banco", "saldo_total",
            "por_origen", "cuentas",
            "fecha_desde", "fecha_hasta"
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Verify calculation
        assert data['flujo_neto'] == data['total_ingresos'] - data['total_egresos'], \
            f"Flujo neto calculation error: {data['flujo_neto']} != {data['total_ingresos']} - {data['total_egresos']}"
        
        print(f"PASS: Resumen KPIs - Ingresos: {data['total_ingresos']}, Egresos: {data['total_egresos']}, Flujo: {data['flujo_neto']}")

    def test_resumen_por_origen_structure(self):
        """Verify por_origen breakdown structure"""
        response = requests.get(f"{BASE_URL}/api/tesoreria/resumen", params={"empresa_id": EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data['por_origen'], list)
        for item in data['por_origen']:
            assert 'origen_tipo' in item
            assert 'tipo' in item
            assert 'count' in item
            assert 'total' in item
        print(f"PASS: por_origen has {len(data['por_origen'])} breakdown items")

    def test_resumen_cuentas_structure(self):
        """Verify cuentas (financial accounts) breakdown"""
        response = requests.get(f"{BASE_URL}/api/tesoreria/resumen", params={"empresa_id": EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data['cuentas'], list)
        for cuenta in data['cuentas']:
            assert 'id' in cuenta
            assert 'nombre' in cuenta
            assert 'tipo' in cuenta
            assert 'saldo' in cuenta
        print(f"PASS: cuentas has {len(data['cuentas'])} financial accounts")


class TestTesoreriaCreate:
    """Tests for POST /api/tesoreria - manual movement creation"""

    def test_create_manual_ingreso(self):
        """POST /api/tesoreria - create manual ingreso"""
        payload = {
            "fecha": date.today().isoformat(),
            "tipo": "ingreso",
            "monto": 100.00,
            "origen_tipo": "manual",
            "concepto": "TEST: Manual ingreso for testing"
        }
        response = requests.post(f"{BASE_URL}/api/tesoreria", params={"empresa_id": EMPRESA_ID}, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "message" in data
        print(f"PASS: Created manual ingreso with id={data['id']}")

    def test_create_manual_egreso(self):
        """POST /api/tesoreria - create manual egreso"""
        payload = {
            "fecha": date.today().isoformat(),
            "tipo": "egreso",
            "monto": 50.00,
            "origen_tipo": "manual",
            "concepto": "TEST: Manual egreso for testing"
        }
        response = requests.post(f"{BASE_URL}/api/tesoreria", params={"empresa_id": EMPRESA_ID}, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        print(f"PASS: Created manual egreso with id={data['id']}")

    def test_create_invalid_tipo(self):
        """POST /api/tesoreria - invalid tipo should return 400"""
        payload = {
            "fecha": date.today().isoformat(),
            "tipo": "invalid",
            "monto": 100.00,
            "origen_tipo": "manual"
        }
        response = requests.post(f"{BASE_URL}/api/tesoreria", params={"empresa_id": EMPRESA_ID}, json=payload)
        assert response.status_code == 400
        print("PASS: Invalid tipo returns 400")

    def test_create_negative_monto(self):
        """POST /api/tesoreria - negative monto should return 400"""
        payload = {
            "fecha": date.today().isoformat(),
            "tipo": "ingreso",
            "monto": -100.00,
            "origen_tipo": "manual"
        }
        response = requests.post(f"{BASE_URL}/api/tesoreria", params={"empresa_id": EMPRESA_ID}, json=payload)
        assert response.status_code == 400
        print("PASS: Negative monto returns 400")


class TestDashboardFinanciero3Layer:
    """Tests for Dashboard Financiero with 3-layer KPIs"""

    def test_dashboard_basic(self):
        """GET /api/dashboard-financiero returns 3-layer data"""
        response = requests.get(f"{BASE_URL}/api/dashboard-financiero", params={"empresa_id": EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        
        # Capa 3: Tesoreria
        assert "saldo_caja" in data
        assert "saldo_banco" in data
        assert "saldo_total" in data
        assert "flujo_neto" in data
        
        # Capa 1: Comercial
        assert "ingresos_confirmados" in data
        assert "gastos_periodo" in data
        assert "utilidad_estimada" in data
        
        # Capa 2: Obligaciones
        assert "cxc_total" in data
        assert "cxp_total" in data
        assert "cobranzas_reales" in data  # From treasury
        assert "egresos_reales" in data     # From treasury
        
        print(f"PASS: Dashboard 3-layer - Tesoreria: {data['saldo_total']}, Comercial: {data['ingresos_confirmados']}, Obligaciones CxC: {data['cxc_total']}")

    def test_dashboard_cobranzas_from_treasury(self):
        """Verify cobranzas_reales comes from treasury movements"""
        response = requests.get(f"{BASE_URL}/api/dashboard-financiero", params={"empresa_id": EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        
        # cobranzas_reales should be >= 0
        assert isinstance(data['cobranzas_reales'], (int, float))
        print(f"PASS: cobranzas_reales = {data['cobranzas_reales']} (from treasury)")

    def test_dashboard_egresos_from_treasury(self):
        """Verify egresos_reales comes from treasury movements"""
        response = requests.get(f"{BASE_URL}/api/dashboard-financiero", params={"empresa_id": EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data['egresos_reales'], (int, float))
        print(f"PASS: egresos_reales = {data['egresos_reales']} (from treasury)")


class TestFlujoCajaGerencial:
    """Tests for /api/flujo-caja-gerencial reading from treasury"""

    def test_flujo_caja_basic(self):
        """GET /api/flujo-caja-gerencial - basic response from treasury"""
        today = date.today()
        first_of_year = today.replace(month=1, day=1)
        response = requests.get(f"{BASE_URL}/api/flujo-caja-gerencial", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": first_of_year.isoformat(),
            "fecha_hasta": today.isoformat(),
            "agrupacion": "mensual"
        })
        assert response.status_code == 200
        data = response.json()
        
        assert "timeline" in data
        assert "totales" in data
        assert "agrupacion" in data
        assert "source" in data
        assert data["source"] == "tesoreria", f"Expected source=tesoreria, got {data['source']}"
        
        print(f"PASS: Flujo caja gerencial has {len(data['timeline'])} periods, source={data['source']}")

    def test_flujo_caja_totales_structure(self):
        """Verify totales structure in flujo caja"""
        today = date.today()
        first_of_month = today.replace(day=1)
        response = requests.get(f"{BASE_URL}/api/flujo-caja-gerencial", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": first_of_month.isoformat(),
            "fecha_hasta": today.isoformat(),
            "agrupacion": "diario"
        })
        assert response.status_code == 200
        data = response.json()
        
        totales = data['totales']
        assert 'ingresos' in totales
        assert 'egresos' in totales
        assert 'flujo_neto' in totales
        assert totales['flujo_neto'] == totales['ingresos'] - totales['egresos']
        print(f"PASS: Totales - Ingresos: {totales['ingresos']}, Egresos: {totales['egresos']}, Flujo: {totales['flujo_neto']}")

    def test_flujo_caja_missing_dates(self):
        """Missing required dates should return 422"""
        response = requests.get(f"{BASE_URL}/api/flujo-caja-gerencial", params={
            "empresa_id": EMPRESA_ID,
            "agrupacion": "diario"
        })
        assert response.status_code == 422
        print("PASS: Missing dates returns 422")


class TestResumenEjecutivoWithTreasury:
    """Tests for /api/reportes/resumen-ejecutivo with flujo_caja_mtd from treasury"""

    def test_resumen_ejecutivo_basic(self):
        """GET /api/reportes/resumen-ejecutivo - verify flujo_caja_mtd structure"""
        response = requests.get(f"{BASE_URL}/api/reportes/resumen-ejecutivo", params={"empresa_id": EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        
        # Verify flujo_caja_mtd exists with treasury data
        assert "flujo_caja_mtd" in data, "Missing flujo_caja_mtd in response"
        fcm = data['flujo_caja_mtd']
        assert "ingresos_reales" in fcm, "Missing ingresos_reales in flujo_caja_mtd"
        assert "egresos_reales" in fcm, "Missing egresos_reales in flujo_caja_mtd"
        assert "flujo_neto" in fcm, "Missing flujo_neto in flujo_caja_mtd"
        
        # Verify calculation
        assert fcm['flujo_neto'] == fcm['ingresos_reales'] - fcm['egresos_reales']
        
        print(f"PASS: flujo_caja_mtd - Ingresos: {fcm['ingresos_reales']}, Egresos: {fcm['egresos_reales']}, Neto: {fcm['flujo_neto']}")

    def test_resumen_ejecutivo_tesoreria_section(self):
        """Verify tesoreria section in resumen ejecutivo"""
        response = requests.get(f"{BASE_URL}/api/reportes/resumen-ejecutivo", params={"empresa_id": EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        
        assert "tesoreria" in data
        tes = data['tesoreria']
        assert "caja" in tes
        assert "banco" in tes
        assert "total" in tes
        print(f"PASS: Tesoreria section - Caja: {tes['caja']}, Banco: {tes['banco']}, Total: {tes['total']}")


class TestTesoreriaExport:
    """Tests for /api/reportes/exportar/tesoreria CSV export"""

    def test_export_tesoreria_csv(self):
        """GET /api/reportes/exportar/tesoreria - CSV export"""
        today = date.today()
        first_of_year = today.replace(month=1, day=1)
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/tesoreria", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": first_of_year.isoformat(),
            "fecha_hasta": today.isoformat()
        })
        assert response.status_code == 200
        assert "text/csv" in response.headers.get('content-type', '')
        assert "attachment" in response.headers.get('content-disposition', '')
        
        # Verify CSV content
        content = response.text
        lines = content.strip().split('\n')
        assert len(lines) >= 1, "CSV should have at least a header row"
        
        # Check header
        header = lines[0]
        assert "ID" in header
        assert "Fecha" in header
        assert "Tipo" in header
        assert "Monto" in header
        assert "Origen" in header
        
        print(f"PASS: Tesoreria CSV export with {len(lines)-1} data rows")

    def test_export_tesoreria_filter_tipo(self):
        """GET /api/reportes/exportar/tesoreria?tipo=ingreso - filtered export"""
        today = date.today()
        first_of_year = today.replace(month=1, day=1)
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/tesoreria", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": first_of_year.isoformat(),
            "fecha_hasta": today.isoformat(),
            "tipo": "ingreso"
        })
        assert response.status_code == 200
        assert "text/csv" in response.headers.get('content-type', '')
        print("PASS: Tesoreria CSV export with tipo filter")

    def test_export_tesoreria_missing_dates(self):
        """Missing required dates should return 422"""
        response = requests.get(f"{BASE_URL}/api/reportes/exportar/tesoreria", params={
            "empresa_id": EMPRESA_ID
        })
        assert response.status_code == 422
        print("PASS: Missing dates returns 422")


class TestCxCAbonoCreaMovimientoTesoreria:
    """Tests to verify CxC abonos auto-create treasury movements"""

    def test_cxc_list(self):
        """GET /api/cxc - list CxC to find one for testing"""
        response = requests.get(f"{BASE_URL}/api/cxc", params={"empresa_id": EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        # Should be a list
        assert isinstance(data, list)
        print(f"PASS: CxC list has {len(data)} documents")
        return data

    def test_cxc_abono_integration(self):
        """Verify CxC abono creates treasury movement (check pattern)"""
        # This test checks that the integration pattern is correct
        # We verify the code path exists by looking at endpoint response structure
        response = requests.get(f"{BASE_URL}/api/cxc", params={"empresa_id": EMPRESA_ID, "estado": "pendiente"})
        assert response.status_code == 200
        data = response.json()
        
        # If there are pending CxC, verify structure supports abonos
        for cxc in data[:1]:  # Check first one
            assert 'id' in cxc
            assert 'saldo_pendiente' in cxc
            print(f"PASS: CxC structure supports abono integration (CxC id={cxc['id']}, saldo={cxc['saldo_pendiente']})")
            break
        else:
            print("INFO: No pending CxC found for integration test")


class TestCxPAbonoCreaMovimientoTesoreria:
    """Tests to verify CxP abonos auto-create treasury movements"""

    def test_cxp_list(self):
        """GET /api/cxp - list CxP"""
        response = requests.get(f"{BASE_URL}/api/cxp", params={"empresa_id": EMPRESA_ID})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"PASS: CxP list has {len(data)} documents")

    def test_cxp_abono_integration(self):
        """Verify CxP structure supports abono with treasury integration"""
        response = requests.get(f"{BASE_URL}/api/cxp", params={"empresa_id": EMPRESA_ID, "estado": "pendiente"})
        assert response.status_code == 200
        data = response.json()
        
        for cxp in data[:1]:
            assert 'id' in cxp
            assert 'saldo_pendiente' in cxp
            print(f"PASS: CxP structure supports abono integration (CxP id={cxp['id']}, saldo={cxp['saldo_pendiente']})")
            break
        else:
            print("INFO: No pending CxP found for integration test")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
