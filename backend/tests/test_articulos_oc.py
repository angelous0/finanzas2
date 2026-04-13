"""
Test suite for GET /api/articulos-oc endpoint
Tests the enriched article data for Purchase Orders (Órdenes de Compra)
Features tested:
- Returns enriched article data (stock_actual, linea_negocio_nombre, ultimo_precio, unidad_medida)
- Filters by search query (nombre and codigo)
- Excludes 'PT' category articles
- ultimo_precio comes from cont_oc_linea (latest) or prod_inventario_ingresos (fallback), or 0 if none
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
EMPRESA_ID = 7


class TestArticulosOCEndpoint:
    """Tests for GET /api/articulos-oc endpoint"""
    
    def test_endpoint_returns_200(self):
        """Test that endpoint returns 200 status"""
        response = requests.get(f"{BASE_URL}/api/articulos-oc", params={"empresa_id": EMPRESA_ID})
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Endpoint returns 200")
    
    def test_returns_list(self):
        """Test that endpoint returns a list"""
        response = requests.get(f"{BASE_URL}/api/articulos-oc", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✓ Returns list with {len(data)} articles")
    
    def test_article_structure(self):
        """Test that each article has required fields"""
        response = requests.get(f"{BASE_URL}/api/articulos-oc", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        assert len(data) > 0, "Expected at least one article"
        
        required_fields = ['id', 'codigo', 'nombre', 'descripcion', 'categoria', 
                          'unidad_medida', 'stock_actual', 'linea_negocio_id', 
                          'linea_negocio_nombre', 'ultimo_precio']
        
        for article in data:
            for field in required_fields:
                assert field in article, f"Missing field: {field}"
        print(f"✓ All {len(data)} articles have required fields")
    
    def test_stock_actual_is_numeric(self):
        """Test that stock_actual is a number"""
        response = requests.get(f"{BASE_URL}/api/articulos-oc", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        for article in data:
            assert isinstance(article['stock_actual'], (int, float)), \
                f"stock_actual should be numeric, got {type(article['stock_actual'])}"
        print("✓ stock_actual is numeric for all articles")
    
    def test_ultimo_precio_is_numeric(self):
        """Test that ultimo_precio is a number"""
        response = requests.get(f"{BASE_URL}/api/articulos-oc", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        for article in data:
            assert isinstance(article['ultimo_precio'], (int, float)), \
                f"ultimo_precio should be numeric, got {type(article['ultimo_precio'])}"
        print("✓ ultimo_precio is numeric for all articles")
    
    def test_excludes_pt_category(self):
        """Test that PT (Producto Terminado) category articles are excluded"""
        response = requests.get(f"{BASE_URL}/api/articulos-oc", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        pt_articles = [a for a in data if a.get('categoria') == 'PT']
        assert len(pt_articles) == 0, f"Found {len(pt_articles)} PT articles that should be excluded"
        print("✓ No PT category articles in response")
    
    def test_search_by_nombre(self):
        """Test search filtering by nombre"""
        response = requests.get(f"{BASE_URL}/api/articulos-oc", 
                               params={"empresa_id": EMPRESA_ID, "search": "boton"})
        data = response.json()
        
        assert len(data) > 0, "Expected at least one result for 'boton' search"
        for article in data:
            assert 'boton' in article['nombre'].lower() or 'boton' in article.get('codigo', '').lower(), \
                f"Article {article['nombre']} doesn't match search 'boton'"
        print(f"✓ Search by nombre 'boton' returns {len(data)} matching articles")
    
    def test_search_by_codigo(self):
        """Test search filtering by codigo"""
        response = requests.get(f"{BASE_URL}/api/articulos-oc", 
                               params={"empresa_id": EMPRESA_ID, "search": "TEL001"})
        data = response.json()
        
        assert len(data) > 0, "Expected at least one result for 'TEL001' search"
        found = any(a['codigo'] == 'TEL001' for a in data)
        assert found, "Expected to find article with codigo TEL001"
        print(f"✓ Search by codigo 'TEL001' returns {len(data)} matching articles")
    
    def test_search_case_insensitive(self):
        """Test that search is case insensitive"""
        response_lower = requests.get(f"{BASE_URL}/api/articulos-oc", 
                                     params={"empresa_id": EMPRESA_ID, "search": "arkanzas"})
        response_upper = requests.get(f"{BASE_URL}/api/articulos-oc", 
                                     params={"empresa_id": EMPRESA_ID, "search": "ARKANZAS"})
        
        data_lower = response_lower.json()
        data_upper = response_upper.json()
        
        assert len(data_lower) == len(data_upper), "Case insensitive search should return same results"
        print(f"✓ Search is case insensitive ({len(data_lower)} results)")
    
    def test_linea_negocio_nombre_populated(self):
        """Test that linea_negocio_nombre is populated when linea_negocio_id exists"""
        response = requests.get(f"{BASE_URL}/api/articulos-oc", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        articles_with_linea = [a for a in data if a.get('linea_negocio_id')]
        for article in articles_with_linea:
            assert article.get('linea_negocio_nombre'), \
                f"Article {article['nombre']} has linea_negocio_id but no linea_negocio_nombre"
        print(f"✓ {len(articles_with_linea)} articles have linea_negocio_nombre populated")


class TestArticulosOCPriceLogic:
    """Tests for ultimo_precio logic: OC history > inventory entries > 0"""
    
    def test_article_with_oc_price(self):
        """Test article with price from OC history (TEL001 should have 15.0)"""
        response = requests.get(f"{BASE_URL}/api/articulos-oc", 
                               params={"empresa_id": EMPRESA_ID, "search": "TEL001"})
        data = response.json()
        
        assert len(data) > 0, "Expected to find TEL001"
        tel001 = next((a for a in data if a['codigo'] == 'TEL001'), None)
        assert tel001 is not None, "TEL001 not found"
        assert tel001['ultimo_precio'] == 15.0, \
            f"TEL001 should have ultimo_precio=15.0 from OC, got {tel001['ultimo_precio']}"
        print(f"✓ TEL001 has ultimo_precio=15.0 from OC history")
    
    def test_article_with_inventory_price(self):
        """Test article with price from inventory entries (BOT001 should have 0.6)"""
        response = requests.get(f"{BASE_URL}/api/articulos-oc", 
                               params={"empresa_id": EMPRESA_ID, "search": "BOT001"})
        data = response.json()
        
        assert len(data) > 0, "Expected to find BOT001"
        bot001 = next((a for a in data if a['codigo'] == 'BOT001'), None)
        assert bot001 is not None, "BOT001 not found"
        assert bot001['ultimo_precio'] == 0.6, \
            f"BOT001 should have ultimo_precio=0.6 from inventory, got {bot001['ultimo_precio']}"
        print(f"✓ BOT001 has ultimo_precio=0.6 from inventory entries")
    
    def test_article_with_no_price_history(self):
        """Test article with no price history defaults to 0"""
        response = requests.get(f"{BASE_URL}/api/articulos-oc", 
                               params={"empresa_id": EMPRESA_ID, "search": "TEL-002"})
        data = response.json()
        
        assert len(data) > 0, "Expected to find TEL-002"
        tel002 = next((a for a in data if a['codigo'] == 'TEL-002'), None)
        assert tel002 is not None, "TEL-002 not found"
        assert tel002['ultimo_precio'] == 0, \
            f"TEL-002 should have ultimo_precio=0 (no history), got {tel002['ultimo_precio']}"
        print(f"✓ TEL-002 has ultimo_precio=0 (no price history)")


class TestArticulosOCDataIntegrity:
    """Tests for data integrity and expected values"""
    
    def test_expected_article_count(self):
        """Test that we have the expected number of non-PT articles (4)"""
        response = requests.get(f"{BASE_URL}/api/articulos-oc", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        # According to context: 4 non-PT articles
        assert len(data) >= 4, f"Expected at least 4 articles, got {len(data)}"
        print(f"✓ Found {len(data)} articles (expected >= 4)")
    
    def test_unidad_medida_values(self):
        """Test that unidad_medida has valid values"""
        response = requests.get(f"{BASE_URL}/api/articulos-oc", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        for article in data:
            assert article.get('unidad_medida'), \
                f"Article {article['nombre']} missing unidad_medida"
        print("✓ All articles have unidad_medida")
    
    def test_stock_values_non_negative(self):
        """Test that stock_actual values are non-negative"""
        response = requests.get(f"{BASE_URL}/api/articulos-oc", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        for article in data:
            assert article['stock_actual'] >= 0, \
                f"Article {article['nombre']} has negative stock: {article['stock_actual']}"
        print("✓ All stock_actual values are non-negative")
    
    def test_ultimo_precio_non_negative(self):
        """Test that ultimo_precio values are non-negative"""
        response = requests.get(f"{BASE_URL}/api/articulos-oc", params={"empresa_id": EMPRESA_ID})
        data = response.json()
        
        for article in data:
            assert article['ultimo_precio'] >= 0, \
                f"Article {article['nombre']} has negative ultimo_precio: {article['ultimo_precio']}"
        print("✓ All ultimo_precio values are non-negative")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
