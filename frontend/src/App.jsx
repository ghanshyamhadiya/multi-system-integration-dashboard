import { useState, useEffect, useRef } from 'react';
import axios from 'axios';

function App() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState('');
  
  const [logsOpen, setLogsOpen] = useState(false);
  const [logs, setLogs] = useState([]);
  const fileInputRef = useRef(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await axios.get('http://localhost:8000/get-merged-data');
      setData(response.data.data);
    } catch (err) {
      console.error('Error fetching data:', err);
      setError('Failed to fetch data from the server. Ensure the backend is running.');
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await fetchData();
  };

  const handleSync = async () => {
    try {
      setIsSyncing(true);
      setSyncMessage('');
      setError(null);
      const response = await axios.post('http://localhost:8000/sync-data');
      setSyncMessage(response.data.message || 'Sync successful!');
      await fetchData();
    } catch (err) {
      console.error('Error syncing data:', err);
      setError('Failed to sync data with the backend.');
    } finally {
      setIsSyncing(false);
      setTimeout(() => setSyncMessage(''), 5000);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      setIsSyncing(true);
      setSyncMessage('');
      setError(null);
      const response = await axios.post('http://localhost:8000/upload-csv', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setSyncMessage(response.data.message || 'Upload successful!');
      await fetchData();
    } catch (err) {
      console.error('Error uploading CSV:', err);
      setError(err.response?.data?.detail || 'Failed to upload CSV.');
    } finally {
      setIsSyncing(false);
      e.target.value = null;
      setTimeout(() => setSyncMessage(''), 5000);
    }
  };

  const fetchLogs = async () => {
    try {
      const res = await axios.get('http://localhost:8000/logs');
      setLogs(res.data.logs);
      setLogsOpen(true);
    } catch (e) {
      console.error(e);
      setError('Failed to fetch logs');
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const getSourceBadgeClass = (source) => {
    if (source.includes('Both')) return 'badge badge-both';
    if (source.includes('Database')) return 'badge badge-db';
    return 'badge badge-api';
  };

  return (
    <div className="dashboard-container">
      <div className="header">
        <div>
          <h1 className="title">Multi-System Integration</h1>
          <p className="subtitle">Data merged from external API and local SQLite DB</p>
        </div>
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <input 
            type="file" 
            accept=".csv" 
            ref={fileInputRef} 
            style={{ display: 'none' }} 
            onChange={handleFileUpload} 
          />
          <button 
            className="btn-secondary" 
            onClick={() => fileInputRef.current.click()}
            disabled={loading || isRefreshing || isSyncing}
          >
            Upload CSV
          </button>
          <button 
            className="btn-secondary" 
            onClick={fetchLogs}
          >
            View Logs
          </button>
          <button 
            className="btn-sync" 
            onClick={handleSync}
            disabled={loading || isRefreshing || isSyncing}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: "6px"}}>
              <path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"></path>
              <path d="M21 3v5h-5"></path>
            </svg>
            {isSyncing ? 'Syncing...' : 'Sync Data'}
          </button>
          <button 
            className="btn-refresh" 
            onClick={handleRefresh}
            disabled={loading || isRefreshing || isSyncing}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: "6px"}}>
              <path d="M21 2v6h-6"></path>
              <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path>
              <path d="M3 3v5h5"></path>
            </svg>
            {isRefreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {syncMessage && (
        <div className="success-banner">
          {syncMessage}
        </div>
      )}

      {loading && !isRefreshing ? (
        <div className="state-container">
          <div className="spinner"></div>
          <p>Loading integrated data...</p>
        </div>
      ) : error ? (
        <div className="state-container">
          <div className="error-text">{error}</div>
          <button className="btn-refresh" onClick={fetchData}>Try Again</button>
        </div>
      ) : (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Email</th>
                <th>Domain</th>
                <th>Data Source</th>
              </tr>
            </thead>
            <tbody>
              {data.map((user) => (
                <tr key={user.id}>
                  <td>{user.id}</td>
                  <td>{user.name}</td>
                  <td>{user.email}</td>
                  <td>{user.domain || '-'}</td>
                  <td>
                    <span className={getSourceBadgeClass(user.source)}>
                      {user.source}
                    </span>
                  </td>
                </tr>
              ))}
              {data.length === 0 && (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center', padding: '2rem' }}>
                    No data available. Click "Sync Data" or upload a CSV to seed database.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {logsOpen && (
        <div className="modal-overlay" onClick={() => setLogsOpen(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>System Logs</h3>
              <button className="btn-secondary" onClick={() => setLogsOpen(false)} style={{ padding: '0.25rem 0.75rem' }}>Close</button>
            </div>
            <div className="logs-container">
              {logs.length === 0 ? (
                <p style={{ color: 'var(--text-secondary)' }}>No logs available yet.</p>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className={`log-entry log-${log.level.toLowerCase()}`}>
                    <span className="log-time">{new Date(log.timestamp).toLocaleTimeString()}</span>
                    <span className="log-level">[{log.level}]</span>
                    <span className="log-msg">{log.message}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
