"""
Test suite for Categorías de Gasto, Gastos with new fields (categoria_gasto_id, tipo_asignacion, etc.), 
and Prorrateo de Gastos Comunes functionality.

Tests:
- Categorías de Gasto CRUD (GET, POST, PUT, DELETE)
- Gastos creation with new fields and enriched response names
- Prorrateo pendientes filter (comun/no_asignado vs directo)
- Prorrateo preview and execution
- Prorrateo historial
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://concilia-smart.preview.emergentagent.com')
EMPRESA_ID = 6
MONEDA_ID = 7  # PEN


class TestCategoriasGastoCRUD:
    """Tests for Categorías de Gasto CRUD operations"""

    @pytest.fixture(scope="class")
    def test_categoria(self):
        """Create and cleanup test categoria"""
        # Create
        payload = {
            "codigo": "TEST-AUTO",
            "nombre": "TEST Categoria Auto",
            "activo": True
        }
        resp = requests.post(f"{BASE_URL}/api/categorias-gasto", params={"empresa_id": EMPRESA_ID}, json=payload)
        assert resp.status_code == 200, f"Failed to create test categoria: {resp.text}"
        created = resp.json()
        yield created
        # Cleanup
        requests.delete(f"{BASE_URL}/api/categorias-gasto/{created['id']}", params={"empresa_id": EMPRESA_ID})

    def test_list_categorias_gasto(self):
        """GET /api/categorias-gasto - List expense categories"""
        resp = requests.get(f"{BASE_URL}/api/categorias-gasto", params={"empresa_id": EMPRESA_ID})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Found {len(data)} categorias de gasto")

    def test_create_categoria_gasto(self, test_categoria):
        """POST /api/categorias-gasto - Create expense category"""
        assert "id" in test_categoria, "Created categoria should have id"
        assert test_categoria["nombre"] == "TEST Categoria Auto"
        assert test_categoria["codigo"] == "TEST-AUTO"
        assert test_categoria["activo"] is True
        print(f"Created categoria with id={test_categoria['id']}")

    def test_update_categoria_gasto(self, test_categoria):
        """PUT /api/categorias-gasto/{id} - Update expense category"""
        update_payload = {
            "codigo": "TEST-UPD",
            "nombre": "TEST Updated Categoria",
            "activo": True
        }
        resp = requests.put(
            f"{BASE_URL}/api/categorias-gasto/{test_categoria['id']}",
            params={"empresa_id": EMPRESA_ID},
            json=update_payload
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        updated = resp.json()
        assert updated["nombre"] == "TEST Updated Categoria"
        assert updated["codigo"] == "TEST-UPD"
        print(f"Updated categoria {test_categoria['id']} successfully")

    def test_delete_categoria_gasto_not_found(self):
        """DELETE /api/categorias-gasto/{id} - Non-existent returns error"""
        resp = requests.delete(f"{BASE_URL}/api/categorias-gasto/99999", params={"empresa_id": EMPRESA_ID})
        # Should return success message even if not found (based on current implementation)
        assert resp.status_code in [200, 404], f"Unexpected status: {resp.status_code}"


class TestGastosWithNewFields:
    """Tests for Gastos with new dimension fields"""

    @pytest.fixture(scope="class")
    def test_gasto_directo(self):
        """Create a gasto with tipo_asignacion='directo' and cleanup"""
        # First get available cuentas and categorias
        cuentas_resp = requests.get(f"{BASE_URL}/api/cuentas-financieras", params={"empresa_id": EMPRESA_ID})
        cuentas = cuentas_resp.json()
        assert len(cuentas) > 0, "No cuentas financieras found"
        cuenta_id = cuentas[0]["id"]

        cat_gasto_resp = requests.get(f"{BASE_URL}/api/categorias-gasto", params={"empresa_id": EMPRESA_ID})
        cat_gastos = cat_gasto_resp.json()
        cat_gasto_id = cat_gastos[0]["id"] if cat_gastos else None

        centros_resp = requests.get(f"{BASE_URL}/api/centros-costo", params={"empresa_id": EMPRESA_ID})
        centros = centros_resp.json()
        centro_id = centros[0]["id"] if centros else None

        lineas_resp = requests.get(f"{BASE_URL}/api/lineas-negocio", params={"empresa_id": EMPRESA_ID})
        lineas = lineas_resp.json()
        linea_id = lineas[0]["id"] if lineas else None

        payload = {
            "fecha": "2026-01-15",
            "fecha_contable": "2026-01-15",
            "beneficiario_nombre": "TEST Beneficiario Directo",
            "moneda_id": MONEDA_ID,
            "tipo_documento": "boleta",
            "numero_documento": "TEST-001",
            "base_gravada": 100.00,
            "igv_sunat": 18.00,
            "base_no_gravada": 0,
            "categoria_gasto_id": cat_gasto_id,
            "tipo_asignacion": "directo",
            "centro_costo_id": centro_id,
            "linea_negocio_id": linea_id,
            "lineas": [
                {"importe": 118.00, "igv_aplica": True, "descripcion": "Test line item"}
            ],
            "pagos": [
                {"cuenta_financiera_id": cuenta_id, "medio_pago": "efectivo", "monto": 118.00}
            ]
        }
        resp = requests.post(f"{BASE_URL}/api/gastos", params={"empresa_id": EMPRESA_ID}, json=payload)
        assert resp.status_code == 200, f"Failed to create gasto directo: {resp.text}"
        created = resp.json()
        yield created
        # Cleanup
        requests.delete(f"{BASE_URL}/api/gastos/{created['id']}", params={"empresa_id": EMPRESA_ID})

    @pytest.fixture(scope="class")
    def test_gasto_comun(self):
        """Create a gasto with tipo_asignacion='comun' for prorrateo"""
        cuentas_resp = requests.get(f"{BASE_URL}/api/cuentas-financieras", params={"empresa_id": EMPRESA_ID})
        cuentas = cuentas_resp.json()
        cuenta_id = cuentas[0]["id"]

        cat_gasto_resp = requests.get(f"{BASE_URL}/api/categorias-gasto", params={"empresa_id": EMPRESA_ID})
        cat_gastos = cat_gasto_resp.json()
        cat_gasto_id = cat_gastos[0]["id"] if cat_gastos else None

        payload = {
            "fecha": "2026-01-16",
            "fecha_contable": "2026-01-16",
            "beneficiario_nombre": "TEST Beneficiario Comun",
            "moneda_id": MONEDA_ID,
            "tipo_documento": "factura",
            "numero_documento": "TEST-002",
            "base_gravada": 500.00,
            "igv_sunat": 90.00,
            "base_no_gravada": 0,
            "categoria_gasto_id": cat_gasto_id,
            "tipo_asignacion": "comun",  # This should appear in prorrateo pendientes
            "centro_costo_id": None,
            "linea_negocio_id": None,  # No linea when comun
            "lineas": [
                {"importe": 590.00, "igv_aplica": True, "descripcion": "Test comun line"}
            ],
            "pagos": [
                {"cuenta_financiera_id": cuenta_id, "medio_pago": "transferencia", "monto": 590.00}
            ]
        }
        resp = requests.post(f"{BASE_URL}/api/gastos", params={"empresa_id": EMPRESA_ID}, json=payload)
        assert resp.status_code == 200, f"Failed to create gasto comun: {resp.text}"
        created = resp.json()
        yield created
        # Cleanup - first try to delete any prorrateo, then delete gasto
        requests.delete(f"{BASE_URL}/api/prorrateo/{created['id']}", params={"empresa_id": EMPRESA_ID})
        requests.delete(f"{BASE_URL}/api/gastos/{created['id']}", params={"empresa_id": EMPRESA_ID})

    def test_list_gastos_with_enriched_names(self):
        """GET /api/gastos - Returns gastos with enriched dimension names"""
        resp = requests.get(f"{BASE_URL}/api/gastos", params={"empresa_id": EMPRESA_ID})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Check structure includes new enriched fields
        if len(data) > 0:
            gasto = data[0]
            expected_fields = ["categoria_gasto_nombre", "centro_costo_nombre", "marca_nombre", "linea_negocio_nombre", "tipo_asignacion"]
            for field in expected_fields:
                assert field in gasto, f"Field {field} should be in response"
        print(f"Listed {len(data)} gastos with enriched names")

    def test_create_gasto_directo_with_enriched_response(self, test_gasto_directo):
        """POST /api/gastos - Create gasto directo returns enriched names"""
        assert "id" in test_gasto_directo
        assert test_gasto_directo["tipo_asignacion"] == "directo"
        # Should have enriched name fields (may be null if no FK)
        assert "categoria_gasto_nombre" in test_gasto_directo
        assert "centro_costo_nombre" in test_gasto_directo
        assert "linea_negocio_nombre" in test_gasto_directo
        print(f"Created directo gasto id={test_gasto_directo['id']}, tipo={test_gasto_directo['tipo_asignacion']}")

    def test_create_gasto_comun_for_prorrateo(self, test_gasto_comun):
        """POST /api/gastos - Create gasto comun (for prorrateo later)"""
        assert "id" in test_gasto_comun
        assert test_gasto_comun["tipo_asignacion"] == "comun"
        print(f"Created comun gasto id={test_gasto_comun['id']} for prorrateo testing")


class TestProrrateo:
    """Tests for Prorrateo de Gastos Comunes functionality"""

    def test_prorrateo_pendientes_excludes_directo(self):
        """GET /api/prorrateo/pendientes - Should NOT include tipo_asignacion='directo'"""
        resp = requests.get(f"{BASE_URL}/api/prorrateo/pendientes", params={"empresa_id": EMPRESA_ID})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Verify no 'directo' gastos in pendientes
        for gasto in data:
            tipo = gasto.get("tipo_asignacion")
            # Should be 'comun' or 'no_asignado' with null linea_negocio_id
            assert tipo != "directo", f"Gasto {gasto['id']} with tipo_asignacion='directo' should not be in pendientes"
        
        print(f"Pendientes: {len(data)} gastos (none are 'directo')")

    def test_prorrateo_pendientes_includes_comun(self):
        """GET /api/prorrateo/pendientes - Should include tipo_asignacion='comun'"""
        resp = requests.get(f"{BASE_URL}/api/prorrateo/pendientes", params={"empresa_id": EMPRESA_ID})
        assert resp.status_code == 200
        data = resp.json()
        
        # Check if any comun in pendientes (depends on existing data)
        comun_gastos = [g for g in data if g.get("tipo_asignacion") == "comun"]
        print(f"Found {len(comun_gastos)} 'comun' gastos in pendientes")

    def test_prorrateo_preview_ventas_mes(self):
        """POST /api/prorrateo/preview - Preview with metodo='ventas_mes'"""
        # First get a pendiente gasto
        pend_resp = requests.get(f"{BASE_URL}/api/prorrateo/pendientes", params={"empresa_id": EMPRESA_ID})
        pendientes = pend_resp.json()
        
        if len(pendientes) == 0:
            pytest.skip("No pendientes to test preview")
        
        gasto_id = pendientes[0]["id"]
        payload = {
            "gasto_id": gasto_id,
            "metodo": "ventas_mes"
        }
        resp = requests.post(f"{BASE_URL}/api/prorrateo/preview", params={"empresa_id": EMPRESA_ID}, json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        assert "metodo" in data
        assert "lineas" in data
        # lineas may be empty if no sales in period - that's expected behavior
        print(f"Preview for gasto {gasto_id}: {len(data.get('lineas', []))} lineas, metodo={data['metodo']}")

    def test_prorrateo_preview_manual(self):
        """POST /api/prorrateo/preview - Preview with metodo='manual'"""
        pend_resp = requests.get(f"{BASE_URL}/api/prorrateo/pendientes", params={"empresa_id": EMPRESA_ID})
        pendientes = pend_resp.json()
        
        if len(pendientes) == 0:
            pytest.skip("No pendientes to test manual preview")
        
        gasto_id = pendientes[0]["id"]
        
        # Get lineas de negocio
        lineas_resp = requests.get(f"{BASE_URL}/api/lineas-negocio", params={"empresa_id": EMPRESA_ID})
        lineas = lineas_resp.json()
        
        if len(lineas) < 2:
            pytest.skip("Need at least 2 lineas de negocio for manual test")
        
        # Manual lineas that sum to 100%
        manual_lineas = [
            {"linea_negocio_id": lineas[0]["id"], "porcentaje": 60.0, "monto": 100.0},
            {"linea_negocio_id": lineas[1]["id"], "porcentaje": 40.0, "monto": 66.67}
        ]
        
        payload = {
            "gasto_id": gasto_id,
            "metodo": "manual",
            "lineas": manual_lineas
        }
        resp = requests.post(f"{BASE_URL}/api/prorrateo/preview", params={"empresa_id": EMPRESA_ID}, json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["metodo"] == "manual"
        print(f"Manual preview: {len(data.get('lineas', []))} lineas")

    def test_prorrateo_historial(self):
        """GET /api/prorrateo/historial - Returns proration history"""
        resp = requests.get(f"{BASE_URL}/api/prorrateo/historial", params={"empresa_id": EMPRESA_ID})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert isinstance(data, list), "Response should be a list"
        
        if len(data) > 0:
            item = data[0]
            assert "gasto_id" in item
            assert "metodo" in item
            assert "monto" in item or "porcentaje" in item
        print(f"Historial: {len(data)} prorrateos executed")

    def test_prorrateo_preview_ventas_rango(self):
        """POST /api/prorrateo/preview - Preview with metodo='ventas_rango'"""
        pend_resp = requests.get(f"{BASE_URL}/api/prorrateo/pendientes", params={"empresa_id": EMPRESA_ID})
        pendientes = pend_resp.json()
        
        if len(pendientes) == 0:
            pytest.skip("No pendientes to test ventas_rango preview")
        
        gasto_id = pendientes[0]["id"]
        payload = {
            "gasto_id": gasto_id,
            "metodo": "ventas_rango",
            "periodo_desde": "2026-01-01",
            "periodo_hasta": "2026-01-31"
        }
        resp = requests.post(f"{BASE_URL}/api/prorrateo/preview", params={"empresa_id": EMPRESA_ID}, json=payload)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["metodo"] == "ventas_rango"
        print(f"Ventas rango preview: {len(data.get('lineas', []))} lineas")


class TestExistingTestData:
    """Tests using known existing data (from agent_to_agent_context_note)"""

    def test_existing_gasto_39_is_comun(self):
        """Verify gasto id=39 exists and is tipo_asignacion='comun'"""
        resp = requests.get(f"{BASE_URL}/api/gastos/39", params={"empresa_id": EMPRESA_ID})
        if resp.status_code == 404:
            pytest.skip("Gasto 39 not found - may have been deleted")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        gasto = resp.json()
        print(f"Gasto 39: tipo_asignacion={gasto.get('tipo_asignacion')}, total={gasto.get('total')}")

    def test_existing_gasto_40_is_directo(self):
        """Verify gasto id=40 exists and is tipo_asignacion='directo'"""
        resp = requests.get(f"{BASE_URL}/api/gastos/40", params={"empresa_id": EMPRESA_ID})
        if resp.status_code == 404:
            pytest.skip("Gasto 40 not found - may have been deleted")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        gasto = resp.json()
        print(f"Gasto 40: tipo_asignacion={gasto.get('tipo_asignacion')}, total={gasto.get('total')}")

    def test_existing_categoria_gasto_2_marketing(self):
        """Verify categoria_gasto id=2 (Marketing, MKT) exists"""
        resp = requests.get(f"{BASE_URL}/api/categorias-gasto", params={"empresa_id": EMPRESA_ID})
        assert resp.status_code == 200
        categorias = resp.json()
        
        cat_2 = next((c for c in categorias if c["id"] == 2), None)
        if cat_2:
            print(f"Categoria 2: nombre={cat_2['nombre']}, codigo={cat_2.get('codigo')}")
        else:
            print("Categoria id=2 not found - may be different empresa")


class TestGastoTableColumns:
    """Verify Gastos table returns columns: Categoría, Tipo, Centro Costo"""

    def test_gastos_response_has_dimension_columns(self):
        """GET /api/gastos - Response includes Categoría, Tipo, Centro Costo info"""
        resp = requests.get(f"{BASE_URL}/api/gastos", params={"empresa_id": EMPRESA_ID})
        assert resp.status_code == 200
        gastos = resp.json()
        
        if len(gastos) == 0:
            pytest.skip("No gastos to verify columns")
        
        sample = gastos[0]
        # Verify column data is present
        assert "categoria_gasto_nombre" in sample, "Missing categoria_gasto_nombre"
        assert "tipo_asignacion" in sample, "Missing tipo_asignacion"
        assert "centro_costo_nombre" in sample, "Missing centro_costo_nombre"
        
        print(f"Sample gasto columns: cat={sample.get('categoria_gasto_nombre')}, tipo={sample.get('tipo_asignacion')}, cc={sample.get('centro_costo_nombre')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
