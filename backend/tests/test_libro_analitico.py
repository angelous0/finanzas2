"""
Test suite for Libro Analítico feature
Tests the /api/libro-analitico endpoint for different dimensions:
- linea_negocio
- marca
- centro_costo
- categoria
Also tests the CSV export endpoint /api/libro-analitico/export
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
EMPRESA_ID = "7"  # Test company

class TestLibroAnaliticoLineasNegocio:
    """Test Libro Analítico for Linea de Negocio dimension"""
    
    def test_linea_negocio_18_returns_movements(self):
        """Test GET /api/libro-analitico with dimension=linea_negocio&dimension_id=18 returns correct data"""
        response = requests.get(
            f"{BASE_URL}/api/libro-analitico",
            params={
                "dimension": "linea_negocio",
                "dimension_id": 18,
                "fecha_desde": "2020-01-01",
                "fecha_hasta": "2026-12-31"
            },
            headers={"X-Empresa-Id": EMPRESA_ID}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Validate response structure
        assert "dimension" in data
        assert "dimension_id" in data
        assert "dimension_nombre" in data
        assert "fecha_desde" in data
        assert "fecha_hasta" in data
        assert "total_entradas" in data
        assert "total_salidas" in data
        assert "saldo_final" in data
        assert "movimientos" in data
        
        # Validate dimension info
        assert data["dimension"] == "linea_negocio"
        assert data["dimension_id"] == 18
        assert data["dimension_nombre"] == "Element Premium - Pantalon Denim"
        
        # Validate totals (based on known test data)
        assert data["total_entradas"] == 200.0, f"Expected 200.0 entradas, got {data['total_entradas']}"
        assert data["total_salidas"] == 3000.0, f"Expected 3000.0 salidas, got {data['total_salidas']}"
        assert data["saldo_final"] == -2800.0, f"Expected -2800.0 saldo, got {data['saldo_final']}"
        
        # Validate movements count - should have 3 movements
        assert len(data["movimientos"]) == 3, f"Expected 3 movements, got {len(data['movimientos'])}"

    def test_linea_negocio_18_movements_structure(self):
        """Test that each movement has correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/libro-analitico",
            params={
                "dimension": "linea_negocio",
                "dimension_id": 18,
                "fecha_desde": "2020-01-01",
                "fecha_hasta": "2026-12-31"
            },
            headers={"X-Empresa-Id": EMPRESA_ID}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        for m in data["movimientos"]:
            # Each movement should have these fields
            assert "fecha" in m
            assert "tipo" in m
            assert "descripcion" in m
            assert "entrada" in m
            assert "salida" in m
            assert "saldo" in m
            assert "ref_tipo" in m
            assert "ref_id" in m
        
        # Verify specific movement types
        tipos = [m["tipo"] for m in data["movimientos"]]
        assert "Venta POS" in tipos
        assert "Pago Letra" in tipos
        assert "Cobranza CxC" in tipos

    def test_linea_negocio_20_confeccion(self):
        """Test GET /api/libro-analitico for Confeccion line"""
        response = requests.get(
            f"{BASE_URL}/api/libro-analitico",
            params={
                "dimension": "linea_negocio",
                "dimension_id": 20,
                "fecha_desde": "2020-01-01",
                "fecha_hasta": "2026-12-31"
            },
            headers={"X-Empresa-Id": EMPRESA_ID}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["dimension_nombre"] == "Confeccion"
        # Confeccion should have data as well
        assert isinstance(data["movimientos"], list)


class TestLibroAnaliticoMarca:
    """Test Libro Analítico for Marca dimension"""
    
    def test_marca_dimension(self):
        """Test GET /api/libro-analitico with dimension=marca"""
        # First get available marcas
        marcas_response = requests.get(
            f"{BASE_URL}/api/marcas",
            headers={"X-Empresa-Id": EMPRESA_ID}
        )
        
        if marcas_response.status_code == 200:
            marcas = marcas_response.json()
            if len(marcas) > 0:
                marca_id = marcas[0]["id"]
                
                response = requests.get(
                    f"{BASE_URL}/api/libro-analitico",
                    params={
                        "dimension": "marca",
                        "dimension_id": marca_id,
                        "fecha_desde": "2020-01-01",
                        "fecha_hasta": "2026-12-31"
                    },
                    headers={"X-Empresa-Id": EMPRESA_ID}
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["dimension"] == "marca"
                assert isinstance(data["movimientos"], list)
            else:
                pytest.skip("No marcas found for testing")
        else:
            pytest.skip("Could not get marcas list")


class TestLibroAnaliticoExport:
    """Test CSV export functionality"""
    
    def test_export_csv_returns_csv_file(self):
        """Test GET /api/libro-analitico/export returns valid CSV"""
        response = requests.get(
            f"{BASE_URL}/api/libro-analitico/export",
            params={
                "dimension": "linea_negocio",
                "dimension_id": 18,
                "fecha_desde": "2020-01-01",
                "fecha_hasta": "2026-12-31"
            },
            headers={"X-Empresa-Id": EMPRESA_ID}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        # Check content type
        content_type = response.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got {content_type}"
        
        # Check Content-Disposition header for filename
        content_disp = response.headers.get("content-disposition", "")
        assert "attachment" in content_disp
        assert "libro_analitico" in content_disp
        
        # Validate CSV content
        csv_content = response.text
        assert "Libro Analítico" in csv_content
        assert "Element Premium" in csv_content
        assert "Fecha,Tipo,Descripción" in csv_content
        assert "TOTALES" in csv_content

    def test_export_csv_has_correct_data(self):
        """Test that CSV export contains the same data as JSON endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/libro-analitico/export",
            params={
                "dimension": "linea_negocio",
                "dimension_id": 18,
                "fecha_desde": "2020-01-01",
                "fecha_hasta": "2026-12-31"
            },
            headers={"X-Empresa-Id": EMPRESA_ID}
        )
        
        assert response.status_code == 200
        csv_content = response.text
        
        # Check for known data values
        assert "Venta POS-146662" in csv_content
        assert "Pago Letra" in csv_content
        assert "Cobranza #133" in csv_content
        assert "200.00" in csv_content  # Total entradas
        assert "3000.00" in csv_content  # Total salidas


class TestLibroAnaliticoValidation:
    """Test input validation and error handling"""
    
    def test_missing_dimension_param(self):
        """Test that missing dimension parameter returns error"""
        response = requests.get(
            f"{BASE_URL}/api/libro-analitico",
            params={
                "dimension_id": 18
            },
            headers={"X-Empresa-Id": EMPRESA_ID}
        )
        
        # Should return 422 for missing required parameter
        assert response.status_code == 422

    def test_missing_dimension_id_param(self):
        """Test that missing dimension_id parameter returns error"""
        response = requests.get(
            f"{BASE_URL}/api/libro-analitico",
            params={
                "dimension": "linea_negocio"
            },
            headers={"X-Empresa-Id": EMPRESA_ID}
        )
        
        # Should return 422 for missing required parameter
        assert response.status_code == 422

    def test_invalid_dimension_id(self):
        """Test with non-existent dimension_id returns empty results"""
        response = requests.get(
            f"{BASE_URL}/api/libro-analitico",
            params={
                "dimension": "linea_negocio",
                "dimension_id": 99999
            },
            headers={"X-Empresa-Id": EMPRESA_ID}
        )
        
        assert response.status_code == 200
        data = response.json()
        # Should return empty movimientos
        assert len(data["movimientos"]) == 0


class TestLineasNegocioEndpoint:
    """Test lineas-negocio endpoint for dropdown options"""
    
    def test_get_lineas_negocio(self):
        """Test GET /api/lineas-negocio returns list"""
        response = requests.get(
            f"{BASE_URL}/api/lineas-negocio",
            headers={"X-Empresa-Id": EMPRESA_ID}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Check for known lineas
        nombres = [ln["nombre"] for ln in data]
        assert "Element Premium - Pantalon Denim" in nombres
        assert "Confeccion" in nombres


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
