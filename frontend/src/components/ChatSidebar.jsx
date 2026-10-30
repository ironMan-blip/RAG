import { MessageSquare, MessageSquarePlus, Sparkles, Trash2, X } from 'lucide-react';

export default function ChatSidebar({ open, sessions, activeId, onClose, onNewChat, onOpenChat, onDeleteChat }) {
  return (
    <>
      <div className={`sidebar-backdrop ${open ? 'open' : ''}`} onClick={onClose} />

      <aside className={`sidebar ${open ? 'open' : ''}`} aria-label="Chat history">
        <div className="sidebar-header">
          <div className="brand">
            <span className="brand-mark"><Sparkles size={16} /></span>
            Knowledge Assistant
          </div>
          <button onClick={onClose} className="icon-btn menu-btn" aria-label="Close sidebar">
            <X size={18} />
          </button>
        </div>
        <div className="sidebar-content">
          <button onClick={onNewChat} className="btn new-chat-btn">
            <MessageSquarePlus size={16} />
            New chat
          </button>
          <div className="sidebar-label">Recent</div>
          {sessions.length === 0 ? (
            <p className="sidebar-empty">Your conversations will appear here.</p>
          ) : (
            <ul className="chat-list">
              {sessions.map(session => (
                <li key={session.id} className={`chat-list-item ${session.id === activeId ? 'active' : ''}`}>
                  <button
                    className="chat-open-btn"
                    onClick={() => onOpenChat(session.id)}
                    aria-current={session.id === activeId ? 'true' : undefined}
                    title={session.name}
                  >
                    <MessageSquare size={15} />
                    <span>{session.name}</span>
                  </button>
                  <button className="icon-btn danger" onClick={() => onDeleteChat(session)} aria-label={`Delete ${session.name}`} title="Delete chat">
                    <Trash2 size={14} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>
    </>
  );
}
