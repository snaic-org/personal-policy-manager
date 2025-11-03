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

      {/* Hidden native file input - we use a styled label as the button */}
      <input
        id="file-input"
        type="file"
        multiple
        onChange={handleFileChange}
        accept=".pdf,.docx,.txt,.md"
        style={{ display: 'none' }}
      />

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
        {/* show selected file names or count */}
        <div style={{ marginLeft: 8, color: '#444', fontSize: '0.95em' }}>
          {files.length === 0 ? (
            <span style={{ color: '#888' }}>No file selected</span>
          ) : (
            <span>{files.length} file{files.length > 1 ? 's' : ''} selected</span>
          )}
        </div>
        
        <button htmlFor="file-input" className="btn secondary">
          Choose Files
        </button>

        <button className="btn primary" onClick={handleUpload} disabled={loading}>
          {loading ? 'Processing...' : 'Upload & Process'}
        </button>

      </div>

      {error && <p style={{ color: 'red', margin: '8px 0 0' }}>{error}</p>}
      {message && <p style={{ color: 'green', margin: '8px 0 0' }}>{message}</p>}
    </div>
  );
}