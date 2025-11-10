import React, { useState, useEffect } from 'react';
import * as api from '../../services/api';

// Re-using file list styles from existing components
export default function CustomerDocuments({ customerId }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // For upload
  const [uploadFiles, setUploadFiles] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState('');

  const fetchFiles = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getInsurerCustomerFiles(customerId);
      setFiles(res.files || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchFiles();
  }, [customerId]);

  const handleFileChange = (e) => {
    setUploadFiles(Array.from(e.target.files));
  };

  const handleUpload = async () => {
    if (uploadFiles.length === 0) return;
    setIsUploading(true);
    setError(null);
    setUploadMessage('');
    try {
      const res = await api.uploadForCustomer(customerId, uploadFiles);
      setUploadMessage(res.message);
      setUploadFiles([]); // Clear selection
      fetchFiles(); // Refresh file list
    } catch (err) {
      setError(err.message);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (filename) => {
    if (!window.confirm(`Delete ${filename}?`)) return;
    setLoading(true);
    setError(null);
    try {
      await api.deleteForCustomer(customerId, [filename]);
      fetchFiles(); // Refresh file list
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '20px', overflowY: 'auto', height: '100%' }}>
      <div className="upload-container" style={{ marginBottom: '24px' }}>
        <h4>Upload Policies for Customer</h4>
        <input
          type="file"
          multiple
          onChange={handleFileChange}
          accept=".pdf,.docx,.txt,.md"
          style={{ display: 'block', marginBottom: '10px' }}
        />
        <button className="btn primary" onClick={handleUpload} disabled={isUploading || uploadFiles.length === 0}>
          {isUploading ? 'Uploading...' : `Upload ${uploadFiles.length} File(s)`}
        </button>
        {uploadMessage && <p className="form-message" style={{ margin: '10px 0 0' }}>{uploadMessage}</p>}
      </div>

      <div className="file-list-container" style={{ borderTop: '1px solid #e0e0e0', paddingTop: '16px' }}>
        <h4>Uploaded Files for Customer</h4>
        {loading && <p>Loading...</p>}
        {error && <p className="form-error">{error}</p>}
        
        {!loading && files.length === 0 ? (
          <p>No files uploaded for this customer.</p>
        ) : (
          <ul className="file-list">
            {files.map((file, i) => (
              <li key={i} className="file-list-item">
                <span className="file-name" title={file}>{file}</span>
                <button
                  className="file-delete-btn"
                  onClick={() => handleDelete(file)}
                  title={`Delete ${file}`}
                  style={{ background: '#fbebee', color: 'var(--danger-color)', border: '1px solid var(--danger-color)', borderRadius: '4px', padding: '4px 8px' }}
                >
                  Delete
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}