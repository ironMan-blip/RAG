import { useEffect } from 'react';
import { AlertTriangle } from 'lucide-react';

// Destructive-action confirmation; Escape or a backdrop click cancels unless busy
export default function ConfirmDialog({ title, children, confirmLabel = 'Delete', busy = false, onConfirm, onCancel }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape' && !busy) onCancel(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [busy, onCancel]);

  return (
    <div className="modal-backdrop" onClick={() => !busy && onCancel()}>
      <div className="modal" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title" onClick={e => e.stopPropagation()}>
        <div className="modal-icon"><AlertTriangle size={20} /></div>
        <h2 id="confirm-title">{title}</h2>
        <p>{children}</p>
        <div className="modal-actions">
          <button className="btn" onClick={onCancel} disabled={busy} autoFocus>
            Cancel
          </button>
          <button className="btn btn-danger" onClick={onConfirm} disabled={busy}>
            {busy ? 'Deleting...' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
