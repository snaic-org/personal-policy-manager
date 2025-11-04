import React, { useEffect, useState } from 'react';
import { getUserFiles, deletePolicies } from '../services/api';

export default function UploadedFiles({ refreshTrigger, onFileChange }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const [selectedFiles, setSelectedFiles] = useState(new Set());
  const [isDeleting, setIsDeleting] = useState(false);

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

  const handleSelect = (filename) => {
    const newSelection = new Set(selectedFiles);
    if (newSelection.has(filename)) {
      newSelection.delete(filename);
    } else {
      newSelection.add(filename);
    }
    setSelectedFiles(newSelection);
  };

  const handleSelectAll = () => {
    if (selectedFiles.size === files.length) {
      setSelectedFiles(new Set()); // Deselect all
    } else {
      setSelectedFiles(new Set(files)); // Select all
    }
  };

  const handleDeleteSelected = async () => {
    const filesToDelete = Array.from(selectedFiles);
    if (filesToDelete.length === 0) return;

    if (!window.confirm(`Are you sure you want to delete ${filesToDelete.length} file(s)? This will re-process your remaining documents.`)) {
      return;
    }
    
    setIsDeleting(true);
    setError(null);
    try {
      await deletePolicies(filesToDelete);
      onFileChange(); // Trigger refresh
      setSelectedFiles(new Set()); // Clear selection
    } catch (err) {
      console.error('Error deleting files:', err);
      setError(err.message);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="file-list-container">
      <div className="file-list-header">
        <h4>Your Uploaded Files</h4>
        {files.length > 0 && (
          <label className="file-list-select-all">
            <input 
              type="checkbox"
              onChange={handleSelectAll}
              checked={files.length > 0 && selectedFiles.size === files.length}
            />
            Select All
          </label>
        )}
      </div>

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
                <input
                  type="checkbox"
                  className="file-list-checkbox"
                  checked={selectedFiles.has(file)}
                  onChange={() => handleSelect(file)}
                />
                <span className={`file-icon ${fileType}`}>{fileType}</span>
                <span className="file-name" title={file}>{file}</span>
              </li>
            );
          })}
        </ul>
      )}
      
      {selectedFiles.size > 0 && (
        <button 
          className="btn danger" 
          onClick={handleDeleteSelected} 
          disabled={isDeleting}
          style={{ width: '100%', marginTop: '10px' }}
        >
          {isDeleting ? 'Deleting...' : `Delete ${selectedFiles.size} Selected File(s)`}
        </button>
      )}

      {error && <p className="form-error" style={{ margin: '10px 0 0' }}>{error}</p>}
    </div>
  );
}

// Helper function (you can keep this)
const getFileType = (filename) => {
  const ext = filename.split('.').pop().toLowerCase();
  if (ext === 'pdf') return 'pdf';
  if (ext === 'docx' || ext === 'doc') return 'doc';
  if (ext === 'txt' || ext === 'md') return 'txt';
  return 'file';
};