import React, { useEffect, useState } from 'react';
import { getUserFiles, deletePolicies, downloadFile } from '../services/api';
import FileDisplayList from './FileDisplayList';

export default function UploadedFiles({ refreshTrigger, onFileChange }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
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

  const handleDelete = async (filesToDelete) => {
    if (filesToDelete.length === 0) return;

    if (!window.confirm(`Are you sure you want to delete ${filesToDelete.length} file(s)? This will re-process your remaining documents.`)) {
      return;
    }

    setIsDeleting(true);
    setError(null);
    try {
      await deletePolicies(filesToDelete);
      onFileChange();
    } catch (err) {
      console.error('Error deleting files:', err);
      setError(err.message);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleDownload = async (filename) => {
    try {
      await downloadFile(filename);
    } catch (err) {
      console.error('Error downloading file:', err);
      setError(err.message);
    }
  };

  return (
    <FileDisplayList
      title="Your Uploaded Files"
      files={files}
      loading={loading}
      error={error}
      isDeleting={isDeleting}
      emptyListMessage="No files uploaded yet."
      onDelete={handleDelete}
      onDownload={handleDownload}
    />
  );
}