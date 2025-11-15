import React from 'react';
import Upload from './Upload';
import UploadedFiles from './UploadedFiles';

export default function Sidebar({ 
  user, 
  onUploadSuccess, 
  refreshTrigger
}) {
  return (
    <aside className="sidebar">
      <div className="sidebar-user-info">
        <h4 style={{ margin: 0, color: '#555', fontWeight: 500 }}>
          Welcome:
        </h4>
        <h3 style={{ margin: '4px 0 0', color: '#111', wordBreak: 'break-all' }}>
          {user ? user.username : 'Loading...'}
        </h3>
      </div>

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