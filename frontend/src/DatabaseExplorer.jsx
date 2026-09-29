import React, { useState, useEffect } from 'react';
import { X, FileText, Database as DatabaseIcon, ChevronRight, ChevronDown } from 'lucide-react';

export default function DatabaseExplorer({ onClose, documentsUrl }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedDoc, setExpandedDoc] = useState(null);
  const [docDetails, setDocDetails] = useState({});
  const [loadingDetails, setLoadingDetails] = useState(false);

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    try {
      const res = await fetch(documentsUrl);
      if (res.ok) {
        const data = await res.json();
        setDocuments(data.documents || []);
      }
    } catch (error) {
      console.error("Failed to fetch documents", error);
    } finally {
      setLoading(false);
    }
  };

  const toggleDocument = async (docId) => {
    if (expandedDoc === docId) {
      setExpandedDoc(null);
      return;
    }
    
    setExpandedDoc(docId);
    
    // Fetch chunks if we haven't already
    if (!docDetails[docId]) {
      setLoadingDetails(true);
      try {
        const [contentRes, chunksRes] = await Promise.all([
          fetch(`${documentsUrl}/${docId}/content`),
          fetch(`http://localhost:8000/api/documents/${docId}/chunks`)
        ]);
        
        let contentData = null;
        let chunksData = null;
        
        if (contentRes.ok) contentData = await contentRes.json();
        if (chunksRes.ok) chunksData = await chunksRes.json();
        
        setDocDetails(prev => ({
          ...prev,
          [docId]: {
            content: contentData?.extracted_text || "No content found.",
            chunks: chunksData?.chunks || []
          }
        }));
      } catch (error) {
        console.error("Error fetching doc details:", error);
      } finally {
        setLoadingDetails(false);
      }
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0, left: 0, right: 0, bottom: 0,
      backgroundColor: 'rgba(0,0,0,0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000
    }}>
      <div style={{
        backgroundColor: '#fff',
        borderRadius: '12px',
        width: '80%',
        maxWidth: '800px',
        height: '80vh',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)'
      }}>
        <div style={{
          padding: '20px',
          borderBottom: '1px solid #e2e8f0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <h2 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '10px', fontSize: '1.25rem' }}>
            <DatabaseIcon size={24} color="#3b82f6" />
            Database Explorer
          </h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '5px' }}>
            <X size={24} color="#64748b" />
          </button>
        </div>

        <div style={{ padding: '20px', overflowY: 'auto', flex: 1, backgroundColor: '#f8fafc' }}>
          {loading ? (
            <p style={{ textAlign: 'center', color: '#64748b' }}>Loading database records...</p>
          ) : documents.length === 0 ? (
            <p style={{ textAlign: 'center', color: '#64748b' }}>No documents found in the database.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {documents.map(doc => (
                <div key={doc.id} style={{ 
                  backgroundColor: '#fff', 
                  border: '1px solid #e2e8f0', 
                  borderRadius: '8px',
                  overflow: 'hidden'
                }}>
                  <div 
                    onClick={() => toggleDocument(doc.id)}
                    style={{ 
                      padding: '15px', 
                      display: 'flex', 
                      alignItems: 'center', 
                      cursor: 'pointer',
                      backgroundColor: expandedDoc === doc.id ? '#f1f5f9' : '#fff'
                    }}
                  >
                    {expandedDoc === doc.id ? <ChevronDown size={20} color="#64748b" style={{ marginRight: '10px' }} /> : <ChevronRight size={20} color="#64748b" style={{ marginRight: '10px' }} />}
                    <FileText size={20} color="#3b82f6" style={{ marginRight: '10px' }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 'bold', color: '#1e293b' }}>{doc.filename}</div>
                      <div style={{ fontSize: '12px', color: '#64748b' }}>ID: {doc.id} | Hash: {doc.file_hash?.substring(0, 8)}...</div>
                    </div>
                  </div>
                  
                  {expandedDoc === doc.id && (
                    <div style={{ padding: '15px', borderTop: '1px solid #e2e8f0', backgroundColor: '#fafafa' }}>
                      {loadingDetails && !docDetails[doc.id] ? (
                        <p style={{ fontSize: '14px', color: '#64748b' }}>Loading details...</p>
                      ) : docDetails[doc.id] ? (
                        <div>
                          <h4 style={{ margin: '0 0 10px 0', fontSize: '14px', color: '#334155' }}>Extracted Content Preview:</h4>
                          <div style={{ 
                            backgroundColor: '#fff', 
                            padding: '10px', 
                            borderRadius: '6px', 
                            border: '1px solid #e2e8f0',
                            fontSize: '13px',
                            maxHeight: '150px',
                            overflowY: 'auto',
                            marginBottom: '15px',
                            whiteSpace: 'pre-wrap',
                            color: '#475569'
                          }}>
                            {docDetails[doc.id].content}
                          </div>
                          
                          <h4 style={{ margin: '0 0 10px 0', fontSize: '14px', color: '#334155' }}>Database Chunks ({docDetails[doc.id].chunks?.length || 0}):</h4>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            {docDetails[doc.id].chunks?.map(chunk => (
                              <div key={chunk.chunk_id} style={{
                                backgroundColor: '#fff',
                                padding: '10px',
                                borderRadius: '6px',
                                border: '1px solid #e2e8f0',
                                fontSize: '12px',
                                color: '#475569'
                              }}>
                                <span style={{ fontWeight: 'bold', marginRight: '5px', color: '#3b82f6' }}>#{chunk.chunk_id}</span>
                                {chunk.chunk_text}
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <p>Failed to load details.</p>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
