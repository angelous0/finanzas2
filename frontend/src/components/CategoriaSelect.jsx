import React, { useState, useRef, useEffect, useMemo } from 'react';
import { ChevronDown, Search } from 'lucide-react';

/**
 * Searchable category selector with parent/child grouping.
 * Only children are selectable; parents appear as group headers.
 */
const CategoriaSelect = ({ categorias = [], value, onChange, placeholder = 'Categoria' }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const containerRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
        setSearchTerm('');
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (isOpen && inputRef.current) inputRef.current.focus();
  }, [isOpen]);

  const { padres, grouped, orphans } = useMemo(() => {
    const p = categorias.filter(c => !c.padre_id).sort((a, b) => a.nombre.localeCompare(b.nombre));
    const h = categorias.filter(c => c.padre_id);
    const padreIds = new Set(p.map(x => x.id));
    const g = {};
    const o = [];
    for (const child of h) {
      if (padreIds.has(child.padre_id)) {
        if (!g[child.padre_id]) g[child.padre_id] = [];
        g[child.padre_id].push(child);
      } else {
        o.push(child);
      }
    }
    for (const key of Object.keys(g)) {
      g[key].sort((a, b) => a.nombre.localeCompare(b.nombre));
    }
    o.sort((a, b) => a.nombre.localeCompare(b.nombre));
    return { padres: p, grouped: g, orphans: o };
  }, [categorias]);

  const filteredGroups = useMemo(() => {
    const term = searchTerm.toLowerCase().trim();
    if (!term) return { padres, grouped, orphans };

    const fp = [];
    const fg = {};
    for (const padre of padres) {
      const children = grouped[padre.id] || [];
      const matched = children.filter(c =>
        c.nombre.toLowerCase().includes(term) ||
        (c.nombre_completo || '').toLowerCase().includes(term) ||
        padre.nombre.toLowerCase().includes(term)
      );
      if (matched.length > 0) {
        fp.push(padre);
        fg[padre.id] = matched;
      }
    }
    const fo = orphans.filter(c =>
      c.nombre.toLowerCase().includes(term) ||
      (c.nombre_completo || '').toLowerCase().includes(term)
    );
    return { padres: fp, grouped: fg, orphans: fo };
  }, [searchTerm, padres, grouped, orphans]);

  const selectedCat = useMemo(() => {
    if (!value) return null;
    return categorias.find(c => c.id === value || String(c.id) === String(value));
  }, [value, categorias]);

  const selectedPadreName = useMemo(() => {
    if (!selectedCat || !selectedCat.padre_id) return null;
    const p = categorias.find(c => c.id === selectedCat.padre_id);
    return p ? p.nombre : null;
  }, [selectedCat, categorias]);

  const hasResults = filteredGroups.padres.length > 0 || filteredGroups.orphans.length > 0;

  return (
    <div ref={containerRef} className={`table-search-select ${isOpen ? 'open' : ''}`}>
      <div className="table-search-trigger" onClick={() => setIsOpen(!isOpen)}>
        {selectedCat ? (
          <span className="value" style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.3 }}>
            <span style={{ fontSize: '0.8125rem', color: 'var(--text-primary)' }}>{selectedCat.nombre}</span>
            {selectedPadreName && (
              <span style={{ fontSize: '0.6875rem', color: 'var(--muted)' }}>{selectedPadreName}</span>
            )}
          </span>
        ) : (
          <span className="placeholder">{placeholder}</span>
        )}
        <ChevronDown size={14} className="chevron" />
      </div>

      {isOpen && (
        <div className="table-search-dropdown" style={{ minWidth: 260 }}>
          <div className="table-search-input-wrap">
            <Search size={14} className="search-icon" />
            <input
              ref={inputRef}
              type="text"
              placeholder="Buscar categoria..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onClick={(e) => e.stopPropagation()}
            />
          </div>
          <div className="table-search-options" style={{ maxHeight: 280 }}>
            {/* Clear option */}
            <div
              className={`table-search-option ${!value ? 'selected' : ''}`}
              onClick={() => { onChange(''); setIsOpen(false); setSearchTerm(''); }}
            >
              <span style={{ color: 'var(--muted)' }}>{placeholder}</span>
            </div>

            {/* Grouped categories */}
            {filteredGroups.padres.map(padre => {
              const children = filteredGroups.grouped[padre.id] || [];
              if (children.length === 0) return null;
              return (
                <React.Fragment key={padre.id}>
                  {/* Group header */}
                  <div style={{
                    padding: '5px 10px',
                    fontSize: '0.625rem',
                    fontWeight: 600,
                    color: 'var(--muted)',
                    background: 'var(--card-bg-alt)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    borderTop: '1px solid var(--border)',
                    pointerEvents: 'none',
                    userSelect: 'none',
                  }}>
                    {padre.nombre}
                  </div>
                  {/* Child options */}
                  {children.map(child => {
                    const isSelected = String(child.id) === String(value);
                    return (
                      <div
                        key={child.id}
                        className={`table-search-option ${isSelected ? 'selected' : ''}`}
                        style={{ padding: '6px 10px', whiteSpace: 'normal' }}
                        onClick={() => { onChange(child.id); setIsOpen(false); setSearchTerm(''); }}
                      >
                        <div style={{ fontSize: '0.8125rem', color: isSelected ? 'var(--primary)' : 'var(--text-primary)', lineHeight: 1.3 }}>
                          {child.nombre}
                        </div>
                        {child.descripcion && (
                          <div style={{ fontSize: '0.6875rem', color: 'var(--muted)', lineHeight: 1.3 }}>
                            {child.descripcion}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </React.Fragment>
              );
            })}

            {/* Orphan categories */}
            {filteredGroups.orphans.map(cat => {
              const isSelected = String(cat.id) === String(value);
              return (
                <div
                  key={cat.id}
                  className={`table-search-option ${isSelected ? 'selected' : ''}`}
                  style={{ padding: '6px 10px', whiteSpace: 'normal' }}
                  onClick={() => { onChange(cat.id); setIsOpen(false); setSearchTerm(''); }}
                >
                  <div style={{ fontSize: '0.8125rem', color: isSelected ? 'var(--primary)' : 'var(--text-primary)' }}>
                    {cat.nombre}
                  </div>
                  {cat.padre_nombre && (
                    <div style={{ fontSize: '0.6875rem', color: 'var(--muted)' }}>
                      {cat.padre_nombre}
                    </div>
                  )}
                </div>
              );
            })}

            {!hasResults && (
              <div className="table-search-empty">Sin resultados</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default CategoriaSelect;
