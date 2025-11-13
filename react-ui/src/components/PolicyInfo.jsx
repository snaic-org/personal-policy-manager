import React, { useState, useEffect, useCallback } from 'react';
import { getProfile, saveProfile, getUserFiles } from '../services/api';

// Define policy types for the dropdown
const POLICY_TYPES = [
  "Health",
  "Critical Illness",
  "Life",
  "Travel",
  "Other"
];

export default function PolicyInfo({ refreshTrigger }) {
  const [profile, setProfile] = useState({});
  // This state will hold the 'insurance_policies' object
  const [localPolicies, setLocalPolicies] = useState({});
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
      
      const files = filesData.files || [];
      const policiesFromProfile = profileData.insurance_policies || {};
      
      // Create an initialized object for our local state
      // This ensures that every file in 'files' has an entry
      // in 'localPolicies', creating a default one if it doesn't exist.
      
      // This ensures all policies have a default structure, including `riders: []`,
      // even if the loaded profile data is missing it.
      const defaultPolicyStructure = {
        policy_type: "",
        insurer: "",
        plan_name: "",
        tier: "",
        riders: []
      };

      const initializedPolicies = {};
      for (const filename of files) {
        initializedPolicies[filename] = {
          ...defaultPolicyStructure, // Start with defaults
          ...(policiesFromProfile[filename] || {}) // Override with loaded data
        };
      }
      
      setProfile(profileData);
      setLocalPolicies(initializedPolicies);
      
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData, refreshTrigger]); // Refetch when files change

  // --- Event Handlers ---

  // Handles changes for top-level policy fields
  const handlePolicyChange = (filename, field, value) => {
    setLocalPolicies(prevPolicies => ({
      ...prevPolicies,
      [filename]: {
        ...prevPolicies[filename],
        [field]: value
      }
    }));
  };

  // Handles changes for fields inside a rider
  const handleRiderChange = (filename, riderIndex, field, value) => {
    setLocalPolicies(prevPolicies => {
      const updatedRiders = [...(prevPolicies[filename].riders || [])];
      updatedRiders[riderIndex] = {
        ...updatedRiders[riderIndex],
        [field]: value
      };
      
      return {
        ...prevPolicies,
        [filename]: {
          ...prevPolicies[filename],
          riders: updatedRiders
        }
      };
    });
  };

  // Adds a new, empty rider to a policy
  const handleAddRider = (filename) => {
    setLocalPolicies(prevPolicies => ({
      ...prevPolicies,
      [filename]: {
        ...prevPolicies[filename],
        riders: [
          ...(prevPolicies[filename].riders || []),
          { plan_name: "", tier: "" } // New empty rider
        ]
      }
    }));
  };

  // Removes a rider by its index
  const handleRemoveRider = (filename, riderIndex) => {
    setLocalPolicies(prevPolicies => ({
      ...prevPolicies,
      [filename]: {
        ...prevPolicies[filename],
        riders: (prevPolicies[filename].riders || []).filter((_, index) => index !== riderIndex)
      }
    }));
  };

  // Saves the entire updated profile
  const handleSave = async () => {
    setLoading(true);
    setError('');
    setMessage('');

    // Merge new localPolicies into the full profile object
    const updatedProfile = {
      ...profile,
      insurance_policies: localPolicies
    };

    try {
      const res = await saveProfile(updatedProfile);
      setMessage(res.message);
      // Refetch all data to get the merged profile from backend
      await fetchData();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const policyFiles = Object.keys(localPolicies);

  return (
    <div className="policy-tiers-container" style={{ paddingTop: '16px', borderTop: '1px solid #e0e0e0' }}>
      <h4>Your Policy Details</h4>
      <p style={{ fontSize: '13px', color: '#555', margin: '0 0 10px' }}>
        Specify your policy details to get more personalized answers.
      </p>
      
      {loading && !policyFiles.length && <p>Loading...</p>}
      
      {!loading && !policyFiles.length && (
        <p style={{ fontSize: '14px', color: '#777' }}>
          Upload a policy document first.
        </p>
      )}

      {policyFiles.length > 0 && (
        <div className="tiers-list" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {policyFiles.map(filename => (
            <div key={filename} className="policy-details-card" style={{ border: '1px solid #ddd', padding: '16px', borderRadius: '8px' }}>
              <label 
                style={{ display: 'block', fontWeight: 600, fontSize: '14px', marginBottom: '12px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', borderBottom: '1px solid #eee', paddingBottom: '8px' }}
                title={filename}
              >
                {filename}
              </label>
              
              <div className="form-group" style={{ marginBottom: '10px' }}>
                <label style={{ marginBottom: '4px', fontSize: '14px' }}>Policy Type</label>
                <select
                  className="form-input"
                  value={localPolicies[filename].policy_type || ''}
                  onChange={e => handlePolicyChange(filename, 'policy_type', e.target.value)}
                >
                  <option value="">Select type...</option>
                  {POLICY_TYPES.map(type => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </select>
              </div>

              <div className="form-group" style={{ marginBottom: '10px' }}>
                <label style={{ marginBottom: '4px', fontSize: '14px' }}>Insurer</label>
                <input
                  type="text"
                  className="form-input"
                  value={localPolicies[filename].insurer || ''}
                  onChange={e => handlePolicyChange(filename, 'insurer', e.target.value)}
                  placeholder="e.g., Great Eastern"
                />
              </div>

              <div className="form-group" style={{ marginBottom: '10px' }}>
                <label style={{ marginBottom: '4px', fontSize: '14px' }}>Plan Name</label>
                <input
                  type="text"
                  className="form-input"
                  value={localPolicies[filename].plan_name || ''}
                  onChange={e => handlePolicyChange(filename, 'plan_name', e.target.value)}
                  placeholder="e.g., GREAT SupremeHealth"
                />
              </div>

              <div className="form-group" style={{ marginBottom: '10px' }}>
                <label style={{ marginBottom: '4px', fontSize: '14px' }}>Tier / Plan Level</label>
                <input
                  type="text"
                  className="form-input"
                  value={localPolicies[filename].tier || ''}
                  onChange={e => handlePolicyChange(filename, 'tier', e.target.value)}
                  placeholder="e.g., P PLUS, Prestige, Elite"
                />
              </div>

              {/* --- Riders Section --- */}
              <div className="riders-section" style={{ marginTop: '16px' }}>
                <h5 style={{ margin: '0 0 10px' }}>Riders</h5>
                {(localPolicies[filename].riders || []).map((rider, index) => (
                  <div key={index} style={{ display: 'flex', gap: '8px', marginBottom: '8px', alignItems: 'center' }}>
                    <input
                      type="text"
                      className="form-input"
                      value={rider.plan_name || ''}
                      onChange={e => handleRiderChange(filename, index, 'plan_name', e.target.value)}
                      placeholder="Rider Plan Name"
                      style={{ flex: 1 }}
                    />
                    <input
                      type="text"
                      className="form-input"
                      value={rider.tier || ''}
                      onChange={e => handleRiderChange(filename, index, 'tier', e.target.value)}
                      placeholder="Rider Tier"
                      style={{ flex: 1 }}
                    />
                    <button 
                      onClick={() => handleRemoveRider(filename, index)} 
                      className="btn danger"
                      style={{ padding: '0', width: '32px', height: '32px', lineHeight: '32px', minHeight: '32px', flexShrink: 0 }}
                      title="Remove Rider"
                    >
                      X
                    </button>
                  </div>
                ))}
                <button 
                  onClick={() => handleAddRider(filename)} 
                  className="btn secondary"
                  style={{ 
                    width: '100%', 
                    height: '36px', 
                    fontSize: '14px', 
                    minHeight: '36px',
                    padding: '0 24px',      // Reset vertical padding
                    lineHeight: '36px'    // Center text vertically
                  }}
                >
                  + Add Rider
                </button>
              </div>

            </div>
          ))}
          
          <button 
            className="btn primary" 
            onClick={handleSave} 
            disabled={loading}
            style={{ width: '100%', marginTop: '10px' }}
          >
            {loading ? 'Saving...' : 'Save Policy Details'}
          </button>
        </div>
      )}

      {error && <p className="form-error" style={{ margin: '10px 0 0' }}>{error}</p>}
      {message && <p className="form-message" style={{ margin: '10px 0 0' }}>{message}</p>}
    </div>
  );
}