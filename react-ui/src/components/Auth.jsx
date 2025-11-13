// In react-ui/src/components/Auth.jsx
import React, { useState } from 'react';
// --- MODIFICATION: Import the new registerInsurer function ---
import { login, register, registerInsurer } from '../services/api';

export default function Auth({ onLogin }) {
  // --- MODIFICATION: Use authMode instead of isRegister ---
  const [authMode, setAuthMode] = useState('login'); // 'login', 'registerCustomer', 'registerInsurer'
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [inviteCode, setInviteCode] = useState(''); // --- ADDED: State for invite code
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');
    
    try {
      if (authMode === 'login') {
        const loginData = await login(username, password); // Returns { access_token, role }
        onLogin(loginData); // Pass full data to App.jsx
      } else {
        // Common registration validation
        if (password !== passwordConfirm) {
          setError('Passwords do not match.');
          return;
        }

        if (authMode === 'registerCustomer') {
          await register(username, password, passwordConfirm);
          setMessage('Registration successful! Please log in.');
          setAuthMode('login'); // Switch to login view
        } else if (authMode === 'registerInsurer') {
          if (!inviteCode) {
            setError('Invite code is required.');
            return;
          }
          await registerInsurer(username, password, passwordConfirm, inviteCode);
          setMessage('Insurer registration successful! Please log in.');
          setAuthMode('login'); // Switch to login view
        }
      }
    } catch (e) {
      setError(e.message);
    }
  };

  const getTitle = () => {
    if (authMode === 'login') return 'Login';
    if (authMode === 'registerCustomer') return 'Register (Customer)';
    if (authMode === 'registerInsurer') return 'Register (Insurer)';
  };
  
  const isRegistering = authMode !== 'login';

  return (
    <div className="auth-container">
      <div className="auth-box">
        <h2>{getTitle()}</h2>
        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              required
              className="form-input"
            />
          </div>
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              className="form-input"
            />
          </div>

          {/* Show for both registration types */}
          {isRegistering && (
            <div className="form-group">
              <label htmlFor="passwordConfirm">Re-enter Password</label>
              <input
                id="passwordConfirm"
                type="password"
                value={passwordConfirm}
                onChange={e => setPasswordConfirm(e.target.value)}
                required
                className="form-input"
              />
            </div>
          )}

          {/* Show ONLY for insurer registration */}
          {authMode === 'registerInsurer' && (
            <div className="form-group">
              <label htmlFor="inviteCode">Invite Code</label>
              <input
                id="inviteCode"
                type="password" // Use password type to hide the code
                value={inviteCode}
                onChange={e => setInviteCode(e.target.value)}
                required
                className="form-input"
                placeholder="Enter your insurer invite code"
              />
            </div>
          )}

          {error && <p className="form-error">{error}</p>}
          {message && <p className="form-message">{message}</p>}

          <button type="submit" className="btn primary form-button">
            {isRegistering ? 'Register' : 'Login'}
          </button>
        </form>
        
        {/* --- MODIFICATION: New auth mode toggles --- */}
        {authMode === 'login' && (
          <>
            <button
              type="button"
              onClick={() => { setAuthMode('registerCustomer'); setError(''); setMessage(''); }}
              className="form-switch-link"
            >
              Don't have an account? Register as Customer
            </button>
            <button
              type="button"
              onClick={() => { setAuthMode('registerInsurer'); setError(''); setMessage(''); }}
              className="form-switch-link"
              style={{ marginTop: '8px' }}
            >
              Are you an Insurer? Register here
            </button>
          </>
        )}
        
        {isRegistering && (
           <button
            type="button"
            onClick={() => { setAuthMode('login'); setError(''); setMessage(''); }}
            className="form-switch-link"
          >
            Already have an account? Login
          </button>
        )}
      </div>
    </div>
  );
}