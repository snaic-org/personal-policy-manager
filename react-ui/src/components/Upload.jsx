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
      <label htmlFor="file-input" className="btn secondary" style={{ display: 'inline-block', marginBottom: 8 }}>
        Choose Files
      </label>
      {files.length > 0 && (
        <ul style={{ paddingLeft: 20, color: '#444', fontSize: '0.95em' }}>
          {files.map((file, idx) => (
            <li key={idx}>{file.name}</li>
          ))}
        </ul>
      )}
      <input className="btn primary"
        id="file-input"
        type="file" 
        multiple 
        onChange={handleFileChange} 
        accept=".pdf,.docx,.txt,.md"
        style={{ display: 'none' }} // hide actual input
      />
      <button className="btn primary" onClick={handleUpload} disabled={loading}>
        {loading ? 'Processing...' : 'Upload & Process Files'}
      </button>

      {error && <p style={{ color: 'red', margin: '5px 0 0' }}>{error}</p>}
      {message && <p style={{ color: 'green', margin: '5px 0 0' }}>{message}</p>}
    </div>
  );
}