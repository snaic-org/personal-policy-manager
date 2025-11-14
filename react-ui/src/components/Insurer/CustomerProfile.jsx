import React from 'react';
import * as api from '../../services/api.js';
import CustomerProfileForm from './CustomerProfileForm';
import CustomerPolicyInfo from './CustomerPolicyInfo';

/**
 * This component wraps the two new forms in the "Profile" tab
 * for the insurer view. It receives data from its parent
 * (CustomerDashboard) and passes it down.
 */
export default function CustomerProfile({ 
  customerId, 
  profile, 
  files, 
  loading, 
  error, 
  onDataChanged 
}) {
  
  // This function is passed to the children forms
  const handleProfileUpdate = async (updatedProfileData) => {
    try {
      await api.saveInsurerProfile(customerId, updatedProfileData);
      onDataChanged(); // <-- Call parent's refresh function
      return { success: true };
    } catch (e) {
      console.error("Failed to save profile:", e);
      return { success: false, error: e.message };
    }
  };

  if (loading) return <p style={{ padding: '20px' }}>Loading profile...</p>;
  if (error) return <p className="form-error" style={{ margin: '20px' }}>{error}</p>;
  if (!profile) return <p style={{ padding: '20px' }}>No profile data found for this customer.</p>;

  return (
    <div style={{ padding: '20px', overflowY: 'auto', height: '100%' }}>
      {/* Pass the profile data and the save handler to the form */}
      <CustomerProfileForm
        customerId={customerId}
        initialProfile={profile} // <-- From props
        onSave={handleProfileUpdate}
      />
      
      {/* Pass profile, files, and save handler to the policy info form */}
      <CustomerPolicyInfo
        customerId={customerId}
        initialProfile={profile} // <-- From props
        customerFiles={files}    // <-- From props
        onSave={handleProfileUpdate}
      />
    </div>
  );
}