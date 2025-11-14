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
  const [selectedFilename, setSelectedFilename] = useState(null);
  
  const [message, setMessage] = useState('');
  const [error, setError] = useState(parentError || '');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    setProfile(initialProfile);
    
    // --- Set the default selected file ---
    // When the profile loads, set the dropdown to the first policy
    if (initialProfile?.insurance_policies && Object.keys(initialProfile.insurance_policies).length > 0) {
      if (!selectedFilename) { // Only set if not already set
        setSelectedFilename(Object.keys(initialProfile.insurance_policies)[0]);
      }
    }

  }, [initialProfile]);
  
  useEffect(() => {
    setError(parentError || '');
  }, [parentError]);

  // handleInputChange and handleNotesBlur are unchanged
  // as they already accept 'filename' as an argument.
  const handleInputChange = (filename, field, value) => {
    setProfile(prevProfile => {
      const updatedUnderwriting = {
        ...prevProfile.insurance_policies[filename].underwriting,
        [field]: value
      };

      if (field === 'risk_classification') {
        if (value !== 'substandard') {
          updatedUnderwriting.substandard_type = null;
          updatedUnderwriting.premium_loading_percent = null;
          updatedUnderwriting.exclusions = null;
          updatedUnderwriting.postponed_reason = null;
        } else {
          updatedUnderwriting.substandard_type = 'loading';
        }
      }

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

  const handleNotesBlur = (filename, value) => {
    if (value != null && value.trim() === '') {
      handleInputChange(filename, 'notes', null);
    } else if (value != null) {
      handleInputChange(filename, 'notes', value.trim());
    }
  };

  const handleSave = async () => {
    setError('');
    setMessage('');

    for (const [filename, policy] of Object.entries(profile.insurance_policies)) {
      const u = policy.underwriting;
      
      if (u?.risk_classification === 'substandard') {
        const type = u.substandard_type;
        
        if (type === 'loading') {
          if (u.premium_loading_percent == null || u.premium_loading_percent === '') {
            setError(`Error: Premium Loading is required for ${filename}.`);
            return;
          }
        } else if (type === 'exclusion') {
          if (!u.exclusions || u.exclusions.trim() === '') {
            setError(`Error: Exclusions are required for ${filename}.`);
            return;
          }
        } else if (type === 'postponed') {
          if (!u.postponed_reason || u.postponed_reason.trim() === '') {
            setError(`Error: Postponed Reason is required for ${filename}.`);
            return;
          }
        }
      }
    }

    setIsSaving(true);
    try {
      const res = await api.saveInsurerProfile(customerId, profile);
      setMessage(res.message);
      onDataChanged();
    } catch (err) {
      setError(`Save failed: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  // --- Helper variables for rendering the single form ---
  const policy = selectedFilename ? profile.insurance_policies[selectedFilename] : null;
  const currentRiskClass = policy?.underwriting?.risk_classification;
  const currentSubstandardType = policy?.underwriting?.substandard_type;
  // ---

  if (loading) return <p style={{ padding: '20px' }}>Loading profile...</p>;
  if (parentError && !error) setError(parentError);
  if (!profile || !profile.insurance_policies || Object.keys(profile.insurance_policies).length === 0) {
    return <p style={{ padding: '20px' }}>No policies found for this customer. Please upload documents first.</p>;
  }

  return (
    <div style={{ padding: '20px', overflowY: 'auto', height: '100%' }}>
      <h3>Underwriting Details</h3>

      {/* --- Policy Selector Dropdown --- */}
      <div className="form-group" style={{ marginBottom: '20px' }}>
        <label>Select Policy to Underwrite</label>
        <select
          className="form-input"
          value={selectedFilename || ''}
          onChange={e => setSelectedFilename(e.target.value)}
        >
          {Object.keys(profile.insurance_policies).map(filename => (
            <option key={filename} value={filename}>
              {filename}
            </option>
          ))}
        </select>
      </div>


      {/* We check 'policy' to make sure selectedFilename is valid */}
      {policy && (
        <div style={{ border: '1px solid #ddd', borderRadius: '8px', padding: '20px' }}>
          <h4 style={{ margin: '0 0 16px', borderBottom: '1px solid #eee', paddingBottom: '8px', wordBreak: 'break-all' }}>
            {selectedFilename}
          </h4>

          {/* --- 1. Risk Classification (Main Dropdown) --- */}
          <div className="form-group">
            <label>Risk Classification</label>
            <select
              className="form-input"
              value={currentRiskClass || 'standard'}
              // Pass the selectedFilename to the handler
              onChange={e => handleInputChange(selectedFilename, 'risk_classification', e.target.value)}
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
                onChange={e => handleInputChange(selectedFilename, 'substandard_type', e.target.value)}
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
                onChange={e => handleInputChange(selectedFilename, 'premium_loading_percent', e.target.value)}
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
                onChange={e => handleInputChange(selectedFilename, 'exclusions', e.target.value)}
                placeholder="e.g., All conditions related to the spine"
                required
              />
            </div>
          )}

          {/* C) Postponed Field */}
          {currentRiskClass === 'substandard' && currentSubstandardType === 'postponed' && (
            <div className="form-group" style={{ marginTop: '10px' }}>
              <label>Postponed Reason / Waiting Period <span style={{ color: 'red' }}>*</span></label>
              <textarea
                className="form-input"
                rows="3"
                value={policy.underwriting?.postponed_reason || ''}
                onChange={e => handleInputChange(selectedFilename, 'postponed_reason', e.target.value)}
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
                onChange={e => handleInputChange(selectedFilename, 'notes', e.target.value)}
                onBlur={e => handleNotesBlur(selectedFilename, e.target.value)}
                placeholder="e.g., User disclosed asthma at age 10."
              />
            </div>
          )}
        </div>
      )}
      
      {/* Display validation or API errors */}
      {error && <p className="form-error" style={{ marginBottom: '10px' }}>{error}</p>}
      
      <button className="btn primary" onClick={handleSave} disabled={isSaving} style={{ width: '100%', marginTop: '20px', height: '48px' }}>
        {isSaving ? 'Saving...' : 'Save All Underwriting Changes'}
      </button>
      {message && <p className="form-message" style={{ margin: '10px 0 0' }}>{message}</p>}
    </div>
  );
}