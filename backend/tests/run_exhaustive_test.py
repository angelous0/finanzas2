#!/usr/bin/env python3
"""
Finanzas 4.0 - Exhaustive Financial Test Script
Tests ALL modules sequentially as a real accountant would use the system.

Run: python /app/backend/tests/run_exhaustive_test.py
"""

import requests
import os
import sys
import json
from datetime import date, timedelta

# API Configuration
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://concilia-smart.preview.emergentagent.com')
BASE_URL = BASE_URL.rstrip('/')

# Reference IDs from catalog data
PROVEEDOR_ID = 1
MONEDA_PEN_ID = 1
CUENTA_BCP_ID = 1
CUENTA_CAJA_ID = 2
CUENTA_IBK_ID = 3
EMPLEADO_JUAN_ID = 9
EMPLEADO_MARIA_ID = 10
EMPLEADO_CARLOS_ID = 11
CATEGORIA_COMPRAS_ID = 3
CATEGORIA_SERVICIOS_ID = 4
CATEGORIA_PLANILLA_ID = 5
CATEGORIA_OTROS_GASTOS_ID = 8

# Test results
results = {
    "passed": [],
    "failed": [],
    "created_ids": {}
}


def test(name, func):
    """Run a test and record result"""
    try:
        func()
        results["passed"].append(name)
        print(f"✓ PASS: {name}")
        return True
    except Exception as e:
        results["failed"].append({"name": name, "error": str(e)})
        print(f"✗ FAIL: {name} - {e}")
        return False


