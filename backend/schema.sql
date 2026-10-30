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
    metadata JSONB, -- year, grade, subject, topic, subtopic
    -- 'uploading' while processing (hidden from search and the Library), 'ready' once saved
    status VARCHAR(20) NOT NULL DEFAULT 'ready' CHECK (status IN ('uploading', 'ready')),
    content BYTEA -- the uploaded file, kept while uploading so a restart can resume; NULL once ready
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id SERIAL PRIMARY KEY,
    doc_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    -- Dimension must match core/ml.py's embedder
    chunk_embedding vector(1024),
    metadata JSONB,
    previous_summary TEXT, -- summary of the preceding chunk (replaces chunk overlap)
    -- 'incomplete' while its tags/summary are still being generated (kept in metadata as each finishes), 'complete'
    -- once they are; a restart resumes incomplete chunks. Embedded when the whole document is saved.
    -- 'unfinished': saved, but its tags or previous summary failed every try; regenerated manually from the Library.
    status VARCHAR(20) NOT NULL DEFAULT 'complete' CHECK (status IN ('incomplete', 'complete', 'unfinished'))
);

-- Databases created before the status columns: add them, and drop the old in-progress uploads table
ALTER TABLE documents ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'ready'
    CHECK (status IN ('uploading', 'ready'));
ALTER TABLE documents ADD COLUMN IF NOT EXISTS content BYTEA;
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'complete'
    CHECK (status IN ('incomplete', 'complete', 'unfinished'));
DROP TABLE IF EXISTS upload_jobs;

CREATE INDEX IF NOT EXISTS chunks_doc_id_idx ON chunks (doc_id);
-- Approximate nearest-neighbour search for ORDER BY chunk_embedding <=> q LIMIT k; cosine ops to match
-- retrieval_service's <=> (cosine distance)
CREATE INDEX IF NOT EXISTS chunks_embedding_cosine_idx ON chunks USING hnsw (chunk_embedding vector_cosine_ops);

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

CREATE INDEX IF NOT EXISTS chat_history_session_idx ON chat_history (session_id, created_at);
