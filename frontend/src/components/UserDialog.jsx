import { useEffect, useState } from 'react';
import { api } from '../api';
import Modal from './Modal';

// Pick who you are from the saved users, or add yourself with a name and country. No auth.
export default function UserDialog({ current, onSelect, onCancel }) {
  const [users, setUsers] = useState([]);
  const [countries, setCountries] = useState([]);
  const [selectedId, setSelectedId] = useState(current?.id ?? null);
  const [name, setName] = useState('');
  const [country, setCountry] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    api('/users', { cache: 'no-store' })
      .then(data => { setUsers(data.users); setCountries(data.countries); })
      .catch(() => setError('Could not load users.'));
  }, []);

  const addUser = (e) => {
    e.preventDefault();
    setError('');
    api('/users', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, country }) })
      .then(data => onSelect(data.user))
      .catch(err => setError(err.detail ?? 'Could not add user.'));
  };

  return (
    <Modal labelId="user-title" onClose={onCancel}>
      <h2 id="user-title">Who are you?</h2>
      {users.length > 0 && (
        <>
          <p>Pick your name.</p>
          <div className="country-list" role="radiogroup" aria-label="Users">
            {users.map(u => (
              <label key={u.id} className="country-option">
                <input type="radio" name="user" checked={selectedId === u.id} onChange={() => setSelectedId(u.id)} />
                {u.name} · {u.country}
              </label>
            ))}
          </div>
          <div className="modal-actions">
            <button className="btn btn-primary" disabled={selectedId == null}
              onClick={() => onSelect(users.find(u => u.id === selectedId))}>
              Continue
            </button>
          </div>
        </>
      )}
      <form onSubmit={addUser}>
        <p>{users.length > 0 ? 'Not listed? Add yourself.' : 'Add your name and country.'}</p>
        <label className="search-field country-search">
          <input value={name} onChange={e => setName(e.target.value)} placeholder="Your name" aria-label="Your name" maxLength={255} />
        </label>
        <label className="search-field country-search">
          <select value={country} onChange={e => setCountry(e.target.value)} aria-label="Your country">
            <option value="" disabled>Select your country</option>
            {countries.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        {error && <p className="detail-note" role="alert">{error}</p>}
        <div className="modal-actions">
          <button type="button" className="btn" onClick={onCancel}>Cancel</button>
          <button type="submit" className="btn btn-primary" disabled={!name.trim() || !country}>Add</button>
        </div>
      </form>
    </Modal>
  );
}
