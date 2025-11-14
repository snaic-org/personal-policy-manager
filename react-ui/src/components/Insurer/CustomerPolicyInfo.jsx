import React from 'react';
import * as api from '../../services/api';
import PolicyInfoForm from '../Shared/PolicyInfoForm';

/**
 * This is a simple "smart" wrapper.
 * It passes data and the insurer-specific save handler
 * to the reusable PolicyInfoForm.
 */
export default function CustomerPolicyInfo({ 
  customerId, 
  profile, 
  files, 
  onDataChanged 
}) {
  
  // This save handler is specific to the Insurer API
  const handleSave = async (updatedProfileData) => {
    try {
      const res = await api.saveInsurerProfile(customerId, updatedProfileData);
      onDataChanged(); // <-- Call parent's refresh function
      return { success: true, message: res.message };
    } catch (e) {
      console.error("Failed to save profile:", e);
      return { success: false, error: e.message };
    }
  };

  // Parent (CustomerDashboard) handles loading/error, so we pass isLoading=false
  return (
    <div style={{ padding: '20px', overflowY: 'auto', height: '100%' }}>
      <PolicyInfoForm
        initialProfile={profile || {}}
        files={files || []}
        onSave={handleSave}
        isLoading={false} 
        saveButtonText="Save All Policy Changes"
        showPolicySelector={true}
        policySelectorLabel="Select Policy to Edit"
      />
    </div>
  );
}