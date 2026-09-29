import React, { useState, useEffect } from 'react';
import { X, Layers, Trash2, Plus, FileText, FolderPlus, CheckCircle, Database } from 'lucide-react';

const API_BASE = 'http://localhost:8000/api';

export default function ChunksExplorer({ onClose }) {
  const [chunks, setChunks] = useState([]);
  const [availableDocs, setAvailableDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newChunkName, setNewChunkName] = useState('');
  
  // State for adding files
  const [showAddDocs, setShowAddDocs] = useState(null); // stores chunk ID

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [chunksRes, docsRes] = await Promise.all([
        fetch(`${API_BASE}/file-groups`),
        fetch(`${API_BASE}/documents`)
      ]);
      
      if (chunksRes.ok) {
        const data = await chunksRes.json();
        setChunks(data.file_groups || []);
      }
      
      if (docsRes.ok) {
        const data = await docsRes.json();
        setAvailableDocs(data.documents || []);
      }
    } catch (error) {
      console.error("Failed to fetch data", error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateChunk = async (e) => {
    e.preventDefault();
    if (!newChunkName.trim()) return;
    try {
      const res = await fetch(`${API_BASE}/file-groups`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newChunkName.trim() })
      });
      if (res.ok) {
        setNewChunkName('');
        fetchData();
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to create chunk");
      }
    } catch (error) {
      console.error("Error creating chunk", error);
    }
  };

  const handleDeleteChunk = async (chunkId) => {
    if (!window.confirm("Are you sure you want to delete this chunk?")) return;
    try {
      const res = await fetch(`${API_BASE}/file-groups/${chunkId}`, { method: 'DELETE' });
      if (res.ok) {
        fetchData();
      }
    } catch (error) {
      console.error("Error deleting chunk", error);
    }
  };

  const handleAddDocument = async (chunkId, documentId) => {
    try {
      const res = await fetch(`${API_BASE}/file-groups/${chunkId}/documents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ document_id: documentId })
      });
      if (res.ok) {
        fetchData();
      }
    } catch (error) {
      console.error("Error adding document", error);
    }
  };

  const handleRemoveDocument = async (chunkId, documentId) => {
    try {
      const res = await fetch(`${API_BASE}/file-groups/${chunkId}/documents/${documentId}`, { method: 'DELETE' });
      if (res.ok) {
        fetchData();
      }
    } catch (error) {
      console.error("Error removing document", error);
    }
  };

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      backgroundColor: 'rgba(15, 23, 42, 0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
    }}>
      <div style={{
        backgroundColor: '#ffffff', borderRadius: '16px', width: '90%', maxWidth: '850px',
        height: '85vh', display: 'flex', flexDirection: 'column', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)'
      }}>
        {/* Header */}
        <div style={{ padding: '24px', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#f8fafc', borderTopLeftRadius: '16px', borderTopRightRadius: '16px' }}>
          <div>
            <h2 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '12px', fontSize: '1.5rem', color: '#0f172a' }}>
              <Layers size={28} color="#8b5cf6" />
              Chunks Manager
            </h2>
            <p style={{ margin: '4px 0 0 0', color: '#64748b', fontSize: '0.9rem' }}>Group your files together into custom chunks</p>
          </div>
          <button onClick={onClose} style={{ background: '#f1f5f9', border: 'none', cursor: 'pointer', padding: '8px', borderRadius: '50%', color: '#64748b', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <X size={20} />
          </button>
        </div>
        
        {/* Create Bar */}
        <form onSubmit={handleCreateChunk} style={{ padding: '20px 24px', borderBottom: '1px solid #f1f5f9', display: 'flex', gap: '12px', backgroundColor: '#ffffff' }}>
          <div style={{ flex: 1, position: 'relative' }}>
            <FolderPlus size={20} color="#94a3b8" style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)' }} />
            <input 
              type="text" 
              placeholder="Name your new chunk..." 
              value={newChunkName} 
              onChange={(e) => setNewChunkName(e.target.value)}
              style={{ width: '100%', padding: '14px 14px 14px 44px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '1rem', outline: 'none', boxSizing: 'border-box' }}
            />
          </div>
          <button type="submit" disabled={!newChunkName.trim()} style={{
            padding: '0 24px', borderRadius: '8px', background: newChunkName.trim() ? '#8b5cf6' : '#c4b5fd', color: '#fff', border: 'none', cursor: newChunkName.trim() ? 'pointer' : 'not-allowed', fontWeight: '600', fontSize: '1rem', transition: 'all 0.2s'
          }}>
            Create Chunk
          </button>
        </form>

        {/* Chunks List */}
        <div style={{ padding: '24px', overflowY: 'auto', flex: 1, backgroundColor: '#f8fafc' }}>
          {loading ? (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: '#64748b' }}>Loading your chunks...</div>
          ) : chunks.length === 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8', gap: '16px' }}>
              <Layers size={48} strokeWidth={1} />
              <p style={{ margin: 0, fontSize: '1.1rem' }}>No chunks created yet. Build your first one above!</p>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '20px' }}>
              {chunks.map(chunk => {
                const isAdding = showAddDocs === chunk.id;
                const chunkDocs = chunk.documents || [];
                const unaddedDocs = availableDocs.filter(d => !chunkDocs.some(cd => cd.id === d.id));
                
                return (
                  <div key={chunk.id} style={{ 
                    backgroundColor: '#fff', border: '1px solid #e2e8f0', borderRadius: '12px', overflow: 'hidden', display: 'flex', flexDirection: 'column', boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
                  }}>
                    {/* Chunk Header */}
                    <div style={{ 
                        padding: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        borderBottom: '1px solid #e2e8f0'
                      }}
                    >
                      <div style={{ fontWeight: '600', color: '#0f172a', fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Database size={18} color="#8b5cf6" />
                        {chunk.name}
                      </div>
                      <button 
                        onClick={() => handleDeleteChunk(chunk.id)}
                        style={{ background: '#fee2e2', border: 'none', cursor: 'pointer', padding: '6px', borderRadius: '6px', color: '#ef4444', display: 'flex', alignItems: 'center' }}
                        title="Delete Chunk"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                    
                    {/* Chunk Files */}
                    <div style={{ padding: '16px', flex: 1 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                        <span style={{ fontSize: '0.85rem', fontWeight: '600', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Included Files ({chunkDocs.length})</span>
                        <button 
                          onClick={() => setShowAddDocs(isAdding ? null : chunk.id)}
                          style={{
                            background: isAdding ? '#f1f5f9' : '#eff6ff', border: 'none', borderRadius: '6px', cursor: 'pointer',
                            padding: '6px 12px', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', color: isAdding ? '#475569' : '#3b82f6', fontWeight: '600'
                          }}
                        >
                          {isAdding ? 'Done' : <><Plus size={14} /> Add File</>}
                        </button>
                      </div>

                      {/* Add File Panel */}
                      {isAdding && (
                        <div style={{ marginBottom: '16px', padding: '12px', backgroundColor: '#f8fafc', borderRadius: '8px', border: '1px dashed #cbd5e1' }}>
                          {unaddedDocs.length === 0 ? (
                            <div style={{ fontSize: '0.85rem', color: '#94a3b8', textAlign: 'center', padding: '8px 0' }}>All available files are already in this chunk.</div>
                          ) : (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '120px', overflowY: 'auto' }}>
                              {unaddedDocs.map(doc => (
                                <div key={doc.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 8px', backgroundColor: '#fff', borderRadius: '4px', border: '1px solid #e2e8f0' }}>
                                  <span style={{ fontSize: '0.85rem', color: '#334155', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', flex: 1, marginRight: '8px' }}>{doc.filename}</span>
                                  <button onClick={() => handleAddDocument(chunk.id, doc.id)} style={{ background: '#10b981', color: '#fff', border: 'none', borderRadius: '4px', padding: '4px 8px', fontSize: '0.75rem', cursor: 'pointer', fontWeight: 'bold' }}>Add</button>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}

                      {/* File List */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {chunkDocs.length === 0 ? (
                          <div style={{ padding: '16px', textAlign: 'center', backgroundColor: '#f8fafc', borderRadius: '8px', border: '1px dashed #e2e8f0', color: '#94a3b8', fontSize: '0.9rem' }}>
                            Empty chunk. Add files to get started.
                          </div>
                        ) : (
                          chunkDocs.map(doc => (
                            <div key={doc.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 12px', background: '#ffffff', borderRadius: '6px', border: '1px solid #e2e8f0', boxShadow: '0 1px 2px rgba(0,0,0,0.02)' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', overflow: 'hidden' }}>
                                <FileText size={16} color="#3b82f6" style={{ flexShrink: 0 }} />
                                <span style={{ fontSize: '0.9rem', color: '#334155', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={doc.filename}>{doc.filename}</span>
                              </div>
                              <button
                                onClick={() => handleRemoveDocument(chunk.id, doc.id)}
                                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8', padding: '4px', flexShrink: 0 }}
                                title="Remove file"
                              >
                                <X size={16} />
                              </button>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
