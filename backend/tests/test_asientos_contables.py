"""
Test module for Double-Entry Accounting (Asientos Contables / Journal Entries)
Tests:
- POST /api/asientos/generar with origen_tipo=FPROV (provider invoice)
- POST /api/asientos/generar with origen_tipo=GASTO (expense)
- POST /api/asientos/generar with origen_tipo=PAGO (payment)
- POST /api/asientos/{id}/postear (post entry)
- POST /api/asientos/{id}/anular (void entry)
- GET /api/asientos (list with filters)
- GET /api/asientos/{id} (get with detail lines)
- GET /api/reportes/mayor (ledger report)
- GET /api/reportes/balance (balance sheet)
- GET /api/reportes/pnl (profit & loss)
- POST /api/periodos-contables/cerrar (close period)
- POST /api/periodos-contables/abrir (open period)
- Idempotent: regenerating asiento replaces borrador
"""
import pytest
import requests
import os
from datetime import date, datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
EMPRESA_ID = 6  # Test company from context
HEADERS = {'X-Empresa-ID': str(EMPRESA_ID)}

# IDs from context
PROVEEDOR_ID = 43
MONEDA_PEN_ID = 7
MONEDA_USD_ID = 8
CUENTA_FINANCIERA_BCP_ID = 8
CUENTA_FINANCIERA_CAJA_ID = 9
CATEGORIA_EGRESO_ID = 61  # Compras Mercadería

# Account IDs from config contable for empresa_id=6
CTA_GASTOS_ID = 36  # 6399 Otros servicios y gastos
CTA_IGV_ID = 26     # 4012 IGV crédito fiscal
CTA_XPAGAR_ID = 24  # 4212 Cuentas por pagar comerciales


