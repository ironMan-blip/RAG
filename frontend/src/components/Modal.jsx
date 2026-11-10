import { useEffect } from 'react';

// Dialog shell: Escape or a backdrop click calls onClose; labelId names the element holding the title
export default function Modal({ role = 'dialog', labelId, onClose, children }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" role={role} aria-modal="true" aria-labelledby={labelId} onClick={e => e.stopPropagation()}>
        {children}
      </div>
    </div>
  );
}
