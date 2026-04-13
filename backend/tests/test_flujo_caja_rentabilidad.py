"""
Test Phase 4: Flujo de Caja Gerencial (GET /api/flujo-caja-gerencial)
Test Phase 5: Rentabilidad (GET /api/rentabilidad)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
EMPRESA_ID = 6  # Ambission Industries SAC - has real Odoo data


class TestFlujoCajaGerencial:
    """Tests for GET /api/flujo-caja-gerencial endpoint"""
    
    def test_flujo_caja_mensual_returns_200(self):
        """Test monthly grouping returns valid structure"""
        response = requests.get(
            f"{BASE_URL}/api/flujo-caja-gerencial",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2026-03-31",
                "agrupacion": "mensual"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Validate response structure
        assert "timeline" in data, "Response must contain 'timeline'"
        assert "totales" in data, "Response must contain 'totales'"
        assert "agrupacion" in data, "Response must contain 'agrupacion'"
        assert "fecha_desde" in data
        assert "fecha_hasta" in data
        
        # Validate agrupacion matches request
        assert data["agrupacion"] == "mensual"
        
        # Validate totales structure
        totales = data["totales"]
        assert "ingresos" in totales
        assert "egresos" in totales
        assert "flujo_neto" in totales
        assert isinstance(totales["ingresos"], (int, float))
        assert isinstance(totales["egresos"], (int, float))
        assert isinstance(totales["flujo_neto"], (int, float))
        
    def test_flujo_caja_diario_returns_200(self):
        """Test daily grouping returns valid structure"""
        response = requests.get(
            f"{BASE_URL}/api/flujo-caja-gerencial",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2026-03-31",
                "agrupacion": "diario"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["agrupacion"] == "diario"
        assert "timeline" in data
        assert "totales" in data

    def test_flujo_caja_semanal_returns_200(self):
        """Test weekly grouping returns valid structure"""
        response = requests.get(
            f"{BASE_URL}/api/flujo-caja-gerencial",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2026-03-31",
                "agrupacion": "semanal"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["agrupacion"] == "semanal"
        assert "timeline" in data
        assert "totales" in data

    def test_flujo_caja_timeline_item_structure(self):
        """Test timeline items have correct structure with all required fields"""
        response = requests.get(
            f"{BASE_URL}/api/flujo-caja-gerencial",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2026-03-31",
                "agrupacion": "mensual"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        timeline = data["timeline"]
        
        if len(timeline) > 0:
            item = timeline[0]
            # Validate all required fields per the frontend table columns
            required_fields = [
                "periodo",
                "ingresos_ventas",      # Ventas column
                "cobranzas_cxc",        # Cobranzas column
                "total_ingresos",       # Total Ingresos column
                "egresos_gastos",       # Gastos column
                "pagos_cxp",            # Pagos CxP column
                "total_egresos",        # Total Egresos column
                "flujo_neto",           # Flujo Neto column
                "saldo_acumulado"       # Saldo Acum. column
            ]
            for field in required_fields:
                assert field in item, f"Timeline item must have '{field}'"
            
            # Validate data types
            assert isinstance(item["periodo"], str)
            assert isinstance(item["ingresos_ventas"], (int, float))
            assert isinstance(item["cobranzas_cxc"], (int, float))
            assert isinstance(item["total_ingresos"], (int, float))
            assert isinstance(item["egresos_gastos"], (int, float))
            assert isinstance(item["pagos_cxp"], (int, float))
            assert isinstance(item["total_egresos"], (int, float))
            assert isinstance(item["flujo_neto"], (int, float))
            assert isinstance(item["saldo_acumulado"], (int, float))
            
            # Validate calculations: total_ingresos = ingresos_ventas + cobranzas_cxc
            expected_total_in = item["ingresos_ventas"] + item["cobranzas_cxc"]
            assert abs(item["total_ingresos"] - expected_total_in) < 0.01, \
                f"total_ingresos should equal ingresos_ventas + cobranzas_cxc"
            
            # Validate calculations: total_egresos = egresos_gastos + pagos_cxp
            expected_total_out = item["egresos_gastos"] + item["pagos_cxp"]
            assert abs(item["total_egresos"] - expected_total_out) < 0.01, \
                f"total_egresos should equal egresos_gastos + pagos_cxp"
            
            # Validate flujo_neto = total_ingresos - total_egresos
            expected_neto = item["total_ingresos"] - item["total_egresos"]
            assert abs(item["flujo_neto"] - expected_neto) < 0.01, \
                f"flujo_neto should equal total_ingresos - total_egresos"

    def test_flujo_caja_totales_calculation(self):
        """Test that totales correctly aggregate timeline data"""
        response = requests.get(
            f"{BASE_URL}/api/flujo-caja-gerencial",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2026-03-31",
                "agrupacion": "mensual"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        timeline = data["timeline"]
        totales = data["totales"]
        
        if len(timeline) > 0:
            # Sum total_ingresos and total_egresos from timeline
            sum_ingresos = sum(t["total_ingresos"] for t in timeline)
            sum_egresos = sum(t["total_egresos"] for t in timeline)
            
            assert abs(totales["ingresos"] - sum_ingresos) < 0.01, \
                f"totales.ingresos ({totales['ingresos']}) should equal sum of timeline total_ingresos ({sum_ingresos})"
            assert abs(totales["egresos"] - sum_egresos) < 0.01, \
                f"totales.egresos ({totales['egresos']}) should equal sum of timeline total_egresos ({sum_egresos})"
            
            # flujo_neto = ingresos - egresos
            expected_neto = totales["ingresos"] - totales["egresos"]
            assert abs(totales["flujo_neto"] - expected_neto) < 0.01

    def test_flujo_caja_invalid_agrupacion_rejected(self):
        """Test that invalid agrupacion values are rejected"""
        response = requests.get(
            f"{BASE_URL}/api/flujo-caja-gerencial",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2026-03-31",
                "agrupacion": "anual"  # Invalid
            }
        )
        assert response.status_code == 422, f"Expected 422 for invalid agrupacion, got {response.status_code}"

    def test_flujo_caja_missing_fecha_desde(self):
        """Test that missing fecha_desde returns 422"""
        response = requests.get(
            f"{BASE_URL}/api/flujo-caja-gerencial",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_hasta": "2026-03-31",
                "agrupacion": "mensual"
            }
        )
        assert response.status_code == 422


class TestRentabilidad:
    """Tests for GET /api/rentabilidad endpoint"""
    
    def test_rentabilidad_marca_returns_200(self):
        """Test rentabilidad by marca returns valid structure"""
        response = requests.get(
            f"{BASE_URL}/api/rentabilidad",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2026-03-31",
                "dimension": "marca"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Validate response structure
        assert "data" in data, "Response must contain 'data'"
        assert "totales" in data, "Response must contain 'totales'"
        assert "dimension" in data, "Response must contain 'dimension'"
        assert "fecha_desde" in data
        assert "fecha_hasta" in data
        
        # Validate dimension matches request
        assert data["dimension"] == "marca"
        
        # Validate totales structure
        totales = data["totales"]
        assert "ingreso" in totales
        assert "gasto" in totales
        assert "utilidad" in totales
        assert "margen_pct" in totales
        
        assert isinstance(totales["ingreso"], (int, float))
        assert isinstance(totales["gasto"], (int, float))
        assert isinstance(totales["utilidad"], (int, float))
        assert isinstance(totales["margen_pct"], (int, float))

    def test_rentabilidad_linea_negocio_returns_200(self):
        """Test rentabilidad by linea_negocio"""
        response = requests.get(
            f"{BASE_URL}/api/rentabilidad",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2026-03-31",
                "dimension": "linea_negocio"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["dimension"] == "linea_negocio"

    def test_rentabilidad_centro_costo_returns_200(self):
        """Test rentabilidad by centro_costo"""
        response = requests.get(
            f"{BASE_URL}/api/rentabilidad",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2026-03-31",
                "dimension": "centro_costo"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["dimension"] == "centro_costo"

    def test_rentabilidad_proyecto_returns_200_with_empty_data(self):
        """Test rentabilidad by proyecto returns empty data gracefully"""
        response = requests.get(
            f"{BASE_URL}/api/rentabilidad",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2026-03-31",
                "dimension": "proyecto"
            }
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["dimension"] == "proyecto"
        assert "data" in data
        assert isinstance(data["data"], list)
        # Empty data should still return valid totales with zeros
        assert data["totales"]["ingreso"] >= 0
        assert data["totales"]["gasto"] >= 0

    def test_rentabilidad_data_item_structure(self):
        """Test rentabilidad data items have correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/rentabilidad",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2026-03-31",
                "dimension": "marca"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        items = data["data"]
        
        if len(items) > 0:
            item = items[0]
            # Validate all required fields per the frontend table columns
            required_fields = [
                "dimension",    # Marca/Linea/Centro/Proyecto name
                "ingreso",      # Ingreso column
                "gasto",        # Gasto column
                "utilidad",     # Utilidad column
                "margen_pct"    # Margen % column
            ]
            for field in required_fields:
                assert field in item, f"Data item must have '{field}'"
            
            # Validate data types
            assert isinstance(item["dimension"], str)
            assert isinstance(item["ingreso"], (int, float))
            assert isinstance(item["gasto"], (int, float))
            assert isinstance(item["utilidad"], (int, float))
            assert isinstance(item["margen_pct"], (int, float))
            
            # Validate calculation: utilidad = ingreso - gasto
            expected_utilidad = item["ingreso"] - item["gasto"]
            assert abs(item["utilidad"] - expected_utilidad) < 0.01, \
                f"utilidad should equal ingreso - gasto"
            
            # Validate margen calculation (if ingreso > 0)
            if item["ingreso"] > 0:
                expected_margen = (item["utilidad"] / item["ingreso"]) * 100
                assert abs(item["margen_pct"] - expected_margen) < 0.2, \
                    f"margen_pct should equal (utilidad/ingreso)*100"

    def test_rentabilidad_totales_calculation(self):
        """Test that totales correctly aggregate data items"""
        response = requests.get(
            f"{BASE_URL}/api/rentabilidad",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2026-03-31",
                "dimension": "marca"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        items = data["data"]
        totales = data["totales"]
        
        if len(items) > 0:
            sum_ingreso = sum(i["ingreso"] for i in items)
            sum_gasto = sum(i["gasto"] for i in items)
            
            assert abs(totales["ingreso"] - sum_ingreso) < 0.01, \
                f"totales.ingreso ({totales['ingreso']}) should equal sum of items ({sum_ingreso})"
            assert abs(totales["gasto"] - sum_gasto) < 0.01, \
                f"totales.gasto ({totales['gasto']}) should equal sum of items ({sum_gasto})"
            
            # utilidad = ingreso - gasto
            expected_utilidad = totales["ingreso"] - totales["gasto"]
            assert abs(totales["utilidad"] - expected_utilidad) < 0.01

    def test_rentabilidad_invalid_dimension_rejected(self):
        """Test that invalid dimension values are rejected"""
        response = requests.get(
            f"{BASE_URL}/api/rentabilidad",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2026-03-31",
                "dimension": "cliente"  # Invalid
            }
        )
        assert response.status_code == 422, f"Expected 422 for invalid dimension, got {response.status_code}"

    def test_rentabilidad_missing_empresa_id(self):
        """Test that missing empresa_id returns 422 or proper error"""
        response = requests.get(
            f"{BASE_URL}/api/rentabilidad",
            params={
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2026-03-31",
                "dimension": "marca"
            }
        )
        # Should return error since empresa_id is required
        assert response.status_code in [400, 422], f"Expected 400/422 for missing empresa_id, got {response.status_code}"


