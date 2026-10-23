import React, { useState, useEffect, useRef } from 'react';
import { X, FileText, Database as DatabaseIcon, Trash2, AlertTriangle, Upload, LayoutList, Search, ChevronRight, ChevronDown, RefreshCw } from 'lucide-react';
import { API_BASE } from './api';

export default function DatabaseExplorer({ onClose }) {
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

  const [uploadSources, setUploadSources] = useState([]);
  const uploadInputRef = useRef(null);
  const uploadSourceRef = useRef(null);

  const query = search.trim();

  useEffect(() => {
    fetch(`${API_BASE}/upload-sources`)
      .then(res => res.json())
      .then(data => setUploadSources(data.sources || []))
      .catch(err => console.error("Failed to fetch upload sources", err));
  }, []);

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

  // kind: 'tags' or 'previous-summary'; the response field replaces the same field on the chunk
  const regenerate = async (docId, chunkId, kind, field) => {
    const key = `${chunkId}:${kind}`;
    setRegeneratingChunkIds(prev => new Set(prev).add(key));
    try {
      const res = await fetch(`${API_BASE}/chunks/${chunkId}/${kind}`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setChunksByDoc(prev => Array.isArray(prev[docId]) ? {
        ...prev,
        [docId]: prev[docId].map(c => c.chunk_id === chunkId ? { ...c, [field]: data[field] } : c)
      } : prev);
    } catch (error) {
      console.error(`Failed to regenerate ${kind}`, error);
      alert(`Failed to regenerate ${kind.replace('-', ' ')}.`);
    } finally {
      setRegeneratingChunkIds(prev => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

  const regenerateButton = (isRegenerating, onClick, label) => (
    <button
      onClick={onClick}
      disabled={isRegenerating}
      title={label}
      aria-label={label}
      style={{
        position: 'absolute',
        top: '6px',
        right: '6px',
        display: 'flex',
        padding: '5px',
        background: '#fff',
        border: '1px solid #cbd5e1',
        borderRadius: '6px',
        cursor: isRegenerating ? 'not-allowed' : 'pointer',
        opacity: isRegenerating ? 0.6 : 1
      }}
    >
      <RefreshCw size={14} color="#475569" style={isRegenerating ? { animation: 'spin 1s linear infinite' } : undefined} />
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

  const handleDeleteClick = (doc) => {
    setDocumentToDelete(doc);
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
        alert("Failed to delete document.");
      }
    } catch (error) {
      console.error("Failed to delete document", error);
      alert("Error deleting document.");
    } finally {
      setIsDeleting(false);
    }
  };

  const handleFileUpload = async (event) => {
    const source = uploadSourceRef.current;
    const file = event.target.files[0];
    if (!file) return;

    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      if (source) formData.append('source', source);
      
      const res = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        body: formData,
      });

      if (res.ok) {
        await refresh();
      } else {
        alert("Failed to upload document.");
      }
    } catch (error) {
      console.error("Failed to upload document", error);
      alert("Error uploading document.");
    } finally {
      setIsUploading(false);
      if (uploadInputRef.current) uploadInputRef.current.value = "";
    }
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      backgroundColor: '#f1f5f9',
      padding: '20px',
      boxSizing: 'border-box'
    }}>
      <div style={{
        backgroundColor: '#fff',
        borderRadius: '12px',
        width: '100%',
        maxWidth: '1200px',
        margin: '0 auto',
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)',
        overflow: 'hidden'
      }}>
        {/* Header */}
        <div style={{
          padding: '20px',
          borderBottom: '1px solid #e2e8f0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          backgroundColor: '#fff',
          zIndex: 10
        }}>
          <h2 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '10px', fontSize: '1.25rem' }}>
            <DatabaseIcon size={24} color="#111111" />
            Library
          </h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <input
              type="file"
              ref={uploadInputRef}
              style={{ display: 'none' }}
              onChange={handleFileUpload}
            />
            {uploadSources.map(src => (
              <button
                key={src.value}
                onClick={() => { uploadSourceRef.current = src.value; uploadInputRef.current?.click(); }}
                disabled={isUploading}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '8px 12px',
                  backgroundColor: src.color,
                  color: '#fff',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: isUploading ? 'not-allowed' : 'pointer',
                  opacity: isUploading ? 0.7 : 1,
                  fontSize: '0.875rem'
                }}
              >
                <Upload size={16} />
                {isUploading ? 'Uploading...' : `Upload ${src.label} File`}
              </button>
            ))}
            <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '5px', marginLeft: '10px' }}>
              <X size={24} color="#64748b" />
            </button>
          </div>
        </div>

        {/* Search */}
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #e2e8f0' }}>
          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 12px',
            border: '1px solid #cbd5e1',
            borderRadius: '6px',
            backgroundColor: '#fff'
          }}>
            <Search size={16} color="#64748b" />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search documents by name..."
              aria-label="Search documents by name"
              style={{ flex: 1, border: 'none', outline: 'none', fontSize: '0.9rem', background: 'transparent' }}
            />
          </label>
        </div>

        {/* Document List */}
        <div style={{ flex: 1, padding: '20px', overflowY: 'auto', backgroundColor: '#fff' }}>
          {loadingDocs ? (
            <p style={{ textAlign: 'center', color: '#64748b', marginTop: '40px' }}>Loading database records...</p>
          ) : documents.length === 0 ? (
            <p style={{ textAlign: 'center', color: '#64748b', marginTop: '40px' }}>
              {query ? `No documents match "${query}".` : 'No documents found in the database.'}
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {documents.map(doc => {
                const isExpanded = expandedDocId === doc.id;
                const chunks = chunksByDoc[doc.id];
                return (
                  <div key={doc.id} style={{
                    backgroundColor: '#fff',
                    border: '1px solid #e2e8f0',
                    borderRadius: '8px',
                    overflow: 'hidden'
                  }}>
                    <div style={{
                        padding: '15px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        backgroundColor: isExpanded ? '#f8fafc' : '#fff'
                      }}
                    >
                      <button
                        onClick={() => toggleDocument(doc.id)}
                        aria-expanded={isExpanded}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          flex: 1,
                          background: 'none',
                          border: 'none',
                          padding: 0,
                          textAlign: 'left',
                          cursor: 'pointer',
                          font: 'inherit'
                        }}
                      >
                        {isExpanded ? <ChevronDown size={18} color="#64748b" /> : <ChevronRight size={18} color="#64748b" />}
                        <FileText size={20} color="#111111" style={{ margin: '0 10px 0 6px' }} />
                        <div>
                          <div style={{ fontWeight: 'bold', color: '#1e293b', marginBottom: '6px' }}>{doc.filename}</div>
                          <div style={{
                            display: 'inline-block',
                            fontSize: '0.7rem',
                            fontWeight: '600',
                            padding: '2px 8px',
                            borderRadius: '12px',
                            backgroundColor: doc.tag_bg_color || '#e2e8f0',
                            color: doc.tag_text_color || '#475569'
                          }}>
                            {doc.tag_label}
                          </div>
                        </div>
                      </button>
                      <button
                        onClick={() => handleDeleteClick(doc)}
                        style={{
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer',
                          padding: '5px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: '#ef4444'
                        }}
                        title="Delete Document"
                      >
                        <Trash2 size={20} />
                      </button>
                    </div>

                    {isExpanded && (
                      <div style={{ padding: '12px 15px 15px 44px', borderTop: '1px solid #e2e8f0', backgroundColor: '#f8fafc' }}>
                        <pre style={{ margin: '0 0 10px', fontSize: '0.8rem', color: '#334155', whiteSpace: 'pre-wrap', backgroundColor: '#f1f5f9', padding: '10px', borderRadius: '6px' }}>
                          {doc.metadata_text}
                        </pre>
                        {chunks == null ? (
                          <p style={{ margin: 0, color: '#64748b', fontSize: '0.875rem' }}>Loading chunks...</p>
                        ) : chunks === 'error' ? (
                          <p style={{ margin: 0, color: '#ef4444', fontSize: '0.875rem' }}>Failed to load chunks.</p>
                        ) : chunks.length === 0 ? (
                          <p style={{ margin: 0, color: '#64748b', fontSize: '0.875rem' }}>This document has no chunks.</p>
                        ) : (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                            {chunks.map((chunk, index) => {
                              const isChunkExpanded = expandedChunkId === chunk.chunk_id;
                              const isRegeneratingTags = regeneratingChunkIds.has(`${chunk.chunk_id}:tags`);
                              const isRegeneratingSummary = regeneratingChunkIds.has(`${chunk.chunk_id}:previous-summary`);
                              return (
                                <div key={chunk.chunk_id} style={{ border: '1px solid #e2e8f0', borderRadius: '6px', backgroundColor: '#fff', overflow: 'hidden' }}>
                                  <button
                                    onClick={() => setExpandedChunkId(isChunkExpanded ? null : chunk.chunk_id)}
                                    aria-expanded={isChunkExpanded}
                                    style={{
                                      display: 'flex',
                                      alignItems: 'center',
                                      gap: '8px',
                                      width: '100%',
                                      padding: '10px 12px',
                                      background: 'none',
                                      border: 'none',
                                      textAlign: 'left',
                                      cursor: 'pointer',
                                      font: 'inherit',
                                      fontSize: '0.875rem',
                                      color: '#1e293b'
                                    }}
                                  >
                                    {isChunkExpanded ? <ChevronDown size={16} color="#64748b" /> : <ChevronRight size={16} color="#64748b" />}
                                    <LayoutList size={16} color="#111111" />
                                    {chunk.label}
                                  </button>
                                  {isChunkExpanded && (
                                    <div style={{ position: 'relative', borderTop: '1px solid #e2e8f0' }}>
                                      {regenerateButton(isRegeneratingTags, () => regenerate(doc.id, chunk.chunk_id, 'tags', 'metadata_text'), 'Regenerate tags')}
                                      <pre style={{ margin: 0, fontSize: '0.8rem', color: '#334155', whiteSpace: 'pre-wrap', backgroundColor: '#f1f5f9', padding: '10px 40px 10px 10px' }}>
                                        {chunk.metadata_text}
                                      </pre>
                                      {/* The first chunk has no previous chunk to summarize */}
                                      {index > 0 && (
                                        <div style={{ position: 'relative', borderTop: '1px solid #e2e8f0' }}>
                                          {regenerateButton(isRegeneratingSummary, () => regenerate(doc.id, chunk.chunk_id, 'previous-summary', 'previous_summary'), 'Regenerate summary')}
                                          <pre style={{ margin: 0, fontSize: '0.8rem', color: '#475569', whiteSpace: 'pre-wrap', backgroundColor: '#fef9c3', padding: '10px 40px 10px 10px' }}>
                                            {'Summary of previous chunk:\n' + (chunk.previous_summary || 'No summary available.')}
                                          </pre>
                                        </div>
                                      )}
                                      <pre style={{ margin: 0, fontSize: '0.8rem', color: '#1e293b', whiteSpace: 'pre-wrap', padding: '10px', borderTop: '1px solid #e2e8f0', maxHeight: '400px', overflowY: 'auto' }}>
                                        {chunk.chunk_text}
                                      </pre>
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {documentToDelete && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.6)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1100
        }}>
          <div style={{
            backgroundColor: '#fff',
            borderRadius: '8px',
            padding: '24px',
            width: '90%',
            maxWidth: '400px',
            boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: '#ef4444' }}>
              <AlertTriangle size={28} />
              <h3 style={{ margin: 0, fontSize: '1.25rem', color: '#1e293b' }}>Delete Document</h3>
            </div>
            
            <p style={{ margin: 0, color: '#475569', lineHeight: '1.5' }}>
              Are you sure you want to delete <strong>{documentToDelete.filename}</strong>? 
              This action cannot be undone and will remove all associated data, including its chunks.
            </p>
            
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '8px' }}>
              <button 
                onClick={() => setDocumentToDelete(null)}
                disabled={isDeleting}
                style={{
                  padding: '8px 16px',
                  borderRadius: '6px',
                  border: '1px solid #cbd5e1',
                  backgroundColor: '#fff',
                  color: '#475569',
                  cursor: isDeleting ? 'not-allowed' : 'pointer',
                  fontWeight: '500'
                }}
              >
                Cancel
              </button>
              <button 
                onClick={executeDelete}
                disabled={isDeleting}
                style={{
                  padding: '8px 16px',
                  borderRadius: '6px',
                  border: 'none',
                  backgroundColor: '#ef4444',
                  color: '#fff',
                  cursor: isDeleting ? 'not-allowed' : 'pointer',
                  fontWeight: '500',
                  opacity: isDeleting ? 0.7 : 1
                }}
              >
                {isDeleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
