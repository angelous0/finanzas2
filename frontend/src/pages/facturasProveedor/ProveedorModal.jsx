import React, { useState } from 'react';
import { createTercero } from '../../services/api';
import { toast } from 'sonner';

const ProveedorModal = ({ show, onClose, onCreated }) => {
  const [nombre, setNombre] = useState('');

  if (!show) return null;

  const handleSave = async () => {
    if (!nombre.trim()) {
      toast.error('Ingrese el nombre del proveedor');
      return;
    }
    try {
      const response = await createTercero({
        nombre: nombre.trim(),
        es_proveedor: true,
        tipo_documento: 'RUC',
        numero_documento: '',
        terminos_pago_dias: 30
      });
      toast.success(`Proveedor "${nombre}" creado exitosamente`);
      setNombre('');
      onCreated(response.data);
    } catch (error) {
      console.error('Error creating proveedor:', error);
      toast.error('Error al crear proveedor');
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose} style={{ zIndex: 1100 }}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '400px', padding: '1.5rem' }}>
        <h3 style={{ margin: '0 0 1rem', fontSize: '1.125rem', fontWeight: 600 }}>Crear nuevo proveedor</h3>
        <div className="form-group" style={{ marginBottom: '1rem' }}>
          <label className="form-label">Nombre del proveedor</label>
          <input
            type="text"
            className="form-input"
            placeholder="Razon social o nombre"
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            autoFocus
            data-testid="nuevo-proveedor-nombre"
          />
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
          <button type="button" className="btn btn-outline" onClick={onClose}>Cancelar</button>
          <button type="button" className="btn btn-primary" onClick={handleSave} data-testid="guardar-proveedor-btn">
            Crear proveedor
          </button>
        </div>
      </div>
    </div>
  );
};

export default ProveedorModal;
