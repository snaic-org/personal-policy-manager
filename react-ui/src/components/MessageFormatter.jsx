import React from 'react';

export default function MessageFormatter({ text }) {
  // Split text into sections based on numbered points (supports multi-digit numbers)
  const sections = text.split(/(?=^\s*\d+\.\s*\*\*)/m);

  return (
    <div className="formatted-message">
      {sections.map((section, i) => {
        // Extract title and content (supports multi-digit numbering)
        const titleMatch = section.match(/^\s*\d+\.\s*\*\*([^*]+)\*\*/m);
        const title = titleMatch ? titleMatch[1].trim() : '';
        const content = titleMatch ?
          section.replace(/^\s*\d+\.\s*\*\*[^*]+\*\*:?\s*/, '') :
          section;

        return (
          <div key={i} className="message-section">
            {title && <h3 className="section-title">{title}</h3>}
            <div className="section-content">
              {content.split('\n').map((line, j) => {
                if (line.trim().startsWith('-')) {
                  return <li key={j}>{line.replace('-', '').trim()}</li>;
                }
                return <p key={j}>{line}</p>;
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
