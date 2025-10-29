import React from 'react';
import Chat from './components/Chat';

export default function App() {
  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', fontFamily: 'Arial, sans-serif' }}>
      <div className="app-header">
        <h2>Domain-Agnostic Chatbot</h2>
      </div>
      <Chat />
    </div>
  );
}
