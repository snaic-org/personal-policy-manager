import React, { useState, useEffect } from 'react';
import Chat from './components/Chat';
import Auth from './components/Auth';
import Sidebar from './components/Sidebar';
import { logout, getUserInfo } from './services/api';

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [refresh, setRefresh] = useState(false);
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
    // This is the main container for the whole app
    <div className="app-container">
      <header className="app-header">
        <h2>Personal Policy Manager</h2>
        {token && (
          <button onClick={handleLogout} className="logout-button-header">
            Logout
          </button>
        )}
      </header>
      
      <div className="app-main-content">
        {token ? (
          <div className="app-layout">
            <Sidebar
              user={user}
              onUploadSuccess={handleUploadSuccess}
              refreshTrigger={refresh}
            />
            <Chat 
              onUploadSuccess={handleUploadSuccess} 
            />
          </div>
        ) : (
          <Auth onLogin={handleLogin} />
        )}
      </div>
    </div>
  );
}