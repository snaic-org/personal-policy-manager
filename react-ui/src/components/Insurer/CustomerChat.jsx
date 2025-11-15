import React, { useState, useRef, useEffect } from 'react';
import { getHistory, sendQueryStream, clearHistory } from '../../services/api';
import MessageFormatter from '../MessageFormatter';

export default function CustomerChat({ customerId }) {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    setLoading(true);
    getHistory(customerId)
      .then(setHistory)
      .catch(err => {
        addMessage('bot', `Error loading chat history: ${err.message}`);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [customerId]);

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
        }, customerId
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
    if (window.confirm(`Are you sure you want to permanently delete this customer's chat history?`)) {
      try {
        await clearHistory(customerId);
        setHistory([]);
      } catch (err) {
        console.error("Failed to clear history", err);
        alert(`Failed to clear history: ${err.message}`);
      }
    }
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

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  useEffect(scrollToBottom, [history]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="chat-header">
        <h3>Customer Policies Query</h3>
        <button
          className="btn secondary"
          onClick={handleClearHistory}
          disabled={loading || history.length === 0}
          title="Clear this customer's chat history"
          style={{ height: '36px', padding: '0 16px', fontSize: '14px' }}
        >
          Clear History
        </button>
      </div>
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