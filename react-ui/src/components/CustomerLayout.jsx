import React, { useState } from 'react';
import Chat from './Chat';
import Sidebar from './Sidebar';
import ProfilePage from './ProfilePage';

/**
 * This component renders the main UI for a logged-in CUSTOMER.
 */
export default function CustomerLayout({ user }) {
  const [refresh, setRefresh] = useState(false);
  const [activeTab, setActiveTab] = useState('chat');

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
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />
      
      <main className="chat-main">
        {activeTab === 'chat' && (
          <Chat 
            onUploadSuccess={handleUploadSuccess} 
          />
        )}
        {activeTab === 'profile' && (
          <ProfilePage 
            refreshTrigger={refresh} 
          />
        )}
      </main>

    </div>
  );
}