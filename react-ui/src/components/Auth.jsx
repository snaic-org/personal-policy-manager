import React, { useState } from 'react';
import { login, register } from '../services/api';

export default function Auth({ onLogin }) {
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');
    try {
      if (isRegister) {
        if (password !== passwordConfirm) {
          setError('Passwords do not match.');
          return;
        }
        await register(username, password, passwordConfirm);
        setMessage('Registration successful! Please log in.');
        setIsRegister(false);
      } else {
        const token = await login(username, password);
        onLogin(token);
      }
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-box">
        <h2>{isRegister ? 'Register' : 'Login'}</h2>
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

          {isRegister && (
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

          {error && <p className="form-error">{error}</p>}
          {message && <p className="form-message">{message}</p>}

          <button type="submit" className="btn primary form-button">
            {isRegister ? 'Register' : 'Login'}
          </button>
        </form>
        
        <button
          type="button"
          onClick={() => { setIsRegister(!isRegister); setError(''); setMessage(''); }}
          className="form-switch-link"
        >
          {isRegister ? 'Already have an account? Login' : "Don't have an account? Register"}
        </button>
      </div>
    </div>
  );
}