import React, { useState, useEffect } from 'react';
import Auth from './components/Auth';
import CustomerLayout from './components/CustomerLayout';
import InsurerLayout from './components/InsurerLayout';
import { logout, getUserInfo } from './services/api';

// Helper to get role from stored token
const getRoleFromToken = () => {
  const token = localStorage.getItem('token');
  if (!token) return null;
  try {
    const claims = JSON.parse(atob(token.split('.')[1]));
    return claims.role;
  } catch (e) {
    return null;
  }
};

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [role, setRole] = useState(getRoleFromToken()); // Get role on load
  const [user, setUser] = useState(null);

  const handleLogin = (loginData) => { // loginData is { token, role }
    setToken(loginData.access_token);
    setRole(loginData.role);
  };

  const handleLogout = () => {
    logout();
    setToken(null);
    setRole(null);
    setUser(null);
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

  const renderLayout = () => {
    if (!token || !role) {
      return <Auth onLogin={handleLogin} />;
    }

    if (role === 'customer') {
      return <CustomerLayout user={user} onLogout={handleLogout} />;
    }

    if (role === 'insurer') {
      return <InsurerLayout user={user} onLogout={handleLogout} />;
    }

    return <Auth onLogin={handleLogin} />; // Fallback
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h2>{role === 'insurer' ? 'Insurer Policy Manager' : 'Personal Policy Manager'}</h2>
        {token && (
          <button onClick={handleLogout} className="logout-button-header">
            Logout
          </button>
        )}
      </header>

      <div className="app-main-content">
        {renderLayout()}
      </div>
    </div>
  );
}