import { AlertTriangle, Pause, Play, RefreshCw, Trash2, X } from 'lucide-react';

// One background upload job; serverDown: the backend is unreachable, so its jobs are shown paused
export default function UploadCard({ upload: u, serverDown, onDismiss, onTogglePause, onCancel }) {
  const paused = serverDown || u.paused;
  return (
    <article className="doc-card upload-card">
      <div className="doc-row">
        <div className="doc-toggle">
          <span className={`doc-icon ${u.error ? 'failed' : ''}`}>
            {u.error ? <AlertTriangle size={18} /> : paused ? <Pause size={18} /> : <RefreshCw size={18} className="spinning" />}
          </span>
          <span style={{ minWidth: 0, flex: 1 }}>
            <div className="doc-name" title={u.filename}>{u.filename}</div>
            {u.error ? (
              <div className="upload-status failed">{u.error}</div>
            ) : (
              <>
                <div className="upload-status">
                  <span>
                    <span className="source-dot" style={{ background: u.color }} aria-hidden="true" />
                    {serverDown ? 'Paused, waiting for the server' : u.status_text}
                  </span>
                  <span>{serverDown ? '' : u.eta_text}</span>
                </div>
                <div
                  className={`upload-progress ${paused ? 'paused' : ''}`}
                  role="progressbar"
                  aria-label={`Processing ${u.filename}`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={u.percent ?? undefined}
                >
                  <span className={u.percent == null ? 'indeterminate' : undefined} style={u.percent == null ? undefined : { width: `${u.percent}%` }} />
                </div>
              </>
            )}
          </span>
        </div>
        {u.error && (
          <button className="icon-btn" onClick={onDismiss} aria-label={`Dismiss ${u.filename}`} title="Dismiss">
            <X size={16} />
          </button>
        )}
        {!u.error && !serverDown && (
          <>
            <button
              className="icon-btn"
              onClick={onTogglePause}
              disabled={u.paused && !u.stopped}
              aria-label={`${u.paused ? 'Resume' : 'Pause'} upload of ${u.filename}`}
              title={u.paused ? 'Resume upload' : 'Pause upload'}
            >
              {u.paused ? <Play size={16} /> : <Pause size={16} />}
            </button>
            <button
              className="icon-btn"
              onClick={onCancel}
              aria-label={`Stop and delete upload of ${u.filename}`}
              title="Stop and delete upload"
            >
              <Trash2 size={16} />
            </button>
          </>
        )}
      </div>
    </article>
  );
}
