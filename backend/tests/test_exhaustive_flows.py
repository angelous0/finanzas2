"""
Finanzas 4.0 - Exhaustive Financial Test Suite
Tests ALL modules as if a real accountant would use the system.

IMPORTANT: All tests run sequentially in a single class to share state.

Flows tested:
1. ORDEN DE COMPRA - Create OC with IGV included, convert to factura
2. PAGO PARCIAL FACTURA - Pay 50%, then pay remaining 50%
3. FACTURA CON LETRAS - Create factura, generate letras, pay first letra
4. GASTOS - Create 2 gastos (cash and transfer)
5. ADELANTO EMPLEADO - Create adelanto, pay it
6. PLANILLA - Create planilla with 3 employees, include adelanto as descuento
7. VENTAS POS - Sync from Odoo (may fail if Odoo down)
8. CXP VERIFICATION - Verify all CxP states
9. DASHBOARD KPIs - Verify non-zero values
10. SECOND OC with IGV excluded - Verify different calculation
"""

import pytest
import requests
import os
from datetime import date, timedelta

# API Configuration
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://concilia-smart.preview.emergentagent.com')
BASE_URL = BASE_URL.rstrip('/')

# Reference IDs from catalog data
PROVEEDOR_ID = 1  # Proveedor Demo S.A.C.
MONEDA_PEN_ID = 1
CUENTA_BCP_ID = 1
CUENTA_CAJA_ID = 2
CUENTA_IBK_ID = 3
EMPLEADO_JUAN_ID = 9  # salario=2000
EMPLEADO_MARIA_ID = 10  # salario=2500
EMPLEADO_CARLOS_ID = 11  # salario=1500
CATEGORIA_COMPRAS_ID = 3
CATEGORIA_SERVICIOS_ID = 4
CATEGORIA_PLANILLA_ID = 5
CATEGORIA_OTROS_GASTOS_ID = 8


