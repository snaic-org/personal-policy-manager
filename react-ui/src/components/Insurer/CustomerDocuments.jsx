import React, { useState, useEffect } from 'react';
import * as api from '../../services/api';
import FileDropzone from '../FileDropzone';
import FileDisplayList from '../FileDisplayList';

export default function CustomerDocuments({ customerId, files, onDataChanged }) {
  // State for the file list
  // const [files, setFiles] = useState([]);
  // const [listLoading, setListLoading] = useState(true);
  // const [listError, setListError] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // State for the new upload
  const [uploadFiles, setUploadFiles] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState('');
  const [uploadError, setUploadError] = useState(null);

  // const fetchFiles = async () => {
  //   setListLoading(true);
  //   setListError(null);
  //   try {
  //     const res = await api.getInsurerCustomerFiles(customerId);
  //     setFiles(res.files || []);
  //   } catch (err) {
  //     setListError(err.message);
  //   } finally {
  //     setListLoading(false);
  //   }
  // };

  // useEffect(() => {
  //   fetchFiles();
  // }, [customerId]);

  // --- Upload Handlers ---
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
      const res = await api.uploadForCustomer(customerId, uploadFiles);
      setUploadMessage(res.message);
      setUploadFiles([]);
      onDataChanged(); // <-- Refresh parent data
    } catch (err) {
      setUploadError(err.message);
    } finally {
      setIsUploading(false);
    }
  };

  // --- List Handlers (passed to FileDisplayList) ---
  const handleListDelete = async (filesToDelete) => {
    if (filesToDelete.length === 0) return;
    if (!window.confirm(`Delete ${filesToDelete.length} file(s) for this customer?`)) return;
    
    setIsDeleting(true);
    // setListError(null);
    try {
      await api.deleteForCustomer(customerId, filesToDelete);
      onDataChanged(); // Refresh parent data
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
    //   await api.downloadForCustomer(customerId, filename);
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
      <div style={{ borderTop: '1px solid #e0e0e0', paddingTop: '16px' }}>
        <FileDisplayList
          title="Uploaded Files for Customer"
          files={files} // <-- From props
          loading={false} // Loading is handled by parent
          error={null}    // Error is handled by parent
          isDeleting={isDeleting}
          emptyListMessage="No files uploaded for this customer."
          onDelete={handleListDelete}
          onDownload={handleListDownload}
        />
      </div>
    </div>
  );
}