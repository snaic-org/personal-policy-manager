import React, { useState, useEffect, useCallback } from 'react';
import { getProfile, saveProfile, getUserFiles } from '../services/api';

export default function PolicyTiers({ refreshTrigger }) {
  const [files, setFiles] = useState([]);
  const [profile, setProfile] = useState({});
  const [tiers, setTiers] = useState({}); // Local state for tier inputs
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  // Fetches all data needed
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [profileData, filesData] = await Promise.all([
        getProfile(),
        getUserFiles()
      ]);
      
      setProfile(profileData);
      setFiles(filesData.files || []);
      
      // Initialize local tiers state from profile
      setTiers(profileData.policy_tiers || {});
      
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData, refreshTrigger]); // Refetch when files change

  const handleTierChange = (filename, value) => {
    setTiers(prevTiers => ({
      ...prevTiers,
      [filename]: value
    }));
  };

  const handleSaveTiers = async () => {
    setLoading(true);
    setError('');
    setMessage('');

    // Merge new tiers into the full profile object
    const updatedProfile = {
      ...profile,
      policy_tiers: tiers
    };

    try {
      const res = await saveProfile(updatedProfile);
      setMessage(res.message);
      setProfile(updatedProfile); // Keep our main profile state in sync
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="policy-tiers-container" style={{ paddingTop: '16px', borderTop: '1px solid #e0e0e0' }}>
      <h4>Your Policy Tiers</h4>
      <p style={{ fontSize: '13px', color: '#555', margin: '0 0 10px' }}>
        Specify your plan tier for each policy to get personalized answers.
      </p>
      
      {loading && !files.length && <p>Loading...</p>}
      
      {!loading && !files.length && (
        <p style={{ fontSize: '14px', color: '#777' }}>
          Upload a policy document first.
        </p>
      )}

      {files.length > 0 && (
        <div className="tiers-list" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {files.map(filename => (
            <div key={filename} className="tier-item">
              <label 
                htmlFor={`tier-${filename}`} 
                style={{ display: 'block', fontWeight: 600, fontSize: '14px', marginBottom: '4px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
                title={filename}
              >
                {filename}
              </label>
              <input
                id={`tier-${filename}`}
                type="text"
                className="form-input"
                value={tiers[filename] || ''}
                onChange={e => handleTierChange(filename, e.target.value)}
                placeholder="e.g., P PLUS, Prestige, Elite"
              />
            </div>
          ))}
          
          <button 
            className="btn primary" 
            onClick={handleSaveTiers} 
            disabled={loading}
            style={{ width: '100%', marginTop: '10px' }}
          >
            {loading ? 'Saving...' : 'Save Tiers'}
          </button>
        </div>
      )}

      {error && <p className="form-error" style={{ margin: '10px 0 0' }}>{error}</p>}
      {message && <p className="form-message" style={{ margin: '10px 0 0' }}>{message}</p>}
    </div>
  );
}