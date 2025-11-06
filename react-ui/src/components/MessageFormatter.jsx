import React from 'react';

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
      currentList.push(trimmedLine.replace('-', '').trim());
    } else {
      // Not a list item. First, push any existing list.
      if (currentList.length > 0) {
        elements.push(
          <ul key={`list-${index}`} className="message-list">
            {currentList.map((item, li) => (
              <li key={li}>{item}</li>
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
                 return <strong key={pi}>{part.slice(2, -2)}</strong>;
               }
               return part; // Return plain text
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
          <li key={li}>{item}</li>
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