import React from 'react';
import PolicyInfoForm from '../Shared/PolicyInfoForm';

/**
 * This is now a simple "smart" wrapper.
 * It receives data and save handlers as props and passes
 * them to the reusable form component.
 */
export default function CustomerPolicyInfo({ 
  customerId, 
  initialProfile, 
  customerFiles, 
  onSave 
}) {

  // Renders the reusable form, passing its props through.
  return (
    <PolicyInfoForm
      initialProfile={initialProfile || {}}
      files={customerFiles || []}
      onSave={onSave}
      isLoading={false} // Loading is handled by the parent
      saveButtonText="Save All Policy Details"
    />
  );
}