import React, { createContext, useContext, useState, useEffect } from 'react';
import { getEmpresas } from '../services/api';

const EmpresaContext = createContext();

export function EmpresaProvider({ children }) {
  const [empresas, setEmpresas] = useState([]);
  const [empresaActual, setEmpresaActual] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadEmpresas();
  }, []);

  const loadEmpresas = async () => {
    try {
      const response = await getEmpresas();
      setEmpresas(response.data);
      
      // Set default empresa from localStorage or first one
      const savedEmpresaId = localStorage.getItem('empresaActualId');
      if (savedEmpresaId && response.data.find(e => e.id === parseInt(savedEmpresaId))) {
        setEmpresaActual(response.data.find(e => e.id === parseInt(savedEmpresaId)));
      } else if (response.data.length > 0) {
        setEmpresaActual(response.data[0]);
        localStorage.setItem('empresaActualId', response.data[0].id);
      }
    } catch (error) {
      console.error('Error loading empresas:', error);
    } finally {
      setLoading(false);
    }
  };

  const cambiarEmpresa = (empresaId) => {
    const empresa = empresas.find(e => e.id === parseInt(empresaId));
    if (empresa) {
      setEmpresaActual(empresa);
      localStorage.setItem('empresaActualId', empresa.id);
    }
  };

  return (
    <EmpresaContext.Provider value={{ 
      empresas, 
      empresaActual, 
      cambiarEmpresa, 
      loading,
      reloadEmpresas: loadEmpresas
    }}>
      {children}
    </EmpresaContext.Provider>
  );
}

export function useEmpresa() {
  const context = useContext(EmpresaContext);
  if (!context) {
    throw new Error('useEmpresa debe usarse dentro de EmpresaProvider');
  }
  return context;
}
