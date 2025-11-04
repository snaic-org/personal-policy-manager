import React, { useEffect, useState } from 'react';
import { getUserFiles, deletePolicy } from '../services/api';

// Helper function to get file type
const getFileType = (filename) => {
  const ext = filename.split('.').pop().toLowerCase();
  if (ext === 'pdf') return 'pdf';
  if (ext === 'docx' || ext === 'doc') return 'doc';
  if (ext === 'txt' || ext === 'md') return 'txt';
  return 'file';
};

// Small delete button component
const DeleteButton = ({ onClick, disabled }) => (
  <button onClick={onClick} disabled={disabled} className="file-delete-btn" title="Delete file">
    &times;
  </button>
);

export default function UploadedFiles({ refreshTrigger, onFileChange }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deleting, setDeleting] = useState(null);

  useEffect(() => {
    async function fetchFiles() {
      setLoading(true);
      setError(null);
      try {
        const res = await getUserFiles();
        setFiles(res.files || []);
      } catch (err) {
        console.error('Error fetching files:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    fetchFiles();
  }, [refreshTrigger]);

  const handleDelete = async (filename) => {
    if (!window.confirm(`Are you sure you want to delete "${filename}"? This will re-process all your documents.`)) {
      return;
    }
    setDeleting(filename);
    setError(null);
    try {
      await deletePolicy(filename);
      onFileChange(); // Trigger refresh in App.jsx
    } catch (err) {
      console.error('Error deleting file:', err);
      setError(err.message);
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="file-list-container">
      <h4>Your Uploaded Files</h4>
      {loading ? (
        <p className="file-list-message">Loading...</p>
      ) : files.length === 0 ? (
        <p className="file-list-message">No files uploaded yet.</p>
      ) : (
        <ul className="file-list">
          {files.map((file, i) => {
            const fileType = getFileType(file);
            return (
              <li key={i} className="file-list-item">
                <span className={`file-icon ${fileType}`}>{fileType}</span>
                <span className="file-name" title={file}>{file}</span>
                <DeleteButton 
                  onClick={() => handleDelete(file)}
                  disabled={deleting === file}
                />
              </li>
            );
          })}
        </ul>
      )}
      {error && <p className="form-error" style={{ margin: '10px 0 0' }}>{error}</p>}
    </div>
  );
}