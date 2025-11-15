import React, { useState, useEffect } from 'react';
import { getInsurerCustomers, createCustomer } from '../../services/api';

export default function CustomerList({ selectedCustomerId, onSelectCustomer }) {
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [username, setUsername] = useState('');
  const [name, setName] = useState('');
  const [dob, setDob] = useState('');
  const [gender, setGender] = useState('');
  const [smokingStatus, setSmokingStatus] = useState('');

  const [formMessage, setFormMessage] = useState('');
  const [formError, setFormError] = useState('');
  const [isCreating, setIsCreating] = useState(false);

  const fetchCustomers = async () => {
    setLoading(true);
    try {
      const data = await getInsurerCustomers();
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

  const resetForm = () => {
    setUsername('');
    setName('');
    setDob('');
    setGender('');
    setSmokingStatus('');
  };

  const handleCreateCustomer = async (e) => {
    e.preventDefault();
    if (!username || !name || !dob || !gender || !smokingStatus) {
      setFormError('All fields are required.');
      return;
    }

    setIsCreating(true);
    setFormError('');
    setFormMessage('');

    try {
      const profileData = { username, name, dob, gender, smokingStatus };
      const res = await createCustomer(profileData);

      setFormMessage(`Success! New password: ${res.password}`);
      resetForm();
      fetchCustomers();
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
            <label htmlFor="new-username" style={{ marginBottom: '4px', fontSize: '14px' }}>Username (for login)</label>
            <input
              id="new-username"
              type="text"
              className="form-input"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="e.g., john_doe"
              required
            />
          </div>
          <div className="form-group" style={{ marginBottom: '10px' }}>
            <label htmlFor="new-name" style={{ marginBottom: '4px', fontSize: '14px' }}>Full Name</label>
            <input
              id="new-name"
              type="text"
              className="form-input"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g., John Doe"
              required
            />
          </div>
          <div className="form-group" style={{ marginBottom: '10px' }}>
            <label htmlFor="new-dob" style={{ marginBottom: '4px', fontSize: '14px' }}>Date of Birth</label>
            <input
              id="new-dob"
              type="date"
              className="form-input"
              value={dob}
              onChange={e => setDob(e.target.value)}
              required
            />
          </div>
          <div className="form-group" style={{ marginBottom: '10px' }}>
            <label htmlFor="new-gender" style={{ marginBottom: '4px', fontSize: '14px' }}>Gender</label>
            <select
              id="new-gender"
              className="form-input"
              value={gender}
              onChange={e => setGender(e.target.value)}
              required
            >
              <option value="">Select gender</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
            </select>
          </div>
          <div className="form-group" style={{ marginBottom: '10px' }}>
            <label htmlFor="new-smoking" style={{ marginBottom: '4px', fontSize: '14px' }}>Smoking Status</label>
            <select
              id="new-smoking"
              className="form-input"
              value={smokingStatus}
              onChange={e => setSmokingStatus(e.target.value)}
              required
            >
              <option value="">Select smoking status</option>
              <option value="non-smoker">Non-smoker</option>
              <option value="smoker">Smoker</option>
              <option value="ex-smoker">Ex-smoker</option>
            </select>
          </div>
          
          <button type="submit" className="btn primary" disabled={isCreating} style={{ width: '100%', marginTop: '10px' }}>
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