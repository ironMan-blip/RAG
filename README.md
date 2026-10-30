# RAG
A basic AI assistant running on local models (Ollama) that uses RAG (Retrieval Augmented Generation): answers draw on an outside database of your documents that the model was not trained on.

It uses Jev (OpenRouter) to decide whether the AI needs additional context.

## Architecture

```mermaid
---
config:
  theme: base
  fontFamily: "Arial, Helvetica, sans-serif"
  themeVariables:
    fontFamily: "Arial, Helvetica, sans-serif"
    fontSize: 16px
    background: "#ffffff"
    lineColor: "#64748b"
    clusterBkg: "#f8fafc"
    clusterBorder: "#cbd5e1"
    edgeLabelBackground: "#ffffff"
  flowchart:
    curve: basis
    wrappingWidth: 280
    padding: 18
    nodeSpacing: 40
    rankSpacing: 55
---
flowchart TB
    subgraph add["&nbsp;&nbsp;&nbsp;<b>① INGESTION</b> · POST /upload&nbsp;&nbsp;&nbsp;"]
        direction LR
        A1(["📄 <b>File upload</b><br/>Library / Tools / Chat"])
        J1["⚙️ <b>Background job</b><br/>202 accepted · progress polled<br/>resumes after restart"]
        A2{"SHA-256<br/>unchanged?"}
        A3(["⏭️ Skip"])
        A4["✂️ <b>Chunking</b><br/>Docling + Tesseract OCR<br/>paragraph / list / table"]
        A5["🏷️ <b>Tagging</b> · qwen3:4b<br/>chunk tags + summaries<br/>doc metadata"]
        A6["🧭 <b>Embedding</b><br/>Qwen3-Embedding-0.6B<br/>1024-d vectors"]
        A1 --> J1 --> A2
        A2 -- yes --> A3
        A2 -- no --> A4 --> A5 --> A6
    end

    KB[("🗄️ <b>PostgreSQL + pgvector</b><br/>documents · chunks<br/>tags · vectors · summaries<br/>status: uploading / ready")]

    subgraph ask["&nbsp;&nbsp;&nbsp;<b>② CHAT</b> · POST /chat&nbsp;&nbsp;&nbsp;"]
        direction LR
        Q1(["💬 <b>User message</b><br/>+ last 5 turns"])
        Q2{"File<br/>attached?"}
        Q3{"<b>Jev</b><br/>OpenRouter<br/>needs context?"}
        Q4["📎 Scope:<br/>attached file"]
        Q5["📚 Scope:<br/>shared + session docs"]
        Q6["🔎 <b>Phase 1</b> · doc filter<br/>qwen3:4b query profile<br/>top 10 docs by metadata"]
        Q7["🎯 <b>Phase 2</b> · vector search<br/>cosine sim ≥ 0.7<br/>min 3 chunks"]
        Q8["🤖 <b>LLM</b> · Ollama<br/>qwen3:4b default<br/>excerpts + history prompt"]
        Q9(["✨ <b>Reply</b><br/>history + title saved"])
        Q1 --> Q2
        Q2 -- yes --> Q4
        Q2 -- no --> Q3
        Q3 -- yes --> Q5
        Q3 -- no --> Q8
        Q4 --> Q6
        Q5 --> Q6 --> Q7 --> Q8 --> Q9
    end

    subgraph legend["&nbsp;Legend&nbsp;"]
        direction LR
        L1(["Input / output"]) ~~~ L2{"Decision"} ~~~ L3["Model call"] ~~~ L4["Processing"] ~~~ L5[("Storage")]
    end

    add == store ==> KB
    KB == retrieve ==> ask
    ask ~~~ legend

    classDef io fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#14532d
    classDef step fill:#ffffff,stroke:#94a3b8,stroke-width:1.5px,color:#0f172a
    classDef ai fill:#ede9fe,stroke:#7c3aed,stroke-width:1.5px,color:#3b0764
    classDef choice fill:#fef3c7,stroke:#d97706,stroke-width:1.5px,color:#78350f
    classDef store fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#1e3a8a
    classDef skip fill:#f1f5f9,stroke:#94a3b8,stroke-dasharray:4 3,color:#475569

    class A1,Q1,Q9,L1 io
    class A4,J1,Q4,Q5,L4 step
    class A5,A6,Q6,Q7,Q8,L3 ai
    class A2,Q2,Q3,L2 choice
    class KB,L5 store
    class A3 skip
    style add fill:#f8fafc,stroke:#cbd5e1,stroke-width:1.5px,color:#334155
    style ask fill:#f8fafc,stroke:#cbd5e1,stroke-width:1.5px,color:#334155
    style legend fill:#ffffff,stroke:#e2e8f0,stroke-width:1px,color:#64748b
```

## How to run

### Prerequisites
- Python 3.9+, Node.js & npm
- PostgreSQL with the pgvector extension, running locally
- Ollama running locally with the models in `backend/.env` pulled: `ollama pull qwen3:4b` (one model serves chat and tagging)

### 1. Database
```bash
psql -U postgres -c "CREATE DATABASE rag;"
psql -U postgres -d rag -f backend/schema.sql
```
`backend/.env` connects with `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/rag`; adjust if your credentials differ.

### 2. Backend (FastAPI)
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```
API docs: `http://localhost:8001/docs`.

### 3. Frontend (React + Vite)
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173`.

### 4. Usage
Upload a file (PDF, text, or image) from the Library; it is processed and saved in PostgreSQL. Then chat with the assistant, which uses your documents as context.
