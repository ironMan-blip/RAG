import React from 'react';
import { useNavigate } from 'react-router-dom';
import DatabaseExplorer from './DatabaseExplorer';

const DOCUMENTS_URL = 'http://localhost:8000/api/documents';
const UPLOAD_URL = 'http://localhost:8000/api/upload';

export default function Admin() {
  const navigate = useNavigate();
  return (
    <DatabaseExplorer 
      onClose={() => navigate('/')} 
      documentsUrl={DOCUMENTS_URL} 
      uploadUrl={UPLOAD_URL} 
    />
  );
}
