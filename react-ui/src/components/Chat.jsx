import React, { useState, useRef, useEffect } from 'react';
import { sendQuery } from '../services/api';
import MessageFormatter from './MessageFormatter';
import Upload from './Upload';

export default function Chat() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);
  const messagesEndRef = useRef(null);

  const addMessage = (role, text) => {
     setHistory(prev => [...prev, { role, text }]);
  };

  const handleSend = async () => {
    if (!query.trim()) return;
    setLoading(true);
    addMessage('user', query);
    setQuery('');
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
  
  const handleUploadSuccess = () => {
     addMessage('bot', 'Your documents have been processed. You can now ask questions about them.');
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
        {history.length === 0 && <div className="empty-state">
            Welcome! Ask a question, or upload your policy documents below.
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

      <div className="chat-input-fixed">
        <Upload onUploadSuccess={handleUploadSuccess} />
      
        <div className="chat-input-container">
          <div className="input-group">
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Ask a question about your policies..."
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