import React from 'react';

export const Clientes = () => (
  <div data-testid="clientes-page">
    <div className="page-header">
      <h1 className="page-title">Clientes</h1>
    </div>
    <div className="page-content">
      <div className="card">
        <div className="empty-state">
          <div className="empty-state-title">Modulo de Clientes</div>
          <div className="empty-state-description">Similar a Proveedores con es_cliente=true</div>
        </div>
      </div>
    </div>
  </div>
);
