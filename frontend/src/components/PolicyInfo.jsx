import React, { useState, useEffect, useCallback } from 'react';
import { getProfile, saveProfile, getUserFiles } from '../services/api';
import PolicyInfoForm from './Shared/PolicyInfoForm';

export default function PolicyInfo({ refreshTrigger }) {
  const [profile, setProfile] = useState(null);
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [profileData, filesData] = await Promise.all([
        getProfile(),
        getUserFiles()
      ]);
      setProfile(profileData);
      setFiles(filesData.files || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData, refreshTrigger]);

  const handleSave = async (updatedProfile) => {
    try {
      const res = await saveProfile(updatedProfile);
      await fetchData();
      return { success: true, message: res.message };
    } catch (e) {
      return { success: false, error: e.message };
    }
  };

  if (error) return <p className="form-error" style={{ margin: '10px 0 0' }}>{error}</p>;

  return (
    <PolicyInfoForm
      initialProfile={profile || {}}
      files={files}
      onSave={handleSave}
      isLoading={loading}
      saveButtonText="Save Policy Details"
      showPolicySelector={true}
      policySelectorLabel="Select Policy to Edit"
    />
  );
}