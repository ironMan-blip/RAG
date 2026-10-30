import { ChevronRight, FileText, LayoutList, RefreshCw, Trash2 } from 'lucide-react';

function RegenerateButton({ busy, onClick, label }) {
  return (
    <button className="icon-btn" onClick={onClick} disabled={busy} title={label} aria-label={label}>
      <RefreshCw size={14} className={busy ? 'spinning' : undefined} />
    </button>
  );
}

// chunks: undefined/null while loading, 'error' if the fetch failed, else the list.
// regenerating: Set of `${chunkId}:${kind}` keys in flight; onRegenerate(chunkId, kind) with kind 'tags' or 'previous-summary'.
export default function DocumentCard({
  doc, expanded, chunks, expandedChunkId, regenerating,
  onToggle, onToggleChunk, onRegenerate, onDelete,
}) {
  return (
    <article className={`doc-card ${expanded ? 'expanded' : ''} ${doc.unfinished_text ? 'unfinished' : ''}`}>
      <div className="doc-row">
        <button className="doc-toggle" onClick={onToggle} aria-expanded={expanded}>
          <ChevronRight size={16} />
          <span className="doc-icon"><FileText size={18} /></span>
          <span style={{ minWidth: 0 }}>
            <div className="doc-name" title={doc.filename}>{doc.filename}</div>
            <span className="tag" style={{ background: doc.tag_bg_color, color: doc.tag_text_color }}>
              {doc.tag_label}
            </span>
          </span>
        </button>
        <button className="icon-btn danger" onClick={onDelete} title="Delete document" aria-label={`Delete ${doc.filename}`}>
          <Trash2 size={17} />
        </button>
      </div>

      {expanded && (
        <div className="doc-detail">
          {doc.unfinished_text && <p className="detail-note unfinished">{doc.unfinished_text}</p>}
          <div className="section-label">Metadata</div>
          <pre className="meta-block">{doc.metadata_text}</pre>
          <div className="section-label">Chunks{Array.isArray(chunks) && ` (${chunks.length})`}</div>
          {chunks == null ? (
            <p className="detail-note">Loading chunks...</p>
          ) : chunks === 'error' ? (
            <p className="detail-note error">Couldn't load chunks. Collapse and expand to retry.</p>
          ) : chunks.length === 0 ? (
            <p className="detail-note">This document has no chunks.</p>
          ) : (
            <div className="chunk-list">
              {chunks.map(chunk => {
                const isChunkExpanded = expandedChunkId === chunk.chunk_id;
                return (
                  <div key={chunk.chunk_id} className={`chunk-card ${chunk.unfinished_text ? 'unfinished' : ''}`}>
                    <button
                      className="chunk-toggle"
                      onClick={() => onToggleChunk(isChunkExpanded ? null : chunk.chunk_id)}
                      aria-expanded={isChunkExpanded}
                    >
                      <ChevronRight size={14} />
                      <LayoutList size={15} />
                      {chunk.label}
                    </button>
                    {isChunkExpanded && (
                      <>
                        {chunk.unfinished_text && <p className="detail-note unfinished">{chunk.unfinished_text}</p>}
                        <div className="chunk-section meta">
                          <RegenerateButton
                            busy={regenerating.has(`${chunk.chunk_id}:tags`)}
                            onClick={() => onRegenerate(chunk.chunk_id, 'tags')}
                            label="Regenerate tags"
                          />
                          <pre>{chunk.metadata_text}</pre>
                        </div>
                        {chunk.previous_summary_text != null && (
                          <div className="chunk-section summary">
                            <RegenerateButton
                              busy={regenerating.has(`${chunk.chunk_id}:previous-summary`)}
                              onClick={() => onRegenerate(chunk.chunk_id, 'previous-summary')}
                              label="Regenerate summary"
                            />
                            <pre>{chunk.previous_summary_text}</pre>
                          </div>
                        )}
                        <div className="chunk-section text">
                          <pre>{chunk.chunk_text}</pre>
                        </div>
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </article>
  );
}
