import React from 'react';

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

    // Get the file as a blob
    const blob = await response.blob();

    // Create a blob URL
    const blobUrl = URL.createObjectURL(blob);

    // Open in new tab
    const newWindow = window.open(blobUrl, '_blank');

    // Clean up the blob URL after a delay (to allow the file to load)
    if (newWindow) {
      setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
    }
  } catch (error) {
    console.error('Error opening file:', error);
    alert('Failed to open file: ' + error.message);
  }
}

/**
 * Parse text to find citations like [Source 1: filename.pdf, Page 5]
 * and convert them to clickable links
 */
function parseTextWithCitations(text) {
  const citationRegex = /\[Source \d+: ([^,]+), Page (\d+)\]/g;
  const parts = [];
  let lastIndex = 0;
  let match;

  while ((match = citationRegex.exec(text)) !== null) {
    // Add text before the citation
    if (match.index > lastIndex) {
      parts.push(text.substring(lastIndex, match.index));
    }

    // Add the citation as a clickable link
    const filename = match[1];
    const page = match[2];
    const citationText = match[0];

    parts.push(
      <a
        key={match.index}
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
    );

    lastIndex = match.index + match[0].length;
  }

  // Add remaining text after last citation
  if (lastIndex < text.length) {
    parts.push(text.substring(lastIndex));
  }

  return parts.length > 0 ? parts : text;
}

/**
 * A helper function to render a block of text, converting
 * paragraphs and bullet lists into proper HTML.
 */
function renderContentLines(contentBlock) {
  if (!contentBlock) return null;

  const lines = contentBlock.split('\n');
  const elements = [];
  let currentList = [];

  lines.forEach((line, index) => {
    const trimmedLine = line.trim();

    if (trimmedLine.startsWith('-')) {
      // If it's a list item, add to the current list
      const listItemText = trimmedLine.replace('-', '').trim();
      currentList.push({ text: listItemText, key: index });
    } else {
      // Not a list item. First, push any existing list.
      if (currentList.length > 0) {
        elements.push(
          <ul key={`list-${index}`} className="message-list">
            {currentList.map((item, li) => (
              <li key={li}>{parseTextWithCitations(item.text)}</li>
            ))}
          </ul>
        );
        currentList = []; // Reset the list
      }

      // Now, push the current paragraph (if it's not empty)
      if (trimmedLine) {
         // Check for **Bold** text and render it
         const parts = trimmedLine.split(/(\*\*.*?\*\*)/g); // Split by **bolded text**
         elements.push(
           <p key={`p-${index}`}>
             {parts.map((part, pi) => {
               if (part.startsWith('**') && part.endsWith('**')) {
                 return <strong key={pi}>{parseTextWithCitations(part.slice(2, -2))}</strong>;
               }
               return parseTextWithCitations(part); // Parse citations in plain text
             })}
           </p>
         );
      }
    }
  });

  // Push any remaining list items after the loop
  if (currentList.length > 0) {
    elements.push(
      <ul key={`list-end`} className="message-list">
        {currentList.map((item, li) => (
          <li key={li}>{parseTextWithCitations(item.text)}</li>
        ))}
      </ul>
    );
  }

  return elements;
}


export default function MessageFormatter({ content }) {
  if (!content) {
    return <div className="formatted-message"></div>;
  }

  // Split the entire message into main content and sources
  const [mainContent, ...sourcesParts] = content.split(/\n---\n/);
  const sourcesContent = sourcesParts.join('\n---\n'); // Re-join if multiple '---'

  // Process the main content sections (split by 1. **Title**)
  const sections = mainContent.split(/(?=^\s*\d+\.\s*\*\*)/m);

  return (
    <div className="formatted-message">
      {sections.map((section, i) => {
        // Find the title (e.g., "1. **Health Insurance (GREAT SupremeHealth):**")
        const titleMatch = section.match(/^\s*\d+\.\s*\*\*([^*]+)\*\*/m);
        const title = titleMatch ? titleMatch[1].trim() : '';
        
        // Get the content *after* the title
        const sectionContent = titleMatch ?
          section.replace(/^\s*\d+\.\s*\*\*[^*]+\*\*:?\s*/, '') :
          section;

        return (
          <div key={i} className="message-section">
            {title && <h3 className="section-title">{title}</h3>}
            <div className="section-content">
              {renderContentLines(sectionContent)}
            </div>
          </div>
        );
      })}

      {/* Render the Sources section if it exists */}
      {sourcesContent && (
        <>
          <hr className="message-divider" />
          <div className="message-section sources-section">
            {renderContentLines(sourcesContent)}
          </div>
        </>
      )}
    </div>
  );
}