"""
Test suite for Planilla (Payroll) module
Tests CRUD operations for planillas with detail lines, workers list, and summary endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
EMPRESA_ID = 7  # Test empresa_id as per requirements


class TestPlanillaEndpoints:
    """Test all Planilla API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.created_planilla_id = None
        yield
        # Cleanup: delete test planilla if created
        if self.created_planilla_id:
            try:
                self.session.delete(
                    f"{BASE_URL}/api/planillas/{self.created_planilla_id}",
                    params={"empresa_id": EMPRESA_ID}
                )
            except:
                pass

    # ── GET /api/planillas/trabajadores/list ──
    def test_get_trabajadores_list(self):
        """Test GET /api/planillas/trabajadores/list returns workers from produccion.prod_personas_produccion"""
        response = self.session.get(
            f"{BASE_URL}/api/planillas/trabajadores/list",
            params={"empresa_id": EMPRESA_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # If workers exist, validate structure
        if len(data) > 0:
            worker = data[0]
            assert "id" in worker, "Worker should have id"
            assert "nombre" in worker, "Worker should have nombre"
            print(f"✓ Found {len(data)} workers")
            print(f"  Sample worker: {worker.get('nombre')} ({worker.get('tipo_persona', 'N/A')})")
        else:
            print("⚠ No workers found in produccion.prod_personas_produccion")

    # ── GET /api/planillas/resumen/totales ──
    def test_get_resumen_totales(self):
        """Test GET /api/planillas/resumen/totales returns summary by unidad and linea"""
        response = self.session.get(
            f"{BASE_URL}/api/planillas/resumen/totales",
            params={"empresa_id": EMPRESA_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "totales" in data, "Response should have 'totales'"
        assert "por_unidad_interna" in data, "Response should have 'por_unidad_interna'"
        assert "por_linea_negocio" in data, "Response should have 'por_linea_negocio'"
        
        totales = data["totales"]
        assert "num_planillas" in totales, "totales should have num_planillas"
        assert "total_bruto" in totales, "totales should have total_bruto"
        assert "total_neto" in totales, "totales should have total_neto"
        
        print(f"✓ Resumen totales: {totales.get('num_planillas')} planillas, Total Neto: {totales.get('total_neto')}")

    # ── GET /api/planillas ──
    def test_list_planillas(self):
        """Test GET /api/planillas returns list of planillas with detail lines"""
        response = self.session.get(
            f"{BASE_URL}/api/planillas",
            params={"empresa_id": EMPRESA_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # If planillas exist, validate structure
        if len(data) > 0:
            planilla = data[0]
            assert "id" in planilla, "Planilla should have id"
            assert "periodo" in planilla, "Planilla should have periodo"
            assert "lineas" in planilla, "Planilla should have lineas (detail lines)"
            assert isinstance(planilla["lineas"], list), "lineas should be a list"
            print(f"✓ Found {len(data)} planillas")
            print(f"  First planilla: {planilla.get('periodo')} with {len(planilla.get('lineas', []))} lines")
        else:
            print("⚠ No planillas found")

    # ── POST /api/planillas ──
    def test_create_planilla(self):
        """Test POST /api/planillas creates planilla with detail lines"""
        # First get workers to use in the planilla
        workers_response = self.session.get(
            f"{BASE_URL}/api/planillas/trabajadores/list",
            params={"empresa_id": EMPRESA_ID}
        )
        workers = workers_response.json() if workers_response.status_code == 200 else []
        
        # Build detail lines
        lineas = []
        if len(workers) > 0:
            worker = workers[0]
            lineas.append({
                "trabajador_id": worker.get("id"),
                "trabajador_nombre": worker.get("nombre"),
                "tipo_trabajador": worker.get("tipo_persona", ""),
                "unidad_interna_id": worker.get("unidad_interna_id"),
                "linea_negocio_id": None,  # Prorated
                "salario_base": 1500.00,
                "bonificaciones": 200.00,
                "adelantos": 100.00,
                "otros_descuentos": 50.00,
                "neto_pagar": 1550.00,  # 1500 + 200 - 100 - 50
                "notas": "Test line"
            })
        
        payload = {
            "periodo": "TEST-2026-Q1",
            "tipo": "quincenal",
            "fecha_inicio": "2026-01-01",
            "fecha_fin": "2026-01-15",
            "fecha_pago": "2026-01-16",
            "notas": "Test planilla created by pytest",
            "lineas": lineas
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/planillas",
            params={"empresa_id": EMPRESA_ID},
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data, "Created planilla should have id"
        assert data["periodo"] == "TEST-2026-Q1", "Periodo should match"
        assert data["tipo"] == "quincenal", "Tipo should match"
        assert "lineas" in data, "Response should include lineas"
        
        self.created_planilla_id = data["id"]
        print(f"✓ Created planilla ID: {self.created_planilla_id}")
        print(f"  Periodo: {data.get('periodo')}, Total Neto: {data.get('total_neto')}")
        
        # Verify with GET
        get_response = self.session.get(
            f"{BASE_URL}/api/planillas/{self.created_planilla_id}",
            params={"empresa_id": EMPRESA_ID}
        )
        assert get_response.status_code == 200, "Should be able to GET created planilla"
        fetched = get_response.json()
        assert fetched["periodo"] == "TEST-2026-Q1", "Fetched periodo should match"

    # ── PUT /api/planillas/{id} ──
    def test_update_planilla(self):
        """Test PUT /api/planillas/{id} updates planilla header and lines"""
        # First create a planilla
        create_payload = {
            "periodo": "TEST-UPDATE-2026",
            "tipo": "mensual",
            "fecha_inicio": "2026-02-01",
            "fecha_fin": "2026-02-28",
            "notas": "To be updated",
            "lineas": [{
                "trabajador_id": None,
                "trabajador_nombre": "Test Worker",
                "tipo_trabajador": "operario",
                "unidad_interna_id": 1,
                "linea_negocio_id": None,
                "salario_base": 1000.00,
                "bonificaciones": 0,
                "adelantos": 0,
                "otros_descuentos": 0,
                "neto_pagar": 1000.00,
                "notas": ""
            }]
        }
        
        create_response = self.session.post(
            f"{BASE_URL}/api/planillas",
            params={"empresa_id": EMPRESA_ID},
            json=create_payload
        )
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        created = create_response.json()
        planilla_id = created["id"]
        self.created_planilla_id = planilla_id
        
        # Update the planilla
        update_payload = {
            "periodo": "TEST-UPD-2026",  # Keep under 20 chars (varchar(20) limit)
            "notas": "Updated notes",
            "lineas": [{
                "trabajador_id": None,
                "trabajador_nombre": "Updated Worker",
                "tipo_trabajador": "operario",
                "unidad_interna_id": 2,
                "linea_negocio_id": 26,  # LN-PD
                "salario_base": 2000.00,
                "bonificaciones": 300.00,
                "adelantos": 200.00,
                "otros_descuentos": 100.00,
                "neto_pagar": 2000.00,
                "notas": "Updated line"
            }]
        }
        
        update_response = self.session.put(
            f"{BASE_URL}/api/planillas/{planilla_id}",
            params={"empresa_id": EMPRESA_ID},
            json=update_payload
        )
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        updated = update_response.json()
        assert updated["periodo"] == "TEST-UPD-2026", "Periodo should be updated"
        assert updated["notas"] == "Updated notes", "Notas should be updated"
        
        # Verify lines were replaced
        assert len(updated["lineas"]) == 1, "Should have 1 line"
        assert updated["lineas"][0]["trabajador_nombre"] == "Updated Worker", "Worker name should be updated"
        assert updated["lineas"][0]["linea_negocio_id"] == 26, "Linea negocio should be set"
        
        print(f"✓ Updated planilla ID: {planilla_id}")
        print(f"  New periodo: {updated.get('periodo')}, Total Neto: {updated.get('total_neto')}")

    # ── DELETE /api/planillas/{id} ──
    def test_delete_planilla(self):
        """Test DELETE /api/planillas/{id} deletes planilla"""
        # First create a planilla to delete
        create_payload = {
            "periodo": "TEST-DELETE-2026",
            "tipo": "semanal",
            "fecha_inicio": "2026-03-01",
            "fecha_fin": "2026-03-07",
            "notas": "To be deleted",
            "lineas": [{
                "trabajador_id": None,
                "trabajador_nombre": "Delete Test Worker",
                "tipo_trabajador": "operario",
                "unidad_interna_id": 1,
                "linea_negocio_id": None,
                "salario_base": 500.00,
                "bonificaciones": 0,
                "adelantos": 0,
                "otros_descuentos": 0,
                "neto_pagar": 500.00,
                "notas": ""
            }]
        }
        
        create_response = self.session.post(
            f"{BASE_URL}/api/planillas",
            params={"empresa_id": EMPRESA_ID},
            json=create_payload
        )
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        created = create_response.json()
        planilla_id = created["id"]
        
        # Delete the planilla
        delete_response = self.session.delete(
            f"{BASE_URL}/api/planillas/{planilla_id}",
            params={"empresa_id": EMPRESA_ID}
        )
        assert delete_response.status_code == 200, f"Delete failed: {delete_response.text}"
        
        data = delete_response.json()
        assert data.get("ok") == True, "Delete should return ok: true"
        
        # Verify it's deleted
        get_response = self.session.get(
            f"{BASE_URL}/api/planillas/{planilla_id}",
            params={"empresa_id": EMPRESA_ID}
        )
        assert get_response.status_code == 404, "Deleted planilla should return 404"
        
        print(f"✓ Deleted planilla ID: {planilla_id}")
        # Clear the created_planilla_id since we already deleted it
        self.created_planilla_id = None

    # ── GET /api/planillas/{id} ──
    def test_get_planilla_by_id(self):
        """Test GET /api/planillas/{id} returns single planilla with lines"""
        # First get list to find an existing planilla
        list_response = self.session.get(
            f"{BASE_URL}/api/planillas",
            params={"empresa_id": EMPRESA_ID}
        )
        planillas = list_response.json() if list_response.status_code == 200 else []
        
        if len(planillas) == 0:
            # Create one for testing
            create_payload = {
                "periodo": "TEST-GET-2026",
                "tipo": "quincenal",
                "fecha_inicio": "2026-04-01",
                "fecha_fin": "2026-04-15",
                "notas": "Test get by id",
                "lineas": [{
                    "trabajador_id": None,
                    "trabajador_nombre": "Get Test Worker",
                    "tipo_trabajador": "operario",
                    "unidad_interna_id": 1,
                    "linea_negocio_id": None,
                    "salario_base": 800.00,
                    "bonificaciones": 0,
                    "adelantos": 0,
                    "otros_descuentos": 0,
                    "neto_pagar": 800.00,
                    "notas": ""
                }]
            }
            create_response = self.session.post(
                f"{BASE_URL}/api/planillas",
                params={"empresa_id": EMPRESA_ID},
                json=create_payload
            )
            assert create_response.status_code == 200
            planilla_id = create_response.json()["id"]
            self.created_planilla_id = planilla_id
        else:
            planilla_id = planillas[0]["id"]
        
        # Get by ID
        response = self.session.get(
            f"{BASE_URL}/api/planillas/{planilla_id}",
            params={"empresa_id": EMPRESA_ID}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["id"] == planilla_id, "ID should match"
        assert "periodo" in data, "Should have periodo"
        assert "lineas" in data, "Should have lineas"
        assert isinstance(data["lineas"], list), "lineas should be a list"
        
        # Check lineas have joined names
        if len(data["lineas"]) > 0:
            line = data["lineas"][0]
            # These fields come from JOIN
            assert "unidad_interna_nombre" in line or line.get("unidad_interna_id") is None, "Should have unidad_interna_nombre if unidad_interna_id set"
            assert "linea_negocio_nombre" in line or line.get("linea_negocio_id") is None, "Should have linea_negocio_nombre if linea_negocio_id set"
        
        print(f"✓ Got planilla ID: {planilla_id}")
        print(f"  Periodo: {data.get('periodo')}, Lines: {len(data.get('lineas', []))}")

    # ── Test 404 for non-existent planilla ──
    def test_get_nonexistent_planilla_returns_404(self):
        """Test GET /api/planillas/{id} returns 404 for non-existent ID"""
        response = self.session.get(
            f"{BASE_URL}/api/planillas/999999",
            params={"empresa_id": EMPRESA_ID}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Non-existent planilla returns 404")

    # ── Test filters on list ──
    def test_list_planillas_with_filters(self):
        """Test GET /api/planillas with tipo and estado filters"""
        # Test tipo filter
        response = self.session.get(
            f"{BASE_URL}/api/planillas",
            params={"empresa_id": EMPRESA_ID, "tipo": "quincenal"}
        )
        assert response.status_code == 200, f"Filter by tipo failed: {response.text}"
        
        # Test estado filter
        response = self.session.get(
            f"{BASE_URL}/api/planillas",
            params={"empresa_id": EMPRESA_ID, "estado": "borrador"}
        )
        assert response.status_code == 200, f"Filter by estado failed: {response.text}"
        
        print("✓ List planillas with filters works")

    # ── Test resumen with date filters ──
    def test_resumen_with_date_filters(self):
        """Test GET /api/planillas/resumen/totales with fecha_desde and fecha_hasta"""
        response = self.session.get(
            f"{BASE_URL}/api/planillas/resumen/totales",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2026-01-01",
                "fecha_hasta": "2026-12-31"
            }
        )
        assert response.status_code == 200, f"Resumen with dates failed: {response.text}"
        
        data = response.json()
        assert "totales" in data
        assert "por_unidad_interna" in data
        assert "por_linea_negocio" in data
        
        print("✓ Resumen with date filters works")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
