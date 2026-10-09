import React, { useState, useEffect } from 'react';
import { Database, Table as TableIcon, ArrowLeft, RefreshCw, Server, AlertCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function DatabasePage() {
  const navigate = useNavigate();
  const [tables, setTables] = useState([]);
  const [selectedTable, setSelectedTable] = useState(null);
  const [tableData, setTableData] = useState({ columns: [], data: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchTables();
  }, []);

  const fetchTables = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/admin/tables');
      if (res.ok) {
        const data = await res.json();
        setTables(data.tables || []);
        if (data.tables && data.tables.length > 0) {
          fetchTableData(data.tables[0]);
        }
      } else {
        setError('Failed to fetch tables');
      }
    } catch (err) {
      setError('Could not connect to database server');
    }
  };

  const fetchTableData = async (tableName) => {
    setSelectedTable(tableName);
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`http://localhost:8000/api/admin/tables/${tableName}`);
      if (res.ok) {
        const data = await res.json();
        setTableData(data);
      } else {
        setError(`Failed to fetch data for ${tableName}`);
      }
    } catch (err) {
      setError('Could not connect to database server');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col font-sans">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-4">
          <button 
            onClick={() => navigate(-1)}
            className="p-2 -ml-2 text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors flex items-center gap-2"
          >
            <ArrowLeft className="w-5 h-5" />
            <span className="font-medium text-sm hidden sm:inline">Back to App</span>
          </button>
          
          <div className="h-6 w-px bg-gray-200"></div>
          
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
              <Server className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900 leading-tight">Database Administration</h1>
              <p className="text-xs text-gray-500">Manage and view your application data</p>
            </div>
          </div>
        </div>
        
        <button 
          onClick={() => selectedTable ? fetchTableData(selectedTable) : fetchTables()}
          className="px-4 py-2 bg-white border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 flex items-center gap-2 transition-colors shadow-sm"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="w-64 bg-white border-r border-gray-200 overflow-y-auto flex-shrink-0">
          <div className="p-4 border-b border-gray-100 bg-gray-50/50">
            <h2 className="text-xs font-bold text-gray-500 uppercase tracking-wider flex items-center gap-2">
              <Database className="w-4 h-4" />
              Public Schema
            </h2>
          </div>
          <div className="p-2">
            <ul className="space-y-0.5">
              {tables.map(table => (
                <li key={table}>
                  <button
                    onClick={() => fetchTableData(table)}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 text-sm rounded-md transition-all ${
                      selectedTable === table 
                        ? 'bg-indigo-50 text-indigo-700 font-semibold shadow-sm ring-1 ring-indigo-500/20' 
                        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900 font-medium'
                    }`}
                  >
                    <TableIcon className={`w-4 h-4 ${selectedTable === table ? 'text-indigo-600' : 'text-gray-400'}`} />
                    {table}
                  </button>
                </li>
              ))}
              {tables.length === 0 && !error && (
                <div className="p-4 text-center text-sm text-gray-500 italic">No tables found</div>
              )}
            </ul>
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 overflow-auto bg-gray-50/50 p-6">
          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3 text-red-700">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="font-semibold text-sm">Error</h3>
                <p className="text-sm mt-1">{error}</p>
              </div>
            </div>
          )}

          {!selectedTable ? (
            <div className="h-full flex flex-col items-center justify-center text-gray-400 space-y-4">
              <div className="p-4 bg-gray-100 rounded-full">
                <Database className="w-12 h-12 text-gray-300" />
              </div>
              <p className="text-lg font-medium text-gray-500">Select a table to view its contents</p>
            </div>
          ) : (
            <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden flex flex-col h-full max-h-[calc(100vh-8rem)]">
              <div className="px-6 py-4 border-b border-gray-200 bg-white flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <h2 className="text-lg font-bold text-gray-900 capitalize">{selectedTable}</h2>
                  <span className="px-2.5 py-0.5 bg-gray-100 text-gray-600 text-xs font-semibold rounded-full border border-gray-200">
                    {tableData.data.length} {tableData.data.length === 100 ? '+ rows (limited)' : 'rows'}
                  </span>
                </div>
              </div>
              
              <div className="flex-1 overflow-auto bg-white">
                {loading && tableData.data.length === 0 ? (
                  <div className="h-full flex items-center justify-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
                  </div>
                ) : tableData.data.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center py-16 text-gray-400">
                    <TableIcon className="w-12 h-12 mb-4 text-gray-200" />
                    <p className="text-base font-medium text-gray-500">No data found in this table</p>
                    <p className="text-sm mt-1">This table is currently empty.</p>
                  </div>
                ) : (
                  <table className="min-w-full text-sm text-left">
                    <thead className="text-xs text-gray-600 uppercase bg-gray-50/80 sticky top-0 z-10 border-b border-gray-200 shadow-sm backdrop-blur-sm">
                      <tr>
                        {tableData.columns.map((col, i) => (
                          <th key={i} className="px-6 py-3.5 font-bold tracking-wider whitespace-nowrap">
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {tableData.data.map((row, i) => (
                        <tr key={i} className="hover:bg-indigo-50/30 transition-colors group">
                          {tableData.columns.map((col, j) => (
                            <td key={j} className="px-6 py-4 whitespace-nowrap text-gray-700 font-medium group-hover:text-gray-900">
                              {!row[col].is_null ? (
                                row[col].original.length > 60 ? (
                                  <span title={row[col].original}>{row[col].display}</span>
                                ) : row[col].display
                              ) : (
                                <span className="text-gray-400 italic font-normal">NULL</span>
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
