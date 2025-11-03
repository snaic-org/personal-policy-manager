import React, { useEffect, useState } from 'react';
import { getUserFiles } from '../services/api';

export default function UploadedFiles({ refreshTrigger }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchFiles() {
      setLoading(true);
      try {
        const res = await getUserFiles();
        setFiles(res.files);
      } catch (err) {
        console.error('Error fetching files:', err);
      } finally {
        setLoading(false);
      }
    }
    fetchFiles();
  }, [refreshTrigger]); // refresh when upload succeeds

  return (
    <div style={{ padding: '10px 16px', borderTop: '1px solid #eee' }}>
      <h4>Your Uploaded Files</h4>
      {loading ? (
        <p>Loading...</p>
      ) : files.length === 0 ? (
        <p>No files uploaded yet.</p>
      ) : (
        <div>
          {files.map((file, i) => (
            <li key={i} className="file-list-item">
              <div>{file}</div>
              <div className="meta">{/* placeholder for date or size if available */}</div>
            </li>
            // <li key={i}>{file}</li>
          ))}
        </div>
      )}
    </div>
  );
}
