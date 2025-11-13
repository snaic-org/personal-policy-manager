import React, { useState } from 'react';
import { uploadPolicies } from '../services/api';
import FileDropzone from './FileDropzone';

export default function Upload({ onUploadSuccess }) {
  const [files, setFiles] = useState([]); // <-- This is passed to the dropzone
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const handleFilesSelected = (selected) => {
    setFiles(selected);
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
      setFiles([]); // <-- This will trigger the dropzone to reset
    }
  };

  return (
    <div className="upload-container">
      <h4>Upload Your Policies</h4>
      
      <FileDropzone
        id="global-file-input"
        onFilesSelected={handleFilesSelected}
        selectedFiles={files}
      />

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