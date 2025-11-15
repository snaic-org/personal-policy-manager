import React, { useState, useEffect } from 'react';
import { getProfile, saveProfile } from '../services/api';
import ProfileFormFields from './Shared/ProfileFormFields';

export default function ProfileForm() {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

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

  const handleSave = async (updatedProfile) => {
    try {
      const res = await saveProfile(updatedProfile);
      const refreshedProfile = await getProfile();
      setProfile(refreshedProfile);
      return { success: true, message: res.message };
    } catch (e) {
      return { success: false, error: e.message };
    }
  };

  if (loading) return <p>Loading profile...</p>;
  if (error) return <p className="form-error">{error}</p>;

  return (
    <ProfileFormFields
      initialProfile={profile}
      onSave={handleSave}
      saveButtonText="Save Info"
      formIdPrefix="customer"
    />
  );
}