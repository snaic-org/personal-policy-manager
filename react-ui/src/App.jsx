import React, { useState } from 'react';
import Chat from './components/Chat';
import Auth from './components/Auth';
import { logout } from './services/api';
import Upload from './components/Upload';
import UploadedFiles from './components/UploadedFiles';

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [refresh, setRefresh] = useState(false);
  const [uploadEvent, setUploadEvent] = useState(0);

  const handleLogin = (newToken) => {
    setToken(newToken);
  };

  const handleLogout = () => {
    logout();
    setToken(null);
  };

  return (
    <div style={{ maxWidth: 2000, margin: '0 auto', fontFamily: 'Arial, sans-serif' }}>
      <div className="app-header">
        <h2>Personal Policy Manager</h2>
        {token && <button onClick={handleLogout} style={{position: 'absolute', right: 20, top: 20}}>Logout</button>}
      </div>
      
      {token ? (
        <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
          {/* Sidebar */}
          <aside style={{ width: 320, borderRight: '1px solid #eee', padding: '10px 16px', minHeight: '70vh' }}>
            <h3 style={{ marginTop: 0 }}>Your Files</h3>
            <Upload onUploadSuccess={() => { setRefresh(prev => !prev); setUploadEvent(n => n + 1); }} />
            <UploadedFiles refreshTrigger={refresh} />
          </aside>

          {/* Main chat area */}
          <main style={{ flex: 1 }}>
            <Chat uploadEvent={uploadEvent} />
          </main>
        </div>
      ) : (
        <Auth onLogin={handleLogin} />
      )}
    </div>
  );
}