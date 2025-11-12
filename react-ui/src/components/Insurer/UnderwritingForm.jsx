// In react-ui/src/components/Insurer/UnderwritingForm.jsx
import React, { useState, useEffect, useCallback } from 'react';
import * as api from '../../services/api';

export default function UnderwritingForm({ customerId }) {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const fetchProfile = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await api.getInsurerProfile(customerId);
      if (data.insurance_policies) {
        for (const filename in data.insurance_policies) {
          if (!data.insurance_policies[filename].underwriting) {
            data.insurance_policies[filename].underwriting = {};
          }
        }
      }
      setProfile(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [customerId]);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  const handleInputChange = (filename, field, value) => {
    setProfile(prevProfile => {
      // Start with the existing underwriting data
      const updatedUnderwriting = {
        ...prevProfile.insurance_policies[filename].underwriting,
        [field]: value
      };

      // If the field being changed is 'status' AND the new value is NOT 'approved_with_loading'
      if (field === 'status' && value !== 'approved_with_loading') {
        // Then automatically clear the premium loading field
        updatedUnderwriting.premium_loading_percent = null;
      }

      const updatedPolicy = {
        ...prevProfile.insurance_policies[filename],
        underwriting: updatedUnderwriting // Use the new underwriting object
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

  const handleSave = async () => {
    setIsSaving(true);
    setError('');
    setMessage('');
    try {
      const res = await api.saveInsurerProfile(customerId, profile);
      setMessage(res.message);
      fetchProfile();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSaving(false);
    }
  };

  if (loading) return <p style={{ padding: '20px' }}>Loading profile...</p>;
  if (error) return <p className="form-error" style={{ margin: '20px' }}>{error}</p>;
  if (!profile || !profile.insurance_policies || Object.keys(profile.insurance_policies).length === 0) {
    return <p style={{ padding: '20px' }}>No policies found for this customer. Please upload documents first.</p>;
  }

  return (
    <div style={{ padding: '20px', overflowY: 'auto', height: '100%' }}>
      <h3>Underwriting Details</h3>
      
      {Object.entries(profile.insurance_policies).map(([filename, policy]) => (
        <div key={filename} style={{ border: '1px solid #ddd', borderRadius: '8px', padding: '20px', marginBottom: '20px' }}>
          <h4 style={{ margin: '0 0 16px', borderBottom: '1px solid #eee', paddingBottom: '8px', wordBreak: 'break-all' }}>
            {filename}
          </h4>
          <div className="form-group">
            <label>Status</label>
            <select
              className="form-input"
              value={policy.underwriting?.status || ''}
              onChange={e => handleInputChange(filename, 'status', e.target.value)}
            >
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="approved_with_loading">Approved with Loading</option>
              <option value="declined">Declined</option>
            </select>
          </div>
          <div className="form-group" style={{ marginTop: '10px' }}>
            <label>Premium Loading (%)</label>
            <input
              type="number"
              className="form-input"
              value={policy.underwriting?.premium_loading_percent || ''}
              onChange={e => handleInputChange(filename, 'premium_loading_percent', e.target.value)}
              placeholder="e.g., 15"
              disabled={policy.underwriting?.status !== 'approved_with_loading'}
            />
          </div>
          <div className="form-group" style={{ marginTop: '10px' }}>
            <label>Exclusions (one per line)</label>
            <textarea
              className="form-input"
              rows="3"
              value={policy.underwriting?.exclusions || ''}
              onChange={e => handleInputChange(filename, 'exclusions', e.target.value)}
              placeholder="e.g., Asthma-related complications"
            />
          </div>
          <div className="form-group" style={{ marginTop: '10px' }}>
            <label>Internal Notes</label>
            <textarea
              className="form-input"
              rows="3"
              value={policy.underwriting?.notes || ''}
              onChange={e => handleInputChange(filename, 'notes', e.target.value)}
              placeholder="e.g., User disclosed asthma at age 10."
            />
          </div>
        </div>
      ))}
      
      <button className="btn primary" onClick={handleSave} disabled={isSaving} style={{ width: '100%', marginTop: '10px', height: '48px' }}>
        {isSaving ? 'Saving...' : 'Save All Underwriting Changes'}
      </button>
      {message && <p className="form-message" style={{ margin: '10px 0 0' }}>{message}</p>}
    </div>
  );
}