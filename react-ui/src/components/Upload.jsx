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
      onUploadSuccess(); // Notify chat and refresh file list
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
    <div className="upload-container">
      <h4>Upload Your Policies</h4>
      
      {/* This label acts as the drop zone */}
      <label 
        htmlFor="file-input" 
        className={`file-drop-zone ${files.length > 0 ? 'has-files' : ''}`}
      >
        {files.length === 0 ? (
          <span>Drag & drop files here, or click to select</span>
        ) : (
          <span>{files.length} file(s) selected</span>
        )}
      </label>
      
      <input
        id="file-input"
        type="file" 
        multiple 
        onChange={handleFileChange} 
        accept=".pdf,.docx,.txt,.md"
        style={{ display: 'none' }} // hide actual input
      />

      {/* Show upload button only when files are staged */}
      {files.length > 0 && (
        <button className="btn primary" onClick={handleUpload} disabled={loading} style={{ width: '100%', marginTop: '10px' }}>
          {loading ? 'Processing...' : `Upload ${files.length} File(s)`}
        </button>
      )}

      {error && <p className="form-error" style={{ margin: '10px 0 0' }}>{error}</p>}
      {message && <p className="form-message" style={{ margin: '10px 0 0' }}>{message}</p>}
    </div>
  );
}