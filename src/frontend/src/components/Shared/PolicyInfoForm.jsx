import React, { useState, useEffect } from 'react';

// Define policy types for the dropdown
const POLICY_TYPES = [
  "Health",
  "Critical Illness",
  "Travel",
  "Other"
];

/**
 * A reusable component that displays and manages the state
 * for the policy info form.
 *
 * NEW: Now supports two modes via `showPolicySelector`:
 * 1. false (default): Renders a list of all policy forms.
 * 2. true: Renders a dropdown to select a single policy to edit.
 */
export default function PolicyInfoForm({
  initialProfile,
  files,
  onSave,
  isLoading,
  saveButtonText = "Save Policy Details",
  showPolicySelector = false,
  policySelectorLabel = "Select Policy"
}) {
  const [localPolicies, setLocalPolicies] = useState({});
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [selectedFilename, setSelectedFilename] = useState(null);

  // When props change, re-initialize the local state
  useEffect(() => {
    const policiesFromProfile = initialProfile.insurance_policies || {};
    const filesList = files || [];

    const defaultPolicyStructure = {
      policy_type: "",
      insurer: "",
      plan_name: "",
      tier: "",
      riders: []
    };

    const initializedPolicies = {};
    for (const filename of filesList) {
      initializedPolicies[filename] = {
        ...defaultPolicyStructure,
        ...(policiesFromProfile[filename] || {})
      };
    }
    setLocalPolicies(initializedPolicies);
    
    // --- Set the default selected file for dropdown mode ---
    if (showPolicySelector && filesList.length > 0) {
      // If a file is already selected, keep it, otherwise set to first
      setSelectedFilename(prev => 
        filesList.includes(prev) ? prev : filesList[0]
      );
    } else if (filesList.length === 0) {
      setSelectedFilename(null);
    }

  }, [initialProfile, files, showPolicySelector]);

  // --- All the form handlers are identical ---
  // They work in both modes because they are passed the
  // 'filename' argument.

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

  // The save handler is generic
  const handleSave = async () => {
    setIsSaving(true);
    setError('');
    setMessage('');

    // Merge new localPolicies into the full profile object
    const updatedProfile = {
      ...initialProfile,
      insurance_policies: localPolicies
    };
    
    // Call the parent's save function
    const result = await onSave(updatedProfile);

    if (result.success) {
      setMessage(result.message || "Policy details saved successfully.");
    } else {
      setError(result.error || "Failed to save policy details.");
    }
    
    setIsSaving(false);
  };

  const policyFiles = Object.keys(localPolicies);

  // --- Reusable render function for a single policy form ---
  const renderPolicyForm = (filename) => {
    const policy = localPolicies[filename];
    if (!policy) return null; // Handle case where selectedFilename might be briefly out of sync
    
    return (
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
            value={policy.policy_type || ''}
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
            value={policy.insurer || ''}
            onChange={e => handlePolicyChange(filename, 'insurer', e.target.value)}
            placeholder="e.g., Great Eastern"
          />
        </div>

        <div className="form-group" style={{ marginBottom: '10px' }}>
          <label style={{ marginBottom: '4px', fontSize: '14px' }}>Plan Name</label>
          <input
            type="text"
            className="form-input"
            value={policy.plan_name || ''}
            onChange={e => handlePolicyChange(filename, 'plan_name', e.target.value)}
            placeholder="e.g., GREAT SupremeHealth"
          />
        </div>

        <div className="form-group" style={{ marginBottom: '10px' }}>
          <label style={{ marginBottom: '4px', fontSize: '14px' }}>Tier / Plan Level</label>
          <input
            type="text"
            className="form-input"
            value={policy.tier || ''}
            onChange={e => handlePolicyChange(filename, 'tier', e.target.value)}
            placeholder="e.g., P PLUS, Prestige, Elite"
          />
        </div>

        {/* --- Riders Section --- */}
        <div className="riders-section" style={{ marginTop: '16px' }}>
          <h5 style={{ margin: '0 0 10px' }}>Riders</h5>
          {(policy.riders || []).map((rider, index) => (
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
              padding: '0 24px',
              lineHeight: '36px'
            }}
          >
            + Add Rider
          </button>
        </div>
      </div>
    );
  };
  // --- END of renderPolicyForm function ---

  return (
    <div className="policy-tiers-container">
      <h3>Policy Details</h3>
      
      {isLoading && <p>Loading...</p>}
      
      {!isLoading && policyFiles.length === 0 && (
        <p style={{ fontSize: '14px', color: '#777' }}>
          Upload a policy document first.
        </p>
      )}

      {/* --- Policy Selector Dropdown --- */}
      {showPolicySelector && policyFiles.length > 0 && (
        <div className="form-group" style={{ marginBottom: '20px' }}>
          <label>{policySelectorLabel}</label>
          <select
            className="form-input"
            value={selectedFilename || ''}
            onChange={e => setSelectedFilename(e.target.value)}
          >
            {policyFiles.map(filename => (
              <option key={filename} value={filename}>
                {filename}
              </option>
            ))}
          </select>
        </div>
      )}


      {policyFiles.length > 0 && (
        <div className="tiers-list" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          {/* --- Conditional Render Logic --- */}
          {showPolicySelector ? (
            // Mode 1: Render single form based on state
            renderPolicyForm(selectedFilename)
          ) : (
            // Mode 2: Render all forms (original behavior)
            policyFiles.map(filename => renderPolicyForm(filename))
          )}
          
          <button 
            className="btn primary" 
            onClick={handleSave} 
            disabled={isSaving}
            style={{ width: '100%', marginTop: '10px' }}
          >
            {isSaving ? 'Saving...' : saveButtonText}
          </button>
        </div>
      )}

      {error && <p className="form-error" style={{ margin: '10px 0 0' }}>{error}</p>}
      {message && <p className="form-message" style={{ margin: '10px 0 0' }}>{message}</p>}
    </div>
  );
}