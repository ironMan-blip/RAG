import { AlertTriangle } from 'lucide-react';
import Modal from './Modal';

// Destructive-action confirmation; Escape or a backdrop click cancels unless busy
export default function ConfirmDialog({ title, children, confirmLabel = 'Delete', busy = false, onConfirm, onCancel }) {
  return (
    <Modal role="alertdialog" labelId="confirm-title" onClose={() => !busy && onCancel()}>
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
    </Modal>
  );
}
