import React from 'react';
import { downloadFile } from '../services/api';

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:5000';

/**
 * Handle citation click - fetch file with auth and open in new tab
 * Accepts an optional customerId for insurer requests.
 */
async function handleCitationClick(filename, customerId) {
  try {
    const token = localStorage.getItem('token');
    if (!token) {
      alert('Please log in to view files');
      return;
    }

    let url;
    if (customerId) {
      url = `${BASE}/api/data/files/${customerId}/${filename}`;
    } else {
      url = `${BASE}/files/${filename}`;
    }

    const response = await fetch(url, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Failed to load file' }));
      alert(error.error || 'Failed to load file');
      return;
    }

    const blob = await response.blob();
    const blobUrl = URL.createObjectURL(blob);
    const newWindow = window.open(blobUrl, '_blank');

    if (newWindow) {
      setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
    }
  } catch (error) {
    console.error('Error opening file:', error);
    alert('Failed to open file: ' + error.message);
  }
}

/**
 * Handle citation download
 * Accepts an optional customerId.
 */
async function handleCitationDownload(filename, customerId, event) {
  event.stopPropagation(); // Prevent triggering the view action
  try {
    await downloadFile(filename, customerId);
  } catch (error) {
    alert('Failed to download file: ' + error.message);
  }
}

/**
 * Parse text to find citations
 * Accepts and passes customerId to handlers.
 */
function parseTextWithCitations(text, customerId) {
  const citationRegex = /\[Source \d+: ([^,]+), Page (\d+)\]/g;
  const urlRegex = /(https:\/\/[^\s)]+)/g;
  
  const parts = [];
  let lastIndex = 0;
  let match;

  while ((match = citationRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.substring(lastIndex, match.index));
    }

    const filename = match[1];
    const citationText = match[0];

    parts.push(
      <span key={match.index} className="citation-wrapper">
        <a
          href="#"
          onClick={(e) => {
            e.preventDefault();
            handleCitationClick(filename, customerId);
          }}
          className="citation-link"
          title={`Open ${filename} in new tab`}
        >
          {citationText}
        </a>
        <button
          onClick={(e) => handleCitationDownload(filename, customerId, e)}
          className="citation-download-btn"
          title={`Download ${filename}`}
          aria-label={`Download ${filename}`}
        >
          ⬇
        </button>
      </span>
    );

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex));
  }
  
  const finalParts = [];
  parts.forEach((part, index) => {
    if (typeof part !== 'string') {
      finalParts.push(part);
      return;
    }
    
    let lastUrlIndex = 0;
    let urlMatch;
    while ((urlMatch = urlRegex.exec(part)) !== null) {
      if (urlMatch.index > lastUrlIndex) {
        finalParts.push(part.substring(lastUrlIndex, urlMatch.index));
      }
      const url = urlMatch[0];
      finalParts.push(
        <a href={url} target="_blank" rel="noopener noreferrer" key={`${index}-${lastUrlIndex}`}>
          {url}
        </a>
      );
      lastUrlIndex = urlMatch.index + url.length;
    }
    if (lastUrlIndex < part.length) {
      finalParts.push(part.substring(lastUrlIndex));
    }
  });

  return finalParts.length > 0 ? finalParts : text;
}


/**
 * Renders a block of text, converting Markdown
 * Accepts and passes customerId.
 */
function renderContentLines(contentBlock, customerId) {
  if (!contentBlock) return null;

  const lines = contentBlock.split('\n');
  const elements = [];
  let currentList = [];
  let currentListType = null; // 'ul' or 'ol'

  const flushList = () => {
    if (currentList.length > 0) {
      const ListTag = currentListType;
      elements.push(
        <ListTag key={`list-${elements.length}`} className="message-list">
          {currentList.map((item, li) => (
            <li key={li}>{parseTextWithCitations(item, customerId)}</li>
          ))}
        </ListTag>
      );
      currentList = [];
      currentListType = null;
    }
  };

  lines.forEach((line, index) => {
    const trimmedLine = line.trim();

    if (trimmedLine.startsWith('### ')) {
      flushList();
      elements.push(<p key={`h-${index}`}><strong>{parseTextWithCitations(trimmedLine.substring(4), customerId)}</strong></p>);
      return;
    }
    if (trimmedLine.startsWith('## ')) {
      flushList();
      elements.push(<p key={`h-${index}`}><strong>{parseTextWithCitations(trimmedLine.substring(3), customerId)}</strong></p>);
      return;
    }
    if (trimmedLine.startsWith('# ')) {
      flushList();
      elements.push(<p key={`h-${index}`}><strong>{parseTextWithCitations(trimmedLine.substring(2), customerId)}</strong></p>);
      return;
    }

    if (trimmedLine.startsWith('- ') || trimmedLine.startsWith('* ')) {
      if (currentListType !== 'ul') {
        flushList();
        currentListType = 'ul';
      }
      currentList.push(trimmedLine.substring(2));
      return;
    }
    
    const numberedListMatch = trimmedLine.match(/^(\d+)\.\s+(.*)/);
    if (numberedListMatch) {
      if (currentListType !== 'ol') {
        flushList();
        currentListType = 'ol';
      }
      currentList.push(numberedListMatch[2]);
      return;
    }

    if (trimmedLine === '---') {
      flushList();
      elements.push(<hr key={`hr-${index}`} className="message-divider" />);
      return;
    }

    if (trimmedLine) {
      flushList();
      const parts = trimmedLine.split(/(\*\*.*?\*\*)/g); 
      elements.push(
        <p key={`p-${index}`}>
          {parts.map((part, pi) => {
            if (part.startsWith('**') && part.endsWith('**')) {
              return <strong key={pi}>{parseTextWithCitations(part.slice(2, -2), customerId)}</strong>;
            }
            return parseTextWithCitations(part, customerId);
          })}
        </p>
      );
      return;
    }

    if (!trimmedLine) {
      flushList();
    }
  });

  flushList();
  return elements;
}

export default function MessageFormatter({ content, customerId = null }) {
  if (!content) {
    return <div className="formatted-message"></div>;
  }

  return (
    <div className="formatted-message">
      {renderContentLines(content, customerId)}
    </div>
  );
}