import React from 'react';
import { saveProfile } from '../../services/api';
import CustomerProfileForm from './CustomerProfileForm';

/**
 * This component wraps the profile form in the "Profile" tab
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
  
  const handleProfileUpdate = async (updatedProfileData) => {
    try {
      await saveProfile(updatedProfileData, customerId);
      onDataChanged();
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
      <CustomerProfileForm
        customerId={customerId}
        initialProfile={profile}
        onSave={handleProfileUpdate}
      />
    </div>
  );
}