import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, MoreHorizontal, Sparkles, Paperclip, X, Database, Layers } from 'lucide-react';
import './App.css';
import DatabaseExplorer from './DatabaseExplorer';
import ChunksExplorer from './ChunksExplorer';

const BACKEND_URL = 'http://localhost:8000/api/chat';
const UPLOAD_URL = 'http://localhost:8000/api/upload';
const DOCUMENTS_URL = 'http://localhost:8000/api/documents';

function App() {
  const [messages, setMessages] = useState([
    { text: "Hello! I'm your AI assistant. How can I help you today?", sender: "bot" }
  ]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [showDbModal, setShowDbModal] = useState(false);
  const [showChunksModal, setShowChunksModal] = useState(false);
  const chatBoxRef = useRef(null);
  const fileInputRef = useRef(null);

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (!file) return;
    setSelectedFile(file);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const scrollToBottom = () => {
    if (chatBoxRef.current) {
      chatBoxRef.current.scrollTop = chatBoxRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const sendMessage = async () => {
    const text = inputValue.trim();
    if (!text && !selectedFile) return;

    let finalMessage = text;

    // Display user message with attachment immediately
    let displayMessage = text;
    if (selectedFile) {
      displayMessage = text ? `[Attached File: ${selectedFile.name}]\n\n${text}` : `[Attached File: ${selectedFile.name}]`;
    }

    setMessages(prev => [...prev, { text: displayMessage, sender: 'user' }]);
    setInputValue("");
    
    const fileToUpload = selectedFile;
    
    setSelectedFile(null); // Clear selected file right away
    setIsLoading(true);

    try {
      let attachedFilename = null;
      if (fileToUpload) {
        // Upload the file first
        const formData = new FormData();
        formData.append('file', fileToUpload);
        
        const uploadRes = await fetch(UPLOAD_URL, {
          method: 'POST',
          body: formData,
        });

        if (!uploadRes.ok) throw new Error("File upload failed");
        const uploadData = await uploadRes.json();
        
        attachedFilename = uploadData.filename;
      }

      const response = await fetch(BACKEND_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          message: text || "",
          attached_filename: attachedFilename 
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      const botReply = data.reply || data.response || data.message || "No response field found in JSON.";
      
      setMessages(prev => [...prev, { text: botReply, sender: 'bot' }]);
    } catch (error) {
      console.error('Error:', error);
      setMessages(prev => [...prev, { text: 'Sorry, there was an error processing your request.', sender: 'bot' }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="app-wrapper">
      <div className="background-shapes">
        <div className="shape shape-1"></div>
        <div className="shape shape-2"></div>
      </div>
      
      <div className="chat-container">
        <header className="chat-header">
          <div className="header-icon">
            <Sparkles size={24} color="#fff" />
          </div>
          <div className="header-info">
            <h2>AI Assistant</h2>
            <span className="status-indicator">
              <span className="dot"></span> Online
            </span>
          </div>
          <div className="header-actions" style={{ marginLeft: 'auto', display: 'flex', gap: '8px' }}>
            <button 
              onClick={() => setShowChunksModal(true)}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'rgba(255,255,255,0.2)', border: 'none', color: '#fff', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '13px', fontWeight: 'bold' }}
              title="View Chunks"
            >
              <Layers size={16} />
              Chunks
            </button>
            <button 
              onClick={() => setShowDbModal(true)}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'rgba(255,255,255,0.2)', border: 'none', color: '#fff', padding: '6px 12px', borderRadius: '6px', cursor: 'pointer', fontSize: '13px', fontWeight: 'bold' }}
              title="View Database"
            >
              <Database size={16} />
              Database
            </button>
          </div>
        </header>

        <main className="chat-box" ref={chatBoxRef}>
          {messages.map((msg, idx) => (
            <div key={idx} className={`message-wrapper ${msg.sender}-wrapper`}>
              {msg.sender === 'bot' && (
                <div className="avatar bot-avatar">
                  <Bot size={18} />
                </div>
              )}
              <div className={`message ${msg.sender}-message`}>
                {msg.text}
              </div>
              {msg.sender === 'user' && (
                <div className="avatar user-avatar">
                  <User size={18} />
                </div>
              )}
            </div>
          ))}
          {isLoading && (
            <div className="message-wrapper bot-wrapper">
              <div className="avatar bot-avatar">
                <Bot size={18} />
              </div>
              <div className="message bot-message loading-message">
                <MoreHorizontal size={20} className="pulsing-dots" />
              </div>
            </div>
          )}
        </main>

        {showDbModal && (
          <DatabaseExplorer onClose={() => setShowDbModal(false)} documentsUrl={DOCUMENTS_URL} />
        )}

        {showChunksModal && (
          <ChunksExplorer onClose={() => setShowChunksModal(false)} />
        )}

        <footer className="chat-input-area">
          {selectedFile && (
            <div className="file-attachment-preview">
              <div className="file-info">
                <Paperclip size={14} />
                <span className="file-name">{selectedFile.name}</span>
              </div>
              <button className="remove-file-btn" onClick={() => setSelectedFile(null)}>
                <X size={14} />
              </button>
            </div>
          )}
          <div className="input-wrapper" style={{ position: 'relative' }}>
            <div className="file-actions" style={{ display: 'flex', gap: '8px' }}>
              <input 
                type="file" 
                ref={fileInputRef} 
                style={{ display: 'none' }} 
                onChange={handleFileSelect}
              />
              <button 
                className="upload-btn" 
                onClick={() => fileInputRef.current?.click()}
                title="Upload New File"
              >
                <Paperclip size={18} />
              </button>
            </div>

            <textarea 
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="Type your message..." 
              autoComplete="off"
              rows={1}
            />
            <button 
              className={`send-btn ${(inputValue.trim() || selectedFile) ? 'active' : ''}`} 
              onClick={sendMessage}
              disabled={!inputValue.trim() && !selectedFile}
            >
              <Send size={18} />
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}

export default App;
