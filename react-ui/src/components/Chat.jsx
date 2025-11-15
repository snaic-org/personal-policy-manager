import React, { useState, useRef, useEffect } from 'react';
import { sendQueryStream, getHistory, clearHistory } from '../services/api';
import MessageFormatter from './MessageFormatter';

const TYPING_PLACEHOLDER = '...';

export default function Chat({ onUploadSuccess }) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const [refresh, setRefresh] = useState(false);

  useEffect(() => {
    setLoading(true);
    getHistory()
      .then(data => {
        setHistory(data);
      })
      .catch(err => {
        console.error("Failed to load history", err);
        addMessage('bot', `Error loading chat history: ${err.message}`);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  const addMessage = (role, content) => {
     setHistory(prev => [...prev, { role, content }]);
  };

  const handleUpload = () => {
     onUploadSuccess();
     addMessage('bot', 'Your documents have been processed. You can now ask questions about them.');
  };
  
  const handleUploadSuccess = () => {
     addMessage('bot', 'Your documents have been processed. You can now ask questions about them.');
     setRefresh(prev => !prev);
  };

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

  const handleSend = async () => {
    if (!query.trim()) return;
    setLoading(true);

    // Optimistically add user message to UI
    addMessage('user', query);
    const currentQuery = query; // Save query in case user types more
    setQuery('');
    resetTextareaHeight();

    const botMessageIndex = history.length + 1;
    addMessage('bot', '');

    try {
      let streamedContent = '';

      await sendQueryStream(
        currentQuery,
        (chunk) => {
          streamedContent += chunk;
          setHistory(prev => {
            const updated = [...prev];
            updated[botMessageIndex] = { role: 'bot', content: streamedContent };
            return updated;
          });
        },
        () => { setLoading(false); },
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

  const handleClearHistory = async () => {
    if (window.confirm('Are you sure you want to permanently delete your chat history?')) {
      try {
        await clearHistory();
        setHistory([]);
      } catch (err) {
        console.error("Failed to clear history", err);
        alert(`Failed to clear history: ${err.message}`);
      }
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
    <main className="chat-main">

      <div className="chat-header">
        <h3>Chat</h3>
        <button
          className="btn secondary"
          onClick={handleClearHistory}
          disabled={loading || history.length === 0}
          title="Clear chat history"
          style={{ height: '36px', padding: '0 16px', fontSize: '14px' }} 
        >
          Clear History
        </button>
      </div>

      <div className="chat-messages">
        {history.length === 0 && !loading && (
          <div className="empty-state">
            Welcome! Ask a question, or upload your policy documents using the sidebar.
          </div>
        )}
        {loading && history.length === 0 && (
          <div className="empty-state">Loading history...</div>
        )}
        {history.map((m, i) => {
          const header = m.role === 'user' ? 'You' : (m.role === 'insurer' ? 'Insurer' : 'Bot');
          return (
          <div key={i} className={`message ${m.role}`}>
            <div className="message-header">{m.role === 'user' ? 'You' : 'Bot'}</div>
            <div className="message-content">
              {m.role === 'user' ? (
                m.content
              ) :
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
        );
        })}
        <div ref={messagesEndRef} />
      </div>

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