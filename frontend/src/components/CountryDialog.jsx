import { useEffect, useState } from 'react';
import { Search } from 'lucide-react';

// Pick the one country an upload is for; options come from the backend with N/A first.
export default function CountryDialog({ options, onConfirm, onCancel }) {
  const [selected, setSelected] = useState(null);
  const [filter, setFilter] = useState('');

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onCancel(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onCancel]);

  const needle = filter.trim().toLowerCase();
  const shown = options.filter(c => c.toLowerCase().includes(needle));

  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="country-title" onClick={e => e.stopPropagation()}>
        <h2 id="country-title">Which country is this for?</h2>
        <p>Pick one, or N/A if it isn't country-specific.</p>
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
        <div className="country-list" role="radiogroup" aria-label="Countries">
          {shown.map(c => (
            <label key={c} className="country-option">
              <input type="radio" name="country" checked={selected === c} onChange={() => setSelected(c)} />
              {c}
            </label>
          ))}
          {shown.length === 0 && <p className="detail-note">No countries match "{filter.trim()}".</p>}
        </div>
        <div className="modal-actions">
          <span className="country-count">{selected ?? 'None selected'}</span>
          <button className="btn" onClick={onCancel}>Cancel</button>
          <button className="btn btn-primary" onClick={() => onConfirm(selected)} disabled={!selected}>
            Choose files
          </button>
        </div>
      </div>
    </div>
  );
}