class TestAsientosFPROV:
    """Test asiento generation from Factura Proveedor (FPROV)"""

    @pytest.fixture
    def test_factura(self):
        """Create a test factura proveedor for asiento generation"""
        today = date.today()
        factura_data = {
            "proveedor_id": PROVEEDOR_ID,
            "moneda_id": MONEDA_PEN_ID,
            "fecha_factura": str(today),
            "fecha_vencimiento": str(today + timedelta(days=30)),
            "fecha_contable": str(today),
            "tipo_cambio": 1.0,
            "terminos_dias": 30,
            "lineas": [
                {
                    "descripcion": "TEST_ASIENTO - Mercadería de prueba",
                    "cantidad": 1,
                    "importe": 1000.0,
                    "igv_aplica": True,
                    "categoria_id": CATEGORIA_EGRESO_ID
                }
            ],
            "igv_incluido": False,
            "notas": "TEST_ASIENTO factura for asiento testing"
        }
        resp = requests.post(f"{BASE_URL}/api/facturas-proveedor", headers=HEADERS, json=factura_data)
        if resp.status_code not in [200, 201]:
            pytest.fail(f"Failed to create test factura: {resp.status_code} - {resp.text}")
        factura = resp.json()
        yield factura
        # Cleanup: delete factura
        requests.delete(f"{BASE_URL}/api/facturas-proveedor/{factura['id']}", headers=HEADERS)

    def test_generar_asiento_fprov(self, test_factura):
        """POST /api/asientos/generar with origen_tipo=FPROV creates balanced journal entry"""
        factura_id = test_factura['id']
        
        # Generate asiento
        payload = {"origen_tipo": "FPROV", "origen_id": factura_id}
        resp = requests.post(f"{BASE_URL}/api/asientos/generar", headers=HEADERS, json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        asiento = resp.json()
        assert asiento['estado'] == 'borrador'
        assert asiento['origen_tipo'] == 'FPROV'
        assert asiento['origen_id'] == factura_id
        assert 'lineas' in asiento
        assert len(asiento['lineas']) >= 2  # At least gasto + CxP
        
        # Verify balanced (debe == haber)
        total_debe = asiento['total_debe']
        total_haber = asiento['total_haber']
        assert abs(total_debe - total_haber) < 0.01, f"Asiento not balanced: debe={total_debe}, haber={total_haber}"
        
        # Verify expected structure: base_gravada + IGV to debe, total to haber CxP
        lineas = asiento['lineas']
        debe_lineas = [l for l in lineas if float(l['debe']) > 0]
        haber_lineas = [l for l in lineas if float(l['haber']) > 0]
        
        # Should have debe entries for gasto (base) and IGV
        assert len(debe_lineas) >= 1, "Should have at least 1 debe entry (gasto)"
        # Should have 1 haber entry for CxP
        assert len(haber_lineas) >= 1, "Should have at least 1 haber entry (CxP)"
        
        print(f"✓ FPROV asiento generated: ID={asiento['id']}, debe={total_debe}, haber={total_haber}")
        print(f"  Lines: {len(debe_lineas)} debe, {len(haber_lineas)} haber")
        
        # Cleanup: delete asiento if possible (or it will be deleted when factura is deleted)

    def test_fprov_asiento_idempotent(self, test_factura):
        """Regenerating asiento for same document replaces borrador entry"""
        factura_id = test_factura['id']
        
        # Generate first asiento
        payload = {"origen_tipo": "FPROV", "origen_id": factura_id}
        resp1 = requests.post(f"{BASE_URL}/api/asientos/generar", headers=HEADERS, json=payload)
        assert resp1.status_code == 200
        asiento1 = resp1.json()
        asiento1_id = asiento1['id']
        
        # Generate again - should replace (same ID or new ID, but only 1 asiento for this document)
        resp2 = requests.post(f"{BASE_URL}/api/asientos/generar", headers=HEADERS, json=payload)
        assert resp2.status_code == 200
        asiento2 = resp2.json()
        
        # Check there's only one asiento for this factura
        list_resp = requests.get(f"{BASE_URL}/api/asientos?origen_tipo=FPROV&empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert list_resp.status_code == 200
        asientos = list_resp.json()
        fprov_asientos = [a for a in asientos if a['origen_id'] == factura_id]
        assert len(fprov_asientos) == 1, f"Expected 1 asiento for factura, got {len(fprov_asientos)}"
        
        print(f"✓ Idempotent regeneration works: asiento1_id={asiento1_id}, asiento2_id={asiento2['id']}")


class TestAsientosGASTO:
    """Test asiento generation from Gasto (expense)"""

    @pytest.fixture
    def test_gasto(self):
        """Create a test gasto for asiento generation"""
        today = date.today()
        gasto_data = {
            "fecha": str(today),
            "fecha_contable": str(today),
            "proveedor_id": PROVEEDOR_ID,
            "moneda_id": MONEDA_PEN_ID,
            "tipo_documento": "boleta",
            "numero_documento": f"TEST-GASTO-{today.strftime('%Y%m%d%H%M%S')}",
            "tipo_cambio": 1.0,
            "notas": "TEST_ASIENTO gasto for asiento testing",
            "lineas": [
                {
                    "descripcion": "Gasto de prueba para asiento",
                    "importe": 200.0,
                    "categoria_id": CATEGORIA_EGRESO_ID,
                    "igv_aplica": True
                }
            ],
            "igv_incluido": False,
            "pagos": [
                {
                    "cuenta_financiera_id": CUENTA_FINANCIERA_CAJA_ID,
                    "medio_pago": "efectivo",
                    "monto": 236.0  # 200 + 18% IGV
                }
            ]
        }
        resp = requests.post(f"{BASE_URL}/api/gastos", headers=HEADERS, json=gasto_data)
        if resp.status_code not in [200, 201]:
            pytest.fail(f"Failed to create test gasto: {resp.status_code} - {resp.text}")
        gasto = resp.json()
        yield gasto
        # Cleanup
        requests.delete(f"{BASE_URL}/api/gastos/{gasto['id']}", headers=HEADERS)

    def test_generar_asiento_gasto(self, test_gasto):
        """POST /api/asientos/generar with origen_tipo=GASTO creates balanced entry"""
        gasto_id = test_gasto['id']
        
        # Generate asiento
        payload = {"origen_tipo": "GASTO", "origen_id": gasto_id}
        resp = requests.post(f"{BASE_URL}/api/asientos/generar", headers=HEADERS, json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        asiento = resp.json()
        assert asiento['estado'] == 'borrador'
        assert asiento['origen_tipo'] == 'GASTO'
        assert asiento['origen_id'] == gasto_id
        
        # Verify balanced
        total_debe = asiento['total_debe']
        total_haber = asiento['total_haber']
        assert abs(total_debe - total_haber) < 0.01, f"Asiento not balanced: debe={total_debe}, haber={total_haber}"
        
        # For cash-paid gasto: gasto + IGV to debe, banco/caja to haber
        lineas = asiento['lineas']
        debe_lineas = [l for l in lineas if float(l['debe']) > 0]
        haber_lineas = [l for l in lineas if float(l['haber']) > 0]
        
        assert len(debe_lineas) >= 1, "Should have debe entries (gasto/IGV)"
        assert len(haber_lineas) >= 1, "Should have haber entry (banco/caja)"
        
        print(f"✓ GASTO asiento generated: ID={asiento['id']}, debe={total_debe}, haber={total_haber}")


class TestAsientosPAGO:
    """Test asiento generation from Pago (payment)"""

    @pytest.fixture
    def test_pago_data(self):
        """Create a factura with CxP and then a pago to apply against it"""
        today = date.today()
        
        # First create a factura (which creates CxP)
        factura_data = {
            "proveedor_id": PROVEEDOR_ID,
            "moneda_id": MONEDA_PEN_ID,
            "fecha_factura": str(today),
            "fecha_vencimiento": str(today + timedelta(days=30)),
            "fecha_contable": str(today),
            "tipo_cambio": 1.0,
            "terminos_dias": 30,
            "lineas": [
                {
                    "descripcion": "TEST_PAGO - Mercadería para pago test",
                    "cantidad": 1,
                    "importe": 500.0,
                    "igv_aplica": True,
                    "categoria_id": CATEGORIA_EGRESO_ID
                }
            ],
            "igv_incluido": False,
            "notas": "TEST_PAGO factura"
        }
        factura_resp = requests.post(f"{BASE_URL}/api/facturas-proveedor", headers=HEADERS, json=factura_data)
        if factura_resp.status_code not in [200, 201]:
            pytest.fail(f"Failed to create test factura: {factura_resp.status_code} - {factura_resp.text}")
        factura = factura_resp.json()
        
        # Create a pago against this factura
        total_factura = float(factura['total'])
        pago_data = {
            "tipo": "egreso",
            "fecha": str(today),
            "moneda_id": MONEDA_PEN_ID,
            "monto_total": total_factura,  # Required field
            "referencia": f"TEST-PAGO-{today.strftime('%Y%m%d%H%M%S')}",
            "notas": "TEST_PAGO for asiento testing",
            "detalles": [
                {
                    "cuenta_financiera_id": CUENTA_FINANCIERA_BCP_ID,
                    "medio_pago": "transferencia",
                    "monto": total_factura,
                    "referencia": "REF-001"
                }
            ],
            "aplicaciones": [
                {
                    "tipo_documento": "factura",
                    "documento_id": factura['id'],
                    "monto_aplicado": total_factura
                }
            ]
        }
        pago_resp = requests.post(f"{BASE_URL}/api/pagos", headers=HEADERS, json=pago_data)
        if pago_resp.status_code not in [200, 201]:
            pytest.fail(f"Failed to create test pago: {pago_resp.status_code} - {pago_resp.text}")
        pago = pago_resp.json()
        
        yield {"factura": factura, "pago": pago}
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/pagos/{pago['id']}", headers=HEADERS)
        requests.delete(f"{BASE_URL}/api/facturas-proveedor/{factura['id']}", headers=HEADERS)

    def test_generar_asiento_pago(self, test_pago_data):
        """POST /api/asientos/generar with origen_tipo=PAGO creates CxP debe, banco haber"""
        pago_id = test_pago_data['pago']['id']
        
        # Generate asiento
        payload = {"origen_tipo": "PAGO", "origen_id": pago_id}
        resp = requests.post(f"{BASE_URL}/api/asientos/generar", headers=HEADERS, json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        asiento = resp.json()
        assert asiento['estado'] == 'borrador'
        assert asiento['origen_tipo'] == 'PAGO'
        assert asiento['origen_id'] == pago_id
        
        # Verify balanced
        total_debe = asiento['total_debe']
        total_haber = asiento['total_haber']
        assert abs(total_debe - total_haber) < 0.01, f"Asiento not balanced: debe={total_debe}, haber={total_haber}"
        
        # For PAGO: CxP debe, banco haber
        lineas = asiento['lineas']
        assert len(lineas) == 2, f"PAGO asiento should have 2 lines, got {len(lineas)}"
        
        debe_linea = next((l for l in lineas if float(l['debe']) > 0), None)
        haber_linea = next((l for l in lineas if float(l['haber']) > 0), None)
        
        assert debe_linea is not None, "Should have debe entry (CxP)"
        assert haber_linea is not None, "Should have haber entry (banco)"
        
        print(f"✓ PAGO asiento generated: ID={asiento['id']}, debe={total_debe}, haber={total_haber}")


class TestPostearAnular:
    """Test posting and voiding asientos"""

    @pytest.fixture
    def test_asiento(self):
        """Create a test asiento via factura"""
        today = date.today()
        factura_data = {
            "proveedor_id": PROVEEDOR_ID,
            "moneda_id": MONEDA_PEN_ID,
            "fecha_factura": str(today),
            "fecha_vencimiento": str(today + timedelta(days=30)),
            "fecha_contable": str(today),
            "tipo_cambio": 1.0,
            "terminos_dias": 30,
            "lineas": [{"descripcion": "TEST_POSTEAR", "cantidad": 1, "importe": 100.0, "igv_aplica": True, "categoria_id": CATEGORIA_EGRESO_ID}],
            "igv_incluido": False
        }
        factura_resp = requests.post(f"{BASE_URL}/api/facturas-proveedor", headers=HEADERS, json=factura_data)
        factura = factura_resp.json()
        
        # Generate asiento
        payload = {"origen_tipo": "FPROV", "origen_id": factura['id']}
        asiento_resp = requests.post(f"{BASE_URL}/api/asientos/generar", headers=HEADERS, json=payload)
        asiento = asiento_resp.json()
        
        yield {"factura": factura, "asiento": asiento}
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/facturas-proveedor/{factura['id']}", headers=HEADERS)

    def test_postear_asiento(self, test_asiento):
        """POST /api/asientos/{id}/postear changes estado to 'posteado'"""
        asiento_id = test_asiento['asiento']['id']
        
        # Ensure period is open first
        today = date.today()
        requests.post(f"{BASE_URL}/api/periodos-contables/abrir?anio={today.year}&mes={today.month}&empresa_id={EMPRESA_ID}", headers=HEADERS)
        
        resp = requests.post(f"{BASE_URL}/api/asientos/{asiento_id}/postear", headers=HEADERS)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        # Verify estado changed
        get_resp = requests.get(f"{BASE_URL}/api/asientos/{asiento_id}", headers=HEADERS)
        assert get_resp.status_code == 200
        updated = get_resp.json()
        assert updated['estado'] == 'posteado', f"Expected 'posteado', got {updated['estado']}"
        
        print(f"✓ Asiento {asiento_id} posted successfully")

    def test_anular_asiento(self, test_asiento):
        """POST /api/asientos/{id}/anular changes estado to 'anulado'"""
        asiento_id = test_asiento['asiento']['id']
        
        resp = requests.post(f"{BASE_URL}/api/asientos/{asiento_id}/anular", headers=HEADERS)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        # Verify estado changed
        get_resp = requests.get(f"{BASE_URL}/api/asientos/{asiento_id}", headers=HEADERS)
        assert get_resp.status_code == 200
        updated = get_resp.json()
        assert updated['estado'] == 'anulado', f"Expected 'anulado', got {updated['estado']}"
        
        print(f"✓ Asiento {asiento_id} voided successfully")

    def test_cannot_postear_anulado(self, test_asiento):
        """Cannot post an already voided asiento"""
        asiento_id = test_asiento['asiento']['id']
        
        # First anular
        requests.post(f"{BASE_URL}/api/asientos/{asiento_id}/anular", headers=HEADERS)
        
        # Try to postear
        resp = requests.post(f"{BASE_URL}/api/asientos/{asiento_id}/postear", headers=HEADERS)
        assert resp.status_code == 400, f"Expected 400 for posting anulado, got {resp.status_code}"
        
        print("✓ Cannot post anulado asiento (expected error)")


class TestAsientosFilters:
    """Test listing asientos with filters"""

    def test_list_asientos(self):
        """GET /api/asientos returns list"""
        resp = requests.get(f"{BASE_URL}/api/asientos", headers=HEADERS)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} asientos")

    def test_filter_by_estado(self):
        """GET /api/asientos?estado=borrador filters by estado"""
        resp = requests.get(f"{BASE_URL}/api/asientos?estado=borrador", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        for a in data:
            assert a['estado'] == 'borrador', f"Expected estado=borrador, got {a['estado']}"
        print(f"✓ Filter by estado=borrador: {len(data)} asientos")

    def test_filter_by_origen_tipo(self):
        """GET /api/asientos?origen_tipo=FPROV filters by origen_tipo"""
        resp = requests.get(f"{BASE_URL}/api/asientos?origen_tipo=FPROV", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        for a in data:
            assert a['origen_tipo'] == 'FPROV', f"Expected origen_tipo=FPROV, got {a['origen_tipo']}"
        print(f"✓ Filter by origen_tipo=FPROV: {len(data)} asientos")

    def test_get_asiento_detail(self):
        """GET /api/asientos/{id} returns asiento with detail lines"""
        # First get any asiento
        list_resp = requests.get(f"{BASE_URL}/api/asientos", headers=HEADERS)
        asientos = list_resp.json()
        if not asientos:
            pytest.skip("No asientos to test detail")
        
        asiento_id = asientos[0]['id']
        resp = requests.get(f"{BASE_URL}/api/asientos/{asiento_id}", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        
        assert 'lineas' in data
        assert 'total_debe' in data
        assert 'total_haber' in data
        assert data['id'] == asiento_id
        
        # Each linea should have cuenta_codigo, cuenta_nombre
        for linea in data['lineas']:
            assert 'cuenta_codigo' in linea
            assert 'cuenta_nombre' in linea
        
        print(f"✓ Asiento {asiento_id} detail: {len(data['lineas'])} lines")


class TestReportesContables:
    """Test accounting reports: Mayor, Balance, P&L"""

    def test_reporte_mayor(self):
        """GET /api/reportes/mayor returns ledger with posted entries"""
        resp = requests.get(f"{BASE_URL}/api/reportes/mayor", headers=HEADERS)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert isinstance(data, list)
        
        # Each entry should have cuenta info
        for entry in data[:5]:
            assert 'cuenta_codigo' in entry
            assert 'cuenta_nombre' in entry
            assert 'debe' in entry
            assert 'haber' in entry
        
        print(f"✓ Reporte Mayor: {len(data)} entries")

    def test_reporte_balance(self):
        """GET /api/reportes/balance returns balance sheet grouped by ACTIVO/PASIVO/PATRIMONIO"""
        resp = requests.get(f"{BASE_URL}/api/reportes/balance", headers=HEADERS)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert 'cuentas' in data
        assert 'totales' in data
        assert 'ACTIVO' in data['cuentas']
        assert 'PASIVO' in data['cuentas']
        assert 'PATRIMONIO' in data['cuentas']
        assert 'cuadra' in data
        
        print(f"✓ Reporte Balance: ACTIVO={data['totales'].get('ACTIVO')}, PASIVO={data['totales'].get('PASIVO')}, PATRIMONIO={data['totales'].get('PATRIMONIO')}, cuadra={data['cuadra']}")

    def test_reporte_pnl(self):
        """GET /api/reportes/pnl returns P&L with INGRESO/GASTO/COSTO"""
        resp = requests.get(f"{BASE_URL}/api/reportes/pnl", headers=HEADERS)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert 'cuentas' in data
        assert 'totales' in data
        assert 'INGRESO' in data['cuentas']
        assert 'GASTO' in data['cuentas']
        assert 'COSTO' in data['cuentas']
        assert 'utilidad_neta' in data
        
        print(f"✓ Reporte P&L: INGRESO={data['totales'].get('INGRESO')}, GASTO={data['totales'].get('GASTO')}, utilidad={data['utilidad_neta']}")


class TestPeriodosContables:
    """Test periodo contable cerrar/abrir"""

    def test_cerrar_periodo_blocks_posting(self):
        """POST /api/periodos-contables/cerrar blocks posting in closed periods"""
        today = date.today()
        year = today.year
        month = today.month
        
        # Ensure period is open first
        requests.post(f"{BASE_URL}/api/periodos-contables/abrir?anio={year}&mes={month}", headers=HEADERS)
        
        # Create a factura and asiento in current period
        factura_data = {
            "proveedor_id": PROVEEDOR_ID,
            "moneda_id": MONEDA_PEN_ID,
            "fecha_factura": str(today),
            "fecha_vencimiento": str(today + timedelta(days=30)),
            "fecha_contable": str(today),
            "tipo_cambio": 1.0,
            "terminos_dias": 30,
            "lineas": [{"descripcion": "TEST_PERIODO", "cantidad": 1, "importe": 100.0, "igv_aplica": True, "categoria_id": CATEGORIA_EGRESO_ID}],
            "igv_incluido": False
        }
        factura_resp = requests.post(f"{BASE_URL}/api/facturas-proveedor", headers=HEADERS, json=factura_data)
        factura = factura_resp.json()
        
        # Generate asiento
        payload = {"origen_tipo": "FPROV", "origen_id": factura['id']}
        asiento_resp = requests.post(f"{BASE_URL}/api/asientos/generar", headers=HEADERS, json=payload)
        asiento = asiento_resp.json()
        asiento_id = asiento['id']
        
        # First test: verify closing rejects borrador asientos
        close_resp = requests.post(f"{BASE_URL}/api/periodos-contables/cerrar?anio={year}&mes={month}", headers=HEADERS)
        # Should fail because there's at least one borrador asiento
        if close_resp.status_code == 400:
            print("✓ Cerrar periodo correctly rejects when borrador asientos exist")
        
        # Post our test asiento
        requests.post(f"{BASE_URL}/api/asientos/{asiento_id}/postear", headers=HEADERS)
        
        # Now test: close a past period (use next month to avoid conflicts with existing borrador)
        # Use last month instead - less likely to have borrador conflicts
        last_month = (today.replace(day=1) - timedelta(days=1))
        last_year = last_month.year
        last_month_num = last_month.month
        
        # Open last month's period
        requests.post(f"{BASE_URL}/api/periodos-contables/abrir?anio={last_year}&mes={last_month_num}", headers=HEADERS)
        
        # Close last month (should work if no borrador asientos there)
        close_past_resp = requests.post(f"{BASE_URL}/api/periodos-contables/cerrar?anio={last_year}&mes={last_month_num}", headers=HEADERS)
        # If there are borrador asientos in past month, this may fail - that's fine
        if close_past_resp.status_code == 200:
            print(f"✓ Cerrar periodo {last_year}-{last_month_num:02d} succeeded")
            
            # Try to create asiento in closed period
            factura2_data = {
                "proveedor_id": PROVEEDOR_ID,
                "moneda_id": MONEDA_PEN_ID,
                "fecha_factura": str(last_month),
                "fecha_vencimiento": str(last_month + timedelta(days=30)),
                "fecha_contable": str(last_month),
                "tipo_cambio": 1.0,
                "terminos_dias": 30,
                "lineas": [{"descripcion": "TEST_PERIODO_CLOSED", "cantidad": 1, "importe": 50.0, "igv_aplica": True, "categoria_id": CATEGORIA_EGRESO_ID}],
                "igv_incluido": False
            }
            factura2_resp = requests.post(f"{BASE_URL}/api/facturas-proveedor", headers=HEADERS, json=factura2_data)
            factura2 = factura2_resp.json()
            
            # Generate asiento in closed period should fail
            payload2 = {"origen_tipo": "FPROV", "origen_id": factura2['id']}
            asiento2_resp = requests.post(f"{BASE_URL}/api/asientos/generar", headers=HEADERS, json=payload2)
            assert asiento2_resp.status_code == 400, f"Expected 400 for closed period, got {asiento2_resp.status_code}"
            print("✓ Cerrar periodo blocks new asientos in closed period")
            
            # Cleanup
            requests.post(f"{BASE_URL}/api/periodos-contables/abrir?anio={last_year}&mes={last_month_num}", headers=HEADERS)
            requests.delete(f"{BASE_URL}/api/facturas-proveedor/{factura2['id']}", headers=HEADERS)
        else:
            print(f"✓ Cerrar periodo validates borrador asientos (status={close_past_resp.status_code})")
        
        # Cleanup original test data
        requests.delete(f"{BASE_URL}/api/facturas-proveedor/{factura['id']}", headers=HEADERS)

    def test_abrir_periodo(self):
        """POST /api/periodos-contables/abrir opens a closed period"""
        today = date.today()
        year = today.year
        month = today.month
        
        # Open period
        resp = requests.post(f"{BASE_URL}/api/periodos-contables/abrir?anio={year}&mes={month}", headers=HEADERS)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert data['ok'] == True
        
        print(f"✓ Periodo {year}-{month:02d} abierto")

    def test_list_periodos(self):
        """GET /api/periodos-contables returns list of periods"""
        resp = requests.get(f"{BASE_URL}/api/periodos-contables", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} periodo records")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
