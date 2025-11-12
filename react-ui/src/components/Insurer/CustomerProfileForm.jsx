import React, { useState, useEffect } from 'react';

/**
 * This is a copy of the customer-facing ProfileForm,
 * adapted for the insurer to edit a customer's profile.
 */
export default function CustomerProfileForm({ customerId, initialProfile, onSave }) {
  const [name, setName] = useState('');
  const [dob, setDob] = useState('');
  const [gender, setGender] = useState('');
  const [smokingStatus, setSmokingStatus] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  
  // Stores the full profile to avoid overwriting other data
  const [fullProfile, setFullProfile] = useState(initialProfile || {});

  // Load data from the prop when it's available
  useEffect(() => {
    if (initialProfile) {
      setName(initialProfile.name || '');
      setDob(initialProfile.date_of_birth || '');
      setGender(initialProfile.gender || '');
      setSmokingStatus(initialProfile.smoking_status || '');
      setFullProfile(initialProfile);
    }
  }, [initialProfile]);

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

    // Call the onSave function passed from the parent tab
    const result = await onSave(updatedProfile);

    if (result.success) {
      setMessage("Profile saved successfully.");
      // The parent (CustomerProfileTab) will refetch and pass new props,
      // which will re-trigger the useEffect above to update the form.
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
          <label htmlFor={`name-${customerId}`} style={{ marginBottom: '4px', fontSize: '14px' }}>Full Name</label>
          <input
            id={`name-${customerId}`}
            type="text"
            className="form-input"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="e.g., Jane Doe"
          />
        </div>
        <div className="form-group" style={{ marginTop: '10px' }}>
          <label htmlFor={`dob-${customerId}`} style={{ marginBottom: '4px', fontSize: '14px' }}>Date of Birth</label>
          <input
            id={`dob-${customerId}`}
            type="date"
            className="form-input"
            value={dob}
            onChange={e => setDob(e.target.value)}
          />
        </div>

        <div className="form-group" style={{ marginTop: '10px' }}>
          <label htmlFor={`gender-${customerId}`} style={{ marginBottom: '4px', fontSize: '14px' }}>Gender</label>
          <select
            id={`gender-${customerId}`}
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
          <label htmlFor={`smoking-${customerId}`} style={{ marginBottom: '4px', fontSize: '14px' }}>Smoking Status</label>
          <select
            id={`smoking-${customerId}`}
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
          {loading ? 'Saving...' : 'Save Customer Info'}
        </button>

        {error && <p className="form-error" style={{ margin: '10px 0 0' }}>{error}</p>}
        {message && <p className="form-message" style={{ margin: '10px 0 0' }}>{message}</p>}
      </form>
    </div>
  );
}