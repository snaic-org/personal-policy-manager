import React, { useState } from 'react';
import { uploadPolicies } from '../services/api';

export default function Upload({ onUploadSuccess }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const handleFileChange = (e) => {
    setFiles(Array.from(e.target.files));
    setMessage('');
    setError('');
  };

  const handleUpload = async () => {
    if (files.length === 0) {
      setError('Please select one or more files to upload.');
      return;
    }
    setLoading(true);
    setError('');
    setMessage('');
    try {
      const res = await uploadPolicies(files);
      setMessage(res.message);
      onUploadSuccess(); // Notify chat to send a new message
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
      setFiles([]);
      // Clear the file input visually
      document.getElementById('file-input').value = null;
    }
  };

  return (
    <div style={{ padding: '10px 16px', borderTop: '1px solid #eee' }}>
      <h4>Upload Your Policies</h4>
      <input 
        id="file-input"
        type="file" 
        multiple 
        onChange={handleFileChange} 
        accept=".pdf,.docx,.txt,.md"
      />
      <button onClick={handleUpload} disabled={loading}>
        {loading ? 'Processing...' : 'Upload & Process Files'}
      </button>
      {error && <p style={{ color: 'red', margin: '5px 0 0' }}>{error}</p>}
      {message && <p style={{ color: 'green', margin: '5px 0 0' }}>{message}</p>}
    </div>
  );
}