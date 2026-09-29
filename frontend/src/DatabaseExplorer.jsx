import React, { useState, useEffect } from 'react';
import { X, FileText, Database as DatabaseIcon } from 'lucide-react';

export default function DatabaseExplorer({ onClose, documentsUrl }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);

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
                  <div style={{ 
                      padding: '15px', 
                      display: 'flex', 
                      alignItems: 'center', 
                      backgroundColor: '#fff'
                    }}
                  >
                    <FileText size={20} color="#3b82f6" style={{ marginRight: '10px' }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 'bold', color: '#1e293b' }}>{doc.filename}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
