import React, { useState, useEffect, useCallback } from 'react';
import { getProfile, getUserFiles } from '../../services/api';
import CustomerChat from './CustomerChat';
import CustomerDocuments from './CustomerDocuments';
import UnderwritingForm from './UnderwritingForm';
import CustomerProfile from './CustomerProfile';
import CustomerPolicyInfo from './CustomerPolicyInfo';

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

const ConstrainedTabView = ({ children }) => (
  <div style={{ 
    maxWidth: '900px', 
    margin: '0 auto', 
    height: '100%', 
    overflowY: 'auto', 
    padding: '20px 40px' 
  }}>
    {children}
  </div>
);

export default function CustomerDashboard({ customerId }) {
  const [activeTab, setActiveTab] = useState('chat');

  const [profile, setProfile] = useState(null);
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [profileData, filesData] = await Promise.all([
        getProfile(customerId),
        getUserFiles(customerId)
      ]);
      
      if (profileData.insurance_policies) {
        for (const filename in profileData.insurance_policies) {
          if (!profileData.insurance_policies[filename].underwriting) {
            profileData.insurance_policies[filename].underwriting = {};
          }
        }
      }
      
      setProfile(profileData);
      setFiles(filesData.files || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [customerId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // --- Tab Content Renderer ---
  const renderTabContent = () => {
    if (activeTab !== 'chat') {
      if (loading) return <p style={{ padding: '20px' }}>Loading data...</p>;
      if (error) return <p className="form-error" style={{ margin: '20px' }}>{error}</p>;
    }
    
    switch (activeTab) {
      case 'chat':
        return <CustomerChat customerId={customerId} />;
      
      case 'documents':
        return (
          <ConstrainedTabView>
            <CustomerDocuments
              customerId={customerId}
              files={files}
              onDataChanged={fetchData}
            />
          </ConstrainedTabView>
        );
      
      case 'policies':
        return (
          <ConstrainedTabView>
            <CustomerPolicyInfo
              customerId={customerId}
              profile={profile}
              files={files}
              onDataChanged={fetchData}
            />
          </ConstrainedTabView>
        );

      case 'underwriting':
        return (
          <ConstrainedTabView>
            <UnderwritingForm
              customerId={customerId}
              profile={profile}
              onDataChanged={fetchData}
            />
          </ConstrainedTabView>
        );

      case 'profile':
        return (
          <ConstrainedTabView>
            <CustomerProfile
              customerId={customerId}
              profile={profile}
              files={files}
              onDataChanged={fetchData}
            />
          </ConstrainedTabView>
        );

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
        <button style={tabButton(activeTab === 'policies')} onClick={() => setActiveTab('policies')}>
          Policies
        </button>
        <button style={tabButton(activeTab === 'underwriting')} onClick={() => setActiveTab('underwriting')}>
          Underwriting
        </button>
        <button style={tabButton(activeTab === 'profile')} onClick={() => setActiveTab('profile')}>
          Profile
        </button>
      </div>
      
      <div className="tab-content" style={{ flex: 1, overflow: 'hidden' }}>
        {renderTabContent()}
      </div>
    </div>
  );
}