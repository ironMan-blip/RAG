import { useState, useRef, useEffect } from 'react';
import { ArrowUp, Sparkles, Paperclip, X, Library, Menu, FileText, User } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import ChatMessage, { BotAvatar } from '../components/ChatMessage';
import ChatSidebar from '../components/ChatSidebar';
import ConfirmDialog from '../components/ConfirmDialog';
import ModelPicker from '../components/ModelPicker';
import UserDialog from '../components/UserDialog';

// The picked user is a per-browser convenience; storage can be unavailable (private mode)
const loadUser = () => { try { return JSON.parse(localStorage.getItem('user')); } catch { return null; } };
const saveUser = (u) => { try { localStorage.setItem('user', JSON.stringify(u)); } catch { /* not remembered */ } };

export default function ChatPage() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [selectedModel, setSelectedModel] = useState("");
  const [availableModels, setAvailableModels] = useState([]);
  const [chatId, setChatId] = useState(null);
  const [chatSessions, setChatSessions] = useState([]);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [openDetailsIdx, setOpenDetailsIdx] = useState(null);
  const [chatToDelete, setChatToDelete] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [user, setUser] = useState(loadUser);
  const [isUserDialogOpen, setIsUserDialogOpen] = useState(() => !loadUser());

  const textareaRef = useRef(null);
  const chatBoxRef = useRef(null);
  const fileInputRef = useRef(null);

  const fetchChatSessions = () => {
    api('/chats', { cache: 'no-store' })
      .then(data => setChatSessions(data.chats))
      .catch(err => console.error("Failed to fetch chats:", err));
  };

  const startNewChat = () => {
    setInputValue("");
    setSelectedFile(null);
    textareaRef.current?.focus();
    api('/chats', { method: 'POST' })
      .then(data => {
        setChatId(data.session_id);
        setMessages(data.history);
        setSuggestions(data.suggestions);
        setOpenDetailsIdx(null);
      })
      .catch(err => console.error("Failed to start chat:", err));
  };

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') setIsSidebarOpen(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    fetchChatSessions();
    startNewChat();
    api('/models')
      .then(data => {
        setAvailableModels(data.models);
        setSelectedModel(data.default || "");
      })
      .catch(err => console.error("Failed to fetch models:", err));
  }, []);

  useEffect(() => {
    if (chatBoxRef.current) chatBoxRef.current.scrollTop = chatBoxRef.current.scrollHeight;
  }, [messages, isLoading]);

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (!file) return;
    setSelectedFile(file);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    textareaRef.current?.focus();
  };

  const loadChat = (id) => {
    api(`/chats/${id}`)
      .then(data => {
        setChatId(id);
        setMessages(data.history);
        setOpenDetailsIdx(null);
        setIsSidebarOpen(false);
      })
      .catch(err => console.error("Failed to load chat:", err));
  };

  const deleteChat = (id) => {
    setChatToDelete(null);
    api(`/chats/${id}`, { method: 'DELETE' })
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

      // No Content-Type header: the browser sets multipart/form-data with its boundary
      const data = await api('/chat', { method: 'POST', body: formData });
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
      <ChatSidebar
        open={isSidebarOpen}
        sessions={chatSessions}
        activeId={chatId}
        onClose={() => setIsSidebarOpen(false)}
        onNewChat={() => { startNewChat(); setIsSidebarOpen(false); }}
        onOpenChat={loadChat}
        onDeleteChat={setChatToDelete}
      />

      <div className="chat-container">
        <header className="chat-header">
          {/* Refetch on open: the backend saves a turn after replying, so the post-send fetch can miss it */}
          <button className="icon-btn menu-btn" onClick={() => { fetchChatSessions(); setIsSidebarOpen(true); }} aria-label="Open chat history" aria-expanded={isSidebarOpen}>
            <Menu size={20} />
          </button>
          <h1 className="chat-title">{currentTitle}</h1>
          <div className="header-actions">
            <button className="btn" onClick={() => setIsUserDialogOpen(true)} title="Change user">
              <User size={15} />
              <span className="btn-label">{user ? `${user.name} · ${user.country}` : 'Select user'}</span>
            </button>
            <ModelPicker models={availableModels} value={selectedModel} onChange={setSelectedModel} />
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
                <ChatMessage
                  key={idx}
                  msg={msg}
                  showMeta={idx > 0}
                  detailsOpen={openDetailsIdx === idx}
                  onToggleDetails={() => setOpenDetailsIdx(openDetailsIdx === idx ? null : idx)}
                />
              ))}
              {isLoading && (
                <div className="message-wrapper bot-wrapper">
                  <BotAvatar />
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

      {isUserDialogOpen && (
        <UserDialog
          current={user}
          onSelect={(u) => { setUser(u); saveUser(u); setIsUserDialogOpen(false); }}
          onCancel={() => setIsUserDialogOpen(false)}
        />
      )}
      {chatToDelete && (
        <ConfirmDialog title="Delete conversation?" onConfirm={() => deleteChat(chatToDelete.id)} onCancel={() => setChatToDelete(null)}>
          <strong>{chatToDelete.name}</strong> will be permanently removed. This can't be undone.
        </ConfirmDialog>
      )}
    </div>
  );
}
