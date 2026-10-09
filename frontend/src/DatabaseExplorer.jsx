import React, { useState, useEffect, useRef } from 'react';
import { X, FileText, Database as DatabaseIcon, Trash2, AlertTriangle, Upload, LayoutList, Layers } from 'lucide-react';

export default function DatabaseExplorer({ onClose, documentsUrl, uploadUrl }) {
  const [activeTab, setActiveTab] = useState('documents');
  const [documents, setDocuments] = useState([]);
  const [chunks, setChunks] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [loadingChunks, setLoadingChunks] = useState(false);
  
  const [documentToDelete, setDocumentToDelete] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [expandedDoc, setExpandedDoc] = useState(null);
  
  const libraryInputRef = useRef(null);
  const toolsInputRef = useRef(null);

  useEffect(() => {
    fetchDocuments();
  }, []);

  useEffect(() => {
    if (activeTab === 'chunks' && chunks.length === 0) {
      fetchChunks();
    }
  }, [activeTab]);

  const fetchDocuments = async () => {
    setLoadingDocs(true);
    try {
      const res = await fetch(documentsUrl, { cache: "no-store" });
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

  const fetchChunks = async () => {
    setLoadingChunks(true);
    try {
      const chunksUrl = documentsUrl.replace('/documents', '/chunks');
      const res = await fetch(chunksUrl, { cache: "no-store" });
      if (res.ok) {
        const data = await res.json();
        setChunks(data.chunks || []);
      }
    } catch (error) {
      console.error("Failed to fetch chunks", error);
    } finally {
      setLoadingChunks(false);
    }
  };

  const handleDeleteClick = (doc) => {
    setDocumentToDelete(doc);
  };

  const executeDelete = async () => {
    if (!documentToDelete) return;
    setIsDeleting(true);
    try {
      const deleteUrl = `${documentsUrl}/${documentToDelete.id}`;
      const res = await fetch(deleteUrl, { method: 'DELETE' });
      if (res.ok) {
        setDocuments(documents.filter(doc => doc.id !== documentToDelete.id));
        setChunks(chunks.filter(chunk => chunk.doc_id !== documentToDelete.id));
        setDocumentToDelete(null);
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

  const handleFileUpload = async (event, source) => {
    const file = event.target.files[0];
    if (!file) return;

    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      if (source) formData.append('source', source);
      
      const res = await fetch(uploadUrl, {
        method: 'POST',
        body: formData,
      });

      if (res.ok) {
        await fetchDocuments();
        if (activeTab === 'chunks' || chunks.length > 0) {
           await fetchChunks();
        }
      } else {
        alert("Failed to upload document.");
      }
    } catch (error) {
      console.error("Failed to upload document", error);
      alert("Error uploading document.");
    } finally {
      setIsUploading(false);
      if (libraryInputRef.current) libraryInputRef.current.value = "";
      if (toolsInputRef.current) toolsInputRef.current.value = "";
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
              ref={libraryInputRef} 
              style={{ display: 'none' }} 
              onChange={(e) => handleFileUpload(e, 'library')} 
            />
            <input 
              type="file" 
              ref={toolsInputRef} 
              style={{ display: 'none' }} 
              onChange={(e) => handleFileUpload(e, 'tools')} 
            />
            <button 
              onClick={() => libraryInputRef.current?.click()}
              disabled={isUploading}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 12px',
                backgroundColor: '#3b82f6',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                cursor: isUploading ? 'not-allowed' : 'pointer',
                opacity: isUploading ? 0.7 : 1,
                fontSize: '0.875rem'
              }}
            >
              <Upload size={16} />
              {isUploading ? 'Uploading...' : 'Upload Library File'}
            </button>
            <button 
              onClick={() => toolsInputRef.current?.click()}
              disabled={isUploading}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 12px',
                backgroundColor: '#10b981',
                color: '#fff',
                border: 'none',
                borderRadius: '6px',
                cursor: isUploading ? 'not-allowed' : 'pointer',
                opacity: isUploading ? 0.7 : 1,
                fontSize: '0.875rem'
              }}
            >
              <Upload size={16} />
              {isUploading ? 'Uploading...' : 'Upload Tool File'}
            </button>
            <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '5px', marginLeft: '10px' }}>
              <X size={24} color="#64748b" />
            </button>
          </div>
        </div>

        {/* Body Container */}
        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          
          {/* Sidebar */}
          <div style={{
            width: '240px',
            backgroundColor: '#f8fafc',
            borderRight: '1px solid #e2e8f0',
            display: 'flex',
            flexDirection: 'column',
            padding: '20px 0'
          }}>
            <button 
              onClick={() => setActiveTab('documents')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '12px 24px',
                backgroundColor: activeTab === 'documents' ? '#e2e8f0' : 'transparent',
                border: 'none',
                width: '100%',
                textAlign: 'left',
                cursor: 'pointer',
                color: activeTab === 'documents' ? '#0f172a' : '#475569',
                fontWeight: activeTab === 'documents' ? '600' : '400',
                transition: 'background-color 0.2s'
              }}
            >
              <FileText size={18} />
              Documents
            </button>
            <button 
              onClick={() => setActiveTab('chunks')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '12px 24px',
                backgroundColor: activeTab === 'chunks' ? '#e2e8f0' : 'transparent',
                border: 'none',
                width: '100%',
                textAlign: 'left',
                cursor: 'pointer',
                color: activeTab === 'chunks' ? '#0f172a' : '#475569',
                fontWeight: activeTab === 'chunks' ? '600' : '400',
                transition: 'background-color 0.2s'
              }}
            >
              <Layers size={18} />
              Chunks
            </button>
          </div>

          {/* Main Content Area */}
          <div style={{ flex: 1, padding: '20px', overflowY: 'auto', backgroundColor: '#fff' }}>
            
            {activeTab === 'documents' && (
              <>
                {loadingDocs ? (
                  <p style={{ textAlign: 'center', color: '#64748b', marginTop: '40px' }}>Loading database records...</p>
                ) : documents.length === 0 ? (
                  <p style={{ textAlign: 'center', color: '#64748b', marginTop: '40px' }}>No documents found in the database.</p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {documents.map(doc => (
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
                            backgroundColor: expandedDoc === `doc-${doc.id}` ? '#f8fafc' : '#fff',
                            cursor: 'pointer'
                          }}
                          onClick={() => setExpandedDoc(expandedDoc === `doc-${doc.id}` ? null : `doc-${doc.id}`)}
                        >
                          <div style={{ display: 'flex', alignItems: 'center' }}>
                            <FileText size={20} color="#111111" style={{ marginRight: '10px' }} />
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
                                {doc.tag_label || doc.tag || 'Document'}
                              </div>
                            </div>
                          </div>
                          <button 
                            onClick={(e) => { e.stopPropagation(); handleDeleteClick(doc); }}
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
                        {expandedDoc === `doc-${doc.id}` && (
                          <div style={{ padding: '15px', borderTop: '1px solid #e2e8f0', backgroundColor: '#f8fafc', overflowX: 'auto' }}>
                            <pre style={{ margin: 0, fontSize: '0.8rem', color: '#334155', whiteSpace: 'pre-wrap' }}>
                              {(() => {
                                if (!doc.metadata) return 'No metadata available for this file.';
                                try {
                                  const parsed = typeof doc.metadata === 'string' ? JSON.parse(doc.metadata) : doc.metadata;
                                  return JSON.stringify(parsed, null, 2);
                                } catch (e) {
                                  return String(doc.metadata);
                                }
                              })()}
                            </pre>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}

            {activeTab === 'chunks' && (
              <>
                {loadingChunks ? (
                  <p style={{ textAlign: 'center', color: '#64748b', marginTop: '40px' }}>Loading chunks...</p>
                ) : chunks.length === 0 ? (
                  <p style={{ textAlign: 'center', color: '#64748b', marginTop: '40px' }}>No chunks found in the database.</p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {chunks.map(chunk => (
                      <div key={chunk.chunk_id} style={{ 
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
                            backgroundColor: expandedDoc === `chunk-${chunk.chunk_id}` ? '#f8fafc' : '#fff',
                            cursor: 'pointer'
                          }}
                          onClick={() => setExpandedDoc(expandedDoc === `chunk-${chunk.chunk_id}` ? null : `chunk-${chunk.chunk_id}`)}
                        >
                          <div style={{ display: 'flex', alignItems: 'center' }}>
                            <LayoutList size={20} color="#111111" style={{ marginRight: '10px' }} />
                            <div>
                              <div style={{ fontWeight: 'bold', color: '#1e293b', marginBottom: '6px' }}>{chunk.filename || `Document ${chunk.doc_id}`}</div>
                              <div style={{
                                display: 'inline-block',
                                fontSize: '0.7rem',
                                fontWeight: '600',
                                padding: '2px 8px',
                                borderRadius: '12px',
                                backgroundColor: '#e0f2fe',
                                color: '#0284c7'
                              }}>
                                Chunk {chunk.chunk_id}
                              </div>
                            </div>
                          </div>
                        </div>
                        {expandedDoc === `chunk-${chunk.chunk_id}` && (
                          <div style={{ padding: '15px', borderTop: '1px solid #e2e8f0', backgroundColor: '#f8fafc' }}>
                            <div style={{ fontSize: '0.9rem', color: '#334155', whiteSpace: 'pre-wrap', lineHeight: '1.5' }}>
                              {chunk.chunk_text}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}

          </div>
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
