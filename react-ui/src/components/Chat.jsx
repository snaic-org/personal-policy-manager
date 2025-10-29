import React, { useState, useRef, useEffect } from 'react';
import { sendQuery } from '../services/api';
import MessageFormatter from './MessageFormatter';

export default function Chat() {
  const [query, setQuery] = useState('');
  const [batch, setBatch] = useState('');
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const messagesEndRef = useRef(null);

  const handleSend = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const res = await sendQuery(query, batch || undefined);
      const text = res?.response ?? res?.error ?? 'No response';
      setHistory(prev => [...prev, { role: 'user', text: query }, { role: 'bot', text }]);
      setQuery('');
    } catch (e) {
      setHistory(prev => [...prev, { role: 'bot', text: `Error: ${e.message}` }]);
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

  return (
    <div className="chat-container">
      <div className="chat-messages">
        {history.length === 0 && <div className="empty-state">No messages yet.</div>}
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

      <div className="chat-input-fixed">
        <div className="chat-input-container">
          {/* <div className="batch-select">
            <label>
              Batch:{' '}
              <input value={batch} onChange={e => setBatch(e.target.value)} placeholder="batch-id" />
            </label>
          </div> */}

          <div className="input-group">
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Ask a question..."
              onKeyDown={e => { if (e.key === 'Enter') handleSend(); }}
            />
            <button onClick={handleSend} disabled={loading}>
              {loading ? 'Sending...' : 'Send'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
