import React, { useState, useEffect } from 'react';

// Helper function
const getFileType = (filename) => {
  const ext = filename.split('.').pop().toLowerCase();
  if (ext === 'pdf') return 'pdf';
  if (ext === 'docx' || ext === 'doc') return 'doc';
  if (ext === 'txt' || ext === 'md') return 'txt';
  return 'file';
};

export default function FileDisplayList({
  // Data props
  files = [],
  loading = false,
  error = null,
  isDeleting = false,
  
  // UI Props
  title,
  emptyListMessage = "No files found.",

  // Action Props (functions to call on parent)
  onDelete,
  onDownload
}) {
  const [selectedFiles, setSelectedFiles] = useState(new Set());

  // When the files list changes (e.g., after a delete),
  // clear the selection.
  useEffect(() => {
    setSelectedFiles(new Set());
  }, [files]);

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

  const handleDeleteClick = () => {
    // Pass the array of selected files to the parent
    // The parent will handle confirmation and API call
    if (onDelete) {
      onDelete(Array.from(selectedFiles));
    }
  };

  const handleDownloadClick = (filename) => {
    // Pass the specific file to the parent
    if (onDownload) {
      onDownload(filename);
    }
  };

  return (
    <div className="file-list-container">
      <div className="file-list-header">
        <h4>{title}</h4>
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
        <p className="file-list-message">{emptyListMessage}</p>
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
                <button
                  className="file-download-btn"
                  onClick={() => handleDownloadClick(file)}
                  title={`Download ${file}`}
                  aria-label={`Download ${file}`}
                >
                  ⬇
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {selectedFiles.size > 0 && (
        <button
          className="btn danger"
          onClick={handleDeleteClick}
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