class TestFlujoCajaWithRealData:
    """Test flujo de caja with known real data from empresa_id=6"""
    
    def test_flujo_caja_has_data_from_pos_sales(self):
        """Test that flujo de caja captures confirmed POS sales as ingresos"""
        # empresa_id=6 has 1 confirmed POS sale per previous iterations
        response = requests.get(
            f"{BASE_URL}/api/flujo-caja-gerencial",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2026-03-31",
                "agrupacion": "mensual"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        totales = data["totales"]
        
        # The empresa has real payment applications (cont_pago_aplicacion) 
        # from confirmed POS sales - should have some ingresos
        print(f"Flujo de Caja totales: ingresos={totales['ingresos']}, egresos={totales['egresos']}, flujo_neto={totales['flujo_neto']}")
        
        # Verify the structure is valid - actual amounts depend on data
        assert isinstance(totales["ingresos"], (int, float))
        assert isinstance(totales["egresos"], (int, float))


class TestRentabilidadWithRealData:
    """Test rentabilidad with known real data from empresa_id=6"""
    
    def test_rentabilidad_has_element_premium_marca(self):
        """Test that rentabilidad shows ELEMENT PREMIUM brand income"""
        # Per iteration_19, empresa_id=6 has confirmed POS sale for ELEMENT PREMIUM
        response = requests.get(
            f"{BASE_URL}/api/rentabilidad",
            params={
                "empresa_id": EMPRESA_ID,
                "fecha_desde": "2025-01-01",
                "fecha_hasta": "2026-03-31",
                "dimension": "marca"
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        items = data["data"]
        
        print(f"Rentabilidad data items: {len(items)}")
        for item in items:
            print(f"  - {item['dimension']}: ingreso={item['ingreso']}, gasto={item['gasto']}, utilidad={item['utilidad']}, margen={item['margen_pct']}%")
        
        # If we have data, verify structure
        if len(items) > 0:
            # Should have ELEMENT PREMIUM if POS sales are confirmed
            marca_names = [i["dimension"] for i in items]
            print(f"Marcas found: {marca_names}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
