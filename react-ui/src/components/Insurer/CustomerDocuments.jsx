import React, { useState, useEffect } from 'react';
import { uploadPolicies, deletePolicies } from '../../services/api';
import FileDropzone from '../FileDropzone';
import FileDisplayList from '../FileDisplayList';

export default function CustomerDocuments({ customerId, files, onDataChanged }) {
  const [isDeleting, setIsDeleting] = useState(false);

  const [uploadFiles, setUploadFiles] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState('');
  const [uploadError, setUploadError] = useState(null);

  const handleFilesSelected = (selected) => {
    setUploadFiles(selected);
    setUploadMessage('');
    setUploadError(null);
  };

  const handleUpload = async () => {
    if (uploadFiles.length === 0) return;
    setIsUploading(true);
    setUploadError(null);
    setUploadMessage('');
    try {
      const res = await uploadPolicies(uploadFiles, customerId);
      setUploadMessage(res.message);
      setUploadFiles([]);
      onDataChanged();
    } catch (err) {
      setUploadError(err.message);
    } finally {
      setIsUploading(false);
    }
  };

  const handleListDelete = async (filesToDelete) => {
    if (filesToDelete.length === 0) return;
    if (!window.confirm(`Delete ${filesToDelete.length} file(s) for this customer?`)) return;
    
    setIsDeleting(true);
    try {
      await deletePolicies(filesToDelete, customerId);
      onDataChanged();
    } catch (err) {
      setUploadError(err.message);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleListDownload = async (filename) => {
    // Assuming an API function exists. If not, this can be removed.
    // For now, it just logs to the console.
    console.log('Download requested for:', customerId, filename);
    setListError('Download is not implemented for customer files yet.');
    // try {
    //   await downloadForCustomer(customerId, filename);
    // } catch (err) {
    //   setListError(err.message);
    // }
  };

  return (
    <div style={{ padding: '20px', overflowY: 'auto', height: '100%' }}>
      
      {/* --- UPLOAD SECTION --- */}
      <div className="upload-container" style={{ marginBottom: '24px' }}>
        <h4>Upload Policies for Customer</h4>
        
        <FileDropzone
          id="customer-file-input"
          onFilesSelected={handleFilesSelected}
          selectedFiles={uploadFiles}
        />

        {uploadFiles.length > 0 && (
          <button className="btn primary" onClick={handleUpload} disabled={isUploading} style={{ width: '100%', marginTop: '10px' }}>
            {isUploading ? 'Uploading...' : `Upload ${uploadFiles.length} File(s)`}
          </button>
        )}

        {uploadError && <p className="form-error" style={{ margin: '10px 0 0' }}>{uploadError}</p>}
        {uploadMessage && <p className="form-message" style={{ margin: '10px 0 0' }}>{uploadMessage}</p>}
      </div>

      {/* --- FILE LIST SECTION --- */}
      <div>
        <FileDisplayList
          title="Uploaded Files for Customer"
          files={files}
          loading={false}
          error={null}
          isDeleting={isDeleting}
          emptyListMessage="No files uploaded for this customer."
          onDelete={handleListDelete}
          onDownload={handleListDownload}
        />
      </div>
    </div>
  );
}