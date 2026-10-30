import { useState, useRef, useEffect } from 'react';
import { Check, ChevronDown, Cpu } from 'lucide-react';

// Closes on outside click or Escape
export default function ModelPicker({ models, value, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const onMouseDown = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onMouseDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onMouseDown);
      document.removeEventListener('keydown', onKey);
    };
  }, []);

  return (
    <div className="custom-dropdown" ref={ref}>
      <button
        className="btn dropdown-trigger"
        onClick={() => setOpen(!open)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label="Select model"
      >
        <Cpu size={15} />
        <span className="dropdown-label">
          {models.find(m => m.value === value)?.label || 'Select model'}
        </span>
        <ChevronDown size={15} className={`dropdown-arrow ${open ? 'open' : ''}`} />
      </button>

      {open && (
        <div className="dropdown-menu">
          <div className="dropdown-header">Model</div>
          <div className="dropdown-list" role="listbox">
            {models.length === 0 && <p className="dropdown-empty">No models available. Check that Ollama is running.</p>}
            {models.map(model => (
              <button
                key={model.value}
                role="option"
                aria-selected={value === model.value}
                className={`dropdown-item ${value === model.value ? 'selected' : ''}`}
                onClick={() => {
                  onChange(model.value);
                  setOpen(false);
                }}
              >
                <span className="item-label">{model.label}</span>
                {value === model.value && <Check size={16} className="check-icon" />}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
