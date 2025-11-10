import React, { useState, useRef, useEffect } from 'react';
import * as api from '../../services/api';
import MessageFormatter from '../MessageFormatter';

export default function CustomerChat({ customerId }) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    // Load this customer's chat history
    setLoading(true);
    api.getInsurerHistory(customerId)
      .then(setHistory)
      .catch(err => {
        addMessage('bot', `Error loading chat history: ${err.message}`);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [customerId]); // Re-fetch if customerId changes

  const addMessage = (role, content) => {
     setHistory(prev => [...prev, { role, content }]);
  };

  const handleSend = async () => {
    if (!query.trim()) return;
    setLoading(true);

    addMessage('user', query);
    const currentQuery = query;
    setQuery('');

    const botMessageIndex = history.length + 1;
    addMessage('bot', ''); // Add placeholder

    try {
      let streamedContent = '';
      await api.sendInsurerQueryStream(
        customerId,
        currentQuery,
        (chunk) => { // onChunk
          streamedContent += chunk;
          setHistory(prev => {
            const updated = [...prev];
            updated[botMessageIndex] = { role: 'bot', content: streamedContent };
            return updated;
          });
        },
        () => { // onComplete
          setLoading(false);
        },
        (error) => { // onError
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

  // --- Auto-resize and scroll logic (copy from your Chat.jsx) ---
  const handleInput = (e) => { /* ... */ };
  const resetTextareaHeight = () => { /* ... */ };
  const scrollToBottom = () => { /* ... */ };
  useEffect(scrollToBottom, [history]);
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };
  // --- End copy ---

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="chat-messages">
        {history.map((m, i) => (
          <div key={i} className={`message ${m.role}`}>
            <div className="message-header">{m.role === 'user' ? 'Insurer (You)' : 'Bot'}</div>
            <div className="message-content">
              {i === history.length - 1 && m.content === '' && loading ? (
                <div className="loading-indicator"><span></span><span></span><span></span></div>
              ) : (
                <MessageFormatter content={m.content} />
              )}
            </div>
          </div>
        ))}
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
            placeholder="Query this customer's policies..."
            onKeyDown={handleKeyDown}
          />
          <button className="btn primary" onClick={handleSend} disabled={loading}>
            {loading ? 'Sending...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  );
}