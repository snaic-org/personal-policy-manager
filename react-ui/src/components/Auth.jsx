import React, { useState } from 'react';
import { login, register } from '../services/api';

export default function Auth({ onLogin }) {
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');
    try {
      if (isRegister) {
        await register(username, password);
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
          />
        </div>
        <div style={{ marginBottom: 10 }}>
          <label>Password: </label>
          <input 
            type="password" 
            value={password} 
            onChange={e => setPassword(e.target.value)} 
            required 
          />
        </div>
        <button type="submit">{isRegister ? 'Register' : 'Login'}</button>
      </form>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {message && <p style={{ color: 'green' }}>{message}</p>}
      <button onClick={() => { setIsRegister(!isRegister); setError(''); setMessage(''); }}>
        {isRegister ? 'Switch to Login' : 'Switch to Register'}
      </button>
    </div>
  );
}