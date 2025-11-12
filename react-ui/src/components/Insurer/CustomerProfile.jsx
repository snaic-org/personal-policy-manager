import React, { useState, useEffect, useCallback } from 'react';
import * as api from '../../services/api.js';
import CustomerProfileForm from './CustomerProfileForm';
import CustomerPolicyInfo from './CustomerPolicyInfo';

/**
 * This component wraps the two new forms in the "Profile" tab
 * for the insurer view. It handles fetching the profile and
 * file data once and passes it down.
 */
export default function CustomerProfile({ customerId }) {
  const [profile, setProfile] = useState(null);
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Fetches all data needed for this tab
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [profileData, filesData] = await Promise.all([
        api.getInsurerProfile(customerId),
        api.getInsurerCustomerFiles(customerId)
      ]);
      
      setProfile(profileData);
      setFiles(filesData.files || []);
      
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [customerId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // This function will be called by the child forms when they save
  const handleProfileUpdate = async (updatedProfileData) => {
    try {
      await api.saveInsurerProfile(customerId, updatedProfileData);
      // Refetch the data to ensure consistency
      await fetchData(); 
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
        initialProfile={profile}
        onSave={handleProfileUpdate}
      />
      
      {/* Pass profile, files, and save handler to the policy info form */}
      <CustomerPolicyInfo
        customerId={customerId}
        initialProfile={profile}
        customerFiles={files}
        onSave={handleProfileUpdate}
      />
    </div>
  );
}