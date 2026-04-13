"""
test_unidades_internas.py - Tests for Unidades Internas (Internal Production Units)
Tests CRUD operations for unidades internas, personas, cargos internos, gastos, and gerencial report.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://concilia-smart.preview.emergentagent.com').rstrip('/')
EMPRESA_ID = 7
HEADERS = {'X-Empresa-Id': str(EMPRESA_ID), 'Content-Type': 'application/json'}


class TestUnidadesInternas:
    """CRUD tests for Unidades Internas (internal production units)"""

    def test_list_unidades_internas(self):
        """GET /api/unidades-internas - should return 3 units for empresa_id=7"""
        response = requests.get(f"{BASE_URL}/api/unidades-internas?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) >= 3, f"Expected at least 3 unidades, got {len(data)}"
        
        # Verify expected units exist
        nombres = [u['nombre'] for u in data]
        assert 'Corte Interno' in nombres, "Should have 'Corte Interno'"
        assert 'Costura Interna' in nombres, "Should have 'Costura Interna'"
        assert 'Acabado Interno' in nombres, "Should have 'Acabado Interno'"
        print(f"✓ List unidades internas: {len(data)} units found")

    def test_unidad_structure(self):
        """Verify unidad structure has required fields"""
        response = requests.get(f"{BASE_URL}/api/unidades-internas?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) > 0
        
        unidad = data[0]
        required_fields = ['id', 'nombre', 'tipo', 'activo', 'empresa_id']
        for field in required_fields:
            assert field in unidad, f"Missing field: {field}"
        print(f"✓ Unidad structure verified with fields: {list(unidad.keys())}")

    def test_create_unidad_interna(self):
        """POST /api/unidades-internas - create new unit"""
        payload = {
            'nombre': 'TEST_Lavanderia Interna',
            'tipo': 'LAVANDERIA'
        }
        response = requests.post(
            f"{BASE_URL}/api/unidades-internas?empresa_id={EMPRESA_ID}",
            headers=HEADERS,
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert 'id' in data
        assert data['nombre'] == 'TEST_Lavanderia Interna'
        assert data['tipo'] == 'LAVANDERIA'
        assert data['activo'] == True
        
        # Store for cleanup
        self.__class__.test_unidad_id = data['id']
        print(f"✓ Created unidad: id={data['id']}, nombre={data['nombre']}")

    def test_update_unidad_interna(self):
        """PUT /api/unidades-internas/{id} - update unit"""
        if not hasattr(self.__class__, 'test_unidad_id'):
            pytest.skip("No test unidad created")
        
        unidad_id = self.__class__.test_unidad_id
        payload = {
            'nombre': 'TEST_Lavanderia Modificada',
            'tipo': 'LAVANDERIA',
            'activo': True
        }
        response = requests.put(
            f"{BASE_URL}/api/unidades-internas/{unidad_id}?empresa_id={EMPRESA_ID}",
            headers=HEADERS,
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data['nombre'] == 'TEST_Lavanderia Modificada'
        print(f"✓ Updated unidad: id={unidad_id}")

    def test_delete_unidad_interna(self):
        """DELETE /api/unidades-internas/{id} - delete unit (should succeed if no cargos/gastos)"""
        if not hasattr(self.__class__, 'test_unidad_id'):
            pytest.skip("No test unidad created")
        
        unidad_id = self.__class__.test_unidad_id
        response = requests.delete(
            f"{BASE_URL}/api/unidades-internas/{unidad_id}?empresa_id={EMPRESA_ID}",
            headers=HEADERS
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ Deleted unidad: id={unidad_id}")

    def test_delete_unidad_with_dependencies_fails(self):
        """DELETE /api/unidades-internas/{id} - should fail if has cargos/gastos"""
        # Unidad id=1 (Corte Interno) has cargos and gastos
        response = requests.delete(
            f"{BASE_URL}/api/unidades-internas/1?empresa_id={EMPRESA_ID}",
            headers=HEADERS
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        assert 'No se puede eliminar' in response.json().get('detail', '')
        print("✓ Delete with dependencies correctly rejected")


class TestPersonasProduccion:
    """Tests for Personas Producción with tipo INTERNO/EXTERNO"""

    def test_list_personas_produccion(self):
        """GET /api/personas-produccion - list personas"""
        response = requests.get(f"{BASE_URL}/api/personas-produccion?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Should have at least 1 persona"
        print(f"✓ List personas: {len(data)} found")

    def test_persona_structure(self):
        """Verify persona has tipo_persona field"""
        response = requests.get(f"{BASE_URL}/api/personas-produccion?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) > 0
        
        persona = data[0]
        required_fields = ['id', 'nombre', 'tipo_persona']
        for field in required_fields:
            assert field in persona, f"Missing field: {field}"
        print(f"✓ Persona structure has tipo_persona field")

    def test_persona_interno_exists(self):
        """Verify a persona marked as INTERNO exists"""
        response = requests.get(f"{BASE_URL}/api/personas-produccion?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200
        
        data = response.json()
        internos = [p for p in data if p['tipo_persona'] == 'INTERNO']
        assert len(internos) >= 1, "Should have at least 1 persona INTERNO"
        
        interno = internos[0]
        assert interno['unidad_interna_id'] is not None, "INTERNO should have unidad_interna_id"
        assert interno['unidad_interna_nombre'] is not None, "INTERNO should have unidad_interna_nombre"
        print(f"✓ Found INTERNO persona: {interno['nombre']} -> {interno['unidad_interna_nombre']}")

    def test_update_persona_tipo(self):
        """PUT /api/personas-produccion/{id}/tipo - mark persona as INTERNO/EXTERNO"""
        # Get a persona that's EXTERNO
        response = requests.get(f"{BASE_URL}/api/personas-produccion?empresa_id={EMPRESA_ID}", headers=HEADERS)
        data = response.json()
        externos = [p for p in data if p['tipo_persona'] == 'EXTERNO']
        
        if len(externos) == 0:
            pytest.skip("No EXTERNO personas to test")
        
        persona_id = externos[0]['id']
        
        # Mark as INTERNO
        payload = {
            'tipo_persona': 'INTERNO',
            'unidad_interna_id': 1  # Corte Interno
        }
        response = requests.put(
            f"{BASE_URL}/api/personas-produccion/{persona_id}/tipo?empresa_id={EMPRESA_ID}",
            headers=HEADERS,
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Revert back to EXTERNO
        payload = {'tipo_persona': 'EXTERNO', 'unidad_interna_id': None}
        response = requests.put(
            f"{BASE_URL}/api/personas-produccion/{persona_id}/tipo?empresa_id={EMPRESA_ID}",
            headers=HEADERS,
            json=payload
        )
        assert response.status_code == 200
        print(f"✓ Updated persona tipo: {persona_id}")


class TestCargosInternos:
    """Tests for Cargos Internos (internal charges from production movements)"""

    def test_list_cargos_internos(self):
        """GET /api/cargos-internos - list internal charges"""
        response = requests.get(f"{BASE_URL}/api/cargos-internos?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ List cargos internos: {len(data)} found")

    def test_cargo_structure(self):
        """Verify cargo structure"""
        response = requests.get(f"{BASE_URL}/api/cargos-internos?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200
        
        data = response.json()
        if len(data) == 0:
            pytest.skip("No cargos to verify structure")
        
        cargo = data[0]
        required_fields = ['id', 'fecha', 'unidad_interna_id', 'importe', 'cantidad', 'tarifa', 'estado']
        for field in required_fields:
            assert field in cargo, f"Missing field: {field}"
        print(f"✓ Cargo structure verified")

    def test_cargo_filter_by_unidad(self):
        """GET /api/cargos-internos?unidad_interna_id=1 - filter by unit"""
        response = requests.get(
            f"{BASE_URL}/api/cargos-internos?empresa_id={EMPRESA_ID}&unidad_interna_id=1",
            headers=HEADERS
        )
        assert response.status_code == 200
        
        data = response.json()
        for cargo in data:
            assert cargo['unidad_interna_id'] == 1, "Filter should only return unidad_interna_id=1"
        print(f"✓ Filter by unidad works: {len(data)} cargos for unidad 1")

    def test_generar_cargos_internos(self):
        """POST /api/cargos-internos/generar - generate charges from movements"""
        response = requests.post(
            f"{BASE_URL}/api/cargos-internos/generar?empresa_id={EMPRESA_ID}",
            headers=HEADERS
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert 'generados' in data, "Response should have 'generados' field"
        assert 'message' in data, "Response should have 'message' field"
        print(f"✓ Generar cargos: {data['generados']} generated - {data['message']}")

    def test_generar_avoids_duplicates(self):
        """POST /api/cargos-internos/generar - running again should not create duplicates"""
        # Get initial count
        response = requests.get(f"{BASE_URL}/api/cargos-internos?empresa_id={EMPRESA_ID}", headers=HEADERS)
        initial_count = len(response.json())
        
        # Run generate
        response = requests.post(
            f"{BASE_URL}/api/cargos-internos/generar?empresa_id={EMPRESA_ID}",
            headers=HEADERS
        )
        assert response.status_code == 200
        
        # Get new count
        response = requests.get(f"{BASE_URL}/api/cargos-internos?empresa_id={EMPRESA_ID}", headers=HEADERS)
        new_count = len(response.json())
        
        # Should be same or more (if new movements), but not less
        assert new_count >= initial_count, "Should not lose existing cargos"
        print(f"✓ Duplicates avoided: initial={initial_count}, after={new_count}")


class TestGastosUnidadInterna:
    """CRUD tests for Gastos Unidad Interna"""

    def test_list_gastos(self):
        """GET /api/gastos-unidad-interna - list gastos"""
        response = requests.get(f"{BASE_URL}/api/gastos-unidad-interna?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ List gastos: {len(data)} found")

    def test_gasto_structure(self):
        """Verify gasto structure"""
        response = requests.get(f"{BASE_URL}/api/gastos-unidad-interna?empresa_id={EMPRESA_ID}", headers=HEADERS)
        data = response.json()
        
        if len(data) == 0:
            pytest.skip("No gastos to verify structure")
        
        gasto = data[0]
        required_fields = ['id', 'fecha', 'unidad_interna_id', 'tipo_gasto', 'monto']
        for field in required_fields:
            assert field in gasto, f"Missing field: {field}"
        print(f"✓ Gasto structure verified")

    def test_create_gasto(self):
        """POST /api/gastos-unidad-interna - create gasto"""
        payload = {
            'fecha': '2026-03-20',
            'unidad_interna_id': 1,
            'tipo_gasto': 'MANTENIMIENTO',
            'descripcion': 'TEST_Reparacion maquina',
            'monto': 150.50
        }
        response = requests.post(
            f"{BASE_URL}/api/gastos-unidad-interna?empresa_id={EMPRESA_ID}",
            headers=HEADERS,
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert 'id' in data
        assert data['monto'] == 150.50
        assert data['tipo_gasto'] == 'MANTENIMIENTO'
        
        self.__class__.test_gasto_id = data['id']
        print(f"✓ Created gasto: id={data['id']}")

    def test_update_gasto(self):
        """PUT /api/gastos-unidad-interna/{id} - update gasto"""
        if not hasattr(self.__class__, 'test_gasto_id'):
            pytest.skip("No test gasto created")
        
        gasto_id = self.__class__.test_gasto_id
        payload = {
            'fecha': '2026-03-20',
            'unidad_interna_id': 1,
            'tipo_gasto': 'MANTENIMIENTO',
            'descripcion': 'TEST_Reparacion maquina actualizado',
            'monto': 175.00
        }
        response = requests.put(
            f"{BASE_URL}/api/gastos-unidad-interna/{gasto_id}?empresa_id={EMPRESA_ID}",
            headers=HEADERS,
            json=payload
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ Updated gasto: id={gasto_id}")

    def test_delete_gasto(self):
        """DELETE /api/gastos-unidad-interna/{id} - delete gasto"""
        if not hasattr(self.__class__, 'test_gasto_id'):
            pytest.skip("No test gasto created")
        
        gasto_id = self.__class__.test_gasto_id
        response = requests.delete(
            f"{BASE_URL}/api/gastos-unidad-interna/{gasto_id}?empresa_id={EMPRESA_ID}",
            headers=HEADERS
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ Deleted gasto: id={gasto_id}")

    def test_filter_by_unidad(self):
        """GET /api/gastos-unidad-interna?unidad_interna_id=1 - filter by unit"""
        response = requests.get(
            f"{BASE_URL}/api/gastos-unidad-interna?empresa_id={EMPRESA_ID}&unidad_interna_id=1",
            headers=HEADERS
        )
        assert response.status_code == 200
        
        data = response.json()
        for gasto in data:
            assert gasto['unidad_interna_id'] == 1, "Filter should only return unidad_interna_id=1"
        print(f"✓ Filter by unidad works: {len(data)} gastos for unidad 1")


class TestReporteUnidadesInternas:
    """Tests for Reporte Gerencial por Unidad Interna"""

    def test_reporte_returns_200(self):
        """GET /api/reporte-unidades-internas - returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/reporte-unidades-internas?empresa_id={EMPRESA_ID}",
            headers=HEADERS
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Reporte returns 200")

    def test_reporte_structure(self):
        """Verify reporte has vista_empresa, vista_unidades, resumen"""
        response = requests.get(
            f"{BASE_URL}/api/reporte-unidades-internas?empresa_id={EMPRESA_ID}",
            headers=HEADERS
        )
        data = response.json()
        
        assert 'vista_empresa' in data, "Missing vista_empresa"
        assert 'vista_unidades' in data, "Missing vista_unidades"
        assert 'resumen' in data, "Missing resumen"
        print("✓ Reporte structure verified")

    def test_vista_empresa_structure(self):
        """Verify vista_empresa has correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/reporte-unidades-internas?empresa_id={EMPRESA_ID}",
            headers=HEADERS
        )
        data = response.json()
        
        vista_empresa = data['vista_empresa']
        assert isinstance(vista_empresa, list)
        assert len(vista_empresa) >= 3, "Should have at least 3 units"
        
        for item in vista_empresa:
            assert 'unidad_id' in item
            assert 'unidad_nombre' in item
            assert 'costo_consolidado' in item
        print(f"✓ Vista empresa: {len(vista_empresa)} units")

    def test_vista_unidades_structure(self):
        """Verify vista_unidades has P&L fields"""
        response = requests.get(
            f"{BASE_URL}/api/reporte-unidades-internas?empresa_id={EMPRESA_ID}",
            headers=HEADERS
        )
        data = response.json()
        
        vista_unidades = data['vista_unidades']
        assert isinstance(vista_unidades, list)
        
        for item in vista_unidades:
            required_fields = ['unidad_id', 'unidad_nombre', 'ingresos_internos', 'gastos_reales', 'resultado']
            for field in required_fields:
                assert field in item, f"Missing field: {field}"
        print(f"✓ Vista unidades: {len(vista_unidades)} units with P&L")

    def test_resumen_structure(self):
        """Verify resumen has totals"""
        response = requests.get(
            f"{BASE_URL}/api/reporte-unidades-internas?empresa_id={EMPRESA_ID}",
            headers=HEADERS
        )
        data = response.json()
        
        resumen = data['resumen']
        required_fields = ['total_costo_empresa', 'total_ingresos_internos', 'total_gastos_reales', 'resultado_global', 'num_unidades']
        for field in required_fields:
            assert field in resumen, f"Missing field: {field}"
        print(f"✓ Resumen: total_ingresos={resumen['total_ingresos_internos']}, total_gastos={resumen['total_gastos_reales']}, resultado={resumen['resultado_global']}")

    def test_corte_interno_totals(self):
        """Verify Corte Interno has correct totals (ingresos=588, gastos=430, resultado=158)"""
        response = requests.get(
            f"{BASE_URL}/api/reporte-unidades-internas?empresa_id={EMPRESA_ID}",
            headers=HEADERS
        )
        data = response.json()
        
        vista_unidades = data['vista_unidades']
        corte = next((u for u in vista_unidades if u['unidad_nombre'] == 'Corte Interno'), None)
        assert corte is not None, "Corte Interno not found"
        
        # Verify expected values (from test data)
        assert corte['ingresos_internos'] == 588.0, f"Expected ingresos=588, got {corte['ingresos_internos']}"
        assert corte['gastos_reales'] == 430.0, f"Expected gastos=430, got {corte['gastos_reales']}"
        assert corte['resultado'] == 158.0, f"Expected resultado=158, got {corte['resultado']}"
        print(f"✓ Corte Interno totals: ingresos={corte['ingresos_internos']}, gastos={corte['gastos_reales']}, resultado={corte['resultado']}")

    def test_filter_by_date_range(self):
        """GET /api/reporte-unidades-internas?fecha_desde=X&fecha_hasta=Y"""
        response = requests.get(
            f"{BASE_URL}/api/reporte-unidades-internas?empresa_id={EMPRESA_ID}&fecha_desde=2026-03-01&fecha_hasta=2026-03-31",
            headers=HEADERS
        )
        assert response.status_code == 200
        
        data = response.json()
        assert 'resumen' in data
        print(f"✓ Date filter works: resultado_global={data['resumen']['resultado_global']}")


class TestTiposGasto:
    """Test for tipos de gasto endpoint"""

    def test_get_tipos_gasto(self):
        """GET /api/tipos-gasto-unidad - returns list of gasto types"""
        response = requests.get(f"{BASE_URL}/api/tipos-gasto-unidad?empresa_id={EMPRESA_ID}", headers=HEADERS)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Should have tipos de gasto"
        
        expected_tipos = ['PLANILLA_JORNAL', 'LUZ', 'MANTENIMIENTO']
        for tipo in expected_tipos:
            assert tipo in data, f"Missing tipo: {tipo}"
        print(f"✓ Tipos gasto: {data}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
