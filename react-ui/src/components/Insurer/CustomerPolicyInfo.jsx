import React, { useState, useEffect } from 'react';

// Define policy types for the dropdown
const POLICY_TYPES = [
  "Health",
  "Critical Illness",
  "Life",
  "Travel",
  "Other"
];

/**
 * This is a copy of the customer-facing PolicyInfo,
 * adapted for the insurer to edit a customer's policy details.
 */
export default function CustomerPolicyInfo({ customerId, initialProfile, customerFiles, onSave }) {
  // This state will hold the 'insurance_policies' object
  const [localPolicies, setLocalPolicies] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  // Stores the full profile to avoid overwriting other data
  const [fullProfile, setFullProfile] = useState(initialProfile || {});

  // Load data from props
  useEffect(() => {
    const policiesFromProfile = initialProfile.insurance_policies || {};
    const files = customerFiles || [];
    setFullProfile(initialProfile);

    // This ensures all policies have a default structure, including `riders: []`,
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
        ...defaultPolicyStructure,
        ...(policiesFromProfile[filename] || {})
      };
    }
    setLocalPolicies(initializedPolicies);

  }, [initialProfile, customerFiles]);

  // --- Event Handlers ---

  const handlePolicyChange = (filename, field, value) => {
    setLocalPolicies(prevPolicies => ({
      ...prevPolicies,
      [filename]: {
        ...prevPolicies[filename],
        [field]: value
      }
    }));
  };

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

  const handleAddRider = (filename) => {
    setLocalPolicies(prevPolicies => ({
      ...prevPolicies,
      [filename]: {
        ...prevPolicies[filename],
        riders: [
          ...(prevPolicies[filename].riders || []),
          { plan_name: "", tier: "" }
        ]
      }
    }));
  };

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
    // IMPORTANT: Also merge any existing underwriting data to prevent overwriting it
    const mergedPolicies = { ...fullProfile.insurance_policies };
    for (const filename in localPolicies) {
      mergedPolicies[filename] = {
        ...(mergedPolicies[filename] || {}), // Keep existing data (like underwriting)
        ...localPolicies[filename] // Overwrite with new form data
      };
    }

    const updatedProfile = {
      ...fullProfile,
      insurance_policies: mergedPolicies
    };
    
    // Call the onSave function passed from the parent tab
    const result = await onSave(updatedProfile);

    if (result.success) {
      setMessage("Policy details saved successfully.");
      // The parent (CustomerProfileTab) will refetch and pass new props,
      // which will re-trigger the useEffect above to update the form.
    } else {
      setError(result.error || "Failed to save policy details.");
    }
    
    setLoading(false);
  };

  const policyFiles = Object.keys(localPolicies);

  return (
    <div className="policy-tiers-container" style={{ paddingTop: '16px', borderTop: '1px solid #e0e0e0' }}>
      <h4>Customer Policy Details</h4>
      
      {!policyFiles.length && (
        <p style={{ fontSize: '14px', color: '#777' }}>
          Upload a policy document first in the "Documents" tab.
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
                  style={{ width: '100%', height: '36px', fontSize: '14px', minHeight: '36px' }}
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
            {loading ? 'Saving...' : 'Save All Policy Details'}
          </button>
        </div>
      )}

      {error && <p className="form-error" style={{ margin: '10px 0 0' }}>{error}</p>}
      {message && <p className="form-message" style={{ margin: '10px 0 0' }}>{message}</p>}
    </div>
  );
}