import React from 'react';
import { downloadFile } from '../services/api';

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:5000';

/**
 * Handle citation click - fetch file with auth and open in new tab
 */
async function handleCitationClick(filename) {
  try {
    const token = localStorage.getItem('token');
    if (!token) {
      alert('Please log in to view files');
      return;
    }

    const response = await fetch(`${BASE}/files/${filename}`, {
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
async function handleCitationDownload(filename, event) {
  event.stopPropagation(); // Prevent triggering the view action
  try {
    await downloadFile(filename);
  } catch (error) {
    alert('Failed to download file: ' + error.message);
  }
}

/**
 * Parse text to find citations like [Source 1: filename.pdf, Page 5]
 * and convert them to clickable links
 */
function parseTextWithCitations(text) {
  // Regex for RAG citations: [Source 1: filename.pdf, Page 5]
  const citationRegex = /\[Source \d+: ([^,]+), Page (\d+)\]/g;
  
  // Regex for Markdown links (like sources in the report): - https://...
  const urlRegex = /(https:\/\/[^\s)]+)/g; // Escaped slashes

  const parts = [];
  let lastIndex = 0;

  // Combine regexes would be complex, so let's process citations first
  let match;
  while ((match = citationRegex.exec(text)) !== null) {
    // Add text before the citation
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
            handleCitationClick(filename);
          }}
          className="citation-link"
          title={`Open ${filename} in new tab`}
        >
          {citationText}
        </a>
        <button
          onClick={(e) => handleCitationDownload(filename, e)}
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

  // Add remaining text
  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex));
  }
  
  // Now, process all text parts for raw URLs (for the Sources list)
  const finalParts = [];
  parts.forEach((part, index) => {
    if (typeof part !== 'string') {
      finalParts.push(part); // It's already a React element (a citation)
      return;
    }
    
    // It's a string, so check for URLs
    let lastUrlIndex = 0;
    let urlMatch;
    while ((urlMatch = urlRegex.exec(part)) !== null) {
      // Add text before the URL
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
    
    // Add remaining text after the last URL
    if (lastUrlIndex < part.length) {
      finalParts.push(part.substring(lastUrlIndex));
    }
  });


  return finalParts.length > 0 ? finalParts : text;
}


/**
 * Renders a block of text, converting Markdown elements
 * (headings, lists, bold) into proper HTML.
 */
function renderContentLines(contentBlock) {
  if (!contentBlock) return null;

  const lines = contentBlock.split('\n');
  const elements = [];
  let currentList = [];
  let currentListType = null; // 'ul' or 'ol'

  // Helper to flush (render) the current list
  const flushList = () => {
    if (currentList.length > 0) {
      const ListTag = currentListType; // 'ul' or 'ol'
      elements.push(
        <ListTag key={`list-${elements.length}`} className="message-list">
          {currentList.map((item, li) => (
            // Apply citation parsing to each list item
            <li key={li}>{parseTextWithCitations(item)}</li>
          ))}
        </ListTag>
      );
      currentList = [];
      currentListType = null;
    }
  };

  lines.forEach((line, index) => {
    const trimmedLine = line.trim();

    // -------------------------------------------------
    // V V V THIS IS THE MODIFIED BLOCK V V V
    // -------------------------------------------------
    // 1. Check for Headings (render as bold paragraphs)
    if (trimmedLine.startsWith('### ')) {
      flushList(); // Render any pending list
      elements.push(<p key={`h-${index}`}><strong>{parseTextWithCitations(trimmedLine.substring(4))}</strong></p>);
      return;
    }
    if (trimmedLine.startsWith('## ')) {
      flushList();
      elements.push(<p key={`h-${index}`}><strong>{parseTextWithCitations(trimmedLine.substring(3))}</strong></p>);
      return;
    }
    if (trimmedLine.startsWith('# ')) {
      flushList();
      elements.push(<p key={`h-${index}`}><strong>{parseTextWithCitations(trimmedLine.substring(2))}</strong></p>);
      return;
    }
    // -------------------------------------------------
    // ^ ^ ^ END OF MODIFIED BLOCK ^ ^ ^
    // -------------------------------------------------

    // 2. Check for Bullet List ('- ' or '* ')
    if (trimmedLine.startsWith('- ') || trimmedLine.startsWith('* ')) {
      if (currentListType !== 'ul') { // If changing list type
        flushList();
        currentListType = 'ul';
      }
      currentList.push(trimmedLine.substring(2));
      return;
    }
    
    // 3. Check for Numbered List ('1. ')
    const numberedListMatch = trimmedLine.match(/^(\d+)\.\s+(.*)/);
    if (numberedListMatch) {
      if (currentListType !== 'ol') { // If changing list type
        flushList();
        currentListType = 'ol';
      }
      currentList.push(numberedListMatch[2]); // Just push the content
      return;
    }

    // 4. Check for Horizontal Rule
    if (trimmedLine === '---') {
      flushList();
      elements.push(<hr key={`hr-${index}`} className="message-divider" />);
      return;
    }

    // 5. Handle Paragraphs (non-empty lines)
    if (trimmedLine) {
      flushList(); // We're in a new paragraph, so flush any list
      
      // Handle **Bold** text within paragraphs
      const parts = trimmedLine.split(/(\*\*.*?\*\*)/g); 
      elements.push(
        <p key={`p-${index}`}>
          {parts.map((part, pi) => {
            if (part.startsWith('**') && part.endsWith('**')) {
              return <strong key={pi}>{parseTextWithCitations(part.slice(2, -2))}</strong>;
            }
            return parseTextWithCitations(part); // Also parse citations in non-bold parts
          })}
        </p>
      );
      return;
    }

    // 6. Handle Empty Lines
    if (!trimmedLine) {
      flushList(); // An empty line ends a list.
    }
  });

  // After the loop, flush any remaining list
  flushList();

  return elements;
}


export default function MessageFormatter({ content }) {
  if (!content) {
    return <div className="formatted-message"></div>;
  }

  // Render the entire content block
  return (
    <div className="formatted-message">
      {renderContentLines(content)}
    </div>
  );
}