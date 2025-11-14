import React, { useState, useRef, useEffect } from 'react';

// You can keep the filter logic inside or move it to a prop
const ACCEPTED_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
  'text/markdown'
];

const isValidFile = (file) => {
  return ACCEPTED_TYPES.includes(file.type) ||
    file.name.endsWith('.pdf') ||
    file.name.endsWith('.docx') ||
    file.name.endsWith('.txt') ||
    file.name.endsWith('.md');
};

export default function FileDropzone({
  id = "file-drop-input",
  onFilesSelected,
  selectedFiles = [],
  accept = ".pdf,.docx,.txt,.md",
  multiple = true
}) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef(null);

  // This effect ensures that if the parent component clears the
  // 'selectedFiles' array (e.g., after an upload),
  // we reset the <input> element's value.
  useEffect(() => {
    if (selectedFiles.length === 0 && inputRef.current) {
      inputRef.current.value = null;
    }
  }, [selectedFiles]);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const filterAndPassFiles = (files) => {
    const validFiles = Array.from(files).filter(isValidFile);
    if (onFilesSelected) {
      onFilesSelected(validFiles);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFiles = e.dataTransfer.files;
    if (droppedFiles.length === 0) return;
    filterAndPassFiles(droppedFiles);
  };

  const handleFileChange = (e) => {
    const chosenFiles = e.target.files;
    if (chosenFiles.length === 0) return;
    filterAndPassFiles(chosenFiles);
  };

  return (
    <>
      <label
        htmlFor={id}
        className={`file-drop-zone ${selectedFiles.length > 0 ? 'has-files' : ''} ${isDragging ? 'is-dragging' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {isDragging ? (
          <span>Drop files here...</span>
        ) : selectedFiles.length === 0 ? (
          <span>Drag & drop files, or click to select</span>
        ) : (
          <span>{selectedFiles.length} file(s) selected</span>
        )}
      </label>
      <input
        ref={inputRef}
        id={id}
        type="file"
        multiple={multiple}
        onChange={handleFileChange}
        accept={accept}
        style={{ display: 'none' }}
      />
    </>
  );
}