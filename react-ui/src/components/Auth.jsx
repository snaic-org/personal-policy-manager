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
    <div style={{ maxWidth: 400, margin: '40px auto', padding: 20, border: '1px solid #ccc', borderRadius: 8 }}>
      <h2>{isRegister ? 'Register' : 'Login'}</h2>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: 10 }}>
          <label>Username: </label>
          <input 
            type="text" 
            value={username} 
            onChange={e => setUsername(e.target.value)} 
            required 
            style={{ width: '100%', boxSizing: 'border-box' }}
          />
        </div>
        <div style={{ marginBottom: 10 }}>
          <label>Password: </label>
          <input 
            type="password" 
            value={password} 
            onChange={e => setPassword(e.target.value)} 
            required 
            style={{ width: '100%', boxSizing: 'border-box' }}
          />
        </div>

        {isRegister && (
          <div style={{ marginBottom: 10 }}>
            <label>Re-enter Password: </label>
            <input 
              type="password" 
              value={passwordConfirm} 
              onChange={e => setPasswordConfirm(e.target.value)} 
              required 
              style={{ width: '100%', boxSizing: 'border-box' }}
            />
          </div>
        )}

        <button type="submit" style={{ width: '100%', padding: '8px' }}>
          {isRegister ? 'Register' : 'Login'}
        </button>
      </form>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {message && <p style={{ color: 'green' }}>{message}</p>}
      
      <button 
        onClick={() => { setIsRegister(!isRegister); setError(''); setMessage(''); }}
        style={{ width: '100%', marginTop: '10px', background: 'none', border: '1px solid #ccc', padding: '8px' }}
      >
        {isRegister ? 'Switch to Login' : 'Switch to Register'}
      </button>
    </div>
  );
}