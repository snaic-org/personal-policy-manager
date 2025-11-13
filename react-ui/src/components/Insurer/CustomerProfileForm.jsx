import React from 'react';
import ProfileFormFields from '../Shared/ProfileFormFields';

/**
 * This is now a simple "smart" wrapper.
 * It receives data and save handlers as props and passes
 * them to the reusable form component.
 */
export default function CustomerProfileForm({ customerId, initialProfile, onSave }) {
  
  // Renders the reusable form, passing its props through.
  // The `onSave` prop from the parent (`CustomerProfile`)
  // is already the exact function `ProfileFormFields` expects.
  return (
    <ProfileFormFields
      initialProfile={initialProfile}
      onSave={onSave}
      saveButtonText="Save Customer Info"
      formIdPrefix={`customer-${customerId}`}
    />
  );
}