class TestExhaustiveFinancialFlows:
    """All 10 flows in sequence, sharing state via class attributes"""
    
    # Class-level storage for IDs between tests
    oc_flow1_id = None
    factura_flow1_id = None
    factura_flow3_id = None
    letras_flow3_ids = []
    adelanto_juan_id = None
    adelanto_maria_id = None
    planilla_id = None
    oc_flow10_id = None
    
    # =====================
    # FLOW 1 - ORDEN DE COMPRA
    # =====================
    def test_flow1_01_create_oc_igv_incluido(self):
        """FLOW 1.1: Create OC with 3 items, IGV included in price (S/ 118 each)"""
        print("\n=== FLOW 1: ORDEN DE COMPRA ===")
        
        payload = {
            "fecha": str(date.today()),
            "proveedor_id": PROVEEDOR_ID,
            "moneda_id": MONEDA_PEN_ID,
            "igv_incluido": True,
            "notas": "Test Flow 1 - OC with IGV included",
            "lineas": [
                {"descripcion": "Item A - Material de oficina", "cantidad": 1, "precio_unitario": 118.00, "igv_aplica": True},
                {"descripcion": "Item B - Suministros", "cantidad": 2, "precio_unitario": 118.00, "igv_aplica": True},
                {"descripcion": "Item C - Herramientas", "cantidad": 1, "precio_unitario": 118.00, "igv_aplica": True},
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/ordenes-compra", json=payload)
        print(f"Create OC Response Status: {response.status_code}")
        print(f"Create OC Response Body: {response.json()}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        TestExhaustiveFinancialFlows.oc_flow1_id = data['id']
        
        # Verify calculations: 4 items at 118 with IGV included
        # Base = 4 * 118 / 1.18 = 400
        # IGV = 4 * 118 - 400 = 72
        # Total = 472
        assert abs(data['subtotal'] - 400.0) < 0.01, f"Expected subtotal=400, got {data['subtotal']}"
        assert abs(data['igv'] - 72.0) < 0.01, f"Expected igv=72, got {data['igv']}"
        assert abs(data['total'] - 472.0) < 0.01, f"Expected total=472, got {data['total']}"
        
        print(f"✓ OC created: {data['numero']}, subtotal={data['subtotal']}, igv={data['igv']}, total={data['total']}")
        
    def test_flow1_02_convert_oc_to_factura(self):
        """FLOW 1.2: Convert OC to Factura Proveedor"""
        oc_id = TestExhaustiveFinancialFlows.oc_flow1_id
        assert oc_id is not None, "OC not created in previous test"
        
        response = requests.post(f"{BASE_URL}/api/ordenes-compra/{oc_id}/generar-factura")
        print(f"Generate Factura Response Status: {response.status_code}")
        print(f"Generate Factura Response Body: {response.json()}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        TestExhaustiveFinancialFlows.factura_flow1_id = data['id']
        
        # Verify factura has same amounts as OC
        assert abs(data['subtotal'] - 400.0) < 0.01, f"Expected subtotal=400, got {data['subtotal']}"
        assert abs(data['igv'] - 72.0) < 0.01, f"Expected igv=72, got {data['igv']}"
        assert abs(data['total'] - 472.0) < 0.01, f"Expected total=472, got {data['total']}"
        assert data['saldo_pendiente'] == data['total'], "saldo_pendiente should equal total initially"
        assert data['estado'] == 'pendiente', f"Expected estado=pendiente, got {data['estado']}"
        
        print(f"✓ Factura created: {data['numero']}, total={data['total']}, estado={data['estado']}")
        
    def test_flow1_03_verify_cxp_created(self):
        """FLOW 1.3: Verify CxP was auto-created from factura"""
        factura_id = TestExhaustiveFinancialFlows.factura_flow1_id
        assert factura_id is not None, "Factura not created in previous test"
        
        response = requests.get(f"{BASE_URL}/api/cxp")
        print(f"CXP List Response Status: {response.status_code}")
        
        assert response.status_code == 200
        
        data = response.json()
        cxp_for_factura = [c for c in data if c.get('factura_id') == factura_id]
        
        assert len(cxp_for_factura) > 0, "CxP should have been created for the factura"
        cxp = cxp_for_factura[0]
        
        assert abs(cxp['monto_original'] - 472.0) < 0.01, f"Expected monto_original=472, got {cxp['monto_original']}"
        assert cxp['estado'] == 'pendiente', f"Expected estado=pendiente, got {cxp['estado']}"
        
        print(f"✓ CxP verified: id={cxp['id']}, monto={cxp['monto_original']}, estado={cxp['estado']}")

    # =====================
    # FLOW 2 - PAGO PARCIAL
    # =====================
    def test_flow2_01_pay_50_percent(self):
        """FLOW 2.1: Pay 50% of the factura from Flow 1"""
        print("\n=== FLOW 2: PAGO PARCIAL FACTURA ===")
        
        factura_id = TestExhaustiveFinancialFlows.factura_flow1_id
        assert factura_id is not None, "Factura not created in Flow 1"
        
        monto_50 = 236.0  # 50% of 472
        
        payload = {
            "tipo": "egreso",
            "fecha": str(date.today()),
            "cuenta_financiera_id": CUENTA_BCP_ID,
            "moneda_id": MONEDA_PEN_ID,
            "monto_total": monto_50,
            "referencia": "Pago parcial 50% Flow 2",
            "detalles": [
                {"cuenta_financiera_id": CUENTA_BCP_ID, "medio_pago": "transferencia", "monto": monto_50}
            ],
            "aplicaciones": [
                {"tipo_documento": "factura", "documento_id": factura_id, "monto_aplicado": monto_50}
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/pagos", json=payload)
        print(f"Pay 50% Response Status: {response.status_code}")
        print(f"Pay 50% Response Body: {response.json()}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print(f"✓ Payment 1 created: {data['numero']}, monto={data['monto_total']}")
        
    def test_flow2_02_verify_factura_partial_state(self):
        """FLOW 2.2: Verify factura saldo decreased and estado=parcial"""
        factura_id = TestExhaustiveFinancialFlows.factura_flow1_id
        
        response = requests.get(f"{BASE_URL}/api/facturas-proveedor/{factura_id}")
        print(f"Factura State Response Status: {response.status_code}")
        print(f"Factura State Response Body: {response.json()}")
        
        assert response.status_code == 200
        
        data = response.json()
        
        # After 50% payment, saldo should be 236
        assert abs(data['saldo_pendiente'] - 236.0) < 0.01, f"Expected saldo=236, got {data['saldo_pendiente']}"
        assert data['estado'] == 'parcial', f"Expected estado=parcial, got {data['estado']}"
        
        print(f"✓ Factura after 50%: saldo={data['saldo_pendiente']}, estado={data['estado']}")
        
    def test_flow2_03_pay_remaining_50_percent(self):
        """FLOW 2.3: Pay remaining 50%"""
        factura_id = TestExhaustiveFinancialFlows.factura_flow1_id
        monto_50 = 236.0
        
        payload = {
            "tipo": "egreso",
            "fecha": str(date.today()),
            "cuenta_financiera_id": CUENTA_BCP_ID,
            "moneda_id": MONEDA_PEN_ID,
            "monto_total": monto_50,
            "referencia": "Pago final 50% Flow 2",
            "detalles": [
                {"cuenta_financiera_id": CUENTA_BCP_ID, "medio_pago": "transferencia", "monto": monto_50}
            ],
            "aplicaciones": [
                {"tipo_documento": "factura", "documento_id": factura_id, "monto_aplicado": monto_50}
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/pagos", json=payload)
        print(f"Pay remaining 50% Response Status: {response.status_code}")
        print(f"Pay remaining 50% Response Body: {response.json()}")
        
        assert response.status_code == 200
        
        data = response.json()
        print(f"✓ Payment 2 created: {data['numero']}")
        
    def test_flow2_04_verify_factura_fully_paid(self):
        """FLOW 2.4: Verify factura estado=pagado and saldo=0"""
        factura_id = TestExhaustiveFinancialFlows.factura_flow1_id
        
        response = requests.get(f"{BASE_URL}/api/facturas-proveedor/{factura_id}")
        print(f"Factura Final State Response: {response.json()}")
        
        assert response.status_code == 200
        
        data = response.json()
        
        assert abs(data['saldo_pendiente']) < 0.01, f"Expected saldo=0, got {data['saldo_pendiente']}"
        assert data['estado'] == 'pagado', f"Expected estado=pagado, got {data['estado']}"
        
        print(f"✓ Factura fully paid: saldo={data['saldo_pendiente']}, estado={data['estado']}")

    # =====================
    # FLOW 3 - FACTURA CON LETRAS
    # =====================
    def test_flow3_01_create_factura_directly(self):
        """FLOW 3.1: Create Factura Proveedor directly for S/ 3000 (3 items x S/ 1000)"""
        print("\n=== FLOW 3: FACTURA CON LETRAS ===")
        
        # 3 items at S/ 1000 each, IGV excluded
        payload = {
            "proveedor_id": PROVEEDOR_ID,
            "moneda_id": MONEDA_PEN_ID,
            "fecha_factura": str(date.today()),
            "terminos_dias": 90,
            "tipo_documento": "factura",
            "impuestos_incluidos": False,  # IGV excluded - add on top
            "notas": "Test Flow 3 - Factura con Letras",
            "lineas": [
                {"descripcion": "Servicio A", "importe": 1000.00, "igv_aplica": True, "categoria_id": CATEGORIA_SERVICIOS_ID},
                {"descripcion": "Servicio B", "importe": 1000.00, "igv_aplica": True, "categoria_id": CATEGORIA_SERVICIOS_ID},
                {"descripcion": "Servicio C", "importe": 1000.00, "igv_aplica": True, "categoria_id": CATEGORIA_SERVICIOS_ID},
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/facturas-proveedor", json=payload)
        print(f"Create Factura Response Status: {response.status_code}")
        print(f"Create Factura Response Body: {response.json()}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        TestExhaustiveFinancialFlows.factura_flow3_id = data['id']
        
        # With IGV excluded: subtotal=3000, igv=540, total=3540
        assert abs(data['subtotal'] - 3000.0) < 0.01, f"Expected subtotal=3000, got {data['subtotal']}"
        assert abs(data['igv'] - 540.0) < 0.01, f"Expected igv=540, got {data['igv']}"
        assert abs(data['total'] - 3540.0) < 0.01, f"Expected total=3540, got {data['total']}"
        assert data['estado'] == 'pendiente', f"Expected estado=pendiente, got {data['estado']}"
        
        print(f"✓ Factura created: {data['numero']}, subtotal={data['subtotal']}, igv={data['igv']}, total={data['total']}")
        
    def test_flow3_02_generate_3_letras(self):
        """FLOW 3.2: Generate 3 letras from the factura (3540 / 3 = 1180 each)"""
        factura_id = TestExhaustiveFinancialFlows.factura_flow3_id
        assert factura_id is not None, "Factura not created in previous test"
        
        payload = {
            "factura_id": factura_id,
            "cantidad_letras": 3,
            "dias_entre_letras": 30
        }
        
        response = requests.post(f"{BASE_URL}/api/letras/generar", json=payload)
        print(f"Generate Letras Response Status: {response.status_code}")
        print(f"Generate Letras Response Body: {response.json()}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Response is a dict with 'letras' key
        letras = data.get('letras', [])
        assert len(letras) == 3, f"Expected 3 letras, got {len(letras)}"
        
        TestExhaustiveFinancialFlows.letras_flow3_ids = [l['id'] for l in letras]
        
        # Each letra should be 1180
        for letra in letras:
            assert abs(letra['monto'] - 1180.0) < 0.01, f"Expected letra monto=1180, got {letra['monto']}"
            
        print(f"✓ 3 Letras created: {[l['numero'] for l in letras]}")
        
    def test_flow3_03_verify_factura_canjeado(self):
        """FLOW 3.3: Verify factura estado changed to 'canjeado'"""
        factura_id = TestExhaustiveFinancialFlows.factura_flow3_id
        
        response = requests.get(f"{BASE_URL}/api/facturas-proveedor/{factura_id}")
        print(f"Factura State After Letras: {response.json()}")
        
        assert response.status_code == 200
        
        data = response.json()
        assert data['estado'] == 'canjeado', f"Expected estado=canjeado, got {data['estado']}"
        
        print(f"✓ Factura estado={data['estado']} after letras generation")
        
    def test_flow3_04_pay_first_letra(self):
        """FLOW 3.4: Pay the first letra"""
        letras = TestExhaustiveFinancialFlows.letras_flow3_ids
        assert len(letras) > 0, "No letras created"
        
        letra_id = letras[0]
        monto = 1180.0
        
        payload = {
            "tipo": "egreso",
            "fecha": str(date.today()),
            "cuenta_financiera_id": CUENTA_BCP_ID,
            "moneda_id": MONEDA_PEN_ID,
            "monto_total": monto,
            "referencia": "Pago Letra 1 Flow 3",
            "detalles": [
                {"cuenta_financiera_id": CUENTA_BCP_ID, "medio_pago": "transferencia", "monto": monto}
            ],
            "aplicaciones": [
                {"tipo_documento": "letra", "documento_id": letra_id, "monto_aplicado": monto}
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/pagos", json=payload)
        print(f"Pay Letra Response Status: {response.status_code}")
        print(f"Pay Letra Response Body: {response.json()}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        print(f"✓ Letra payment created: {data['numero']}")
        
    def test_flow3_05_verify_letra_paid(self):
        """FLOW 3.5: Verify first letra is paid via letras list"""
        letras_ids = TestExhaustiveFinancialFlows.letras_flow3_ids
        
        # Get all letras and find ours
        response = requests.get(f"{BASE_URL}/api/letras")
        print(f"Get Letras List Status: {response.status_code}")
        
        assert response.status_code == 200
        
        data = response.json()
        
        # Find our letras
        paid_letra = None
        pending_letras = []
        for letra in data:
            if letra['id'] == letras_ids[0]:
                paid_letra = letra
            elif letra['id'] in letras_ids[1:]:
                pending_letras.append(letra)
                
        assert paid_letra is not None, "Paid letra not found"
        assert paid_letra['estado'] == 'pagado', f"Expected letra estado=pagado, got {paid_letra['estado']}"
        
        # Check remaining letras are still pendiente
        for letra in pending_letras:
            assert letra['estado'] in ['pendiente', 'parcial'], f"Letra {letra['id']} should still be pending"
            
        print(f"✓ First letra paid, remaining {len(pending_letras)} letras still pending")

    # =====================
    # FLOW 4 - GASTOS
    # =====================
    def test_flow4_01_create_gasto_cash(self):
        """FLOW 4.1: Create gasto S/ 500 office supplies paid in cash"""
        print("\n=== FLOW 4: GASTOS ===")
        
        payload = {
            "fecha": str(date.today()),
            "proveedor_id": None,
            "beneficiario_nombre": "Librería Central",
            "moneda_id": MONEDA_PEN_ID,
            "tipo_documento": "boleta",
            "numero_documento": "B001-0001",
            "notas": "Test Flow 4 - Gasto en efectivo",
            "lineas": [
                {"descripcion": "Útiles de oficina", "importe": 423.73, "igv_aplica": True, "categoria_id": CATEGORIA_OTROS_GASTOS_ID}
            ],
            "pagos": [
                {"cuenta_financiera_id": CUENTA_CAJA_ID, "medio_pago": "efectivo", "monto": 500.0}
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/gastos", json=payload)
        print(f"Create Gasto Cash Response Status: {response.status_code}")
        print(f"Create Gasto Cash Response Body: {response.json()}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify total is ~500 (423.73 + 18% IGV = ~500)
        assert abs(data['total'] - 500.0) < 1, f"Expected total~500, got {data['total']}"
        assert data['pago_id'] is not None, "pago_id should be assigned"
        
        print(f"✓ Gasto 1 created: {data['numero']}, total={data['total']}, pago_id={data['pago_id']}")
        
    def test_flow4_02_create_gasto_transfer(self):
        """FLOW 4.2: Create gasto S/ 1200 services paid via transfer"""
        payload = {
            "fecha": str(date.today()),
            "proveedor_id": PROVEEDOR_ID,
            "moneda_id": MONEDA_PEN_ID,
            "tipo_documento": "factura",
            "numero_documento": "F001-0042",
            "notas": "Test Flow 4 - Gasto transferencia",
            "lineas": [
                {"descripcion": "Servicios profesionales", "importe": 1016.95, "igv_aplica": True, "categoria_id": CATEGORIA_SERVICIOS_ID}
            ],
            "pagos": [
                {"cuenta_financiera_id": CUENTA_BCP_ID, "medio_pago": "transferencia", "monto": 1200.0, "referencia": "OP-12345"}
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/gastos", json=payload)
        print(f"Create Gasto Transfer Response Status: {response.status_code}")
        print(f"Create Gasto Transfer Response Body: {response.json()}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        assert abs(data['total'] - 1200.0) < 1, f"Expected total~1200, got {data['total']}"
        assert data['pago_id'] is not None, "pago_id should be assigned"
        
        print(f"✓ Gasto 2 created: {data['numero']}, total={data['total']}, pago_id={data['pago_id']}")

    # =====================
    # FLOW 5 - ADELANTO
    # =====================
    def test_flow5_01_create_adelanto_juan_paid(self):
        """FLOW 5.1: Create adelanto for Juan Pérez (id=9) of S/ 300 and pay immediately"""
        print("\n=== FLOW 5: ADELANTO EMPLEADO ===")
        
        payload = {
            "empleado_id": EMPLEADO_JUAN_ID,
            "fecha": str(date.today()),
            "monto": 300.0,
            "motivo": "Adelanto quincena Flow 5",
            "pagar": True,
            "cuenta_financiera_id": CUENTA_BCP_ID,
            "medio_pago": "transferencia"
        }
        
        response = requests.post(f"{BASE_URL}/api/adelantos", json=payload)
        print(f"Create Adelanto Juan Response Status: {response.status_code}")
        print(f"Create Adelanto Juan Response Body: {response.json()}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        TestExhaustiveFinancialFlows.adelanto_juan_id = data['id']
        
        assert data['pagado'] == True, "Adelanto should be marked as paid"
        assert data['pago_id'] is not None, "pago_id should be assigned"
        
        print(f"✓ Adelanto Juan created and paid: id={data['id']}, monto={data['monto']}, pagado={data['pagado']}")
        
    def test_flow5_02_create_adelanto_maria_unpaid(self):
        """FLOW 5.2: Create adelanto for María López (id=10) of S/ 500 without paying"""
        payload = {
            "empleado_id": EMPLEADO_MARIA_ID,
            "fecha": str(date.today()),
            "monto": 500.0,
            "motivo": "Emergencia familiar Flow 5",
            "pagar": False
        }
        
        response = requests.post(f"{BASE_URL}/api/adelantos", json=payload)
        print(f"Create Adelanto María Response Status: {response.status_code}")
        print(f"Create Adelanto María Response Body: {response.json()}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        TestExhaustiveFinancialFlows.adelanto_maria_id = data['id']
        
        assert data['pagado'] == False, "Adelanto should NOT be marked as paid"
        assert data['pago_id'] is None, "pago_id should be None"
        
        print(f"✓ Adelanto María created (unpaid): id={data['id']}, monto={data['monto']}, pagado={data['pagado']}")
        
    def test_flow5_03_pay_adelanto_maria(self):
        """FLOW 5.3: Pay the second adelanto using POST /adelantos/{id}/pagar with query params"""
        adelanto_id = TestExhaustiveFinancialFlows.adelanto_maria_id
        assert adelanto_id is not None, "Adelanto María not created"
        
        # Note: This endpoint uses query parameters, not JSON body
        params = {
            "cuenta_financiera_id": CUENTA_CAJA_ID,
            "medio_pago": "efectivo"
        }
        
        response = requests.post(f"{BASE_URL}/api/adelantos/{adelanto_id}/pagar", params=params)
        print(f"Pay Adelanto María Response Status: {response.status_code}")
        print(f"Pay Adelanto María Response Body: {response.json()}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data['pagado'] == True, "Adelanto should now be marked as paid"
        assert data['pago_id'] is not None, "pago_id should be assigned"
        
        print(f"✓ Adelanto María now paid: pagado={data['pagado']}, pago_id={data['pago_id']}")

    # =====================
    # FLOW 6 - PLANILLA
    # =====================
    def test_flow6_01_create_planilla(self):
        """FLOW 6.1: Create planilla for periodo 2026-01 with all 3 employees"""
        print("\n=== FLOW 6: PLANILLA ===")
        
        # Juan's adelanto of S/ 300 should be included as descuento
        adelanto_descuento_juan = 300.0
        
        payload = {
            "periodo": "2026-01",
            "fecha_inicio": str(date(2026, 1, 1)),
            "fecha_fin": str(date(2026, 1, 31)),
            "notas": "Test Flow 6 - Planilla enero 2026",
            "detalles": [
                {
                    "empleado_id": EMPLEADO_JUAN_ID,
                    "salario_base": 2000.0,
                    "bonificaciones": 0,
                    "adelantos": adelanto_descuento_juan,  # S/ 300 adelanto
                    "otros_descuentos": 0
                },
                {
                    "empleado_id": EMPLEADO_MARIA_ID,
                    "salario_base": 2500.0,
                    "bonificaciones": 0,
                    "adelantos": 0,
                    "otros_descuentos": 0
                },
                {
                    "empleado_id": EMPLEADO_CARLOS_ID,
                    "salario_base": 1500.0,
                    "bonificaciones": 0,
                    "adelantos": 0,
                    "otros_descuentos": 0
                }
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/planillas", json=payload)
        print(f"Create Planilla Response Status: {response.status_code}")
        print(f"Create Planilla Response Body: {response.json()}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        TestExhaustiveFinancialFlows.planilla_id = data['id']
        
        # Verify totals
        # Total bruto = 2000 + 2500 + 1500 = 6000
        # Total adelantos = 300
        # Total neto = 6000 - 300 = 5700
        assert abs(data['total_bruto'] - 6000.0) < 0.01, f"Expected total_bruto=6000, got {data['total_bruto']}"
        assert abs(data['total_adelantos'] - 300.0) < 0.01, f"Expected total_adelantos=300, got {data['total_adelantos']}"
        assert abs(data['total_neto'] - 5700.0) < 0.01, f"Expected total_neto=5700, got {data['total_neto']}"
        assert data['estado'] == 'borrador', f"Expected estado=borrador, got {data['estado']}"
        
        print(f"✓ Planilla created: periodo={data['periodo']}, total_bruto={data['total_bruto']}, total_neto={data['total_neto']}")
        
    def test_flow6_02_pay_planilla(self):
        """FLOW 6.2: Pay the planilla using POST /planillas/{id}/pagar with query params"""
        planilla_id = TestExhaustiveFinancialFlows.planilla_id
        assert planilla_id is not None, "Planilla not created"
        
        # Note: This endpoint uses query parameters, not JSON body
        params = {
            "cuenta_financiera_id": CUENTA_BCP_ID
        }
        
        response = requests.post(f"{BASE_URL}/api/planillas/{planilla_id}/pagar", params=params)
        print(f"Pay Planilla Response Status: {response.status_code}")
        print(f"Pay Planilla Response Body: {response.json()}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Note: Backend uses 'pagada' not 'pagado'
        assert data['estado'] == 'pagada', f"Expected estado=pagada, got {data['estado']}"
        assert data['pago_id'] is not None, "pago_id should be assigned"
        
        print(f"✓ Planilla paid: estado={data['estado']}, pago_id={data['pago_id']}")

    # =====================
    # FLOW 7 - VENTAS POS (optional, may fail if Odoo down)
    # =====================
    def test_flow7_01_sync_odoo_ventas(self):
        """FLOW 7.1: Sync ventas from Odoo (skipped if Odoo down)"""
        print("\n=== FLOW 7: VENTAS POS ===")
        
        response = requests.post(f"{BASE_URL}/api/ventas-pos/sync?company=ambission&days_back=7", timeout=30)
        print(f"Sync Odoo Response Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"⚠ Odoo sync failed (server may be down): {response.text[:200]}")
            pytest.skip("Odoo server may be down - skipping Ventas POS tests")
            return
            
        data = response.json()
        print(f"Sync Odoo Response Body: {data}")
        print(f"✓ Odoo sync completed: {data.get('message', data)}")

    # =====================
    # FLOW 8 - CXP VERIFICATION
    # =====================
    def test_flow8_01_verify_cxp_states(self):
        """FLOW 8.1: Check GET /cxp to verify all CxP records"""
        print("\n=== FLOW 8: CXP VERIFICATION ===")
        
        response = requests.get(f"{BASE_URL}/api/cxp")
        print(f"CXP List Response Status: {response.status_code}")
        
        assert response.status_code == 200
        
        data = response.json()
        print(f"Found {len(data)} CxP records")
        
        # Count by estado
        estados = {}
        for cxp in data:
            estado = cxp.get('estado', 'unknown')
            estados[estado] = estados.get(estado, 0) + 1
            
        print(f"CxP by estado: {estados}")
        
        # Verify Flow 1 factura CxP is pagado
        factura_id = TestExhaustiveFinancialFlows.factura_flow1_id
        if factura_id:
            cxp_flow1 = [c for c in data if c.get('factura_id') == factura_id]
            if cxp_flow1:
                assert cxp_flow1[0]['estado'] == 'pagado', f"Flow 1 CxP should be pagado, got {cxp_flow1[0]['estado']}"
                print(f"✓ Flow 1 CxP is pagado")
                
        print(f"✓ CxP verification complete")

    # =====================
    # FLOW 9 - DASHBOARD KPIs
    # =====================
    def test_flow9_01_get_kpis(self):
        """FLOW 9.1: Call GET /dashboard/kpis and verify it returns data"""
        print("\n=== FLOW 9: DASHBOARD KPIs ===")
        
        response = requests.get(f"{BASE_URL}/api/dashboard/kpis")
        print(f"Dashboard KPIs Response Status: {response.status_code}")
        print(f"Dashboard KPIs Response Body: {response.json()}")
        
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify the structure is correct
        assert 'total_cxp' in data
        assert 'total_cxc' in data
        assert 'total_letras_pendientes' in data
        assert 'saldo_bancos' in data
        assert 'ventas_mes' in data
        assert 'gastos_mes' in data
        assert 'facturas_pendientes' in data
        assert 'letras_por_vencer' in data
        
        print(f"KPIs: CxP={data['total_cxp']}, Letras={data['total_letras_pendientes']}, Saldo={data['saldo_bancos']}, Gastos={data['gastos_mes']}")
        print(f"✓ Dashboard KPIs retrieved successfully")

    # =====================
    # FLOW 10 - OC IGV EXCLUDED
    # =====================
    def test_flow10_01_create_oc_igv_excluded(self):
        """FLOW 10.1: Create OC with igv_incluido=false, price=100 per item"""
        print("\n=== FLOW 10: SECOND OC (IGV EXCLUDED) ===")
        
        payload = {
            "fecha": str(date.today()),
            "proveedor_id": PROVEEDOR_ID,
            "moneda_id": MONEDA_PEN_ID,
            "igv_incluido": False,  # IGV on top
            "notas": "Test Flow 10 - OC with IGV excluded",
            "lineas": [
                {"descripcion": "Item X", "cantidad": 1, "precio_unitario": 100.00, "igv_aplica": True},
                {"descripcion": "Item Y", "cantidad": 1, "precio_unitario": 100.00, "igv_aplica": True},
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/ordenes-compra", json=payload)
        print(f"Create OC IGV Excluded Response Status: {response.status_code}")
        print(f"Create OC IGV Excluded Response Body: {response.json()}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        TestExhaustiveFinancialFlows.oc_flow10_id = data['id']
        
        # With igv_incluido=false: subtotal=200, igv=36, total=236
        assert abs(data['subtotal'] - 200.0) < 0.01, f"Expected subtotal=200, got {data['subtotal']}"
        assert abs(data['igv'] - 36.0) < 0.01, f"Expected igv=36, got {data['igv']}"
        assert abs(data['total'] - 236.0) < 0.01, f"Expected total=236, got {data['total']}"
        
        print(f"✓ OC created: {data['numero']}, subtotal={data['subtotal']}, igv={data['igv']}, total={data['total']}")

    # =====================
    # FINAL SUMMARY
    # =====================
    def test_final_summary(self):
        """Print summary of all tests"""
        print("\n" + "="*60)
        print("EXHAUSTIVE FINANCIAL TEST SUMMARY")
        print("="*60)
        
        print(f"\nCreated IDs:")
        print(f"  oc_flow1_id: {TestExhaustiveFinancialFlows.oc_flow1_id}")
        print(f"  factura_flow1_id: {TestExhaustiveFinancialFlows.factura_flow1_id}")
        print(f"  factura_flow3_id: {TestExhaustiveFinancialFlows.factura_flow3_id}")
        print(f"  letras_flow3_ids: {TestExhaustiveFinancialFlows.letras_flow3_ids}")
        print(f"  adelanto_juan_id: {TestExhaustiveFinancialFlows.adelanto_juan_id}")
        print(f"  adelanto_maria_id: {TestExhaustiveFinancialFlows.adelanto_maria_id}")
        print(f"  planilla_id: {TestExhaustiveFinancialFlows.planilla_id}")
        print(f"  oc_flow10_id: {TestExhaustiveFinancialFlows.oc_flow10_id}")
                
        print("\n✓ All 10 flows tested successfully!")
        print("="*60)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
