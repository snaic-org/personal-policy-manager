import React, { useState, useRef, useEffect } from 'react';
import { sendQuery } from '../services/api';
import MessageFormatter from './MessageFormatter';

export default function Chat({ onUploadSuccess }) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null); // For auto-resize
  const [refresh, setRefresh] = useState(false); // Already exists, but wasn't used

  const addMessage = (role, text) => {
     setHistory(prev => [...prev, { role, text }]);
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
    addMessage('user', query);
    setQuery('');
    resetTextareaHeight(); // Reset textarea height
    try {
      const res = await sendQuery(query);
      const text = res?.response ?? res?.error ?? 'No response';
      addMessage('bot', text);
    } catch (e) {
      addMessage('bot', `Error: ${e.message}`);
    } finally {
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
        {history.length === 0 && <div className="empty-state">
            Welcome! Ask a question, or upload your policy documents using the sidebar.
        </div>}
        {history.map((m, i) => (
          <div key={i} className={`message ${m.role}`}>
            <div className="message-header">{m.role === 'user' ? 'You' : 'Bot'}</div>
            <div className="message-content">
              {m.role === 'bot' ? <MessageFormatter text={m.text} /> : m.text}
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