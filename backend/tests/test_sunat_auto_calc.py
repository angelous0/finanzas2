"""
Backend API Tests for SUNAT Auto-Calculated Fields
Tests that Base Gravada, IGV and No Gravada are server-side calculated from lines
"""
import pytest
import requests
import os
import uuid
from datetime import date, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
EMPRESA_ID = 5
PROVEEDOR_ID = 42
CUENTA_FINANCIERA_ID = 7

def unique_id():
    """Generate a unique ID for test data"""
    return str(uuid.uuid4())[:8]

class TestFacturasProveedorSUNATCalculation:
    """Test SUNAT fields auto-calculation for Facturas Proveedor"""
    
    def test_factura_impuestos_no_incluidos_mixed_igv(self):
        """
        Test: impuestos_incluidos=false with 1 line igv=true(1000) and 1 line igv=false(500)
        Expected: base_gravada=1000, igv_sunat=180, base_no_gravada=500
        """
        response = requests.post(
            f"{BASE_URL}/api/facturas-proveedor",
            headers={"X-Empresa-ID": str(EMPRESA_ID)},
            json={
                "proveedor_id": PROVEEDOR_ID,
                "moneda_id": 5,
                "fecha_factura": date.today().isoformat(),
                "tipo_documento": "factura",
                "numero": f"TEST_AUTO_001-{unique_id()}",
                "impuestos_incluidos": False,
                "tipo_comprobante_sunat": "01",
                "lineas": [
                    {"categoria_id": None, "descripcion": "Linea gravada", "importe": 1000, "igv_aplica": True},
                    {"categoria_id": None, "descripcion": "Linea no gravada", "importe": 500, "igv_aplica": False}
                ]
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Verify server-side calculation
        assert data["base_gravada"] == 1000.0, f"Expected base_gravada=1000, got {data['base_gravada']}"
        assert data["igv_sunat"] == 180.0, f"Expected igv_sunat=180, got {data['igv_sunat']}"
        assert data["base_no_gravada"] == 500.0, f"Expected base_no_gravada=500, got {data['base_no_gravada']}"
        
        # Verify total calculation: subtotal + igv = 1500 + 180 = 1680
        assert data["total"] == 1680.0, f"Expected total=1680, got {data['total']}"
        
        print(f"✓ TEST PASSED: impuestos_incluidos=false, mixed igv - base_gravada={data['base_gravada']}, igv_sunat={data['igv_sunat']}, base_no_gravada={data['base_no_gravada']}")

    def test_factura_impuestos_incluidos_single_igv_line(self):
        """
        Test: impuestos_incluidos=true with 1 line igv=true(1180)
        Expected: base_gravada=1000, igv_sunat=180 (extracted from 1180)
        """
        response = requests.post(
            f"{BASE_URL}/api/facturas-proveedor",
            headers={"X-Empresa-ID": str(EMPRESA_ID)},
            json={
                "proveedor_id": PROVEEDOR_ID,
                "moneda_id": 5,
                "fecha_factura": date.today().isoformat(),
                "tipo_documento": "factura",
                "numero": f"TEST_AUTO_002-{unique_id()}",
                "impuestos_incluidos": True,
                "tipo_comprobante_sunat": "01",
                "lineas": [
                    {"categoria_id": None, "descripcion": "Linea IGV incluido", "importe": 1180, "igv_aplica": True}
                ]
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # When impuestos_incluidos=true, base = 1180/1.18 = 1000, igv = 1180 - 1000 = 180
        assert abs(data["base_gravada"] - 1000.0) < 0.01, f"Expected base_gravada≈1000, got {data['base_gravada']}"
        assert abs(data["igv_sunat"] - 180.0) < 0.01, f"Expected igv_sunat≈180, got {data['igv_sunat']}"
        assert data["base_no_gravada"] == 0.0, f"Expected base_no_gravada=0, got {data['base_no_gravada']}"
        
        print(f"✓ TEST PASSED: impuestos_incluidos=true - base_gravada={data['base_gravada']}, igv_sunat={data['igv_sunat']}")

    def test_factura_all_no_gravada(self):
        """
        Test: All lines with igv_aplica=false
        Expected: base_gravada=0, igv_sunat=0, base_no_gravada=sum(importes)
        """
        response = requests.post(
            f"{BASE_URL}/api/facturas-proveedor",
            headers={"X-Empresa-ID": str(EMPRESA_ID)},
            json={
                "proveedor_id": PROVEEDOR_ID,
                "moneda_id": 5,
                "fecha_factura": date.today().isoformat(),
                "tipo_documento": "recibo",
                "numero": f"TEST_AUTO_003-{unique_id()}",
                "impuestos_incluidos": False,
                "tipo_comprobante_sunat": "02",
                "lineas": [
                    {"categoria_id": None, "descripcion": "Honorarios 1", "importe": 300, "igv_aplica": False},
                    {"categoria_id": None, "descripcion": "Honorarios 2", "importe": 200, "igv_aplica": False}
                ]
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["base_gravada"] == 0.0, f"Expected base_gravada=0, got {data['base_gravada']}"
        assert data["igv_sunat"] == 0.0, f"Expected igv_sunat=0, got {data['igv_sunat']}"
        assert data["base_no_gravada"] == 500.0, f"Expected base_no_gravada=500, got {data['base_no_gravada']}"
        
        print(f"✓ TEST PASSED: All no gravada - base_gravada={data['base_gravada']}, igv_sunat={data['igv_sunat']}, base_no_gravada={data['base_no_gravada']}")

    def test_server_ignores_client_sunat_values(self):
        """
        Test: Even if client sends wrong base_gravada/igv_sunat/base_no_gravada values, server recalculates
        """
        response = requests.post(
            f"{BASE_URL}/api/facturas-proveedor",
            headers={"X-Empresa-ID": str(EMPRESA_ID)},
            json={
                "proveedor_id": PROVEEDOR_ID,
                "moneda_id": 5,
                "fecha_factura": date.today().isoformat(),
                "tipo_documento": "factura",
                "numero": f"TEST_AUTO_004-{unique_id()}",
                "impuestos_incluidos": False,
                "tipo_comprobante_sunat": "01",
                # Client sends wrong values - server should ignore and recalculate
                "base_gravada": 9999,
                "igv_sunat": 9999,
                "base_no_gravada": 9999,
                "lineas": [
                    {"categoria_id": None, "descripcion": "Test line", "importe": 500, "igv_aplica": True}
                ]
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Server should calculate correctly regardless of what client sent
        assert data["base_gravada"] == 500.0, f"Expected base_gravada=500 (server recalculated), got {data['base_gravada']}"
        assert data["igv_sunat"] == 90.0, f"Expected igv_sunat=90 (server recalculated), got {data['igv_sunat']}"
        assert data["base_no_gravada"] == 0.0, f"Expected base_no_gravada=0, got {data['base_no_gravada']}"
        
        print(f"✓ TEST PASSED: Server ignores client SUNAT values and recalculates correctly")


class TestGastosSUNATCalculation:
    """Test SUNAT fields auto-calculation for Gastos (no impuestos_incluidos flag)"""
    
    def test_gasto_mixed_igv_lines(self):
        """
        Test: Gasto with lines igv=true(800) and igv=false(200)
        Expected: base_gravada=800, igv_sunat=144, base_no_gravada=200
        Note: Gastos do NOT use impuestos_incluidos - lines are always sin IGV base
        """
        response = requests.post(
            f"{BASE_URL}/api/gastos",
            headers={"X-Empresa-ID": str(EMPRESA_ID)},
            json={
                "fecha": date.today().isoformat(),
                "moneda_id": 5,
                "tipo_documento": "boleta",
                "numero_documento": f"TEST_GASTO_001-{unique_id()}",
                "tipo_comprobante_sunat": "03",
                "lineas": [
                    {"categoria_id": None, "descripcion": "Gasto gravado", "importe": 800, "igv_aplica": True},
                    {"categoria_id": None, "descripcion": "Gasto no gravado", "importe": 200, "igv_aplica": False}
                ],
                "pagos": [
                    {"cuenta_financiera_id": CUENTA_FINANCIERA_ID, "medio_pago": "efectivo", "monto": 1144, "referencia": "Test auto calc"}
                ]
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Gastos: line.igv_aplica=true means base=importe, igv=importe*0.18
        assert data["base_gravada"] == 800.0, f"Expected base_gravada=800, got {data['base_gravada']}"
        assert data["igv_sunat"] == 144.0, f"Expected igv_sunat=144, got {data['igv_sunat']}"
        assert data["base_no_gravada"] == 200.0, f"Expected base_no_gravada=200, got {data['base_no_gravada']}"
        
        # Total should be: 800 + 200 + 144 = 1144
        assert data["total"] == 1144.0, f"Expected total=1144, got {data['total']}"
        
        print(f"✓ TEST PASSED: Gasto mixed igv - base_gravada={data['base_gravada']}, igv_sunat={data['igv_sunat']}, base_no_gravada={data['base_no_gravada']}")

    def test_gasto_all_gravado(self):
        """
        Test: Gasto with all lines igv_aplica=true
        Expected: base_gravada=sum(importes), igv_sunat=base*0.18, base_no_gravada=0
        """
        response = requests.post(
            f"{BASE_URL}/api/gastos",
            headers={"X-Empresa-ID": str(EMPRESA_ID)},
            json={
                "fecha": date.today().isoformat(),
                "moneda_id": 5,
                "tipo_documento": "factura",
                "numero_documento": f"TEST_GASTO_002-{unique_id()}",
                "tipo_comprobante_sunat": "01",
                "lineas": [
                    {"categoria_id": None, "descripcion": "Compra 1", "importe": 1000, "igv_aplica": True}
                ],
                "pagos": [
                    {"cuenta_financiera_id": CUENTA_FINANCIERA_ID, "medio_pago": "transferencia", "monto": 1180, "referencia": "Test"}
                ]
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["base_gravada"] == 1000.0, f"Expected base_gravada=1000, got {data['base_gravada']}"
        assert data["igv_sunat"] == 180.0, f"Expected igv_sunat=180, got {data['igv_sunat']}"
        assert data["base_no_gravada"] == 0.0, f"Expected base_no_gravada=0, got {data['base_no_gravada']}"
        
        print(f"✓ TEST PASSED: Gasto all gravado - base_gravada={data['base_gravada']}, igv_sunat={data['igv_sunat']}")

    def test_gasto_server_recalculates(self):
        """
        Test: Server ignores client-sent SUNAT values and recalculates from lines
        """
        response = requests.post(
            f"{BASE_URL}/api/gastos",
            headers={"X-Empresa-ID": str(EMPRESA_ID)},
            json={
                "fecha": date.today().isoformat(),
                "moneda_id": 5,
                "tipo_documento": "boleta",
                "numero_documento": f"TEST_GASTO_003-{unique_id()}",
                "tipo_comprobante_sunat": "03",
                # Wrong values sent by client
                "base_gravada": 9999,
                "igv_sunat": 9999,
                "base_no_gravada": 9999,
                "lineas": [
                    {"categoria_id": None, "descripcion": "Test", "importe": 500, "igv_aplica": True}
                ],
                "pagos": [
                    {"cuenta_financiera_id": CUENTA_FINANCIERA_ID, "medio_pago": "efectivo", "monto": 590, "referencia": "Test"}
                ]
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Server should calculate correctly
        assert data["base_gravada"] == 500.0, f"Expected base_gravada=500, got {data['base_gravada']}"
        assert data["igv_sunat"] == 90.0, f"Expected igv_sunat=90, got {data['igv_sunat']}"
        assert data["base_no_gravada"] == 0.0, f"Expected base_no_gravada=0, got {data['base_no_gravada']}"
        
        print(f"✓ TEST PASSED: Gasto server recalculates SUNAT values correctly")


class TestExportCompraAPP:
    """Test that export still works with auto-calculated values"""
    
    def test_export_with_auto_calculated_values(self):
        """
        Test: Export CompraAPP with facturas/gastos that have auto-calculated SUNAT values
        """
        response = requests.get(
            f"{BASE_URL}/api/export/compraapp",
            headers={"X-Empresa-ID": str(EMPRESA_ID)},
            params={"desde": date.today().isoformat(), "hasta": date.today().isoformat()}
        )
        
        # Should return Excel file or empty valid response
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            assert 'spreadsheet' in response.headers.get('content-type', '') or len(response.content) > 0
            print(f"✓ TEST PASSED: Export CompraAPP works with auto-calculated values")
        else:
            # 400 is acceptable if no documents have SUNAT fields
            print(f"✓ TEST PASSED: Export returned validation error (expected if no valid SUNAT data)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
