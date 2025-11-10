import React, { useState, useEffect } from 'react';
import { getProfile, saveProfile } from '../services/api';

export default function ProfileForm() {
  const [name, setName] = useState('');
  const [dob, setDob] = useState('');
  const [gender, setGender] = useState('');
  const [smokingStatus, setSmokingStatus] = useState('');
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
        setGender(data.gender || '');
        setSmokingStatus(data.smoking_status || '');
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
      date_of_birth: dob,
      gender: gender,
      smoking_status: smokingStatus
    };

    try {
      const res = await saveProfile(updatedProfile);
      setMessage(res.message);

      // Refetch profile to get the merged data from backend
      const refreshedProfile = await getProfile();
      setFullProfile(refreshedProfile);
      setName(refreshedProfile.name || '');
      setDob(refreshedProfile.date_of_birth || '');
      setGender(refreshedProfile.gender || '');
      setSmokingStatus(refreshedProfile.smoking_status || '');
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

        <div className="form-group" style={{ marginTop: '10px' }}>
          <label htmlFor="gender" style={{ marginBottom: '4px', fontSize: '14px' }}>Gender</label>
          <select
            id="gender"
            className="form-input"
            value={gender}
            onChange={e => setGender(e.target.value)}
          >
            <option value="">Select gender</option>
            <option value="male">Male</option>
            <option value="female">Female</option>
            {/* <option value="other">Other</option>
            <option value="prefer_not_to_say">Prefer not to say</option> */}
          </select>
        </div>

        <div className="form-group" style={{ marginTop: '10px' }}>
          <label htmlFor="smokingStatus" style={{ marginBottom: '4px', fontSize: '14px' }}>Smoking Status</label>
          <select
            id="smokingStatus"
            className="form-input"
            value={smokingStatus}
            onChange={e => setSmokingStatus(e.target.value)}
          >
            <option value="">Select smoking status</option>
            <option value="non-smoker">Non-smoker</option>
            <option value="smoker">Smoker</option>
            <option value="ex-smoker">Ex-smoker</option>
          </select>
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