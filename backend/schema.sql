CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS source (
    uuid VARCHAR(255) PRIMARY KEY,
    source_name VARCHAR(255) NOT NULL
);

INSERT INTO source (uuid, source_name) 
VALUES 
    ('20a26963-d20c-469f-8837-620321d589a6', 'files attached from chat interface'),
    ('79279d88-e2c3-4a36-9da6-3f02dd71796b', 'files directly attached from library'),
    ('b8118424-5418-47b7-a661-8bb768aa8ef5', 'tools')
ON CONFLICT (uuid) DO NOTHING;

CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) UNIQUE NOT NULL,
    file_hash VARCHAR(255),
    source_id VARCHAR(255) REFERENCES source(uuid),
    session_id VARCHAR(255),
    metadata JSONB -- year, grade, subject, topic, subtopic
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id SERIAL PRIMARY KEY,
    doc_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    -- Dimension must match core/ml.py's embedder
    chunk_embedding vector(1024),
    metadata JSONB,
    previous_summary TEXT -- summary of the preceding chunk (replaces chunk overlap)
);

CREATE INDEX IF NOT EXISTS chunks_doc_id_idx ON chunks (doc_id);
-- Approximate nearest-neighbour search (<-> is L2 distance) for ORDER BY chunk_embedding <-> q LIMIT k.
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (chunk_embedding vector_l2_ops);

CREATE TABLE IF NOT EXISTS chats (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) DEFAULT 'New Chat',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_history (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) REFERENCES chats(id) ON DELETE CASCADE,
    user_message TEXT NOT NULL,
    bot_reply TEXT NOT NULL,
    model TEXT,
    prompt TEXT, -- full prompt (system + user) sent to the LLM for this turn
    timings JSONB, -- [{"step", "ms"}] per pipeline step, in order; for finding slow steps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Existing databases created before the prompt column
ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS prompt TEXT;
ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS timings JSONB;

-- Uploads still processing: the file plus every result finished so far, so a restart resumes instead of
-- starting over. A row is deleted when its document is saved (or processing fails).
CREATE TABLE IF NOT EXISTS upload_jobs (
    id VARCHAR(255) PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    source VARCHAR(255) NOT NULL, -- 'library' or 'tools'
    content BYTEA NOT NULL,
    content_type VARCHAR(255),
    chunks JSONB, -- extracted chunks; NULL until extraction finishes
    doc_metadata JSONB, -- tools only
    tags JSONB, -- per chunk, null entries not generated yet
    summaries JSONB, -- per chunk, null entries not generated yet
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS chat_history_session_idx ON chat_history (session_id, created_at);