def run_tests():
    """Run all tests sequentially"""
    
    print("\n" + "="*70)
    print("FINANZAS 4.0 - EXHAUSTIVE FINANCIAL TEST")
    print("="*70)
    
    # Verify API is healthy
    print("\n--- API Health Check ---")
    resp = requests.get(f"{BASE_URL}/api/health", timeout=30)
    if resp.status_code != 200:
        print(f"API not healthy: {resp.status_code}")
        return False
    print(f"API healthy: {resp.json()}")
    
    # =====================
    # FLOW 1 - ORDEN DE COMPRA
    # =====================
    print("\n" + "="*70)
    print("FLOW 1: ORDEN DE COMPRA (IGV INCLUDED)")
    print("="*70)
    
    def flow1_01():
        payload = {
            "fecha": str(date.today()),
            "proveedor_id": PROVEEDOR_ID,
            "moneda_id": MONEDA_PEN_ID,
            "igv_incluido": True,
            "notas": "Test Flow 1 - OC with IGV included",
            "lineas": [
                {"descripcion": "Item A", "cantidad": 1, "precio_unitario": 118.00, "igv_aplica": True},
                {"descripcion": "Item B", "cantidad": 2, "precio_unitario": 118.00, "igv_aplica": True},
                {"descripcion": "Item C", "cantidad": 1, "precio_unitario": 118.00, "igv_aplica": True},
            ]
        }
        resp = requests.post(f"{BASE_URL}/api/ordenes-compra", json=payload, timeout=30)
        assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
        data = resp.json()
        results["created_ids"]["oc_flow1"] = data['id']
        assert abs(data['subtotal'] - 400.0) < 0.01, f"subtotal={data['subtotal']}, expected=400"
        assert abs(data['igv'] - 72.0) < 0.01, f"igv={data['igv']}, expected=72"
        assert abs(data['total'] - 472.0) < 0.01, f"total={data['total']}, expected=472"
        print(f"  OC created: {data['numero']}, subtotal={data['subtotal']}, igv={data['igv']}, total={data['total']}")
    
    test("Flow1.1: Create OC with IGV included", flow1_01)
    
    def flow1_02():
        oc_id = results["created_ids"]["oc_flow1"]
        resp = requests.post(f"{BASE_URL}/api/ordenes-compra/{oc_id}/generar-factura", timeout=30)
        assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
        data = resp.json()
        results["created_ids"]["factura_flow1"] = data['id']
        assert data['estado'] == 'pendiente'
        assert data['saldo_pendiente'] == data['total']
        print(f"  Factura created: {data['numero']}, total={data['total']}, estado={data['estado']}")
    
    test("Flow1.2: Convert OC to Factura", flow1_02)
    
    def flow1_03():
        factura_id = results["created_ids"]["factura_flow1"]
        resp = requests.get(f"{BASE_URL}/api/cxp", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        cxp = [c for c in data if c.get('factura_id') == factura_id]
        assert len(cxp) > 0, "CxP not created"
        assert cxp[0]['estado'] == 'pendiente'
        print(f"  CxP verified: monto={cxp[0]['monto_original']}, estado={cxp[0]['estado']}")
    
    test("Flow1.3: Verify CxP created", flow1_03)
    
    # =====================
    # FLOW 2 - PAGO PARCIAL
    # =====================
    print("\n" + "="*70)
    print("FLOW 2: PAGO PARCIAL FACTURA")
    print("="*70)
    
    def flow2_01():
        factura_id = results["created_ids"]["factura_flow1"]
        monto_50 = 236.0
        payload = {
            "tipo": "egreso",
            "fecha": str(date.today()),
            "cuenta_financiera_id": CUENTA_BCP_ID,
            "moneda_id": MONEDA_PEN_ID,
            "monto_total": monto_50,
            "referencia": "Pago parcial 50%",
            "detalles": [{"cuenta_financiera_id": CUENTA_BCP_ID, "medio_pago": "transferencia", "monto": monto_50}],
            "aplicaciones": [{"tipo_documento": "factura", "documento_id": factura_id, "monto_aplicado": monto_50}]
        }
        resp = requests.post(f"{BASE_URL}/api/pagos", json=payload, timeout=30)
        assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
        data = resp.json()
        print(f"  Pago 1: {data['numero']}, monto={data['monto_total']}")
    
    test("Flow2.1: Pay 50%", flow2_01)
    
    def flow2_02():
        factura_id = results["created_ids"]["factura_flow1"]
        resp = requests.get(f"{BASE_URL}/api/facturas-proveedor/{factura_id}", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert abs(data['saldo_pendiente'] - 236.0) < 0.01, f"saldo={data['saldo_pendiente']}, expected=236"
        assert data['estado'] == 'parcial', f"estado={data['estado']}, expected=parcial"
        print(f"  Factura after 50%: saldo={data['saldo_pendiente']}, estado={data['estado']}")
    
    test("Flow2.2: Verify partial state", flow2_02)
    
    def flow2_03():
        factura_id = results["created_ids"]["factura_flow1"]
        monto_50 = 236.0
        payload = {
            "tipo": "egreso",
            "fecha": str(date.today()),
            "cuenta_financiera_id": CUENTA_BCP_ID,
            "moneda_id": MONEDA_PEN_ID,
            "monto_total": monto_50,
            "referencia": "Pago final 50%",
            "detalles": [{"cuenta_financiera_id": CUENTA_BCP_ID, "medio_pago": "transferencia", "monto": monto_50}],
            "aplicaciones": [{"tipo_documento": "factura", "documento_id": factura_id, "monto_aplicado": monto_50}]
        }
        resp = requests.post(f"{BASE_URL}/api/pagos", json=payload, timeout=30)
        assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
        print(f"  Pago 2: completed")
    
    test("Flow2.3: Pay remaining 50%", flow2_03)
    
    def flow2_04():
        factura_id = results["created_ids"]["factura_flow1"]
        resp = requests.get(f"{BASE_URL}/api/facturas-proveedor/{factura_id}", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert abs(data['saldo_pendiente']) < 0.01, f"saldo={data['saldo_pendiente']}, expected=0"
        assert data['estado'] == 'pagado', f"estado={data['estado']}, expected=pagado"
        print(f"  Factura fully paid: saldo={data['saldo_pendiente']}, estado={data['estado']}")
    
    test("Flow2.4: Verify fully paid", flow2_04)
    
    # =====================
    # FLOW 3 - FACTURA CON LETRAS
    # =====================
    print("\n" + "="*70)
    print("FLOW 3: FACTURA CON LETRAS")
    print("="*70)
    
    def flow3_01():
        payload = {
            "proveedor_id": PROVEEDOR_ID,
            "moneda_id": MONEDA_PEN_ID,
            "fecha_factura": str(date.today()),
            "terminos_dias": 90,
            "tipo_documento": "factura",
            "impuestos_incluidos": False,
            "notas": "Test Flow 3 - Factura con Letras",
            "lineas": [
                {"descripcion": "Servicio A", "importe": 1000.00, "igv_aplica": True, "categoria_id": CATEGORIA_SERVICIOS_ID},
                {"descripcion": "Servicio B", "importe": 1000.00, "igv_aplica": True, "categoria_id": CATEGORIA_SERVICIOS_ID},
                {"descripcion": "Servicio C", "importe": 1000.00, "igv_aplica": True, "categoria_id": CATEGORIA_SERVICIOS_ID},
            ]
        }
        resp = requests.post(f"{BASE_URL}/api/facturas-proveedor", json=payload, timeout=30)
        assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
        data = resp.json()
        results["created_ids"]["factura_flow3"] = data['id']
        assert abs(data['subtotal'] - 3000.0) < 0.01
        assert abs(data['igv'] - 540.0) < 0.01
        assert abs(data['total'] - 3540.0) < 0.01
        print(f"  Factura: {data['numero']}, subtotal={data['subtotal']}, igv={data['igv']}, total={data['total']}")
    
    test("Flow3.1: Create factura directly", flow3_01)
    
    def flow3_02():
        factura_id = results["created_ids"]["factura_flow3"]
        payload = {
            "factura_id": factura_id,
            "cantidad_letras": 3,
            "dias_entre_letras": 30
        }
        resp = requests.post(f"{BASE_URL}/api/letras/generar", json=payload, timeout=30)
        assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
        data = resp.json()
        # Response is a List[Letra], not a dict
        letras = data if isinstance(data, list) else data.get('letras', [])
        assert len(letras) == 3, f"Expected 3 letras, got {len(letras)}"
        results["created_ids"]["letras_flow3"] = [l['id'] for l in letras]
        for letra in letras:
            assert abs(letra['monto'] - 1180.0) < 0.01
        print(f"  3 Letras: {[l['numero'] for l in letras]}, monto=1180 each")
    
    test("Flow3.2: Generate 3 letras", flow3_02)
    
    def flow3_03():
        factura_id = results["created_ids"]["factura_flow3"]
        resp = requests.get(f"{BASE_URL}/api/facturas-proveedor/{factura_id}", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert data['estado'] == 'canjeado', f"estado={data['estado']}, expected=canjeado"
        print(f"  Factura estado={data['estado']} after letras")
    
    test("Flow3.3: Verify factura canjeado", flow3_03)
    
    def flow3_04():
        letra_id = results["created_ids"]["letras_flow3"][0]
        monto = 1180.0
        payload = {
            "tipo": "egreso",
            "fecha": str(date.today()),
            "cuenta_financiera_id": CUENTA_BCP_ID,
            "moneda_id": MONEDA_PEN_ID,
            "monto_total": monto,
            "referencia": "Pago Letra 1",
            "detalles": [{"cuenta_financiera_id": CUENTA_BCP_ID, "medio_pago": "transferencia", "monto": monto}],
            "aplicaciones": [{"tipo_documento": "letra", "documento_id": letra_id, "monto_aplicado": monto}]
        }
        resp = requests.post(f"{BASE_URL}/api/pagos", json=payload, timeout=30)
        assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
        print(f"  Letra 1 paid")
    
    test("Flow3.4: Pay first letra", flow3_04)
    
    def flow3_05():
        resp = requests.get(f"{BASE_URL}/api/letras", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        letras_ids = results["created_ids"]["letras_flow3"]
        paid = [l for l in data if l['id'] == letras_ids[0]]
        pending = [l for l in data if l['id'] in letras_ids[1:]]
        assert len(paid) > 0 and paid[0]['estado'] == 'pagado'
        assert all(l['estado'] in ['pendiente', 'parcial'] for l in pending)
        print(f"  Letra 1 pagado, 2 letras pendiente")
    
    test("Flow3.5: Verify letra states", flow3_05)
    
    # =====================
    # FLOW 4 - GASTOS
    # =====================
    print("\n" + "="*70)
    print("FLOW 4: GASTOS")
    print("="*70)
    
    def flow4_01():
        payload = {
            "fecha": str(date.today()),
            "proveedor_id": None,
            "beneficiario_nombre": "Librería Central",
            "moneda_id": MONEDA_PEN_ID,
            "tipo_documento": "boleta",
            "numero_documento": "B001-0001",
            "lineas": [{"descripcion": "Útiles", "importe": 423.73, "igv_aplica": True, "categoria_id": CATEGORIA_OTROS_GASTOS_ID}],
            "pagos": [{"cuenta_financiera_id": CUENTA_CAJA_ID, "medio_pago": "efectivo", "monto": 500.0}]
        }
        resp = requests.post(f"{BASE_URL}/api/gastos", json=payload, timeout=30)
        assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
        data = resp.json()
        assert abs(data['total'] - 500.0) < 1
        assert data['pago_id'] is not None
        print(f"  Gasto 1: {data['numero']}, total={data['total']}, pago_id={data['pago_id']}")
    
    test("Flow4.1: Create gasto cash", flow4_01)
    
    def flow4_02():
        payload = {
            "fecha": str(date.today()),
            "proveedor_id": PROVEEDOR_ID,
            "moneda_id": MONEDA_PEN_ID,
            "tipo_documento": "factura",
            "numero_documento": "F001-0042",
            "lineas": [{"descripcion": "Servicios", "importe": 1016.95, "igv_aplica": True, "categoria_id": CATEGORIA_SERVICIOS_ID}],
            "pagos": [{"cuenta_financiera_id": CUENTA_BCP_ID, "medio_pago": "transferencia", "monto": 1200.0}]
        }
        resp = requests.post(f"{BASE_URL}/api/gastos", json=payload, timeout=30)
        assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
        data = resp.json()
        assert abs(data['total'] - 1200.0) < 1
        assert data['pago_id'] is not None
        print(f"  Gasto 2: {data['numero']}, total={data['total']}, pago_id={data['pago_id']}")
    
    test("Flow4.2: Create gasto transfer", flow4_02)
    
    # =====================
    # FLOW 5 - ADELANTOS
    # =====================
    print("\n" + "="*70)
    print("FLOW 5: ADELANTO EMPLEADO")
    print("="*70)
    
    def flow5_01():
        payload = {
            "empleado_id": EMPLEADO_JUAN_ID,
            "fecha": str(date.today()),
            "monto": 300.0,
            "motivo": "Adelanto quincena",
            "pagar": True,
            "cuenta_financiera_id": CUENTA_BCP_ID,
            "medio_pago": "transferencia"
        }
        resp = requests.post(f"{BASE_URL}/api/adelantos", json=payload, timeout=30)
        assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
        data = resp.json()
        results["created_ids"]["adelanto_juan"] = data['id']
        assert data['pagado'] == True
        assert data['pago_id'] is not None
        print(f"  Adelanto Juan: id={data['id']}, monto={data['monto']}, pagado={data['pagado']}")
    
    test("Flow5.1: Create adelanto Juan (paid)", flow5_01)
    
    def flow5_02():
        payload = {
            "empleado_id": EMPLEADO_MARIA_ID,
            "fecha": str(date.today()),
            "monto": 500.0,
            "motivo": "Emergencia",
            "pagar": False
        }
        resp = requests.post(f"{BASE_URL}/api/adelantos", json=payload, timeout=30)
        assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
        data = resp.json()
        results["created_ids"]["adelanto_maria"] = data['id']
        assert data['pagado'] == False
        print(f"  Adelanto María: id={data['id']}, monto={data['monto']}, pagado={data['pagado']}")
    
    test("Flow5.2: Create adelanto María (unpaid)", flow5_02)
    
    def flow5_03():
        adelanto_id = results["created_ids"]["adelanto_maria"]
        params = {"cuenta_financiera_id": CUENTA_CAJA_ID, "medio_pago": "efectivo"}
        resp = requests.post(f"{BASE_URL}/api/adelantos/{adelanto_id}/pagar", params=params, timeout=30)
        assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data['pagado'] == True
        assert data['pago_id'] is not None
        print(f"  Adelanto María paid: pagado={data['pagado']}, pago_id={data['pago_id']}")
    
    test("Flow5.3: Pay adelanto María", flow5_03)
    
    # =====================
    # FLOW 6 - PLANILLA
    # =====================
    print("\n" + "="*70)
    print("FLOW 6: PLANILLA")
    print("="*70)
    
    def flow6_01():
        payload = {
            "periodo": "2026-01",
            "fecha_inicio": str(date(2026, 1, 1)),
            "fecha_fin": str(date(2026, 1, 31)),
            "notas": "Planilla enero 2026",
            "detalles": [
                {"empleado_id": EMPLEADO_JUAN_ID, "salario_base": 2000.0, "bonificaciones": 0, "adelantos": 300.0, "otros_descuentos": 0},
                {"empleado_id": EMPLEADO_MARIA_ID, "salario_base": 2500.0, "bonificaciones": 0, "adelantos": 0, "otros_descuentos": 0},
                {"empleado_id": EMPLEADO_CARLOS_ID, "salario_base": 1500.0, "bonificaciones": 0, "adelantos": 0, "otros_descuentos": 0}
            ]
        }
        resp = requests.post(f"{BASE_URL}/api/planillas", json=payload, timeout=30)
        assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
        data = resp.json()
        results["created_ids"]["planilla"] = data['id']
        assert abs(data['total_bruto'] - 6000.0) < 0.01
        assert abs(data['total_adelantos'] - 300.0) < 0.01
        assert abs(data['total_neto'] - 5700.0) < 0.01
        print(f"  Planilla: periodo={data['periodo']}, bruto={data['total_bruto']}, neto={data['total_neto']}")
    
    test("Flow6.1: Create planilla", flow6_01)
    
    def flow6_02():
        planilla_id = results["created_ids"]["planilla"]
        params = {"cuenta_financiera_id": CUENTA_BCP_ID}
        resp = requests.post(f"{BASE_URL}/api/planillas/{planilla_id}/pagar", params=params, timeout=30)
        assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data['estado'] == 'pagada'
        assert data['pago_id'] is not None
        print(f"  Planilla paid: estado={data['estado']}, pago_id={data['pago_id']}")
    
    test("Flow6.2: Pay planilla", flow6_02)
    
    # =====================
    # FLOW 7 - VENTAS POS (OPTIONAL)
    # =====================
    print("\n" + "="*70)
    print("FLOW 7: VENTAS POS (Odoo sync - optional)")
    print("="*70)
    
    def flow7_01():
        try:
            resp = requests.post(f"{BASE_URL}/api/ventas-pos/sync?company=ambission&days_back=7", timeout=60)
            if resp.status_code == 200:
                print(f"  Odoo sync: {resp.json().get('message', 'completed')}")
            else:
                print(f"  Odoo sync failed (server may be down): {resp.status_code}")
        except Exception as e:
            print(f"  Odoo sync skipped: {e}")
    
    test("Flow7.1: Sync Odoo (optional)", flow7_01)
    
    # =====================
    # FLOW 8 - CXP VERIFICATION
    # =====================
    print("\n" + "="*70)
    print("FLOW 8: CXP VERIFICATION")
    print("="*70)
    
    def flow8_01():
        resp = requests.get(f"{BASE_URL}/api/cxp", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        estados = {}
        for cxp in data:
            e = cxp.get('estado', 'unknown')
            estados[e] = estados.get(e, 0) + 1
        print(f"  CxP by estado: {estados}")
        
        # Verify Flow 1 factura is pagado
        factura_id = results["created_ids"].get("factura_flow1")
        if factura_id:
            cxp1 = [c for c in data if c.get('factura_id') == factura_id]
            if cxp1:
                assert cxp1[0]['estado'] == 'pagado', f"Flow1 CxP should be pagado"
                print(f"  Flow1 CxP verified: pagado")
    
    test("Flow8.1: Verify CxP states", flow8_01)
    
    # =====================
    # FLOW 9 - DASHBOARD KPIs
    # =====================
    print("\n" + "="*70)
    print("FLOW 9: DASHBOARD KPIs")
    print("="*70)
    
    def flow9_01():
        resp = requests.get(f"{BASE_URL}/api/dashboard/kpis", timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        print(f"  KPIs: CxP={data['total_cxp']}, Letras={data['total_letras_pendientes']}, Saldo={data['saldo_bancos']}")
    
    test("Flow9.1: Get dashboard KPIs", flow9_01)
    
    # =====================
    # FLOW 10 - OC IGV EXCLUDED
    # =====================
    print("\n" + "="*70)
    print("FLOW 10: OC IGV EXCLUDED")
    print("="*70)
    
    def flow10_01():
        payload = {
            "fecha": str(date.today()),
            "proveedor_id": PROVEEDOR_ID,
            "moneda_id": MONEDA_PEN_ID,
            "igv_incluido": False,
            "notas": "Test Flow 10 - OC IGV excluded",
            "lineas": [
                {"descripcion": "Item X", "cantidad": 1, "precio_unitario": 100.00, "igv_aplica": True},
                {"descripcion": "Item Y", "cantidad": 1, "precio_unitario": 100.00, "igv_aplica": True},
            ]
        }
        resp = requests.post(f"{BASE_URL}/api/ordenes-compra", json=payload, timeout=30)
        assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text}"
        data = resp.json()
        results["created_ids"]["oc_flow10"] = data['id']
        assert abs(data['subtotal'] - 200.0) < 0.01, f"subtotal={data['subtotal']}, expected=200"
        assert abs(data['igv'] - 36.0) < 0.01, f"igv={data['igv']}, expected=36"
        assert abs(data['total'] - 236.0) < 0.01, f"total={data['total']}, expected=236"
        print(f"  OC: {data['numero']}, subtotal={data['subtotal']}, igv={data['igv']}, total={data['total']}")
    
    test("Flow10.1: Create OC IGV excluded", flow10_01)
    
    # =====================
    # SUMMARY
    # =====================
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    total = len(results["passed"]) + len(results["failed"])
    print(f"\nTotal tests: {total}")
    print(f"Passed: {len(results['passed'])}")
    print(f"Failed: {len(results['failed'])}")
    
    if results["failed"]:
        print("\nFailed tests:")
        for f in results["failed"]:
            print(f"  - {f['name']}: {f['error']}")
    
    print(f"\nCreated IDs: {json.dumps(results['created_ids'], indent=2)}")
    
    return len(results["failed"]) == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
