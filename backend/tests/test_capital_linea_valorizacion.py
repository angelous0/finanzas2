"""
Tests for Capital Linea Negocio CRUD + Rentabilidad and Valorizacion Inventario FIFO
Iteration 25 - Testing new features for profitability per business line and FIFO inventory valuation
"""
import pytest
import requests
import os
from datetime import date

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
EMPRESA_ID = 6  # Ambission Industries SAC
LINEA_PRINCIPAL_ID = 7
LINEA_SECUNDARIA_ID = 8


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestCapitalLineaNegocioCRUD:
    """CRUD tests for capital movements per business line"""
    
    created_ids = []
    
    def test_list_capital_movimientos_empty(self, api_client):
        """GET /api/capital-linea-negocio - List capital movements (starts empty per context)"""
        response = api_client.get(f"{BASE_URL}/api/capital-linea-negocio?empresa_id={EMPRESA_ID}")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "total" in data
        assert isinstance(data["data"], list)
        print(f"✓ List capital: {data['total']} existing movements")
    
    def test_create_capital_inicial(self, api_client):
        """POST /api/capital-linea-negocio - Create capital_inicial movement"""
        payload = {
            "linea_negocio_id": LINEA_PRINCIPAL_ID,
            "fecha": date.today().isoformat(),
            "tipo_movimiento": "capital_inicial",
            "monto": 50000.00,
            "observacion": "TEST: Capital inicial para prueba"
        }
        response = api_client.post(
            f"{BASE_URL}/api/capital-linea-negocio?empresa_id={EMPRESA_ID}",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "message" in data
        self.__class__.created_ids.append(data["id"])
        print(f"✓ Created capital_inicial ID={data['id']}")
    
    def test_create_aporte(self, api_client):
        """POST /api/capital-linea-negocio - Create aporte movement"""
        payload = {
            "linea_negocio_id": LINEA_SECUNDARIA_ID,
            "fecha": date.today().isoformat(),
            "tipo_movimiento": "aporte",
            "monto": 10000.00,
            "observacion": "TEST: Aporte adicional"
        }
        response = api_client.post(
            f"{BASE_URL}/api/capital-linea-negocio?empresa_id={EMPRESA_ID}",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        self.__class__.created_ids.append(data["id"])
        print(f"✓ Created aporte ID={data['id']}")
    
    def test_create_retiro(self, api_client):
        """POST /api/capital-linea-negocio - Create retiro movement"""
        payload = {
            "linea_negocio_id": LINEA_PRINCIPAL_ID,
            "fecha": date.today().isoformat(),
            "tipo_movimiento": "retiro",
            "monto": 5000.00,
            "observacion": "TEST: Retiro de capital"
        }
        response = api_client.post(
            f"{BASE_URL}/api/capital-linea-negocio?empresa_id={EMPRESA_ID}",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        self.__class__.created_ids.append(data["id"])
        print(f"✓ Created retiro ID={data['id']}")
    
    def test_create_invalid_tipo(self, api_client):
        """POST /api/capital-linea-negocio - Invalid tipo_movimiento returns 400"""
        payload = {
            "linea_negocio_id": LINEA_PRINCIPAL_ID,
            "fecha": date.today().isoformat(),
            "tipo_movimiento": "invalid_tipo",
            "monto": 1000.00
        }
        response = api_client.post(
            f"{BASE_URL}/api/capital-linea-negocio?empresa_id={EMPRESA_ID}",
            json=payload
        )
        assert response.status_code == 400
        print("✓ Invalid tipo returns 400")
    
    def test_create_negative_monto(self, api_client):
        """POST /api/capital-linea-negocio - Negative monto returns 400"""
        payload = {
            "linea_negocio_id": LINEA_PRINCIPAL_ID,
            "fecha": date.today().isoformat(),
            "tipo_movimiento": "aporte",
            "monto": -500.00
        }
        response = api_client.post(
            f"{BASE_URL}/api/capital-linea-negocio?empresa_id={EMPRESA_ID}",
            json=payload
        )
        assert response.status_code == 400
        print("✓ Negative monto returns 400")
    
    def test_create_zero_monto(self, api_client):
        """POST /api/capital-linea-negocio - Zero monto returns 400"""
        payload = {
            "linea_negocio_id": LINEA_PRINCIPAL_ID,
            "fecha": date.today().isoformat(),
            "tipo_movimiento": "aporte",
            "monto": 0.0
        }
        response = api_client.post(
            f"{BASE_URL}/api/capital-linea-negocio?empresa_id={EMPRESA_ID}",
            json=payload
        )
        assert response.status_code == 400
        print("✓ Zero monto returns 400")
    
    def test_list_with_filter(self, api_client):
        """GET /api/capital-linea-negocio?linea_negocio_id - Filter by linea"""
        response = api_client.get(
            f"{BASE_URL}/api/capital-linea-negocio?empresa_id={EMPRESA_ID}&linea_negocio_id={LINEA_PRINCIPAL_ID}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        # All should be for LINEA_PRINCIPAL_ID
        for mov in data["data"]:
            assert mov.get("linea_negocio_id") == LINEA_PRINCIPAL_ID
        print(f"✓ Filter by linea_negocio_id: {len(data['data'])} results")
    
    def test_list_all_created(self, api_client):
        """GET /api/capital-linea-negocio - Verify all created movements appear"""
        response = api_client.get(f"{BASE_URL}/api/capital-linea-negocio?empresa_id={EMPRESA_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= len(self.__class__.created_ids)
        ids_in_response = [m["id"] for m in data["data"]]
        for cid in self.__class__.created_ids:
            assert cid in ids_in_response, f"Created ID {cid} not in list"
        print(f"✓ All {len(self.__class__.created_ids)} created IDs found in list")


class TestRentabilidadLineaNegocio:
    """Tests for rentabilidad calculation per business line"""
    
    def test_rentabilidad_basic(self, api_client):
        """GET /api/rentabilidad-linea-negocio - Basic response structure"""
        response = api_client.get(f"{BASE_URL}/api/rentabilidad-linea-negocio?empresa_id={EMPRESA_ID}")
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "lineas" in data
        assert "totales" in data
        assert "fecha_desde" in data
        assert "fecha_hasta" in data
        
        # Should have 2 lineas (Principal and Secundaria)
        assert len(data["lineas"]) == 2
        print(f"✓ Rentabilidad returns {len(data['lineas'])} lineas")
    
    def test_rentabilidad_line_structure(self, api_client):
        """GET /api/rentabilidad-linea-negocio - Verify line data structure"""
        response = api_client.get(f"{BASE_URL}/api/rentabilidad-linea-negocio?empresa_id={EMPRESA_ID}")
        assert response.status_code == 200
        data = response.json()
        
        for linea in data["lineas"]:
            # Required fields for Vista 1: Rendimiento Economico
            assert "linea_negocio_id" in linea
            assert "linea_negocio" in linea
            assert "capital_neto" in linea
            assert "ingresos" in linea
            assert "costos" in linea
            assert "gastos" in linea
            assert "utilidad" in linea
            assert "roi_pct" in linea
            
            # Required fields for Vista 2: Recuperacion de Caja
            assert "cobrado_real" in linea
            assert "pagado_real" in linea
            assert "flujo_neto_caja" in linea
            assert "saldo_por_recuperar" in linea
            assert "payback_meses" in linea or linea["payback_meses"] is None
            assert "flujo_mensual_promedio" in linea
        
        print("✓ All line fields present for both views")
    
    def test_rentabilidad_totals_structure(self, api_client):
        """GET /api/rentabilidad-linea-negocio - Verify totals structure"""
        response = api_client.get(f"{BASE_URL}/api/rentabilidad-linea-negocio?empresa_id={EMPRESA_ID}")
        assert response.status_code == 200
        data = response.json()
        totales = data["totales"]
        
        assert "capital_total" in totales
        assert "ingresos" in totales
        assert "costos" in totales
        assert "gastos" in totales
        assert "utilidad" in totales
        assert "roi_pct" in totales
        assert "cobrado_real" in totales
        assert "pagado_real" in totales
        assert "flujo_neto_caja" in totales
        assert "saldo_por_recuperar" in totales
        
        print("✓ Totals structure verified")
    
    def test_rentabilidad_with_date_filter(self, api_client):
        """GET /api/rentabilidad-linea-negocio - With date filters"""
        response = api_client.get(
            f"{BASE_URL}/api/rentabilidad-linea-negocio?empresa_id={EMPRESA_ID}&fecha_desde=2026-01-01&fecha_hasta=2026-12-31"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["fecha_desde"] == "2026-01-01"
        assert data["fecha_hasta"] == "2026-12-31"
        print("✓ Date filter works correctly")
    
    def test_rentabilidad_capital_calculation(self, api_client):
        """GET /api/rentabilidad-linea-negocio - Verify capital_neto = invertido - retirado"""
        response = api_client.get(f"{BASE_URL}/api/rentabilidad-linea-negocio?empresa_id={EMPRESA_ID}")
        assert response.status_code == 200
        data = response.json()
        
        for linea in data["lineas"]:
            capital_neto = linea["capital_neto"]
            capital_invertido = linea["capital_invertido"]
            capital_retirado = linea["capital_retirado"]
            expected_neto = capital_invertido - capital_retirado
            assert abs(capital_neto - expected_neto) < 0.01, f"Capital neto calculation mismatch for {linea['linea_negocio']}"
        
        print("✓ Capital neto calculation verified")
    
    def test_rentabilidad_utilidad_calculation(self, api_client):
        """GET /api/rentabilidad-linea-negocio - Verify utilidad = ingresos - costos - gastos"""
        response = api_client.get(f"{BASE_URL}/api/rentabilidad-linea-negocio?empresa_id={EMPRESA_ID}")
        assert response.status_code == 200
        data = response.json()
        
        for linea in data["lineas"]:
            utilidad = linea["utilidad"]
            expected = linea["ingresos"] - linea["costos"] - linea["gastos"]
            assert abs(utilidad - expected) < 0.01, f"Utilidad calculation mismatch for {linea['linea_negocio']}"
        
        print("✓ Utilidad calculation verified")


class TestValorizacionInventario:
    """Tests for FIFO inventory valuation from produccion schema"""
    
    def test_valorizacion_basic(self, api_client):
        """GET /api/valorizacion-inventario - Basic response structure"""
        response = api_client.get(f"{BASE_URL}/api/valorizacion-inventario?empresa_id={EMPRESA_ID}")
        assert response.status_code == 200
        data = response.json()
        
        assert "data" in data
        assert "total_articulos" in data
        assert "total_valor_fifo" in data
        assert "total_valor_promedio" in data
        assert "categorias" in data
        
        print(f"✓ Valorizacion returns {data['total_articulos']} articulos, FIFO total: S/ {data['total_valor_fifo']}")
    
    def test_valorizacion_article_structure(self, api_client):
        """GET /api/valorizacion-inventario - Verify article structure"""
        response = api_client.get(f"{BASE_URL}/api/valorizacion-inventario?empresa_id={EMPRESA_ID}")
        assert response.status_code == 200
        data = response.json()
        
        if data["data"]:
            article = data["data"][0]
            assert "id" in article
            assert "codigo" in article
            assert "nombre" in article
            assert "categoria" in article
            assert "unidad" in article
            assert "stock_actual" in article
            assert "stock_fifo" in article
            assert "costo_fifo_unitario" in article
            assert "valor_fifo" in article
            assert "costo_promedio" in article
            assert "valor_promedio" in article
            assert "lotes_fifo" in article
            
            print(f"✓ Article structure verified: {article['codigo']} - {article['nombre']}")
    
    def test_valorizacion_lotes_structure(self, api_client):
        """GET /api/valorizacion-inventario - Verify FIFO lots structure"""
        response = api_client.get(f"{BASE_URL}/api/valorizacion-inventario?empresa_id={EMPRESA_ID}")
        assert response.status_code == 200
        data = response.json()
        
        # Find an article with lots
        for article in data["data"]:
            if article.get("lotes_fifo") and len(article["lotes_fifo"]) > 0:
                lote = article["lotes_fifo"][0]
                assert "id" in lote
                assert "cantidad_disponible" in lote
                assert "costo_unitario" in lote
                assert "fecha" in lote or lote["fecha"] is None
                assert "documento" in lote or lote["documento"] is None
                print(f"✓ Lote structure verified for {article['codigo']}")
                return
        
        print("✓ No lotes found (some articles may have no available lots)")
    
    def test_valorizacion_fifo_calculation(self, api_client):
        """GET /api/valorizacion-inventario - Verify FIFO calculation"""
        response = api_client.get(f"{BASE_URL}/api/valorizacion-inventario?empresa_id={EMPRESA_ID}")
        assert response.status_code == 200
        data = response.json()
        
        # Verify valor_fifo = sum(cantidad_disponible * costo_unitario for lotes)
        for article in data["data"]:
            if article.get("lotes_fifo"):
                expected_valor = sum(l["cantidad_disponible"] * l["costo_unitario"] for l in article["lotes_fifo"])
                actual_valor = article["valor_fifo"]
                assert abs(actual_valor - expected_valor) < 0.01, f"FIFO value mismatch for {article['codigo']}"
        
        print("✓ FIFO calculation verified")
    
    def test_valorizacion_categorias(self, api_client):
        """GET /api/valorizacion-inventario - Categorias list populated"""
        response = api_client.get(f"{BASE_URL}/api/valorizacion-inventario?empresa_id={EMPRESA_ID}")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data["categorias"], list)
        print(f"✓ Categorias: {data['categorias']}")
    
    def test_valorizacion_search_filter(self, api_client):
        """GET /api/valorizacion-inventario?search=NYLON - Search filter"""
        response = api_client.get(f"{BASE_URL}/api/valorizacion-inventario?empresa_id={EMPRESA_ID}&search=NYLON")
        assert response.status_code == 200
        data = response.json()
        
        # All results should contain NYLON in codigo or nombre
        for article in data["data"]:
            assert "NYLON" in article["nombre"].upper() or "NYLON" in article["codigo"].upper(), f"Search mismatch: {article['nombre']}"
        
        print(f"✓ Search filter works: {len(data['data'])} results for 'NYLON'")
    
    def test_valorizacion_categoria_filter(self, api_client):
        """GET /api/valorizacion-inventario?categoria=Avios - Category filter"""
        response = api_client.get(f"{BASE_URL}/api/valorizacion-inventario?empresa_id={EMPRESA_ID}&categoria=Avios")
        assert response.status_code == 200
        data = response.json()
        
        for article in data["data"]:
            assert article["categoria"] == "Avios", f"Category mismatch: {article['categoria']}"
        
        print(f"✓ Category filter works: {len(data['data'])} Avios articles")
    
    def test_valorizacion_total_consistency(self, api_client):
        """GET /api/valorizacion-inventario - Total valor equals sum of individual valores"""
        response = api_client.get(f"{BASE_URL}/api/valorizacion-inventario?empresa_id={EMPRESA_ID}")
        assert response.status_code == 200
        data = response.json()
        
        calculated_total = sum(a["valor_fifo"] for a in data["data"])
        reported_total = data["total_valor_fifo"]
        
        assert abs(calculated_total - reported_total) < 0.1, f"Total mismatch: calculated={calculated_total}, reported={reported_total}"
        print(f"✓ Total valor FIFO consistent: S/ {reported_total}")


class TestCleanup:
    """Cleanup test data created during tests"""
    
    def test_cleanup_capital_movimientos(self, api_client):
        """DELETE /api/capital-linea-negocio - Cleanup test data"""
        # Get all movements to find TEST ones
        response = api_client.get(f"{BASE_URL}/api/capital-linea-negocio?empresa_id={EMPRESA_ID}")
        assert response.status_code == 200
        data = response.json()
        
        deleted_count = 0
        for mov in data["data"]:
            if mov.get("observacion") and "TEST:" in mov.get("observacion", ""):
                del_response = api_client.delete(
                    f"{BASE_URL}/api/capital-linea-negocio/{mov['id']}?empresa_id={EMPRESA_ID}"
                )
                if del_response.status_code == 200:
                    deleted_count += 1
        
        print(f"✓ Cleanup: deleted {deleted_count} TEST capital movements")
    
    def test_delete_nonexistent(self, api_client):
        """DELETE /api/capital-linea-negocio/{id} - Non-existent returns 404"""
        response = api_client.delete(f"{BASE_URL}/api/capital-linea-negocio/99999?empresa_id={EMPRESA_ID}")
        assert response.status_code == 404
        print("✓ Delete non-existent returns 404")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
