import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Search } from 'lucide-react';

export const TableSearchSelect = ({
  options = [],
  value,
  onChange,
  placeholder = 'Seleccionar...',
  displayKey = 'nombre',
  valueKey = 'id',
  renderOption,
  className = ''
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const containerRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setIsOpen(false);
        setSearchTerm('');
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  const filteredOptions = options.filter(option => {
    const displayValue = typeof option === 'object' 
      ? (renderOption ? renderOption(option) : option[displayKey]) 
      : option;
    return displayValue?.toString().toLowerCase().includes(searchTerm.toLowerCase());
  });

  const selectedOption = options.find(opt => {
    const optValue = typeof opt === 'object' ? opt[valueKey] : opt;
    return optValue === value || optValue?.toString() === value?.toString();
  });

  const getDisplayValue = (option) => {
    if (!option) return '';
    if (renderOption) return renderOption(option);
    return typeof option === 'object' ? option[displayKey] : option;
  };

  return (
    <div ref={containerRef} className={`table-search-select ${isOpen ? 'open' : ''} ${className}`}>
      <div 
        className="table-search-trigger"
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className={selectedOption ? 'value' : 'placeholder'}>
          {selectedOption ? getDisplayValue(selectedOption) : placeholder}
        </span>
        <ChevronDown size={14} className="chevron" />
      </div>

      {isOpen && (
        <div className="table-search-dropdown">
          <div className="table-search-input-wrap">
            <Search size={14} className="search-icon" />
            <input
              ref={inputRef}
              type="text"
              placeholder="Buscar..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onClick={(e) => e.stopPropagation()}
            />
          </div>
          <div className="table-search-options">
            <div 
              className={`table-search-option ${!value ? 'selected' : ''}`}
              onClick={() => { onChange(''); setIsOpen(false); setSearchTerm(''); }}
            >
              <span style={{ color: 'var(--muted)' }}>{placeholder}</span>
            </div>
            {filteredOptions.map((option, index) => {
              const optValue = typeof option === 'object' ? option[valueKey] : option;
              const isSelected = optValue === value || optValue?.toString() === value?.toString();
              return (
                <div
                  key={optValue || index}
                  className={`table-search-option ${isSelected ? 'selected' : ''}`}
                  onClick={() => { onChange(optValue); setIsOpen(false); setSearchTerm(''); }}
                >
                  {getDisplayValue(option)}
                </div>
              );
            })}
            {filteredOptions.length === 0 && (
              <div className="table-search-empty">Sin resultados</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default TableSearchSelect;
