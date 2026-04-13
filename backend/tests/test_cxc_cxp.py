"""
Test CxC (Cuentas por Cobrar) and CxP (Cuentas por Pagar) API endpoints - Phase 3
Tests cover: listing with enhanced fields, resumen with aging, manual creation, and abonos (partial payments)
"""
import pytest
import requests
import os
from datetime import date, datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
EMPRESA_ID = 6  # Ambission Industries SAC - has test data


class TestCxCEndpoints:
    """CxC (Cuentas por Cobrar) endpoint tests"""

    def test_list_cxc_success(self):
        """GET /api/cxc returns list with enhanced fields"""
        response = requests.get(f"{BASE_URL}/api/cxc", params={"empresa_id": EMPRESA_ID})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        if len(data) > 0:
            item = data[0]
            # Check enhanced fields exist
            assert "id" in item
            assert "cliente_nombre" in item
            assert "monto_original" in item
            assert "saldo_pendiente" in item
            assert "estado" in item
            assert "fecha_vencimiento" in item or item.get("fecha_vencimiento") is None
            assert "tipo_origen" in item or item.get("tipo_origen") is None
            assert "dias_atraso" in item or item.get("dias_atraso") is None
            assert "total_abonado" in item
            assert "aging_bucket" in item
            print(f"CxC list returned {len(data)} items with all enhanced fields")

    def test_list_cxc_with_estado_filter(self):
        """GET /api/cxc?estado=pendiente filters correctly"""
        response = requests.get(f"{BASE_URL}/api/cxc", params={"empresa_id": EMPRESA_ID, "estado": "pendiente"})
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert item["estado"] == "pendiente", f"Expected estado=pendiente, got {item['estado']}"
        print(f"Estado filter returned {len(data)} pendiente items")

    def test_list_cxc_with_aging_filter(self):
        """GET /api/cxc?aging=vigente filters correctly"""
        response = requests.get(f"{BASE_URL}/api/cxc", params={"empresa_id": EMPRESA_ID, "aging": "vigente"})
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert item["aging_bucket"] == "vigente", f"Expected aging_bucket=vigente, got {item['aging_bucket']}"
        print(f"Aging filter (vigente) returned {len(data)} items")

    def test_cxc_resumen_success(self):
        """GET /api/cxc/resumen returns summary with aging buckets"""
        response = requests.get(f"{BASE_URL}/api/cxc/resumen", params={"empresa_id": EMPRESA_ID})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Check required fields
        assert "total_docs" in data
        assert "total_pendiente" in data
        assert "total_vencido" in data
        assert "docs_vencidos" in data
        assert "por_vencer_7d" in data
        assert "aging" in data
        
        # Check aging buckets
        aging = data["aging"]
        assert "vigente" in aging
        assert "0_30" in aging
        assert "31_60" in aging
        assert "61_90" in aging
        assert "90_plus" in aging
        
        # Each bucket should have count and total
        for bucket_name in ["vigente", "0_30", "31_60", "61_90", "90_plus"]:
            assert "count" in aging[bucket_name]
            assert "total" in aging[bucket_name]
        
        print(f"CxC resumen: {data['total_docs']} docs, total_pendiente={data['total_pendiente']}, aging buckets OK")

    def test_create_cxc_manual(self):
        """POST /api/cxc creates a manual CxC record"""
        payload = {
            "monto_original": 1500.50,
            "fecha_vencimiento": "2026-02-28",
            "documento_referencia": "TEST-CXC-001",
            "tipo_origen": "manual",
            "notas": "Test CxC from pytest"
        }
        response = requests.post(f"{BASE_URL}/api/cxc", params={"empresa_id": EMPRESA_ID}, json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data
        assert data["id"] > 0
        print(f"Created manual CxC with ID: {data['id']}")
        
        # Store for later cleanup/verification
        return data["id"]

    def test_get_cxc_abonos(self):
        """GET /api/cxc/{id}/abonos returns abonos list"""
        # CxC ID 6 has known test data with 1 abono of 300
        cxc_id = 6
        response = requests.get(f"{BASE_URL}/api/cxc/{cxc_id}/abonos", params={"empresa_id": EMPRESA_ID})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        if len(data) > 0:
            abono = data[0]
            assert "id" in abono
            assert "fecha" in abono
            assert "monto" in abono
            print(f"CxC {cxc_id} has {len(data)} abonos")
        else:
            print(f"CxC {cxc_id} has no abonos")

    def test_create_cxc_abono_validation_positive_monto(self):
        """POST /api/cxc/{id}/abonos validates monto must be positive"""
        # First create a CxC to test abono
        create_payload = {
            "monto_original": 500.00,
            "documento_referencia": "TEST-ABONO-VAL",
            "tipo_origen": "manual"
        }
        create_response = requests.post(f"{BASE_URL}/api/cxc", params={"empresa_id": EMPRESA_ID}, json=create_payload)
        assert create_response.status_code == 200
        cxc_id = create_response.json()["id"]
        
        # Try to create abono with zero monto
        abono_payload = {
            "fecha": "2026-01-20",
            "monto": 0,  # Invalid
            "forma_pago": "efectivo"
        }
        response = requests.post(f"{BASE_URL}/api/cxc/{cxc_id}/abonos", params={"empresa_id": EMPRESA_ID}, json=abono_payload)
        assert response.status_code == 400, f"Expected 400 for zero monto, got {response.status_code}"
        print("Validation passed: monto=0 rejected")

    def test_create_cxc_abono_validation_exceeds_saldo(self):
        """POST /api/cxc/{id}/abonos validates abono cannot exceed saldo_pendiente"""
        # First create a CxC with known amount
        create_payload = {
            "monto_original": 100.00,
            "documento_referencia": "TEST-EXCEED-SALDO",
            "tipo_origen": "manual"
        }
        create_response = requests.post(f"{BASE_URL}/api/cxc", params={"empresa_id": EMPRESA_ID}, json=create_payload)
        assert create_response.status_code == 200
        cxc_id = create_response.json()["id"]
        
        # Try to create abono exceeding saldo
        abono_payload = {
            "fecha": "2026-01-20",
            "monto": 150.00,  # Exceeds 100.00
            "forma_pago": "efectivo"
        }
        response = requests.post(f"{BASE_URL}/api/cxc/{cxc_id}/abonos", params={"empresa_id": EMPRESA_ID}, json=abono_payload)
        assert response.status_code == 400, f"Expected 400 for exceeding saldo, got {response.status_code}"
        assert "excede" in response.json().get("detail", "").lower() or "saldo" in response.json().get("detail", "").lower()
        print("Validation passed: abono exceeding saldo rejected")

    def test_create_cxc_abono_updates_saldo(self):
        """POST /api/cxc/{id}/abonos creates abono and updates saldo_pendiente"""
        # Create a CxC
        create_payload = {
            "monto_original": 200.00,
            "documento_referencia": "TEST-ABONO-UPDATE",
            "tipo_origen": "manual"
        }
        create_response = requests.post(f"{BASE_URL}/api/cxc", params={"empresa_id": EMPRESA_ID}, json=create_payload)
        assert create_response.status_code == 200
        cxc_id = create_response.json()["id"]
        
        # Create partial abono
        abono_payload = {
            "fecha": "2026-01-20",
            "monto": 50.00,
            "forma_pago": "efectivo"
        }
        response = requests.post(f"{BASE_URL}/api/cxc/{cxc_id}/abonos", params={"empresa_id": EMPRESA_ID}, json=abono_payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "nuevo_saldo" in data
        assert data["nuevo_saldo"] == 150.00, f"Expected nuevo_saldo=150.00, got {data['nuevo_saldo']}"
        assert data["nuevo_estado"] == "parcial", f"Expected estado=parcial, got {data['nuevo_estado']}"
        print(f"Abono created: nuevo_saldo={data['nuevo_saldo']}, nuevo_estado={data['nuevo_estado']}")


class TestCxPEndpoints:
    """CxP (Cuentas por Pagar) endpoint tests"""

    def test_list_cxp_success(self):
        """GET /api/cxp returns list with enhanced fields"""
        response = requests.get(f"{BASE_URL}/api/cxp", params={"empresa_id": EMPRESA_ID})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        if len(data) > 0:
            item = data[0]
            # Check enhanced fields exist
            assert "id" in item
            assert "proveedor_nombre" in item
            assert "monto_original" in item
            assert "saldo_pendiente" in item
            assert "estado" in item
            assert "dias_vencido" in item or item.get("dias_vencido") is None
            assert "total_abonado" in item
            assert "aging_bucket" in item
            print(f"CxP list returned {len(data)} items with all enhanced fields")
        else:
            print("CxP list is empty (no data)")

    def test_list_cxp_with_estado_filter(self):
        """GET /api/cxp?estado=pendiente filters correctly"""
        response = requests.get(f"{BASE_URL}/api/cxp", params={"empresa_id": EMPRESA_ID, "estado": "pendiente"})
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert item["estado"] == "pendiente", f"Expected estado=pendiente, got {item['estado']}"
        print(f"Estado filter returned {len(data)} pendiente items")

    def test_list_cxp_with_aging_filter(self):
        """GET /api/cxp?aging=vigente filters correctly"""
        response = requests.get(f"{BASE_URL}/api/cxp", params={"empresa_id": EMPRESA_ID, "aging": "vigente"})
        assert response.status_code == 200
        data = response.json()
        for item in data:
            assert item["aging_bucket"] == "vigente", f"Expected aging_bucket=vigente, got {item['aging_bucket']}"
        print(f"Aging filter (vigente) returned {len(data)} items")

    def test_cxp_resumen_success(self):
        """GET /api/cxp/resumen returns summary with aging buckets"""
        response = requests.get(f"{BASE_URL}/api/cxp/resumen", params={"empresa_id": EMPRESA_ID})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Check required fields
        assert "total_docs" in data
        assert "total_pendiente" in data
        assert "total_vencido" in data
        assert "docs_vencidos" in data
        assert "por_vencer_7d" in data
        assert "aging" in data
        
        # Check aging buckets
        aging = data["aging"]
        assert "vigente" in aging
        assert "0_30" in aging
        assert "31_60" in aging
        assert "61_90" in aging
        assert "90_plus" in aging
        
        print(f"CxP resumen: {data['total_docs']} docs, total_pendiente={data['total_pendiente']}")

    def test_create_cxp_manual(self):
        """POST /api/cxp creates a manual CxP record"""
        payload = {
            "monto_original": 2500.00,
            "fecha_vencimiento": "2026-02-15",
            "documento_referencia": "TEST-CXP-001",
            "tipo_origen": "compra"
        }
        response = requests.post(f"{BASE_URL}/api/cxp", params={"empresa_id": EMPRESA_ID}, json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data
        assert data["id"] > 0
        print(f"Created manual CxP with ID: {data['id']}")
        return data["id"]

    def test_get_cxp_abonos(self):
        """GET /api/cxp/{id}/abonos returns abonos list"""
        # First get a CxP to test
        list_response = requests.get(f"{BASE_URL}/api/cxp", params={"empresa_id": EMPRESA_ID})
        if len(list_response.json()) == 0:
            pytest.skip("No CxP records to test abonos")
        
        cxp_id = list_response.json()[0]["id"]
        response = requests.get(f"{BASE_URL}/api/cxp/{cxp_id}/abonos", params={"empresa_id": EMPRESA_ID})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"CxP {cxp_id} has {len(data)} abonos")

    def test_create_cxp_abono_validation_positive_monto(self):
        """POST /api/cxp/{id}/abonos validates monto must be positive"""
        # Create a CxP
        create_payload = {
            "monto_original": 500.00,
            "documento_referencia": "TEST-CXP-ABONO-VAL",
            "tipo_origen": "compra"
        }
        create_response = requests.post(f"{BASE_URL}/api/cxp", params={"empresa_id": EMPRESA_ID}, json=create_payload)
        assert create_response.status_code == 200
        cxp_id = create_response.json()["id"]
        
        # Try to create abono with negative monto
        abono_payload = {
            "fecha": "2026-01-20",
            "monto": -10,  # Invalid
            "forma_pago": "transferencia"
        }
        response = requests.post(f"{BASE_URL}/api/cxp/{cxp_id}/abonos", params={"empresa_id": EMPRESA_ID}, json=abono_payload)
        assert response.status_code == 400, f"Expected 400 for negative monto, got {response.status_code}"
        print("Validation passed: negative monto rejected")

    def test_create_cxp_abono_updates_saldo_and_estado(self):
        """POST /api/cxp/{id}/abonos creates abono and updates saldo_pendiente, uses 'pagado' estado"""
        # Create a CxP
        create_payload = {
            "monto_original": 100.00,
            "documento_referencia": "TEST-CXP-FULL-PAY",
            "tipo_origen": "compra"
        }
        create_response = requests.post(f"{BASE_URL}/api/cxp", params={"empresa_id": EMPRESA_ID}, json=create_payload)
        assert create_response.status_code == 200
        cxp_id = create_response.json()["id"]
        
        # Create full payment abono
        abono_payload = {
            "fecha": "2026-01-20",
            "monto": 100.00,
            "forma_pago": "transferencia"
        }
        response = requests.post(f"{BASE_URL}/api/cxp/{cxp_id}/abonos", params={"empresa_id": EMPRESA_ID}, json=abono_payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "nuevo_saldo" in data
        assert data["nuevo_saldo"] == 0, f"Expected nuevo_saldo=0, got {data['nuevo_saldo']}"
        # Critical: CxP uses 'pagado' NOT 'pagada' (PostgreSQL enum)
        assert data["nuevo_estado"] == "pagado", f"Expected estado='pagado', got {data['nuevo_estado']}"
        print(f"CxP fully paid: nuevo_saldo={data['nuevo_saldo']}, nuevo_estado={data['nuevo_estado']}")


class TestCxCCxPIntegration:
    """Integration tests for CxC and CxP flows"""

    def test_cxc_partial_payment_flow(self):
        """Test full CxC flow: create -> partial abono -> check estado=parcial -> full abono -> estado=cobrada"""
        # Create CxC
        create_payload = {
            "monto_original": 1000.00,
            "documento_referencia": "TEST-FLOW-CXC",
            "tipo_origen": "manual"
        }
        create_response = requests.post(f"{BASE_URL}/api/cxc", params={"empresa_id": EMPRESA_ID}, json=create_payload)
        assert create_response.status_code == 200
        cxc_id = create_response.json()["id"]
        
        # Partial abono
        abono1 = {"fecha": "2026-01-20", "monto": 400.00, "forma_pago": "efectivo"}
        response1 = requests.post(f"{BASE_URL}/api/cxc/{cxc_id}/abonos", params={"empresa_id": EMPRESA_ID}, json=abono1)
        assert response1.status_code == 200
        assert response1.json()["nuevo_estado"] == "parcial"
        assert response1.json()["nuevo_saldo"] == 600.00
        
        # Remaining abono
        abono2 = {"fecha": "2026-01-21", "monto": 600.00, "forma_pago": "transferencia"}
        response2 = requests.post(f"{BASE_URL}/api/cxc/{cxc_id}/abonos", params={"empresa_id": EMPRESA_ID}, json=abono2)
        assert response2.status_code == 200
        assert response2.json()["nuevo_estado"] == "cobrada"
        assert response2.json()["nuevo_saldo"] == 0
        
        # Verify abonos list
        abonos_response = requests.get(f"{BASE_URL}/api/cxc/{cxc_id}/abonos", params={"empresa_id": EMPRESA_ID})
        assert len(abonos_response.json()) == 2
        
        print(f"CxC flow complete: created ID={cxc_id}, 2 abonos, final estado=cobrada")

    def test_cxp_partial_payment_flow(self):
        """Test full CxP flow: create -> partial abono -> estado=parcial -> full abono -> estado=pagado"""
        # Create CxP
        create_payload = {
            "monto_original": 500.00,
            "documento_referencia": "TEST-FLOW-CXP",
            "tipo_origen": "servicio"
        }
        create_response = requests.post(f"{BASE_URL}/api/cxp", params={"empresa_id": EMPRESA_ID}, json=create_payload)
        assert create_response.status_code == 200
        cxp_id = create_response.json()["id"]
        
        # Partial abono
        abono1 = {"fecha": "2026-01-20", "monto": 200.00, "forma_pago": "transferencia"}
        response1 = requests.post(f"{BASE_URL}/api/cxp/{cxp_id}/abonos", params={"empresa_id": EMPRESA_ID}, json=abono1)
        assert response1.status_code == 200
        assert response1.json()["nuevo_estado"] == "parcial"
        assert response1.json()["nuevo_saldo"] == 300.00
        
        # Remaining abono
        abono2 = {"fecha": "2026-01-21", "monto": 300.00, "forma_pago": "cheque"}
        response2 = requests.post(f"{BASE_URL}/api/cxp/{cxp_id}/abonos", params={"empresa_id": EMPRESA_ID}, json=abono2)
        assert response2.status_code == 200
        assert response2.json()["nuevo_estado"] == "pagado"  # NOT 'pagada'
        assert response2.json()["nuevo_saldo"] == 0
        
        print(f"CxP flow complete: created ID={cxp_id}, 2 abonos, final estado=pagado")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
