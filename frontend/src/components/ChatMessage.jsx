import { useState } from 'react';
import { Bot, Check, ChevronRight, Copy } from 'lucide-react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

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

export function BotAvatar() {
  return (
    <div className="avatar" aria-hidden="true">
      <Bot size={16} />
    </div>
  );
}

// showMeta: false for the greeting, which has no copy or details row
export default function ChatMessage({ msg, showMeta, detailsOpen, onToggleDetails }) {
  const isBot = msg.sender === 'bot';
  return (
    <div className={`message-wrapper ${msg.sender}-wrapper`}>
      {isBot && <BotAvatar />}
      <div className={`message ${msg.sender}-message ${msg.error ? 'error' : ''}`}>
        {isBot ? (
          <div className="markdown"><Markdown remarkPlugins={[remarkGfm]}>{msg.text}</Markdown></div>
        ) : msg.text}
        {isBot && !msg.error && showMeta && (
          <div className="message-meta">
            <div className="msg-actions">
              <CopyButton text={msg.text} />
              {(msg.prompt || msg.timings?.length > 0) && (
                <button className="msg-action details-toggle" onClick={onToggleDetails} aria-expanded={detailsOpen}>
                  <ChevronRight size={14} />
                  Details
                  {msg.total_text && <span className="msg-time">{msg.total_text}</span>}
                </button>
              )}
            </div>
            {detailsOpen && (
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
  );
}
