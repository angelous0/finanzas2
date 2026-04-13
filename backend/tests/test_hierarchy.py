"""
Test category hierarchy features - Backend API Tests
Tests for:
1. GET /api/categorias?tipo=egreso returns nombre_completo field
2. nombre_completo shows hierarchy like 'Padre > Hijo'
3. Gastos with sub-categories show hierarchy in detail view
4. Factura lines with sub-categories show hierarchy
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCategoryHierarchy:
    """Test category hierarchy in API"""
    
    def test_categorias_returns_nombre_completo(self):
        """Test that /api/categorias returns nombre_completo field"""
        response = requests.get(f"{BASE_URL}/api/categorias?tipo=egreso")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) > 0, "Should have categories"
        
        # All categories should have nombre_completo
        for cat in data:
            assert "nombre_completo" in cat, f"Category {cat.get('id')} missing nombre_completo"
            assert cat["nombre_completo"], f"Category {cat.get('id')} has empty nombre_completo"
        
        print(f"✓ All {len(data)} categories have nombre_completo field")
    
    def test_nombre_completo_shows_hierarchy(self):
        """Test that nombre_completo shows 'Padre > Hijo' format for sub-categories"""
        response = requests.get(f"{BASE_URL}/api/categorias?tipo=egreso")
        assert response.status_code == 200
        
        data = response.json()
        
        # Find categories with padre_id
        sub_categories = [c for c in data if c.get("padre_id")]
        assert len(sub_categories) > 0, "Should have sub-categories with padre_id"
        
        # All sub-categories should have " > " in nombre_completo
        for cat in sub_categories:
            assert " > " in cat["nombre_completo"], f"Sub-category {cat.get('id')} should have ' > ' in nombre_completo: {cat['nombre_completo']}"
        
        # Parent-only categories should NOT have " > "
        parent_categories = [c for c in data if not c.get("padre_id")]
        for cat in parent_categories:
            assert " > " not in cat["nombre_completo"], f"Parent category {cat.get('id')} should not have ' > ' in nombre_completo"
        
        print(f"✓ Found {len(sub_categories)} sub-categories with hierarchy format")
        print(f"✓ Found {len(parent_categories)} parent categories without hierarchy")
        print(f"Sample hierarchy: {sub_categories[0]['nombre_completo']}")
    
    def test_gasto_with_subcategory_returns_padre_nombre(self):
        """Test creating a gasto with sub-category returns categoria_padre_nombre"""
        # First get a sub-category (one with padre_id)
        cat_response = requests.get(f"{BASE_URL}/api/categorias?tipo=egreso")
        assert cat_response.status_code == 200
        
        categories = cat_response.json()
        sub_cat = next((c for c in categories if c.get("padre_id")), None)
        if not sub_cat:
            pytest.skip("No sub-categories available for testing")
        
        print(f"Using sub-category: {sub_cat['nombre_completo']} (ID: {sub_cat['id']})")
        
        # Get a cuenta financiera for payment
        cuentas_response = requests.get(f"{BASE_URL}/api/cuentas-financieras")
        assert cuentas_response.status_code == 200
        cuentas = cuentas_response.json()
        assert len(cuentas) > 0, "Need at least one cuenta financiera"
        cuenta_id = cuentas[0]["id"]
        
        # Create a gasto with this sub-category
        gasto_data = {
            "fecha": "2026-02-09",
            "moneda_id": 1,
            "tipo_documento": "recibo",
            "numero_documento": "TEST-HIERARCHY-001",
            "beneficiario_nombre": "TEST Hierarchy Test",
            "lineas": [
                {
                    "categoria_id": sub_cat["id"],
                    "descripcion": "Testing hierarchy display",
                    "importe": 100.00,
                    "igv_aplica": True
                }
            ],
            "pagos": [
                {
                    "cuenta_financiera_id": cuenta_id,
                    "medio": "efectivo",
                    "monto": 118.00
                }
            ]
        }
        
        gasto_response = requests.post(f"{BASE_URL}/api/gastos", json=gasto_data)
        assert gasto_response.status_code in [200, 201], f"Failed to create gasto: {gasto_response.text}"
        
        created_gasto = gasto_response.json()
        print(f"Created gasto: {created_gasto.get('numero')}")
        
        # Fetch the gasto to check lineas data
        get_response = requests.get(f"{BASE_URL}/api/gastos/{created_gasto['id']}")
        assert get_response.status_code == 200
        
        gasto = get_response.json()
        assert "lineas" in gasto and len(gasto["lineas"]) > 0, "Gasto should have lineas"
        
        linea = gasto["lineas"][0]
        assert "categoria_padre_nombre" in linea, "Linea should have categoria_padre_nombre field"
        
        # The sub-category should have a parent name
        assert linea.get("categoria_padre_nombre"), f"Linea should have categoria_padre_nombre value for sub-category"
        print(f"✓ Gasto linea has categoria_padre_nombre: {linea.get('categoria_padre_nombre')}")
        print(f"✓ Full hierarchy: {linea.get('categoria_padre_nombre')} > {linea.get('categoria_nombre')}")
        
        # Clean up - delete the test gasto
        delete_response = requests.delete(f"{BASE_URL}/api/gastos/{created_gasto['id']}")
        assert delete_response.status_code == 200, f"Failed to delete test gasto"
        print(f"✓ Cleaned up test gasto")

    def test_factura_lines_with_subcategory(self):
        """Test that factura lines with sub-category return hierarchy info"""
        # First get a sub-category
        cat_response = requests.get(f"{BASE_URL}/api/categorias?tipo=egreso")
        assert cat_response.status_code == 200
        
        categories = cat_response.json()
        sub_cat = next((c for c in categories if c.get("padre_id")), None)
        if not sub_cat:
            pytest.skip("No sub-categories available for testing")
        
        # Get a proveedor
        prov_response = requests.get(f"{BASE_URL}/api/proveedores")
        assert prov_response.status_code == 200
        proveedores = prov_response.json()
        if not proveedores:
            pytest.skip("No proveedores available")
        
        proveedor_id = proveedores[0]["id"]
        
        # Create a factura with sub-category line
        factura_data = {
            "proveedor_id": proveedor_id,
            "moneda_id": 1,
            "fecha_factura": "2026-02-09",
            "terminos_dias": 30,
            "tipo_documento": "factura",
            "numero": "TEST-HIER-FP-001",
            "impuestos_incluidos": False,
            "lineas": [
                {
                    "categoria_id": sub_cat["id"],
                    "descripcion": "Testing factura hierarchy",
                    "importe": 200.00,
                    "igv_aplica": True
                }
            ]
        }
        
        factura_response = requests.post(f"{BASE_URL}/api/facturas-proveedor", json=factura_data)
        assert factura_response.status_code in [200, 201], f"Failed to create factura: {factura_response.text}"
        
        created_factura = factura_response.json()
        print(f"Created factura: {created_factura.get('numero')}")
        
        # Check the lineas
        assert "lineas" in created_factura and len(created_factura["lineas"]) > 0
        
        linea = created_factura["lineas"][0]
        assert "categoria_padre_nombre" in linea, "Linea should have categoria_padre_nombre field"
        
        if linea.get("categoria_padre_nombre"):
            print(f"✓ Factura linea has categoria_padre_nombre: {linea.get('categoria_padre_nombre')}")
            print(f"✓ Full hierarchy: {linea.get('categoria_padre_nombre')} > {linea.get('categoria_nombre')}")
        
        # Clean up
        delete_response = requests.delete(f"{BASE_URL}/api/facturas-proveedor/{created_factura['id']}")
        assert delete_response.status_code == 200
        print(f"✓ Cleaned up test factura")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
