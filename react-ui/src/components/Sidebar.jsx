import React from 'react';
import Upload from './Upload';
import UploadedFiles from './UploadedFiles';

export default function Sidebar({ 
  user, 
  onUploadSuccess, 
  refreshTrigger,
  activeTab,
  onTabChange
}) {
  return (
    <aside className="sidebar">
      {/* User info section at the top */}
      <div className="sidebar-user-info">
        <h4 style={{ margin: 0, color: '#555', fontWeight: 500 }}>
          Welcome:
        </h4>
        <h3 style={{ margin: '4px 0 0', color: '#111', wordBreak: 'break-all' }}>
          {user ? user.username : 'Loading...'}
        </h3>
      </div>

      {/* --- Tab Navigation --- */}
      <div className="sidebar-nav">
        <button
          className={`sidebar-nav-btn ${activeTab === 'chat' ? 'active' : ''}`}
          onClick={() => onTabChange('chat')}
        >
          Chat
        </button>
        <button
          className={`sidebar-nav-btn ${activeTab === 'profile' ? 'active' : ''}`}
          onClick={() => onTabChange('profile')}
        >
          My Profile & Policies
        </button>
      </div>
      {/* --- Tab Navigation --- */}


      {/* This part will scroll if content is long */}
      <div className="sidebar-content">
        <Upload onUploadSuccess={onUploadSuccess} />
        <UploadedFiles
            refreshTrigger={refreshTrigger}
            onFileChange={onUploadSuccess}
        />
      </div>
    </aside>
  );
}