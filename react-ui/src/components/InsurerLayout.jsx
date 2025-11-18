import React, { useState } from 'react';
import CustomerList from './Insurer/CustomerList';
import CustomerDashboard from './Insurer/CustomerDashboard';

/**
 * This component renders the main UI for a logged-in INSURER.
 */
export default function InsurerLayout({ user }) {
  const [selectedCustomerId, setSelectedCustomerId] = useState(null);

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-user-info">
          <h4 style={{ margin: 0, color: '#555', fontWeight: 500 }}>
            Insurer Agent:
          </h4>
          <h3 style={{ margin: '4px 0 0', color: '#111', wordBreak: 'break-all' }}>
            {user ? user.username : 'Loading...'}
          </h3>
        </div>
        <div className="sidebar-content">
          <CustomerList
            selectedCustomerId={selectedCustomerId}
            onSelectCustomer={setSelectedCustomerId}
          />
        </div>
      </aside>
      
      <main className="chat-main">
        {selectedCustomerId ? (
          <CustomerDashboard 
            key={selectedCustomerId}
            customerId={selectedCustomerId} 
          />
        ) : (
          <div className="empty-state" style={{ paddingTop: '40px' }}>
            Please select a customer from the list, or create a new one.
          </div>
        )}
      </main>
    </div>
  );
}