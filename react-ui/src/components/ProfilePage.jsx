import React from 'react';
import ProfileForm from './ProfileForm';
import PolicyInfo from './PolicyInfo';

/**
 * This component is a simple wrapper for the
 * forms that will live in the "Profile" tab.
 */
export default function ProfilePage({ refreshTrigger }) {
  return (
    <div className="profile-page-container">
      <ProfileForm />
      <PolicyInfo refreshTrigger={refreshTrigger} />
    </div>
  );
}