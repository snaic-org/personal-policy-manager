import React, { useState, useEffect } from 'react';
import * as api from '../../services/api';

export default function CustomerList({ selectedCustomerId, onSelectCustomer }) {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // For the create form
  const [newUsername, setNewUsername] = useState('');
  const [formMessage, setFormMessage] = useState('');
  const [formError, setFormError] = useState('');
  const [isCreating, setIsCreating] = useState(false);

  const fetchCustomers = async () => {
    setLoading(true);
    try {
      const data = await api.getInsurerCustomers();
      setCustomers(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCustomers();
  }, []);

  const handleCreateCustomer = async (e) => {
    e.preventDefault();
    if (!newUsername) {
      setFormError('Username is required.');
      return;
    }
    setIsCreating(true);
    setFormError('');
    setFormMessage('');
    try {
      const res = await api.createCustomer(newUsername);
      setFormMessage(`Success! New password: ${res.password}`);
      setNewUsername('');
      fetchCustomers(); // Refresh the list
    } catch (err) {
      setFormError(err.message);
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="customer-list-container">
      <div className="create-customer-form" style={{ marginBottom: '24px' }}>
        <h4>Create New Customer</h4>
        <form onSubmit={handleCreateCustomer}>
          <div className="form-group" style={{ marginBottom: '10px' }}>
            <label htmlFor="new-username" style={{ marginBottom: '4px', fontSize: '14px' }}>Username</label>
            <input
              id="new-username"
              type="text"
              className="form-input"
              value={newUsername}
              onChange={e => setNewUsername(e.target.value)}
              placeholder="e.g., john_doe"
            />
          </div>
          <button type="submit" className="btn primary" disabled={isCreating} style={{ width: '100%' }}>
            {isCreating ? 'Creating...' : 'Create Customer'}
          </button>
          {formError && <p className="form-error" style={{ margin: '10px 0 0' }}>{formError}</p>}
          {formMessage && <p className="form-message" style={{ margin: '10px 0 0' }}>{formMessage}</p>}
        </form>
      </div>

      <div className="customer-list" style={{ borderTop: '1px solid #e0e0e0', paddingTop: '16px' }}>
        <h4>Your Customers</h4>
        {loading && <p>Loading customers...</p>}
        {error && <p className="form-error">{error}</p>}
        {!loading && customers.length === 0 && (
          <p style={{ fontSize: '14px', color: '#777' }}>No customers created yet.</p>
        )}
        <ul style={{ listStyle: 'none', padding: 0, margin: 0, maxHeight: '400px', overflowY: 'auto' }}>
          {customers.map(customer => (
            <li
              key={customer.id}
              onClick={() => onSelectCustomer(customer.id)}
              style={{
                padding: '12px',
                margin: '4px 0',
                background: selectedCustomerId === customer.id ? 'var(--primary-color)' : '#fff',
                color: selectedCustomerId === customer.id ? '#fff' : '#333',
                border: '1px solid #ddd',
                borderRadius: '4px',
                cursor: 'pointer',
                fontWeight: selectedCustomerId === customer.id ? '600' : '400'
              }}
            >
              {customer.username}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}