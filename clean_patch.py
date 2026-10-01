import re

with open("frontend/src/App.jsx", "r") as f:
    content = f.read()

# Replace imports
content = content.replace("import { Send, Bot, User, MoreHorizontal, Sparkles, Paperclip, X, Database, ChevronDown, Check, Cpu, MessageSquarePlus } from 'lucide-react';",
"import { Send, Bot, User, MoreHorizontal, Sparkles, Paperclip, X, Database, ChevronDown, Check, Cpu, MessageSquarePlus, Menu, Trash2, Clock } from 'lucide-react';")


# Add states
content = content.replace("""  const [availableModels, setAvailableModels] = useState([]);
  const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false);
  const [chatId, setChatId] = useState(crypto.randomUUID());""", 
"""  const [availableModels, setAvailableModels] = useState([]);
  const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false);
  const [chatId, setChatId] = useState(crypto.randomUUID());
  const [chatSessions, setChatSessions] = useState([]);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);""")

# Add useEffect for fetching history
content = content.replace("""  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);""",
"""  useEffect(() => {
    fetchChatSessions();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);""")

# Add helper functions before sendMessage
helpers = """
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

  const sendMessage = async () => {"""

content = content.replace("  const sendMessage = async () => {", helpers)

# Update the fetch update line
content = content.replace("""      const data = await response.json();
      const botReply = data.reply || data.response || data.message || "No response field found in JSON.";
      
      setMessages(prev => [...prev, { text: botReply, sender: 'bot' }]);""",
"""      const data = await response.json();
      const botReply = data.reply || data.response || data.message || "No response field found in JSON.";
      
      fetchChatSessions();
      
      setMessages(prev => [...prev, { text: botReply, sender: 'bot' }]);""")

# Add Sidebar in JSX
sidebar = """      <div className={`sidebar ${isSidebarOpen ? 'open' : ''}`}>
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
                <span className="chat-id" title={session.id}>{session.id.substring(0, 8)}...</span>
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
          </button>"""

content = content.replace("""      <div className="chat-container">
        <header className="chat-header">""", sidebar)

with open("frontend/src/App.jsx", "w") as f:
    f.write(content)

