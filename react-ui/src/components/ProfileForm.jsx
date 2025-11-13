import React, { useState, useEffect } from 'react';
import { getProfile, saveProfile } from '../services/api';
import ProfileFormFields from './Shared/ProfileFormFields';

export default function ProfileForm() {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // 1. Fetches its own data
  useEffect(() => {
    setLoading(true);
    getProfile()
      .then(data => {
        setProfile(data);
      })
      .catch(err => {
        setError(err.message);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  // 2. Defines its own save function
  const handleSave = async (updatedProfile) => {
    try {
      const res = await saveProfile(updatedProfile);
      // After saving, refetch the profile to ensure UI is in sync
      const refreshedProfile = await getProfile();
      setProfile(refreshedProfile);
      return { success: true, message: res.message };
    } catch (e) {
      return { success: false, error: e.message };
    }
  };

  if (loading) return <p>Loading profile...</p>;
  if (error) return <p className="form-error">{error}</p>;

  // 3. Renders the reusable form
  return (
    <ProfileFormFields
      initialProfile={profile}
      onSave={handleSave}
      saveButtonText="Save Info"
      formIdPrefix="customer"
    />
  );
}