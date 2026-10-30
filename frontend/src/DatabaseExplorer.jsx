import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, AlertTriangle, Upload, Search, X, Inbox } from 'lucide-react';
import { API_BASE } from './api';
import ConfirmDialog from './components/ConfirmDialog';
import DocumentCard from './components/DocumentCard';
import UploadCard from './components/UploadCard';

export default function DatabaseExplorer() {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState([]);
  const [countText, setCountText] = useState('');
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
        setCountText(data.count_text);
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
      fetchDocuments();  // the document's unfinished mark may have cleared
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
    const files = [...event.target.files];
    if (!files.length) return;

    setIsUploading(true);
    setError(null);
    const errors = [];
    try {
      // One request per file; the backend queues each as its own upload job
      for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);
        if (source) formData.append('source', source);

        const res = await fetch(`${API_BASE}/upload`, {
          method: 'POST',
          body: formData,
        });

        if (!res.ok) {
          // Backend explains rejections (size limit, unknown source); validation errors come as a list
          const { detail } = await res.json().catch(() => ({}));
          errors.push(typeof detail === 'string' ? detail : `Couldn't upload ${file.name}. Check the file type and try again.`);
        }
        await fetchUploads();
      }
    } catch (error) {
      console.error("Failed to upload document", error);
      errors.push("Couldn't reach the server to upload the document.");
    } finally {
      if (errors.length) setError(errors.join(' '));
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
          <span className="explorer-count">{countText}</span>
        )}
        <div className="explorer-actions">
          <input type="file" multiple ref={uploadInputRef} style={{ display: 'none' }} onChange={handleFileUpload} />
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
            <UploadCard
              key={u.id}
              upload={u}
              serverDown={serverDown}
              onDismiss={() => setDismissedUploadIds(prev => new Set(prev).add(u.id))}
              onTogglePause={() => setUploadPaused(u, !u.paused)}
              onCancel={() => cancelUpload(u)}
            />
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
          ) : documents.map(doc => (
            <DocumentCard
              key={doc.id}
              doc={doc}
              expanded={expandedDocId === doc.id}
              chunks={chunksByDoc[doc.id]}
              expandedChunkId={expandedChunkId}
              regenerating={regeneratingChunkIds}
              onToggle={() => toggleDocument(doc.id)}
              onToggleChunk={setExpandedChunkId}
              onRegenerate={(chunkId, kind) => regenerate(doc.id, chunkId, kind)}
              onDelete={() => setDocumentToDelete(doc)}
            />
          ))}
        </div>
      </div>

      {documentToDelete && (
        <ConfirmDialog title="Delete document?" busy={isDeleting} onConfirm={executeDelete} onCancel={() => setDocumentToDelete(null)}>
          <strong>{documentToDelete.filename}</strong> and all its chunks will be removed from the library. This can't be undone.
        </ConfirmDialog>
      )}
    </div>
  );
}
