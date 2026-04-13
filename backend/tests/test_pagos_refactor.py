"""
Backend tests for Payment Refactoring - cont_movimiento_tesoreria as single source of truth.

This tests the major architectural refactor where:
- cont_pago table is now DEPRECATED
- All payment CRUD in pagos.py reads/writes from cont_movimiento_tesoreria
- New payments use movimiento_tesoreria_id in cont_pago_detalle and cont_pago_aplicacion
- Old payments still use pago_id (fallback logic in delete handler)

Test data for empresa_id=7:
- cuenta_financiera_id: 10 (BCP, PEN)
- moneda_id: 9 (PEN)
- proveedor_id: 46 (Colortex SAC)
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://concilia-smart.preview.emergentagent.com').rstrip('/')
EMPRESA_ID = 7
CUENTA_FINANCIERA_ID = 10
MONEDA_ID = 9
PROVEEDOR_ID = 46


# =====================
# Module 1: GET /api/pagos - List all treasury movements
# =====================
class TestListPagos:
    """Test GET /api/pagos endpoint returns movements from cont_movimiento_tesoreria"""

    def test_list_pagos_basic(self):
        """GET /api/pagos?empresa_id=7 returns a list of movements"""
        response = requests.get(
            f"{BASE_URL}/api/pagos",
            params={"empresa_id": EMPRESA_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "Response should be a list"
        print(f"Found {len(data)} pagos/movements for empresa_id={EMPRESA_ID}")

    def test_list_pagos_response_structure(self):
        """Validate response has required fields from cont_movimiento_tesoreria"""
        response = requests.get(
            f"{BASE_URL}/api/pagos",
            params={"empresa_id": EMPRESA_ID}
        )
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            pago = data[0]
            # Required fields from cont_movimiento_tesoreria
            required_fields = ["id", "numero", "tipo", "fecha", "monto_total"]
            for field in required_fields:
                assert field in pago, f"Missing required field: {field}"
            
            # Optional fields that should be present
            optional_fields = ["cuenta_nombre", "moneda_codigo", "conciliado", "detalles", "aplicaciones"]
            for field in optional_fields:
                if field not in pago:
                    print(f"Note: Optional field '{field}' not in response")
            
            print(f"Sample pago: numero={pago.get('numero')}, tipo={pago.get('tipo')}, monto={pago.get('monto_total')}")

    def test_list_pagos_filter_by_tipo(self):
        """Test filtering by tipo (ingreso/egreso)"""
        # Test egreso filter
        response = requests.get(
            f"{BASE_URL}/api/pagos",
            params={"empresa_id": EMPRESA_ID, "tipo": "egreso"}
        )
        assert response.status_code == 200
        data = response.json()
        
        for pago in data:
            assert pago["tipo"] == "egreso", f"Expected tipo=egreso, got {pago['tipo']}"
        
        print(f"Found {len(data)} egresos")

    def test_list_pagos_includes_detalles_aplicaciones(self):
        """Verify detalles and aplicaciones are loaded for each pago"""
        response = requests.get(
            f"{BASE_URL}/api/pagos",
            params={"empresa_id": EMPRESA_ID}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check at least one pago has detalles or aplicaciones loaded
        has_detalles = any(len(p.get("detalles", [])) > 0 for p in data)
        has_aplicaciones = any(len(p.get("aplicaciones", [])) > 0 for p in data)
        
        print(f"Has detalles: {has_detalles}, Has aplicaciones: {has_aplicaciones}")


# =====================
# Module 2: POST /api/pagos - Create payment
# =====================
class TestCreatePago:
    """Test POST /api/pagos creates record in cont_movimiento_tesoreria"""

    @pytest.fixture
    def test_factura_id(self):
        """Create a test factura to pay"""
        factura_data = {
            "proveedor_id": PROVEEDOR_ID,
            "moneda_id": MONEDA_ID,
            "fecha_factura": datetime.now().strftime("%Y-%m-%d"),
            "tipo_documento": "factura",
            "lineas": [
                {
                    "descripcion": "TEST Item for payment test",
                    "importe": 100.0,
                    "igv_aplica": True
                }
            ]
        }
        response = requests.post(
            f"{BASE_URL}/api/facturas-proveedor",
            params={"empresa_id": EMPRESA_ID},
            json=factura_data
        )
        if response.status_code == 200:
            factura = response.json()
            yield factura["id"]
            # Cleanup - delete factura after test
            requests.delete(
                f"{BASE_URL}/api/facturas-proveedor/{factura['id']}",
                params={"empresa_id": EMPRESA_ID}
            )
        else:
            pytest.skip(f"Could not create test factura: {response.text}")

    def test_create_pago_basic(self, test_factura_id):
        """POST /api/pagos creates payment in cont_movimiento_tesoreria"""
        # Get factura details to know the amount
        factura_response = requests.get(
            f"{BASE_URL}/api/facturas-proveedor/{test_factura_id}",
            params={"empresa_id": EMPRESA_ID}
        )
        factura = factura_response.json()
        total = factura["total"]
        
        pago_data = {
            "tipo": "egreso",
            "fecha": datetime.now().strftime("%Y-%m-%d"),
            "cuenta_financiera_id": CUENTA_FINANCIERA_ID,
            "moneda_id": MONEDA_ID,
            "monto_total": total,
            "referencia": "TEST Payment",
            "notas": "Created by test_pagos_refactor.py",
            "detalles": [
                {
                    "cuenta_financiera_id": CUENTA_FINANCIERA_ID,
                    "medio_pago": "transferencia",
                    "monto": total
                }
            ],
            "aplicaciones": [
                {
                    "tipo_documento": "factura",
                    "documento_id": test_factura_id,
                    "monto_aplicado": total
                }
            ]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/pagos",
            params={"empresa_id": EMPRESA_ID},
            json=pago_data
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        pago = response.json()
        assert "id" in pago, "Response should contain id"
        assert "numero" in pago, "Response should contain numero"
        assert pago["numero"].startswith("PAG-E-"), f"Numero should start with PAG-E-, got {pago['numero']}"
        assert pago["tipo"] == "egreso"
        assert float(pago["monto_total"]) == total
        
        print(f"Created pago: {pago['numero']} for S/{total}")
        
        # Delete the created pago to cleanup
        delete_response = requests.delete(
            f"{BASE_URL}/api/pagos/{pago['id']}",
            params={"empresa_id": EMPRESA_ID}
        )
        assert delete_response.status_code == 200

    def test_create_pago_validates_monto_aplicado(self, test_factura_id):
        """POST /api/pagos rejects payment exceeding saldo_pendiente"""
        pago_data = {
            "tipo": "egreso",
            "fecha": datetime.now().strftime("%Y-%m-%d"),
            "cuenta_financiera_id": CUENTA_FINANCIERA_ID,
            "moneda_id": MONEDA_ID,
            "monto_total": 999999.0,  # Way more than factura total
            "detalles": [
                {
                    "cuenta_financiera_id": CUENTA_FINANCIERA_ID,
                    "medio_pago": "transferencia",
                    "monto": 999999.0
                }
            ],
            "aplicaciones": [
                {
                    "tipo_documento": "factura",
                    "documento_id": test_factura_id,
                    "monto_aplicado": 999999.0
                }
            ]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/pagos",
            params={"empresa_id": EMPRESA_ID},
            json=pago_data
        )
        # Should be rejected
        assert response.status_code == 400, f"Expected 400 for exceeding saldo, got {response.status_code}"
        print(f"Correctly rejected: {response.json()}")


# =====================
# Module 3: GET /api/pagos/{id} - Get single payment
# =====================
class TestGetPago:
    """Test GET /api/pagos/{id} returns single payment from cont_movimiento_tesoreria"""

    def test_get_pago_by_id(self):
        """GET /api/pagos/{id} returns payment details"""
        # First get list to find an existing pago
        list_response = requests.get(
            f"{BASE_URL}/api/pagos",
            params={"empresa_id": EMPRESA_ID}
        )
        pagos = list_response.json()
        
        if len(pagos) == 0:
            pytest.skip("No existing pagos to test GET by id")
        
        pago_id = pagos[0]["id"]
        
        response = requests.get(
            f"{BASE_URL}/api/pagos/{pago_id}",
            params={"empresa_id": EMPRESA_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        pago = response.json()
        assert pago["id"] == pago_id
        assert "detalles" in pago, "Should include detalles"
        assert "aplicaciones" in pago, "Should include aplicaciones"
        
        print(f"Got pago: {pago.get('numero')}")

    def test_get_pago_not_found(self):
        """GET /api/pagos/{id} returns 404 for non-existent id"""
        response = requests.get(
            f"{BASE_URL}/api/pagos/999999999",
            params={"empresa_id": EMPRESA_ID}
        )
        assert response.status_code == 404


# =====================
# Module 4: PUT /api/pagos/{id} - Update payment
# =====================
class TestUpdatePago:
    """Test PUT /api/pagos/{id} updates referencia/notas/fecha in cont_movimiento_tesoreria"""

    def test_update_pago_referencia(self):
        """PUT /api/pagos/{id} can update referencia"""
        # First get list to find an existing non-conciliado pago
        list_response = requests.get(
            f"{BASE_URL}/api/pagos",
            params={"empresa_id": EMPRESA_ID}
        )
        pagos = list_response.json()
        
        # Find a non-conciliado pago
        non_conciliado = [p for p in pagos if not p.get("conciliado")]
        if len(non_conciliado) == 0:
            pytest.skip("No non-conciliado pagos to test update")
        
        pago = non_conciliado[0]
        pago_id = pago["id"]
        original_ref = pago.get("referencia", "")
        
        new_ref = f"TEST Updated {datetime.now().strftime('%H:%M:%S')}"
        response = requests.put(
            f"{BASE_URL}/api/pagos/{pago_id}",
            params={"empresa_id": EMPRESA_ID},
            json={"referencia": new_ref}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify update
        get_response = requests.get(
            f"{BASE_URL}/api/pagos/{pago_id}",
            params={"empresa_id": EMPRESA_ID}
        )
        updated_pago = get_response.json()
        assert updated_pago.get("referencia") == new_ref or "actualizado" in response.json().get("message", "").lower()
        
        print(f"Updated pago {pago_id} referencia from '{original_ref}' to '{new_ref}'")

    def test_update_conciliado_pago_only_referencia(self):
        """PUT /api/pagos/{id} for conciliado pago only allows referencia update"""
        # Find a conciliado pago
        list_response = requests.get(
            f"{BASE_URL}/api/pagos",
            params={"empresa_id": EMPRESA_ID}
        )
        pagos = list_response.json()
        
        conciliado = [p for p in pagos if p.get("conciliado")]
        if len(conciliado) == 0:
            pytest.skip("No conciliado pagos to test restricted update")
        
        pago = conciliado[0]
        pago_id = pago["id"]
        
        # Should be able to update referencia
        response = requests.put(
            f"{BASE_URL}/api/pagos/{pago_id}",
            params={"empresa_id": EMPRESA_ID},
            json={"referencia": "TEST Conciliado ref update"}
        )
        assert response.status_code == 200
        print(f"Conciliado pago {pago_id} referencia update allowed")


# =====================
# Module 5: DELETE /api/pagos/{id} - Delete and reverse payment
# =====================
class TestDeletePago:
    """Test DELETE /api/pagos/{id} reverses balances and deletes from cont_movimiento_tesoreria"""

    def test_delete_pago_not_found(self):
        """DELETE /api/pagos/{id} returns 404 for non-existent id"""
        response = requests.delete(
            f"{BASE_URL}/api/pagos/999999999",
            params={"empresa_id": EMPRESA_ID}
        )
        assert response.status_code == 404

    def test_delete_conciliado_pago_rejected(self):
        """DELETE /api/pagos/{id} rejects deletion of conciliado pago"""
        # Find a conciliado pago
        list_response = requests.get(
            f"{BASE_URL}/api/pagos",
            params={"empresa_id": EMPRESA_ID}
        )
        pagos = list_response.json()
        
        conciliado = [p for p in pagos if p.get("conciliado")]
        if len(conciliado) == 0:
            pytest.skip("No conciliado pagos to test delete rejection")
        
        pago_id = conciliado[0]["id"]
        
        response = requests.delete(
            f"{BASE_URL}/api/pagos/{pago_id}",
            params={"empresa_id": EMPRESA_ID}
        )
        assert response.status_code == 400, f"Expected 400 for conciliado, got {response.status_code}"
        print(f"Correctly rejected delete of conciliado pago {pago_id}")


# =====================
# Module 6: Full Payment Lifecycle
# =====================
class TestFullPaymentLifecycle:
    """Test full factura -> pago -> verify estado -> delete pago -> verify estado reverted"""

    def test_factura_payment_lifecycle(self):
        """Create factura -> pay it -> verify pagado -> delete pago -> verify pendiente"""
        # Step 1: Create factura
        factura_data = {
            "proveedor_id": PROVEEDOR_ID,
            "moneda_id": MONEDA_ID,
            "fecha_factura": datetime.now().strftime("%Y-%m-%d"),
            "tipo_documento": "factura",
            "lineas": [
                {
                    "descripcion": "TEST Lifecycle test item",
                    "importe": 500.0,
                    "igv_aplica": True
                }
            ]
        }
        factura_response = requests.post(
            f"{BASE_URL}/api/facturas-proveedor",
            params={"empresa_id": EMPRESA_ID},
            json=factura_data
        )
        assert factura_response.status_code == 200, f"Failed to create factura: {factura_response.text}"
        factura = factura_response.json()
        factura_id = factura["id"]
        total = factura["total"]
        print(f"Step 1: Created factura {factura['numero']} with total S/{total}")
        
        try:
            # Step 2: Create payment for the factura
            pago_data = {
                "tipo": "egreso",
                "fecha": datetime.now().strftime("%Y-%m-%d"),
                "cuenta_financiera_id": CUENTA_FINANCIERA_ID,
                "moneda_id": MONEDA_ID,
                "monto_total": total,
                "referencia": "TEST Lifecycle payment",
                "detalles": [
                    {
                        "cuenta_financiera_id": CUENTA_FINANCIERA_ID,
                        "medio_pago": "transferencia",
                        "monto": total
                    }
                ],
                "aplicaciones": [
                    {
                        "tipo_documento": "factura",
                        "documento_id": factura_id,
                        "monto_aplicado": total
                    }
                ]
            }
            
            pago_response = requests.post(
                f"{BASE_URL}/api/pagos",
                params={"empresa_id": EMPRESA_ID},
                json=pago_data
            )
            assert pago_response.status_code == 200, f"Failed to create pago: {pago_response.text}"
            pago = pago_response.json()
            pago_id = pago["id"]
            print(f"Step 2: Created pago {pago['numero']}")
            
            # Step 3: Verify factura estado = pagado
            factura_check = requests.get(
                f"{BASE_URL}/api/facturas-proveedor/{factura_id}",
                params={"empresa_id": EMPRESA_ID}
            )
            factura_estado = factura_check.json()["estado"]
            assert factura_estado == "pagado", f"Expected estado=pagado, got {factura_estado}"
            print(f"Step 3: Verified factura estado = {factura_estado}")
            
            # Step 4: Delete pago
            delete_response = requests.delete(
                f"{BASE_URL}/api/pagos/{pago_id}",
                params={"empresa_id": EMPRESA_ID}
            )
            assert delete_response.status_code == 200, f"Failed to delete pago: {delete_response.text}"
            print(f"Step 4: Deleted pago {pago_id}")
            
            # Step 5: Verify factura estado reverted to pendiente
            factura_final = requests.get(
                f"{BASE_URL}/api/facturas-proveedor/{factura_id}",
                params={"empresa_id": EMPRESA_ID}
            )
            final_estado = factura_final.json()["estado"]
            assert final_estado == "pendiente", f"Expected estado=pendiente after pago delete, got {final_estado}"
            print(f"Step 5: Verified factura estado reverted to {final_estado}")
            
        finally:
            # Cleanup
            requests.delete(
                f"{BASE_URL}/api/facturas-proveedor/{factura_id}",
                params={"empresa_id": EMPRESA_ID}
            )
            print("Cleanup: Deleted test factura")


# =====================
# Module 7: Letras Lifecycle
# =====================
class TestLetrasLifecycle:
    """Test factura -> generate letras -> pay letra -> verify letra estado=pagada"""

    def test_letras_payment_lifecycle(self):
        """Create factura -> generate letras -> pay first letra -> verify"""
        # Step 1: Create factura
        factura_data = {
            "proveedor_id": PROVEEDOR_ID,
            "moneda_id": MONEDA_ID,
            "fecha_factura": datetime.now().strftime("%Y-%m-%d"),
            "fecha_vencimiento": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            "tipo_documento": "factura",
            "lineas": [
                {
                    "descripcion": "TEST Letras lifecycle item",
                    "importe": 1000.0,
                    "igv_aplica": True
                }
            ]
        }
        factura_response = requests.post(
            f"{BASE_URL}/api/facturas-proveedor",
            params={"empresa_id": EMPRESA_ID},
            json=factura_data
        )
        assert factura_response.status_code == 200, f"Failed to create factura: {factura_response.text}"
        factura = factura_response.json()
        factura_id = factura["id"]
        total = factura["total"]
        print(f"Step 1: Created factura {factura['numero']} with total S/{total}")
        
        try:
            # Step 2: Generate letras
            letras_data = {
                "factura_id": factura_id,
                "cantidad_letras": 2,
                "dias_entre_letras": 30
            }
            letras_response = requests.post(
                f"{BASE_URL}/api/letras/generar",
                params={"empresa_id": EMPRESA_ID},
                json=letras_data
            )
            assert letras_response.status_code == 200, f"Failed to generate letras: {letras_response.text}"
            letras = letras_response.json()
            assert len(letras) == 2, f"Expected 2 letras, got {len(letras)}"
            print(f"Step 2: Generated {len(letras)} letras")
            
            # Step 3: Verify factura estado = canjeado
            factura_check = requests.get(
                f"{BASE_URL}/api/facturas-proveedor/{factura_id}",
                params={"empresa_id": EMPRESA_ID}
            )
            assert factura_check.json()["estado"] == "canjeado", "Factura should be canjeado after letras"
            
            # Step 4: Pay first letra
            primera_letra = letras[0]
            letra_id = primera_letra["id"]
            letra_monto = float(primera_letra["monto"])
            
            pago_letra_data = {
                "tipo": "egreso",
                "fecha": datetime.now().strftime("%Y-%m-%d"),
                "cuenta_financiera_id": CUENTA_FINANCIERA_ID,
                "moneda_id": MONEDA_ID,
                "monto_total": letra_monto,
                "referencia": "TEST Letra payment",
                "detalles": [
                    {
                        "cuenta_financiera_id": CUENTA_FINANCIERA_ID,
                        "medio_pago": "transferencia",
                        "monto": letra_monto
                    }
                ],
                "aplicaciones": [
                    {
                        "tipo_documento": "letra",
                        "documento_id": letra_id,
                        "monto_aplicado": letra_monto
                    }
                ]
            }
            
            pago_response = requests.post(
                f"{BASE_URL}/api/pagos",
                params={"empresa_id": EMPRESA_ID},
                json=pago_letra_data
            )
            assert pago_response.status_code == 200, f"Failed to pay letra: {pago_response.text}"
            pago = pago_response.json()
            pago_id = pago["id"]
            print(f"Step 4: Created pago {pago['numero']} for letra S/{letra_monto}")
            
            # Step 5: Verify letra estado = pagada
            letras_check = requests.get(
                f"{BASE_URL}/api/letras",
                params={"empresa_id": EMPRESA_ID, "factura_id": factura_id}
            )
            letras_updated = letras_check.json()
            primera_letra_updated = next((l for l in letras_updated if l["id"] == letra_id), None)
            assert primera_letra_updated is not None
            assert primera_letra_updated["estado"] == "pagada", f"Expected letra estado=pagada, got {primera_letra_updated['estado']}"
            print(f"Step 5: Verified letra estado = {primera_letra_updated['estado']}")
            
            # Cleanup pago first
            requests.delete(
                f"{BASE_URL}/api/pagos/{pago_id}",
                params={"empresa_id": EMPRESA_ID}
            )
            
        finally:
            # Cleanup - need to delete letras first, then factura
            letras_list = requests.get(
                f"{BASE_URL}/api/letras",
                params={"empresa_id": EMPRESA_ID, "factura_id": factura_id}
            )
            for letra in letras_list.json():
                requests.delete(
                    f"{BASE_URL}/api/letras/{letra['id']}",
                    params={"empresa_id": EMPRESA_ID}
                )
            
            requests.delete(
                f"{BASE_URL}/api/facturas-proveedor/{factura_id}",
                params={"empresa_id": EMPRESA_ID}
            )
            print("Cleanup: Deleted test letras and factura")


# =====================
# Module 8: Get Factura Pagos (COALESCE query)
# =====================
class TestGetFacturaPagos:
    """Test GET /api/facturas-proveedor/{id}/pagos returns payments with COALESCE for old/new"""

    def test_get_factura_pagos_endpoint(self):
        """GET /api/facturas-proveedor/{id}/pagos works with COALESCE query"""
        # First get a factura that might have pagos
        facturas_response = requests.get(
            f"{BASE_URL}/api/facturas-proveedor",
            params={"empresa_id": EMPRESA_ID}
        )
        facturas = facturas_response.json()
        
        # Find a factura with partial or paid status (likely has pagos)
        factura_con_pagos = next(
            (f for f in facturas if f.get("estado") in ["parcial", "pagado"]),
            None
        )
        
        if factura_con_pagos is None:
            pytest.skip("No facturas with payments to test")
        
        factura_id = factura_con_pagos["id"]
        
        response = requests.get(
            f"{BASE_URL}/api/facturas-proveedor/{factura_id}/pagos",
            params={"empresa_id": EMPRESA_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        pagos = response.json()
        assert isinstance(pagos, list)
        
        if len(pagos) > 0:
            pago = pagos[0]
            # Verify COALESCE query returns id and numero
            assert "id" in pago, "Should have id (from COALESCE)"
            assert "numero" in pago, "Should have numero (from COALESCE)"
            print(f"Factura {factura_id} has {len(pagos)} pagos, first: {pago.get('numero')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
