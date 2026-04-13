"""
Test suite for Phase 6: Presupuesto vs Real and ROI Proyectos endpoints
Tests backend API functionality for finanzas gerenciales module
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
EMPRESA_ID = 6


class TestPresupuestoVsReal:
    """Tests for /api/presupuesto-vs-real endpoint"""
    
    def test_presupuesto_vs_real_2026_has_data(self):
        """Test: GET /api/presupuesto-vs-real?anio=2026 returns presupuesto data"""
        response = requests.get(f"{BASE_URL}/api/presupuesto-vs-real", params={
            "empresa_id": EMPRESA_ID,
            "anio": 2026
        })
        assert response.status_code == 200
        data = response.json()
        
        # Verify presupuesto info
        assert data["presupuesto"] is not None
        assert data["presupuesto"]["id"] == 2
        assert "Presupuesto Operativo 2026" in data["presupuesto"]["nombre"]
        
    def test_presupuesto_vs_real_2026_totales(self):
        """Test: Totales structure and values for 2026 budget"""
        response = requests.get(f"{BASE_URL}/api/presupuesto-vs-real", params={
            "empresa_id": EMPRESA_ID,
            "anio": 2026
        })
        assert response.status_code == 200
        data = response.json()
        
        # Verify totales structure
        totales = data["totales"]
        assert "presupuestado" in totales
        assert "real" in totales
        assert "desviacion" in totales
        assert "ejecucion_pct" in totales
        
        # Verify totales values (S/16,500 budget)
        assert totales["presupuestado"] == 16500.0
        assert totales["real"] == 0  # No real gastos for 2026 yet
        assert totales["desviacion"] == 16500.0
        assert totales["ejecucion_pct"] == 0.0
        
    def test_presupuesto_vs_real_2026_por_mes(self):
        """Test: por_mes array with 12 months data"""
        response = requests.get(f"{BASE_URL}/api/presupuesto-vs-real", params={
            "empresa_id": EMPRESA_ID,
            "anio": 2026
        })
        assert response.status_code == 200
        data = response.json()
        
        # Verify 12 months
        por_mes = data["por_mes"]
        assert len(por_mes) == 12
        
        # Verify structure
        for item in por_mes:
            assert "mes" in item
            assert "mes_nombre" in item
            assert "presupuestado" in item
            assert "real" in item
            assert "desviacion" in item
        
        # Verify month names
        meses_esperados = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        for i, item in enumerate(por_mes):
            assert item["mes"] == i + 1
            assert item["mes_nombre"] == meses_esperados[i]
        
        # Verify Jan-Mar have budget values
        assert por_mes[0]["presupuestado"] == 5000.0  # Ene
        assert por_mes[1]["presupuestado"] == 6000.0  # Feb
        assert por_mes[2]["presupuestado"] == 5500.0  # Mar
        
    def test_presupuesto_vs_real_2026_data_by_category(self):
        """Test: data array with category breakdown"""
        response = requests.get(f"{BASE_URL}/api/presupuesto-vs-real", params={
            "empresa_id": EMPRESA_ID,
            "anio": 2026
        })
        assert response.status_code == 200
        data = response.json()
        
        # Verify data structure
        for item in data["data"]:
            assert "categoria" in item
            assert "presupuestado" in item
            assert "real" in item
            assert "desviacion" in item
            assert "ejecucion_pct" in item
            
    def test_presupuesto_vs_real_2025_no_budget(self):
        """Test: GET /api/presupuesto-vs-real?anio=2025 returns null presupuesto gracefully"""
        response = requests.get(f"{BASE_URL}/api/presupuesto-vs-real", params={
            "empresa_id": EMPRESA_ID,
            "anio": 2025
        })
        assert response.status_code == 200
        data = response.json()
        
        # Verify null presupuesto
        assert data["presupuesto"] is None
        assert data["data"] == []
        assert data["por_mes"] == []
        assert data["totales"]["presupuestado"] == 0
        assert data["totales"]["real"] == 0
        assert data["totales"]["desviacion"] == 0
        
    def test_presupuesto_vs_real_missing_anio(self):
        """Test: Missing anio parameter returns 422"""
        response = requests.get(f"{BASE_URL}/api/presupuesto-vs-real", params={
            "empresa_id": EMPRESA_ID
        })
        assert response.status_code == 422
        
    def test_presupuesto_vs_real_missing_empresa(self):
        """Test: Missing empresa_id parameter returns 4xx error"""
        response = requests.get(f"{BASE_URL}/api/presupuesto-vs-real", params={
            "anio": 2026
        })
        assert response.status_code in [400, 422]


class TestRoiProyectos:
    """Tests for /api/roi-proyectos endpoint"""
    
    def test_roi_proyectos_basic_response(self):
        """Test: GET /api/roi-proyectos returns valid structure"""
        response = requests.get(f"{BASE_URL}/api/roi-proyectos", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": "2025-01-01",
            "fecha_hasta": "2026-12-31"
        })
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "data" in data
        assert "totales" in data
        assert "fecha_desde" in data
        assert "fecha_hasta" in data
        assert isinstance(data["data"], list)
        
    def test_roi_proyectos_totales_structure(self):
        """Test: ROI totales has correct fields"""
        response = requests.get(f"{BASE_URL}/api/roi-proyectos", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": "2025-01-01",
            "fecha_hasta": "2026-12-31"
        })
        assert response.status_code == 200
        data = response.json()
        
        totales = data["totales"]
        assert "inversion" in totales
        assert "retorno" in totales
        assert "utilidad" in totales
        assert "roi_pct" in totales
        
    def test_roi_proyectos_empty_data(self):
        """Test: No active projects returns empty data gracefully"""
        response = requests.get(f"{BASE_URL}/api/roi-proyectos", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": "2025-01-01",
            "fecha_hasta": "2026-12-31"
        })
        assert response.status_code == 200
        data = response.json()
        
        # No projects exist, so empty data expected
        assert data["data"] == []
        assert data["totales"]["inversion"] == 0
        assert data["totales"]["retorno"] == 0
        assert data["totales"]["utilidad"] == 0
        assert data["totales"]["roi_pct"] == 0
        
    def test_roi_proyectos_date_filters(self):
        """Test: Date filters are returned correctly"""
        response = requests.get(f"{BASE_URL}/api/roi-proyectos", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": "2025-01-01",
            "fecha_hasta": "2026-12-31"
        })
        assert response.status_code == 200
        data = response.json()
        
        assert data["fecha_desde"] == "2025-01-01"
        assert data["fecha_hasta"] == "2026-12-31"
        
    def test_roi_proyectos_missing_fecha_desde(self):
        """Test: Missing fecha_desde parameter returns 422"""
        response = requests.get(f"{BASE_URL}/api/roi-proyectos", params={
            "empresa_id": EMPRESA_ID,
            "fecha_hasta": "2026-12-31"
        })
        assert response.status_code == 422
        
    def test_roi_proyectos_missing_fecha_hasta(self):
        """Test: Missing fecha_hasta parameter returns 422"""
        response = requests.get(f"{BASE_URL}/api/roi-proyectos", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": "2025-01-01"
        })
        assert response.status_code == 422
        
    def test_roi_proyectos_missing_empresa(self):
        """Test: Missing empresa_id parameter returns 4xx error"""
        response = requests.get(f"{BASE_URL}/api/roi-proyectos", params={
            "fecha_desde": "2025-01-01",
            "fecha_hasta": "2026-12-31"
        })
        assert response.status_code in [400, 422]


class TestRoiProyectosDataStructure:
    """Tests for ROI data item structure when projects exist"""
    
    def test_roi_data_item_fields(self):
        """Test: ROI data items have expected fields (if projects exist)"""
        response = requests.get(f"{BASE_URL}/api/roi-proyectos", params={
            "empresa_id": EMPRESA_ID,
            "fecha_desde": "2025-01-01",
            "fecha_hasta": "2026-12-31"
        })
        assert response.status_code == 200
        data = response.json()
        
        # If there are projects, verify structure
        for item in data["data"]:
            assert "proyecto" in item
            assert "proyecto_id" in item
            assert "inversion" in item
            assert "retorno" in item
            assert "utilidad" in item
            assert "roi_pct" in item
