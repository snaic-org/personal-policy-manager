import React, { useState } from 'react';
import Chat from './components/Chat';
import Auth from './components/Auth';
import { logout } from './services/api';

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));

  const handleLogin = (newToken) => {
    setToken(newToken);
  };

  const handleLogout = () => {
    logout();
    setToken(null);
  };

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', fontFamily: 'Arial, sans-serif' }}>
      <div className="app-header">
        <h2>Personal Policy Manager</h2>
        {token && <button onClick={handleLogout} style={{position: 'absolute', right: 20, top: 20}}>Logout</button>}
      </div>
      
      {token ? (
        <Chat />
      ) : (
        <Auth onLogin={handleLogin} />
      )}
    </div>
  );
}