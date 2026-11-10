import { useEffect, useState } from 'react';
import { Search } from 'lucide-react';

const NA = 'N/A';

// Pick countries for an upload; options come from the backend with N/A first. N/A excludes every country.
export default function CountryDialog({ options, onConfirm, onCancel }) {
  const [selected, setSelected] = useState([]);
  const [filter, setFilter] = useState('');

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onCancel(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onCancel]);

  const toggle = (c) => setSelected(prev =>
    prev.includes(c) ? prev.filter(x => x !== c) : c === NA ? [NA] : [...prev.filter(x => x !== NA), c]
  );
  const needle = filter.trim().toLowerCase();
  const shown = options.filter(c => c.toLowerCase().includes(needle));

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="country-title" onClick={e => e.stopPropagation()}>
        <h2 id="country-title">Which countries is this for?</h2>
        <p>Pick at least one, or N/A if it isn't country-specific.</p>
        <label className="search-field country-search">
          <Search size={16} />
          <input
            type="search"
            value={filter}
            onChange={e => setFilter(e.target.value)}
            placeholder="Search countries"
            aria-label="Search countries"
            autoFocus
          />
        </label>
        <div className="country-list" role="group" aria-label="Countries">
          {shown.map(c => (
            <label key={c} className="country-option">
              <input type="checkbox" checked={selected.includes(c)} onChange={() => toggle(c)} />
              {c}
            </label>
          ))}
          {shown.length === 0 && <p className="detail-note">No countries match "{filter.trim()}".</p>}
        </div>
        <div className="modal-actions">
          <span className="country-count">{selected.length ? selected.join(', ') : 'None selected'}</span>
          <button className="btn" onClick={onCancel}>Cancel</button>
          <button className="btn btn-primary" onClick={() => onConfirm(selected)} disabled={!selected.length}>
            Choose files
          </button>
        </div>
      </div>
    </div>
  );
}
