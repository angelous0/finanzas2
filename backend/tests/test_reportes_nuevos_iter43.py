"""
Test suite for 3 new financial reports (Iteration 43):
- Rentabilidad por Linea de Negocio
- CxP Aging (Accounts Payable Aging)
- CxC Aging (Accounts Receivable Aging)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
EMPRESA_ID = 7


class TestRentabilidadLinea:
    """Tests for GET /api/reportes/rentabilidad-linea endpoint"""
    
    def test_endpoint_returns_200(self):
        """Endpoint should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/reportes/rentabilidad-linea", params={"empresa_id": EMPRESA_ID})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Rentabilidad endpoint returns 200")
    
    def test_response_has_required_structure(self):
        """Response should have periodo, lineas, and totales"""
        response = requests.get(f"{BASE_URL}/api/reportes/rentabilidad-linea", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        assert "periodo" in data, "Missing 'periodo' in response"
        assert "lineas" in data, "Missing 'lineas' in response"
        assert "totales" in data, "Missing 'totales' in response"
        print("✓ Response has required structure (periodo, lineas, totales)")
    
    def test_periodo_has_desde_hasta(self):
        """Periodo should have desde and hasta dates"""
        response = requests.get(f"{BASE_URL}/api/reportes/rentabilidad-linea", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        assert "desde" in data["periodo"], "Missing 'desde' in periodo"
        assert "hasta" in data["periodo"], "Missing 'hasta' in periodo"
        print(f"✓ Periodo: {data['periodo']['desde']} - {data['periodo']['hasta']}")
    
    def test_lineas_is_array(self):
        """Lineas should be an array"""
        response = requests.get(f"{BASE_URL}/api/reportes/rentabilidad-linea", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        assert isinstance(data["lineas"], list), "lineas should be a list"
        print(f"✓ Lineas is array with {len(data['lineas'])} items")
    
    def test_linea_has_required_fields(self):
        """Each linea should have all required financial fields"""
        response = requests.get(f"{BASE_URL}/api/reportes/rentabilidad-linea", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        required_fields = ["linea_id", "linea_nombre", "ventas", "costo_mp", "costo_servicios", 
                          "costo_total", "margen_bruto", "pct_margen", "gastos", "utilidad"]
        
        if data["lineas"]:
            linea = data["lineas"][0]
            for field in required_fields:
                assert field in linea, f"Missing '{field}' in linea"
            print(f"✓ Linea has all required fields: {required_fields}")
    
    def test_totales_has_required_fields(self):
        """Totales should have ventas, costo_total, margen_bruto, pct_margen, gastos, utilidad"""
        response = requests.get(f"{BASE_URL}/api/reportes/rentabilidad-linea", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        required_fields = ["ventas", "costo_total", "margen_bruto", "pct_margen", "gastos", "utilidad"]
        for field in required_fields:
            assert field in data["totales"], f"Missing '{field}' in totales"
        print(f"✓ Totales has all required fields")
    
    def test_accepts_date_parameters(self):
        """Endpoint should accept fecha_desde and fecha_hasta parameters"""
        response = requests.get(f"{BASE_URL}/api/reportes/rentabilidad-linea", 
                               params={"empresa_id": EMPRESA_ID, "fecha_desde": "2026-01-01", "fecha_hasta": "2026-04-05"})
        assert response.status_code == 200
        data = response.json()
        assert data["periodo"]["desde"] == "2026-01-01"
        assert data["periodo"]["hasta"] == "2026-04-05"
        print("✓ Accepts fecha_desde and fecha_hasta parameters")


class TestCxpAging:
    """Tests for GET /api/reportes/cxp-aging endpoint"""
    
    def test_endpoint_returns_200(self):
        """Endpoint should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/reportes/cxp-aging", params={"empresa_id": EMPRESA_ID})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ CxP Aging endpoint returns 200")
    
    def test_response_has_required_structure(self):
        """Response should have fecha_corte, buckets, total, detalle, resumen_proveedor"""
        response = requests.get(f"{BASE_URL}/api/reportes/cxp-aging", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        assert "fecha_corte" in data, "Missing 'fecha_corte'"
        assert "buckets" in data, "Missing 'buckets'"
        assert "total" in data, "Missing 'total'"
        assert "detalle" in data, "Missing 'detalle'"
        assert "resumen_proveedor" in data, "Missing 'resumen_proveedor'"
        print("✓ Response has required structure")
    
    def test_buckets_has_5_aging_periods(self):
        """Buckets should have vigente, 1_30, 31_60, 61_90, 90_plus"""
        response = requests.get(f"{BASE_URL}/api/reportes/cxp-aging", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        expected_buckets = ["vigente", "1_30", "31_60", "61_90", "90_plus"]
        for bucket in expected_buckets:
            assert bucket in data["buckets"], f"Missing bucket '{bucket}'"
        print(f"✓ Buckets has all 5 aging periods: {expected_buckets}")
    
    def test_detalle_is_array(self):
        """Detalle should be an array"""
        response = requests.get(f"{BASE_URL}/api/reportes/cxp-aging", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        assert isinstance(data["detalle"], list), "detalle should be a list"
        print(f"✓ Detalle is array with {len(data['detalle'])} items")
    
    def test_detalle_item_has_required_fields(self):
        """Each detalle item should have proveedor, documento, saldo, fecha_vencimiento, dias_vencido, bucket"""
        response = requests.get(f"{BASE_URL}/api/reportes/cxp-aging", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        required_fields = ["proveedor", "documento", "saldo", "fecha_vencimiento", "dias_vencido", "bucket"]
        
        if data["detalle"]:
            item = data["detalle"][0]
            for field in required_fields:
                assert field in item, f"Missing '{field}' in detalle item"
            print(f"✓ Detalle item has required fields: {required_fields}")
            print(f"  Sample: {item['proveedor']} - {item['documento']} - S/{item['saldo']}")
    
    def test_resumen_proveedor_is_array(self):
        """Resumen proveedor should be an array"""
        response = requests.get(f"{BASE_URL}/api/reportes/cxp-aging", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        assert isinstance(data["resumen_proveedor"], list), "resumen_proveedor should be a list"
        print(f"✓ Resumen proveedor is array with {len(data['resumen_proveedor'])} items")
    
    def test_resumen_proveedor_has_bucket_totals(self):
        """Each resumen_proveedor item should have bucket totals"""
        response = requests.get(f"{BASE_URL}/api/reportes/cxp-aging", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        if data["resumen_proveedor"]:
            item = data["resumen_proveedor"][0]
            assert "nombre" in item, "Missing 'nombre'"
            assert "total" in item, "Missing 'total'"
            assert "vigente" in item, "Missing 'vigente'"
            print(f"✓ Resumen proveedor has bucket totals: {item['nombre']} = S/{item['total']}")
    
    def test_accepts_fecha_corte_parameter(self):
        """Endpoint should accept fecha_corte parameter"""
        response = requests.get(f"{BASE_URL}/api/reportes/cxp-aging", 
                               params={"empresa_id": EMPRESA_ID, "fecha_corte": "2026-04-01"})
        assert response.status_code == 200
        data = response.json()
        assert data["fecha_corte"] == "2026-04-01"
        print("✓ Accepts fecha_corte parameter")
    
    def test_bucket_assignment_correct(self):
        """Verify bucket assignment based on dias_vencido"""
        response = requests.get(f"{BASE_URL}/api/reportes/cxp-aging", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        for item in data["detalle"]:
            dias = item["dias_vencido"]
            bucket = item["bucket"]
            
            if dias <= 0:
                assert bucket == "vigente", f"dias={dias} should be 'vigente', got '{bucket}'"
            elif dias <= 30:
                assert bucket == "1_30", f"dias={dias} should be '1_30', got '{bucket}'"
            elif dias <= 60:
                assert bucket == "31_60", f"dias={dias} should be '31_60', got '{bucket}'"
            elif dias <= 90:
                assert bucket == "61_90", f"dias={dias} should be '61_90', got '{bucket}'"
            else:
                assert bucket == "90_plus", f"dias={dias} should be '90_plus', got '{bucket}'"
        
        print("✓ Bucket assignment is correct based on dias_vencido")


class TestCxcAging:
    """Tests for GET /api/reportes/cxc-aging endpoint"""
    
    def test_endpoint_returns_200(self):
        """Endpoint should return 200 OK"""
        response = requests.get(f"{BASE_URL}/api/reportes/cxc-aging", params={"empresa_id": EMPRESA_ID})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ CxC Aging endpoint returns 200")
    
    def test_response_has_required_structure(self):
        """Response should have fecha_corte, buckets, total, detalle"""
        response = requests.get(f"{BASE_URL}/api/reportes/cxc-aging", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        assert "fecha_corte" in data, "Missing 'fecha_corte'"
        assert "buckets" in data, "Missing 'buckets'"
        assert "total" in data, "Missing 'total'"
        assert "detalle" in data, "Missing 'detalle'"
        print("✓ Response has required structure")
    
    def test_buckets_has_5_aging_periods(self):
        """Buckets should have vigente, 1_30, 31_60, 61_90, 90_plus"""
        response = requests.get(f"{BASE_URL}/api/reportes/cxc-aging", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        expected_buckets = ["vigente", "1_30", "31_60", "61_90", "90_plus"]
        for bucket in expected_buckets:
            assert bucket in data["buckets"], f"Missing bucket '{bucket}'"
        print(f"✓ Buckets has all 5 aging periods")
    
    def test_detalle_is_array(self):
        """Detalle should be an array"""
        response = requests.get(f"{BASE_URL}/api/reportes/cxc-aging", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        assert isinstance(data["detalle"], list), "detalle should be a list"
        print(f"✓ Detalle is array with {len(data['detalle'])} items")
    
    def test_handles_empty_data(self):
        """Endpoint should handle empty data gracefully"""
        response = requests.get(f"{BASE_URL}/api/reportes/cxc-aging", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        # CxC has 0 records per context
        assert data["total"] == 0, f"Expected total=0, got {data['total']}"
        assert len(data["detalle"]) == 0, f"Expected empty detalle, got {len(data['detalle'])} items"
        print("✓ Handles empty data correctly (total=0, detalle=[])")
    
    def test_accepts_fecha_corte_parameter(self):
        """Endpoint should accept fecha_corte parameter"""
        response = requests.get(f"{BASE_URL}/api/reportes/cxc-aging", 
                               params={"empresa_id": EMPRESA_ID, "fecha_corte": "2026-04-01"})
        assert response.status_code == 200
        data = response.json()
        assert data["fecha_corte"] == "2026-04-01"
        print("✓ Accepts fecha_corte parameter")


class TestDataIntegrity:
    """Cross-validation tests for data integrity"""
    
    def test_cxp_total_equals_bucket_sum(self):
        """CxP total should equal sum of all buckets"""
        response = requests.get(f"{BASE_URL}/api/reportes/cxp-aging", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        bucket_sum = sum(data["buckets"].values())
        assert abs(data["total"] - bucket_sum) < 0.01, f"Total {data['total']} != bucket sum {bucket_sum}"
        print(f"✓ CxP total ({data['total']}) equals bucket sum ({bucket_sum})")
    
    def test_cxc_total_equals_bucket_sum(self):
        """CxC total should equal sum of all buckets"""
        response = requests.get(f"{BASE_URL}/api/reportes/cxc-aging", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        bucket_sum = sum(data["buckets"].values())
        assert abs(data["total"] - bucket_sum) < 0.01, f"Total {data['total']} != bucket sum {bucket_sum}"
        print(f"✓ CxC total ({data['total']}) equals bucket sum ({bucket_sum})")
    
    def test_rentabilidad_totales_match_lineas_sum(self):
        """Rentabilidad totales should match sum of lineas"""
        response = requests.get(f"{BASE_URL}/api/reportes/rentabilidad-linea", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        ventas_sum = sum(l["ventas"] for l in data["lineas"])
        costo_sum = sum(l["costo_total"] for l in data["lineas"])
        
        assert abs(data["totales"]["ventas"] - ventas_sum) < 0.01, f"Ventas mismatch"
        assert abs(data["totales"]["costo_total"] - costo_sum) < 0.01, f"Costo mismatch"
        print(f"✓ Rentabilidad totales match lineas sum (ventas={ventas_sum}, costo={costo_sum})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
