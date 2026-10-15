import React from 'react';
import { useNavigate } from 'react-router-dom';
import DatabaseExplorer from './DatabaseExplorer';

export default function Admin() {
  const navigate = useNavigate();
  return <DatabaseExplorer onClose={() => navigate('/')} />;
}
