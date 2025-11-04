import React, { useState, useEffect } from 'react';
import Chat from './components/Chat';
import Auth from './components/Auth';
import { logout, getUserInfo } from './services/api';
import Upload from './components/Upload';
import UploadedFiles from './components/UploadedFiles';

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [refresh, setRefresh] = useState(false);
  const [history, setHistory] = useState([]);
  const [user, setUser] = useState(null);

  const handleLogin = (newToken) => {
    setToken(newToken);
  };

  const handleLogout = () => {
    logout();
    setToken(null);
    setUser(null); // Clear user info on logout
  };
  
  const handleUploadSuccess = () => {
    // addMessage('bot', 'Your documents have been processed. You can now ask questions about them.');
    setRefresh(prev => !prev); // triggers UploadedFiles to re-fetch
  };

  // Fetch user info when token is available
  useEffect(() => {
    if (token) {
      getUserInfo()
        .then(setUser)
        .catch(err => {
          console.error("Failed to fetch user info, logging out.", err);
          handleLogout(); // Log out if token is bad or expired
        });
    } else {
      setUser(null); // Clear user if token is gone
    }
  }, [token]); // Re-run this effect if the token changes

  return (
    <div style={{ maxWidth: 2000, margin: '0 auto', fontFamily: 'Arial, sans-serif' }}>
      <div className="app-header">
        <h2>Personal Policy Manager</h2>
        {token && <button className="btn primary login" onClick={handleLogout} style={{position: 'absolute', right: 20, top: 20}}>Logout</button>}
      </div>
      
      {token ? (
        <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
          {/* Sidebar */}
          <aside style={{ width: 320, borderRight: '5px solid #eee', padding: '10px 16px',maxHeight: '80vh', minHeight: '70vh', paddingTop: 50, overflowY: 'auto' }}>
            <div style={{ padding: '10px 16px', borderBottom: '1px solid #eee', marginBottom: 20 }}>
              <h4 style={{ margin: 0, color: '#555', fontWeight: 500 }}>
                Welcome!
              </h4>
              <h3 style={{ margin: '4px 0 0', color: '#111' }}>
                {user ? user.username : 'Loading...'}
              </h3>
            </div>
            <Upload onUploadSuccess={handleUploadSuccess} refreshTrigger={refresh} />
            <UploadedFiles refreshTrigger={refresh} />
          </aside>  
          {/* Chat */}
          <div style={{ flex: 1 }}>
            <Chat />
              history={history}
              addMessage={(role, text) => addMessage(role, text)}
          </div>
        </div>
      ) : (
        <Auth onLogin={handleLogin} />
      )}
    </div>
  );
}