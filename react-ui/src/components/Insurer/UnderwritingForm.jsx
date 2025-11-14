import React, { useState, useEffect } from 'react';
import * as api from '../../services/api';

export default function UnderwritingForm({
  customerId,
  profile: initialProfile,
  loading,
  error: parentError,
  onDataChanged
}) {
  const [profile, setProfile] = useState(initialProfile);
  const [message, setMessage] = useState('');
  const [error, setError] = useState(parentError || ''); // Use parent's error initially
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    setProfile(initialProfile);
  }, [initialProfile]);
  
  // Also update local error if parent error changes
  useEffect(() => {
    setError(parentError || '');
  }, [parentError]);


  const handleInputChange = (filename, field, value) => {
    setProfile(prevProfile => {
      // Get a copy of the underwriting object for this policy
      const updatedUnderwriting = {
        ...prevProfile.insurance_policies[filename].underwriting,
        [field]: value
      };

      // 1. If Risk Classification changes, reset substandard fields
      if (field === 'risk_classification') {
        if (value !== 'substandard') {
          // Clear all substandard details if set to Standard
          updatedUnderwriting.substandard_type = null;
          updatedUnderwriting.premium_loading_percent = null;
          updatedUnderwriting.exclusions = null;
          updatedUnderwriting.postponed_reason = null;
        } else {
          // Default to 'loading' if switching to substandard
          updatedUnderwriting.substandard_type = 'loading';
        }
      }

      // 2. If Substandard Type changes, reset other substandard fields
      if (field === 'substandard_type') {
        if (value !== 'loading') {
          updatedUnderwriting.premium_loading_percent = null;
        }
        if (value !== 'exclusion') {
          updatedUnderwriting.exclusions = null;
        }
        if (value !== 'postponed') {
          updatedUnderwriting.postponed_reason = null;
        }
      }

      // Update the policy in the profile state
      const updatedPolicy = {
        ...prevProfile.insurance_policies[filename],
        underwriting: updatedUnderwriting
      };

      return {
        ...prevProfile,
        insurance_policies: {
          ...prevProfile.insurance_policies,
          [filename]: updatedPolicy
        }
      };
    });
  };

  /**
   * Cleans up the 'notes' field on blur.
   * If the field contains only whitespace, it sets the value to null.
   */
  const handleNotesBlur = (filename, value) => {
    if (value != null && value.trim() === '') {
      // Value is just whitespace, set it to null in the state
      handleInputChange(filename, 'notes', null);
    } else if (value != null) {
      // Value has content, so trim it for cleanliness
      handleInputChange(filename, 'notes', value.trim());
    }
  };

  const handleSave = async () => {
    setError(''); // Clear previous errors
    setMessage('');

    for (const [filename, policy] of Object.entries(profile.insurance_policies)) {
      const u = policy.underwriting; // shorthand
      
      if (u?.risk_classification === 'substandard') {
        const type = u.substandard_type;
        
        if (type === 'loading') {
          // Check for null, undefined, or empty string. 0 is a valid loading.
          if (u.premium_loading_percent == null || u.premium_loading_percent === '') {
            setError(`Error: Premium Loading is required for ${filename}.`);
            return; // Stop the save
          }
        } else if (type === 'exclusion') {
          // Check for null, undefined, or empty/whitespace string
          if (!u.exclusions || u.exclusions.trim() === '') {
            setError(`Error: Exclusions are required for ${filename}.`);
            return; // Stop the save
          }
        } else if (type === 'postponed') {
          // Check for null, undefined, or empty/whitespace string
          if (!u.postponed_reason || u.postponed_reason.trim() === '') {
            setError(`Error: Postponed Reason is required for ${filename}.`);
            return; // Stop the save
          }
        }
      }
    }

    setIsSaving(true);
    try {
      const res = await api.saveInsurerProfile(customerId, profile);
      setMessage(res.message);
      onDataChanged(); // Refresh parent data
    } catch (err) {
      setError(`Save failed: ${err.message}`); // Use setError instead of alert
    } finally {
      setIsSaving(false);
    }
  };

  if (loading) return <p style={{ padding: '20px' }}>Loading profile...</p>;
  if (parentError && !error) setError(parentError); // Sync parent error
  if (!profile || !profile.insurance_policies || Object.keys(profile.insurance_policies).length === 0) {
    return <p style={{ padding: '20px' }}>No policies found for this customer. Please upload documents first.</p>;
  }

  return (
    <div style={{ padding: '20px', overflowY: 'auto', height: '100%' }}>
      <h3>Underwriting Details</h3>

      {Object.entries(profile.insurance_policies).map(([filename, policy]) => {
        // Get the current values from state for conditional rendering
        const currentRiskClass = policy.underwriting?.risk_classification;
        const currentSubstandardType = policy.underwriting?.substandard_type;

        return (
          <div key={filename} style={{ border: '1px solid #ddd', borderRadius: '8px', padding: '20px', marginBottom: '20px' }}>
            <h4 style={{ margin: '0 0 16px', borderBottom: '1px solid #eee', paddingBottom: '8px', wordBreak: 'break-all' }}>
              {filename}
            </h4>

            {/* --- 1. Risk Classification (Main Dropdown) --- */}
            <div className="form-group">
              <label>Risk Classification</label>
              <select
                className="form-input"
                value={currentRiskClass || 'standard'}
                onChange={e => handleInputChange(filename, 'risk_classification', e.target.value)}
              >
                <option value="standard">Standard</option>
                <option value="substandard">Substandard</option>
              </select>
            </div>

            {/* --- 2. Substandard Type (Conditional Dropdown) --- */}
            {currentRiskClass === 'substandard' && (
              <div className="form-group" style={{ marginTop: '10px' }}>
                <label>Substandard Type</label>
                <select
                  className="form-input"
                  value={currentSubstandardType || ''}
                  onChange={e => handleInputChange(filename, 'substandard_type', e.target.value)}
                >
                  <option value="loading">Loading</option>
                  <option value="exclusion">Exclusion</option>
                  <option value="postponed">Postponed</option>
                </select>
              </div>
            )}

            {/* --- 3. Substandard Detail Fields (Conditional Inputs) --- */}

            {/* A) Loading Field */}
            {currentRiskClass === 'substandard' && currentSubstandardType === 'loading' && (
              <div className="form-group" style={{ marginTop: '10px' }}>
                <label>Premium Loading (%) <span style={{ color: 'red' }}>*</span></label>
                <input
                  type="number"
                  className="form-input"
                  value={policy.underwriting?.premium_loading_percent || ''}
                  onChange={e => handleInputChange(filename, 'premium_loading_percent', e.target.value)}
                  placeholder="e.g., 25"
                  required
                />
              </div>
            )}

            {/* B) Exclusion Field */}
            {currentRiskClass === 'substandard' && currentSubstandardType === 'exclusion' && (
              <div className="form-group" style={{ marginTop: '10px' }}>
                <label>Exclusions (one per line) <span style={{ color: 'red' }}>*</span></label>
                <textarea
                  className="form-input"
                  rows="3"
                  value={policy.underwriting?.exclusions || ''}
                  onChange={e => handleInputChange(filename, 'exclusions', e.target.value)}
                  placeholder="e.g., All conditions related to the spine"
                  required
                />
              </div>
            )}

            {/* C) Postponed Field (NEW) */}
            {currentRiskClass === 'substandard' && currentSubstandardType === 'postponed' && (
              <div className="form-group" style={{ marginTop: '10px' }}>
                <label>Postponed Reason / Waiting Period <span style={{ color: 'red' }}>*</span></label>
                <textarea
                  className="form-input"
                  rows="3"
                  value={policy.underwriting?.postponed_reason || ''}
                  onChange={e => handleInputChange(filename, 'postponed_reason', e.target.value)}
                  placeholder="e.g., Postpone for 6 months due to recent surgery."
                  required
                />
              </div>
            )}

            {/* Internal Notes (Visible when Substandard) */}
            {currentRiskClass === 'substandard' && (
              <div className="form-group" style={{ marginTop: '10px' }}>
                <label>Internal Notes</label>
                <textarea
                  className="form-input"
                  rows="3"
                  value={policy.underwriting?.notes || ''}
                  onChange={e => handleInputChange(filename, 'notes', e.target.value)}
                  onBlur={e => handleNotesBlur(filename, e.target.value)}
                  placeholder="e.g., User disclosed asthma at age 10."
                />
              </div>
            )}
          </div>
        )
      })}
      
      {/* Display validation or API errors */}
      {error && <p className="form-error" style={{ marginBottom: '10px' }}>{error}</p>}
      
      <button className="btn primary" onClick={handleSave} disabled={isSaving} style={{ width: '100%', marginTop: '10px', height: '48px' }}>
        {isSaving ? 'Saving...' : 'Save All Underwriting Changes'}
      </button>
      {message && <p className="form-message" style={{ margin: '10px 0 0' }}>{message}</p>}
    </div>
  );
}