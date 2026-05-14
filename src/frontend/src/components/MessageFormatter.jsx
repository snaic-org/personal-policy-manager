import React from 'react';
import { downloadFile } from '../services/api';

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Handle citation click - fetch file with auth and open in new tab
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
 */
async function handleCitationDownload(filename, customerId, event) {
  event.stopPropagation();
  try {
    await downloadFile(filename, customerId);
  } catch (error) {
    alert('Failed to download file: ' + error.message);
  }
}

/**
 * Parse text to find citations and links
 */
function parseTextWithCitations(text, customerId) {
  if (!text) return "";
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
 * Parse text for Bold formatting (**text**) and then Citations/Links
 */
function parseInlineFormatting(text, customerId) {
  if (!text) return null;
  // Split by bold syntax
  const parts = text.split(/(\*\*.*?\*\*)/g);

  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      // Remove the ** markers and parse content inside
      const content = part.slice(2, -2);
      return <strong key={`bold-${index}`}>{parseTextWithCitations(content, customerId)}</strong>;
    }
    // Parse regular text for citations
    return parseTextWithCitations(part, customerId);
  });
}

/**
 * Renders a block of text, converting Markdown (Headers, Lists, Tables)
 */
function renderContentLines(contentBlock, customerId) {
  if (!contentBlock) return null;

  const lines = contentBlock.split('\n');
  const elements = [];

  let currentList = [];
  let currentListType = null; // 'ul' or 'ol'
  let currentTable = [];

  // -- Flush Functions --

  const flushList = () => {
    if (currentList.length > 0) {
      const ListTag = currentListType;
      elements.push(
        <ListTag key={`list-${elements.length}`} className="message-list">
          {currentList.map((item, li) => (
            <li key={li}>{parseInlineFormatting(item, customerId)}</li>
          ))}
        </ListTag>
      );
      currentList = [];
      currentListType = null;
    }
  };

  const flushTable = () => {
    if (currentTable.length === 0) return;

    // Improved Table Separator Logic
    // A valid separator row contains only |, -, :, and whitespace, AND must have at least one dash.
    const rows = currentTable.filter(row => {
      const cleanRow = row.trim();
      // Remove all allowed separator chars
      const leftovers = cleanRow.replace(/[|:\-\s]/g, '');
      // If leftovers is empty (meaning only separator chars existed) AND it has a dash
      const isSeparator = leftovers.length === 0 && cleanRow.includes('-');
      return !isSeparator;
    });

    if (rows.length > 0) {
      // Helper to split a pipe-separated line into cells
      const parseRow = (r) => r.split('|').map(c => c.trim()).filter((c, i, arr) => {
        // Remove empty first/last cells if line starts/ends with pipe
        if (i === 0 && c === '' && r.trim().startsWith('|')) return false;
        if (i === arr.length - 1 && c === '' && r.trim().endsWith('|')) return false;
        return true;
      });

      const headerCols = parseRow(rows[0]);
      const bodyRows = rows.slice(1).map(r => parseRow(r));

      elements.push(
        <div key={`table-${elements.length}`} className="message-table-wrapper">
          <table className="message-table">
            <thead>
              <tr>
                {headerCols.map((h, i) => <th key={i}>{parseInlineFormatting(h, customerId)}</th>)}
              </tr>
            </thead>
            <tbody>
              {bodyRows.map((row, ri) => (
                <tr key={ri}>
                  {row.map((c, ci) => <td key={ci}>{parseInlineFormatting(c, customerId)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
    currentTable = [];
  };

  const flushAll = () => {
    flushList();
    flushTable();
  };

  // -- Line Processing Loop --
  // Using standard for-loop to allow "peeking" ahead
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmedLine = line.trim();

    // 1. Handle Tables
    if (trimmedLine.startsWith('|')) {
      flushList(); // Close any open list
      currentTable.push(trimmedLine);
      continue;
    }

    // If we were building a table but hit a non-pipe line, flush the table
    if (currentTable.length > 0) {
      flushTable();
    }

    // 2. Handle Headers
    if (trimmedLine.startsWith('### ')) {
      flushAll();
      elements.push(<h4 key={`h4-${i}`} className="msg-h4">{parseInlineFormatting(trimmedLine.substring(4), customerId)}</h4>);
      continue;
    }
    if (trimmedLine.startsWith('## ')) {
      flushAll();
      elements.push(<h3 key={`h3-${i}`} className="msg-h3">{parseInlineFormatting(trimmedLine.substring(3), customerId)}</h3>);
      continue;
    }
    if (trimmedLine.startsWith('# ')) {
      flushAll();
      elements.push(<h2 key={`h2-${i}`} className="msg-h2">{parseInlineFormatting(trimmedLine.substring(2), customerId)}</h2>);
      continue;
    }

    // 3. Handle Lists (Unordered)
    if (trimmedLine.startsWith('- ') || trimmedLine.startsWith('* ')) {
      if (currentListType !== 'ul') {
        flushAll();
        currentListType = 'ul';
      }
      currentList.push(trimmedLine.substring(2));
      continue;
    }

    // 4. Handle Lists (Ordered)
    const numberedListMatch = trimmedLine.match(/^(\d+)\.\s+(.*)/);
    if (numberedListMatch) {
      if (currentListType !== 'ol') {
        flushAll();
        currentListType = 'ol';
      }
      currentList.push(numberedListMatch[2]);
      continue;
    }

    // 5. Handle Divider
    if (trimmedLine === '---') {
      flushAll();
      elements.push(<hr key={`hr-${i}`} className="message-divider" />);
      continue;
    }

    // 6. Handle Empty Lines
    // FIX: If we are inside a list, check if the NEXT non-empty line is also a list item.
    // If so, do NOT flush. This keeps the list grouped together.
    if (!trimmedLine) {
      if (currentList.length > 0) {
        // Peek ahead
        let nextLineIsList = false;
        for (let j = i + 1; j < lines.length; j++) {
          const nextTrimmed = lines[j].trim();
          if (!nextTrimmed) continue; // Skip multiple empty lines

          // Check if next line matches current list type
          if (currentListType === 'ul' && (nextTrimmed.startsWith('- ') || nextTrimmed.startsWith('* '))) {
            nextLineIsList = true;
          } else if (currentListType === 'ol' && nextTrimmed.match(/^(\d+)\.\s+/)) {
            nextLineIsList = true;
          }
          break; // Only check the immediate next content line
        }

        if (nextLineIsList) {
          continue; // Just skip this empty line, don't flush
        }
      }

      // Otherwise, flush as normal
      flushAll();
      continue;
    }

    // 7. Handle Paragraphs / Plain Text
    flushAll();
    elements.push(
      <p key={`p-${i}`}>
        {parseInlineFormatting(trimmedLine, customerId)}
      </p>
    );
  }

  flushAll();
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