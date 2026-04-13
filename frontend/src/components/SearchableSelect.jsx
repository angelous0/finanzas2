import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Plus, Search, X } from 'lucide-react';

export const SearchableSelect = ({
  options = [],
  value,
  onChange,
  placeholder = 'Seleccionar...',
  searchPlaceholder = 'Buscar...',
  displayKey = 'nombre',
  valueKey = 'id',
  onCreateNew,
  createNewLabel = 'Crear nuevo',
  clearable = false,
  disabled = false,
  className = '',
  'data-testid': testId
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const containerRef = useRef(null);
  const searchInputRef = useRef(null);

  // Close dropdown when clicking outside
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

  // Focus search input when opening
  useEffect(() => {
    if (isOpen && searchInputRef.current) {
      setTimeout(() => searchInputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  const filteredOptions = options.filter(option => {
    const displayValue = typeof option === 'object' ? option[displayKey] : option;
    return displayValue?.toString().toLowerCase().includes(searchTerm.toLowerCase());
  });

  const selectedOption = options.find(opt => {
    const optValue = typeof opt === 'object' ? opt[valueKey] : opt;
    return optValue === value || optValue?.toString() === value?.toString();
  });

  const displayValue = selectedOption 
    ? (typeof selectedOption === 'object' ? selectedOption[displayKey] : selectedOption)
    : null;

  const handleSelect = (option) => {
    const newValue = typeof option === 'object' ? option[valueKey] : option;
    onChange(newValue);
    setIsOpen(false);
    setSearchTerm('');
  };

  const handleCreateNew = () => {
    if (onCreateNew) {
      onCreateNew(searchTerm);
      setIsOpen(false);
      setSearchTerm('');
    }
  };

  return (
    <div 
      ref={containerRef}
      className={`searchable-select ${isOpen ? 'open' : ''} ${className}`}
      data-testid={testId}
    >
      <button
        type="button"
        className="searchable-select-trigger"
        onClick={() => !disabled && setIsOpen(!isOpen)}
        disabled={disabled}
      >
        {displayValue ? (
          <span className="value" style={{ flex: 1 }}>{displayValue}</span>
        ) : (
          <span className="placeholder" style={{ flex: 1 }}>{placeholder}</span>
        )}
        {clearable && value && !disabled && (
          <span
            role="button"
            onClick={(e) => { e.stopPropagation(); onChange(''); }}
            style={{ padding: '2px', borderRadius: '50%', display: 'flex', alignItems: 'center', cursor: 'pointer', color: 'var(--muted)', marginRight: '2px' }}
            onMouseEnter={(e) => e.currentTarget.style.color = '#ef4444'}
            onMouseLeave={(e) => e.currentTarget.style.color = '#9ca3af'}
          >
            <X size={14} />
          </span>
        )}
        <ChevronDown size={16} className="chevron" />
      </button>

      {isOpen && (
        <div className="searchable-select-dropdown">
          <div className="searchable-select-search">
            <div style={{ position: 'relative' }}>
              <Search 
                size={16} 
                style={{ 
                  position: 'absolute', 
                  left: '0.75rem', 
                  top: '50%', 
                  transform: 'translateY(-50%)',
                  color: 'var(--muted)'
                }} 
              />
              <input
                ref={searchInputRef}
                type="text"
                placeholder={searchPlaceholder}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{ paddingLeft: '2.25rem' }}
              />
            </div>
          </div>

          <div className="searchable-select-options">
            {filteredOptions.length === 0 && !onCreateNew ? (
              <div className="searchable-select-empty">
                No se encontraron resultados
              </div>
            ) : (
              <>
                {filteredOptions.map((option, index) => {
                  const optValue = typeof option === 'object' ? option[valueKey] : option;
                  const optDisplay = typeof option === 'object' ? option[displayKey] : option;
                  const isSelected = optValue === value || optValue?.toString() === value?.toString();

                  return (
                    <div
                      key={optValue || index}
                      className={`searchable-select-option ${isSelected ? 'selected' : ''}`}
                      onClick={() => handleSelect(option)}
                    >
                      {optDisplay}
                    </div>
                  );
                })}
              </>
            )}

            {onCreateNew && (
              <div
                className="searchable-select-option create-new"
                onClick={handleCreateNew}
              >
                <Plus size={16} />
                {searchTerm ? `${createNewLabel}: "${searchTerm}"` : createNewLabel}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default SearchableSelect;
