import React, { useState } from 'react';
import Chat from './Chat';
import Sidebar from './Sidebar';

/**
 * This component renders the main UI for a logged-in CUSTOMER.
 */
export default function CustomerLayout({ user }) {
  const [refresh, setRefresh] = useState(false);

  // This function is passed down to refresh file list, etc.
  const handleUploadSuccess = () => {
    setRefresh(prev => !prev);
  };

  return (
    <div className="app-layout">
      <Sidebar
        user={user}
        onUploadSuccess={handleUploadSuccess}
        refreshTrigger={refresh}
      />
      <Chat 
        onUploadSuccess={handleUploadSuccess} 
      />
    </div>
  );
}