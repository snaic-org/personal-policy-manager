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
      // Ensure underwriting object exists for each policy
      if (data.policy_details) {
        data.policy_details = data.policy_details.map(policy => ({
          ...policy,
          underwriting: policy.underwriting || {} // Ensure object exists
        }));
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

  const handleInputChange = (policyId, field, value) => {
    setProfile(prevProfile => {
      const newPolicyDetails = prevProfile.policy_details.map(policy => {
        if (policy.policy_id === policyId) {
          return {
            ...policy,
            underwriting: {
              ...policy.underwriting,
              [field]: value
            }
          };
        }
        return policy;
      });
      return { ...prevProfile, policy_details: newPolicyDetails };
    });
  };

  const handleSave = async () => {
    setIsSaving(true);
    setError('');
    setMessage('');
    try {
      const res = await api.saveInsurerProfile(customerId, profile);
      setMessage(res.message);
      fetchProfile(); // Refetch to confirm
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSaving(false);
    }
  };

  if (loading) return <p style={{ padding: '20px' }}>Loading profile...</p>;
  if (error) return <p className="form-error" style={{ margin: '20px' }}>{error}</p>;
  if (!profile || !profile.policy_details || profile.policy_details.length === 0) {
    return <p style={{ padding: '20px' }}>No policies found for this customer. Please upload documents first.</p>;
  }

  return (
    <div style={{ padding: '20px', overflowY: 'auto', height: '100%' }}>
      <h3>Underwriting Details</h3>
      <p style={{ fontSize: '14px', color: '#555', margin: '0 0 20px' }}>
        Set underwriting status, loading, and exclusions for each policy.
      </p>
      
      {profile.policy_details.map(policy => (
        <div key={policy.policy_id} style={{ border: '1px solid #ddd', borderRadius: '8px', padding: '20px', marginBottom: '20px' }}>
          <h4 style={{ margin: '0 0 16px', borderBottom: '1px solid #eee', paddingBottom: '8px' }}>
            {policy.filename}
          </h4>
          <div className="form-group">
            <label>Status</label>
            <select
              className="form-input"
              value={policy.underwriting?.status || ''}
              onChange={e => handleInputChange(policy.policy_id, 'status', e.target.value)}
            >
              <option value="">Pending</option>
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
              onChange={e => handleInputChange(policy.policy_id, 'premium_loading_percent', e.target.value)}
              placeholder="e.g., 15"
            />
          </div>
          <div className="form-group" style={{ marginTop: '10px' }}>
            <label>Exclusions (one per line)</label>
            <textarea
              className="form-input"
              rows="3"
              value={policy.underwriting?.exclusions || ''}
              onChange={e => handleInputChange(policy.policy_id, 'exclusions', e.target.value)}
              placeholder="e.g., Asthma-related complications"
            />
          </div>
          <div className="form-group" style={{ marginTop: '10px' }}>
            <label>Internal Notes</label>
            <textarea
              className="form-input"
              rows="3"
              value={policy.underwriting?.notes || ''}
              onChange={e => handleInputChange(policy.policy_id, 'notes', e.target.value)}
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