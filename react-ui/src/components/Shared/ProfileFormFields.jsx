import React, { useState, useEffect } from 'react';

/**
 * A reusable "dumb" component that displays and manages the state
 * for the profile form fields. It doesn't know *how* to save,
 * it just calls a function prop.
 */
export default function ProfileFormFields({ 
  initialProfile, 
  onSave, 
  saveButtonText = "Save Info",
  // customerId is used to make form field 'id' attributes unique
  // which is important for accessibility.
  formIdPrefix = 'user' 
}) {
  
  const [name, setName] = useState('');
  const [dob, setDob] = useState('');
  const [gender, setGender] = useState('');
  const [smokingStatus, setSmokingStatus] = useState('');
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  // When the initialProfile prop changes (e.g., after a
  // parent refetch), update the local state.
  useEffect(() => {
    if (initialProfile) {
      setName(initialProfile.name || '');
      setDob(initialProfile.date_of_birth || '');
      setGender(initialProfile.gender || '');
      setSmokingStatus(initialProfile.smoking_status || '');
    }
  }, [initialProfile]);

  const handleSave = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setMessage('');

    // Construct the data to save, merging it with the
    // full profile to avoid overwriting other data
    const updatedProfile = {
      ...initialProfile,
      name: name,
      date_of_birth: dob,
      gender: gender,
      smoking_status: smokingStatus
    };

    // Call the save function passed in from the parent
    // The parent is responsible for the actual API call
    // and letting us know if it succeeded.
    const result = await onSave(updatedProfile);

    if (result.success) {
      setMessage(result.message || "Saved successfully.");
    } else {
      setError(result.error || "Failed to save profile.");
    }
    
    setLoading(false);
  };

  return (
    <div className="profile-form-container" style={{ marginBottom: '24px' }}>
      <h4>Customer Personal Info</h4>
      <form onSubmit={handleSave}>
        <div className="form-group">
          <label htmlFor={`name-${formIdPrefix}`} style={{ marginBottom: '4px', fontSize: '14px' }}>Full Name</label>
          <input
            id={`name-${formIdPrefix}`}
            type="text"
            className="form-input"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="e.g., Jane Doe"
          />
        </div>
        <div className="form-group" style={{ marginTop: '10px' }}>
          <label htmlFor={`dob-${formIdPrefix}`} style={{ marginBottom: '4px', fontSize: '14px' }}>Date of Birth</label>
          <input
            id={`dob-${formIdPrefix}`}
            type="date"
            className="form-input"
            value={dob}
            onChange={e => setDob(e.target.value)}
          />
        </div>
        <div className="form-group" style={{ marginTop: '10px' }}>
          <label htmlFor={`gender-${formIdPrefix}`} style={{ marginBottom: '4px', fontSize: '14px' }}>Gender</label>
          <select
            id={`gender-${formIdPrefix}`}
            className="form-input"
            value={gender}
            onChange={e => setGender(e.target.value)}
          >
            <option value="">Select gender</option>
            <option value="male">Male</option>
            <option value="female">Female</option>
          </select>
        </div>
        <div className="form-group" style={{ marginTop: '10px' }}>
          <label htmlFor={`smoking-${formIdPrefix}`} style={{ marginBottom: '4px', fontSize: '14px' }}>Smoking Status</label>
          <select
            id={`smoking-${formIdPrefix}`}
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
          {loading ? 'Saving...' : saveButtonText}
        </button>
        {error && <p className="form-error" style={{ margin: '10px 0 0' }}>{error}</p>}
        {message && <p className="form-message" style={{ margin: '10px 0 0' }}>{message}</p>}
      </form>
    </div>
  );
}