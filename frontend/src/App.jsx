import { useState, useRef, useEffect } from 'react';
import { ArrowUp, Bot, Sparkles, Paperclip, X, Library, ChevronDown, ChevronRight, Check, Cpu, MessageSquarePlus, MessageSquare, Menu, Trash2, FileText, Copy } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { API_BASE } from './api';
import ConfirmDialog from './ConfirmDialog';

// One segment per backend pipeline step, width proportional to its time
function TimingBar({ timings, total }) {
  return (
    <div className="timing">
      <div className="timing-bar" role="img" aria-label={`Reply took ${total} ms`}>
        {timings.map((t, i) => (
          <span key={i} className={`timing-seg seg-${i % 7}`} style={{ flexGrow: Math.max(t.ms, 1) }} title={`${t.step}: ${t.ms} ms`} />
        ))}
      </div>
      <div className="timing-legend">
        {timings.map((t, i) => (
          <span key={i}><i className={`seg-${i % 7}`} />{t.step} {t.ms} ms</span>
        ))}
        <span className="timing-total">Total {total} ms</span>
      </div>
    </div>
  )
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const copy = () => navigator.clipboard.writeText(text).then(() => {
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  });
  return (
    <button className="msg-action" onClick={copy} aria-label="Copy reply">
      {copied ? <Check size={14} /> : <Copy size={14} />}
      {copied ? 'Copied' : 'Copy'}
    </button>
  );
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
  const [openDetailsIdx, setOpenDetailsIdx] = useState(null);
  const [chatToDelete, setChatToDelete] = useState(null);
  const [suggestions, setSuggestions] = useState([]);

  const modelDropdownRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (modelDropdownRef.current && !modelDropdownRef.current.contains(event.target)) {
        setIsModelDropdownOpen(false);
      }
    }
    function handleEscape(event) {
      if (event.key !== 'Escape') return;
      setIsModelDropdownOpen(false);
      setIsSidebarOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  const chatBoxRef = useRef(null);
  const fileInputRef = useRef(null);

  const startNewChat = () => {
    setInputValue("");
    setSelectedFile(null);
    textareaRef.current?.focus();
    fetch(`${API_BASE}/chats`, { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        setChatId(data.session_id);
        setMessages(data.history);
        setSuggestions(data.suggestions);
        setOpenDetailsIdx(null);
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
    textareaRef.current?.focus();
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
          setOpenDetailsIdx(null);
          setIsSidebarOpen(false);
        }
      })
      .catch(err => console.error("Failed to load chat:", err));
  };

  const deleteChat = (id) => {
    setChatToDelete(null);
    fetch(`${API_BASE}/chats/${id}`, { method: 'DELETE' })
      .then(() => {
        fetchChatSessions();
        if (chatId === id) startNewChat();
      })
      .catch(err => console.error("Failed to delete chat:", err));
  };

  const sendMessage = async (override) => {
    const text = (override ?? inputValue).trim();
    if ((!text && !selectedFile) || isLoading) return;

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
        { text: "Couldn't reach the assistant. Check that the backend is running and try again.", sender: 'bot', error: true }
      ]);
    } finally {
      setIsLoading(false);
      textareaRef.current?.focus();
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      sendMessage();
    }
  };

  const currentTitle = chatSessions.find(s => s.id === chatId)?.name || 'New chat';
  // Until the user writes, the thread holds only the backend greeting; show a welcome instead
  const isFreshChat = !isLoading && !messages.some(m => m.sender === 'user');

  return (
    <div className="app-wrapper">
      <div className={`sidebar-backdrop ${isSidebarOpen ? 'open' : ''}`} onClick={() => setIsSidebarOpen(false)} />

      <aside className={`sidebar ${isSidebarOpen ? 'open' : ''}`} aria-label="Chat history">
        <div className="sidebar-header">
          <div className="brand">
            <span className="brand-mark"><Sparkles size={16} /></span>
            Knowledge Assistant
          </div>
          <button onClick={() => setIsSidebarOpen(false)} className="icon-btn menu-btn" aria-label="Close sidebar">
            <X size={18} />
          </button>
        </div>
        <div className="sidebar-content">
          <button onClick={() => { startNewChat(); setIsSidebarOpen(false); }} className="btn new-chat-btn">
            <MessageSquarePlus size={16} />
            New chat
          </button>
          <div className="sidebar-label">Recent</div>
          {chatSessions.length === 0 ? (
            <p className="sidebar-empty">Your conversations will appear here.</p>
          ) : (
            <ul className="chat-list">
              {chatSessions.map(session => (
                <li key={session.id} className={`chat-list-item ${session.id === chatId ? 'active' : ''}`}>
                  <button
                    className="chat-open-btn"
                    onClick={() => loadChat(session.id)}
                    aria-current={session.id === chatId ? 'true' : undefined}
                    title={session.name}
                  >
                    <MessageSquare size={15} />
                    <span>{session.name}</span>
                  </button>
                  <button className="icon-btn danger" onClick={() => setChatToDelete(session)} aria-label={`Delete ${session.name}`} title="Delete chat">
                    <Trash2 size={14} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>

      <div className="chat-container">
        <header className="chat-header">
          {/* Refetch on open: the backend saves a turn after replying, so the post-send fetch can miss it */}
          <button className="icon-btn menu-btn" onClick={() => { fetchChatSessions(); setIsSidebarOpen(true); }} aria-label="Open chat history" aria-expanded={isSidebarOpen}>
            <Menu size={20} />
          </button>
          <h1 className="chat-title">{currentTitle}</h1>
          <div className="header-actions">
            <div className="custom-dropdown" ref={modelDropdownRef}>
              <button
                className="btn dropdown-trigger"
                onClick={() => setIsModelDropdownOpen(!isModelDropdownOpen)}
                aria-haspopup="listbox"
                aria-expanded={isModelDropdownOpen}
                aria-label="Select model"
              >
                <Cpu size={15} />
                <span className="dropdown-label">
                  {availableModels.find(m => m.value === selectedModel)?.label || 'Select model'}
                </span>
                <ChevronDown size={15} className={`dropdown-arrow ${isModelDropdownOpen ? 'open' : ''}`} />
              </button>

              {isModelDropdownOpen && (
                <div className="dropdown-menu">
                  <div className="dropdown-header">Model</div>
                  <div className="dropdown-list" role="listbox">
                    {availableModels.length === 0 && <p className="dropdown-empty">No models available. Check that Ollama is running.</p>}
                    {availableModels.map(model => (
                      <button
                        key={model.value}
                        role="option"
                        aria-selected={selectedModel === model.value}
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
            <button className="btn" onClick={() => navigate('/admin')} title="Browse indexed documents">
              <Library size={15} />
              <span className="btn-label">Library</span>
            </button>
          </div>
        </header>

        <main className="chat-box" ref={chatBoxRef}>
          {isFreshChat ? (
            <section className="welcome">
              <span className="welcome-mark"><Sparkles size={22} /></span>
              <h2>What would you like to know?</h2>
              <p>Ask a question and the assistant answers from the documents in your library. Attach a file to ask about it directly.</p>
              <div className="suggestions">
                {suggestions.map(s => (
                  <button key={s} className="suggestion" onClick={() => sendMessage(s)}>
                    {s}
                    <ArrowUp size={14} />
                  </button>
                ))}
              </div>
              <button className="welcome-link" onClick={() => navigate('/admin')}>
                <Library size={14} />
                Manage documents in the library
              </button>
            </section>
          ) : (
            <div className="chat-thread" aria-live="polite">
              {messages.map((msg, idx) => (
                <div key={idx} className={`message-wrapper ${msg.sender}-wrapper`}>
                  {msg.sender === 'bot' && (
                    <div className="avatar" aria-hidden="true">
                      <Bot size={16} />
                    </div>
                  )}
                  <div className={`message ${msg.sender}-message ${msg.error ? 'error' : ''}`}>
                    {msg.sender === 'bot' ? (
                      <div className="markdown"><Markdown remarkPlugins={[remarkGfm]}>{msg.text}</Markdown></div>
                    ) : msg.text}
                    {msg.sender === 'bot' && !msg.error && idx > 0 && (
                      <div className="message-meta">
                        <div className="msg-actions">
                          <CopyButton text={msg.text} />
                          {(msg.prompt || msg.timings?.length > 0) && (
                            <button
                              className="msg-action details-toggle"
                              onClick={() => setOpenDetailsIdx(openDetailsIdx === idx ? null : idx)}
                              aria-expanded={openDetailsIdx === idx}
                            >
                              <ChevronRight size={14} />
                              Details
                              {msg.total_text && <span className="msg-time">{msg.total_text}</span>}
                            </button>
                          )}
                        </div>
                        {openDetailsIdx === idx && (
                          <div className="details-panel">
                            {msg.timings?.length > 0 && <TimingBar timings={msg.timings} total={msg.total_ms} />}
                            {msg.prompt && (
                              <>
                                <div className="section-label">Prompt sent to model</div>
                                <pre className="prompt-view">{msg.prompt}</pre>
                              </>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="message-wrapper bot-wrapper">
                  <div className="avatar" aria-hidden="true">
                    <Bot size={16} />
                  </div>
                  <div className="typing" role="status" aria-label="Assistant is thinking">
                    <span /><span /><span />
                  </div>
                </div>
              )}
            </div>
          )}
        </main>

        <footer className="chat-input-area">
          <div className="input-wrapper">
            <textarea
              ref={textareaRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="Ask about your documents..."
              aria-label="Message"
              autoComplete="off"
              autoFocus
              rows={1}
            />
            <div className="input-row">
              <input
                style={{ display: "none" }}
                type="file"
                ref={fileInputRef}
                onChange={handleFileSelect}
              />
              <button
                className="icon-btn"
                onClick={() => fileInputRef.current?.click()}
                title="Attach a file"
                aria-label="Attach a file"
              >
                <Paperclip size={18} />
              </button>
              {selectedFile && (
                <div className="file-chip">
                  <FileText size={14} />
                  <span title={selectedFile.name}>{selectedFile.name}</span>
                  <button className="icon-btn danger" onClick={() => setSelectedFile(null)} aria-label="Remove attachment">
                    <X size={14} />
                  </button>
                </div>
              )}
              <button
                className="send-btn"
                onClick={() => sendMessage()}
                disabled={isLoading || (!inputValue.trim() && !selectedFile)}
                aria-label="Send message"
              >
                <ArrowUp size={18} />
              </button>
            </div>
          </div>
          <p className="input-hint"><kbd>Enter</kbd> to send · <kbd>Shift</kbd> + <kbd>Enter</kbd> for a new line</p>
        </footer>
      </div>

      {chatToDelete && (
        <ConfirmDialog title="Delete conversation?" onConfirm={() => deleteChat(chatToDelete.id)} onCancel={() => setChatToDelete(null)}>
          <strong>{chatToDelete.name}</strong> will be permanently removed. This can't be undone.
        </ConfirmDialog>
      )}
    </div>
  );
}

export default App;
