import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, FileText, Trash2, AlertTriangle, Upload, LayoutList, Search, ChevronRight, RefreshCw, X, Inbox, Pause, Play } from 'lucide-react';
import { API_BASE } from './api';

export default function DatabaseExplorer() {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [search, setSearch] = useState('');

  // doc id -> its chunks, fetched the first time the document is expanded
  const [chunksByDoc, setChunksByDoc] = useState({});
  const [expandedDocId, setExpandedDocId] = useState(null);
  const [expandedChunkId, setExpandedChunkId] = useState(null);
  const [regeneratingChunkIds, setRegeneratingChunkIds] = useState(new Set());

  const [documentToDelete, setDocumentToDelete] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);

  const [uploadSources, setUploadSources] = useState([]);
  const uploadInputRef = useRef(null);
  const uploadSourceRef = useRef(null);

  // Background processing jobs from the backend; failed ones linger until dismissed here
  const [uploads, setUploads] = useState([]);
  const [dismissedUploadIds, setDismissedUploadIds] = useState(new Set());
  const runningUploadsRef = useRef(0);
  // Server unreachable: its uploads are paused and resume from saved progress when it restarts
  const [serverDown, setServerDown] = useState(false);
  const isProcessing = uploads.some(u => !u.error);
  const visibleUploads = uploads.filter(u => !dismissedUploadIds.has(u.id));

  const query = search.trim();

  useEffect(() => {
    fetch(`${API_BASE}/upload-sources`)
      .then(res => res.json())
      .then(data => setUploadSources(data.sources || []))
      .catch(err => console.error("Failed to fetch upload sources", err));
  }, []);

  const fetchUploads = async () => {
    try {
      const res = await fetch(`${API_BASE}/uploads`, { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      const list = data.uploads || [];
      const running = list.filter(u => !u.error).length;
      // A job left the running set, so its document is now in (or failed out of) the list
      if (running < runningUploadsRef.current) fetchDocuments();
      runningUploadsRef.current = running;
      setUploads(list);
      setServerDown(false);
    } catch (error) {
      console.error("Failed to fetch uploads", error);
      setServerDown(true);
    }
  };

  const cancelUpload = async (u) => {
    try {
      const res = await fetch(`${API_BASE}/uploads/${u.id}`, { method: "DELETE" });
      if (!res.ok && res.status !== 404) setError(`Couldn't stop the upload of ${u.filename}.`);
    } catch (error) {
      console.error("Failed to cancel upload", error);
      setError(`Couldn't stop the upload of ${u.filename}.`);
    }
    await fetchUploads();
  };

  const setUploadPaused = async (u, pause) => {
    try {
      const res = await fetch(`${API_BASE}/uploads/${u.id}/${pause ? 'pause' : 'resume'}`, { method: "POST" });
      if (!res.ok) setError(`Couldn't ${pause ? 'pause' : 'resume'} the upload of ${u.filename}.`);
    } catch (error) {
      console.error("Failed to change upload state", error);
      setError(`Couldn't ${pause ? 'pause' : 'resume'} the upload of ${u.filename}.`);
    }
    await fetchUploads();
  };

  useEffect(() => { fetchUploads(); }, []);

  // Poll only while something is processing
  useEffect(() => {
    if (!isProcessing) return;
    const timer = setInterval(fetchUploads, 1000);
    return () => clearInterval(timer);
  }, [isProcessing]);

  // Backend filters by name; debounce so typing doesn't fire a request per key
  useEffect(() => {
    const timer = setTimeout(fetchDocuments, 250);
    return () => clearTimeout(timer);
  }, [query]);

  const fetchDocuments = async () => {
    setLoadingDocs(true);
    try {
      const params = new URLSearchParams({ q: query });
      const res = await fetch(`${API_BASE}/documents?${params}`, { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        setDocuments(data.documents || []);
      }
    } catch (error) {
      console.error("Failed to fetch documents", error);
    } finally {
      setLoadingDocs(false);
    }
  };

  const fetchChunks = async (docId) => {
    setChunksByDoc(prev => ({ ...prev, [docId]: null }));
    try {
      const res = await fetch(`${API_BASE}/documents/${docId}/chunks`, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setChunksByDoc(prev => ({ ...prev, [docId]: data.chunks || [] }));
    } catch (error) {
      console.error("Failed to fetch chunks", error);
      setChunksByDoc(prev => ({ ...prev, [docId]: 'error' }));
    }
  };

  // kind: 'tags' or 'previous-summary'; the backend returns the whole updated chunk
  const regenerate = async (docId, chunkId, kind) => {
    const key = `${chunkId}:${kind}`;
    setRegeneratingChunkIds(prev => new Set(prev).add(key));
    try {
      const res = await fetch(`${API_BASE}/chunks/${chunkId}/${kind}`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setChunksByDoc(prev => Array.isArray(prev[docId]) ? {
        ...prev,
        [docId]: prev[docId].map(c => c.chunk_id === chunkId ? data.chunk : c)
      } : prev);
    } catch (error) {
      console.error(`Failed to regenerate ${kind}`, error);
      setError(`Couldn't regenerate the ${kind === 'tags' ? 'tags' : 'summary'}. Try again.`);
    } finally {
      setRegeneratingChunkIds(prev => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

  const regenerateButton = (isRegenerating, onClick, label) => (
    <button className="icon-btn" onClick={onClick} disabled={isRegenerating} title={label} aria-label={label}>
      <RefreshCw size={14} className={isRegenerating ? 'spinning' : undefined} />
    </button>
  );

  const toggleDocument = (docId) => {
    setExpandedChunkId(null);
    if (expandedDocId === docId) {
      setExpandedDocId(null);
      return;
    }
    setExpandedDocId(docId);
    if (!Array.isArray(chunksByDoc[docId])) fetchChunks(docId);
  };

  // Re-read backend state after a change instead of patching lists locally
  const refresh = () => {
    setChunksByDoc({});
    setExpandedDocId(null);
    setExpandedChunkId(null);
    return fetchDocuments();
  };

  const executeDelete = async () => {
    if (!documentToDelete) return;
    setIsDeleting(true);
    try {
      const res = await fetch(`${API_BASE}/documents/${documentToDelete.id}`, { method: 'DELETE' });
      if (res.ok) {
        setDocumentToDelete(null);
        await refresh();
      } else {
        setError(`Couldn't delete ${documentToDelete.filename}. Try again.`);
      }
    } catch (error) {
      console.error("Failed to delete document", error);
      setError("Couldn't reach the server to delete the document.");
    } finally {
      setIsDeleting(false);
    }
  };

  const handleFileUpload = async (event) => {
    const source = uploadSourceRef.current;
    const file = event.target.files[0];
    if (!file) return;

    setIsUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      if (source) formData.append('source', source);
      
      const res = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        body: formData,
      });

      if (res.ok) {
        await fetchUploads();
      } else {
        // Backend explains rejections (size limit, unknown source); validation errors come as a list
        const { detail } = await res.json().catch(() => ({}));
        setError(typeof detail === 'string' ? detail : `Couldn't upload ${file.name}. Check the file type and try again.`);
      }
    } catch (error) {
      console.error("Failed to upload document", error);
      setError("Couldn't reach the server to upload the document.");
    } finally {
      setIsUploading(false);
      if (uploadInputRef.current) uploadInputRef.current.value = "";
    }
  };

  return (
    <div className="explorer">
      <header className="explorer-header">
        <button className="icon-btn" onClick={() => navigate('/')} aria-label="Back to chat" title="Back to chat">
          <ArrowLeft size={18} />
        </button>
        <h1>Library</h1>
        {!loadingDocs && (
          <span className="explorer-count">{documents.length} {documents.length === 1 ? 'document' : 'documents'}</span>
        )}
        <div className="explorer-actions">
          <input type="file" ref={uploadInputRef} style={{ display: 'none' }} onChange={handleFileUpload} />
          {uploadSources.map(src => (
            <button
              key={src.value}
              className="btn"
              onClick={() => { uploadSourceRef.current = src.value; uploadInputRef.current?.click(); }}
              disabled={isUploading}
            >
              <Upload size={15} />
              <span className="source-dot" style={{ background: src.color }} aria-hidden="true" />
              {`Upload ${src.label}`}
            </button>
          ))}
        </div>
      </header>

      <div className="explorer-body">
        <label className="search-field">
          <Search size={16} />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search documents by name"
            aria-label="Search documents by name"
          />
        </label>

        {error && (
          <div className="alert" role="alert">
            <AlertTriangle size={16} />
            <span>{error}</span>
            <button className="icon-btn" onClick={() => setError(null)} aria-label="Dismiss">
              <X size={16} />
            </button>
          </div>
        )}

        <div className="explorer-list">
          {visibleUploads.map(u => (
              <article key={u.id} className="doc-card upload-card">
                <div className="doc-row">
                  <div className="doc-toggle">
                    <span className={`doc-icon ${u.error ? 'failed' : ''}`}>
                      {u.error ? <AlertTriangle size={18} /> : serverDown || u.paused ? <Pause size={18} /> : <RefreshCw size={18} className="spinning" />}
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
                            className={`upload-progress ${serverDown || u.paused ? 'paused' : ''}`}
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
                    <button
                      className="icon-btn"
                      onClick={() => setDismissedUploadIds(prev => new Set(prev).add(u.id))}
                      aria-label={`Dismiss ${u.filename}`}
                      title="Dismiss"
                    >
                      <X size={16} />
                    </button>
                  )}
                  {!u.error && !serverDown && (
                    <button
                      className="icon-btn"
                      onClick={() => setUploadPaused(u, !u.paused)}
                      disabled={u.paused && !u.stopped}
                      aria-label={`${u.paused ? 'Resume' : 'Pause'} upload of ${u.filename}`}
                      title={u.paused ? 'Resume upload' : 'Pause upload'}
                    >
                      {u.paused ? <Play size={16} /> : <Pause size={16} />}
                    </button>
                  )}
                  {!u.error && !serverDown && (
                    <button
                      className="icon-btn"
                      onClick={() => cancelUpload(u)}
                      aria-label={`Stop and delete upload of ${u.filename}`}
                      title="Stop and delete upload"
                    >
                      <Trash2 size={16} />
                    </button>
                  )}
                </div>
              </article>
          ))}
          {loadingDocs ? (
            <div aria-label="Loading documents" role="status">
              {[0, 1, 2].map(i => <div key={i} className="skeleton" style={{ marginBottom: 8 }} />)}
            </div>
          ) : documents.length === 0 ? (
            visibleUploads.length > 0 && !query ? null : <div className="empty-state">
              <Inbox size={32} />
              {query ? (
                <><strong>No matches</strong>No documents match "{query}".</>
              ) : (
                <><strong>No documents yet</strong>Upload a file to make it searchable in chat.</>
              )}
            </div>
          ) : documents.map(doc => {
            const isExpanded = expandedDocId === doc.id;
            const chunks = chunksByDoc[doc.id];
            return (
              <article key={doc.id} className={`doc-card ${isExpanded ? 'expanded' : ''}`}>
                <div className="doc-row">
                  <button className="doc-toggle" onClick={() => toggleDocument(doc.id)} aria-expanded={isExpanded}>
                    <ChevronRight size={16} />
                    <span className="doc-icon"><FileText size={18} /></span>
                    <span style={{ minWidth: 0 }}>
                      <div className="doc-name" title={doc.filename}>{doc.filename}</div>
                      <span className="tag" style={{ background: doc.tag_bg_color, color: doc.tag_text_color }}>
                        {doc.tag_label}
                      </span>
                    </span>
                  </button>
                  <button className="icon-btn danger" onClick={() => setDocumentToDelete(doc)} title="Delete document" aria-label={`Delete ${doc.filename}`}>
                    <Trash2 size={17} />
                  </button>
                </div>

                {isExpanded && (
                  <div className="doc-detail">
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
                          const isRegeneratingTags = regeneratingChunkIds.has(`${chunk.chunk_id}:tags`);
                          const isRegeneratingSummary = regeneratingChunkIds.has(`${chunk.chunk_id}:previous-summary`);
                          return (
                            <div key={chunk.chunk_id} className="chunk-card">
                              <button
                                className="chunk-toggle"
                                onClick={() => setExpandedChunkId(isChunkExpanded ? null : chunk.chunk_id)}
                                aria-expanded={isChunkExpanded}
                              >
                                <ChevronRight size={14} />
                                <LayoutList size={15} />
                                {chunk.label}
                              </button>
                              {isChunkExpanded && (
                                <>
                                  <div className="chunk-section meta">
                                    {regenerateButton(isRegeneratingTags, () => regenerate(doc.id, chunk.chunk_id, 'tags'), 'Regenerate tags')}
                                    <pre>{chunk.metadata_text}</pre>
                                  </div>
                                  {chunk.previous_summary_text != null && (
                                    <div className="chunk-section summary">
                                      {regenerateButton(isRegeneratingSummary, () => regenerate(doc.id, chunk.chunk_id, 'previous-summary'), 'Regenerate summary')}
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
          })}
        </div>
      </div>

      {documentToDelete && (
        <div className="modal-backdrop" onClick={() => !isDeleting && setDocumentToDelete(null)}>
          <div className="modal" role="alertdialog" aria-modal="true" aria-labelledby="delete-title" onClick={e => e.stopPropagation()}>
            <div className="modal-icon"><AlertTriangle size={20} /></div>
            <h2 id="delete-title">Delete document?</h2>
            <p>
              <strong>{documentToDelete.filename}</strong> and all its chunks will be removed from the library. This can't be undone.
            </p>
            <div className="modal-actions">
              <button className="btn" onClick={() => setDocumentToDelete(null)} disabled={isDeleting} autoFocus>
                Cancel
              </button>
              <button className="btn btn-danger" onClick={executeDelete} disabled={isDeleting}>
                {isDeleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
