import React, { useState, useEffect } from 'react';
import { getProfile, saveProfile } from '../services/api';

export default function ProfileForm() {
  const [name, setName] = useState('');
  const [dob, setDob] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [fullProfile, setFullProfile] = useState({}); // To store the whole profile

  useEffect(() => {
    setLoading(true);
    getProfile()
      .then(data => {
        setName(data.name || '');
        setDob(data.date_of_birth || '');
        setFullProfile(data); // Store the full object
      })
      .catch(err => {
        setError(err.message);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  const handleSave = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setMessage('');

    // Merge new data into the full profile object
    const updatedProfile = {
      ...fullProfile,
      name: name,
      date_of_birth: dob
      // Add other fields like gender, smoking_status here
    };

    try {
      const res = await saveProfile(updatedProfile);
      setMessage(res.message);
      setFullProfile(updatedProfile); // Keep our state in sync
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="profile-form-container" style={{ marginBottom: '24px' }}>
      <h4>Your Personal Info</h4>
      <form onSubmit={handleSave}>
        <div className="form-group">
          <label htmlFor="name" style={{ marginBottom: '4px', fontSize: '14px' }}>Full Name</label>
          <input
            id="name"
            type="text"
            className="form-input"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="e.g., Jane Doe"
          />
        </div>
        <div className="form-group" style={{ marginTop: '10px' }}>
          <label htmlFor="dob" style={{ marginBottom: '4px', fontSize: '14px' }}>Date of Birth</label>
          <input
            id="dob"
            type="date"
            className="form-input"
            value={dob}
            onChange={e => setDob(e.target.value)}
          />
        </div>
        
        <button 
          type="submit" 
          className="btn primary" 
          disabled={loading}
          style={{ width: '100%', marginTop: '10px' }}
        >
          {loading ? 'Saving...' : 'Save Info'}
        </button>

        {error && <p className="form-error" style={{ margin: '10px 0 0' }}>{error}</p>}
        {message && <p className="form-message" style={{ margin: '10px 0 0' }}>{message}</p>}
      </form>
    </div>
  );
}