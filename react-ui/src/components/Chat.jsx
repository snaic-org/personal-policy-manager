import React, { useState, useRef, useEffect } from 'react';
import { sendQueryStream, getHistory } from '../services/api';
import MessageFormatter from './MessageFormatter';

const TYPING_PLACEHOLDER = '...'; // A constant for our placeholder

export default function Chat({ onUploadSuccess }) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null); // For auto-resize
  const [refresh, setRefresh] = useState(false); // Already exists, but wasn't used

  useEffect(() => {
    // Load chat history when component mounts
    setLoading(true);
    getHistory()
      .then(data => {
        setHistory(data); // Set the history from the database
      })
      .catch(err => {
        console.error("Failed to load history", err);
        // Add a local-only error message to the chat
        addMessage('bot', `Error loading chat history: ${err.message}`);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []); // Empty dependency array means this runs only once on mount

  const addMessage = (role, content) => {
     setHistory(prev => [...prev, { role, content }]);
  };

  // This function gets called by the Upload component via App.jsx
  const handleUpload = () => {
     onUploadSuccess(); // Let App.jsx know to refresh the file list
     addMessage('bot', 'Your documents have been processed. You can now ask questions about them.');
  };
  
  // This is passed to the Sidebar > Upload component
  const handleUploadSuccess = () => {
     addMessage('bot', 'Your documents have been processed. You can now ask questions about them.');
     setRefresh(prev => !prev); // triggers UploadedFiles to re-fetch
  };

  // Auto-resize logic
  const handleInput = (e) => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  };

  const resetTextareaHeight = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };
  // End auto-resize logic

  const handleSend = async () => {
    if (!query.trim()) return;
    setLoading(true);

    // Optimistically add user message to UI
    addMessage('user', query);
    const currentQuery = query; // Save query in case user types more
    setQuery('');
    resetTextareaHeight();

    // Add placeholder for bot message that will be updated as chunks arrive
    const botMessageIndex = history.length + 1; // User message was just added
    addMessage('bot', '');

    try {
      let streamedContent = '';

      await sendQueryStream(
        currentQuery,
        // onChunk: called for each content chunk
        (chunk) => {
          streamedContent += chunk;
          // Update the bot message with accumulated content
          setHistory(prev => {
            const updated = [...prev];
            updated[botMessageIndex] = { role: 'bot', content: streamedContent };
            return updated;
          });
        },
        // onComplete: called when streaming is done
        () => {
          setLoading(false);
        },
        // onError: called if there's an error
        (error) => {
          setHistory(prev => {
            const updated = [...prev];
            updated[botMessageIndex] = { role: 'bot', content: `Error: ${error.message}` };
            return updated;
          });
          setLoading(false);
        }
      );
    } catch (e) {
      setHistory(prev => {
        const updated = [...prev];
        updated[botMessageIndex] = { role: 'bot', content: `Error: ${e.message}` };
        return updated;
      });
      setLoading(false);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [history]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    // This 'main' tag is the main chat column
    <main className="chat-main">
      {/* This div handles the scrolling messages */}
      <div className="chat-messages">
        {history.length === 0 && !loading && (
          <div className="empty-state">
            Welcome! Ask a question, or upload your policy documents using the sidebar.
          </div>
        )}
        {loading && history.length === 0 && (
          <div className="empty-state">Loading history...</div>
        )}
        {history.map((m, i) => (
          <div key={i} className={`message ${m.role}`}>
            <div className="message-header">{m.role === 'user' ? 'You' : 'Bot'}</div>
            <div className="message-content">
              {m.role === 'user' ? (
                m.content
              ) :
              // Check if it's the last message, it's a bot,
              // content is empty, AND we are in the loading state.
              i === history.length - 1 && m.content === '' && loading ? (
                <div className="loading-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              ) : (
                <MessageFormatter content={m.content} />
              )
              }
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* This div is the input area, fixed to the bottom of the column */}
      <div className="chat-input-container">
        <div className="input-group">
          <textarea
            ref={textareaRef}
            rows={1}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onInput={handleInput}
            placeholder="Ask a question about your policies... (Shift+Enter for new line)"
            onKeyDown={handleKeyDown}
          />
          <button className="btn primary" onClick={handleSend} disabled={loading}>
            {loading ? 'Sending...' : 'Send'}
          </button>
        </div>
      </div>
    </main>
  );
}