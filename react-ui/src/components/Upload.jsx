import React, { useState } from 'react';
import { uploadPolicies } from '../services/api';

export default function Upload({ onUploadSuccess }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [isDragging, setIsDragging] = useState(false); // <-- ADDED: State for drag UI

  const handleFileChange = (e) => {
    const chosenFiles = Array.from(e.target.files);
    setFiles(chosenFiles);
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
      if (document.getElementById('file-input')) {
        document.getElementById('file-input').value = null;
      }
    }
  };

  // --- START: NEW DRAG-AND-DROP HANDLERS ---
  const handleDragOver = (e) => {
    e.preventDefault(); // Prevent browser from opening file
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault(); // Prevent browser from opening file
    setIsDragging(false);
    
    const droppedFiles = Array.from(e.dataTransfer.files);
    if (droppedFiles.length === 0) return;

    // Optional: Filter files by accepted types
    const acceptedTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain', 'text/markdown'];
    const validFiles = droppedFiles.filter(file => 
      acceptedTypes.includes(file.type) || 
      file.name.endsWith('.pdf') || 
      file.name.endsWith('.docx') || 
      file.name.endsWith('.txt') || 
      file.name.endsWith('.md')
    );

    setFiles(validFiles);
    setMessage('');
    setError('');
  };
  // --- END: NEW DRAG-AND-DROP HANDLERS ---

  return (
    <div className="upload-container">
      <h4>Upload Your Policies</h4>
      
      <label 
        htmlFor="file-input" 
        className={`file-drop-zone ${files.length > 0 ? 'has-files' : ''} ${isDragging ? 'is-dragging' : ''}`}
        onDragOver={handleDragOver}   // <-- ADDED
        onDragLeave={handleDragLeave} // <-- ADDED
        onDrop={handleDrop}           // <-- ADDED
      >
        {isDragging ? (
          <span>Drop files here...</span>
        ) : files.length === 0 ? (
          <span>Drag & drop files, or click to select</span>
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