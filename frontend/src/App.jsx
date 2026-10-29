import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, MoreHorizontal, Sparkles, Paperclip, X, Library, ChevronDown, Check, Cpu, MessageSquarePlus, Menu, Trash2, Clock, Database } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import './App.css';
import { API_BASE } from './api';

// One segment per backend pipeline step, width proportional to its time
function TimingBar({ timings, total }) {
  return (
    <div className="timing" onClick={e => e.stopPropagation()}>
      <div className="timing-bar" role="img" aria-label={`Reply took ${total} ms`}>
        {timings.map((t, i) => (
          <span key={i} className={`timing-seg seg-${i % 7}`} style={{ flexGrow: Math.max(t.ms, 1) }} title={`${t.step}: ${t.ms} ms`} />
        ))}
      </div>
      <div className="timing-legend">
        {timings.map((t, i) => (
          <span key={i}><i className={`seg-${i % 7}`} />{t.step} {t.ms} ms</span>
        ))}
        <span className="timing-total">total {total} ms</span>
      </div>
    </div>
  )
}

function App() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [selectedModel, setSelectedModel] = useState("");
  const [availableModels, setAvailableModels] = useState([]);
  const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false);
  const [chatId, setChatId] = useState(null);
  const [chatSessions, setChatSessions] = useState([]);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [openPromptIdx, setOpenPromptIdx] = useState(null);

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
    setInputValue("");
    setSelectedFile(null);
    fetch(`${API_BASE}/chats`, { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        setChatId(data.session_id);
        setMessages(data.history);
        setOpenPromptIdx(null);
      })
      .catch(err => console.error("Failed to start chat:", err));
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
    startNewChat();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  useEffect(() => {
    fetch(`${API_BASE}/models`)
      .then(res => res.json())
      .then(data => {
        setAvailableModels(data.models);
        setSelectedModel(data.default || "");
      })
      .catch(err => console.error("Failed to fetch models:", err));
  }, []);


  const fetchChatSessions = () => {
    fetch(`${API_BASE}/chats`, { cache: 'no-store' })
      .then(res => res.json())
      .then(data => {
        if (data.chats) setChatSessions(data.chats);
      })
      .catch(err => console.error("Failed to fetch chats:", err));
  };

  const loadChat = (id) => {
    fetch(`${API_BASE}/chats/${id}`)
      .then(res => res.json())
      .then(data => {
        if (data.history) {
          setChatId(id);
          setMessages(data.history);
          setOpenPromptIdx(null);
          setIsSidebarOpen(false);
        }
      })
      .catch(err => console.error("Failed to load chat:", err));
  };

  const deleteChat = (id, e) => {
    e.stopPropagation();
    fetch(`${API_BASE}/chats/${id}`, { method: 'DELETE' })
      .then(() => {
        fetchChatSessions();
        if (chatId === id) startNewChat();
      })
      .catch(err => console.error("Failed to delete chat:", err));
  };

  const sendMessage = async () => {
    const text = inputValue.trim();
    if (!text && !selectedFile) return;

    // Show the raw input until the backend returns the stored version of this turn
    setMessages(prev => [...prev, { text: text || selectedFile.name, sender: 'user', pending: true }]);
    setInputValue("");
    
    const fileToUpload = selectedFile;
    setSelectedFile(null); // Clear selected file right away
    setIsLoading(true);

    try {
      const formData = new FormData();
      formData.append('message', text || "");
      if (selectedModel) formData.append('model', selectedModel);
      if (chatId) formData.append('session_id', chatId);
      if (fileToUpload) formData.append('file', fileToUpload);

      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        // Note: Do not set Content-Type header when using FormData, 
        // the browser will automatically set it to multipart/form-data with boundary
        body: formData
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setChatId(data.session_id);
      fetchChatSessions();
      setMessages(prev => [...prev.filter(m => !m.pending), ...data.messages]);
    } catch (error) {
      console.error('Error:', error);
      setMessages(prev => [
        ...prev.map(m => ({ ...m, pending: false })),
        { text: 'Sorry, there was an error processing your request.', sender: 'bot' }
      ]);
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
                <span className="chat-id" title={session.id}>{session.name}</span>
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
          {/* Refetch on open: the backend saves a turn after replying, so the post-send fetch can miss it */}
          <button className="menu-btn" onClick={() => { fetchChatSessions(); setIsSidebarOpen(true); }}>
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
              onClick={() => navigate('/admin')}
              title="View Library"
            >
              <Library size={16} />
              Library
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
              <div
                className={`message ${msg.sender}-message ${msg.prompt ? 'has-prompt' : ''}`}
                onClick={msg.prompt ? () => setOpenPromptIdx(openPromptIdx === idx ? null : idx) : undefined}
                title={msg.prompt ? 'Click to show the prompt the AI received' : undefined}
              >
                {msg.text}
                {openPromptIdx === idx && <pre className="prompt-view" onClick={e => e.stopPropagation()}>{msg.prompt}</pre>}
                {msg.timings?.length > 0 && <TimingBar timings={msg.timings} total={msg.total_ms} />}
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

        {/* Admin modal removed in favor of separate page */}

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
