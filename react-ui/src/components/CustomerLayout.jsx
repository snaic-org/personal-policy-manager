import React, { useState } from 'react';
import Chat from './Chat';
import Sidebar from './Sidebar';
import ProfileForm from './ProfileForm';
import PolicyInfo from './PolicyInfo';

const tabStyles = {
  display: 'flex',
  padding: '0 20px',
  borderBottom: '1px solid var(--light-gray-border)',
  background: 'var(--light-gray-bg)',
};
const tabButton = (isActive) => ({
  padding: '16px 20px',
  background: isActive ? '#fff' : 'transparent',
  border: 'none',
  borderBottom: isActive ? '3px solid var(--primary-color)' : '3px solid transparent',
  cursor: 'pointer',
  fontSize: '16px',
  fontWeight: isActive ? '600' : '400',
  color: isActive ? 'var(--primary-color)' : '#555',
  marginBottom: '-1px',
});

/**
 * This component renders the main UI for a logged-in CUSTOMER.
 * It now features a tabbed main content area.
 */
export default function CustomerLayout({ user }) {
  const [refresh, setRefresh] = useState(false);
  const [activeTab, setActiveTab] = useState('chat');

  const handleUploadSuccess = () => {
    setRefresh(prev => !prev);
  };

  // --- Tab Content Renderer ---
  const renderTabContent = () => {
    switch (activeTab) {
      case 'chat':
        // Chat component is full-width by default inside its container
        return <Chat onUploadSuccess={handleUploadSuccess} />;
      
      case 'profile':
        return (
          <div style={{ padding: '20px 40px', overflowY: 'auto', height: '100%', maxWidth: '900px', margin: '0 auto' }}>
            <ProfileForm />
          </div>
        );
      
      case 'policies':
        return (
          <div style={{ padding: '20px 40px', overflowY: 'auto', height: '100%', maxWidth: '900px', margin: '0 auto' }}>
            <PolicyInfo refreshTrigger={refresh} />
          </div>
        );
      
      default:
        return <Chat onUploadSuccess={handleUploadSuccess} />;
    }
  };

  return (
    <div className="app-layout">
      <Sidebar
        user={user}
        onUploadSuccess={handleUploadSuccess}
        refreshTrigger={refresh}
      />
      
      <main className="chat-main" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        
        <div className="customer-dashboard-tabs" style={tabStyles}>
          <button style={tabButton(activeTab === 'chat')} onClick={() => setActiveTab('chat')}>
            Chat
          </button>
          <button style={tabButton(activeTab === 'profile')} onClick={() => setActiveTab('profile')}>
            My Profile
          </button>
          <button style={tabButton(activeTab === 'policies')} onClick={() => setActiveTab('policies')}>
            My Policies
          </button>
        </div>

        {/* This 'tab-content' div contains either a 
          full-width component (Chat) or a constrained-width div 
          (Profile/Policies), achieving the desired effect.
        */}
        <div className="tab-content" style={{ flex: 1, overflow: 'hidden' }}>
          {renderTabContent()}
        </div>
      </main>

    </div>
  );
}