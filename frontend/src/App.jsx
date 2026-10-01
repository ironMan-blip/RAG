import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, MoreHorizontal, Sparkles, Paperclip, X, Database, ChevronDown, Check, Cpu, MessageSquarePlus, Menu, Trash2, Clock } from 'lucide-react';
import './App.css';
import DatabaseExplorer from './DatabaseExplorer';


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
  const [selectedModel, setSelectedModel] = useState("");
  const [availableModels, setAvailableModels] = useState([]);
  const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false);
  const [chatId, setChatId] = useState(crypto.randomUUID());
  const [chatSessions, setChatSessions] = useState([]);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const modelDropdownRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (modelDropdownRef.current && !modelDropdownRef.current.contains(event.target)) {
        setIsModelDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const chatBoxRef = useRef(null);
  const fileInputRef = useRef(null);

  const startNewChat = () => {
    setMessages([{ text: "Hello! I'm your AI assistant. How can I help you today?", sender: "bot" }]);
    setInputValue("");
    setSelectedFile(null);
    setChatId(crypto.randomUUID());
  };

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
    fetchChatSessions();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  useEffect(() => {
    fetch('http://localhost:8000/api/models')
      .then(res => res.json())
      .then(data => {
        if (data.models && data.models.length > 0) {
          setAvailableModels(data.models);
          setSelectedModel(data.models[0].value);
        }
      })
      .catch(err => console.error("Failed to fetch models:", err));
  }, []);


  const fetchChatSessions = () => {
    fetch('http://localhost:8000/api/chats')
      .then(res => res.json())
      .then(data => {
        if (data.chats) setChatSessions(data.chats);
      })
      .catch(err => console.error("Failed to fetch chats:", err));
  };

  const loadChat = (id) => {
    fetch(`http://localhost:8000/api/chats/${id}`)
      .then(res => res.json())
      .then(data => {
        if (data.history) {
          setChatId(id);
          const msgs = data.history.map(msg => ({ text: msg.text, sender: msg.role === 'user' ? 'user' : 'bot' }));
          setMessages(msgs.length ? msgs : [{ text: "Hello! I'm your AI assistant. How can I help you today?", sender: "bot" }]);
          setIsSidebarOpen(false);
        }
      })
      .catch(err => console.error("Failed to load chat:", err));
  };

  const deleteChat = (id, e) => {
    e.stopPropagation();
    fetch(`http://localhost:8000/api/chats/${id}`, { method: 'DELETE' })
      .then(() => {
        fetchChatSessions();
        if (chatId === id) startNewChat();
      })
      .catch(err => console.error("Failed to delete chat:", err));
  };

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
          attached_filename: attachedFilename,
          model: selectedModel,
          session_id: chatId
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      const botReply = data.reply || data.response || data.message || "No response field found in JSON.";
      
      fetchChatSessions();
      
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
      
      <div className={`sidebar ${isSidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <h3>Chat History</h3>
          <button onClick={() => setIsSidebarOpen(false)} className="close-btn">
            <X size={20} />
          </button>
        </div>
        <div className="sidebar-content">
          <button onClick={() => { startNewChat(); setIsSidebarOpen(false); }} className="new-chat-btn">
            <MessageSquarePlus size={16} />
            New Chat
          </button>
          <div className="chat-list">
            {chatSessions.map(session => (
              <div 
                key={session.id} 
                className={`chat-list-item ${session.id === chatId ? 'active' : ''}`}
                onClick={() => loadChat(session.id)}
              >
                <Clock size={16} className="history-icon" />
                <span className="chat-id" title={session.id}>{session.name || session.id.substring(0, 8) + '...'}</span>
                <button className="delete-btn" onClick={(e) => deleteChat(session.id, e)}>
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="chat-container">
        <header className="chat-header">
          <button className="menu-btn" onClick={() => setIsSidebarOpen(true)}>
            <Menu size={24} />
          </button>
          <div className="header-icon">
            <Sparkles size={24} color="#111111" />
          </div>
          <div className="header-info">
            <h2>AI Assistant</h2>
            <span className="status-indicator">
              <span className="dot"></span> Online
            </span>
          </div>
          <div className="header-actions" style={{ marginLeft: 'auto', display: 'flex', gap: '8px', alignItems: 'center' }}>
            <div className="custom-dropdown" ref={modelDropdownRef}>
              <button 
                className="dropdown-trigger" 
                onClick={() => setIsModelDropdownOpen(!isModelDropdownOpen)}
              >
                <Cpu size={16} className="dropdown-icon" />
                <span className="dropdown-label">
                  {availableModels.find(m => m.value === selectedModel)?.label || 'Select Model'}
                </span>
                <ChevronDown size={16} className={`dropdown-arrow ${isModelDropdownOpen ? 'open' : ''}`} />
              </button>
              
              {isModelDropdownOpen && (
                <div className="dropdown-menu">
                  <div className="dropdown-header">Available Models</div>
                  <div className="dropdown-list">
                    {availableModels.map(model => (
                      <button
                        key={model.value}
                        className={`dropdown-item ${selectedModel === model.value ? 'selected' : ''}`}
                        onClick={() => {
                          setSelectedModel(model.value);
                          setIsModelDropdownOpen(false);
                        }}
                      >
                        <span className="item-label">{model.label}</span>
                        {selectedModel === model.value && <Check size={16} className="check-icon" />}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
            <button 
              onClick={() => setShowDbModal(true)}
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
          <div className="input-wrapper" >
            <div className="file-actions" >
              <input style={{ display: "none" }} 
                type="file" 
                ref={fileInputRef} 
                 
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
