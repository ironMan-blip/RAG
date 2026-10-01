import re

with open('frontend/src/App.jsx', 'r') as f:
    content = f.read()

# 1. Import updates
content = content.replace(
    "import { Send, Bot, User, MoreHorizontal, Sparkles, Paperclip, X, Database } from 'lucide-react';",
    "import { Send, Bot, User, MoreHorizontal, Sparkles, Paperclip, X, Database, ChevronDown, Check, Cpu } from 'lucide-react';"
)

# 2. Add state and ref for dropdown
state_code = """  const [availableModels, setAvailableModels] = useState([]);
  const [isModelDropdownOpen, setIsModelDropdownOpen] = useState(false);

  const modelDropdownRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (modelDropdownRef.current && !modelDropdownRef.current.contains(event.target)) {
        setIsModelDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);"""

content = content.replace("  const [availableModels, setAvailableModels] = useState([]);", state_code)


# 3. Replace the <select> with custom dropdown
select_code = """            <select 
              value={selectedModel} 
              onChange={(e) => setSelectedModel(e.target.value)}
              className="model-select"
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: '1px solid #ddd',
                backgroundColor: '#fff',
                fontSize: '14px',
                outline: 'none',
                cursor: 'pointer',
                fontFamily: 'inherit'
              }}
            >
              {availableModels.map(model => (
                <option key={model.value} value={model.value}>
                  {model.label}
                </option>
              ))}
            </select>"""

custom_dropdown_code = """            <div className="custom-dropdown" ref={modelDropdownRef}>
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
            </div>"""

content = content.replace(select_code, custom_dropdown_code)

with open('frontend/src/App.jsx', 'w') as f:
    f.write(content)

