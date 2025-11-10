import React, { useState } from 'react';
import CustomerChat from './CustomerChat';
import CustomerDocuments from './CustomerDocuments';
import UnderwritingForm from './UnderwritingForm';

// Simple tab styles
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
  marginBottom: '-1px', // To overlap the container border
});

export default function CustomerDashboard({ customerId }) {
  const [activeTab, setActiveTab] = useState('chat');

  const renderTabContent = () => {
    switch (activeTab) {
      case 'chat':
        return <CustomerChat customerId={customerId} />;
      case 'documents':
        return <CustomerDocuments customerId={customerId} />;
      case 'underwriting':
        return <UnderwritingForm customerId={customerId} />;
      default:
        return null;
    }
  };

  return (
    <div className="customer-dashboard" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="dashboard-tabs" style={tabStyles}>
        <button style={tabButton(activeTab === 'chat')} onClick={() => setActiveTab('chat')}>
          Query
        </button>
        <button style={tabButton(activeTab === 'documents')} onClick={() => setActiveTab('documents')}>
          Documents
        </button>
        <button style={tabButton(activeTab === 'underwriting')} onClick={() => setActiveTab('underwriting')}>
          Underwriting
        </button>
      </div>
      
      <div className="tab-content" style={{ flex: 1, overflow: 'hidden' }}>
        {renderTabContent()}
      </div>
    </div>
  );
}